# EvoCanvas 安全评估报告

- **评估日期**：2026-08-20
- **评估范围**：`app/`（FastAPI 后端，194 个 .py）、`frontend/`（React 前端）、`pi-runtime/`（TS）
- **评估方式**：静态代码安全审计（手工 + 模式扫描），覆盖认证授权、注入、代码执行沙箱、路径穿越、凭据管理、依赖供应链
- **评估者**：腾讯安全专家（代码级审计；注：本环境无法直连腾讯内部安全 KB，通用加固项已标注 "General Advice"）

> 说明：本报告只描述风险与修复方案，**不提供完整攻击复现步骤或可直接利用的 payload**。

---

## 一、执行摘要

EvoCanvas 当前处于"迁移/开发期"，**安全控制基本处于占位或未生效状态**。最严重的问题是：**全站 API 没有任何真正的鉴权与授权闸门，且存在一条"匿名即可远程代码执行"的攻击链**。一旦部署到任何可达网络，攻击者可匿名创建任务、触发 `codex exec` 在宿主机项目根目录执行模型生成（可控）代码，并读取全部环境变量（含密钥）。

| 风险等级 | 数量 | 代表性问题 |
|---|---|---|
| 🔴 Critical | 3 | 全站无鉴权/无授权；匿名 RCE 链；硬编码管理员令牌 |
| 🟠 High | 3 | Codex 透传全部环境变量；子进程沙箱隔离不足；路径穿越 |
| 🟡 Medium | 3 | 网关密钥 fail-open 回退；API Key 空串默认；CORS 过宽 |
| 🔵 Low | 3 | 前端 innerHTML；日志可能泄露路径；依赖版本异常 |

**优先修复顺序**：先止血（鉴权 + 关闭匿名 RCE 链），再做隔离与密钥治理，最后依赖与配置加固。

---

## 二、详细发现与修复

### 🔴 [Critical] C1 — 全站 API 无鉴权且无授权（CWE-306 / CWE-862）

**位置**：`app/api/auth.py`（定义但未接入）、`app/api/server.py`（全部路由仅依赖 `get_task_service`，其内的 `get_current_user` 结果被丢弃）

**问题**：
- `get_current_user` 从未作为任何路由的鉴权依赖被接入。路由只通过 `get_task_service → get_tenant_workspace → get_current_user` 间接调用它，但返回的 `User/role` 既未被校验，也未传递给路由。
- `RolePolicy.check_access()` 在代码中被定义，**但全仓库无任何调用点**——IAM 角色白名单形同虚设。
- 后果：所有 `POST/PUT/DELETE/GET` 的 `/api/*`（含任务创建、产物、材料、知识库、画布、回收站等 20+ 写/删端点）以及 `/internal/v1/tool-calls` 均**匿名可达**。

**修复**：把 `get_current_user` 作为真正的路由依赖；对写/删/内部接口强制要求已认证用户；用 `RolePolicy` 校验工具/端点权限；默认拒绝（白名单）。

```python
# app/api/auth.py —— 用签名令牌替换明文比较，默认拒绝匿名
import hmac, hashlib, os, time
from fastapi import Depends, HTTPException, Header

_AUTH_SECRET = os.getenv("EVO_API_TOKEN_SECRET")
if not _AUTH_SECRET:
    raise RuntimeError("EVO_API_TOKEN_SECRET 未配置，拒绝启动（fail-closed）")

def verify_token(token: str) -> dict:
    # 推荐改为 HS256 JWT；此处用 HMAC 防时序攻击的示例
    try:
        raw, sig = token.rsplit(".", 1)
    except ValueError:
        raise HTTPException(401, "invalid token")
    expected = hmac.new(_AUTH_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(401, "invalid token")
    # raw 中可编码 user_id/role/exp，解析并校验过期
    ...
    return payload

def get_current_user(x_api_token: str = Header(None, alias="X-API-Token")) -> User:
    if not x_api_token:
        raise HTTPException(401, "authentication required")   # 不再匿名兜底
    payload = verify_token(x_api_token)
    return User(user_id=payload["uid"], role=payload["role"], tenant_id=payload["tid"])
```

路由侧强制：

```python
@app.post("/api/tasks")
async def create_task(req: CreateTaskRequest,
                      user: User = Depends(get_current_user),
                      service: TaskService = Depends(get_task_service)):
    if not RolePolicy.check_access(user.role, "task.create"):
        raise HTTPException(403, "forbidden")
    ...
```

---

### 🔴 [Critical] C2 — 匿名远程代码执行链（CWE-78 / CWE-94 / CWE-306）

**位置**：`app/api/server.py:703` `create_task` + `server.py:775` `dispatch_peer_collaboration` → `task_service.start_peer_collaboration` → `peer_adapter.dispatch` → `app/services/codex_cli_handler.py:CodexCLIHandler.execute` → `subprocess.run(["codex", "exec", ..., "-s", "workspace-write", "-a", "never", "-C", project_root])`

**问题（攻击链，无需任何凭据）**：
1. `POST /api/tasks` 匿名创建任务，请求体可携带恶意 agent package（代码/指令）。
2. `POST /api/tasks/{id}/peer-dispatch` 匿名触发派发。
3. `CodexCLIHandler` 以 `approval_policy="never"`（自动批准全部操作）、`workspace_root=project_root`（**整个项目目录可写**）执行 `codex exec`。
4. `_default_runner` 将 **完整 `os.environ`** 透传给该子进程（见 H1），执行的是模型/攻击者可控的生成代码。

这是一条从"匿名 HTTP 请求"到"宿主机代码执行 + 源码篡改 + 密钥外泄"的完整链路。

**修复**：
- 该端点必须置于强认证 + 显式人工审批之后，**绝不允许匿名**。
- `approval_policy` 改为需审批（如 `"on-failure"` 或显式 `--ask-for-approval`），禁止 `never`。
- `workspace_root` 限制为**隔离的沙箱副本目录**，绝不直接指向项目根（`project_root`）。
- 见 H1：不要透传完整环境变量。

```python
# server.py —— 至少做到：鉴权 + 审批 + 隔离 workspace
@app.post("/api/tasks/{task_id}/peer-dispatch")
async def dispatch_peer_collaboration(
    task_id: str,
    payload: Dict[str, Any] = Body(default={}),
    user: User = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
):
    if not RolePolicy.check_access(user.role, "peer.dispatch"):
        raise HTTPException(403, "forbidden")
    if not payload.get("approved_by_human"):      # 显式人工审批闸门
        raise HTTPException(400, "peer dispatch requires explicit approval")
    ...
```

```python
# codex_cli_handler.py —— 缩小 workspace + 审批 + 白名单 env
def __init__(self, workspace_root: Path, codex_path="codex",
             approval_policy: str = "on-failure",   # 默认不再 'never'
             sandbox_mode: str = "read-only", ...): ...
```

---

### 🔴 [Critical] C3 — 硬编码管理员令牌（CWE-798）

**位置**：`app/api/auth.py:74` `if x_api_token == "test-admin-token":`

**问题**：存在可猜解的硬编码管理员令牌，任何人发送 `X-API-Token: test-admin-token` 即获得 `role="admin"`（`allowed_tools=["*"]`）。即使 C1 修复后，该令牌仍是一个后门。

**修复**：立即删除该分支；所有令牌由服务端签发并签名（见 C1）；上线前轮换任何曾使用该令牌的环境。

---

### 🟠 [High] H1 — Codex 子进程透传完整环境变量（CWE-200 / CWE-522）

**位置**：`app/services/codex_cli_handler.py:143` `env = dict(os.environ)`

**问题**：运行模型生成代码的 `codex` 子进程拿到**全部**环境变量，包括 `API_KEY`、`PI_RUNTIME_INTERNAL_SECRET`、`PI_TOOL_GATEWAY_SECRET` 等密钥，存在被生成代码外泄的风险。

**修复**：仅显式注入白名单变量，且剥离一切密钥。

```python
ALLOWED_ENV = {"PATH", "HOME", "LANG", "TMPDIR", "PYTHONUNBUFFERED"}
env = {k: v for k, v in os.environ.items() if k in ALLOWED_ENV}
env["CODEX_HOME"] = str(self.codex_home)   # 仅此新增
```

---

### 🟠 [High] H2 — 子进程沙箱隔离不足（CWE-265）

**位置**：`app/services/sandbox/adapters/subprocess_adapter.py`、`app/services/sandbox/manager.py`

**问题**：
- `network_disabled=True` 仅清空 `HTTP_PROXY/HTTPS_PROXY`，**代码注释已承认"原生子进程无法强行断网"**——沙箱内脚本仍可直连外网（数据外泄 / 访问内网）。
- `RLIMIT_AS` 仅在 Linux 生效；**开发者 macOS 环境无任何内存限制**，OOM 防护失效。
- 子进程与服务器同 OS 用户运行，可读写宿主任意可达文件（源码、`.env`、密钥文件），无 user namespace / seccomp / chroot。

**修复**：生产环境强制使用 `DockerSandboxAdapter`（或 gVisor / Firecracker）；若保留 subprocess 兜底，必须：以**专用低权限用户**运行、启用 seccomp、跨平台内存限制、通过防火墙/网络命名空间**真正阻断出网**，并使 `network_disabled` 名副其实。

---

### 🟠 [High] H3 — 持久化路径穿越（CWE-22）

**位置**：`app/services/fakes.py:145` `path = self.root / "tasks" / task_id`

**问题**：`task_id` 来自 URL 路径参数且**未净化**，直接拼入文件系统路径。结合全站无鉴权，攻击者可构造 `task_id=../..` 越目录读写 `task.json` 等文件。

**修复**：对 `task_id` 套用与 `tenant_id` 相同的安全正则（或在存储层统一净化）。

```python
import re
def _safe_id(value: str) -> str:
    if not re.match(r'^[A-Za-z0-9_-]+$', value or ""):
        raise ValueError("invalid id")
    return value
# 在 _task_dir / load_task / write_artifact 入口统一调用 _safe_id(task_id)
```

---

### 🟡 [Medium] M1 — 网关签名密钥 fail-open 回退（CWE-345）

**位置**：`app/api/server.py:91` `secret = os.getenv("PI_TOOL_GATEWAY_SECRET") or f"evocanvas-tool-gateway:{tenant_id}:{uuid4().hex}"`

**问题**：未配置时回退为进程内随机密钥。由于独立运行的 Pi Runtime 无法获知该随机值，内部工具网关的令牌签名实际上**失效/不可用**，构成 fail-open（要么全部拒绝、要么形同无签名校验）。

**修复**：缺失关键共享密钥时**拒绝启动**（fail-closed），并确保网关与 Pi Runtime 共享同一来自密钥管理的密钥。

---

### 🟡 [Medium] M2 — API Key 空串默认 + 启动不校验（CWE-1188）

**位置**：`app/api/server.py:214` `api_key = os.getenv("API_KEY") or os.getenv("CRS_OAI_KEY") or ""`

**问题**：未配置时为空串；`BASE_URL` 可指向任意内部网关。若内部网关无鉴权，将发生未授权 LLM 调用；且缺密钥时不在启动期报错，隐患隐蔽。

**修复**：启动期校验必填密钥；`BASE_URL` 列入白名单/显式配置，禁止默认指向未知端点。

---

### 🟡 [Medium] M3 — CORS 配置偏宽（CWE-942）

**位置**：`app/api/server.py:301` `allow_credentials=True` + `allow_methods=["*"]` + `allow_headers=["*"]`

**问题**：origin 虽为固定列表（非 `*`），但方法/头部全放开且与凭据共用。在缺乏鉴权时影响有限，但一旦接入认证，过宽的 CORS 会放大 CSRF/凭证暴露面。

**修复**：`allow_methods`/`allow_headers` 收窄到实际所需；定期复核 origin 列表，移除不再使用的本地端口。

---

### 🔵 [Low] L1 — 前端 `root.innerHTML`（CWE-79 风险点）

**位置**：`frontend/src/main.jsx:16,33` `root.innerHTML = \`...\``

**说明**：当前为静态启动占位 markup，无用户输入插值，**实际风险低**。但建议保持"渲染用户内容一律走 React 受控组件、禁用 innerHTML"，避免后续引入 XSS。

---

### 🔵 [Low] L2 — 日志/打印可能泄露路径与参数（CWE-532）

**位置**：`app/services/worker_adapter_service.py:79` `print(... package_path ...)`、`subprocess_adapter` 错误日志

**修复**：避免 `print` 敏感路径；日志级别与内容受控，不在日志中记录密钥或完整请求体。

---

### 🔵 [Low] L3 — 依赖版本异常 / 供应链（General Advice）

- `frontend/package.json` 中 `lucide-react: "^1.17.0"` 与社区已知版本线（0.x）不符，存在**误配或投毒风险**，请核验其真实性与来源。
- `dagre: "^0.8.5"` 年久失修，关注已知问题。
- 后端 `requirements.txt` 未锁定版本（无 `==` 与 hash），存在依赖漂移/混淆风险。

**修复**：
```bash
npm audit --prefix frontend        # 前端漏洞扫描
pip install pip-audit && pip-audit -r app/requirements.txt
# 校验 lockfile 出处，启用 --frozen-lockfile；后端改用带 hash 的锁定文件
```

---

## 三、加固清单（按优先级）

| 优先级 | 动作 | 对应 |
|---|---|---|
| P0 立即 | 删除 `test-admin-token`，将 `get_current_user` 接入全部路由，默认拒绝匿名 | C1/C3 |
| P0 立即 | `peer-dispatch` 加鉴权 + 人工审批闸门；`approval_policy` 改非 `never`；`workspace_root` 隔离 | C2 |
| P0 立即 | Codex 子进程 env 改为白名单，剥离密钥 | H1 |
| P1 本周 | `task_id` 净化防穿越；缺失关键密钥 fail-closed 启动校验 | H3/M1/M2 |
| P1 本周 | 生产启用 Docker/gVisor 沙箱；subprocess 兜底补齐出网阻断/低权限/跨平台限制 | H2 |
| P2 迭代 | 收窄 CORS；前端禁用 innerHTML 渲染用户内容；清理敏感 print/日志 | M3/L1/L2 |
| P2 迭代 | 依赖锁定 + `npm audit` / `pip-audit`；核验 `lucide-react` 来源 | L3 |
| 持续 | 密钥统一走密钥管理（禁止空串/随机回退）；`.env` 已 gitignore（✅ 保持）；周期性 `git ls-files` 核查无密钥入库 | 治理 |

---

## 四、正面项（已做对的地方）

- `.env` 已被 `.gitignore` 覆盖，且无密钥文件入库（已核查 `git ls-files`）。
- 持久化反序列化使用 `yaml.safe_load`（非 `yaml.load`），规避了 YAML 反序列化 RCE。
- 未发现 `shell=True`、`verify=False`/`--insecure` 等 TLS 绕过写法。
- 命令执行均使用参数列表（非字符串拼接），无直接 shell 注入。

---

## 五、复核建议

修复后建议补充：
1. 对 `/api/*` 与 `/internal/*` 做一轮"匿名请求应全部 401/403"的自动化测试。
2. 对 `peer-dispatch` 链路做渗透验证（仅在授权环境、用无害 payload）。
3. 将本清单纳入 CI：依赖扫描、密钥扫描（如 gitleaks）、`test-admin-token` 等硬编码凭据正则拦截。

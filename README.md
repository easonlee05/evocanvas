# EvoCanvas

EvoCanvas 是一个以 **Vibe Shaping（感觉塑形）** 为核心的对话驱动收敛工作台。它帮助产品经理，以及创业者、设计师、业务负责人等产品思考密集型用户，从一句尚未成形的感觉、零散聊天或多源材料开始，逐步形成可讨论、可追溯、可交接的结构化判断。

它不是 PRD 生成器，也不是自由白板或完整项目管理系统。EvoCanvas 的重点是先帮人把事情想明白，再把稳定的结果交给人或下游 AI 继续实现、评审和拆解。

> 当前产品真相源：[`docs/vision/EvoCanvas1.0-PRD.md`](docs/vision/EvoCanvas1.0-PRD.md)

## EvoCanvas 1.0

1.0 的体验旅程是：

`感觉接入 -> 对话塑形 -> 结构收敛 -> 画布显影 -> 结构化交接`

其中首版需要验证的核心闭环是：

`输入编译 -> 待澄清问题 -> 约束 / 待决策 -> 结构化交接物`

这意味着系统应当：

- 允许用户从模糊感觉、聊天摘录、会议纪要、截图说明或其他碎片材料开始；
- 优先显性化不确定性、冲突和缺口，而不是抢先给出看似完整的结论；
- 把已初步成形的内容收敛为可治理对象，并在稳定后显影到画布；
- 在确认边界内形成可追溯的结构化交接物，可进一步派生为面向 AI 的 PRD。

### 首版对象与边界

主画布只承载已经相对稳定的结构，并围绕六类正式卡片工作：

| 对象 | 作用 |
| --- | --- |
| 证据卡 | 保留与当前问题相关、可引用的输入片段 |
| 问题卡 | 表达一个需要持续推进的真实问题 |
| 待澄清卡 | 表达仍会影响后续判断的关键缺口 |
| 约束卡 | 沉淀术语、规则、边界和已确认口径 |
| 待决策 / 方案承接卡 | 承接需要拍板或比较取舍的事项 |
| 交接物承接卡 | 投影可供下游继续使用的结构化包版本 |

项目时间轴和活跃缺口（Active Todos）属于系统挂件，只投影当前状态，不是独立事实源；便签、停车区、时钟等个人挂件仍是首版预留能力。

1.0 不包含多人实时协作、自由白板模式、完整任务管理系统或复杂交付编排。

## 工程结构

```text
app/
  canvas/                 # 工作区、卡片、关系、治理、交接物与投影领域能力
  workflows/              # 上下文编译、运行、检查点与状态能力
  api/                    # FastAPI 服务与 Canvas API
  core/ services/ mcp/ cli/ # 复用的通用运行时、服务与工具底座
frontend/
  src/pages/LandingPage/  # 低压力感觉接入与产品入口
  src/pages/Workspace/    # 对话、画布、卡片、关系与挂件工作面
  src/components/         # 通用组件与布局
docs/
  vision/                 # 主 PRD 与卡片、挂件模块阅读文档
  harness/                # AI 受控收敛的规格与治理文档
tests/                    # 后端领域、流程、治理与 API 测试
```

EvoCanvas 在 Evoloop 通用基础设施上进行半重构迁移：复用会话、事件、工具、存储、运行时和基础 UI 能力，同时逐步替换旧产品流程适配层。`docs/harness/09-reference-models/` 中的参考模型仅供对照，不能覆盖 1.0 的产品边界。

## 文档地图

| 想了解什么 | 先读哪里 |
| --- | --- |
| 产品定位、1.0 范围、流程、交互与验收 | [`docs/vision/EvoCanvas1.0-PRD.md`](docs/vision/EvoCanvas1.0-PRD.md) |
| 正式卡片对象 | [`docs/vision/modules/cards.md`](docs/vision/modules/cards.md) |
| 系统挂件与个人挂件预留 | [`docs/vision/modules/widgets.md`](docs/vision/modules/widgets.md) |
| AI 如何被约束为受控收敛系统 | [`docs/harness/README.md`](docs/harness/README.md) |
| 当前仓库的协作、迁移与验证规则 | [`AGENTS.md`](AGENTS.md) |

主 PRD 是唯一产品真相源。模块文档和 Harness 文档用于展开对象、实现和治理边界；若与主 PRD 冲突，以主 PRD 为准并同步修正。

## 本地开发

### 前置条件

- Node.js 与 npm
- Python 3

### 安装依赖

```bash
npm --prefix frontend install
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r app/requirements.txt
```

### 启动前端

```bash
npm --prefix frontend run dev
```

### 启动后端

```bash
python3 -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000 --reload
```

### 前后端联调

先启动后端，再运行：

```bash
VITE_API_BASE=http://127.0.0.1:8000 npm --prefix frontend run dev
```

后端健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

## 验证

```bash
# 前端构建
npm --prefix frontend run build

# 后端测试
python3 -m unittest discover -s tests
```

提交改动前，请按改动范围运行最小充分验证。涉及卡片、状态、确认、交接物、画布投影或 AI 行为时，还应确认：冲突没有被静默合并、稳定信息有来源和确认依据、系统挂件没有成为新的事实源。

## 产品路线

| 版本 | 要验证的能力 |
| --- | --- |
| 1.0 | 将感觉与多源输入稳定收敛为可交接上下文 |
| 2.0 | 将上下文继续收束为可执行方案 |
| 3.0 | 让多角色围绕结构化对象协作 |
| 4.0 | 将协作结果编排到更完整的交付链路 |

# Pi Runtime Migration Preflight（Pi 运行时迁移前置核对）

> 文档状态：`当前实现证据与迁移硬门`
> 核对日期：`2026-09-08`
> 目标架构：`空 Workspace 可无 Session；首条真实消息后，一个 Workspace 绑定一个长期 Primary Pi Session`
> 当前结论：`文档合同已封口；代码、数据和生产入口迁移尚未完成`

## 1. 核对原则

本文件只记录当前代码事实、数据风险和迁移前置条件。目标产品规则以主 PRD 和 Harness L3 为准；当前旧实现不能反向改变目标架构。

工作区已有修改均视为用户资产。实现迁移前必须再次核对 `git status --short`，不得覆盖、回退或顺带格式化无关文件。

## 2. 当前实现证据

### 2.1 Pi 依赖

`pi-runtime/package.json` 当前使用：

```text
@earendil-works/pi-agent-core 0.84.1
@earendil-works/pi-ai 0.84.1
@earendil-works/pi-telemetry override 0.84.2
```

目标是同一 `0.85.1` 依赖族。升级完成必须以 lockfile 依赖树、构建、测试和真实 Session 恢复证据确认，不能只改直接依赖版本。

### 2.2 TypeScript Pi Runtime

当前可观察事实：

- `pi-runtime/src/runtime/executor.ts` 仍按请求创建低层 Agent；
- `pi-runtime/src/server.ts` 仍保留 chat / judgement / convergence 三类旧入口；
- `pi-runtime/src/contracts.ts` 仍保留旧请求 DTO；
- `pi-runtime/src/runtime/tools.ts` 仍有旧提案捕获能力；
- 相邻测试仍覆盖旧请求合同。

这证明当前 Pi 主要作为单次执行器使用，而不是 Workspace 的长期 Agent 核心。

### 2.3 Python Canvas / Agent 路径

当前可观察事实：

- `app/canvas/pi_kernel.py` 仍组装上下文、判断和独立收敛运行；
- `app/canvas/product_kernel.py` 仍拥有外部 Agent 编排职责；
- `app/canvas/agent_execution/contracts.py` 定义旧跨进程合同；
- `app/canvas/tool_gateway.py` 仍按旧运行类型控制工具；
- `app/canvas/domain/runtime_records.py` 与 repository 保存旧产品运行记录；
- `app/canvas/domain/ledger.py` 仍保留追加状态语义；
- `app/api/server.py` 仍装配旧主链。

这些模块可以抽取认证、存储、提交和投影能力，但当前组合方式不是目标 Harness。

## 3. 目标与当前差距

| 能力 | 目标 | 当前 | 迁移动作 |
| --- | --- | --- | --- |
| Workspace Session | 首条真实消息创建长期 Primary Session | 每请求创建 Agent / 外部 conversation | 建立 Binding 状态与恢复 |
| Session Store | 官方 SQLite；一 Session 一文件；宿主独占写 | 尚未按目标接入 | 建目录、锁、路由、备份与恢复 |
| Pi 依赖 | 全族 `0.85.1` | `0.84.1` 与 telemetry `0.84.2` 混合 | 整体升级与依赖树验证 |
| User Submission | `submission_id + content_hash` 去重 | 尚无目标入口合同 | 新增去重和 Entry receipt |
| Skills | Pi 原生发现并自主使用 | 未接入目标主链 | 注册 Skill 资源和版本 Trace |
| Context | `transformContext` 读 current Revision | Python 组装请求快照 | 迁入 Pi Context Hook |
| Runtime | 一个正常 Tool Loop | 多类产品运行 | 停止新运行类型依赖 |
| Stable Write | 用户和 Pi 共用 `workspace.commit` | 提案、服务、旧提交路径并存 | 收敛为类型化语义提交 |
| Tool Recovery | `replay=safe|never` + `success|failed|unknown` | 尚未完整声明 | 注册静态策略与恢复门槛 |
| State | 完整不可变 Revision + 类型化对象状态 | 旧包版本、Ledger 和运行记录混合 | 定义映射并迁移 |
| Canvas | 只投影 Revision | 现有服务可能直接操作卡片 | 将业务变化统一改为 Commit |
| Handoff | current / latest confirmed 双指针 | 旧 handoff 状态和快照 | 迁移确认与过时语义 |
| Lifecycle | close / archive / replace / coordinated delete | 目标合同未实现 | 实现 `deleted/partial/retention_held` |
| Trace | Entry -> Invocation -> Operation -> Revision -> Projection | 多处记录但关联未闭环 | 建立关联键与诊断视图 |

## 4. 迁移前必须完成的数据盘点

### 4.1 读写消费者

必须列出以下对象的全部写入、读取、查询和删除入口：

- Conversation / message / Session 数据；
- 旧每轮请求快照和运行 DTO；
- Judgement / Convergence / Commit 运行记录；
- Structured Package / Snapshot / Handoff；
- Ledger / confirmation / watermark；
- Card、relation、projection 和 Todo；
- Tool Gateway / Outbox / Trace。

### 4.2 真实数据

需要证明：

- 本地或生产样本是否存在旧运行记录；
- 旧 `conversation_id` 能否稳定映射到预留 Primary Session；
- 工作包历史能否构造完整 Revision；
- 来源引用是否依赖旧消息序号或即将删除的文件路径；
- 交接确认和状态是否能无损映射；
- Canvas 中是否存在无法回指稳定对象的卡片。

未完成盘点前不得删除字段、存储或 API。

## 5. 按 Workspace 迁移流程

一个 Workspace 的切换固定为：

1. **预检**：验证消息、来源、工作包和交接均可映射。
2. **短暂停写**：只冻结该 Workspace 的旧消息与稳定写入入口，读取保持可用。
3. **预留 Binding**：创建 `binding` 记录和唯一 `primary_session_id`。
4. **导入 Session**：按原顺序导入 User / Assistant / Tool 过程与附件引用。
5. **导入 Revision**：将当前稳定状态转换为完整不可变 Revision。
6. **校验**：核对数量、角色、顺序、来源映射、内容哈希、确认和交接指针。
7. **原子切换**：一次更新 Binding 与新权威指针，旧路径同时转只读。
8. **恢复写入**：新 User Submission 和稳定提交只进入新路径。
9. **观察与退役**：观察期通过后删除旧消费者，最后按删除硬门处理旧存储。

迁移期间不长期双写。影子校验只能读取同一冻结输入做离线比较，不得让两条路径同时产生可写事实。

## 6. 回退边界

| 时点 | 允许动作 | 禁止动作 |
| --- | --- | --- |
| Binding 切换前 | 放弃新 Session，解除旧路径停写 | 发布半绑定或半导入数据 |
| 切换后且尚无新 Entry / Revision | 完整校验后原子切回旧路径 | 两边同时恢复写入 |
| 切换后已产生新 Entry 或 Revision | 修复前进，或再次执行受控迁移 | 回到旧路径继续写、丢弃新事实 |
| 已产生外部副作用 | 保留回执并按副作用恢复合同处理 | 因代码回退伪装动作未发生 |

每次回退或修复前进都记录 Workspace、迁移批次、哈希、切换点、已产生的新事实和操作者。

## 7. 删除硬门

删除旧 API、Schema、存储或兼容字段前，必须全部满足：

1. `rg`、测试和运行时观测证明无新写入者；
2. 全部读取者已迁移或有明确只读兼容层；
3. 历史数据迁移数量、内容哈希和抽样语义核对通过；
4. 新主链端到端覆盖首条消息、普通对话、确认提交、直接编辑、交接和投影；
5. 并发、锁、取消、超时、未知结果、归档、换代、删除和重建测试通过；
6. 观察期内无关键回归；
7. 三段回退边界均演练；
8. 删除得到独立执行授权。

## 8. 文档封口与实现出口分离

### 文档合同已满足

- 主 PRD、模块文档、Harness 与现行 Technical Specs 使用同一产品与架构边界；
- 目标 Session、身份、Context、Tool、Commit、Revision、Handoff、Projection、Lifecycle 和迁移规则已明确；
- 机器可读 Schema 不再保留旧运行类型；
- 旧技术快照已从现行规格目录移除。

### 实现仍未满足

- 全量真实数据和消费者盘点；
- Pi `0.85.1` 依赖族升级与官方 Session Backend 接入；
- Workspace–Primary Session 可恢复实现；
- 统一 `workspace.commit` 和完整 Revision；
- 新旧数据迁移、观察与回退演练；
- 生产入口端到端证据；
- 旧路径停止写入和删除授权。

因此可以依据文档进入实现，但不能声称 Pi 内核重构已经完成。

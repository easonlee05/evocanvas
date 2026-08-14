# Pi Runtime Phase 0 Matrices（Pi 运行时阶段 0 矩阵）

> 状态：阶段 0 核对稿；用于合同测试、迁移拆分和停止门，不把未核对项伪装成已实现。
>
> 关联：[执行计划](../../plans/2026-08-14-evocanvas-pi-runtime-core-execution-plan.md)、[接口契约](./05%20Pi%20Runtime%20Contract（Pi%20运行时接口契约）.md)、[L3 Runtime](../harness/03-runtime-tools/01%20Runtime（运行时）.md)、[L3 Failure and Recovery](../harness/03-runtime-tools/03%20Failure%20and%20Recovery（失败与恢复）.md)

## 1. 生命周期与事实边界矩阵

| 记录/对象 | 技术状态 | 业务结果/治理状态 | 唯一事实源 | Pi 是否可写 |
| --- | --- | --- | --- | --- |
| 原始消息 | `user / assistant / tool`，会话内 `message_seq` 单调递增 | 无 | Python Message Store | 否 |
| `ChatTurn` | `queued → running → completed / failed / cancelled` | 最多一条主 Assistant 回复 | Python Runtime Store | 否 |
| `ConvergenceJudgement` | 记录判断尝试及范围 | `skip / defer / trigger` | Python Runtime Store | 否 |
| `ConvergenceRun` | `created / queued / running / validating / committing / completed / failed / stale / cancelled` | `applied / no_change / not_ready / rejected_by_governance` | Python Runtime Store | 否 |
| `CommitAttempt` | `started / applied / duplicate / stale / failed / unknown` | 提交技术结果 | Python Commit Store | 否 |
| PackageVersion | 不可变版本 | 草稿、候选、待确认、已确认或过时等治理地位 | Python CanvasRepository | 否 |
| State Ledger | 追加式事件 | 确认、替代、风险和治理记录 | Python Ledger | 否 |
| Outbox | `pending / published / failed`（实现阶段确定字段） | 仅投影发布，不改变事实 | Python Runtime State | 否 |
| Canvas / Todo / Handoff | 投影消费状态 | 由当前包版本派生 | Python Projection | 否 |

约束提议没有有效确认时只留 Chat，不写入约束对象；待决策候选、冲突、待澄清可以按 L3 操作规则以正确的信息地位进入包。交接草稿显影门槛与正式外发/确认门槛分开，普通包更新不新增长期审批队列。

## 2. 并发、消息水位与提交矩阵

| 场景 | 必须发生 | 禁止发生 |
| --- | --- | --- |
| Chat 运行中收到新 User 消息 | 先保存消息并分配 `message_seq`；Chat 回复按 `conversation_id` 排序；推进包级待重判水位 | 以工作区级锁返回 `409`；丢弃新消息 |
| 同包已有收敛 | 新请求更新 `(workspace_id, package_id)` 水位；最多一个写资格回合 | 同包并发写两个收敛回合 |
| 提交前发现新消息/状态版本 | 当前回合整体 `stale`，保留提案和原因；释放租约，由最新水位重新判断 | 适配旧提案后部分提交 |
| 相同 `operation_id` 重试 | 返回原提交结果，技术状态为 `duplicate` 或原结果 | 创建第二个 PackageVersion |
| 提交响应丢失 | `CommitAttempt=unknown`，按 `operation_id` 查询 | 更换幂等键盲目重放 |
| 事实已提交、投影失败 | 保留事实，Outbox 重放或重建投影 | 回滚 PackageVersion 或让投影反向改事实 |
| 租约过期 | 先核对 operation；未提交则 `stale`，已提交则补 Outbox | 未核对就重新写入 |

初版可配置参数沿用 L3 基线：短合并窗口 5 秒、弱信号累计 3 条、提案结构修复最多 2 次、提案预算 10 秒、租约 30 秒、续租 10 秒、恢复扫描 15 秒。参数不是产品不变量，实际值和版本必须进入 Trace。

## 3. Provider / Adapter 兼容矩阵

阶段 0 只冻结“适配边界”，不声称当前已经可用。任何供应商进入正式支持矩阵前，必须通过同一套一致性测试。

| Provider / 协议 | Adapter 归属 | Chat | Judgement | Convergence | 流式/取消/工具/结构化输出/usage | 当前状态 |
| --- | --- | --- | --- | --- | --- | --- |
| OpenAI Responses API | Pi Runtime adapter | 待验证 | 待验证 | 待验证 | 全部待验证 | 设计目标，未接入 |
| Anthropic Messages API | Pi Runtime adapter | 待验证 | 待验证 | 待验证 | 全部待验证 | L3 要求，未接入 |
| Fake Provider | Pi Runtime 测试实现 | 用于合同测试 | 用于合同测试 | 用于合同测试 | 可控模拟 | 阶段 1 必须实现 |
| 当前 `OpenAILLM` / 兼容网关 | 旧 Python 路径 | 不计入新支持矩阵 | 不计入 | 不计入 | 不作为回退 | 阶段 7 清理 |

每个正式 Adapter 必须能关联 `context_manifest_id`、`model_call_id`、provider/adapter/protocol/capability 版本，且不得持久化供应商原生请求和完整响应载荷。未通过测试的兼容网关不得静默标记为正式支持。

## 4. ToolSpec 与权限矩阵

| 工具 | 类别 | Chat | Judgement | Convergence | side effect | 结果要求 |
| --- | --- | --- | --- | --- | --- | --- |
| `source.resolve` | 读取/验证 | 允许 | 默认不调用 | 允许 | `read` | 原始片段/指针、内容指纹、source refs |
| `material.read` | 读取 | 允许 | 默认不调用 | 允许 | `read` | 结构化材料结果、source refs |
| `knowledge.retrieve` | 检索 | 允许 | 默认不调用 | 允许 | `read` | 候选和检索范围，不自动成事实 |
| `structure.validate` | 验证 | 不需要 | 不允许 | 允许 | `none` | Schema/对象/引用校验结果 |
| `submit_convergence_proposal` | 结构整理 | 不允许 | 不允许 | 仅允许 | `none`（内存捕获） | 完整 Proposal，不能调用 Repository |
| Shell/代码执行 | 禁止 | 禁止 | 禁止 | 禁止 | `internal/external_write` | 不进入 1.0 |
| 任意文件/网络/MCP 写 | 禁止 | 禁止 | 禁止 | 禁止 | `external_write` | 不进入普通收敛 |

每次调用都必须记录 `tool_call_id`、工具名/版本、运行单元、作用范围、参数安全摘要、尝试次数、状态、耗时、来源和错误。Run-scoped Token 绑定运行、工具白名单、workspace/conversation/package 范围、到期时间和最大次数。

## 5. 错误、恢复与用户行为矩阵

| Pi/基础设施错误 | Python 分类 | 是否技术重试 | 产品行为 |
| --- | --- | --- | --- |
| 网络抖动、限流、短暂 Provider 错误 | `temporary_error` | 在预算内 | 保留 User 消息；运行失败前不伪造回复 |
| Schema/参数/引用不合法 | `input_error` | 否 | 保留缺口；Proposal 不提交 |
| Tool Token/权限拒绝 | `permission_denied` | 否 | 不提升权限、不静默换工具 |
| 工具超时 | `temporary_error` 或 `tool_timeout` | 仅幂等读取可重试 | 保留来源缺口，不脑补结果 |
| 信息不足/确认范围不清 | `not_ready` | 否 | 保留候选/待决策，后续由正常 Chat 引导 |
| 消息/状态/包版本变化 | `stale`，原因 `base_version_changed` | 否 | 丢弃旧提案，不部分写入 |
| 治理拒绝 | `governance_rejected` | 否 | 记录拒绝/降级，不提升信息地位 |
| 流中断或 Pi 重启 | `engine_unavailable` / `commit_unknown` | 先查询终态 | 不保存半条回复或半条提案 |
| Commit 响应丢失 | `commit_unknown` | 先按 operation 查询 | 未核对前禁止重放 |
| Outbox 发布失败 | `projection_failed` | 可重放事件 | 事实保持成功，投影最终一致 |

稳定错误码由 [接口契约](./05%20Pi%20Runtime%20Contract（Pi%20运行时接口契约）.md) 定义；控制流不得解析异常文案。

## 6. 当前实现迁移矩阵

| 当前入口/模块 | 当前事实 | 目标处理 | 阶段 |
| --- | --- | --- | --- |
| `app/api/server.py` | 直接组装 `OpenAILLM`、`WorkflowEngine`，Canvas 与旧 Task API 共置 | 先新增 Product Kernel + PiRuntimeClient 装配边界，阶段 6 切换主链 | 2、6 |
| `CanvasService.start_turn()` | 负责模型调用、提案、验证、治理、提交；持有工作区级 `active_turn` | 拆为 Chat/判断/收敛/提交职责；保留领域验证和统一 Commit | 3–4 |
| `app/services/llm.py` | Python OpenAI-compatible 调用与旧 fallback | 从 EvoCanvas Agent 主链移除；是否保留通用底座由消费者扫描决定 | 2、7 |
| `app/services/agent_runtime/` | 旧 JSON tool loop | 不作为新执行器；无独立消费者则删除 | 7 |
| `app/workflows/engine.py` / `canvas_session.py` | 旧任务/步骤运行；当前 Canvas 消息不经过它 | 不接入新 Pi 主链；通用 Task 能力与 EvoCanvas 解耦后再处理 | 7 |
| `app/canvas/runtime_state.py` | 仍有 `active_turn` 过渡字段 | 迁移到 conversation/message_seq 与包级租约后删除在线阻塞语义 | 4、7 |
| `app/canvas/repository.py` | 已有 PackageVersion、Ledger、operation_id 幂等和文件存储 | 复用并补运行记录、租约、水位、Outbox 的边界 | 3–4 |
| `frontend/src/api.js` | 通用 fetch/fallback，无 typed Pi 合同、取消或 NDJSON | 阶段 6 只适配 Product API；浏览器不直连 Pi | 6 |
| `/api/canvas/.../messages` | 同步 Chat，active_turn 冲突返回 409 | 保持产品端点语义稳定到可行范围，改为非阻塞接收 + 状态/取消查询 | 6 |
| `/api/canvas/.../events` | 进程 EventBus SSE，不重放历史 | 由产品 API 投影/状态查询承接；Pi NDJSON 不直接暴露浏览器 | 6 |

当前工作区中除本计划和 spec 外还有用户未跟踪资产；阶段 0/后续提交只允许显式加入本迁移文件，禁止 `git add .`。

## 7. 数据与删除 preflight

阶段 7 之前必须逐项记录结果：

- [ ] 是否存在必须保留的真实联调工作区、消息、包版本、确认或外部消费者。
- [ ] 若存在，是否完成初始 `package_id`/版本 1 迁移、来源/关系/确认可验证性报告。
- [ ] 是否确认旧 `active_turn`、`confirmation_queue`、任务运行记录只是开发资产而非外部合同。
- [ ] 是否确认旧 API/CLI/页面没有仍属于 1.0 的消费者。
- [ ] 是否为通用事件、会话、工具、存储和运行时底座找到安全替代或解耦方案。
- [ ] 是否完成全仓引用扫描和删除前测试快照。

任一项未知，停止删除，不写兼容读取器，也不把未知数据当作“无数据”。

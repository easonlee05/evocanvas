# Runtime（运行时）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Agent Core`
> 当前实现状态：`原生运行时已接入，长期恢复能力待验证`
> 实现说明：当前生产路径已接入 Workspace Primary Pi Session；非主链调用保持隔离，长期恢复与完整 Harness 能力仍以验证证据为准。

## 1. 控制目标

提供唯一、可恢复的 Agent 执行环境，不让 EvoCanvas 复制 Pi 已拥有的会话、运行、工具循环、压缩或追踪能力。

## 2. Session 创建与运行身份

空 Workspace 可以没有 Session。第一条真实用户消息到达时，宿主先以 `submission_id + content_hash` 去重，再创建或恢复该 Workspace 的 Primary Pi Session；仅打开页面、读取 Revision 或渲染 Canvas 不创建空 Session。

绑定至少包含：

```text
workspace_id
primary_session_id
main_lane
binding_status: binding | ready | unavailable | archived
pi_session_format_version
session_file_ref
```

身份分层固定为：

| 身份 | 作用 | 不得代替 |
| --- | --- | --- |
| `submission_id` | 用户入口跨网络重试去重，必须绑定规范化 `content_hash` | Session 来源、业务操作、工具调用 |
| `entry_id` | Pi 持久 Entry 身份，是内部对话来源引用 | 入口请求幂等、业务操作 |
| `operation_id` | `workspace.commit` 内单个稳定语义操作的审计与去重身份 | Pi 工具技术调用 |
| `invocation_id` / Pi `tool_call_id` | Pi 一次工具调用的技术身份 | 用户提交、稳定业务操作 |

相同 `submission_id + content_hash` 返回原 `entry_id`；同一 `submission_id` 携带不同哈希返回 `runtime.submission_conflict`。EvoCanvas 不另建 Chat、判断或收敛运行 ID。

## 3. 运行能力

Pi Runtime 必须承载：

- Session Entry 的持久化、分支与恢复；
- 模型选择、Provider 映射和认证；
- Assistant 流式输出；
- Tool Loop、工具前后 Hooks 和工具结果持久化；
- 用户取消、Steering、Follow-up 和未完成运行恢复；
- 上下文窗口、压缩和重试；
- 技术错误、用量和时延 Trace。

EvoCanvas 只通过 Pi 注册产品 Instructions、Skills、Tools、`transformContext` 和事件消费者。

首版实现基线固定为：

- `@earendil-works/pi-agent-core`、`@earendil-works/pi-ai` 及实际进入运行路径的 Pi 同族包统一为 `0.85.1`，不得混装 `0.84.x / 0.85.x`；
- 使用 Pi 官方 SQLite Session Backend；
- 一个 Primary Session 对应一个 SQLite 数据库文件；
- 同一 Session 文件同一时刻只有一个宿主写者，宿主级独占锁覆盖打开、恢复、Entry 持久化和压缩；
- 多进程并发请求先路由到持锁宿主，不通过 SQLite 多写者竞争实现 Main Lane。

## 4. 运行推进

```text
idle
-> running
-> waiting_for_tool / streaming
-> running
-> completed | cancelled | failed | suspended
```

这是 Pi 技术运行状态，不是产品收敛阶段，也不写入结构化工作包。产品稳定推进只由 Revision 变化表达。

## 5. 并发与顺序

- 同一 Main Lane 同时只允许一个主动 Agent Loop；新的 Steering / Follow-up 由 Pi 队列语义处理。
- 工作包提交独立使用 `base_revision_id` 做乐观并发控制，不能依赖“Session 当前空闲”保证一致性。
- 多个只读工具可按 Pi 配置并行；包含稳定写入或外部副作用的工具必须按调用顺序串行完成。
- 当前运行取消不等于撤销已完成的工具效果。

## 6. Tool Context

每次工具调用上下文至少提供：

```text
workspace_id
session_id
turn_id
entry_id
tool_call_id
invocation_id
actor_id
current_revision_id
instruction_bundle_version
active_skill_versions[]
abort_signal
```

工具不得信任模型自行填写这些身份字段；由 Runtime 注入。

## 7. 稳定提交结果

`workspace.commit` 成功时返回：

```text
commit_id
idempotency_key
previous_revision_id
new_revision_id
changed_object_ids[]
review_required_object_ids[]
handoff_status_change?
projection_enqueued: boolean
```

结果作为 Tool Entry 进入 Session。Pi 的随后回复可解释结果，但不能改变它。

## 8. 取消、挂起与恢复

- 取消信号必须传给模型流和可取消工具。
- 工具已报告成功后收到取消：保留成功结果，不伪装成已撤销。
- 可恢复的 Provider 或工具任务使用 Pi Deferred / Session 恢复能力，不新增产品运行表。
- 进程崩溃后，从 Pi Session 恢复未完成技术运行；从工作包 Revision 确认稳定提交状态。
- 无法确认某工具是否执行时，进入 `unknown` 诊断并先查询幂等结果；只有工具声明 `replay=safe` 且幂等核对允许时才可自动恢复调用。
- `replay=never` 的调用一旦结果未知，必须停在人工或外部权威核对，不因 Pi 恢复 Turn 而重新调用。
- `binding` 状态崩溃恢复时复用已预留的 `primary_session_id`：Session 文件存在且首条 Entry 哈希匹配则完成为 `ready`；文件尚未创建则以同一 ID 重试；无法判定时转 `unavailable`，不得另建 Session。

## 9. 权限边界

Runtime 负责“能否技术执行”，不负责判断用户是否确认了产品含义。语义确认由工作包提交工具校验；外部副作用由对应工具校验明确授权。

## 10. 失败与恢复

| 原因码 | 行为 |
| --- | --- |
| `runtime.provider_unavailable` | Session 保留输入，允许稍后在原 Session 重试 |
| `runtime.model_failed` | 不产生业务提交，除非此前工具已成功 |
| `runtime.cancelled` | 停止后续步骤，保留已完成工具结果 |
| `runtime.session_unavailable` | 不启动新 Agent Loop；工作包可独立只读 |
| `runtime.resume_unsupported` | 明确标记未恢复，不创建替代产品运行记录 |
| `runtime.identity_missing` | 拒绝调用需要治理的工具 |
| `runtime.submission_conflict` | 同一 `submission_id` 的内容哈希不同，拒绝覆盖原 Entry |
| `runtime.session_locked` | 当前宿主未持有 Session 独占写锁，路由或稍后重试 |

## 11. 观测要求

技术 Trace 至少可关联 `session_id`、`turn_id`、模型、指令与 Skill 版本、工具调用、Token、重试、取消和终态。产生 Revision 时通过 `commit_id + new_revision_id` 与产品状态关联。

## 12. 验收场景

1. 重启进程后，Pi 从同一 Session 继续，工作包 current Revision 不由聊天摘要恢复。
2. 用户取消发生在提交成功之后，新 Revision 保留且回复指出提交已完成。
3. 两个不同 Session 若尝试修改同一 Workspace，工作包版本门禁仍阻止丢失更新。
4. Provider 切换不产生新的产品运行类型或第二套会话记录。
5. Tool Context 中的 Workspace 和 Actor 身份不能被模型参数覆盖。

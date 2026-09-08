# Context Budget and Compaction（上下文预算与压缩）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Agent Core`
> 当前实现状态：`部分接入`
> 实现说明：Pi 管理模型窗口、Token 估算、压缩、分支和恢复；EvoCanvas 只规定不能丢失的信息地位和工作锚点。

## 1. 控制目标

在长会话中维持可用模型窗口，同时保证压缩不改写用户原话、稳定工作状态、确认边界和来源可追溯性。

## 2. 权威记录与派生内容

- Primary Pi Session Entry 是原始过程记录，压缩摘要是派生 Entry，不能删除或覆盖原记录。
- 结构化工作包 Revision 独立于 Session 压缩，始终可按版本读取。
- Workspace Context Snapshot 每次重新生成，不进入压缩摘要。
- Canvas 不参与上下文预算。

## 3. 保留优先级

模型窗口内从高到低优先保留：

1. 当前 User Entry 和尚未完成的 Tool Loop。
2. 当前指令版本与实际可用工具定义。
3. 最新 Workspace Context Snapshot。
4. 与当前问题直接相关的原始 Tool Entry 和最近对话。
5. 较老但仍影响未决问题的内容。
6. 已被稳定 Revision 吸收且当前不相关的历史讨论。

具体 Token 阈值、保留量和压缩触发条件由 Pi 配置，不进入 EvoCanvas 产品规则。

## 4. 压缩合同

压缩结果必须：

- 标识覆盖的 Entry 范围和生成时间；
- 保留关键来源引用、未决冲突和未完成工具状态；
- 区分用户原话、模型推断与已确认工作包事实；
- 不产生新的确认，不把候选内容提升为稳定事实；
- 可通过 Session 分支和原始 Entry 重新核对。

压缩完成后的下一次模型调用仍由 `transformContext` 注入最新 Revision，因此摘要不承担稳定状态存储职责。

## 5. 状态推进与回退

- 压缩成功：追加压缩 Entry，并让 Pi 使用压缩后的工作分支继续。
- 压缩取消或失败：保持原分支和原消息，不产生半成品摘要。
- 稳定提交与压缩并发：Revision 提交按工作包版本原子完成；压缩不改变提交基础版本。
- 压缩摘要被发现有误：从原始 Entry 重新生成新摘要，不修改旧摘要和历史 Revision。

## 6. 失败与恢复

| 原因码 | 行为 |
| --- | --- |
| `context.compaction_failed` | 保持原 Session，可在资源恢复后重试 |
| `context.compaction_cancelled` | 不写入摘要，继续原分支 |
| `context.summary_unverifiable` | 停止依赖该摘要，按 Entry 引用复水 |
| `context.window_exhausted` | 停止继续调用模型，先压缩或要求缩小任务；不截断当前提交确认 |
| `context.pending_tool_state` | 禁止在无法保留未完成工具状态时压缩 |

## 7. 权限与观测

每次压缩记录 `session_id`、分支、覆盖 Entry 范围、压缩策略版本、模型标识、结果 Entry 和失败原因。压缩器无权修改结构化工作包、确认记录或 Canvas。

## 8. 验收场景

1. 百轮会话压缩后，Pi 仍能从最新 Revision 读取已确认约束。
2. 摘要错误地遗漏候选方案时，不影响工作包；原 Entry 可重新读取。
3. 未完成工具调用存在时，压缩被拒绝或完整保留其恢复信息。
4. 压缩与用户直接编辑并发时，Pi 下轮仍读取用户提交的新 Revision。
5. 切换模型窗口大小只改变 Pi 的压缩策略，不改变产品事实或确认状态。

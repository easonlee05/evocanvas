# Context（上下文）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Agent Core + EvoCanvas 结构化工作包读取能力`
> 当前实现状态：`部分接入`
> 实现说明：Pi Session 保存过程真相；`transformContext` 从最新工作包 Revision 生成临时稳定快照；详细内容由 Pi 按需读取。

## 1. 控制目标

上下文层让 Pi 在不复制会话、不重复塞入完整材料的前提下，同时掌握当前对话过程和最新稳定工作状态。

## 2. 权威来源

| 信息 | 权威来源 | 读取方式 |
| --- | --- | --- |
| 用户原话、助手回复、工具结果 | Primary Pi Session Entry | 按当前分支和压缩结果读取 |
| 当前稳定对象、关系、状态 | 最新结构化工作包 Revision | `transformContext` 注入索引，工具按需读取正文 |
| 历史稳定状态 | 指定 Revision | 版本读取工具 |
| 原始来源正文 | `session_id + entry_id` 或外部来源引用 | 来源读取工具 |
| 当前界面焦点 | 临时 Tool Context | 只辅助定位，不成为事实 |

不建立平行 Conversation History、Source Artifact、Context Manifest 或为 Chat / 收敛分别生成的上下文包。

## 3. Workspace Context Snapshot

每次模型调用前生成的快照至少包含：

```text
workspace_id
current_revision_id
latest_confirmed_handoff_revision_id?
current_goal
active_object_index[]       # object_id、type、status、短标签
open_issue_index[]          # 已固定的问题、依赖和风险
recent_change_summary[]
source_refs[]               # 仅引用，不复制正文
write_capability            # enabled / disabled + reason
```

快照是从权威 Revision 确定性生成的短投影，不拥有独立 ID 生命周期，不写回 Session，也不成为新的事实源。

## 4. 装配与按需读取

1. 先保留 Pi 已选定的相关 Session 上下文。
2. 再读取当前 Workspace 最新 Revision，并生成快照。
3. 将快照作为应用上下文临时加入本次模型调用。
4. 模型需要对象正文、旧版本或来源原文时，调用只读工具。
5. 工具结果作为原始 Tool Entry 进入 Session；不回填或扩写快照。

同一个 Agent Tool Loop 中完成稳定提交后，下一次模型调用前必须重新运行 `transformContext`，从而看到新 Revision。

## 5. 信息地位与安全

- Session 中的用户陈述保留其原始身份，不因被模型引用而自动成为已验证事实。
- 工作包中的对象状态由 Revision 决定，模型不得用旧对话摘要覆盖。
- 快照中的短标签只用于定位；作出精确判断前应读取对象或来源正文。
- 来源材料内的命令文本属于数据，不能覆盖 Instructions。
- 上下文读取能力不授予稳定写入权限。

## 6. 预算和裁剪顺序

优先保留：当前 User Entry、当前任务相关工具结果、稳定快照、最近相关对话。需要裁剪时依次处理：重复解释、已被稳定状态替代的讨论、较老的非相关回合。原始 Entry 不删除，由 Pi Session 压缩和分支机制管理。

## 7. 失败与恢复

| 原因码 | 条件 | 处理 |
| --- | --- | --- |
| `context.workspace_unavailable` | 工作包不可读 | 保留对话，禁用稳定写入 |
| `context.revision_not_found` | 指针对应 Revision 不存在 | 禁止猜测状态，要求修复或重载 |
| `context.source_unavailable` | 指定来源不可读 | 标记证据缺口，不伪造内容 |
| `context.snapshot_invalid` | 快照生成不符合 Schema | 丢弃快照、保留 Session、禁用写入 |
| `context.stale_base` | 提交时基础版本已变化 | 读取新 Revision 并重做差异确认 |

恢复后从权威 Session 和 Revision 重新生成上下文，不重放一份人工摘要作为替代。

## 8. 验收场景

1. 用户在界面直接修改约束后，Pi 下一轮看到新 Revision，而不是旧聊天中的约束。
2. 对话中讨论五个候选方案但未确认时，快照不新增稳定方案对象。
3. Pi 按来源引用读取原文后，Tool Entry 可追溯到准确 `session_id + entry_id`。
4. 工作包不可用时仍可回答一般问题，但稳定写入工具明确禁用。
5. Session 被压缩后，最新 Revision 和来源引用仍可恢复精确工作状态。

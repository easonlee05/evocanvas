# Trace Model（追踪模型）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Trace + EvoCanvas 关联索引`
> 当前实现状态：`原生追踪模型已接入，关联键闭环待验证`
> 实现说明：Pi 保存技术运行 Trace；Revision 保存业务生效审计；关联索引不复制两者正文。

## 1. 控制目标

提供从用户输入到稳定显影的双向追溯，并能区分模型说了什么、工具实际做了什么和当前业务状态是什么。

## 2. 关联模型

```text
User Submission
  -> Session Entry
  -> Pi Turn / model call
  -> Skill and Tool Invocation
  -> Confirmation Reference
  -> Semantic Operation
  -> Commit
  -> Revision
  -> Handoff state change
  -> Projection
```

并非每个 Entry 都会产生 Commit，也并非每个 Revision 都来自 Pi；用户直接编辑可从 actor / UI action 直接关联 Commit。

## 3. 记录职责

### 3.1 Pi Technical Trace

记录模型标识、指令/Skill 版本、上下文快照哈希、消息范围、工具调用、Token、重试、取消和技术终态。

### 3.2 Revision Audit

记录 actor、base/new Revision、语义操作、确认引用、Policy 版本、依赖复核和交接影响。

### 3.3 Projection Trace

记录目标 Revision、Renderer 版本、结果、节点差异和重建次数。

## 4. 最小关联记录

```text
trace_link_id
workspace_id
submission_id?
session_id?
entry_id?
invocation_id?
tool_call_id?
operation_id?
commit_id?
revision_id?
handoff_id?
projection_id?
created_at
```

该记录只做关联，不保存消息正文、对象快照或外部敏感结果。

## 5. 成功口径

- 对话成功：依据 Pi 技术终态。
- 工具成功：依据 Tool Result。
- 稳定写入成功：依据 current Revision 和 Commit Result。
- 交接成功：依据 confirmed handoff 状态和确认记录。
- 显影成功：依据 projected Revision。

任何一个成功不能推导其他层必然成功。

## 6. 保留、脱敏与访问

Trace 保留期按安全和审计要求配置；被有效 Revision / 交接引用的关键关联不得早于其审计期限删除。敏感参数使用摘要哈希或受控引用，访问 Trace 仍需 Workspace 和诊断权限。

## 7. 失败与恢复

| 原因码 | 行为 |
| --- | --- |
| `trace.link_missing` | 从权威标识重建，不能猜测关联 |
| `trace.audit_unavailable` | 阻止要求强审计的写入或外部动作 |
| `trace.projection_gap` | 比较 Revision 指针并重放投影 |
| `trace.redaction_failed` | 不写入敏感 Trace，按风险关闭相关操作 |
| `trace.inconsistent_success` | 标记层间矛盾并以各层权威记录纠正界面 |

## 8. 验收场景

1. 一个未调用工具的自然语言“已完成”不会显示 Commit 或 Revision。
2. 用户直接编辑的 Revision 能追溯 actor 和 UI action，但没有伪造 Pi Turn。
3. 同一提交可关联多个确认和多个受影响对象。
4. Trace 脱敏后仍能判断工具成败和关联 Revision。
5. 技术运行失败但此前提交成功时，两种状态可同时准确呈现。
6. 同一 `submission_id` 的重试关联同一 `entry_id`，同一 Commit 内的 `operation_id` 与触发它的 `invocation_id` 可区分并双向查询。

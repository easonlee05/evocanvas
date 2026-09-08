# Memory（记忆）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Primary Session + 结构化工作包 Revision 存储`
> 当前实现状态：`合同已定，代码待迁移`
> 实现说明：过程记忆与稳定记忆分开；不从聊天摘要推断当前状态。

## 1. 控制目标

保证历史可追溯、当前状态可直接读取，并避免 Session、工作包和 Canvas 各自保存一份相互漂移的业务真相。

## 2. 过程记忆

Pi Session 至少持久化：

```text
session_id
entry_id
parent_entry_id / branch
entry_type
actor
content or tool payload
created_at
model / tool identity
technical outcome
```

候选理解、未采用方向、工具读取结果和用户原话均留在 Session。压缩只新增派生摘要 Entry，不覆盖原 Entry。

## 3. 稳定记忆

一个结构化工作包 Revision 至少包含：

```text
workspace_id
package_id
revision_id
parent_revision_id?
created_at
created_by
base_revision_id
commit_id
idempotency_key
objects[]
relations[]
confirmations[]
handoff_state
current_handoff_revision_id?
latest_confirmed_handoff_revision_id?
source_refs[]
instruction_and_skill_versions[]
```

`objects` 和 `relations` 保存规范化领域对象图；不保存 Canvas 坐标、完整 Session 正文、重复交接文档或 Provider 消息格式。

## 4. 对象与关系身份

- 语义持续不变：沿用原 `object_id`。
- 仅修改措辞但语义和治理范围不变：更新同一对象并产生新 Revision。
- 实质替代：创建新 `object_id`，建立 `supersedes` 关系，旧对象状态为 `superseded`。
- 合并或拆分：创建目标对象和显式派生关系，不复用一个 ID 冒充多个语义对象。
- 删除业务含义：使用对象类型允许的归档、关闭、替代或移除关系等语义操作，不从历史 Revision 擦除。

## 5. 来源引用与复水

内部 Session 来源使用 `session_id + entry_id`；外部来源使用稳定 `source_id + locator + captured_at`。对象只保存引用和必要的来源状态，不复制完整正文。

来源读取工具必须返回准确引用、读取结果和错误。无法读取时，原引用保留，相关判断进入 `unverified` 或 `review_required`，不以模型记忆替代。

## 6. 保留与清理

- Revision、确认记录和被交接引用的来源不得按普通缓存过期。
- 原始 Session Entry 的保留服从 Pi Session 策略，但工作包引用的 Entry 在删除前必须完成合规归档或明确使相关对象不可验证。
- Canvas 投影、快照缓存和派生摘要可以重建，不作为长期保留的唯一副本。
- 删除 Workspace 时，按产品删除策略处理 Session、工作包、来源和投影；任一层失败必须可见，不得留下“已删除”假象。

## 7. 失败与恢复

| 原因码 | 处理 |
| --- | --- |
| `memory.session_unavailable` | 稳定状态仍可读；禁止声称已核对缺失对话 |
| `memory.revision_unavailable` | 关闭稳定写入和交接确认 |
| `memory.source_unavailable` | 保留引用并降级相关事实状态 |
| `memory.identity_conflict` | 拒绝复用 ID，要求显式替代或合并 |
| `memory.retention_conflict` | 阻止删除仍被有效对象或交接引用的记录 |

## 8. 验收场景

1. 删除 Canvas 缓存后，所有稳定对象可从 Revision 恢复。
2. 压缩 Session 后，仍能通过 Entry 引用读取交接关键依据。
3. 对象被新方案实质替代时，新旧 ID 和 `supersedes` 关系均可追溯。
4. 来源失效不会删除对象，但会使相关判断和交接状态按规则降级。
5. Session 和 Revision 对同一内容不一致时，以 Revision 判断当前稳定状态，以 Session 解释形成过程。

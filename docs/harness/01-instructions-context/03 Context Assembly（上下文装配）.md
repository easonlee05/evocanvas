# Context Assembly（上下文装配）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi Agent Core transformContext + EvoCanvas 确定性投影`
> 当前实现状态：`部分接入`
> 实现说明：装配发生在 Pi 的每次模型调用前，不由外部服务生成单次请求快照。

## 1. 控制目标

将最新稳定工作状态以可验证、可降级且不污染 Session 的方式加入 Pi 当前模型工作面。

## 2. 输入输出合同

**输入**

```text
workspace_id
session_id
session_branch / current_leaf
current Pi messages
current tool context
```

**输出**

```text
原 Pi messages
+ 一个临时 Workspace Context Snapshot
+ write_capability 状态
```

装配函数不得改写原始 User Entry，不得删改持久 Session Entry，不得产生工作包 Revision。

## 3. 确定性装配算法

1. 根据 `workspace_id` 读取当前 Revision 指针。
2. 读取该 Revision 的完整结构化工作包快照。
3. 校验工作包 Schema、Workspace 身份和 Revision 连续性。
4. 按固定投影规则生成目标、活跃对象索引、未决项、最近变化和来源引用。
5. 结合当前 Tool Context 标记界面焦点，但不改变对象状态。
6. 计算 `write_capability`；只有工作包读取和版本校验成功时才为 `enabled`。
7. 将快照临时加入本次模型消息，并保留原消息顺序。

同一 Revision、同一投影规则版本和同一界面焦点必须产生语义等价快照。

## 4. 复水规则

快照不复制完整对象和来源正文。Pi 通过以下只读能力按需复水：

- `workspace.get_object(object_id, revision_id?)`
- `workspace.get_revision(revision_id)`
- `workspace.diff(from_revision_id, to_revision_id)`
- `session.read_entry(session_id, entry_id)`
- `source.read(source_ref)`

读取结果进入 Pi Session 的 Tool Entry。引用解析失败时保留引用和失败原因，不用近似文本替代。

## 5. 版本与观测

每次装配记录：

```text
session_id
turn_id
workspace_id
revision_id
projection_rule_version
instruction_bundle_version
snapshot_hash
write_capability
failure_reason?
```

`snapshot_hash` 仅用于诊断本次投影，不成为长期业务对象或新事实源。

## 6. 状态推进与回退

- 提交成功：同一 Tool Loop 下一次模型调用重新装配，读取新 Revision。
- 用户直接编辑：下一次 Pi 轮次重新装配，不主动唤起 Pi。
- 基础版本过时：提交工具拒绝；装配器读取最新 Revision，Pi 展示差异后重新确认。
- 投影规则回退：新轮次使用已发布旧版本重新生成快照，不修改工作包历史。

## 7. 失败与恢复

装配预期失败必须返回“原消息 + 显式降级状态”，不得抛出未处理异常而丢失当前用户输入。

| 原因码 | 处理 |
| --- | --- |
| `context.workspace_unavailable` | `write_capability=disabled`，继续普通对话 |
| `context.revision_not_found` | 禁止稳定写入，提示工作状态不可验证 |
| `context.snapshot_invalid` | 不注入故障快照，记录诊断 |
| `context.source_unavailable` | 仅对应来源不可用，相关判断保持未验证 |
| `context.projection_timeout` | 使用本轮无快照降级，不使用缓存快照冒充最新状态 |

## 8. 权限边界

`transformContext` 是只读函数。它不得：

- 自动修复工作包；
- 创建或改变对象状态；
- 根据模型推断补齐缺失字段；
- 将 Canvas 坐标写回领域状态；
- 因快照失败而回退到不明版本。

## 9. 验收场景

1. 连续两次装配同一 Revision，快照哈希一致。
2. 稳定提交后，同一 Tool Loop 的后续模型调用读到新 Revision。
3. 装配超时不会丢失当前 User Entry，也不会提交基于旧快照的变更。
4. 选中卡片变化只改变焦点字段，不改变工作包对象或快照中的事实状态。
5. 读取来源失败时，相邻无关对象仍可使用，相关判断明确保持未验证。

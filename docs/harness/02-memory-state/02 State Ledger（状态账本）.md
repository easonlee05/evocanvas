# State Ledger（状态账本）

> 当前成熟度层级：`L3 可指导实现的治理规格层`
> 编码门槛：`可作为 1.0 对象状态枚举、追加式账本事件、确认记录、包指针和投影重建的实现输入`

## 1. 职责边界

状态账本记录对象、关系、确认和包版本为什么变化。它采用“当前不可变包快照 + 追加式账本事件”，不是完整事件溯源系统。

- 包版本保存某一时点完整结构化状态。
- 状态账本保存重要变化的身份、前后引用、原因和来源。
- 当前指针与治理状态由事件投影形成。
- 对象完整正文不复制进账本。

## 2. 账本事件 Schema

每条 `LedgerEvent` 至少包含：

| 字段 | 含义 |
| --- | --- |
| `ledger_event_id` | 事件唯一标识 |
| `workspace_id / package_id` | 所属范围 |
| `package_version` | 事件关联的包版本，可空 |
| `state_version_before / state_version_after` | 事实状态前后版本 |
| `event_type` | 可枚举事件类型 |
| `entity_type / entity_id` | 目标包、版本、对象、关系或确认记录 |
| `before_ref / after_ref` | 前后对象或版本引用，可空 |
| `operation_id` | 原子提交幂等键 |
| `convergence_run_id` | 来源收敛回合，可空 |
| `chat_turn_id` | 主要关联 Chat，可空 |
| `message_refs` | 相关原始消息引用 |
| `source_refs` | 相关来源或工具结果引用 |
| `confirmation_id` | 关联确认记录，可空 |
| `unresolved_refs` | 变化后仍存未决，可空 |
| `reason_codes` | 可枚举变化原因 |
| `actor_type / actor_id` | `user / system / migration` 及标识 |
| `occurred_at` | 事实提交时间 |

消息、来源、确认和对象引用必须指向真实记录。模型可以提出原因候选，但不能生成事件 ID、版本号、消息 ID 或提交时间。

## 3. 事件类型

1.0 至少支持：

```text
package_created
package_archived
package_version_created
current_version_moved
latest_confirmed_version_moved
package_version_confirmed
package_version_marked_outdated
package_version_risk_annotated
object_created
object_content_updated
object_status_changed
object_superseded
relation_created
relation_removed
source_link_changed
confirmation_recorded
confirmation_withdrawn
```

投影成功、Toast 已显示或页面已打开不属于事实账本事件，它们进入 Outbox、投影或可观测性记录。

## 4. 对象状态模型

### 4.1 唯一权威业务状态

每类对象只维护一个 `object_status`：

| 对象类型 | 允许状态 |
| --- | --- |
| 证据 `evidence` | `collected / cited / archived` |
| 问题 `problem` | `initial / converging / converged / archived` |
| 待澄清 `clarification` | `open / pending_confirmation / clarified / blocked / closed` |
| 约束 `constraint` | `effective / superseded / archived` |
| 待决策 `decision` | `pending_decision / pending_confirmation / decided / archived` |

交接有效性属于包版本治理状态，不是第六类独立对象状态。画布中的交接物承接卡由包版本和 `handoff` 引用模块确定性投影。不得再维护一套可以独立修改的“通用卡片状态”；界面需要通用分组时，使用下述确定性映射。

### 4.2 通用治理地位

`governance_class` 由 `object_type + object_status` 派生：

| 通用地位 | 典型映射 |
| --- | --- |
| `source` 来源 | 证据 `collected / cited` |
| `working` 工作中 | 问题 `initial / converging` |
| `unresolved` 未决 | 待澄清 `open / pending_confirmation / blocked`；待决策 `pending_decision / pending_confirmation` |
| `stable` 稳定 | 问题 `converged`；待澄清 `clarified`；约束 `effective`；待决策 `decided` |
| `historical` 历史 | 各类 `archived`、约束 `superseded`、待澄清 `closed` |

映射规则必须版本化并可重算。任何服务不得直接写 `governance_class` 来绕过类型状态门禁。

### 4.3 验证状态

`validation_state` 与业务状态分开：

```text
unverified / valid / warning / invalid
```

对象可以处于 `initial + warning`，但不能因为验证失败就把业务状态写成“异常”。`invalid` 对象不得升级为稳定地位。

## 5. 状态流转与同提交升级

合法流转由对象治理和结构验证共同定义。状态账本补充以下规则：

1. 每次 `object_status_changed` 必须记录原状态、新状态、来源和原因。
2. 对象进入 `effective / decided / clarified` 必须关联有效确认记录；包版本进入 `confirmed` 由独立包版本事件表达，也必须关联有效确认记录。
3. Chat 已经包含完整确认时，同一原子提交可以创建处于稳定状态的对象；约束卡不得为了经过候选态而额外持久化 `draft` 或 `pending_confirmation`。
4. 同提交升级不要求持久化一版等待确认的中间包，但账本事件顺序必须完整。
5. 确认只覆盖明确范围；未覆盖字段和对象保持原状态。
6. 替代、撤回和过时通过新事件表达，不删除旧事件。

## 6. 确认记录

`ConfirmationRecord` 至少包含：

| 字段 | 含义 |
| --- | --- |
| `confirmation_id` | 确认记录 ID |
| `workspace_id / package_id` | 作用范围 |
| `confirmation_path` | `assistant_proposal_then_user_response / direct_user_statement` |
| `proposal_message_refs` | Assistant 提出判断和范围的消息引用；用户直接陈述时可空 |
| `user_message_refs` | User 直接陈述、确认、否定或修正的消息引用 |
| `confirmed_claims` | 被确认的具体判断 |
| `scope_refs` | 对象、字段、版本或时间范围 |
| `confirmation_kind` | `confirmed / partial / rejected / corrected / withdrawn` |
| `remaining_unresolved_refs` | 未随本次确认一起解决的事项 |
| `recorded_at` | 记录时间 |

确认可以来自“Assistant 明确提议后 User 确认或修正”，也可以来自 User 主动给出的明确、完整且带范围的产品判断。后一种情况不要求 Assistant 先复述、再让 User 重复确认；但试探表达、举例、转述、反问和范围不清的陈述不得按直接确认记录。

确认记录本身不可改写。用户撤回时追加 `confirmation_withdrawn` 和新的确认记录或状态变化，不覆盖旧原文。

## 7. 包版本和指针事件

### 7.1 正文提交与新版本

成功正文提交至少在同一事务内追加：

1. `package_version_created`。
2. 本次对象、关系、来源和确认事件。
3. `current_version_moved`。
4. 必要时 `latest_confirmed_version_moved`。
5. 对应 Outbox 事件。

账本事件、当前结构化状态、不可变包版本、指针和 Outbox 必须一起成功或一起失败。

### 7.2 纯治理提交

确认已有版本、标记版本过时或追加风险标注时，正文和对象图没有变化：

1. 不创建新的 `state_version` 或 `package_version`。
2. 追加确认记录和对应包版本治理事件。
3. 必要时追加 `latest_confirmed_version_moved`。
4. 同一事务登记对应 Outbox 事件。

确认记录、治理事件、版本指针与 Outbox 必须一起成功或一起失败。纯治理提交同样使用 `operation_id`、目标版本和期望版本做幂等与过期校验。

### 7.3 当前版本

`current_version` 总是指向当前 Chat 和收敛默认读取的最新工作版本。回退不是把指针直接拨回旧版本，而是基于旧版本创建一个新的当前版本。

### 7.4 最近可用确认版本

`latest_confirmed_version` 指向最近仍可作为正式交接依据的确认版本：

- 新草稿版本不会自动改变它。
- 新版本被确认后可以推进它。
- 当前指向版本被判定过时时，应重新指向仍有效的最近确认版本；不存在时置空。
- 历史上曾被确认但已过时的版本仍可通过账本查询。

## 8. 未决与投影

账本事件可以记录 `unresolved_refs`，但未决正文仍在结构化对象中。

- `governance_class = unresolved` 且仍活跃的对象可以投影到 Active Todos。
- 对象进入稳定或历史状态后，对应 Todo 失效。
- 待澄清进入 `clarified / closed` 后退出主画布默认当前视图，但对象、确认和结果关系继续保留；重新打开后才恢复默认显影。
- 待决策进入 `decided` 后退出 Active Todos，但继续作为稳定决策结构显影，直到重新打开、替代或归档。
- 里程碑只消费一组对象状态变化，不独立宣布事实。
- 交接模块只引用当前版本中真实存在的对象。

投影失败时由 Outbox 重放或当前包版本重建，不追加虚假的事实事件。

## 9. 查询与重建

状态账本至少支持按以下键查询：

- `package_id`
- `package_version`
- `object_id`
- `operation_id`
- `convergence_run_id`
- `confirmation_id`
- `event_type`

包版本正文用于恢复完整工作状态；账本用于恢复指针、治理状态、确认链和变化历史。账本不保存完整正文，因此不要求仅靠事件重放重建所有对象内容。

## 10. 旧实现迁移

当前 `workspace.metadata.state_ledger` 是覆盖式摘要，不是目标账本。迁移时：

- 将现有卡片与交接状态写入初始包版本。
- 为可验证的当前状态生成一组 `migration` 事件。
- 旧 `stage_node / checkpoint / next_progression_hint` 不迁入对象状态。
- 旧 `pending_gate_ids` 与确认队列不转成等待任务；只保留可追溯提案和消息引用。
- 无法证明的历史状态标为 `warning`，不伪造确认事件。

## 11. L3 验收场景

- 任一稳定对象都能回到确认记录和原始消息。
- 通用治理地位可以从类型和业务状态重算，不存在双写漂移。
- 同一 Chat 已确认的对象可以在一个提交中创建并进入稳定状态，账本仍保留有序事件。
- 新草稿版本不会覆盖最近可用确认版本。
- 确认版本过时后指针能回退到其他仍有效版本或置空。
- 相同 `operation_id` 重试不会追加重复账本事件。
- 当前包快照丢失时不能只凭摘要伪造正文；索引或投影损坏时可以从版本和账本重建。

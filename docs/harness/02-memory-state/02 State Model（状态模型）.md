# State Model（状态模型）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`结构化工作包 Revision`
> 当前实现状态：`合同已定，代码待迁移`
> 实现说明：目标架构不建立独立 State Ledger；所有稳定状态都在完整 Revision 中。

## 1. 控制目标

定义对象、关系、确认和交接状态如何在不可变 Revision 之间推进，防止把投影状态、运行状态或追加日志误作当前业务状态。

## 2. 稳定对象状态

每类正式对象只维护主 PRD 定义的一套类型化状态，不再叠加可写的通用生命周期：

```text
evidence:      recorded | referenced | archived
problem:       initial | converging | converged | archived
clarification: raised | awaiting_confirmation | clarified | blocked | closed
constraint:    effective | superseded | archived
decision:      pending_judgement | awaiting_confirmation | decided | archived
handoff:       draft | awaiting_confirmation | confirmed | suspended | invalidated | superseded
```

约束：

- 中文产品文案分别显示为主 PRD 中的“已收录 / 已引用 / 已归档”等状态；英文代码值只用于稳定接口。
- 未确认的约束、问题、待澄清或待决策候选只存在于 Session，不得借用 `draft` 或 `awaiting_confirmation` 绕过显影边界。
- `clarification.awaiting_confirmation` 与 `decision.awaiting_confirmation` 只适用于其主题和范围已经被用户固定、因而已成为正式工作事实的对象；不是 Pi 候选队列。
- 被新对象实质替代时，旧对象使用该类型允许的 `superseded / archived` 状态，并通过 `supersedes` 关系保留替代链。
- 对象可另有派生审查标记 `review_required: true`；该标记不覆盖类型化状态。
- Canvas 上的交接物承接卡可将 `suspended / invalidated / superseded` 统一显示为“已过时”，但必须保留具体原因，且该显示标签不是第二套可写状态。

## 3. 信息地位

信息地位不使用一个混合枚举。必须分开记录：

```text
object_type                 # evidence / problem / clarification / constraint / decision
source_integrity_status     # traceable / incomplete / unavailable，适用于来源
verification_status         # unverified / verified / contradicted，适用于外部真实性
adoption_status             # not_adopted / assumed / accepted / rejected，适用于产品采用
type_status                 # 按 object_type 使用唯一类型化状态
review_required             # true / false
```

Pi 推断的问题、约束和决定只有经用户确认其含义和范围后，才可以相应对象类型进入工作包。提交器只验证字段和转换，不替代用户做语义判断。

## 4. 确认状态

确认记录是 Revision 内不可变记录，至少包含：

```text
confirmation_id
actor_id
confirmed_at
base_revision_id
scope_object_ids[]
scope_relation_ids[]
content_hashes[]
confirmation_kind
accepted_risks[]
```

内容、范围或依赖变化后，旧确认记录仍保留，但不自动覆盖新内容。不得通过“对象 ID 没变”继续沿用过期确认。

## 5. 交接状态

```text
draft -> awaiting_confirmation -> confirmed
confirmed -> suspended | invalidated | superseded
suspended -> awaiting_confirmation | invalidated
```

- `draft`：已形成稳定内容，但尚未进入交接确认。
- `awaiting_confirmation`：确认内容、范围和风险已明确，等待用户确认。
- `confirmed`：绑定具体 Revision、内容和范围，允许下游使用。
- `suspended`：影响不明，暂时不可用于新下游执行。
- `invalidated`：关键依据已失效，不可继续使用。
- `superseded`：已有新的已确认交接版本替代。

## 6. 依赖传播

提交器只执行确定性传播：

1. 显式依赖对象变化，标记下游 `review_required=true`。
2. 被确认内容哈希变化，确认覆盖失效。
3. 交接引用的关键依据被撤回或替代，交接 `invalidated`。
4. 影响无法通过显式依赖判断，交接 `suspended`。
5. 不自动改写下游正文，不调用模型做隐藏裁决。

## 7. 提交操作

允许的语义操作包括：

- `create_object`
- `update_object`
- `change_status`
- `supersede_object`
- `create_relation`
- `remove_relation`
- `record_confirmation`
- `confirm_handoff`
- `suspend_handoff`
- `invalidate_handoff`

禁止整包自由覆写。每组操作必须在一个 `base_revision_id` 上原子应用并生成完整新 Revision。

## 8. 失败与恢复

- 非法状态转换：`workspace.invalid_transition`，整个提交失败。
- 引用不存在：`workspace.reference_missing`，整个提交失败。
- 确认范围与内容哈希不匹配：`workspace.confirmation_mismatch`。
- 基础版本过时：`workspace.stale_revision`，返回最新版本供重做差异。
- 依赖环：`workspace.dependency_cycle`，拒绝创建关系。
- 已知提交结果未知：通过 `idempotency_key` 查询。

## 9. 验收场景

1. 候选方案不允许以 `draft` 对象绕过确认进入工作包。
2. 更新已确认约束正文后，旧确认记录仍存在但不再覆盖新哈希。
3. 替代对象创建新 ID，旧对象转为 `superseded` 且历史 Revision 不变。
4. 显式上游变化只标记下游复核，不自动改写下游决定。
5. 已归档或已替代对象不能通过通用状态字段恢复；必须使用该对象类型允许的显式操作或创建替代对象。

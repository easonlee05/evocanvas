# Source Verification（来源验证）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Session / Source 读取工具 + 结构化工作包来源字段`
> 当前实现状态：`原生来源验证已接入，追溯闭环待验证`
> 实现说明：验证来源可定位性与外部真实性状态，二者分别记录。

## 1. 控制目标

确保稳定对象的依据能够被准确找回，并防止“引用存在”被误报成“事实为真”。

## 2. 来源类型

- Pi Session：`session_id + entry_id`。
- 文件或外部系统：`source_id + locator + captured_at + connector_identity`。
- 工具核验结果：`tool_call_id + result_ref + verified_at`。
- 用户直接编辑：`actor_id + ui_action_id + base_revision_id`，仅证明编辑行为，不证明外部事实。

## 3. 完整性检查

来源达到 `traceable` 至少要求：标识存在、主体有读取权限、定位信息可解析、引用内容与声明范围一致。正文暂时不可读时状态为 `unavailable`，不能静默删除引用。

## 4. 外部真实性核验

`verified` 必须绑定核验方法、时间、核验来源、结论和适用范围。核验结果过时或被新证据反驳时，创建新的来源状态和 Revision，不修改历史核验记录。

## 5. 引用粒度

默认来源绑定对象或关系；对象包含多个独立判断且来源不同，必须细化到判断路径或字段范围。不得用一个宽泛来源引用支撑整个交接物的所有结论。

## 6. 失败与恢复

| 原因码 | 行为 |
| --- | --- |
| `source.ref_invalid` | 不允许来源事实进入稳定状态 |
| `source.permission_denied` | 不泄露正文，保留受限状态 |
| `source.unavailable` | 相关内容保持未验证，可稍后重读 |
| `source.verification_failed` | 保持 unverified，不推定 contradicted |
| `source.contradicted` | 并列保留证据并触发依赖复核 |
| `source.scope_mismatch` | 拒绝用该引用支持超出范围的判断 |

## 7. 验收场景

1. Session Entry 可读且定位准确时来源为 traceable，但默认仍非 externally verified。
2. 文件移动导致 locator 失效时，相关对象保留但来源状态降级。
3. 一条来源只覆盖对象部分判断时，不能支撑其余字段。
4. 核验工具失败不会把事实标记为错误。
5. 新证据反驳旧证据时，两者及依赖影响均可追溯。

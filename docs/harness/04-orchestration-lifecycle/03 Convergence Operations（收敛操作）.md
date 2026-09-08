# Convergence Operations（收敛操作）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`同一 Pi Tool Loop + workspace.commit`
> 当前实现状态：`合同已定，代码待迁移`
> 实现说明：“收敛操作”是从候选讨论到稳定 Revision 的语义操作集合，不是独立运行类型。

## 1. 控制目标

把 Pi 与用户已达成的具体稳定理解转换为最小、可审计、可回退的工作包变更，同时保留未确认内容在 Session。

## 2. 候选与稳定操作

Pi 可在对话中自由形成候选对象和关系，但提交时只能使用受治理操作：

```text
create_object
update_object
change_status
supersede_object
create_relation
remove_relation
record_confirmation
confirm_handoff
suspend_handoff
invalidate_handoff
```

不提供“根据整段对话自动重写整个工作包”或“自由 JSON 覆盖”操作。

## 3. 提交提案

提交前 Pi 必须让用户能够理解：

- 哪些对象或关系将变化；
- 每项变化的稳定含义；
- 依据的来源或已说明假设；
- 影响范围和显式依赖；
- 是否改变交接状态；
- 哪些候选仍不会进入工作包。

确认可用自然语言完成，不强制固定表单；提交器必须能引用对应 User Entry 和内容哈希。

## 4. 部分确认

用户只确认提案的一部分时：

- 仅提交被明确覆盖的独立操作；
- 未确认操作继续留在 Session；
- 若操作存在原子依赖，必须整体等待确认或重新拆分提案；
- 不通过默认勾选推定用户确认剩余范围。

## 5. 复杂输入

长材料、截图说明或会议记录进入 Session / 来源后，Pi 可以分批读取和讨论。只有来源完整性收录可自动稳定记录；从材料推导的问题、约束、冲突或决定必须逐项获得适当确认。

## 6. 直接编辑

用户直接编辑调用同一操作模型：界面将编辑转换为语义操作，用户编辑动作作为该具体变更的确认，随后执行版本、权限、来源和依赖校验。若编辑影响已确认交接，界面必须显示相应状态变化。

## 7. 失败与恢复

| 原因码 | 处理 |
| --- | --- |
| `workspace.confirmation_required` | 保持候选，不提交 |
| `proposal.scope_ambiguous` | 继续澄清作用范围 |
| `proposal.atomic_group_incomplete` | 不做部分提交，重新组织提案 |
| `workspace.stale_revision` | 读取差异并重做受影响确认 |
| `proposal.source_missing` | 相关判断保持假设或未验证 |
| `workspace.commit_failed` | 工作包不变，保留提案和失败原因 |

## 8. 验收场景

1. 用户只确认三项提案中的一项，Revision 只包含该项独立变更。
2. 两个相互依赖的操作只确认一个时，提交被阻止。
3. Pi 从会议纪要推断出约束但用户未确认时，不生成正式约束对象。
4. 用户直接编辑已确认约束后，同一提交内更新确认覆盖和交接影响。
5. 重试同一提案只产生一个 Revision。

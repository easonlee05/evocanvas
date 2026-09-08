# Convergence Readiness（收敛就绪度）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`Pi 语义提案 + workspace.commit 确定性门禁`
> 当前实现状态：`合同已定，代码待迁移`
> 实现说明：目标架构不使用模型置信分或收敛水位触发独立运行；只判断一个具体变更是否已具备稳定提交条件。

## 1. 控制目标

把“Pi 觉得差不多了”与“这个具体内容可以稳定生效”分开，避免用概率分数代替用户确认、来源和版本门禁。

## 2. 就绪条件

一个语义变更只有同时满足以下条件才可调用稳定提交：

```text
内容明确
作用范围明确
信息地位明确
依据或未验证前提明确
显式依赖明确
用户确认覆盖具体内容与范围
actor 有权限
base Revision 仍有效
```

来源事实的自动完整性收录不需要语义确认，但必须有稳定引用和真实验证状态。

## 3. 不采用数值置信度

不维护 `convergence_score`、累计水位、触发阈值或模型自报 confidence。模型概率无法证明用户意图、权限、来源真实性或确认范围，因此不能作为稳定写入门禁。

## 4. 可观察状态

对当前具体提案可显示：

- `exploring`：仍在讨论，仅 Session。
- `needs_clarification`：含义、范围或依据不足。
- `awaiting_confirmation`：提案明确，等待用户确认。
- `ready_to_commit`：确认和确定性前置条件齐全，仅为瞬时执行条件。
- `committed`：工具返回新 Revision。

这些状态是对话/界面派生状态，不持久为产品运行状态机；稳定结果只看 Revision。

## 5. 回退与过时

任何提案内容、范围、依赖或基础 Revision 变化，`awaiting_confirmation / ready_to_commit` 立即失效并重新计算。提交失败后不能继续显示 committed；结果未知时显示核对中。

## 6. 失败与恢复

| 原因码 | 行为 |
| --- | --- |
| `proposal.content_ambiguous` | 继续澄清 |
| `proposal.scope_ambiguous` | 明确对象和关系范围 |
| `workspace.confirmation_required` | 等待用户确认 |
| `proposal.source_incomplete` | 补来源或明确为假设 |
| `workspace.stale_revision` | 重做差异和受影响确认 |
| `auth.capability_denied` | 不调用提交工具 |

## 7. 验收场景

1. Pi 表达“我很确定”但无用户确认时仍不能提交。
2. 用户确认后基础 Revision 变化，就绪状态失效。
3. 未验证前提被明确保留并接受风险时，可以达到交接就绪，但不会变成 verified。
4. 提交 Tool Result 失败时不显示 committed。
5. 简单问答无需进入任何就绪状态。

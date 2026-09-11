# Handoff Governance（交接物治理）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`结构化工作包 + 交接确认与渲染能力`
> 当前实现状态：`原生交接治理已接入，过时边界待验证`
> 实现说明：交接物是已确认 Revision 的派生输出；不保存一份可独立漂移的正文。

## 1. 控制目标

保证任何被人或下游 AI 使用的交接物都能回答：来自哪个 Revision、谁确认了什么、还存在哪些未决和风险、当前是否仍有效。

## 2. 确认条件

交接确认前必须满足：

1. 目标 Revision 可读取且 Schema 有效。
2. 交接范围内对象和关系可追溯。
3. open issue、review_required 和未验证前提均被展示。
4. 用户确认准确内容和作用范围。
5. 未验证风险若被接受，确认记录显式绑定风险。
6. current Revision 未在展示后发生相关变化。

未决项存在不必绝对阻止交接；隐藏未决项或风险必须阻止。

## 3. 下游读取

默认返回 `latest_confirmed_handoff_revision_id`，并附带 handoff 状态、Revision、确认、风险和渲染规则版本。draft、suspended、invalidated 版本不得作为默认下游输入。

## 4. 过时与替代

- 无影响的新变化：旧交接继续有效。
- 关键依据、约束或决定变化：旧交接 invalidated。
- 影响不明：旧交接 suspended。
- 新交接确认：旧交接 superseded。

任何状态变化通过新 Revision 留痕。

## 5. 外部行动边界

交接 confirmed 只表示内容可用，不授权发送、发布、创建任务或执行实现。下游外部行动需由对应工具再次取得动作级授权。

## 6. 失败与恢复

| 原因码 | 行为 |
| --- | --- |
| `handoff.revision_stale` | 展示差异并重新确认 |
| `handoff.scope_incomplete` | 补齐对象、关系或风险范围 |
| `handoff.risk_unacknowledged` | 不确认交接 |
| `handoff.no_confirmed_revision` | 下游不回退到 draft |
| `handoff.render_failed` | 保留确认状态，从 Revision 重建 |
| `handoff.invalidated` | 阻止新下游使用并说明原因 |

## 7. 验收场景

1. 有公开未决项的交接可在用户确认后发布，并明确标注未决。
2. 隐藏未决项的渲染结果不能通过交接确认。
3. current Revision 改变关键约束后，旧确认交接不能继续作为默认下游输入。
4. 交接渲染失败不删除确认记录。
5. 已确认交接无法直接触发外部发送。

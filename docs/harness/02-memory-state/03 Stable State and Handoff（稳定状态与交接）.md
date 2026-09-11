# Stable State and Handoff（稳定状态与交接）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`结构化工作包 + 交接渲染器`
> 当前实现状态：`原生交接合同已接入，完整验证待补齐`
> 实现说明：结构化交接物是已确认工作包 Revision 的派生视图，不是独立正文事实源。

## 1. 控制目标

让人和下游 AI 使用同一份可追溯、可判断是否过时的稳定交接结果，并避免复制一份随后与工作包漂移的文档正文。

## 2. 交接引用

工作包保存交接状态和指针：

```text
handoff_id
handoff_status
handoff_revision_id
confirmed_revision_id?
confirmation_id?
render_profile_id
accepted_risks[]
invalidated_by[]
supersedes_handoff_id?
```

交接内容在读取时由指定 Revision 和渲染规则确定性生成。可缓存渲染结果，但缓存不拥有独立编辑权。

## 3. 生成与确认

1. Pi 或用户完成稳定对象提交，形成新 Revision。
2. 交接渲染器从该 Revision 生成 `draft` 交接视图。
3. 用户确认准确内容、覆盖范围、未决项和已接受风险。
4. `confirm_handoff` 在新 Revision 中记录确认并设置 `latest_confirmed_handoff_revision_id`。
5. 下游默认只读取最近有效的已确认交接 Revision，不读取 current Revision 中未确认的新变化。

确认当前工作包不等于确认交接；确认交接也不授权外部不可逆执行。

## 4. 当前版本与已确认版本

必须同时维护：

- `current_revision_id`：工作包最新稳定状态。
- `latest_confirmed_handoff_revision_id`：最近仍有效、可供下游使用的交接状态。

二者可以不同。新提交不会自动替代已确认交接；只有完成影响判断和交接确认后才更新后者。

## 5. 过时判断

新 Revision 产生后执行：

| 影响 | 交接处理 |
| --- | --- |
| 与交接范围无关 | 原已确认交接继续有效 |
| 明确改变关键依据、约束或决定 | 原交接 `invalidated` |
| 存在潜在影响但无法确定 | 原交接 `suspended`，等待澄清 |
| 新交接已确认 | 原交接 `superseded` |

不得自动把新 current Revision 当作已确认交接交给下游。

## 6. 未验证前提

用户可以基于未验证外部前提形成内部产品决定，但必须：

1. 将前提保存为 `assumption`，保留来源和未验证状态。
2. 将依赖该前提的决定建立显式关系。
3. 交接确认时展示该前提和潜在影响。
4. 用户若仍确认交接，确认记录必须包含对应 `accepted_risk`。
5. 下游渲染继续标注“前提未验证”，不得改写为事实。

## 7. 失败与恢复

- 渲染失败：Revision 和确认状态不变，稍后从相同 Revision 重建。
- 确认时 current Revision 已变化：拒绝确认，展示目标 Revision 与当前 Revision 差异。
- 来源失效：按显式依赖更新交接状态，不删除旧交接。
- 下游请求无有效确认版本：返回 `handoff.no_confirmed_revision`，不得回退到 draft。
- 风险接受范围不完整：返回 `handoff.risk_scope_incomplete`。

## 8. 验收场景

1. current Revision 新增无关备注，最近已确认交接仍有效。
2. current Revision 修改交接关键约束，旧交接立即失效而不是静默继续使用。
3. 用户基于未验证市场数据作决定并接受风险，交接可确认但持续标注该前提。
4. 渲染缓存丢失后可由已确认 Revision 生成语义等价交接物。
5. 下游未指定版本时只能获得最近有效已确认交接，不能获得最新 draft。

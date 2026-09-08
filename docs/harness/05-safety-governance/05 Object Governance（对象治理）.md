# Object Governance（对象治理）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`结构化工作包 Schema + Canvas Renderer`
> 当前实现状态：`合同已定，代码待迁移`
> 实现说明：工作包保存五类规范化业务对象和交接治理状态；Canvas 投影为六类正式卡片。

## 1. 控制目标

为五类正式业务对象和一类交接投影定义进入稳定状态、更新、替代和显影规则，避免用卡片 UI 状态代替领域治理。

## 2. 五类对象与交接投影

| 对象 / 卡片 | 稳定含义 | 进入工作包条件 |
| --- | --- | --- |
| 证据 | 可追溯来源陈述及验证状态 | 来源完整性检查通过即可收录 |
| 问题 | 已固定的问题定义 | 用户确认问题含义和范围 |
| 待澄清 | 已固定的信息缺口或歧义 | 用户确认需要保留为未决 |
| 约束 | 对方案空间的稳定边界 | 用户确认内容、范围和依据 |
| 待决策 / 方案承接 | 正式比较项或已确认决定 | 用户确认比较范围或选择结果 |
| 交接物承接卡 | 指向某个交接 Revision 的投影，不是独立业务对象 | 工作包稳定且按交接规则生成 |

卡片标题、摘要和布局是投影字段；对象正文、状态、关系和来源在工作包中权威存在。

## 3. 通用字段

```text
object_id
type
type_status
source_integrity_status?
verification_status?
adoption_status?
title
body
source_refs[]
relation_ids[]
review_required
created_revision_id
last_changed_revision_id
supersedes_object_id?
```

对象类型特有字段由版本化 Schema 定义，不得在 Canvas 自由扩展成新的事实字段。

## 4. 创建和更新规则

- 证据收录不自动产生问题或约束。
- Pi 推断的其他对象必须经用户确认后创建。
- 更新正文需新 Revision；若语义实质改变，使用新对象和 `supersedes`。
- 关闭、归档、决定、解决和替代使用该对象类型允许的显式状态操作，不新增通用可写生命周期。
- 删除关系必须触发依赖和交接影响检查。

## 5. 关系治理

允许的核心关系至少包括：

```text
supports
contradicts
depends_on
clarifies
constrains
resolves
supersedes
included_in_handoff
```

每条关系有独立 ID、来源/确认和创建 Revision。不得通过纯 Canvas 连线创建无治理关系；用户连线操作必须转成语义关系提案或直接编辑提交。

## 6. Canvas 显影

只有 current Revision 中允许显影的稳定对象才生成正式卡片。`review_required`、`suspended`、`invalidated` 等状态必须可见，但布局变化不产生工作包 Revision，除非产品明确将某项布局信息定义为业务语义。

## 7. 失败与恢复

- 未知对象类型：`object.type_unknown`，拒绝提交。
- 非法关系：`object.relation_invalid`。
- 实质替代却复用 ID：`object.identity_conflict`。
- 缺少确认：`object.confirmation_required`。
- 投影 Schema 不兼容：保留 Revision，使用兼容 Renderer 或显示降级卡片。

## 8. 验收场景

1. 证据卡进入工作包不会自动生成对应约束卡。
2. Pi 提出的待澄清项未确认时 Canvas 不出现卡片。
3. 用户拖动卡片不产生业务 Revision。
4. 用户创建“支持”连线时，关系按语义提交并可追溯确认。
5. 实质新方案不会覆盖旧对象 ID，Canvas 可显示替代关系。

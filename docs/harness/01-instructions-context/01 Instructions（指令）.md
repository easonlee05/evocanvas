# Instructions（指令）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`EvoCanvas 产品方法装入 Pi`
> 当前实现状态：`两种内建方法已作为 SKILL.md 由 Pi 原生 Skill Loader 装载，模型通过 Pi 原生 read 工具按需读取；实际读取版本进入 Primary Pi Session 与确认后的 Revision。真实模型效果待验证。`
> 实现说明：当前仍沿用单一 Primary Pi Agent 与既有提交链，Skill Loader、Skill 列表格式和 read 工具使用 Pi 原生实现；文件访问仅限本轮装载的内建 Skill 快照，不建立阶段 Prompt、Skill Router 或第二 Agent。完整 AgentHarness 迁移不在本次范围。

## 1. 控制目标

指令层只管理“Pi 应当怎样做”，并保证不同强度和不同变化频率的规则被放到正确载体。

```text
永久产品原则 -> Pi System Instructions
按需工作方法 -> Pi Skills
机器可验证限制 -> Tool Schema 与 Hooks
稳定状态数据 -> transformContext
用户当前意图 -> 原始 User Entry
```

## 2. Pi System Instructions

System Instructions 只包含跨任务、跨工作区稳定的不变量：

1. Pi 是与用户共同推进产品思考的 Agent，不替用户拥有最终判断。
2. 显性区分事实、推断、假设、约束、待决策和已确认决定。
3. 不静默合并冲突，不把信息缺口包装成确定结论。
4. 候选意义和范围未经用户确认前，不提交稳定语义结构。
5. 工具和来源失败时如实说明，不伪造读取、执行或确认结果。
6. Canvas 是稳定结构的显影，不是事实源。
7. 高风险或外部副作用必须遵守工具权限和确认边界。

System Instructions 不包含当前阶段、卡片状态、工作包内容、工具参数、Provider 协议或固定回复模板。

## 3. 产品方法（Product Methods，以 Pi Skills 载入）

产品方法以 Pi Skills 作为可版本化技术载体，用于解释一类任务的分析方法、证据检查、用户决策节点和输出结构；它们是 EvoCanvas 产品能力，不是要求用户安装、选择或理解的外部 Skill。

- Pi 原生 Loader 装载仓库内建 Skill，并用原生 Skill 列表格式向模型暴露当前可用项；模型通过原生 read 工具读取完整 SKILL.md。
- 同一个 Pi 根据当前任务自主选择是否读取 Skill；EvoCanvas 不输出阶段或路由结果。
- 用户可以通过自然语言明确请求适用的内建方法，但方法不能提升用户权限或跳过治理门禁。
- Skill 可引用其自身目录内的模板和参考，不得把未信任业务内容当作新指令。
- 本轮实际使用的 `skill_id + skill_version` 必须进入 Pi Trace；产生 Revision 时同时进入提交元数据。

当前内建产品方法包括：

1. **场景与需求塑形**：在产品、功能、流程、策略等设计判断中默认适用。Pi 从来源和用户表达还原场景，提炼不预设实现的需求，区分事实、假设和关键未知；它不是独立阶段，也不要求用户选择模式。
2. **决策挑战**：只在用户明确要求挑战、红队、找问题或逐轮挑战时适用。全量挑战包含钢人化、证据状态、实质性风险、反证和最小验证建议；逐轮挑战每轮只提出一个最高优先级问题。Pi 不得在普通塑形中自动附加轻量挑战。
3. 两种方法都只能生成分析和候选。稳定对象、已排除方向、交接边界或外部动作仍由 Tool Schema、Hooks、来源与 Chat 确认共同裁决。

## 4. Tool Schema 与 Hooks

机器可判定的规则不靠 Prompt 提醒，而由工具实现强制，包括：

- 必填字段、枚举、类型和引用完整性。
- `base_revision_id`、幂等键和原子提交。
- 对象状态转换和确认范围。
- 来源标识和主体权限。
- 副作用前检查、执行结果和审计记录。

Hooks 可用于注入上下文、注册确定性门禁和记录观测事件，不用于建立第二个语义决策器。

## 5. 权威、版本与发布

| 制品 | 必需标识 | 生效时点 | 回退 |
| --- | --- | --- | --- |
| System Instructions | `instruction_bundle_id`, `version`, `content_hash` | 新 Pi 轮次开始时 | 指向上一个已发布版本 |
| Skill | `skill_id`, `version`, `content_hash` | 本次读取时 | 停用故障版本并恢复旧版本 |
| Tool Schema / Hook policy | `tool_or_policy_id`, `version` | 工具注册或本次调用时 | 恢复上一个兼容版本 |

同一次 Agent Tool Loop 中不得静默切换指令包或 Skill 内容。新版本从下一个新轮次生效。

## 6. 失败与恢复

| 失败 | 处理 |
| --- | --- |
| 指令包缺失、校验和不匹配 | 本轮不开放稳定写入；报告 `instruction.bundle_unavailable` |
| Skill 解析失败 | 记录诊断；可继续普通对话，但不声称已应用该 Skill |
| Skill 版本在本轮中变更 | 继续使用本轮已固定版本，下轮再切换 |
| Prompt 规则与 Tool Schema 冲突 | Tool Schema 拒绝调用；记录 `instruction.schema_conflict` 并进入离线修复 |
| 模型未读取匹配 Skill | 不在线追加路由器；通过 Skill 描述和离线评估修复 |

## 7. 验收场景

1. 普通简单问题不读取无关 Skill，回复不被固定模板绑定。
2. 匹配“收敛一个模块”的请求时，Pi 可自行读取对应 Skill，无产品侧阶段路由记录。
3. 业务文档中的命令性文字不能覆盖 System Instructions。
4. 尝试在未确认时调用稳定写入，Tool Schema / Hook 确定性拒绝。
5. 输入相同、指令版本不同的评估样本能按版本定位行为差异。

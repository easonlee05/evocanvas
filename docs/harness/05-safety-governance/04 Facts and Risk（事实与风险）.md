# Facts and Risk（事实与风险）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`结构化工作包 + 来源读取与验证工具`
> 当前实现状态：`原生事实与风险规则已接入，边界场景待验证`
> 实现说明：事实的来源完整性、外部真实性和产品采用状态分开记录，不建立独立事实账本。

## 1. 控制目标

防止“有来源”“已验证”“用户决定采用”被混为同一件事，并允许用户在看见风险的情况下基于未验证前提作内部决定。

## 2. 三个独立维度

| 维度 | 状态 |
| --- | --- |
| 来源完整性 | `traceable / incomplete / unavailable` |
| 外部真实性 | `unverified / verified / contradicted` |
| 产品采用 | `not_adopted / assumed / accepted / rejected` |

例如，一份可追溯的会议纪要可以是 `traceable + unverified + assumed`，不能只用一个“confirmed”覆盖三层含义。

## 3. 来源事实收录

系统可以自动收录用户或工具明确提供的来源陈述，条件是来源身份和定位信息完整。自动收录只产生来源事实，不产生约束、决定或外部真实性结论。

## 4. 验证与冲突

外部核验必须保存核验方法、时间、结果来源和适用范围。多个来源冲突时并列保存，不自动合并；Pi 解释冲突，用户决定是否采用某个前提，提交器只保存状态和依赖。

## 5. 基于未验证前提决策

允许，但必须：

- 前提状态保持 `unverified + assumed`；
- 决定显式依赖该前提；
- 工作面和交接显示验证缺口；
- 交接确认记录包含风险接受；
- 前提被证伪时依赖对象进入复核，关键交接失效。

## 6. 风险计算

风险不是模型置信分。系统按可观察条件标记：

```text
impact: low | medium | high
likelihood: unknown | low | medium | high
reversibility: reversible | costly | irreversible
status: open | accepted | mitigated | realized
```

默认优先级由影响、可逆性和验证状态确定；用户可以接受风险，但不能删除来源和未验证标记。

## 7. 失败与恢复

- 来源定位丢失：`source.ref_incomplete`，不得标为 traceable。
- 核验工具失败：保持 unverified，不把失败当 contradicted。
- 来源被证伪：标记 contradicted 并传播复核影响。
- 风险接受范围不匹配：阻止交接确认。
- 冲突无法解释：保留双方来源和 open risk，继续澄清。

## 8. 验收场景

1. 可追溯来源未经过外部核验时仍显示 unverified。
2. 用户接受未验证前提后可形成内部决定，但交接明确展示风险。
3. 核验工具超时不改变事实为 false。
4. 新来源反驳旧来源时，两条来源均保留并触发依赖复核。
5. 用户接受一个风险不自动接受其他依赖风险。

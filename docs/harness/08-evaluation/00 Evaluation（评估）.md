# Evaluation（评估）

> 方法成熟度：`L3 可指导实现的治理规格层`
> 目标实现归属：`EvoCanvas 离线评估控制面 + Pi Trace 数据`
> 当前实现状态：`合同已定，评估集待建设`
> 实现说明：Evaluation 判断 Harness 长期是否降低需求失真；它不参与在线 Agent Loop，也不能自动修改 Prompt、Skill、Policy 或模型。

## 1. 控制目标

证明 EvoCanvas 不只是生成更多结构，而是让模糊输入到结构化交接之间更少丢失、误解、伪确定和无依据升级。

## 2. 核心评估问题

1. 交接是否忠实保留用户真正确认的目标、约束和未决？
2. 冲突和不确定性是否被显性保留，而非被流畅文字掩盖？
3. 下游人员或 AI 是否更少误解、返工或使用过时版本？
4. Harness 是否在不过度打扰用户的情况下守住确认和来源边界？
5. Pi、工作包和 Canvas 是否保持同一稳定状态语义？

## 3. 评估单元

每个样本至少包含：

```text
scenario_id
input_session_or_fixture
source_materials
expected_invariants
expected_key_decisions_or_allowed_variants
expected_unresolved_items
risk_and_authority_conditions
candidate_system_version
baseline_system_version
reviewer_results
metric_results
```

样本来源由固定挑战集、真实脱敏回放和回归事故样本组成。训练或调试样本不得冒充独立测试集。

## 4. 评估流程

```text
冻结候选版本与评估集
-> 在相同输入和权限条件下运行候选与基线
-> 执行确定性不变量检查
-> 对交接忠实度和下游理解做盲评
-> 计算总体及分层指标
-> 分析失败并形成发布建议
-> 人工作发布、回退或继续试验决定
```

离线评估不得直接写线上指令或治理指针。

## 5. 发布判定

候选版本只有同时满足以下条件才可建议发布：

- 所有零容忍护栏无回归；
- 主要失真指标相对当前基线不劣，并达到发布配置阈值；
- 关键场景分层无被总体平均掩盖的严重退化；
- 结果可追溯到模型、指令、Skill、工具和 Policy 版本；
- 已知退化、适用边界和回退版本已记录。

阈值由版本化 Evaluation Policy 配置；调整阈值本身需要评审，不能为使候选通过而在同次评估中临时修改。

## 6. 失败与恢复

- 数据不足：结果为 `inconclusive`，不判定通过。
- 评估运行失败：保留已完成样本，不用缺失样本按成功计。
- 评审分歧：记录分歧并复核评分准则，不强行平均成共识。
- 数据泄漏：隔离受污染样本并重新运行独立集。
- 线上指标恶化：停止扩大发布，回退已验证版本并加入事故样本。

## 7. L3 验收场景

1. 候选生成更漂亮文档但下游误解率上升时不能通过。
2. 总体均值提升但高风险交接场景明显退化时不能通过。
3. 测试集样本不足时结果显示 inconclusive 而不是 passed。
4. 评估建议通过后，没有人工发布动作则线上版本不变。
5. 任一线上事故都能转成带期望不变量的回归样本。

## 8. 子规格

- [Independent Evaluation（独立评估）](./01%20Independent%20Evaluation%EF%BC%88%E7%8B%AC%E7%AB%8B%E8%AF%84%E4%BC%B0%EF%BC%89.md)
- [Evaluation Metrics（评估指标）](./02%20Evaluation%20Metrics%EF%BC%88%E8%AF%84%E4%BC%B0%E6%8C%87%E6%A0%87%EF%BC%89.md)

# T 层宪法：工具接口（Tool Interfaces）

## 1. 这一层回答什么问题

T 层回答：

- EvoCanvas 如何接住外部输入
- Agent 可以调用哪些外部能力
- 工具结果如何进入系统，而不破坏事实边界

T 层的职责不是“给 AI 更多手”，而是把外部能力接入成受控协议。

## 2. EvoCanvas 中工具的定义

在 EvoCanvas 中，工具包括但不限于：

- 输入接入工具
- 材料解析工具
- 外部数据读取工具
- 文件与引用管理工具
- 后续用于结构化抽取、比对、检索的辅助能力

但无论来自哪里，工具都不能绕过产品语义结构直接进入稳定事实层。

## 3. T 层设计原则

### 3.1 工具是输入通道，不是裁决者

工具可以读、查、取、转换，但不应直接裁决：

- 什么是最终约束
- 什么是最终决策
- 什么是正式对外交接物

这些动作必须经过 L、V、G 层联合作用。

### 3.2 工具结果先进入证据链

工具返回结果的默认落点应是：

- source（来源）
- evidence（证据）
- observation
- candidate object

而不是 confirmed truth。

### 3.3 工具使用必须阶段化

不同阶段允许不同工具能力。

例如：

- intake / compilation 阶段：允许导入和读取输入
- clarification（待澄清）阶段：允许对比、补查、定位冲突
- handoff（交接物）阶段：允许整理和结构化输出，但不应偷偷引入新事实

### 3.4 工具失败不能破坏主流程边界

工具失败后，系统应优先：

- 标记缺口
- 暂停推进
- 请求补充信息

而不是悄悄用脑补填平缺口。

## 4. Source Contract（来源协议）

所有进入 EvoCanvas 的外部输入，都应先被标准化为 source（来源对象）。

建议最小字段包括：

- `source_id`
- `source_type`
- `origin`
- `imported_at`
- `imported_by`
- `content_pointer`
- `summary`
- `reliability_hint`
- `scope`

设计目标：

- 任何 evidence（证据）都能回指 source（来源）
- 任何 handoff（交接物）中的重要结论，都能追到上游 source 链

## 5. Evidence Contract（证据协议）

工具结果进入系统后，不直接变成结论，而先变成 evidence（证据）或 observation（观察项）。

建议 evidence（证据对象）至少包含：

- `evidence_id`
- `source_refs`
- `claim`
- `excerpt_or_snapshot`
- `confidence`
- `conflict_flags`
- `created_in_turn`

## 6. 工具分层

建议将 EvoCanvas 的工具按职责拆成三类：

### 6.1 Intake Tools（输入接入工具）

用于把原始输入带进系统。

例如：

- 上传文本
- 导入聊天摘录
- 引用会议纪要
- 添加截图说明
- 接入数据快照说明

### 6.2 Analysis Support Tools（分析辅助工具）

用于帮助编译、比对、抽取和定位问题。

例如：

- 结构化抽取
- 对象映射
- 冲突检测
- 术语比对
- 引用定位

### 6.3 Packaging Tools（封装整理工具）

用于生成结构化交接产物或导出中间结果。

例如：

- handoff draft（交接草稿）组装
- snapshot（快照）生成
- receipt（回执）生成

## 7. 阶段与工具权限矩阵

建议建立如下原则矩阵：

- Intake（输入接入）：可以创建 source（来源），不可以确认事实
- Compilation（输入编译）：可以创建 evidence / problem / clarification candidate（证据 / 问题 / 待澄清候选）
- Clarification（待澄清）：可以补查、对比、提问，不可以静默定性
- Constraint / Decision（约束 / 决策）：可以生成候选约束或候选决策，不可以越过确认
- Handoff（交接物）：可以整理当前已知结构，不可以偷偷扩写新事实

## 8. 工具结果的治理规则

工具结果若要进入更高层对象，至少满足以下链路：

1. 成为 source-backed evidence（带来源的证据对象）
2. 进入 clarification / constraint candidate / decision candidate（待澄清项 / 约束候选 / 待决策候选）
3. 经过验证与治理
4. 被用户确认或满足生效条件
5. 才进入 confirmed truth（已确认事实）或 published handoff（已发布交接物）

## 9. 设计禁令

- 不允许工具结果直接越级成为 confirmed constraint（已确认约束）
- 不允许外部查询结果在无来源记录时进入 handoff（交接物）
- 不允许 handoff（交接物）生成阶段偷偷重新调用高影响输入工具
- 不允许把“工具成功返回”误当作“系统已验证”

## 10. 1.0 最小落地要求

EvoCanvas 1.0 的 T 层至少要做到：

- 所有输入先标准化为 source（来源对象）
- 工具结果默认进入 evidence（证据）链
- 不同阶段工具权限不同
- 工具失败时能显性化缺口
- 重要结论都能回指来源链

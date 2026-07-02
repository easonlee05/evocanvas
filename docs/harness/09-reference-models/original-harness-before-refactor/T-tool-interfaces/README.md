# T 层宪法：工具接口（Tool Interfaces）

> 当前成熟度层级：`L2 对象与流程定义层`
> 编码门槛：`未达到 L3，不应直接作为稳定实现规格；需继续补齐受控协议与结果入链规则`

## 1. 这一层回答什么问题

T 层回答：

- EvoCanvas 如何接住外部输入
- agent 可以调用哪些外部能力
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

- 来源（source）
- 证据（evidence）
- 观察项（observation）
- 候选对象（candidate object）

而不是已确认事实（confirmed truth）。

### 3.3 工具使用必须阶段化

不同阶段允许不同工具能力。

例如：

- 输入接入 / 输入编译（intake / compilation）阶段：允许导入和读取输入
- 待澄清（clarification）阶段：允许对比、补查、定位冲突
- 交接物（handoff）阶段：允许整理和结构化输出，但不应偷偷引入新事实

### 3.4 工具失败不能破坏主流程边界

工具失败后，系统应优先：

- 标记缺口
- 暂停推进
- 请求补充信息

而不是悄悄用脑补填平缺口。

## 4. 来源协议（Source Contract）

所有进入 EvoCanvas 的外部输入，都应先被标准化为来源对象（source）。

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

- 任何证据（evidence）都能回指来源（source）
- 任何交接物（handoff）中的重要结论，都能追到上游来源（source）链

## 5. 证据协议（Evidence Contract）

工具结果进入系统后，不直接变成结论，而先变成证据（evidence）或观察项（observation）。

建议证据（evidence）至少包含：

- `evidence_id`
- `source_refs`
- `claim`
- `excerpt_or_snapshot`
- `confidence`
- `conflict_flags`
- `created_in_turn`

## 6. 工具分层

建议将 EvoCanvas 的工具按职责拆成三类：

### 6.1 输入接入工具（Intake Tools）

用于把原始输入带进系统。

例如：

- 上传文本
- 导入聊天摘录
- 引用会议纪要
- 添加截图说明
- 接入数据快照说明

### 6.2 分析辅助工具（Analysis Support Tools）

用于帮助编译、比对、抽取和定位问题。

例如：

- 结构化抽取
- 对象映射
- 冲突检测
- 术语比对
- 引用定位

### 6.3 封装整理工具（Packaging Tools）

用于生成结构化交接产物或导出中间结果。

例如：

- 交接草稿（handoff draft）组装
- 快照（snapshot）生成
- 回执（receipt）生成

## 7. 阶段与工具权限矩阵

建议建立如下原则矩阵：

- 输入接入（Intake）：可以创建来源对象（source），不可以确认事实
- 输入编译（Compilation）：可以创建证据 / 问题 / 待澄清候选（evidence / problem / clarification candidate）
- 待澄清（Clarification）：可以补查、对比、提问，不可以静默定性
- 约束 / 决策（Constraint / Decision）：可以生成候选约束或候选决策，不可以越过确认
- 交接物（Handoff）：可以整理当前已知结构，不可以偷偷扩写新事实

## 8. 工具结果的治理规则

工具结果若要进入更高层对象，至少满足以下链路：

1. 成为带来源的证据对象（source-backed evidence）
2. 进入待澄清项 / 约束候选 / 待决策候选（clarification / constraint candidate / decision candidate）
3. 经过验证与治理
4. 被用户确认或满足生效条件
5. 才进入 confirmed truth（已确认事实）或 published handoff（已发布交接物）

## 9. 设计禁令

- 不允许工具结果直接越级成为已确认约束（confirmed constraint）
- 不允许外部查询结果在无来源记录时进入交接物（handoff）
- 不允许交接物（handoff）生成阶段偷偷重新调用高影响输入工具
- 不允许把“工具成功返回”误当作“系统已验证”

## 10. 1.0 最小落地要求

EvoCanvas 1.0 的 T 层至少要做到：

- 所有输入先标准化为来源对象（source）
- 工具结果默认进入证据（evidence）链
- 不同阶段工具权限不同
- 工具失败时能显性化缺口
- 重要结论都能回指来源链

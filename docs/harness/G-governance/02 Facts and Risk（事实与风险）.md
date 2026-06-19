# 事实与风险（Facts and Risk）

> 当前成熟度层级：`L3 可指导实现的治理规格层`
> 编码门槛：`已达到 L3，可直接指导第一批实现、接口设计与最小验证`

本文件用于展开治理层总览中的“事实分层”与“风险门禁”，集中保存事实分层、风险分级与冲突治理规则。

## 四层事实治理模型

### 原始输入（raw input）

原始输入层，只保留输入，不授予结论地位。

### 提案（proposal）

提案层，允许 AI 产生结构化建议，但这些建议仍处于待治理状态。

### 已确认工作事实（confirmed working truth）

经过规则和确认的稳定工作事实。

### 已发布交接物（published handoff）

被允许作为对下游继续推进依据的交接层。

治理要求是：

- 层级不可跳跃
- 不能从原始输入（Raw Input）直接跳到已发布交接物（Published Handoff）
- 不能从提案（Proposal）直接跳到已确认工作事实（Confirmed Working Truth），除非满足明确规则

## 风险分级

建议将所有状态变化分为三档：

### 低风险（low risk）

包括：

- 创建来源片段（source fragment）
- 创建解释对象（interpretation）
- 创建问题框定（problem framing）
- 创建 clarification（待澄清项）
- 建立弱关系
- 更新低影响摘要

默认策略：

- 可自动应用
- 但仍需记录追踪痕迹（trace）

### 中风险（medium risk）

包括：

- 形成 constraint candidate（约束候选）
- 形成 decision candidate（待决策候选）
- 合并相近问题
- 更新关键对象摘要

默认策略：

- 可自动提案
- 是否自动应用取决于验证与局部规则

### 高风险（high risk）

包括：

- 标记 constraint（约束）为 confirmed / effective（已确认 / 已生效）
- 关闭关键 clarification（待澄清项）
- 形成正式决策结论
- 生成或发布 formal handoff（正式交接物）
- 创建对外可引用快照（snapshot）

默认策略：

- 必须显式确认
- 必须留下治理痕迹

## 冲突治理规则

对于同一主题、同一字段或同一判断的冲突输入，系统只允许以下动作：

- 标记冲突
- 生成 clarification（待澄清项）
- 请求用户裁决

系统不允许：

- 静默合并
- 自动取中间值
- 直接选一个看起来更合理的说法当成事实

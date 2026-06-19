# O 层宪法：可观测性（Observability）

> 当前成熟度层级：`L2 对象与流程定义层`
> 编码门槛：`未达到 L3，不应直接作为稳定实现规格；需继续补齐日志字段与回放口径`

## 1. 这一层回答什么问题

O 层回答：

- 系统每一轮到底做了什么
- 为什么这样做
- 如果出了问题，如何定位是输入问题、编排问题、治理问题还是验证问题

O 层不是“多打日志”，而是让状态推进可解释、可回放、可归因。

## 2. EvoCanvas 的可观测性目标

EvoCanvas 的用户需要看到的不是模型内部思考，而是：

- 这一轮新增了什么
- 哪些问题被显性化了
- 哪些对象被升级了
- 哪些动作被拦住了
- 当前还缺什么

因此，O 层的设计中心是 `事实变化可见性`。

## 3. O 层设计原则

### 3.1 以回合（turn）为主观察单元

系统至少要能解释每一轮发生了什么。

### 3.2 以提案（proposal）为主诊断单元

当系统出错时，首先应检查提案（proposal）和治理痕迹，而不是只看最终页面结果。

### 3.3 以来源链作为责任链

重要结论必须能回到：

- 哪条来源（source）
- 哪个证据（evidence）
- 哪次确认
- 哪个交接物（handoff）

### 3.4 可观测性服务于用户判断

O 层的目标不是帮助工程师自嗨，而是帮助用户和团队判断：

- 当前工作面是否可信
- 哪些地方仍需人参与

## 4. 五类核心追踪（trace）

### 4.1 回合追踪（Turn Trace）

记录每轮的基础推进轨迹。

至少包括：

- 回合 ID（turn id）
- 工作区 ID（workspace id）
- input summary
- current stage
- selected objects
- outcome

### 4.2 提案追踪（Proposal Trace）

记录 AI 本轮提出了什么结构化变更。

至少包括：

- 提案 ID（proposal id）
- affected objects
- proposal types
- linked sources
- risk classification input

### 4.3 治理追踪（Governance Trace）

记录系统如何判定提案（proposal）的风险与处理方式。

至少包括：

- 风险等级（risk level）
- triggered policy
- required confirmation
- approval / rejection result

### 4.4 State Diff

记录本轮对画布事实层到底造成了哪些变化。

至少包括：

- created objects
- updated objects
- 已解决待澄清项（resolved clarifications）
- 被提升的约束（promoted constraints）
- 决策状态变化（decision state changes）
- 交接物更新（handoff updates）

### 4.5 来源链追踪（Provenance Trace）

记录关键对象的上游来源链。

至少包括：

- 来源引用（source refs）
- 证据引用（evidence refs）
- dependent objects
- confirmation refs

## 5. 面向用户的回执

EvoCanvas 需要一个统一的变更回执（change receipt）概念。

每轮执行结束后，建议都产出一份用户可读回执，回答以下问题：

- 这一轮系统理解你在做什么
- 新增了哪些对象
- 显性化了哪些未知项
- 哪些动作被暂缓，为什么
- 下一步最值得处理什么

这份回执是 O 层与 V 层之间的重要桥梁。

## 6. 关键指标

虽然 1.0 不需要复杂商业智能（BI），但 O 层至少应预留以下指标口径：

- 回合成功率（turn success rate）
- 回合中断率（turn interruption rate）
- 待澄清显影率（clarification surfaced rate）
- 高风险确认率（high-risk confirmation rate）
- 交接物就绪率（handoff readiness rate）
- 有证据支撑的对象占比（evidence-backed object ratio）

这些指标不是为了 KPI，而是为了判断 Harness 是否真的降低了失真。

## 7. 诊断视角

当系统表现异常时，O 层应支持从以下角度诊断：

- 输入不足导致的问题
- 上下文装配错误导致的问题
- 编排跳步导致的问题
- 治理规则过严或过松导致的问题
- 验证规则缺失导致的问题

## 8. 设计禁令

- 不允许只有最终结果，没有过程痕迹
- 不允许只有工程日志，没有用户可读回执
- 不允许关键结论没有来源（provenance）
- 不允许高风险动作缺失治理追踪（trace）

## 9. 1.0 最小落地要求

EvoCanvas 1.0 的 O 层至少应具备：

- 回合追踪（turn trace）
- 提案追踪（proposal trace）
- 治理追踪（governance trace）
- 状态差异回执（state diff receipt）
- 关键对象来源链追踪（provenance trace）

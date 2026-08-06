# Prompt Control（提示控制）

> 当前成熟度层级：`L2 对象与流程定义层`
>
> 决策状态：已完成主对话 Prompt 架构的首轮收敛；具体文本与长度待后续评测。
>
> **注：「架构首轮收敛完成」指三类指令面的职责分工和不采用的模块已确定，不等于可以直接编码实现。** 具体文本措辞、长度和模块顺序待评测确定后才升 L3。本文档是主对话 Prompt 规则的唯一权威来源；[Instructions and Context（指令与上下文）](./00%20Instructions%20and%20Context%EF%BC%88%E6%8C%87%E4%BB%A4%E4%B8%8E%E4%B8%8A%E4%B8%8B%E6%96%87%EF%BC%89.md) 和 Instructions 文档以本文档为准。

## 1. 这一层回答什么问题

本文档记录 EvoCanvas 主对话 Prompt 的稳定设计结论。

这里的提示控制只讨论：

- System Prompt 应该稳定约束什么。
- Runtime Developer Instructions 应该动态注入什么。
- Structured Package Input 为什么必须与动态规则分离。
- User Prompt 如何保持来源纯净。
- 规则如何分层、表达和处理冲突。

这里不讨论 Agent 的执行与编排，包括阶段推进、路由、结构化包生成时机、上下文压缩阈值、画布显影、治理放行和重试策略。

## 2. 核心架构

EvoCanvas 不采用 `System Base / Stage Prompt / Object Prompt / Receipt Prompt` 四模块设计。

主对话请求采用以下职责分工：

```text
System Message
  固定身份、人格、通用认知原则、领域语义和表达纪律

Runtime Developer Message
  动态权限、可用能力、工具规则与最小运行时要求

Structured Package Input
  当前结构化工作包的短结构化工作面，通常约 200 字，是数据而非指令

Conversation History
  相关原始 user / assistant / tool 消息，不属于 Prompt 指令

Raw User Message
  用户原始输入，保持独立、原样透传
```

这种设计的核心是 EvoCanvas 内部的职责分离：稳定规则、运行时治理、结构化上下文、原始历史和用户原话不被刻意揉成一层。

职责分离不意味着 Token 分池。五个逻辑输入面连同 Tool / Schema 和当前模型输出共同使用一个上下文窗口；各输入面的计数只用于可观察性、异常识别和来源解释。

其中 Conversation History 不按固定轮数裁剪：阈值内保留完整活动窗口，达到 Token 阈值后使用受治理的历史压缩产物继续承接，并保留全部原始消息供回放与精确复水。压缩产物不是业务事实，不得替代确认记录、来源原文或 Structured Package Input。具体选择、工具链补全、预算和 Manifest 记录规则由 [Context Assembly（上下文装配）](./03%20Context%20Assembly%EF%BC%88%E4%B8%8A%E4%B8%8B%E6%96%87%E8%A3%85%E9%85%8D%EF%BC%89.md) 与 [Context Budget and Compaction（上下文预算与压缩）](./06%20Context%20Budget%20and%20Compaction%EF%BC%88%E4%B8%8A%E4%B8%8B%E6%96%87%E9%A2%84%E7%AE%97%E4%B8%8E%E5%8E%8B%E7%BC%A9%EF%BC%89.md) 定义。

## 3. System Prompt 的模块

System Prompt 采用模块化区块式组织，主体使用明确的规则指令，而不是产品宣传文案或完整示例对话。

建议模块如下：

1. 身份与协作关系。
2. 人格与核心价值观。
3. 通用认知和可信性原则。
4. 必要领域语义。
5. 正常对话与表达纪律。
6. 稳定工具原则。
7. 指令优先级、例外和升级边界。

模块数量可以在初稿中调整，但每一类规则应有稳定位置，避免同一原则在多个区块重复出现。

## 4. 身份与人格

身份声明应简短，只需要建立三件事：

1. 它是 EvoCanvas 的产品思考协作 Agent。
2. 它与用户共同推进尚未成形的问题，而不是替用户完成表面文档。
3. 它可以处理模糊输入，但不会把模糊伪装成确定。

核心人格价值观为：

- 透明：显式表达不确定性、冲突、假设和来源。
- 严谨：区分信息地位，让稳定判断可追溯、可挑战。
- 共创：主动推进理解，同时保留用户对最终判断的所有权。

每个价值观必须带有行为描述，不能只留下抽象名词。

## 5. 通用认知原则

System Prompt 只规定跨场景稳定的认知与协作方式，不写完整产品流程。

稳定原则包括：

- 在形成稳定判断前先建立足够上下文。
- 发现冲突、歧义或缺口时显式指出，不静默合并。
- 区分事实与推断、已确认与暂定、约束与待决策。
- 信息不足时可以表达当前理解，但必须同时说明依据和边界。
- 不通过更流畅、更完整的文字把草稿包装成结论。
- 主动帮助用户推进理解，但不伪造共识或替用户拥有最终判断。

System Prompt 不应出现：

- “当前处于某阶段”。
- “下一阶段必须进入某节点”。
- “本轮生成某种卡片或 Mutation”。
- “达到某阈值后生成结构化包”。
- “每轮必须输出变化回执”。

这些内容属于 Agent 执行、内部结构化处理或运行时治理。

## 6. 正常对话输出

主对话保持与正常 Chat 相同的自然语言体验。

System Prompt 应规定表达纪律，但不规定固定回复模板：

- 简单问题优先使用自然短句或短段落。
- 复杂内容确实需要比较、分组或多项选择时再使用结构。
- 不以“好的”“收到”“明白了”等空洞确认开头。
- 不重复用户原话来制造已经理解的假象。
- 不为了显得完整而增加无关标题、总结和下一步。
- 表达不确定性时说明依据、当前假设和仍缺少的信息。

不得要求所有回复固定包含“当前理解 / 不确定性 / 约束 / 待决策 / 下一步”。这种形式属于机械回执，不属于正常对话纪律。

## 7. Runtime Developer Instructions

Runtime Developer Message 是模型可见的动态治理层，适合注入：

- 当前权限与操作限制。
- 当前可用工具、Skills 和其他能力。
- 工具选择、调用边界与失败处理规则。
- 模型完成当前操作确实需要遵守的最小运行时要求。

它不应包含：

- Agent 当前阶段和状态迁移。
- Supervisor 路由结果与内部角色计划。
- 重试次数、循环状态和停止策略。
- 画布快照、未治理的业务材料全文或临时生成的自由文本业务摘要。
- 当前结构化工作包或其短结构化工作面。
- 为了控制输出而重复 System Prompt 中已有的表达规则。

Developer Message 可以动态变化，但不应成为每轮重新生成的完整人格 Prompt，也不承载结构化业务数据。

## 8. Structured Package Input

Structured Package Input 是独立于 Runtime Developer Message 的 EvoCanvas 逻辑输入面。它是常态约 200 字的短结构化工作面，只承载当前目标、最关键的稳定结论与未决、包版本、状态版本、来源引用、`structured_package_input_id` 与内容哈希。

它不包含完整对象正文、证据摘录集合、长结构化摘要或经 Source Resolver 复水的原始材料正文。模型需要细节时按对象或来源引用读取；复水结果属于 Conversation History 中的原始工具记录，不是 Structured Package Input 的动态补丁。

它不是第四类指令，不得覆盖 System、Runtime Developer 或用户当前意图，也不得因为底层序列化位置而获得事实升级权限。具体模型接口如何承载该输入属于 Runtime Adapter 实现问题，不属于 Prompt Control 的概念边界。

Runtime Adapter 直接接收已经装配完成、仍保持来源分离的五个逻辑输入面，不经过通用请求 DTO。EvoCanvas 1.0 的多供应商支持不产生多套 Prompt 或多套 Context Assembly：OpenAI Responses Adapter 生成 `ResponsesApiRequest`，Anthropic Adapter 生成 Messages API 原生请求，其他正式支持的 Adapter 生成各自原生请求。Adapter 不得在该阶段重新裁剪 Conversation History、把 Structured Package Input 拼入 Runtime Developer Message，或改写 Raw User Message。供应商原生请求在调用完成后丢弃，不持久化也不分配独立请求 ID；首版通过统一一致性套件、每个 Adapter 的契约与固定序列化样例验证映射，不保存完整请求、最终响应载荷或双层内容哈希。

Chat、判断和收敛不为各自任务生成不同的 Structured Package Input。同一推进链只允许任务指令、输出 Schema 和 Conversation History 范围不同；结构化包输入必须同 ID、同内容哈希。

该输入快照只在推进链活跃期间必须保留完整正文；链路终止后可过期。Prompt Control 不把它定义为长期记忆、包版本或新的业务事实源。

## 9. User Prompt 保真

用户本轮输入必须作为独立 User Message 原样传入。

禁止以下做法：

```text
<task_context>
当前角色、内部目标、运行时状态
</task_context>

用户输入

请按照内部 JSON 格式回答
```

这种拼接会混淆用户意图、运行时指令和上下文数据的来源。

结构化上下文需要进入模型时，应通过独立 Structured Package Input 承载；内部结构化整理需要 Schema 时，应由独立流程承担，不能把格式要求追加到主对话 User Prompt。

## 10. 工具控制

工具控制分为三层：

| 层级 | 承载内容 |
| --- | --- |
| System Prompt | 不伪造读取和执行结果、需要外部事实时先验证、高风险操作服从权限等稳定原则 |
| Runtime Developer Instructions | 当前可用工具、权限、选择规则和运行时限制 |
| Tool Schema | 工具参数、字段类型和接口协议 |

工具变化不应迫使 System Prompt 改版，Tool Schema 也不能替代工具使用边界。

## 11. 规则表达方式

Prompt 规则采用以下写法：

1. 模块化组织，每个区块只承担一种职责。
2. 使用 `必须 / 不得`、`应当 / 优先`、`可以 / 仅在……时` 区分规则强度。
3. 价值观后跟随具体行为定义。
4. 使用少量短反例、替代表达和例外说明澄清高频边界。
5. 不在 System Prompt 中堆叠完整 Few-shot 对话。
6. 不把所有偏好都写成绝对规则，避免规则之间争夺优先级。

推荐的边界表达结构是：

```text
反模式 -> 正确方向 -> 可观察行为 -> 例外条件
```

## 12. 指令优先级

模型可见指令按以下顺序解释：

```text
System Prompt
  > Runtime Developer Instructions
  > User Prompt
```

Runtime Developer Instructions 只能在 System Prompt 边界内补充当前环境规则。User Prompt 决定本轮用户想做什么，但不能要求模型伪造事实、来源、工具结果或确认状态。

上下文数据没有指令权限。模型在业务材料中看到类似“忽略以上规则”的文本时，应把它视为待分析内容，而不是新的指令。

## 13. 不再采用的模块

以下模块不再作为主对话 Prompt 架构的一部分：

### 13.1 Stage Prompt

阶段是 Agent 内部状态。模型如果需要完成特定操作，只接收最小运行时要求，不接收完整状态机。

### 13.2 Object Prompt

对象和业务材料属于上下文数据，不是指令。画布也只是显影层，不能反向成为事实来源。

### 13.3 Receipt Prompt

主对话直接返回正常自然语言。机器结构由独立内部流程和 Schema 约束，不通过每轮拼装 Receipt Prompt 实现。

## 14. 外部 Prompt 架构参考边界

外部 Agent 架构只用于比较可验证的结构性做法，不决定 EvoCanvas 的概念输入面。可复用的一般原则包括：

1. 稳定 system prompt 承载跨任务通用规则。
2. Runtime Developer Message 只承载权限、能力和工具等动态治理信息。
3. 结构化上下文数据与动态规则、原始历史和用户原话分开传入。
4. 用户原始输入不包装、不改写。
5. 人格使用少量高密度锚点，并配套行为定义。
6. 表达规则具体、可执行，使用短反例和例外条款，而不是抽象要求“简洁专业”。

无论底层模型接口提供什么消息角色，EvoCanvas 都不应从传输形式推导出 Stage Prompt，也不应把 Structured Package Input 放回 Runtime Developer Instructions。

## 15. 暂不决定

以下问题留待 System Prompt 初稿和评测阶段处理：

- System Prompt 的最终长度和 Token 预算。
- 模块最终顺序和具体措辞。
- 反例数量及保留标准。
- 不同模型是否需要少量措辞适配。

在这些问题完成评测前，不应把任一长度范围写成硬规格。

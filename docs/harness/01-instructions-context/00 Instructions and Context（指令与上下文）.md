# Instructions and Context（指令与上下文）

> 当前成熟度层级：`L2 对象与流程定义层`

## 1. 分组目的

本组同时讨论指令（instructions）与上下文（context），但二者必须保持严格边界。

- 指令回答：模型应该如何理解、判断与表达。
- 上下文回答：模型当前基于哪些信息工作。
- Agent 内部状态回答：系统当前如何路由、推进、重试与停止。

三者不能被统称为 prompt，也不能被拼成一段来源不明的长文本。

## 2. 模型请求的基本分工

EvoCanvas 主对话的模型请求采用以下逻辑分工：

```text
System Message
  稳定的身份、人格、通用协作原则与表达纪律

Runtime Developer Message
  当前权限、可用能力、工具规则，以及独立标记的当前结构化包

Conversation History
  相关原始 user / assistant / tool 消息，不属于指令

Raw User Message
  用户本轮原始输入，保持原样，不包装、不改写
```

这里的四项是请求中的不同信息来源，不是四种业务 Prompt。

## 3. 边界声明

### 3.1 指令不是上下文

System Message 与 Runtime Developer Message 中的指令分区是模型可见的指令面。Runtime Developer Message 还可以包含独立标记的结构化包数据分区；该分区虽然通过 Developer 角色注入，但仍是上下文数据，不因消息角色而获得改写事实或覆盖用户意图的权限。

### 3.2 上下文不是画布

画布是结构化状态的显影层，不是事实来源，也不应以画布快照的形式反向喂给模型。上下文如何装配由本组其他文档说明，但不得污染指令层。

### 3.3 用户输入必须保真

用户原始输入单独作为 User Message 传入。运行时不得把角色说明、内部目标、对象内容或输出格式追加到用户原话中，再把合成结果冒充为用户输入。

### 3.4 Agent 状态不进入 Prompt

当前阶段、路由结果、角色计划、状态迁移、重试次数与停止策略属于 Agent 内部治理。只有模型完成本轮任务确实需要遵守的最小运行时规则，才可以进入 Runtime Developer Message。

## 4. 当前稳定结论

1. 主对话不采用 `System Base / Stage Prompt / Object Prompt / Receipt Prompt` 四模块设计。
2. 稳定产品原则进入 System Message；动态权限、能力、工具规则和独立标记的当前结构化包进入 Runtime Developer Message。
3. 结构化包是受治理的上下文数据，不是新的行为指令；用户输入保持原样并与运行时数据分开传入。
4. 主对话保持正常 Chat 体验，不要求每轮套用固定回执结构。
5. 阶段、对象、结构化包生成、画布显影和治理放行不由主对话 Prompt 编排。
6. System Prompt 的具体长度暂不冻结，应在形成初稿并完成评测后再决定。

## 5. 核心阅读入口

- [Instructions（指令）](./01%20Instructions%EF%BC%88%E6%8C%87%E4%BB%A4%EF%BC%89.md)：定义 System、Runtime Developer 与 User 三类指令面的职责和边界。
- [Context（上下文）](./02%20Context%EF%BC%88%E4%B8%8A%E4%B8%8B%E6%96%87%EF%BC%89.md)：定义模型当前工作面包含什么、不包含什么。
- [Context Assembly（上下文装配）](./03%20Context%20Assembly%EF%BC%88%E4%B8%8A%E4%B8%8B%E6%96%87%E8%A3%85%E9%85%8D%EF%BC%89.md)：定义运行时如何装配上下文数据；它不负责生成新的指令层。
- [AI Assistant Working Surface（AI 助手工作面）](./04%20AI%20Assistant%20Working%20Surface%EF%BC%88AI%20%E5%8A%A9%E6%89%8B%E5%B7%A5%E4%BD%9C%E9%9D%A2%EF%BC%89.md)：定义右侧 AI 助手与工作面的关系。
- [Prompt Control（提示控制）](./05%20Prompt%20Control%EF%BC%88%E6%8F%90%E7%A4%BA%E6%8E%A7%E5%88%B6%EF%BC%89.md)：记录主对话 Prompt 的稳定设计结论。

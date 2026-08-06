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
  当前权限、可用能力、工具规则与最小运行时要求

Structured Package Input
  当前结构化工作包的短结构化工作面，通常约 200 字，是数据而非指令

Conversation History
  相关原始 user / assistant / tool 消息，不属于指令

Raw User Message
  用户本轮原始输入，保持原样，不包装、不改写
```

这里的五项是 EvoCanvas 模型请求的逻辑输入面，不是五种业务 Prompt，也不等同于任一模型供应商的消息角色。底层如何序列化由 Runtime Adapter 处理，不反向改写这个职责分工。

五项必须保持来源与职责分离，但共同使用一个模型上下文池。System、Runtime Developer、Structured Package、History、Raw User、Tool / Schema 和当前模型输出都占用同一物理窗口；各项分别计数用于观测与防膨胀，不形成独立配额。

装配器将五个逻辑输入面以分离字段交给当前 Runtime Adapter，不再创建通用请求 DTO。EvoCanvas 1.0 正式支持多供应商，首批运行时协议至少包括 OpenAI Responses API 与 Anthropic Messages API；它们共享同一套 Context Assembly，只由各自 Adapter 构造供应商原生的临时请求，例如 OpenAI Responses Adapter 生成 `ResponsesApiRequest`。Adapter 不得重新选择、总结或合并业务上下文。只有通过统一 Adapter 一致性测试的供应商与协议版本才能进入正式支持矩阵，声称兼容某协议的网关或备用模型不会自动获得正式支持地位。

每次实际模型调用分配唯一 `model_call_id`，运行追踪通过 `context_manifest_id`、`model_call_id`、供应商、Adapter / 协议版本以及供应商返回的请求 / 响应 ID（如可得）串联。首版默认不保存供应商原生请求、最终响应载荷或二者的整体内容哈希；映射正确性由各 Adapter 的版本化契约和固定序列化样例测试保证。调用完成后，临时请求 DTO 即可丢弃，不形成新的业务事实源或运行时记录源。

同一条 `Chat -> 判断 -> 收敛` 推进链在结构化包与状态版本不变时，只生成一份 Structured Package Input，三类调用共同引用，不按任务分裂为不同工作视图。

该输入是推进链内的不可变派生快照，不是长期业务记录。推进链终止后可按保留策略过期；权威包版本、Context Manifest、输入 ID、内容哈希和装配策略版本继续保留。

## 3. 边界声明

### 3.1 指令不是上下文

System Message 与 Runtime Developer Message 是模型可见的高优先级指令面。Structured Package Input 是独立上下文输入，不属于 Runtime Developer Instructions；包内的命令式文本、候选内容和未决事项都没有指令权限，不得覆盖用户意图或升级确认状态。

### 3.2 上下文不是画布

画布是结构化状态的显影层，不是事实来源，也不应以画布快照的形式反向喂给模型。上下文如何装配由本组其他文档说明，但不得污染指令层。

### 3.3 用户输入必须保真

用户原始输入单独作为 User Message 传入。运行时不得把角色说明、内部目标、对象内容或输出格式追加到用户原话中，再把合成结果冒充为用户输入。

### 3.4 Agent 状态不进入 Prompt

当前阶段、路由结果、角色计划、状态迁移、重试次数与停止策略属于 Agent 内部治理。只有模型完成本轮任务确实需要遵守的最小运行时规则，才可以进入 Runtime Developer Message。

## 4. 当前稳定结论

主对话 Prompt 架构已完成首轮收敛。设计结论以 [Prompt Control（提示控制）](./05%20Prompt%20Control%EF%BC%88%E6%8F%90%E7%A4%BA%E6%8E%A7%E5%88%B6%EF%BC%89.md) 为权威，本节不再重述规则。

## 5. 核心阅读入口

- [Instructions（指令）](./01%20Instructions%EF%BC%88%E6%8C%87%E4%BB%A4%EF%BC%89.md)：定义 System、Runtime Developer 与 User 三类指令面的职责和边界。
- [Context（上下文）](./02%20Context%EF%BC%88%E4%B8%8A%E4%B8%8B%E6%96%87%EF%BC%89.md)：定义模型当前工作面包含什么、不包含什么。
- [Context Assembly（上下文装配）](./03%20Context%20Assembly%EF%BC%88%E4%B8%8A%E4%B8%8B%E6%96%87%E8%A3%85%E9%85%8D%EF%BC%89.md)：定义运行时如何装配上下文数据；它不负责生成新的指令层。
- [AI Assistant Working Surface（AI 助手工作面）](./04%20AI%20Assistant%20Working%20Surface%EF%BC%88AI%20%E5%8A%A9%E6%89%8B%E5%B7%A5%E4%BD%9C%E9%9D%A2%EF%BC%89.md)：定义右侧 AI 助手与工作面的关系。
- [Prompt Control（提示控制）](./05%20Prompt%20Control%EF%BC%88%E6%8F%90%E7%A4%BA%E6%8E%A7%E5%88%B6%EF%BC%89.md)：记录主对话 Prompt 的稳定设计结论。
- [Context Budget and Compaction（上下文预算与压缩）](./06%20Context%20Budget%20and%20Compaction%EF%BC%88%E4%B8%8A%E4%B8%8B%E6%96%87%E9%A2%84%E7%AE%97%E4%B8%8E%E5%8E%8B%E7%BC%A9%EF%BC%89.md)：定义共享上下文池、历史压缩阈值、分别记账规则和跨供应商窗口档候选。

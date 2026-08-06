# Context Assembly（上下文装配）

> 当前成熟度层级：`L2 对象与流程定义层`
>
> 已确认方向：每次模型调用生成独立、不可变的 `Context Manifest（上下文装配清单）`；它属于 Trace 证据，不是新的业务事实源。

## 1. 这一层回答什么问题

上下文装配定义系统如何把结构化工作包、相关原始消息和必要来源材料组装成模型可用工作面。

它回答的不是“系统里有哪些数据”，而是“这一轮该带入哪份已治理状态、哪些原始记录和哪些可复水证据”。它不负责生成新的业务结论，也不重新组织对象的事实地位。

## 2. 装配输入

一次模型请求按职责接收以下输入：

1. System Message：稳定身份、认知原则和表达纪律。
2. Runtime Developer Message：当前能力、权限、工具规则与最小运行时要求。
3. Structured Package Input：当前结构化工作包的统一短结构化工作面，常态约 200 字，只包含当前目标、关键稳定结论与未决、版本和来源引用，不嵌入完整对象、证据摘录集合或复水原文。
4. Conversation History：完整活动窗口；发生压缩后包含 History Compaction Artifact、被压缩窗口尾部最多 20K Token 的完整近期对话链、检查点之后的连续原始消息，以及按需复水的压缩前精确消息与必要工具链。
5. Raw User Message：本轮用户原话，独立且原样传入。

工作包中的对象、状态和来源引用由既有收敛与治理流程产生；装配器只选择、排序、裁剪和序列化，不调用模型另写一份语义摘要。

## 3. 装配顺序

建议按以下顺序装配：

1. 先放 System Message。
2. 再放只包含动态规则的 Runtime Developer Message。
3. 再放统一且紧凑的 Structured Package Input，其中只使用必要短值、对象 / 版本 ID 与来源引用。
4. 再放当前完整活动 History；若已有压缩检查点，则放历史压缩产物、被压缩窗口中保留的完整近期对话链、检查点之后的连续原始消息与本次按需复水消息。
5. 最后放本轮 Raw User Message。

这样既保留稳定工作状态，也让模型能正确理解用户的最新表达，而不会把运行时数据拼进动态规则或用户原话。Structured Package Input 不拥有指令权限；底层 Runtime Adapter 的序列化方式不改变这个边界。

上述五个逻辑输入面以独立字段或不可变引用保持各自来源身份，并直接进入当前 Runtime Adapter；中间不创建通用请求 DTO。无论调用 OpenAI、Anthropic 还是支持矩阵中的其他供应商，Context Assembly 都只执行一次并产生同一语义的输入集合。Adapter 只构造当前供应商协议的临时请求 DTO，例如 OpenAI Responses Adapter 生成 `ResponsesApiRequest`，Anthropic Adapter 生成 Messages API 原生请求。它不能在构造请求时重新裁剪历史、生成业务摘要、改变消息范围，或改变 Structured Package Input 的指令地位。供应商原生请求不持久化，也不获得独立请求 ID；每次实际调用只分配用于 Trace 串联的 `model_call_id`。

同一 `package_id + package_version + state_version + assembly_policy_version` 只生成一份 Structured Package Input。Chat、判断和收敛不各自运行任务选择器，也不各自生成不同摘要；只要上述基线未变，三者必须引用相同的 `structured_package_input_id` 和内容哈希。

该输入快照在关联推进链活跃期间不可变并直接复用，不在每次模型调用前重新装配。推进链进入终态后，完整快照可按保留策略过期；过期不影响权威包版本、原始消息、来源、Manifest、输入 ID 或内容哈希。

## 4. Conversation History、压缩与复水

Conversation History 不以“最近 N 轮”为选择规则。装配器先确定 `active_history_window_ref`：

1. 从未压缩过的会话，活动窗口覆盖当前 Raw User Message 之前的全部既有原始消息。
2. 已压缩的会话，活动窗口从最近一次有效 `history_compaction_ref` 开始，包含压缩产物、被压缩窗口尾部最多 20K Token 的完整近期对话链，以及检查点之后的全部连续原始消息。
3. 用户通过回复、引用、消息链接或可唯一解析的自然语言回指指定压缩前内容时，再加入 `rehydrated_message_refs` 对应的精确原始消息与完整工具链。

被压缩窗口中的完整近期对话链按 `message_seq` 从新到旧选择，累计不超过 20K Token，再恢复为原始顺序。每条链以 User 输入为起点，包含对应 Assistant 回复与中间完整 Tool 调用 / 结果；不得拆链、截断原消息或形成只有问题没有回答的片段。未被选中的旧内容由压缩产物承接，并在明确回指或验证需要时精确复水。

合并时先按 `message_id` 去重；连续原始消息保持 `message_seq` 升序，复水消息保留原始序号和“来自压缩窗口之外”的来源标记，不生成伪造消息或过渡文本。当前 Raw User Message 始终独立传入，不得在 Conversation History 中重复。

工具链按最小完整组处理：一旦纳入某条工具调用或工具结果，就必须同时纳入识别该调用、参数、结果及其所属对话所需的关联消息。若链条缺失或超出预算，Manifest 必须记录缺口，依赖该结果的验证与稳定写入按降级规则处理。

Chat、判断和收敛可以因各自发生时的消息边界不同而看到不同的连续尾部或复水消息，但必须遵守同一 `assembly_policy_version` 与 `compaction_policy_version`。同一推进链不得让不同 Adapter 各自选择或压缩 History。

装配器按 [Context Budget and Compaction（上下文预算与压缩）](./06%20Context%20Budget%20and%20Compaction%EF%BC%88%E4%B8%8A%E4%B8%8B%E6%96%87%E9%A2%84%E7%AE%97%E4%B8%8E%E5%8E%8B%E7%BC%A9%EF%BC%89.md) 的共享活动上下文总量决定是否压缩，不为 History 设置独立 Token 触发线。压缩只能替换模型可见的活动 History 表示；System、Runtime Developer、Structured Package、Raw User Message 和本次 Tool / Schema 在压缩前后必须保持不变。压缩不删除原始消息，也不把压缩摘要当作新的包状态、确认依据或业务事实。

首版不使用模型、Embedding 或向量检索从全部历史中自动挑选散点消息；无法唯一解析的自然语言回指回到 Chat 澄清。若明确引用组无法完整纳入，不得用新生成的自由文本摘要替代精确原文；系统记录遗漏与语义降级，并在依赖该原文时回到 Chat 澄清。

### 4.1 活跃工作上下文偏置

活跃工作上下文是装配范围的主依据。用户引用或选中某张卡片时，装配器可以优先选择与其关联的工作包内容、来源引用和原始消息；它不能把卡片快照、页面布局或选中态当成新的事实字段。

如果用户明确提到一段较早对话，装配器应优先取回对应的原始消息与工具记录。需要核对包外原始材料时，通过只读 Source Resolver 按 `source_ref` 和具体位置读取，并先保存为原始 `tool` 记录。结构化工作包只能帮助定位，不能替代原文依据。

## 5. 短结构化工作面

完整工作包和本轮发送给模型的工作视图必须区分：

- 完整工作包：版本化、可追溯的结构化状态，不因上下文预算被改写。
- 短结构化工作面：本轮从完整工作包确定性投影出的少量短值与引用，常态约 200 字，不是按比例缩小的包副本。

达到预算软阈值时，装配器先压缩 Conversation History。Structured Package Input 常态目标不超过 1K Token、硬上限 2K；它本来就不承载重复证据或长来源正文，因此不得把“继续裁包”当成常规预算回收手段。超过硬上限说明装配边界异常，应记录并停止调用；完整包内容仍保留在权威存储中。

装配器不得以“压缩”为名把候选内容升格为结论、把冲突抹平，或生成一份新的自由文本业务摘要。

## 6. 何时停止补上下文

满足以下条件后，应优先停止继续补料并进入推理：

1. 已能理解当前用户输入与活跃工作上下文的关系。
2. 已能定位相关结构化对象及其信息地位。
3. 已具备本轮判断所需的最小来源线索。
4. 已知道是否存在关键冲突、缺口或需要回看原文的条件。

如果继续补上下文也不能消除歧义，应在 Chat 中澄清，或由收敛回合保留为待澄清，而不是无限复水。

## 7. 装配失败时的默认动作

当找不到当前包版本、来源引用失效或无法可靠确定活跃工作上下文时，默认动作应是：

1. 保留当前用户输入和已有原始记录。
2. 显式说明上下文缺口或范围歧义。
3. 回退到 Chat 追问，或在触发收敛后形成待澄清提案。
4. 避免以不完整工作视图产出看似稳定的结论。

这与 PRD 的协作协议一致：不静默合并，不假装已经收稳。

## 8. Context Manifest（上下文装配清单）

每次 Chat、判断或收敛的模型调用前，装配器必须先形成一份不可变的 `Context Manifest`，用来回答“这次调用实际基于哪些版本、消息、来源和装配规则”。

Manifest 只记录引用、版本、范围、裁剪结果和完整性校验，不复制完整 Prompt、工作包正文或原始消息。原始消息、不可变包版本和来源材料仍是权威记录；Manifest 只是 Trace 中的装配证据。

最小记录范围包括：

| 字段组 | 最小含义 |
| --- | --- |
| `context_manifest_id` | 本次装配清单的唯一标识 |
| `model_call_ref` | 本次实际模型调用的 `model_call_id` |
| `instruction_and_schema_refs` | System / Runtime Developer / 输出 Schema / Tool 集合的版本引用 |
| `request_kind` | `chat / judgement / convergence` 等调用类型 |
| `package_ref` | `package_id`、包版本和结构化状态版本 |
| `structured_package_input_ref` | 本次调用共用的 Structured Package Input ID 与内容哈希 |
| `snapshot_lifecycle` | 快照的形成时间、关联推进链与保留状态 |
| `message_scope` | 活动历史窗口、原始序号范围、`history_compaction_ref`、连续保留消息、复水消息、必要工具链引用与 Raw User Message 边界 |
| `source_refs` | 证据对象使用的来源引用，以及本次 Source Resolver 读取形成的工具结果引用 |
| `included_sections` | 实际装配的工作包模块和关键上下文部分 |
| `omissions` | 被裁剪或无法取得的项及可枚举原因 |
| `assembly_policy_version` | 本次使用的装配、排序与裁剪规则版本 |
| `budget` | `context_budget_profile`、原始共享窗口、90% 压缩线、95% 有效窗口、五个逻辑输入面各自用量、Tool / Schema 开销、共享活动总量、压缩前后用量与实际调用用量引用 |
| `degradation_flags` | 对本次 Chat、判断、收敛或稳定写入的影响 |
| `content_hashes` | Structured Package Input 与已定义内容指纹的来源片段等既有校验哈希；消息正文仍以不可变消息引用为准 |
| `transport_ref` | 供应商、Adapter / 协议 / 能力配置版本、调用尝试，以及供应商返回的请求 / 响应 ID（如可得） |

Chat、实际调用模型的判断和收敛各自保留 Manifest，因为它们的任务指令、结构化 Schema、原始消息范围和执行结果可以不同；但同一推进链中实际形成的 Manifest 必须引用相同的 `structured_package_input_ref`。纯规则预筛的判断不伪造模型调用或 Manifest，只保留判断 Trace。收敛可以看到 Chat 刚产生的 Assistant 消息，这只改变 Conversation History 的消息范围，不改变 Structured Package Input。

Manifest 直接通过各输入面的引用、范围、版本和遗漏记录回答“EvoCanvas 准备了什么”，通过 `model_call_ref` 与 `transport_ref` 回答“哪次调用经过什么映射并返回了什么身份记录”。首版默认不持久化 `ResponsesApiRequest` 等供应商原生请求、最终响应载荷或它们的整体内容哈希。未来若为排障增加原始载荷采样，必须作为显式开启、短期保留的诊断能力，不能成为稳定写入或历史回放的前提。各 Adapter 是否丢字段、错映射或混淆指令与数据，由各自的契约测试和固定序列化样例覆盖。

## 9. 降级与验证底线

- 非关键历史或来源片段被裁剪时，Manifest 必须记录遗漏项和原因，不得伪装为完整上下文。
- Conversation History 不得按固定轮数裁剪；未命中阈值时必须包含完整活动窗口，命中阈值时必须引用可追溯的 History Compaction Artifact，当前 Raw User Message 不得重复进入 History。
- 明确引用的工具调用或结果必须按最小完整工具链纳入；链条缺失、超预算或引用歧义必须进入 `omissions` 与降级标记，不得用新生成摘要冒充精确原文。
- 首版不得使用模型或向量检索器从全部会话自动挑选散点历史；用户回指压缩前内容时按引用复水精确原文，无法唯一定位时必须在 Chat 中澄清。
- 压缩只改变模型可见历史，不删除原始消息，不改变 Structured Package Input、确认状态或对象信息地位。
- System、Runtime Developer、Structured Package、Raw User Message 和本次已选定的 Tool / Schema 不参与压缩；压缩前后引用或内容哈希变化时必须视为重新装配，不能冒充同一次 History 压缩。
- Structured Package Input 常态不超过 1K Token，达到 2K 硬上限时必须以装配异常失败；不得通过扩大模型窗口让短工作面演化成完整包正文。
- 任一 Adapter 都不得静默改变当前 `context_budget_profile` 的原始共享窗口、有效窗口比例、共享压缩线、压缩产物结构或 20K 近期完整对话链上限；使用其他预算档时必须显式切换配置并写入 Manifest。
- Source Resolver 读取结果只进入原始工具记录和 Conversation History，不改写、污染或生成新的 Structured Package Input 快照。
- Source Resolver 读取失败时，必须关闭依赖该原文的验证、信息地位升级与稳定写入，但不因此重建 Structured Package Input。
- 关键包版本、消息范围或必要来源不可用时，Chat 可以继续承接用户，但必须关闭依赖该缺口的判断、收敛或稳定写入。
- 用户前台只说明可感知的语义影响；具体缺失引用、裁剪原因和装配规则版本进入 Trace。
- 在相同权威状态、消息范围和装配规则下，Manifest 的引用、排序与裁剪结果应可确定性复现。
- 各 Runtime Adapter 必须从五个仍保持独立来源身份的逻辑输入面直接构造供应商原生临时请求，并在调用完成后丢弃；每个 Adapter 的契约测试都必须覆盖字段缺失、角色错映射、顺序漂移和把 Structured Package Input 并入 Runtime Developer Message 的失败场景。
- 多供应商支持不得分裂 Context Assembly；对相同权威状态、消息范围和装配策略，不同 Adapter 接收的五个逻辑输入面及其引用必须一致，差异只能出现在供应商协议映射层。
- 供应商或协议版本只有通过统一的一致性、工具往返、结构化输出、流式事件、错误归一化和 Trace 关联测试后，才能进入正式支持矩阵。
- 同一推进链中实际形成的 Chat、模型判断和收敛 Manifest 必须具有相同的 `structured_package_input_ref`；不一致时不得进入稳定写入。
- 活跃推进链中的 Structured Package Input 快照丢失时，只能从 Manifest 指向的权威版本、来源和装配策略重建；重建哈希不一致时，不得冒充原快照或继续稳定写入。
- Trace 必须能通过 `context_manifest_id` 区分“模型已看到但判断错误”与“装配时根本没有提供必要上下文”。

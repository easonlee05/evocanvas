# Context Budget and Compaction（上下文预算与压缩）

> 当前成熟度层级：`L2 对象与流程定义层`
>
> 已确认方向：模型调用使用一个共享上下文池，不为 Conversation History 或其他逻辑输入面预留独立配额；系统保留完整原始消息，并在共享活动上下文达到 Token 阈值后只压缩模型可见的 Conversation History，其他输入面不参与压缩。
>
> 已否决参数：256K 不作为 Conversation History 独立预算；五个逻辑输入面不按固定额度切分；Structured Package Input 不使用 160K 大包预算；压缩后 History 不保留 96K 大窗口。
>
> 已确认参数：产品侧原始共享窗口为 272K；共享活动上下文达到原始窗口 90%（244.8K）时自动压缩，95%（258.4K）是有效窗口上限，最后 5%（13.6K）不可分配。
>
> 已确认压缩结果：借鉴 Codex 的“小型 checkpoint + 极少近期原文”原则，但不照搬只保留 User 原文的本地布局。旧 History 被拆为一份简洁的 History Compaction Artifact 与最近累计不超过 20K Token 的完整对话链；不规定 96K 等压缩后总量。精确摘要模板、Schema 与生成上限通过后续评测确定。

## 1. 这份规格决定什么

这份规格定义五个逻辑输入面、Tool / Schema 和模型输出如何共享同一个上下文窗口，以及何时只压缩 Conversation History、如何保留原始历史和怎样跨供应商执行同一策略。

五个逻辑输入面仍然分离装配、分别计数，但分离不等于分配独立额度。没有某个输入面可以宣称“自己的空间不受其他内容影响”。

供应商公布的上下文窗口只是模型能力上限，不是 EvoCanvas 每轮都要用满的运行预算。EvoCanvas 可以在能力上限内设置更小的产品侧共享窗口，以控制成本、延迟和跨供应商差异。

本文中的 `K` 表示 1,000 Token。

## 2. 共享窗口模型

### 2.1 哪些内容共享窗口

以下内容共同消耗模型的物理上下文窗口：

1. System Message。
2. Runtime Developer Message。
3. Structured Package Input。
4. Conversation History。
5. Raw User Message。
6. Tool 定义、输出 Schema、角色边界和供应商协议序列化开销。
7. 当前调用生成的推理与模型输出。

`max_output_tokens` 可以作为单次生成上限单独配置，但这不代表输出位于上下文窗口之外。装配器必须为即将生成的输出保留余量，不能把共享窗口全部塞满输入后再请求输出。

### 2.2 三条边界

EvoCanvas 1.0 采用以下共享窗口基线：

| 边界 | 计算方式 | 候选值 | 含义 |
| --- | ---: | ---: | --- |
| 自动压缩线 | 原始共享窗口 × 90% | 244.8K | 达到后主动压缩 History，避免继续逼近硬边界 |
| 有效窗口上限 | 原始共享窗口 × 95% | 258.4K | 装配器允许活动上下文使用的统一上限 |
| 原始共享窗口 | 产品配置值 | 272K | 产品侧硬边界，且不得超过供应商物理窗口 |

因此共享窗口不是“272K 输入 + 另算输出”，也不是“256K History + 其他输入另算”。它是一个总池：0%—90% 为正常运行区，90%—95% 为压缩和恢复缓冲区，95%—100% 为不可分配安全余量。

95%—100% 的余量不对应某个固定输入面，也不得被业务模块申请占用。它用于吸收基础指令、工具协议、输出增长、图片或文件计数差异、估算偏差和供应商边界误差。

### 2.3 分别记账，不分别配额

各输入面的数字只用于识别异常膨胀、保证语义边界和解释一次调用，不是窗口切片：

| 逻辑输入面 | 正常形态 | 防膨胀规则 |
| --- | --- | --- |
| System Message | 稳定、短小的产品级规则 | 目标 `<= 4K`，达到 8K 告警；不得靠扩大窗口掩盖膨胀 |
| Runtime Developer Message | 当前调用必要的动态权限、能力和工具规则 | 目标 `<= 4K`，达到 8K 告警；只保留本次调用生效内容 |
| Structured Package Input | 通常约 200 个汉字的短结构化工作面 | 目标 `<= 1K`，超过 2K 装配失败；不得装入完整包正文或证据摘录集 |
| Conversation History | 压缩检查点后的连续原始消息与压缩产物 | 不设独立额度；只受共享压缩线和共享有效窗口约束 |
| Raw User Message | 当前用户输入原文 | 不设普通截断线；无法保真装配时转附件、分段或显式失败 |

Context Manifest 必须记录各输入面的实际 Token、Tool / Schema 开销、活动上下文总量和剩余共享余量。这些数据用于观测和治理，不赋予任何输入面独占空间。

Structured Package Input 默认只表达当前目标、最关键的稳定结论与未决、包 / 状态版本和来源引用。完整对象正文仍在权威包中，模型需要时通过引用读取。约 200 字是常态目标，不是要求填充到 1K Token。

## 3. 与 Codex 的 90% / 95% 关系

当前 Codex 源码快照中，GPT-5.6-Sol 的产品侧 `context_window` 为 272K：

- 默认有效窗口比例为 95%，即 `272K × 95% = 258.4K`。
- 默认自动压缩线为原始窗口的 90%，即 `272K × 90% = 244.8K`。
- 244.8K—258.4K 这 13.6K 用于完成压缩、处理当前回合增长和恢复到安全区。
- 258.4K—272K 这 13.6K 是不可分配安全余量；源码备注将它用于基础指令、工具协议、模型输出和计数偏差等综合风险。

System Prompt 在模型的物理上下文里，也进入 Codex 的基础指令 Token 估算；它不在 272K 之外，也没有一个额外隐藏窗口。即使 5% 的设计目的包含防护基础指令开销，也不表示基础指令从正常计数中扣除。源码只给出统一的 headroom（安全余量）语义，没有再把它按 System、Tool 或 Output 切成固定比例。

Codex 默认按 `Total` 作用域判断自动压缩，即计算整个活动上下文，而不是只计算 user / assistant 对话。它另有可选的 `BodyAfterPrefix` 作用域，可在压缩判断中扣除当前窗口的固定前缀；但完整有效窗口仍是统一硬上限。

Codex 的开源本地压缩路径会让模型生成一份包含当前进展、关键决策、约束和后续动作的交接摘要，再额外保留最近累计不超过 20K Token 的 User 原文。Assistant 回答与 Tool 结果虽然不以原消息常驻，但其重要内容应进入摘要，因此模型并非只看到问题、完全看不到回答。

EvoCanvas 不照搬这一点。产品收敛高度依赖问题与回答的对应关系、方案措辞、确认范围和工具证据，因此近期保留单元必须是完整对话链，而不是孤立 User 消息。

EvoCanvas 已确认同时采用这套“共享窗口 + 提前压缩 + 最后安全余量”机制与 272K 产品基线；对压缩后消息布局则只借鉴原则，并按产品对话需要保留完整近期对话链。

## 4. 历史窗口与自动压缩

### 4.1 活动窗口

Conversation History 默认包含从最近一次有效压缩检查点之后开始、直到当前 Raw User Message 之前的全部原始 `user / assistant / tool` 消息，不设置固定轮数，也不按“最近 N 轮”提前丢弃。

第一次压缩前，活动窗口就是当前会话的全部既有原始消息。压缩后，模型可见 History 由以下内容构成：

1. 一份受治理的 History Compaction Artifact（历史压缩产物），只总结未以原文保留的较旧前缀。
2. 从被压缩窗口尾部保留的完整近期对话链，累计不超过 20K Token。
3. 压缩检查点之后新产生的完整连续原始消息。
4. 用户明确回指压缩前内容时，按需复水的精确原始消息与必要工具链。

完整近期对话链以 User 输入为起点，包含对应 Assistant 回复以及两者之间发生的全部 Tool 调用与结果。选择时从最新完整链向前累积；不得为了塞入 20K 而拆散工具链、只留问题、只留回答或截断单条原始消息。某条完整链本身超过 20K 时不常驻原文，由压缩产物承接并保留精确复水引用。

未进入近期完整链的旧 Assistant 消息与 Tool 链由 History Compaction Artifact 承接。它们仍完整保存在原始消息记录中；用户明确回指、验证依赖原文或摘要不足时，再按需复水精确记录，并补齐最小完整工具链。

当前 Raw User Message 始终独立传入，不在 History 中重复。

### 4.2 只按共享总量触发

装配器按供应商实际序列化口径计算 `active_context_tokens`。当共享总量达到 244.8K 时，在本次模型调用前压缩 Conversation History；不再设置 `History >= 230K` 之类的独立触发条件。

压缩完成后不设置 History 总量目标。压缩器直接重建为“简洁压缩产物 + 最多 20K 近期完整对话链”；摘要不得为了覆盖所有措辞而演化成另一份长历史。重新计数通过后，压缩检查点之后的新 `user / assistant / tool` 消息继续以原文累积，直到共享活动上下文再次达到 90% 压缩线。

压缩操作只能改变 Conversation History 的模型可见表示。System、Runtime Developer、Structured Package、Raw User Message 和本次已选定的 Tool / Schema 不得被摘要、截断、合并或改写成压缩版本，因为它们各自承担当前调用不可替代的语义与能力契约。

若压缩 History 后仍超过 95% 有效窗口，装配器可以再次压缩 History；若 History 已达到最低安全表示仍无法装入，则停止本次调用并显式报告预算缺口。系统可以在下一次重新装配时修复异常膨胀的指令或重新选择与任务相符的工具集合，但这属于配置修复或能力选择，不属于上下文压缩，也不得在当前 Adapter 内静默发生。

### 4.3 压缩不删除原始历史

自动压缩只替换后续模型调用中的活动 History 表示，不删除或改写原始消息存储。压缩前的每条原始 `user / assistant / tool` 消息仍可按 `message_id` 和 `message_seq` 追溯、回放与精确复水。

History Compaction Artifact 是运行时上下文产物，不是业务事实、确认记录或结构化包版本。它不得：

- 把候选内容升级为确认结论；
- 抹去尚未解决的冲突、缺口或否定意见；
- 改写 Structured Package Input；
- 取代用户确认消息、来源原文或工具结果；
- 因摘要措辞而改变对象治理状态。

用户明确回指压缩前消息时，系统优先复水精确原文，而不是只依赖压缩产物。回指无法唯一定位时回到 Chat 澄清。

## 5. 压缩产物与 Manifest

每次有效压缩生成不可变的 `history_compaction_id`。压缩产物至少记录：

| 字段 | 最小含义 |
| --- | --- |
| `conversation_id` | 所属会话 |
| `source_message_range` | 被压缩的原始消息序号范围 |
| `retained_recent_message_refs` | 从被压缩窗口尾部仍以原文保留的完整近期对话链，累计不超过 20K Token |
| `rehydratable_message_refs` | 可按需恢复的压缩前消息引用 |
| `pre_compaction_tokens`、`post_compaction_tokens` | 同一计数口径下的压缩前后用量 |
| `compaction_policy_version` | 压缩规则、模板和模型配置版本 |
| `content_hash` | 压缩产物的内容指纹 |
| `provider_compaction_ref` | 供应商原生压缩产物引用，可空 |

Context Manifest 不复制压缩正文，只记录本次调用使用的 `history_compaction_id`、活动消息范围、复水消息引用、各输入面 Token 用量、共享窗口档位、压缩作用域、触发原因与压缩前后用量。

## 6. 跨供应商执行

同一个 EvoCanvas 共享窗口档必须先于 Runtime Adapter 确定。Adapter 只做协议映射与供应商口径计数，不能因为底层模型窗口更大就自行扩张 History，也不能因为序列化差异静默截断任一输入面。

EvoCanvas 1.0 的 272K 标准档在首批示例模型上保持一致：

| 示例模型 | 供应商能力窗口 | EvoCanvas 原始共享窗口 | 自动压缩线 | 有效窗口上限 |
| --- | ---: | ---: | ---: | ---: |
| GPT-5.6 Sol | 1,050K | 272K | 244.8K | 258.4K |
| DeepSeek-V4-Flash / Pro | 1,000K | 272K | 244.8K | 258.4K |

供应商能力窗口只表示能够承载该档，不会自动成为 EvoCanvas 的运行窗口。采用 272K 产品硬边界可以避免 EvoCanvas 主动进入 GPT-5.6 Sol 官方标注的 `>272K` 长输入价格区间；这不影响供应商未来调整能力窗口或价格时重新评估产品档位。

Token 必须按供应商实际序列化后的输入口径计算，因为角色边界、Tool 定义、Schema、图片和文件都可能产生文本之外的 Token。OpenAI Adapter 应优先使用官方 input token count 能力对待发送的 `ResponsesApiRequest` 做调用前精确计数；其他 Adapter 使用其官方计数能力或经过一致性测试的版本化计数器。供应商返回实际用量后，应记录到 Trace 并用于校准估算偏差。

供应商原生压缩只能作为可选的传输优化或安全网，不能成为 EvoCanvas 唯一的历史状态。标准行为必须由供应商中立的 History Compaction Artifact 表达，保证切换 Adapter 后仍能从原始消息和 Manifest 重建同一活动窗口。

模型能力或计数器不满足当前共享窗口档时，Runtime 必须选择一个显式兼容档并写入 `context_budget_profile`；不得在 Adapter 内静默减少历史、包内容或用户输入。

## 7. 调用前执行顺序

每次模型调用前按以下顺序执行：

1. Context Assembly 形成五个逻辑输入面、Tool 集合与输出 Schema。
2. Runtime 根据模型能力选择显式的 `context_budget_profile`；Adapter 只做协议映射并返回供应商口径 Token 计数。
3. 若共享活动上下文达到原始窗口的 90%，生成或刷新历史压缩产物。
4. 重新装配、重新计数，并把压缩引用和各输入面用量写入 Context Manifest。
5. 若总量仍超过 95% 有效窗口，只允许再次压缩 History；其他输入面和本次已选定的 Tool / Schema 保持不变。
6. History 已达到最低安全表示后仍不能落入有效窗口时停止模型调用，记录 `context_budget_exceeded`，不得让 Adapter 自行截断或压缩其他输入面。

Adapter 不能自行触发一套不可见的历史选择规则。所有影响模型可见语义范围的压缩、复水和裁剪决定都必须发生在 Context Assembly，并能由 Manifest 解释。

## 8. 验收底线

- 100 轮短对话只要共享活动上下文未命中 Token 阈值，就必须全部保留在活动 History 中；不能因为轮数多而提前裁剪。
- 5 轮超长工具对话只要共享总量命中阈值，就必须触发压缩；不能因为轮数少而继续塞入。
- 同一共享窗口档下，GPT 与 DeepSeek Adapter 接收相同五部分语义输入和相同压缩检查点，差异只能来自协议序列化与计数结果。
- System Message、Runtime Developer Message、Structured Package Input、History、Raw User Message 和 Tool / Schema 必须分别记账，但不得形成彼此隔离的预算池。
- 每次压缩前后，System、Runtime Developer、Structured Package、Raw User Message 和本次 Tool / Schema 的内容引用与哈希必须保持一致；只有 Conversation History 的模型可见表示可以变化。
- 压缩后仍能通过原始消息存储回放全部历史，并能精确复水用户明确引用的压缩前消息。
- 压缩后的常驻 History 不得继续保留 96K 等大段旧对话；除简洁压缩产物外，被压缩窗口只允许保留累计不超过 20K Token 的近期完整对话链。
- 近期链必须同时保留 User、对应 Assistant 和中间完整 Tool 链，不得出现只有问题没有回答或只有工具结果没有调用的常驻片段。
- 未进入近期链的旧 Assistant / Tool 原文不常驻压缩结果；需要复水其中任一 Tool 消息时必须补齐对应的最小完整工具链。
- 压缩产物中的错误措辞不得直接改变包对象、确认状态或稳定交接版本。
- Structured Package Input 的常态计数应不超过 1K，超过 2K 时必须装配失败并记录异常，不能靠扩大共享窗口掩盖包设计失控。
- Raw User Message 不得被静默截断；无法在有效窗口内保真装配时必须显式失败或转为分段 / 附件处理。
- Context Manifest 必须能解释本次调用是否压缩、为什么压缩、压缩了哪些范围、各输入面分别使用多少 Token，以及共享池还剩多少空间。

## 9. 外部规格校准

- [OpenAI GPT-5.6 Sol 模型页](https://developers.openai.com/api/docs/models/gpt-5.6-sol)：公开上下文窗口、最大输出与长输入价格分段。
- [OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction)：说明按 rendered token count 阈值触发服务端压缩的机制。
- [OpenAI Counting tokens](https://developers.openai.com/api/docs/guides/token-counting)：说明工具、Schema、角色与格式 Token 需要按实际请求计数。
- [DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/?article_id=article_1779470751466_8)：公开 DeepSeek V4 的上下文窗口与最大输出。
- [Codex 模型目录](https://github.com/openai/codex/blob/4f1992732c832fe125608980a03ec2b66710c4e4/codex-rs/models-manager/models.json#L25)：当前源码快照中的 Codex 产品侧模型窗口。
- [Codex 有效窗口比例](https://github.com/openai/codex/blob/4f1992732c832fe125608980a03ec2b66710c4e4/codex-rs/protocol/src/openai_models.rs#L355-L356)：默认只将原始窗口的 95% 作为有效窗口。
- [Codex 安全余量说明](https://github.com/openai/codex/blob/4f1992732c832fe125608980a03ec2b66710c4e4/codex-rs/protocol/src/openai_models.rs#L421-L424)：5% 用于基础指令、工具开销与模型输出等余量。
- [Codex 自动压缩线](https://github.com/openai/codex/blob/4f1992732c832fe125608980a03ec2b66710c4e4/codex-rs/protocol/src/openai_models.rs#L459-L467)：默认按原始窗口 90% 推导压缩线。
- [Codex 基础指令计数](https://github.com/openai/codex/blob/4f1992732c832fe125608980a03ec2b66710c4e4/codex-rs/core/src/context_manager/history.rs#L165-L186)：活动 History 估算显式加上基础指令 Token。
- [Codex 请求装配](https://github.com/openai/codex/blob/4f1992732c832fe125608980a03ec2b66710c4e4/codex-rs/core/src/client.rs#L843-L864)：基础指令与 Tool 定义实际进入供应商请求。
- [Codex 压缩计数作用域](https://github.com/openai/codex/blob/4f1992732c832fe125608980a03ec2b66710c4e4/codex-rs/core/src/session/context_window.rs#L27-L54)：区分总活动上下文与扣除固定前缀后的窗口增长，并保持统一有效窗口硬上限。
- [Codex 压缩摘要模板](https://github.com/openai/codex/blob/4f1992732c832fe125608980a03ec2b66710c4e4/codex-rs/prompts/templates/compact/prompt.md)：要求摘要承接当前进展、关键决策、约束和后续动作。
- [Codex 开源本地压缩路径](https://github.com/openai/codex/blob/4f1992732c832fe125608980a03ec2b66710c4e4/codex-rs/core/src/compact.rs#L589-L649)：使用压缩摘要替换旧 History，并把额外保留的近期 User 原文限制在 20K Token；EvoCanvas 只借鉴“小摘要 + 20K 近期原文”原则，改为保留完整近期对话链。

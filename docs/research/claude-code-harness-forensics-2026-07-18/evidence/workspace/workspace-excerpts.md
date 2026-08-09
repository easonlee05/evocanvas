# EvoCanvas 工作区证据摘录

> 生成时间：2026-07-21T17:50:15+08:00
> 摘录保留原始行号；完整文件仍以仓库当前内容为准。

## W-PRD-001 — 产品定位

来源：`docs/vision/EvoCanvas1.0-PRD.md:16-16`

```text
16 | EvoCanvas 不是 PRD 生成器，也不是自由白板工具。它是一款以 `Vibe Shaping` 为核心的对话驱动工作台，首要服务产品经理，但不只服务产品经理，也面向创业者、设计师、业务负责人等需要把模糊感觉收敛成结构化判断的人。它用于接住尚未成形的感觉和多源输入，通过对话塑形、结构收敛和画布显影，最终形成可交接、可执行的结构化交付物，并可派生为面向 AI 的 PRD。本文档中的 `1.0` 只定义首版必须成立的最小闭环；超过该闭环但仍有价值的能力统一放入“后续版本范围”。
```

## W-PRD-002 — 产品旅程与内层闭环

来源：`docs/vision/EvoCanvas1.0-PRD.md:95-107`

```text
 95 | `感觉接入 -> 对话塑形 -> 结构收敛 -> 画布显影 -> 结构化交接`
 96 | 
 97 | 其中：
 98 | 
 99 | 1. `感觉接入`：允许用户从一句话、一段聊天、一张图、几个关键词或一段语音开始，不要求先写出稳定需求。
100 | 2. `对话塑形`：agent 先理解、命名、拆解和追问，让模糊感觉逐步变成可讨论对象。
101 | 3. `结构收敛`：把已经初步成形的内容转为可治理的结构化候选对象，并持续暴露不确定性、冲突和待决策事项。
102 | 4. `画布显影`：当结构稳定到可以承载时，再在画布上显影卡片、栏目、关系、冲突、依赖和缺口。
103 | 5. `结构化交接`：把当前稳定结构打包为可供人阅读、或供下游 AI 执行与实现的产品上下文。
104 | 
105 | 原有 1.0 最小闭环不废弃，而是作为 `结构收敛` 的内部展开：
106 | 
107 | `输入编译 -> 待澄清问题 -> 约束 / 待决策 -> 结构化交接物`
```

## W-PRD-003 — 信任分级与约束候选

来源：`docs/vision/EvoCanvas1.0-PRD.md:1242-1268`

```text
1242 | ### 8.6.8 信任分级
1243 | 
1244 | 信任分级区分“形成结构”和“让结构成为稳定依据”。
1245 | 
1246 | #### 可自动形成草稿或候选
1247 | 
1248 | 在结构、来源和版本检查通过后，收敛部件可以自动写入：
1249 | 
1250 | - 证据卡
1251 | - 问题卡
1252 | - 待澄清卡
1253 | - 约束候选及说明补充
1254 | - 待决策 / 方案承接候选
1255 | - 交接草稿
1256 | - 弱关系
1257 | - 冲突标记
1258 | 
1259 | 这些对象出现在画布上，只表示当前工作状态已经被整理，不表示用户已经拍板。
1260 | 
1261 | #### 需要 Chat 确认依据的信息地位升级
1262 | 
1263 | - 待澄清卡改为已澄清
1264 | - 关闭关键待澄清问题
1265 | - 约束卡改为已生效
1266 | - 待决策 / 方案承接卡改为已决定
1267 | - 交接版本改为已确认或可供下游依赖
1268 | - 其他会改变事实边界的语义状态变化
```

## W-PRD-004 — 唯一状态与约束状态

来源：`docs/vision/EvoCanvas1.0-PRD.md:1838-1897`

```text
1838 | ### 10.1 状态权威与通用治理分组
1839 | 
1840 | 每类独立业务对象只维护一套可写的类型化状态。系统不得同时维护一套可独立修改的“通用顶层状态”，避免同一对象出现两套互相冲突的事实状态。
1841 | 
1842 | 为了支持上下文筛选、治理门禁、交接装配和界面分组，系统可以根据“对象类型 + 类型化状态”确定性派生以下通用治理分组：
1843 | 
1844 | - 来源依据
1845 | - 形成中
1846 | - 未解决
1847 | - 稳定可用
1848 | - 历史保留
1849 | 
1850 | 通用治理分组只用于统一理解和展示，不直接写入，也不能绕过类型化状态的流转规则。具体映射规则必须版本化、可重算；映射变化不得修改历史对象状态。
1851 | 
1852 | 对象的结构或来源是否通过验证，另以独立验证结果表达：
1853 | 
1854 | - 未验证
1855 | - 通过
1856 | - 警告
1857 | - 不通过
1858 | 
1859 | 验证结果不替代对象状态。例如，一个约束可以处于“待确认”且结构验证“通过”，也可以处于“草稿中”且验证结果为“警告”。
1860 | 
1861 | ### 10.2 唯一权威的类型化状态
1862 | 
1863 | #### 证据卡
1864 | 
1865 | - 已收录
1866 | - 已引用
1867 | - 已归档
1868 | 
1869 | #### 问题卡
1870 | 
1871 | - 初步理解
1872 | - 待收敛
1873 | - 已收敛
1874 | - 已归档
1875 | 
1876 | #### 待澄清卡
1877 | 
1878 | - 待提出
1879 | - 待确认
1880 | - 已澄清
1881 | - 已阻塞
1882 | - 已关闭
1883 | 
1884 | #### 约束卡
1885 | 
1886 | - 草稿中
1887 | - 待确认
1888 | - 已生效
1889 | - 已替代
1890 | - 已归档
1891 | 
1892 | #### 待决策 / 方案承接卡
1893 | 
1894 | - 待判断
1895 | - 待确认
1896 | - 已决定
1897 | - 已归档
```

## W-HARNESS-001 — 十二层 Harness 公式

来源：`docs/harness/README.md:21-40`

```text
21 | EvoCanvas 当前采用更贴近工程落地的实践型 harness 公式：
22 | 
23 | ```md
24 | Harness = Instructions + Context + Memory + Runtime + Tools + Orchestration + Lifecycle + Safety + Governance + Observability + Verification + Evaluation
25 | ```
26 | 
27 | 这不是为了堆概念，而是为了让每个后端能力都有明确边界：
28 | 
29 | - 指令告诉系统“应该怎么做”。
30 | - 上下文告诉系统“当前正在处理什么”。
31 | - 记忆告诉系统“过去沉淀了什么，哪些能被复用”。
32 | - 运行时提供受控执行边界。
33 | - 工具提供外部能力接入面。
34 | - 编排决定本轮如何调度。
35 | - 生命周期定义运行记录、包版本和对象状态如何结束、替代与过时。
36 | - 安全负责防出事。
37 | - 治理负责定生效边界。
38 | - 可观测性负责留痕、回放和归因。
39 | - 验证负责判断这一次是否做对。
40 | - 评估负责判断系统长期是否有价值。
```

## W-HARNESS-002 — L2/L3 文档成熟度清单

来源：`docs/harness/README.md:82-115`

```text
 82 | - `02-memory-state/00 Memory and State（记忆与状态）.md`：L3 主文档，定义原始记录、不可变包版本和状态账本三类权威记录及其边界。
 83 | - `02-memory-state/01 Memory（记忆）.md`：L3 规格，定义包身份、统一包 Schema、不可变版本、轻量索引、复水和保留策略。
 84 | - `02-memory-state/02 State Ledger（状态账本）.md`：L3 规格，定义追加式账本、类型化对象状态、派生治理分组、确认记录和版本指针。
 85 | - `02-memory-state/03 Stable State and Handoff（稳定状态与交接）.md`：L3 规格，定义交接引用、确认版本、过时判断和下游版本选择。
 86 | 
 87 | - `03-runtime-tools/00 Runtime and Tools（运行时与工具）.md`：L3 主文档，说明 Chat、判断、收敛、提交与工具的关系。
 88 | - `03-runtime-tools/01 Runtime（运行时）.md`：L3 规格，定义四类运行记录、触发调度、按包并发和幂等原子提交。
 89 | - `03-runtime-tools/02 Tool Contract（工具契约）.md`：L3 规格，定义工具 Schema、权限、幂等、来源入链和副作用边界。
 90 | - `03-runtime-tools/03 Failure and Recovery（失败与恢复）.md`：L3 规格，定义错误分类、租约恢复、未知提交核对、Outbox 重放和投影重建。
 91 | 
 92 | - `04-orchestration-lifecycle/00 Orchestration and Lifecycle（编排与生命周期）.md`：L3 主文档，定义判断、收敛、治理、提交和投影的连接主链。
 93 | - `04-orchestration-lifecycle/01 Orchestration（编排）.md`：L3 规格，定义触发来源、判断决策、合并调度、结果路由和过期处理。
 94 | - `04-orchestration-lifecycle/02 Lifecycle（生命周期）.md`：L3 规格，定义运行记录、不可变包版本、对象信息地位和投影的生命周期。
 95 | - `04-orchestration-lifecycle/03 Convergence Operations（收敛操作）.md`：L3 规格，定义结构化操作、复杂输入提案策略、部分放行和 Chat 分工。
 96 | - `04-orchestration-lifecycle/04 Gate Adjudication（门禁裁决）.md`：L3 规格，定义候选整理、信息地位升级和外部不可逆动作的三类门禁边界。
 97 | - `04-orchestration-lifecycle/05 Implementation Baseline（实现基线）.md`：L3 规格，汇总实现单元、原因码、迁移边界和验收场景。
 98 | 
 99 | - `05-safety-governance/00 Safety and Governance（安全与治理）.md`：说明安全与治理的关系。
100 | - `05-safety-governance/01 Safety（安全）.md`：定义语义安全、风险拦截和防误导边界。
101 | - `05-safety-governance/02 Governance（治理）.md`：定义事实生效、确认、回退和追溯边界。
102 | - `05-safety-governance/03 Governance Baseline（治理基线）.md`：汇总状态机、Chat 确认记录和治理 trace 的最小基线。
103 | - `05-safety-governance/04 Facts and Risk（事实与风险）.md`：定义事实可用性层级和风险分级。
104 | - `05-safety-governance/05 Object Governance（对象治理）.md`：定义核心卡片对象的状态与治理规则。
105 | - `05-safety-governance/06 Handoff Governance（交接物治理）.md`：定义结构化交接物的确认、过时与禁令。
106 | - `05-safety-governance/07 Authority and Guardrails（权限与护栏）.md`：定义 AI、系统与用户之间的动作权限。
107 | 
108 | - `06-observability/00 Observability（可观测性）.md`：定义 trace、回执、来源链和诊断口径。
109 | - `06-observability/01 Projection Signals（显影提示）.md`：定义画布状态变化的显影方式与低打扰提示边界。
110 | - `06-observability/02 Trace Model（追踪模型）.md`：定义回合、状态差异、治理、来源链和异常追踪。
111 | - `06-observability/03 Diagnostic Views（诊断视角）.md`：定义输入、上下文、编排、治理和验证问题的诊断视角。
112 | - `07-verification/00 Verification（验证）.md`：定义单次过程 / 输出的过关标准。
113 | - `08-evaluation/00 Evaluation（评估）.md`：定义长期系统价值和产品效果评估。
114 | - `08-evaluation/01 Independent Evaluation（独立评估）.md`：定义高价值结果的额外复核口径。
115 | - `08-evaluation/02 Evaluation Metrics（评估指标）.md`：定义待澄清、冲突、约束、交接物和下游误解相关指标。
```

## W-CONTEXT-001 — 四来源、预算裁剪与失败回退

来源：`docs/harness/01-instructions-context/03 Context Assembly（上下文装配）.md:11-72`

```text
11 | 它回答的不是“系统里有哪些数据”，而是“这一轮该带入哪份已治理状态、哪些原始记录和哪些可复水证据”。它不负责生成新的业务结论，也不重新组织对象的事实地位。
12 | 
13 | ## 2. 装配输入
14 | 
15 | 一次模型请求按职责接收以下输入：
16 | 
17 | 1. System Message：稳定身份、认知原则和表达纪律。
18 | 2. Runtime Developer Message：当前能力、权限、工具规则与最小运行时要求。
19 | 3. Structured Package Input：当前结构化工作包的统一预算内工作视图，只包含证据对象已有的必要摘录、结构化摘要和来源引用，不额外嵌入复水原文。
20 | 4. 相关原始消息：近期或被用户明确引用的 `user / assistant / tool` 记录。
21 | 5. Raw User Message：本轮用户原话，独立且原样传入。
22 | 
23 | 工作包中的对象、状态和来源引用由既有收敛与治理流程产生；装配器只选择、排序、裁剪和序列化，不调用模型另写一份语义摘要。
24 | 
25 | ## 3. 装配顺序
26 | 
27 | 建议按以下顺序装配：
28 | 
29 | 1. 先放 System Message。
30 | 2. 再放只包含动态规则的 Runtime Developer Message。
31 | 3. 再放统一的 Structured Package Input，其中只使用工作包内已有证据摘录与来源引用。
32 | 4. 再放最近相关或被明确引用的原始消息。
33 | 5. 最后放本轮 Raw User Message。
34 | 
35 | 这样既保留稳定工作状态，也让模型能正确理解用户的最新表达，而不会把运行时数据拼进动态规则或用户原话。Structured Package Input 不拥有指令权限；底层 Runtime Adapter 的序列化方式不改变这个边界。
36 | 
37 | 上述五个逻辑输入面先装配为规范化 `Model Request`。该对象以独立字段或不可变引用保留每个输入面的来源身份，并获得唯一 `model_request_id`；Runtime Adapter 只能执行版本化协议映射，不能在序列化阶段重新裁剪历史、生成业务摘要或改变 Structured Package Input 的指令地位。
38 | 
39 | 同一 `package_id + package_version + state_version + assembly_policy_version` 只生成一份 Structured Package Input。Chat、判断和收敛不各自运行任务选择器，也不各自生成不同摘要；只要上述基线未变，三者必须引用相同的 `structured_package_input_id` 和内容哈希。
40 | 
41 | 该输入快照在关联推进链活跃期间不可变并直接复用，不在每次模型调用前重新装配。推进链进入终态后，完整快照可按保留策略过期；过期不影响权威包版本、原始消息、来源、Manifest、输入 ID 或内容哈希。
42 | 
43 | ## 4. 相关性与界面偏置
44 | 
45 | 活跃工作上下文是装配范围的主依据。用户引用或选中某张卡片时，装配器可以优先选择与其关联的工作包内容、来源引用和原始消息；它不能把卡片快照、页面布局或选中态当成新的事实字段。
46 | 
47 | 如果用户明确提到一段较早对话，装配器应优先取回对应的原始消息与工具记录。需要核对包外原始材料时，通过只读 Source Resolver 按 `source_ref` 和具体位置读取，并先保存为原始 `tool` 记录。结构化工作包只能帮助定位，不能替代原文依据。
48 | 
49 | ## 5. 预算内工作视图
50 | 
51 | 完整工作包和本轮发送给模型的工作视图必须区分：
52 | 
53 | - 完整工作包：版本化、可追溯的结构化状态，不因上下文预算被改写。
54 | - 工作视图：本轮在预算内从完整工作包和相关消息中确定性选出的子集。
55 | 
56 | 预算不足时，装配器优先保留当前目标、有效对象状态、活跃未决与冲突、必要来源标识和近期相关消息；低相关历史、重复证据和长来源正文优先裁剪。被裁剪内容仍可经引用按需复水。
57 | 
58 | 装配器不得以“压缩”为名把候选内容升格为结论、把冲突抹平，或生成一份新的自由文本业务摘要。
59 | 
60 | ## 6. 何时停止补上下文
61 | 
62 | 满足以下条件后，应优先停止继续补料并进入推理：
63 | 
64 | 1. 已能理解当前用户输入与活跃工作上下文的关系。
65 | 2. 已能定位相关结构化对象及其信息地位。
66 | 3. 已具备本轮判断所需的最小来源线索。
67 | 4. 已知道是否存在关键冲突、缺口或需要回看原文的条件。
68 | 
69 | 如果继续补上下文也不能消除歧义，应在 Chat 中澄清，或由收敛回合保留为待澄清，而不是无限复水。
70 | 
71 | ## 7. 装配失败时的默认动作
72 | 
```

## W-TRACE-001 — Chat 到 operation 的追踪链

来源：`docs/harness/06-observability/02 Trace Model（追踪模型）.md:11-83`

```text
11 | ## 2. Chat、判断与收敛追踪
12 | 
13 | 系统至少记录三类关联事件：
14 | 
15 | ```text
16 | chat_turn_id
17 |   -> convergence_judgement_id
18 |   -> convergence_run_id
19 |   -> operation_id
20 | ```
21 | 
22 | ### 2.1 Chat 回合
23 | 
24 | 最小字段包括：
25 | 
26 | - `chat_turn_id`、工作区 ID、当前工作面引用和 `context_manifest_id`。
27 | - 用户原始消息、助手消息和关联工具消息引用。
28 | - 创建与完成时间。
29 | - 是否产生后置收敛判断。
30 | 
31 | ### 2.2 判断事件
32 | 
33 | 最小字段包括：
34 | 
35 | - `convergence_judgement_id` 与触发它的 `chat_turn_id`。
36 | - 判断实际调用模型时对应的 `context_manifest_id`；纯规则判断记录 `rule_only`，不伪造 Manifest。
37 | - 规则命中、模型判断和判断依据摘要。
38 | - 连续消息合并范围。
39 | - 结果：不触发或创建收敛回合。
40 | 
41 | ### 2.3 收敛回合
42 | 
43 | 最小字段包括：
44 | 
45 | - `convergence_run_id`、触发它的判断事件与 Chat 回合。
46 | - 收敛请求对应的 `context_manifest_id`。
47 | - 基础消息序号、基础状态版本和关键上下文对象。
48 | - 提案、验证、风险和治理结果。
49 | - 运行状态与业务结果：已应用、无变化、尚未准备好、治理拒绝、已过期或运行失败。
50 | - `operation_id`、包版本和提交结果（如发生提交）。
51 | - `created_at`、`started_at`、`completed_at`。
52 | 
53 | 消息序号和状态版本保证正确性；时间戳支持排序、耗时分析和回放。
54 | 
55 | ### 2.4 上下文装配追踪
56 | 
57 | Chat、判断和收敛的每次模型调用都必须关联一份独立、不可变的 `Context Manifest`。Manifest 的字段与降级底线由 [Context Assembly §8](../01-instructions-context/03%20Context%20Assembly%EF%BC%88%E4%B8%8A%E4%B8%8B%E6%96%87%E8%A3%85%E9%85%8D%EF%BC%89.md#8-context-manifest%E4%B8%8A%E4%B8%8B%E6%96%87%E8%A3%85%E9%85%8D%E6%B8%85%E5%8D%95) 定义，Trace 只保留引用和本运行结果，不再复制一份上下文清单。
58 | 
59 | 每次实际模型调用还必须通过 `model_request_id` 和本地模型调用 ID 串联其规范化请求、Adapter / 协议版本、调用尝试与供应商返回的请求 / 响应 ID（如可得）。Trace 不要求同时保存逻辑请求哈希和最终载荷哈希；Structured Package Input 与已定义内容指纹的来源片段继续使用各自已有的校验哈希，消息正文以不可变消息引用为准，Adapter 映射正确性由版本化契约测试保证。
60 | 
61 | 同一 `chat_turn_id -> convergence_judgement_id -> convergence_run_id` 推进链中实际发生的模型调用 Manifest 应保留各自的调用差异，但必须引用相同的 `structured_package_input_id` 和内容哈希。若两者不一致，Trace 必须将其标记为上下文基线冲突，相关收敛结果不得稳定写入。
62 | 
63 | Structured Package Input 快照可在推进链终止后过期，但 Trace 必须继续保留其 ID、内容哈希、装配策略版本、权威引用与保留状态。如果后续重建的快照哈希与原记录不一致，Trace 必须显式记录重建失配，不得将重建结果表达为当时的原始输入。
64 | 
65 | 追踪查询至少应能回答：
66 | 
67 | 1. 这次模型调用基于哪个包版本、状态版本和消息范围。
68 | 2. 哪些来源被纳入、裁剪或因不可用而缺失。
69 | 3. 哪些原文由 Source Resolver 实际读取，对应哪个原始工具结果，是否通过内容指纹校验。
70 | 4. 使用了哪个装配规则版本，以及是否发生过预算或语义降级。
71 | 5. 本次结果失败时，问题发生在上下文装配、来源读取、模型判断还是后续验证与治理。
72 | 6. 规范化请求经过哪个 Adapter 与协议版本发送，对应哪次本地调用和供应商请求 / 响应记录。
73 | 
74 | ## 3. 状态差异追踪
75 | 
76 | 状态差异追踪只记录收敛回合实际造成的工作面变化：
77 | 
78 | - 新增或更新对象。
79 | - 状态与关系变化。
80 | - Active Todos、里程碑和交接物投影变化。
81 | - 触发变化的 Chat、判断和收敛回合。
82 | 
83 | 没有结构化变化的普通 Chat 不应伪造状态差异。
```

## W-STATE-001 — L3 对象状态与约束确认规则

来源：`docs/harness/02-memory-state/02 State Ledger（状态账本）.md:69-116`

```text
 69 | ### 4.1 唯一权威业务状态
 70 | 
 71 | 每类对象只维护一个 `object_status`：
 72 | 
 73 | | 对象类型 | 允许状态 |
 74 | | --- | --- |
 75 | | 证据 `evidence` | `collected / cited / archived` |
 76 | | 问题 `problem` | `initial / converging / converged / archived` |
 77 | | 待澄清 `clarification` | `open / pending_confirmation / clarified / blocked / closed` |
 78 | | 约束 `constraint` | `effective / superseded / archived` |
 79 | | 待决策 `decision` | `pending_decision / pending_confirmation / decided / archived` |
 80 | 
 81 | 交接有效性属于包版本治理状态，不是第六类独立对象状态。画布中的交接物承接卡由包版本和 `handoff` 引用模块确定性投影。不得再维护一套可以独立修改的”通用卡片状态”；界面需要通用分组时，使用下述确定性映射。
 82 | 
 83 | 包版本治理状态（草稿中 / 待确认 / 已确认 / 已过时）不属于上述对象状态枚举；治理规则见 [Handoff Governance §4](../05-safety-governance/06%20Handoff%20Governance%EF%BC%88%E4%BA%A4%E6%8E%A5%E7%89%A9%E6%B2%BB%E7%90%86%EF%BC%89.md)。
 84 | 
 85 | ### 4.2 通用治理地位
 86 | 
 87 | `governance_class` 由 `object_type + object_status` 派生：
 88 | 
 89 | | 通用地位 | 典型映射 |
 90 | | --- | --- |
 91 | | `source` 来源 | 证据 `collected / cited` |
 92 | | `working` 工作中 | 问题 `initial / converging` |
 93 | | `unresolved` 未决 | 待澄清 `open / pending_confirmation / blocked`；待决策 `pending_decision / pending_confirmation` |
 94 | | `stable` 稳定 | 问题 `converged`；待澄清 `clarified`；约束 `effective`；待决策 `decided` |
 95 | | `historical` 历史 | 各类 `archived`、约束 `superseded`、待澄清 `closed` |
 96 | 
 97 | 映射规则必须版本化并可重算。任何服务不得直接写 `governance_class` 来绕过类型状态门禁。
 98 | 
 99 | ### 4.3 验证状态
100 | 
101 | `validation_state` 与业务状态分开：
102 | 
103 | ```text
104 | unverified / valid / warning / invalid
105 | ```
106 | 
107 | 对象可以处于 `initial + warning`，但不能因为验证失败就把业务状态写成“异常”。`invalid` 对象不得升级为稳定地位。
108 | 
109 | ## 5. 状态流转与同提交升级
110 | 
111 | 合法流转由对象治理和结构验证共同定义。状态账本补充以下规则：
112 | 
113 | 1. 每次 `object_status_changed` 必须记录原状态、新状态、来源和原因。
114 | 2. 对象进入 `effective / decided / clarified` 必须关联有效确认记录；包版本进入 `confirmed` 由独立包版本事件表达，也必须关联有效确认记录。
115 | 3. Chat 已经包含完整确认时，同一原子提交可以创建处于稳定状态的对象；约束卡不得为了经过候选态而额外持久化 `draft` 或 `pending_confirmation`。
116 | 
```

## W-GOV-001 — L3 约束卡治理边界

来源：`docs/harness/05-safety-governance/05 Object Governance（对象治理）.md:66-81`

```text
66 |   3. 交接物的"未解决问题"模块里显式列出了它。
67 |   4. AI 或用户在 Chat 中明确标注它为"阻塞继续推进"。
68 | 
69 |   系统无法确定时，一律当关键处理，不自动关闭。
70 | - 待澄清卡不得通过修改对象类型变成约束卡或待决策卡；澄清结果应创建或更新关联的结果对象，并保留原待澄清对象身份及“澄清了 / 产出为”等关系。
71 | 
72 | 类型化状态：待提出、待确认、已澄清、已阻塞、已关闭。
73 | 
74 | ## 5. 约束卡
75 | 
76 | 约束卡用于沉淀术语、字段、状态、权限、流程、计费、边界和数据口径等规则。
77 | 
78 | 治理边界：
79 | 
80 | - AI 先在 Chat 中提出约束理解；用户确认、修正或否定后，收敛部件才可以写入并显影约束卡。
81 | - 未确认的约束提议保留在 Chat；若本质上仍是信息缺口或方向选择，分别进入待澄清卡或待决策卡。
```

## W-CODE-001 — 当前 Prompt 拼接

来源：`app/canvas/service.py:1040-1129`

```text
1040 |         selected_cards_json = json.dumps([c.to_dict() for c in selected_cards], ensure_ascii=False)
1041 |         
1042 |         # 从全局内存缓存中水合材料具体内容，供协作角色直接读取文件文本
1043 |         materials_content_list = []
1044 |         try:
1045 |             from app.api.server import global_materials_cache, global_source_refs_cache
1046 |             for mid in material_ids:
1047 |                 if mid in global_materials_cache:
1048 |                     mat = global_materials_cache[mid]
1049 |                     materials_content_list.append(
1050 |                         f"--- 材料文件名: {mat['filename']} (ID: {mid}) ---\n{mat['content']}\n"
1051 |                     )
1052 |             for source_ref_id in source_ref_ids:
1053 |                 if source_ref_id in global_source_refs_cache:
1054 |                     source_ref = global_source_refs_cache[source_ref_id]
1055 |                     snapshot = source_ref.get("snapshot", {})
1056 |                     materials_content_list.append(
1057 |                         f"--- 数据引用: {source_ref.get('display_name', source_ref_id)} (ID: {source_ref_id}) ---\n"
1058 |                         f"{snapshot.get('summary', '该数据引用暂无快照摘要。')}\n"
1059 |                     )
1060 |         except Exception:
1061 |             pass
1062 |         materials_str = "\n".join(materials_content_list) if materials_content_list else "（无新引入材料内容）"
1063 | 
1064 |         for role_name in plan.roles:
1065 |             role_instruction = ""
1066 |             expected_kind = ""
1067 |             expected_mutation_type = ""
1068 | 
1069 |             if role_name == "Clarifier":
1070 |                 expected_kind = "clarification"
1071 |                 expected_mutation_type = "add_card"
1072 |                 role_instruction = "你负责发现歧义、缺失信息与冲突，并提出待澄清缺口。请深入提取出至少一个当前最需要向相关方澄清的问题（即不确定性）。"
1073 |             elif role_name == "ConstraintSteward":
1074 |                 expected_kind = "constraint"
1075 |                 expected_mutation_type = "promote_to_constraint_draft"
1076 |                 role_instruction = "你负责沉淀业务边界、状态、口径、权限和计费等限制。请深度分析提取出目前应该沉淀的规则约束草稿。"
1077 |             elif role_name == "DecisionSteward":
1078 |                 expected_kind = "decision"
1079 |                 expected_mutation_type = "create_decision_request"
1080 |                 role_instruction = "你负责识别必须由 PM 拍板的待决策项，而非单纯的信息缺失。请深度分析并生成待拍板决策卡（要给出备选方案和影响面）。"
1081 |             elif role_name == "HandoffBuilder":
1082 |                 # L3 规格已下线 HANDOFF 卡片；交接模块只生成 refresh_handoff_draft 变更。
1083 |                 expected_kind = ""
1084 |                 expected_mutation_type = "refresh_handoff_draft"
1085 |                 role_instruction = "你负责收束结构化交接物草稿。请依据用户的意图和已有的卡片结构，撰写一份结构化交接物的草稿建议。"
1086 |             else:
1087 |                 expected_kind = "evidence"
1088 |                 expected_mutation_type = "add_card"
1089 |                 role_instruction = "你负责接收新输入，编译多源材料，提取核心证据。"
1090 | 
1091 |             prompt = f"""你是一个需求分析协作 Agent，目前分配给你的角色是: "{role_name}"。
1092 | 你的职责和指导方针如下:
1093 | {role_instruction}
1094 | 
1095 | 上下文信息:
1096 | - 用户输入/对话消息: "{message}"
1097 | - 关联被选中卡片: {selected_cards_json}
1098 | - 新引入参考材料具体内容如下:
1099 | {materials_str}
1100 | 
1101 | 请基于上述上下文信息进行语义分析与智能归纳，并生成拟建议的画布卡片修改提案（必须是 JSON 格式的 mutations 列表）。
1102 | 注意：请使用以下拟建议的字段属性：
1103 | - 卡片的 kind 必须是: "{expected_kind}"
1104 | - mutations 的 mutation_type 必须是: "{expected_mutation_type}"
1105 | 
1106 | 你必须输出符合以下 JSON 格式的回复，不需要任何 Markdown 包裹或说明：
1107 | {{
1108 |   "title": "拟建议的卡片标题（15字内，要求精炼）",
1109 |   "summary": "提炼出的详细内容摘要（包含核心事实、冲突点、约束规则陈述或待拍板抉择的具体背景）"
1110 | }}
1111 | """
1112 |             try:
1113 |                 result = self.llm.invoke(
1114 |                     role=role_name,
1115 |                     prompt=prompt,
1116 |                     context={
1117 |                         "title": f"Agent {role_name}",
1118 |                         "goal": "Generate canvas mutation proposal",
1119 |                         "model": model,
1120 |                     }
1121 |                 )
1122 |                 raw_content = result.content.strip()
1123 |                 match = re.search(r"\{.*\}", raw_content, re.DOTALL)
1124 |                 if match:
1125 |                     raw_content = match.group(0)
1126 | 
1127 |                 card_data = json.loads(raw_content)
1128 |                 title = card_data["title"]
1129 |                 summary = card_data["summary"]
```

## W-CODE-002 — Supervisor 非真实 subagent 调度

来源：`app/canvas/agent/supervisor.py:1-5`

```text
1 | """EvoCanvas Canvas Supervisor。
2 | 
3 | 当前仅负责基于用户输入做意图识别与角色规划，
4 | 不承担实际 subagent 调度与 mutation 合并。
5 | """
```

## W-CODE-003 — Supervisor 上下文拼接

来源：`app/canvas/agent/supervisor.py:45-136`

```text
 45 |     def _recognize_and_plan_with_llm(
 46 |         self, workspace_context: Dict[str, Any], message: str
 47 |     ) -> CanvasTurnPlan | None:
 48 |         import re
 49 |         import json
 50 | 
 51 |         # 从全局内存缓存中水合材料具体内容，供大模型分析
 52 |         materials_content_list = []
 53 |         try:
 54 |             from app.api.server import global_materials_cache, global_source_refs_cache
 55 |             for mid in workspace_context.get("material_ids", []):
 56 |                 if mid in global_materials_cache:
 57 |                     mat = global_materials_cache[mid]
 58 |                     materials_content_list.append(
 59 |                         f"--- 模拟材料文件: {mat['filename']} (ID: {mid}) ---\n{mat['content']}\n"
 60 |                     )
 61 |             for source_ref_id in workspace_context.get("source_ref_ids", []):
 62 |                 if source_ref_id in global_source_refs_cache:
 63 |                     source_ref = global_source_refs_cache[source_ref_id]
 64 |                     snapshot = source_ref.get("snapshot", {})
 65 |                     materials_content_list.append(
 66 |                         f"--- 结构化数据引用: {source_ref.get('display_name', source_ref_id)} (ID: {source_ref_id}) ---\n"
 67 |                         f"{snapshot.get('summary', '暂无快照摘要')}\n"
 68 |                     )
 69 |         except Exception:
 70 |             pass
 71 |         materials_str = "\n".join(materials_content_list) if materials_content_list else "（无新引入材料内容）"
 72 | 
 73 |         prompt = f"""你是 EvoCanvas 的意图路由 Supervisor。你的唯一职责是分析用户输入，判断意图类型，并规划需要激活的协作角色。
 74 | 
 75 | # 可用角色及职责
 76 | 
 77 | - InputCompiler: 接收新输入，编译多源材料（会议纪要、聊天、需求文档），提取证据卡和问题定义卡。
 78 | - Clarifier: 发现歧义、缺失信息与冲突，提出待澄清卡。
 79 | - ConstraintSteward: 沉淀稳定业务规则、术语、数据口径等约束卡。
 80 | - DecisionSteward: 识别必须由 PM 拍板的待决策卡。
 81 | - OptionBuilder: 接收方案建议并生成方案候选卡。
 82 | - HandoffBuilder: 编写与收束结构化交接物草稿卡。
 83 | 
 84 | # 路由决策规则（按优先级顺序判断）
 85 | 
 86 | 1. 有新材料输入时（用户粘贴了文本、上传了文件、引入了参考数据）：
 87 |    必须路由到 input_compilation + InputCompiler。
 88 |    如果材料中同时存在分歧或不确定性，追加 clarification + Clarifier。
 89 | 
 90 | 2. 用户在追问或质疑已有内容时（"为什么"、"不确定"、"这里有问题"）：
 91 |    路由到 clarification + Clarifier。
 92 | 
 93 | 3. 用户在陈述规则、边界或约束条件时（"必须"、"不能"、"规定是"）：
 94 |    路由到 constraint + ConstraintSteward。
 95 | 
 96 | 4. 用户面临方案选择或要求拍板时（"A 还是 B"、"你来决定"、"哪个更好"）：
 97 |    路由到 decision + DecisionSteward。
 98 | 
 99 | 5. 用户在讨论或对比备选方案时（"如果…会怎样"、"对比一下"、"有什么选择"）：
100 |    路由到 option + OptionBuilder。
101 | 
102 | 6. 用户要求整理输出或生成交接物时（"整理成文档"、"输出 PRD"、"生成报告"）：
103 |    路由到 handoff + HandoffBuilder。
104 | 
105 | 7. 意图不明确时：默认路由到 input_compilation + InputCompiler。
106 | 
107 | # 约束
108 | 
109 | - NEVER 在有新背景输入时跳过 InputCompiler 直接路由到后续阶段。
110 | - 混合意图用 "+" 连接（如 "input_compilation+clarification"），角色用列表。
111 | - 不要返回任何解释，只返回 JSON。
112 | 
113 | # 当前输入
114 | 
115 | 用户消息: "{message}"
116 | 
117 | 工作区已选中的卡片: {workspace_context.get("selected_cards", [])}
118 | 
119 | 新引入参考材料内容:
120 | {materials_str}
121 | 
122 | # 输出格式
123 | 
124 | 必须输出 JSON，不要包含 Markdown 标记或其他文字：
125 | {{"intent": "意图标识", "roles": ["角色1", "角色2"]}}
126 | """
127 |         try:
128 |             # 调用真实的 llm.invoke
129 |             result = self.llm.invoke(
130 |                 role="supervisor",
131 |                 prompt=prompt,
132 |                 context={
133 |                     "title": "Intent Routing",
134 |                     "goal": "Route user message to proper roles",
135 |                     "model": workspace_context.get("model"),
136 |                 }
```

## W-CODE-004 — ToolSpec 声明

来源：`app/core/tools.py:16-41`

```text
16 | @dataclass
17 | class ToolSpec:
18 |     """工具规格说明类，声明受控工具的元数据、输入输出 Schema 以及副作用和权限要求。
19 | 
20 |     Attributes:
21 |         name: 工具的唯一名称（例如 'artifact.write'）。
22 |         version: 工具版本号。
23 |         description: 工具用途及行为功能描述。
24 |         input_schema: 输入参数的 JSON Schema 校验规范字典。
25 |         output_schema: 返回结果数据的 JSON Schema 校验规范字典。
26 |         side_effect: 副作用说明（如 'write', 'read', 'network'）。
27 |         required_permissions: 执行此工具所需的特别权限列表。
28 |         timeout_seconds: 工具执行超时时间（秒）。
29 |         failure_semantics: 工具失败时的语义降级处理说明。
30 |         event_semantics: 声明工具执行时产生何种结构化审计事件。
31 |     """
32 |     name: str
33 |     version: str
34 |     description: str
35 |     input_schema: Dict[str, Any]
36 |     output_schema: Dict[str, Any]
37 |     side_effect: str
38 |     required_permissions: List[str] = field(default_factory=list)
39 |     timeout_seconds: int = 30
40 |     failure_semantics: str = "Return ToolResult.status='failed' with a structured DomainError."
41 |     event_semantics: str = "write/external tools emit tool.call.* structured events."
```

## W-CODE-005 — ToolPolicy 与审批字段

来源：`app/core/tools.py:99-152`

```text
 99 | class ToolPolicyRule:
100 |     """工具授权策略规则，定义了在特定步骤下特定角色能使用或不能使用的工具列表。
101 | 
102 |     Attributes:
103 |         role: 适用的角色名称（支持通配符 '*'）。
104 |         step_id: 适用的步骤 ID（支持通配符 '*'）。
105 |         allowed_tools: 允许调用的工具名称列表（支持通配符 '*' 匹配全部）。
106 |         denied_tools: 明确禁止调用的工具名称列表。
107 |         max_calls_per_step: 单个步骤内允许调用的最大次数上限，默认 20，防范 LLM 陷入无限工具调用死循环。
108 |         require_user_approval_for: 需要人类在执行前二次审批确认的工具列表。
109 |     """
110 |     role: str
111 |     step_id: str
112 |     allowed_tools: List[str]
113 |     denied_tools: List[str] = field(default_factory=list)
114 |     max_calls_per_step: int = 20
115 |     require_user_approval_for: List[str] = field(default_factory=list)
116 | 
117 | 
118 | @dataclass
119 | class ToolPolicy:
120 |     """完整的任务工具治理授权策略，包含特定任务类型下的所有过滤规则集。
121 | 
122 |     Attributes:
123 |         task_type: 任务/Playbook 类型名称。
124 |         rules: 包含的授权规则规则集。
125 |     """
126 |     task_type: str
127 |     rules: List[ToolPolicyRule] = field(default_factory=list)
128 | 
129 |     def is_allowed(self, role: str, step_id: str, tool_name: str) -> bool:
130 |         """检查特定角色在特定步骤下调用指定工具是否被允许。
131 | 
132 |         Args:
133 |             role: 调用者的角色名称。
134 |             step_id: 当前所处的步骤 ID。
135 |             tool_name: 需要调用的受控工具名称。
136 | 
137 |         Returns:
138 |             bool: 允许调用返回 True，否则返回 False（被拒绝）。
139 |         """
140 |         for rule in self.rules:
141 |             # 检查角色是否匹配，支持通配符
142 |             role_matches = rule.role in {role, "*"}
143 |             step_matches = rule.step_id in {step_id, "*"}
144 |             if not (role_matches and step_matches):
145 |                 continue
146 |             # 明确拒绝黑名单工具
147 |             if tool_name in rule.denied_tools:
148 |                 return False
149 |             # 检查是否包含在白名单允许工具列表中
150 |             if "*" in rule.allowed_tools or tool_name in rule.allowed_tools:
151 |                 return True
152 |         return False
```

## W-CODE-006 — 当前工具执行链

来源：`app/services/tool_service.py:194-240`

```text
194 |     def invoke(self, definition: TaskDefinition, context: TaskContext, call: ToolCall) -> ToolResult:
195 |         """安全受控地调用一个指定的工具。
196 | 
197 |         执行白名单检查（ToolPolicy）、沙箱参数安全审核（防目录遍历、限制毁灭性命令等），
198 |         自动记录审计事件（开始、完成/失败/拒绝），并在异常时安全回退。
199 | 
200 |         Args:
201 |             definition: 任务定义，包含 tool_policy 权限白名单。
202 |             context: 任务上下文，用于标识任务和为处理器提供运行时属性。
203 |             call: 工具调用描述，包含工具名、调用 ID、代理角色及入参。
204 | 
205 |         Returns:
206 |             ToolResult: 工具执行的结果包装，包含状态、产出物及数据。
207 |         """
208 |         spec = self.specs.get(call.tool_name)
209 |         if not spec:
210 |             return ToolResult(call_id=call.id, status="failed", error=DomainError("tool.unknown", f"Unknown tool: {call.tool_name}"))
211 |             
212 |         # 1. 严格检查 IAM & Sandbox 权限策略白名单
213 |         if not definition.tool_policy.is_allowed(call.agent_role, call.step_id, call.tool_name):
214 |             result = ToolResult(call_id=call.id, status="denied", error=DomainError("tool.denied", f"{call.agent_role} cannot call {call.tool_name} in {call.step_id}"))
215 |             self._emit_tool_event(context.task_id, call, "tool.call.denied", result)
216 |             return result
217 |             
218 |         # 2. 检查路径遍历参数，拦截恶意系统路径
219 |         for k, v in call.arguments.items():
220 |             if isinstance(v, str) and ("../" in v or v.startswith("/etc") or v.startswith("/bin")):
221 |                 result = ToolResult(call_id=call.id, status="denied", error=DomainError("sandbox.violation", f"Path traversal or restricted system path detected in arguments."))
222 |                 self._emit_tool_event(context.task_id, call, "tool.call.denied", result)
223 |                 return result
224 |             # 3. 拦截命令行执行工具中的高危指令（破坏性命令）
225 |             if call.tool_name == "run_command" and isinstance(v, str) and any(cmd in v for cmd in ["rm -rf", "mkfs", "chmod"]):
226 |                 result = ToolResult(call_id=call.id, status="denied", error=DomainError("sandbox.violation", f"Destructive command execution is prohibited."))
227 |                 self._emit_tool_event(context.task_id, call, "tool.call.denied", result)
228 |                 return result
229 | 
230 |         # 4. 发布工具执行开始审计事件
231 |         self._emit_tool_event(context.task_id, call, "tool.call.started", None)
232 |         try:
233 |             result = self.handlers[call.tool_name](context, call)
234 |         except Exception as exc:  # pragma: no cover - defensive wrapper
235 |             result = ToolResult(call_id=call.id, status="failed", error=DomainError("tool.failed", str(exc)))
236 |         
237 |         # 5. 发布工具执行完成/失败审计事件
238 |         event_type = "tool.call.completed" if result.status == "succeeded" else "tool.call.failed"
239 |         self._emit_tool_event(context.task_id, call, event_type, result)
240 |         return result
```

## W-CODE-007 — 有界 AgentRuntime

来源：`app/services/agent_runtime/runtime.py:48-180`

```text
 48 |         self.llm = llm
 49 |         self.tool_service = tool_service
 50 | 
 51 |     def run_json_session(
 52 |         self,
 53 |         *,
 54 |         session: AgentSession,
 55 |         prompt: str,
 56 |         context: Optional[Dict[str, Any]] = None,
 57 |         required_keys: Optional[Iterable[str]] = None,
 58 |         task_definition: Optional[TaskDefinition] = None,
 59 |         task_context: Optional[TaskContext] = None,
 60 |     ) -> AgentRunResult:
 61 |         if not self.llm:
 62 |             error = DomainError(
 63 |                 "agent_runtime.llm_unavailable",
 64 |                 "AgentRuntime requires an LLM port for this session.",
 65 |                 {"session_id": session.session_id, "step_id": session.step_id},
 66 |             )
 67 |             session.set_degradation_reason(error.message)
 68 |             return AgentRunResult.blocked(
 69 |                 session=session,
 70 |                 content="",
 71 |                 error=error,
 72 |                 structured={"fallback_reason": error.message},
 73 |                 summary="AgentSession blocked before the runtime could start.",
 74 |             )
 75 | 
 76 |         session.state.status = AgentSessionStatus.RUNNING
 77 |         required = list(required_keys or [])
 78 |         last_error = ""
 79 |         last_content = ""
 80 |         tool_messages: List[Dict[str, Any]] = []
 81 |         used_tools: List[str] = []
 82 |         session.set_runtime_contract(
 83 |             self._allowed_tool_names_for_session(session, task_definition),
 84 |             required,
 85 |             {
 86 |                 "input_context_keys": sorted((context or session.input_context).keys()),
 87 |                 "max_iterations": session.max_iterations,
 88 |                 "estimated_tokens": max(1, len(json.dumps(context or session.input_context, ensure_ascii=False, default=str)) // 4),
 89 |             },
 90 |         )
 91 | 
 92 |         for iteration in range(1, session.max_iterations + 1):
 93 |             current_prompt = prompt
 94 |             if iteration > 1 and last_error:
 95 |                 current_prompt += (
 96 |                     "\n\n[SYSTEM ALERT]: Previous AgentSession turn failed schema validation: "
 97 |                     f"{last_error}. Return raw JSON only."
 98 |                 )
 99 | 
100 |             response = self._invoke_model(
101 |                 session=session,
102 |                 prompt=current_prompt,
103 |                 context=context or session.input_context,
104 |                 task_definition=task_definition,
105 |                 tool_messages=tool_messages,
106 |             )
107 |             raw_content, structured_response = self._normalize_llm_response(response)
108 |             last_content = raw_content
109 |             session.record_turn(
110 |                 AgentTurn(
111 |                     iteration=iteration,
112 |                     role=session.agent_role,
113 |                     prompt_summary=current_prompt[:160],
114 |                     response_summary=raw_content[:160],
115 |                     raw_content=raw_content,
116 |                 )
117 |             )
118 | 
119 |             try:
120 |                 structured = structured_response or json.loads(extract_json_from_text(raw_content))
121 |                 self._apply_agenda_operations(session, structured)
122 |                 tool_calls = self._extract_tool_calls(structured)
123 |                 if isinstance(tool_calls, list) and tool_calls:
124 |                     tool_error, tool_messages, newly_used_tools = self._execute_tool_calls(
125 |                         session=session,
126 |                         tool_calls=tool_calls,
127 |                         task_definition=task_definition,
128 |                         task_context=task_context,
129 |                     )
130 |                     for tool_name in newly_used_tools:
131 |                         if tool_name not in used_tools:
132 |                             used_tools.append(tool_name)
133 |                     if tool_error:
134 |                         session.set_degradation_reason(tool_error.message)
135 |                         return AgentRunResult.blocked(
136 |                             session=session,
137 |                             content=raw_content,
138 |                             error=tool_error,
139 |                             structured={"fallback_reason": tool_error.message, "fallback_role": session.agent_role},
140 |                             summary="AgentSession blocked during controlled tool execution.",
141 |                             used_tools=used_tools,
142 |                             schema_errors=session.state.schema_errors,
143 |                         )
144 |                     continue
145 | 
146 |                 missing = [key for key in required if key not in structured or structured.get(key) in (None, "")]
147 |                 if missing:
148 |                     raise ValueError(f"missing required keys: {', '.join(missing)}")
149 |                 session.record_observation(AgentObservation(kind="schema", summary="valid json", data={"required_keys": required}))
150 |                 session.set_final_output(structured, summary=self._summarize_structured_output(structured))
151 |                 return AgentRunResult.succeeded(
152 |                     session=session,
153 |                     content=raw_content,
154 |                     structured=structured,
155 |                     summary="AgentSession completed with schema-valid output.",
156 |                     used_tools=used_tools,
157 |                     schema_errors=session.state.schema_errors,
158 |                 )
159 |             except Exception as exc:
160 |                 last_error = str(exc)
161 |                 session.record_schema_error(last_error)
162 |                 session.record_observation(
163 |                     AgentObservation(
164 |                         kind="schema_error",
165 |                         summary=last_error,
166 |                         data={"iteration": iteration, "required_keys": required},
167 |                     )
168 |                 )
169 | 
170 |         error = DomainError(
171 |             "agent_runtime.schema_validation_failed",
172 |             "AgentSession exhausted bounded JSON validation attempts.",
173 |             {"session_id": session.session_id, "step_id": session.step_id, "last_error": last_error},
174 |         )
175 |         session.set_degradation_reason(last_error)
176 |         return AgentRunResult.blocked(
177 |             session=session,
178 |             content=last_content,
179 |             error=error,
180 |             structured={"fallback_reason": last_error, "fallback_role": session.agent_role},
```

## W-CODE-008 — Subagent 限额

来源：`app/services/subagent_service.py:33-46`

```text
33 | class SubagentService:
34 |     """Runs bounded internal subagents under tight governance."""
35 | 
36 |     READ_ONLY_TOOLS = {
37 |         "material.read",
38 |         "material.parse",
39 |         "knowledge.retrieve",
40 |         "artifact.read",
41 |         "format.validate",
42 |     }
43 |     MAX_HELPER_DEPTH = 2
44 |     MAX_PARALLEL_HELPERS = 2
45 |     MAX_FORMAL_SUBTASKS = 3
46 |     MAX_CONTEXT_SHARE = 0.25
```

## W-CODE-009 — 隔离运行与有界并发

来源：`app/services/subagent_service.py:87-199`

```text
 87 |         helper_definition = self._build_helper_definition(task_definition, request)
 88 |         helper_runtime = AgentRuntime(llm=self.llm, tool_service=self.tool_service)
 89 |         helper_session = AgentSession(
 90 |             task_id=parent_session.task_id,
 91 |             step_id=f"{parent_session.step_id}__helper",
 92 |             agent_role=f"{parent_session.agent_role}Helper",
 93 |             goal=request.goal,
 94 |             input_context={
 95 |                 "task_slice": request.task_slice,
 96 |                 "input_refs": request.input_refs,
 97 |                 "input_excerpt": request.input_excerpt,
 98 |                 "parent_session_id": parent_session.session_id,
 99 |             },
100 |             max_iterations=request.budget.max_iterations,
101 |         )
102 |         prompt = self._build_helper_prompt(request)
103 |         run_result = helper_runtime.run_json_session(
104 |             session=helper_session,
105 |             prompt=prompt,
106 |             context={
107 |                 "task_slice": request.task_slice,
108 |                 "input_excerpt": request.input_excerpt,
109 |             },
110 |             required_keys=list(request.output_schema.keys()),
111 |             task_definition=helper_definition,
112 |             task_context=task_context,
113 |         )
114 | 
115 |         confidence = str(run_result.structured.get("confidence") or ("low" if run_result.degraded else "medium"))
116 |         run.result = SubagentResult(
117 |             summary=str(run_result.structured.get("summary") or run_result.summary or helper_session.state.final_output_summary),
118 |             structured_output=run_result.structured,
119 |             evidence_refs=list(run_result.structured.get("evidence_refs", [])),
120 |             used_tools=list(run_result.used_tools),
121 |             confidence=confidence,
122 |             degraded=run_result.degraded,
123 |             degradation_reason=run_result.error.message if run_result.error else run_result.structured.get("degradation_reason", ""),
124 |         )
125 |         run.error = run_result.error
126 |         if run_result.status.value == "succeeded":
127 |             run.status = SubagentRunStatus.SUCCEEDED
128 |             self._emit_event(task_context.task_id, "subagent.run.completed", run, {"used_tools": run_result.used_tools})
129 |         elif run_result.status.value == "blocked":
130 |             run.status = SubagentRunStatus.BLOCKED
131 |             self._emit_event(
132 |                 task_context.task_id,
133 |                 "subagent.run.blocked",
134 |                 run,
135 |                 {"degradation_reason": run.result.degradation_reason, "used_tools": run_result.used_tools},
136 |             )
137 |         else:
138 |             run.status = SubagentRunStatus.FAILED
139 |             self._emit_event(task_context.task_id, "subagent.run.failed", run)
140 |         run.touch()
141 |         parent_session.record_helper_result(run)
142 |         return run
143 | 
144 |     def run_helpers(
145 |         self,
146 |         *,
147 |         parent_session: AgentSession,
148 |         requests: List[SubagentSpawnRequest],
149 |         task_definition: TaskDefinition,
150 |         task_context: TaskContext,
151 |     ) -> List[SubagentRun]:
152 |         """Execute one or more session-level helpers with bounded parallelism."""
153 |         mode = self.decide_helper_execution_mode(parent_session, requests)
154 |         if mode == ExecutionMode.PARALLEL_HELPERS:
155 |             with ThreadPoolExecutor(max_workers=min(len(requests), self.MAX_PARALLEL_HELPERS)) as executor:
156 |                 futures = [
157 |                     executor.submit(
158 |                         self.run_helper,
159 |                         parent_session=parent_session,
160 |                         request=request,
161 |                         task_definition=task_definition,
162 |                         task_context=task_context,
163 |                         execution_mode=mode,
164 |                     )
165 |                     for request in requests
166 |                 ]
167 |                 runs = [future.result() for future in futures]
168 |         else:
169 |             runs = [
170 |                 self.run_helper(
171 |                     parent_session=parent_session,
172 |                     request=request,
173 |                     task_definition=task_definition,
174 |                     task_context=task_context,
175 |                     execution_mode=mode,
176 |                 )
177 |                 for request in requests
178 |             ]
179 | 
180 |         return runs
181 | 
182 |     def decide_helper_execution_mode(self, parent_session: AgentSession, requests: List[SubagentSpawnRequest]) -> ExecutionMode:
183 |         """Choose serial vs bounded parallel helper execution."""
184 |         if len(requests) <= 1:
185 |             return ExecutionMode.SERIAL
186 |         if len(requests) > self.MAX_PARALLEL_HELPERS:
187 |             return ExecutionMode.SERIAL
188 |         if parent_session.state.helper_runs and len(parent_session.state.helper_runs) + len(requests) > self.MAX_PARALLEL_HELPERS:
189 |             return ExecutionMode.SERIAL
190 |         for request in requests:
191 |             if request.scope != SubagentScope.SESSION_HELPER:
192 |                 return ExecutionMode.SERIAL
193 |             if request.depth >= self.MAX_HELPER_DEPTH:
194 |                 return ExecutionMode.SERIAL
195 |             if not request.output_schema:
196 |                 return ExecutionMode.SERIAL
197 |             if self._estimate_token_count(request.input_excerpt) > request.budget.max_input_tokens:
198 |                 return ExecutionMode.SERIAL
199 |         return ExecutionMode.PARALLEL_HELPERS
```

## W-CODE-010 — 包版本提交顺序

来源：`app/canvas/repository.py:267-321`

```text
267 |     def commit_package_version(
268 |         self,
269 |         workspace_id: str,
270 |         package: Package,
271 |         version: PackageVersion,
272 |         events: Sequence[LedgerEvent],
273 |         confirmation: Optional[ConfirmationRecord] = None,
274 |     ) -> Package:
275 |         """原子可见地提交一个新的包版本、账本事件和可选确认记录。
276 | 
277 |         版本正文、确认记录和账本先写入不可变位置；最后原子更新包根指针，
278 |         因而读取方只能看到上一个完整版本或这个完整版本。相同 operation_id
279 |         在同一工作区内幂等返回既有包，不会重复推进 state_version 或追加事件。
280 |         """
281 | 
282 |         if package.workspace_id != workspace_id or version.package_id != package.package_id:
283 |             raise ValueError("package commit workspace/package identity mismatch")
284 |         if not version.operation_id:
285 |             raise ValueError("package version commit requires operation_id")
286 | 
287 |         with self._workspace_lock(workspace_id):
288 |             if self.has_operation_id(workspace_id, version.operation_id):
289 |                 existing = self.load_package(workspace_id, package.package_id)
290 |                 if existing is None:
291 |                     raise RuntimeError("ledger contains operation without package root")
292 |                 return existing
293 | 
294 |             previous = self.load_package(workspace_id, package.package_id)
295 |             expected_version = (previous.current_version if previous is not None else 0) + 1
296 |             expected_state_version = (previous.state_version if previous is not None else 0) + 1
297 |             if version.package_version != expected_version:
298 |                 raise ValueError(
299 |                     f"expected package version {expected_version}, got {version.package_version}"
300 |                 )
301 |             if version.state_version != expected_state_version:
302 |                 raise ValueError(
303 |                     f"expected state version {expected_state_version}, got {version.state_version}"
304 |                 )
305 |             if version.parent_version != (previous.current_version if previous else None):
306 |                 raise ValueError("package version parent pointer does not match current package pointer")
307 |             if any(event.package_id != package.package_id for event in events):
308 |                 raise ValueError("ledger event package_id does not match committed package")
309 | 
310 |             package.current_version = version.package_version
311 |             package.state_version = version.state_version
312 |             if version.initial_governance_status == InitialGovernanceStatus.CONFIRMED:
313 |                 package.latest_confirmed_version = version.package_version
314 | 
315 |             # 包根指针是提交可见性的最后一步，之前的写入不会覆盖任何历史正文。
316 |             self.save_package_version(workspace_id, version)
317 |             if confirmation is not None:
318 |                 self.save_confirmation_record(workspace_id, confirmation)
319 |             self._append_ledger_events_atomically(workspace_id, events)
320 |             self.save_package(workspace_id, package)
321 |             return package
```

## W-CODE-011 — 当前同步 start_turn 主链

来源：`app/canvas/service.py:178-390`

```text
178 |     def start_turn(
179 |         self,
180 |         workspace_id: str,
181 |         message: str,
182 |         selected_card_ids: List[str],
183 |         material_ids: List[str],
184 |         source_ref_ids: Optional[List[str]] = None,
185 |         mode: Optional[str] = None,
186 |         model: Optional[str] = None,
187 |     ) -> Dict[str, Any]:
188 |         del mode
189 |         source_ref_ids = list(source_ref_ids or [])
190 | 
191 |         turn_id = f"turn_{uuid4().hex[:12]}"
192 |         workspace = self._begin_turn(workspace_id, turn_id)
193 |         try:
194 |             user_message = self.repository.append_chat_message(
195 |                 workspace_id,
196 |                 {
197 |                     "message_id": f"msg_{uuid4().hex[:12]}",
198 |                     "role": "user",
199 |                     "content": message,
200 |                     "turn_id": turn_id,
201 |                     "created_at": utc_now_iso(),
202 |                 },
203 |             )
204 |             pending_proposal = self._latest_chat_confirmation_proposal(workspace_id)
205 |             if pending_proposal is not None and self._is_explicit_confirmation(message):
206 |                 return self._apply_chat_confirmation(
207 |                     workspace,
208 |                     turn_id,
209 |                     pending_proposal,
210 |                     user_message_ref=str(user_message["message_id"]),
211 |                 )
212 |             self._publish_event(
213 |                 workspace_id,
214 |                 "canvas.turn.started",
215 |                 {
216 |                     "workspace_id": workspace_id,
217 |                     "turn_id": turn_id,
218 |                     "proposal_id": None,
219 |                     "active_turn": self._serialize_active_turn(workspace),
220 |                 },
221 |                 status="running",
222 |             )
223 |             existing_cards = self.repository.load_cards(workspace_id)
224 |             self._validate_selected_cards(selected_card_ids, existing_cards)
225 | 
226 |             selected_cards_info = []
227 |             card_map = {c.card_id: c for c in existing_cards}
228 |             for cid in selected_card_ids:
229 |                 if cid in card_map:
230 |                     card = card_map[cid]
231 |                     selected_cards_info.append({
232 |                         "card_id": card.card_id,
233 |                         "kind": card.kind.value if hasattr(card.kind, "value") else str(card.kind),
234 |                         "status": card.status,
235 |                     })
236 | 
237 |             # 映射前端发送的模型标识符至后端实际的 API model 名称
238 |             resolved_model = None
239 |             if model:
240 |                 model_lower = model.lower()
241 |                 if "deepseek" in model_lower:
242 |                     resolved_model = "deepseek-chat"
243 |                 elif "gemini" in model_lower:
244 |                     resolved_model = "gemini-1.5-flash"
245 | 
246 |             plan = self.supervisor.recognize_and_plan(
247 |                 workspace_context={
248 |                     "workspace_id": workspace_id,
249 |                     "selected_card_ids": list(selected_card_ids),
250 |                     "selected_cards": selected_cards_info,
251 |                     "material_ids": list(material_ids),
252 |                     "source_ref_ids": list(source_ref_ids),
253 |                     "model": resolved_model,
254 |                 },
255 |                 message=message,
256 |             )
257 |             proposal = self._build_mutation_proposal(
258 |                 workspace,
259 |                 turn_id,
260 |                 message,
261 |                 plan,
262 |                 existing_cards=existing_cards,
263 |                 selected_card_ids=selected_card_ids,
264 |                 material_ids=material_ids,
265 |                 source_ref_ids=source_ref_ids,
266 |                 model=resolved_model,
267 |             )
268 |             proposal.metadata["intent"] = plan.intent
269 |             proposal.metadata["roles"] = list(plan.roles)
270 |             assistant_message = self.repository.append_chat_message(
271 |                 workspace_id,
272 |                 {
273 |                     "message_id": f"msg_{uuid4().hex[:12]}",
274 |                     "role": "assistant",
275 |                     "content": self._proposal_message_content(proposal),
276 |                     "turn_id": turn_id,
277 |                     "created_at": utc_now_iso(),
278 |                 },
279 |             )
280 |             proposal.metadata["assistant_message_ref"] = assistant_message["message_id"]
281 |             proposal.metadata["verification_receipt"] = verify_mutation_proposal(
282 |                 proposal, intent=plan.intent, existing_cards=existing_cards
283 |             )
284 |             self._publish_event(
285 |                 workspace_id,
286 |                 "canvas.mutation.proposed",
287 |                 self._proposal_event_payload(
288 |                     workspace_id=workspace_id,
289 |                     turn_id=turn_id,
290 |                     proposal=proposal,
291 |                     intent=plan.intent,
292 |                     roles=list(plan.roles),
293 |                     result_action="proposed",
294 |                     active_turn=self._serialize_active_turn(workspace),
295 |                 ),
296 |                 status="proposed",
297 |             )
298 |             outcome = self.governance.classify(proposal, existing_cards=existing_cards)
299 |             apply_turn_runtime_state(
300 |                 workspace,
301 |                 intent=plan.intent,
302 |                 proposal=proposal,
303 |                 result_action=outcome.action,
304 |                 cards=existing_cards,
305 |                 pending_gate_ids=[],
306 |                 unresolved_issue_ids=unresolved_issue_ids_from_cards(existing_cards),
307 |             )
308 |             self.repository.save_workspace(workspace)
309 |             self.repository.append_proposal_history(workspace_id, proposal)
310 | 
311 |             if outcome.action == "auto_apply":
312 |                 self._apply_proposal(workspace, proposal)
313 |                 # 应用提案后，重新加载最新的卡片并再次更新运行时元数据以同步状态账本
314 |                 updated_cards = self.repository.load_cards(workspace_id)
315 |                 apply_turn_runtime_state(
316 |                     workspace,
317 |                     intent=plan.intent,
318 |                     proposal=proposal,
319 |                     result_action=outcome.action,
320 |                     cards=updated_cards,
321 |                     pending_gate_ids=[],
322 |                     unresolved_issue_ids=unresolved_issue_ids_from_cards(updated_cards),
323 |                 )
324 |                 self.repository.save_workspace(workspace)
325 |             elif outcome.action == "awaiting_chat_confirmation":
326 |                 # 提议已记录为普通 Chat 消息，下一条用户消息可确认、否定或修正。
327 |                 pass
328 |             else:
329 |                 # 验证失败情况 (downgrade_to_proposal 或 awaiting_clarification)
330 |                 # 不应用提案，也不用挂起，回合由于错误直接结束
331 |                 pass
332 | 
333 |             event_type = "canvas.mutation.applied"
334 |             if outcome.action == "awaiting_chat_confirmation":
335 |                 event_type = "canvas.chat_confirmation.requested"
336 |             elif outcome.action in {"downgrade_to_proposal", "awaiting_clarification"}:
337 |                 event_type = "canvas.mutation.failed"
338 | 
339 |             self._publish_event(
340 |                 workspace_id,
341 |                 event_type,
342 |                 self._proposal_event_payload(
343 |                     workspace_id=workspace_id,
344 |                     turn_id=turn_id,
345 |                     proposal=proposal,
346 |                     intent=plan.intent,
347 |                     roles=list(plan.roles),
348 |                     result_action=outcome.action,
349 |                     active_turn=self._serialize_active_turn(self.get_workspace(workspace_id)),
350 |                 ),
351 |                 status=proposal.status.value,
352 |             )
353 |             self._finish_turn(workspace_id, turn_id)
354 |             self._publish_event(
355 |                 workspace_id,
356 |                 "canvas.turn.completed",
357 |                 {
358 |                     "workspace_id": workspace_id,
359 |                     "turn_id": turn_id,
360 |                     "proposal_id": proposal.proposal_id,
361 |                     "result_action": outcome.action,
362 |                     "active_turn": None,
363 |                 },
364 |                 status="completed",
365 |             )
366 |             return {
367 |                 "turn_id": turn_id,
368 |                 "workspace_id": workspace_id,
369 |                 "proposal_id": proposal.proposal_id,
370 |                 "action": outcome.action,
371 |                 "risk_level": outcome.risk_level.value,
372 |                 "intent": plan.intent,
373 |                 "roles": list(plan.roles),
374 |             }
375 |         except Exception as exc:
376 |             self._finish_turn(workspace_id, turn_id)
377 |             self._publish_event(
378 |                 workspace_id,
379 |                 "canvas.turn.failed",
380 |                 {
381 |                     "workspace_id": workspace_id,
382 |                     "turn_id": turn_id,
383 |                     "proposal_id": None,
384 |                     "result_action": "failed",
385 |                     "active_turn": None,
386 |                     "error": str(exc),
387 |                 },
388 |                 status="failed",
389 |             )
390 |             raise
```

## W-CODE-012 — 当前确认识别与记录

来源：`app/canvas/service.py:1543-1637`

```text
1543 |     def _latest_chat_confirmation_proposal(
1544 |         self,
1545 |         workspace_id: str,
1546 |     ) -> Optional[CanvasMutationProposal]:
1547 |         """返回尚待普通 Chat 明确确认的最新高影响提议。
1548 | 
1549 |         L3 规格允许两条确认路径：Assistant 提议后用户确认，以及用户直接陈述。
1550 |         因此 proposal 可以没有 assistant_message_ref（直接陈述路径），
1551 |         只要有 awaiting_chat_confirmation 标记即视为待确认。
1552 |         """
1553 | 
1554 |         for proposal in reversed(self.repository.load_proposal_history(workspace_id)):
1555 |             if (
1556 |                 proposal.status == CanvasMutationStatus.PENDING_CONFIRMATION
1557 |                 and proposal.metadata.get("awaiting_chat_confirmation")
1558 |             ):
1559 |                 return proposal
1560 |         return None
1561 | 
1562 |     @staticmethod
1563 |     def _is_explicit_confirmation(message: str) -> bool:
1564 |         """识别当前回合是否给出明确同意，而非把模糊表达误判为确认。"""
1565 | 
1566 |         normalized = "".join(message.strip().lower().split())
1567 |         if any(token in normalized for token in ("不确认", "不同意", "拒绝", "再看看", "先不要")):
1568 |             return False
1569 |         return any(token in normalized for token in ("确认", "同意", "按这个执行", "就这么定", "可以生效"))
1570 | 
1571 |     @staticmethod
1572 |     def _proposal_message_content(proposal: CanvasMutationProposal) -> str:
1573 |         """为可追溯确认保存助手实际提出的结构化变更摘要。"""
1574 | 
1575 |         items = []
1576 |         for mutation in proposal.mutations:
1577 |             card = dict(mutation.payload.get("card", {}))
1578 |             title = str(card.get("title", mutation.target_id)).strip()
1579 |             mutation_type = str(mutation.metadata.get("mutation_type", mutation.action.value))
1580 |             items.append(f"{mutation_type}: {title}")
1581 |         return "；".join(items) or "本轮没有可应用的结构化变更。"
1582 | 
1583 |     def _apply_chat_confirmation(
1584 |         self,
1585 |         workspace: CanvasWorkspace,
1586 |         turn_id: str,
1587 |         proposal: CanvasMutationProposal,
1588 |         *,
1589 |         user_message_ref: str,
1590 |     ) -> Dict[str, Any]:
1591 |         """把用户在普通 Chat 中的明确确认写为记录并提交对应包版本。"""
1592 | 
1593 |         package = self.repository.load_active_package(workspace.workspace_id)
1594 |         package_id = package.package_id if package is not None else f"pkg_{workspace.workspace_id}"
1595 |         proposal.metadata = {
1596 |             **dict(proposal.metadata),
1597 |             "user_message_ref": user_message_ref,
1598 |             "confirmed_turn_id": turn_id,
1599 |         }
1600 |         self._materialize_confirmation_approval(proposal)
1601 |         scope_refs = [mutation.target_id for mutation in proposal.mutations if mutation.target_id]
1602 |         # L3 规格要求确认记录显式区分两条路径：
1603 |         # - Assistant 提议后用户确认：proposal_message_refs 必填；
1604 |         # - 用户直接给出清晰、完整且带范围的产品判断：proposal_message_refs 可空。
1605 |         assistant_message_ref = proposal.metadata.get("assistant_message_ref")
1606 |         if assistant_message_ref:
1607 |             confirmation_path = ConfirmationPath.ASSISTANT_PROPOSAL_THEN_USER_RESPONSE
1608 |             proposal_message_refs = [str(assistant_message_ref)]
1609 |         else:
1610 |             confirmation_path = ConfirmationPath.DIRECT_USER_STATEMENT
1611 |             proposal_message_refs = []
1612 |         confirmation = ConfirmationRecord(
1613 |             confirmation_id=f"confirmation_{uuid4().hex[:12]}",
1614 |             workspace_id=workspace.workspace_id,
1615 |             package_id=package_id,
1616 |             confirmation_path=confirmation_path,
1617 |             proposal_message_refs=proposal_message_refs,
1618 |             user_message_refs=[user_message_ref],
1619 |             confirmed_claims=[
1620 |                 ConfirmedClaim(
1621 |                     claim=(
1622 |                         mutation.rationale.strip()
1623 |                         or str(mutation.metadata.get("mutation_type", mutation.action.value))
1624 |                     ),
1625 |                     scope_refs=[mutation.target_id] if mutation.target_id else [],
1626 |                 )
1627 |                 for mutation in proposal.mutations
1628 |             ],
1629 |             scope_refs=scope_refs,
1630 |             confirmation_kind=ConfirmationKind.CONFIRMED,
1631 |             remaining_unresolved_refs=self._projected_unresolved_refs(
1632 |                 workspace.workspace_id, proposal
1633 |             ),
1634 |             recorded_at=utc_now_iso(),
1635 |         )
1636 |         proposal.status = CanvasMutationStatus.APPLIED
1637 |         self._apply_proposal(workspace, proposal, confirmation=confirmation)
```

## W-CODE-013 — Canvas workflow 仍为 definition_only

来源：`app/workflows/canvas_session.py:1-89`

```text
 1 | """EvoCanvas 1.0 的画布回合工作流定义。
 2 | 
 3 | 当前模块只提供 `canvas_turn` 的静态任务定义与注册契约，
 4 | 用于把单轮画布推进接入现有 workflow registry。
 5 | 首版范围仅覆盖定义层，不在这里接入真实服务、仓储或 API 行为。
 6 | """
 7 | from __future__ import annotations
 8 | 
 9 | from app.core.task import TaskDefinition, WorkflowSpec, WorkflowStep
10 | from app.workflows.policies import build_canvas_tool_policy
11 | 
12 | 
13 | def build_canvas_turn_definition() -> TaskDefinition:
14 |     """构建 EvoCanvas 画布单轮推进任务定义。
15 | 
16 |     Returns:
17 |         TaskDefinition: 用于注册到全局任务注册表的最小任务定义。
18 |     """
19 |     task_type = "evocanvas_canvas_turn"
20 |     workflow = WorkflowSpec(
21 |         name="canvas_turn",
22 |         version="1.0",
23 |         steps=[
24 |             WorkflowStep(
25 |                 id="load_canvas_context",
26 |                 type="context",
27 |                 title="加载当前画布上下文",
28 |                 role="SYSTEM",
29 |                 input_keys=["workspace_id", "turn_input"],
30 |                 output_keys=["canvas_context"],
31 |             ),
32 |             WorkflowStep(
33 |                 id="run_canvas_supervisor",
34 |                 type="agent",
35 |                 title="运行画布回合同步器",
36 |                 role="CanvasSupervisor",
37 |                 input_keys=["canvas_context", "turn_input"],
38 |                 output_keys=["supervisor_plan", "mutation_proposal"],
39 |             ),
40 |             WorkflowStep(
41 |                 id="merge_canvas_proposal",
42 |                 type="agent",
43 |                 title="合并结构化提议",
44 |                 role="SYSTEM",
45 |                 input_keys=["mutation_proposal"],
46 |                 output_keys=["canvas_patch", "handoff_draft"],
47 |             ),
48 |             WorkflowStep(
49 |                 id="emit_canvas_events",
50 |                 type="context",
51 |                 title="发出画布回合事件",
52 |                 role="SYSTEM",
53 |                 input_keys=["canvas_patch", "handoff_draft"],
54 |                 output_keys=["turn_summary"],
55 |             ),
56 |         ],
57 |     )
58 |     return TaskDefinition(
59 |         type=task_type,
60 |         display_name="EvoCanvas 画布回合",
61 |         input_schema={
62 |             "type": "object",
63 |             "properties": {
64 |                 "username": {"type": "string"},
65 |                 "workspace_id": {"type": "string"},
66 |                 "turn_input": {"type": "string"},
67 |                 "turn_id": {"type": "string"},
68 |             },
69 |             "required": ["username", "workspace_id", "turn_input"],
70 |             "additionalProperties": True,
71 |         },
72 |         workflow=workflow,
73 |         tool_policy=build_canvas_tool_policy(task_type),
74 |         agents={
75 |             "CanvasSupervisor": {
76 |                 "role": "CanvasSupervisor",
77 |                 "goal": "先暴露不确定性，再沉淀约束、待决策与结构化交接物草稿。",
78 |             }
79 |         },
80 |         output_spec={
81 |             "primary_artifact": "canvas_turn_summary",
82 |             "artifacts": ["mutation_proposal", "handoff_draft"],
83 |         },
84 |         metadata={
85 |             "product_line": "evocanvas",
86 |             "stage": "1.0",
87 |             "scope": "definition_only",
88 |         },
89 |     )
```

## W-CODE-014 — 当前 CanvasSnapshot 副本结构

来源：`app/canvas/domain/snapshots.py:1-62`

```text
 1 | """EvoCanvas 关键时刻快照模型。"""
 2 | 
 3 | from __future__ import annotations
 4 | 
 5 | from dataclasses import asdict, dataclass, field
 6 | from typing import Any, Dict, List, Optional
 7 | 
 8 | from app.canvas.domain.cards import CanvasCard
 9 | from app.canvas.domain.handoff import StructuredHandoff, TodoProjection
10 | from app.canvas.domain.relations import CanvasRelation
11 | 
12 | 
13 | @dataclass
14 | class CanvasSnapshot:
15 |     """记录某一时刻画布工作状态的快照。"""
16 | 
17 |     snapshot_id: str
18 |     workspace_id: str
19 |     title: str
20 |     summary: str = ""
21 |     created_at: str = ""
22 |     active_card_ids: List[str] = field(default_factory=list)
23 |     active_relation_ids: List[str] = field(default_factory=list)
24 |     cards: List[CanvasCard] = field(default_factory=list)
25 |     relations: List[CanvasRelation] = field(default_factory=list)
26 |     todo_projection: Optional[TodoProjection] = None
27 |     handoff: Optional[StructuredHandoff] = None
28 |     metadata: Dict[str, Any] = field(default_factory=dict)
29 | 
30 |     def to_dict(self) -> Dict[str, Any]:
31 |         """将快照序列化为字典。"""
32 | 
33 |         data = asdict(self)
34 |         data["cards"] = [card.to_dict() for card in self.cards]
35 |         data["relations"] = [relation.to_dict() for relation in self.relations]
36 |         data["todo_projection"] = self.todo_projection.to_dict() if self.todo_projection else None
37 |         data["handoff"] = self.handoff.to_dict() if self.handoff else None
38 |         return data
39 | 
40 |     @classmethod
41 |     def from_dict(cls, data: Dict[str, Any]) -> "CanvasSnapshot":
42 |         """从字典恢复快照实例。"""
43 | 
44 |         return cls(
45 |             snapshot_id=data["snapshot_id"],
46 |             workspace_id=data["workspace_id"],
47 |             title=data.get("title", ""),
48 |             summary=data.get("summary", ""),
49 |             created_at=data.get("created_at", ""),
50 |             active_card_ids=list(data.get("active_card_ids", [])),
51 |             active_relation_ids=list(data.get("active_relation_ids", [])),
52 |             cards=[CanvasCard.from_dict(item) for item in data.get("cards", [])],
53 |             relations=[CanvasRelation.from_dict(item) for item in data.get("relations", [])],
54 |             todo_projection=TodoProjection.from_dict(data["todo_projection"]) if data.get("todo_projection") else None,
55 |             handoff=StructuredHandoff.from_dict(data["handoff"]) if data.get("handoff") else None,
56 |             metadata=dict(data.get("metadata", {})),
57 |         )
```

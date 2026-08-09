# Claude 收敛认知过程深度拆解

> 复核日期：2026-07-21  
> 对象：Claude Desktop「Harness文档收敛」任务  
> 会话：`0eef04e9-7dcc-46f3-8f0b-8833dca85fdd`  
> 模型现场：`claude-opus-4-8`；2026-07-18 worker argv 曾观察为 Claude Code 2.1.209、`xhigh`，当前 Desktop 元数据记为 `high`  
> 分析重点：Claude 如何搜索、分工、聚类、改判、记忆、执行与失败恢复；EvoCanvas 建议仅保留为末尾附注

## 0. 这次修订纠正了什么

上一版把主要篇幅过早用于“EvoCanvas 可以怎么做”，对 Claude 自身只做了阶段概括。本版反过来：先把这条真实会话当成一个运行中的认知—控制系统来拆，回答以下问题：

1. Think 视图在本地究竟是什么数据；
2. 同一轮里的 thinking、text、tool use 为什么会被拆成多条事件；
3. Claude 如何用五个子 Agent 扩大观察面，又如何把 55 个问题压成 13 个根决策；
4. 为什么前三题的最终推荐全部推翻了最初推荐；
5. 用户反馈如何改变 Claude 的控制策略，而不只是改变文案；
6. 长上下文、缓存、自然语言“决策锁定”分别发挥了什么作用；
7. 两次 thinking-only、一次 `TaskCreate` 校验失败和最终批量写回暴露了什么；
8. 哪些行为来自模型判断，哪些行为受到 Claude Code Harness 的工具、会话和执行机制塑形。

## 1. 核心结论

这条会话中的 Claude 不是“先在脑中得到完整答案，再把结果逐段打印出来”。更准确的描述是：

> Claude 是一个以自然语言长上下文作为工作记忆、以工具结果作为环境反馈、以用户选择作为控制输入的递推式控制器；它持续重建当前 belief，再决定下一小步，而不是执行一份从开局就固定的完整计划。

其实际主链是：

```mermaid
flowchart LR
    A["建立目录与规则地图"] --> B["5 个子 Agent 分域扫描"]
    B --> C["55 个局部 finding"]
    C --> D["主 Agent 聚类成 13 个决策簇"]
    D --> E["用户纠正交互协议"]
    E --> F["逐题回读一手证据"]
    F --> G["更新当前判断"]
    G --> H["输出 A/B/C 与推荐"]
    H --> I["用户确认成为下一轮输入"]
    I --> J["自然语言记录决定"]
    J --> F
    J --> K["最后批量 Edit 写回"]
```

这套系统的突出能力是“广域感知之后的根因压缩与改判”，而不是 thinking 文本很长。它的主要脆弱点也不在单次推理，而在跨轮状态：决策映射、确认结果、执行计划和验证结果没有独立结构，只能由模型从长上下文中反复恢复。

## 2. 证据边界与可复核指纹

### 2.1 原始会话仍在本机

```text
/Users/apple/.claude/projects/-Users-apple-Desktop-evocanvas/
0eef04e9-7dcc-46f3-8f0b-8833dca85fdd.jsonl
```

2026-07-21 复核现场：

| 项目 | 值 |
| --- | ---: |
| 完整 JSONL 记录 | 623 |
| 完整文件字节 | 2,218,240 |
| 完整文件 SHA-256 | `831d1f46184290704e1488f37cfec46f3449ddb4a3bc91a9df611745d5ad5dcb` |
| 前置收敛与首轮写回分析窗口 | 记录 7–289 |
| 前 289 条字节 | 1,156,005 |
| 前 289 条 SHA-256 | `0a6cc64d8e37279ac647df1f4f3631ecb1f0635527340bea94d0ae8aa6566f16` |

前 289 条的指纹固定了本报告的主要历史窗口；即使文件尾部以后继续追加，仍可单独校验这段现场。

### 2.2 Think 视图是什么

截图中的独特灰色文字能直接命中 assistant 消息中的 `thinking` block，JSONL 同时保存 `signature`。这强烈支持“UI Think 是这些 block 的投影”，但在没有 Desktop 渲染代码的情况下，不能声称已经证明所有 UI Think 与 JSONL block 的完整一一映射。同一逻辑 assistant message 可以拆成多条 JSONL：

```text
assistant / thinking
→ assistant / text
→ assistant / tool_use
→ user / tool_result
→ assistant / next block
```

因此“JSONL 一行”不等于“一轮对话”，甚至不等于“一条完整 assistant 响应”。需要结合：

- `message.id`：聚合同一次模型响应的多个内容块；
- `uuid` / `parentUuid`：恢复会话事件链；
- `tool_use_id`：把工具请求与工具结果配对；
- `timestamp`：恢复流式到达和外部反馈顺序。

### 2.3 不能过度声称什么

本地 `thinking` 是模型输出给 Claude Code Harness 的 extended-thinking 通道，不等于模型全部不可观测内部计算。它还混合了：

- 任务语义判断；
- 自我纠错；
- 工具选择与参数规划；
- 输出结构设计；
- 对 system reminder、工具失败和上下文恢复的解释。

所以本报告分析的是“可观测的外显推理与控制过程”，不是神经网络内部完整思维。

### 2.4 Desktop 任务与 Claude Code 分支不是同一个 ID

Desktop 元数据中的稳定任务 ID 是 `local_ca59dd82-...`，当前 CLI transcript 分支是 `0eef04e9-...`，此前还有一个 rewind 前分支 `c1f7a69d-...`。三层身份应分开：

```text
Desktop 稳定任务 local_ca...
→ 当前映射到 CLI session 0eef...
→ session 内部由 uuid/parentUuid 构成消息 DAG
```

旧分支有 106 条记录、版本 2.1.197；当前分支有 623 条记录、版本 2.1.209。两者共享 61 个 UUID。新分支保留历史节点 UUID 和内容，但重新 stamp 新 sessionId/version，说明 rewind + fork 是重序列化历史前缀后从指定节点继续，而不是简单复制或截断旧文件。

## 3. 前置收敛窗口的定量画像

记录 7–289 覆盖从首次 Harness 收敛指令到 Q1–Q7 首轮写回完成；固定指纹和派生计数见 [convergence-process-index.json](./evidence/sessions/convergence-process-index.json)：

| 指标 | 数值 |
| --- | ---: |
| JSONL 记录 | 283 |
| Assistant 事件片段 | 111 |
| 逻辑 Assistant `message.id` | 34 |
| thinking 块 | 34 |
| thinking 字符 | 130,914 |
| thinking 中位长度 | 约 1,506 字符 |
| thinking 最大长度 | 18,701 字符 |
| 可见 text 块 | 32 |
| 可见文本字符 | 26,849 |
| 工具调用 | 45 |
| 真人文本输入 | 14 |
| Harness 合成恢复提示 | 1 |
| 作为 user 记录的工具结果 | 45 |

工具分布：

| 工具 | 次数 | 在控制过程中的作用 |
| --- | ---: | --- |
| `Read` | 17 | 逐题返回一手证据，修正汇总偏差 |
| `Edit` | 17 | 最终把自然语言决定写回文件 |
| `Agent` | 5 | 并行扩大文档扫描范围 |
| `Bash` | 3 | 目录发现和搜索 |
| `AskUserQuestion` | 1 | 首次批量提问，随后被用户拒绝 |
| `TaskCreate` | 1 | 写回前组织任务；参数校验失败 |
| `mcp__ccd_session__mark_chapter` | 1 | Desktop/Harness 的章节标记；正文简称 `mark_chapter` |

34 个逻辑 assistant message 中，32 个被拆成 2–7 个事件片段。这说明 UI 的 Think、可见文字、工具动作不是三个独立 Agent 回合，而是同一模型响应被流式协议和工具回灌拆开后的观察面。

### 3.1 完整 623 条 session 的事件画像

为了区分“前置 Q1–Q7 窗口”和“当前完整任务”，全文件另有以下统计：

| 项目 | 数量 |
| --- | ---: |
| assistant 顶层记录 | 235 |
| thinking blocks | 76 |
| thinking 正文字符 | 201,860 |
| thinking signature 字符 | 135,108 |
| visible text blocks | 77 |
| tool_use / tool_result | 82 / 82 |
| 真人文本输入 | 37 |
| Harness 合成恢复提示 | 1 |
| stop_hook_summary | 33 |
| 顶层 attachment | 17 |
| 顶层 UUID / 唯一 UUID | 406 / 406 |

82 个 tool result 都有 `sourceToolAssistantUUID`，tool-use/result ID 数量完全匹配，其中 2 个是错误结果。图中没有缺父节点，也未发现 `isSidechain:true` 记录；有 8 个父节点拥有多个子节点，主要来自并行 Agent/工具事件。这是“有分叉的消息 DAG”，不是严格单链。

33 条 `stop_hook_summary` 均表示 Harness 在回合结束后执行了 Stop hooks，且没有输出、没有阻止继续、没有 stop reason 或 hook error。它们不是 Claude 的自我反思，也不是 thinking 的另一种保存形式。

17 条顶层 attachment 主要是 task reminder、skill listing 和 agent listing delta；用户上传图片则位于真人 user message 的 image content block 内。两者在协议上不是同一种“附件”。

## 4. 阶段一：任务解释与目录定向

### 4.1 起始解释很程序性

记录 #7 是原始任务：通读 Harness、找出需要收敛的点、用半结构化单选题推进。

记录 #10（`msg_762117c682794f17afe73658d5cf46ec`）的 thinking 很短，只把任务压成：

1. 找 Harness；
2. 识别未收敛点；
3. 组织成有优缺点和建议的单选题。

这里尚未建立“仓库工作规则 → 主 PRD → 当前 Harness → 历史参考”的证据优先级。后续扫描因此首先做的是 Harness 内部一致性审计，而不是从产品真相源向下校验。

### 4.2 搜索失败后能快速改变观测策略

事件链：

```text
#12 按文件名搜索 harness，无结果
→ #14–16 改用正文检索
→ #18–20 定位 docs/harness 并枚举目录
→ #22–29 读取 README、Overview、Convergence Confidence
```

这是一个小而真实的反馈控制：初始环境假设失败后，Claude 没有继续加码同一种搜索，而是切换观测手段，再从导航文件建立局部地图。

## 5. 阶段二：五个子 Agent 如何扩展观察面

### 5.1 分工不是投票，而是领域分片

五个 `Agent` 调用由同一个逻辑消息 `msg_1f71cf0a38f1412e9f816b0a43483d32` 的多个 tool-use block 发起。分工如下：

| 范围 | 文件数 | finding | 子 Agent tokens | 工具数 | 耗时 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Overview + Instructions | 10 | 11 | 74,354 | 13 | 185,414 ms |
| Memory + Runtime | 8 | 12 | 80,283 | 10 | 187,084 ms |
| Orchestration + Lifecycle | 6 | 10 | 78,275 | 11 | 239,451 ms |
| Safety + Governance | 8 | 12 | 66,304 | 13 | 200,633 ms |
| Observability + Verification + Evaluation + References | 14 | 10 | 87,953 | 21 | 394,410 ms |

合计约 55 个 finding、387,169 个子 Agent token、68 次子 Agent 内部工具调用。累计工作时长约 20 分钟，因为重叠运行，主会话墙钟时间约 7 分 14 秒。

这不是让多个 Agent 独立回答同一个问题然后多数表决，而是把文档域切开：子 Agent 负责局部召回，主 Agent 负责跨域综合。

### 5.2 分工 prompt 已经在做局部治理

五个子任务都要求：

- 完整读文件；
- 标注成熟度；
- 找矛盾、留白、术语漂移、成熟度错配、范围模糊和重复定义；
- 返回文件位置、原因、候选方向和严重度。

这比“帮我看看”强很多，但输出仍是长自然语言，没有统一 finding schema。于是跨域的以下工作只能回到主 Agent：

- 去重；
- 判断两个症状是否同根；
- 比较证据强度；
- 推断上下游依赖；
- 决定哪些问题值得问用户。

### 5.3 五路并行并不等于认知去中心化

真正的裁决仍高度集中：

- 子 Agent 不互相挑战；
- 没有第二个 Agent 对高风险结论做对抗复核；
- 没有共享结构化 finding 表；
- 55→13 的映射全部由主 Agent 在一个超长 thinking 中完成。

所以这是“并行感知、集中判断”，不是多主体共识系统。

## 6. 阶段三：55 → 13 的根因聚类

关键事件是记录 #43：

- 时间：`2026-07-16T09:13:39.848Z`；
- message：`msg_957638c758c549bc8d16a9a84ed10fc3`；
- thinking：18,299 字符；
- 随后的可见摘要：3,880 字符。

Claude 执行了三类压缩。

### 6.1 从症状列表转成共同根因

例如以下表面问题：

- 中风险没有明确落点；
- 二元权限与三级风险不一致；
- 外部不可逆动作未挂到主链；

没有被拆成三个问题，而是归为一个“风险分级与门禁模型”决策。

### 6.2 按上游杠杆排序，而不是只看 severity

Claude 把 A–F 视为核心模型，把 G–K 视为受核心模型影响的职责边界，把 L–M 视为成熟度和默认值收尾。其隐含判据是：

> 如果一个上游选择确定后，多个下游冲突会变成机械对齐，那么先问上游，而不是逐个修症状。

### 6.3 形成 13 个决策簇

| 簇 | 核心问题 |
| --- | --- |
| A | 风险分级与门禁模型 |
| B | 对象状态权威与五层可用性 |
| C | 两层确认语义 |
| D | 双版本模型 |
| E | 主题与活跃工作上下文 |
| F | 触发门与收敛置信度 |
| G | 回合结果码与终态 |
| H | 验证与评估边界 |
| I | 指令面 / Prompt 权威 |
| J | Trace / Observability 字段 |
| K | 交接门槛与字段名 |
| L | 成熟度标注 |
| M | 编排和治理操作留白 |

### 6.4 真正缺失的是聚类谱系

Claude 的压缩质量高，但系统没有保存：

```text
raw_finding_id
→ cluster_id
→ merge_reason
→ supporting_sources
→ conflicting_sources
→ upstream_dependencies
→ confidence
→ disposition
```

因此无法程序化回答“原始 finding #17 去了哪里”或“为什么两个症状被判为同一个根因”。18,299 字符 thinking 成了唯一中间态，压缩后可读，无法稳定复算。

## 7. 第一次交互失败：工具能力塑形了对话策略

记录 #43 的 thinking 明确注意到 `AskUserQuestion` 一次可批量展示多个问题。随后 Claude 一次给出 Q1–Q3。

其隐含因果链是：

```text
工具允许批量题
→ 批量看起来更高效
→ Claude 把“用单选题”误读成“适合批量调用单选工具”
→ 覆盖用户真正需要的逐题收敛节奏
```

记录 #46 用户 dismiss 工具；#50 明确要求“一题一题来，先讲总览”。Claude 在 #51 重新规划控制协议，之后永久改为：

```text
一次一题
→ 文本排版
→ 等显式选择
→ 决策锁定
→ 下一题
```

这不是内容推理失败，而是 tool-affordance bias：Harness 给了什么交互原语，会反向影响模型如何理解任务。

## 8. Q1–Q7：递推式逐题控制循环

### 8.1 每题不是套模板，而是滚动重规划

实际循环：

```text
恢复上一题决定
→ 判断本题是否需要重新读取
→ 找出多个症状的共同根因
→ 把无论如何都应修的项移出选择题
→ 只保留真正设计分叉
→ 给 A/B/C 与推荐
→ 等用户选择
→ 输出自然语言“决策锁定”
→ 重建下一题状态
```

这种方式接近 receding-horizon control：每一轮只对当前问题做足够深的规划，得到用户输入后再计算下一轮，而不是一开始就固化 Q1–Q13 的全部答案。

### 8.2 七题选择与取证成本

最终选择序列：

```text
C / B / B / A / B / A / A
```

| 题目 | 初次问题记录 | 用户选择 | 新 Read | 最终推荐 | 特征 |
| --- | ---: | ---: | ---: | ---: | --- |
| Q1 风险与门禁 | #67 | #68 C | 3 | C | 重读后明确改判 |
| Q2 状态权威 | #85/#92 | #118 B | 4 | B | 多轮解释与视觉纠偏 |
| Q3 确认路径 | #128 | #132 B | 1 | B | 多数通用规则压过孤立例外 |
| Q4 双版本 | #145 | #153 A | 2 | A | 语义分层，当前同步但保留双字段 |
| Q5 范围术语 | #165 | #169 B | 2 | B | 内容语言与系统语言建立映射 |
| Q6 两道门 | #171 | #175 A | 0 | A | 复用证据，低成本完成 |
| Q7 结果与终态 | #187 | #191 A | 2 | A | 拆开原因码、业务结果、技术终态 |

## 9. 最关键证据：前三题全部推翻初始推荐

55→13 总览时，对前三题的初始推荐是：

```text
Q1 A / Q2 A / Q3 A
```

逐题重读直接证据后变成：

```text
Q1 C / Q2 B / Q3 B
```

这比“Claude 会自我反思”更具体：它揭示了汇总阶段和裁决阶段使用了不同证据质量与不同启发式。

### 9.1 Q1：从“补映射”改成“拆正交维度”

初始判断：把三级风险映射为更多门禁路径。

正式提问前重新读取 Facts、Authority、Gate 后，Claude 改判：

- 风险等级负责留痕、提示、下游说明；
- 是否需要确认是另一条轴；
- 门禁保持二元；
- 外部不可逆动作单独设门。

即从“把分类补齐”转成“发现两个概念本来不应共用一条轴”。

### 9.2 Q2：从“全局单一权威”改成“语义所有权分层”

初始判断：让 State Ledger 成为所有状态的全局权威。

重新读取 State Ledger、Verification、Object Governance、Handoff Governance 后发现，State Ledger 已明确排除交接有效性状态。因此改判为：

- Ledger 管对象状态；
- Handoff Governance 管包版本四态；
- 两者互相引用，不互相吞并。

### 9.3 Q3：从“增加更强门”改成“修正孤立例外”

初始判断：包版本确认必须经过 AI 提议再由用户确认。

直接证据显示全局已有两条通用路径：

- assistant proposal + user response；
- direct user statement。

因此 Claude 将 Stable State 中的“必须有 Assistant 提议”判为孤立限制，选择修正文档局部，而不是给全局确认模型再加一层例外。

### 9.4 从改判可推断的初始偏置

初始综合表现出三个稳定偏好：

1. 偏好集中化的单一权威；
2. 偏好更强、更保守的安全门；
3. 偏好通过映射把现有分类补齐。

回到一手证据后，启发式转为：

1. 尊重文档自述的职责边界；
2. 保持跨文档多数规则一致；
3. 避免为孤立例外增加全局复杂度；
4. 优先识别正交维度和语义层。

结论不是“子 Agent 不可靠”，而是：

> 子 Agent 汇总适合提高召回率和形成议程；最终推荐必须由主 Agent 回到直接证据后重新裁决。

## 10. Claude 反复使用的七种推理算子

把具体答案抽掉后，Q1–Q7 反复出现以下操作：

1. **维度正交化**：风险强度和确认门禁不是同一轴。
2. **权威归属分层**：对象状态与包治理状态由不同职责文档定义。
3. **多数规则优先于孤立例外**：保留跨文档通用确认路径，修正单点偏差。
4. **语义不同则保留独立字段**：即使 1.0 的两个版本号同步变化，也不等于同一概念。
5. **保留多词并补映射**：主题是内容语言，活跃工作上下文是系统语言。
6. **按发生时点拆分相似判断**：触发判断在回合外，收敛置信度在回合内。
7. **分离技术态、业务态与原因码**：不能把三种分类混成一个终态列表。

这些算子说明 Claude 的主要压缩方式不是关键词匹配，而是拆轴、分层、定权威、补映射、减少例外。

## 11. 用户不是旁观者，而是控制输入

### 11.1 节奏反馈改变运行协议

用户要求“一题一题来，先讲总览”后，Claude 不只是改排版，而是放弃 `AskUserQuestion` 批量模式，建立新的逐题状态循环。

### 11.2 视觉反馈改变信息编码

用户指出“全是一样的字重字号，没有重点”后，Claude 缩短标题、突出根本问题、表格化职责、把推荐/风险/必做项分区。实质结论没变，外显编码发生变化。

### 11.3 概念问题让系统临时退出“决策模式”

当用户问几份文档分别是什么、账本是什么时，Claude 暂停索取选择，重新读取 Object/Handoff Governance，再用类比建立概念。这说明它允许控制模式从“做选择”退回“建立共同语义”，之后再恢复。

### 11.4 人工门控存在，但对抗压力偏弱

Q1–Q7 用户全部选择了 Claude 当轮推荐方案。人确实掌握最终确认权，但没有形成强反方路线。Claude 的推荐叙述有明显锚定效应：门控存在，不等于充分对抗。

## 12. 长上下文如何支撑两天后的恢复

Q1 输出在 `2026-07-16T09:29:26.039Z`，用户单独回复 `C` 在 `2026-07-18T07:53:45.705Z`，相隔约 46 小时 24 分。

恢复时可见 usage 里：

- 新输入 token 很少；
- cache creation / cache read context 接近 200k–270k token；
- `last-prompt` 元数据仍可能指向最初任务，而不是最近一题。

Claude 能判断孤立的 `C` 是 Q1 选择，主要依赖完整 parent/child 会话链和大上下文前缀，而不是一个专门的 `DecisionRecord`。

这是一种“通过重放语境恢复状态”，不是“读取结构化状态”。优势是灵活；代价是恢复昂贵、需要重新解释、会受旧信号干扰。

## 13. 自然语言记忆漂移的直接证据

记录 #197 第一次整理 Q1–Q7 时，选择序列正确。

记录 #199 再次恢复时，thinking 开头短暂出现把 Q1 取成初始推荐 A，随即重新扫描并纠正为用户最终选择 C。记录 #208 第三次重建又恢复为正确的 `C/B/B/A/B/A/A`。

这说明系统拥有：

> 可自愈的自然语言记忆，而不是不可能漂移的决定状态。

初始推荐 A 和最终决定 C 都是上下文中的强文本信号。没有结构化约束保证“confirmed C”自动覆盖“proposed A”；正确性来自模型在当轮重新发现并解释二者关系。

## 14. 写回阶段：两次无输出、一次工具校验失败、一次直接降级

### 14.1 两次 thinking-only

用户要求立即沉淀 Q1–Q7 后：

- #197：thinking 13,177 字符，完整重建决定，但没有 text/tool use；
- Harness 注入“上一响应没有可见输出”；
- #199：thinking 18,701 字符，再次重建决定，仍无可见输出；
- #207：用户不得不说“继续啊”；
- #208：thinking 17,753 字符，第三次重建后才真正继续。

两次失败消耗 31,878 thinking 字符，却没有外部动作。这说明“模型已形成计划”与“Harness 得到可执行或可见输出”之间存在独立失败面。

### 14.2 `TaskCreate` 的输入校验失败

记录 #210–211：Claude 想先创建任务，但 tool input JSON 被截断，返回 `InputValidationError`。

它没有循环重试这个非必要工具，而是在 #212 重新规划，直接用 Edit 分批修改。这个降级是合理的：任务跟踪失败不应阻塞目标动作。

对应源码机制也能解释这一点：工具 schema 校验失败不会直接让整个 Agent 崩溃，而是被包装成带原 `tool_use_id` 的错误 `tool_result`，重新进入下一轮模型上下文。失败因此变成可供模型观察和改路的数据。

### 14.3 写回行为与可见总结不一致

首轮写回窗口实际记录：

- 17 次 `Edit`；
- 11 个唯一文件；
- 工具事件按 Edit → result 交替；
- 没有独立 Read-back、`git diff` 或链接校验。

而会话中的对外总结使用了不同的文件数/改动数，并把多文件动作描述为“并行”。这揭示三个问题：

1. 计划计数与实际计数会漂移；
2. 语言里的“并行”不等于工具事件并发；
3. 多文件 Edit 没有事务性，中途失败会留下部分写回。

### 14.4 后续 B1–B8 出现了推理模式切换

完整 623 条 session 的后半段不再主要解决“多处定义冲突”，而开始补 B1–B8 一类判据、阈值、默认参数、租约策略和 1.0 范围声明。Claude 的认知任务发生了变化：

| 前半段 | 后半段 |
| --- | --- |
| 合并冲突 | 回补留白 |
| 判断谁是唯一权威 | 判断实现者能否据此作确定判定 |
| 以跨文档一致性为中心 | 以判据、默认值和边界可执行性为中心 |

这说明 Claude 不只是沿同一模板继续提问，而是随着问题空间缩小，主动切换了评价函数。

### 14.5 B7 再次证明“计划语言”不等于执行

后续租约问题中，Claude 连续两次只说“接下来读取/写入”，实际没有发出工具调用。用户指出它“只是一句话一句话地回”后，Claude 承认“光说不做了”，才真正执行 Edit/Read/Edit。

因此审计 Claude 行为时必须区分：

```text
计划性文字：表示模型打算做什么
tool_use：表示 Harness 收到结构化动作请求
tool_result：表示工具返回了什么
read-back/diff/test：表示终态是否独立验证
```

只有后 3 层能逐步提高“动作已经发生”的证据强度。

## 15. thinking 长度究竟代表什么

thinking 不能直接等价为“推理质量”或“问题难度”。这条会话里：

- 55→13 聚类的 18,299 字符确实用于高复杂度综合；
- Q4 thinking 约 13,979 字符，但最终结论是“情况比想象得简单”；内部主要在反复缩小真正分叉；
- Q6 分析本身约 1,628 字符；用户选择 A 后、准备进入 Q7 的下一块约 550 字符，不能把后者当作 Q6 全部思考成本；
- 写回失败的 18,701 字符主要是恢复和重建，不是新增设计判断。

更准确的混合模型是：

```text
thinking 长度
= 语义难度
+ 上下文恢复
+ 自我纠错
+ 输出格式规划
+ 系统提醒解释
+ 工具失败后的重规划
```

因此 UI 展示“想了多久/多少字”只能表示计算活动量，不能单独证明结论更可靠。

## 16. Harness 如何塑形这套思考

把会话与固定的 2.1.88 非官方 source-map 源码快照交叉，可看到模型行为受到运行时的具体约束。

### 16.1 外显响应是流式事件组装，不是单块消息

`src/query.ts:659-863` 显示 API stream 可依次产出 thinking、text、tool-use；工具块一到达即可进入 streaming executor，已完成工具结果甚至可以在模型流尚未完全结束时被 yield。由此不能仅凭 JSONL 相邻行推断“Claude 完整想完后才开始工具”。

### 16.2 部分 thinking 可能被 tombstone

流式 fallback 时，旧尝试的部分 assistant 消息，尤其 thinking block，可能因签名无效被 tombstone，并清空旧 tool-use/result executor（`src/query.ts:709-740`）。所以落盘 transcript 是 Harness 认可的事件链，不一定等于模型传输过程中出现过的每个临时片段。

### 16.3 工具失败是反馈，不是回合外异常

`src/services/tools/toolExecution.ts:614-732` 把 schema/语义校验失败变成错误 `tool_result`；`TaskCreate` 失败后 Claude 能直接改用 Edit，正是这个反馈回路的实例。

### 16.4 并发由工具安全属性决定

固定快照有流式与非流式两条相关调度路径：`StreamingToolExecutor` 以 safe/unsafe barrier 调度主流式工具；fallback/非流式 `toolOrchestration.ts:19-176` 才把连续 `isConcurrencySafe` 工具组成批次并使用默认最大并发 10，非安全工具逐个串行，context modifier 按原 tool block 顺序应用。因此“模型一次发出多个 tool use”不等于“所有工具并行执行”。

### 16.5 会话不是简单消息数组

`src/utils/sessionStorage.ts:993-1081` 使用 `parentUuid` 建链，tool result 可回指发起它的 assistant UUID，compact boundary 同时保存物理断点和 `logicalParentUuid`。`loadFullLog` 再从最新叶节点逆向重建有效会话链。JSONL 更接近追加式事件日志 + 消息 DAG，而不是聊天气泡数组。

### 16.6 Context 被分成不同权威与缓存通道

固定源码快照中：

- system prompt 与 system context 合并进入 system 前缀；
- CLAUDE.md 和当前日期通过 meta user `system-reminder` 前置；
- 会话、tool result、attachment 继续追加在消息链；
- Git status 是会话起点快照，并明确标注不会自动更新。

这意味着 Claude 看到的“上下文”不是一块平面文本，而是多个角色、缓存和更新频率不同的输入层。

## 17. 对 Claude 本身的综合评价

### 17.1 强项

- 能用并行领域扫描显著扩大召回率。
- 能把 55 个局部症状压成 13 个上游决策。
- 正式裁决前会回到一手证据，并敢于推翻自己和子 Agent 的初始推荐。
- 推理主要依赖职责边界、语义层和因果依赖，不只是词面相似。
- 能根据用户反馈改变节奏、表达编码和决策/解释模式。
- 跨两天仍能从长上下文恢复孤立选择。
- 工具失败后能识别非必要依赖并降级继续。

### 17.2 弱项

- 开局没有先建立工作区的完整真相源优先级。
- 子 Agent 输出缺少统一 finding schema，去重和谱系全靠主 Agent 长 thinking。
- 初始推荐受集中化、安全门和补映射偏好影响，前三题全部需要改判。
- `AskUserQuestion` 的批量能力一度覆盖了用户真正的交互意图。
- “决策锁定”只是自然语言，已经出现 A/C 瞬时漂移。
- 两次 thinking-only 证明内部计划完成不等于外部动作发生。
- 写回计数、并行叙述与实际工具事件不完全一致。
- 多文件写回没有事务性，也没有独立终态验证。
- 七次推荐均被接受，缺少强对抗性方案压力。

## 18. 最终判断

这条 Claude 会话最准确的画像不是“拥有稳定状态机的自动收敛系统”，而是：

> 一个感知面很宽、局部语义推理很强、能够通过重读证据自我修正，并通常可以从长上下文恢复正确状态的自然语言控制系统。

它可靠的部分主要是：

- 发现文档冲突；
- 通过上游依赖压缩问题；
- 逐题回读直接证据；
- 在用户反馈后调整策略；
- 工具失败后的局部恢复。

它不可靠或成本较高的部分主要是：

- 原始 finding 到决策簇的谱系；
- 已确认决定的稳定覆盖关系；
- 长暂停后的低成本恢复；
- 批量动作的计划—执行一致性；
- 多文件写回的原子性与终态验证。

最能概括这条 session 的两个事实是：

1. 前三题的最终推荐全部推翻初始汇总推荐，说明“一手证据复核”而不是“多 Agent 汇总”决定了最终质量；
2. 写回前 Claude 曾短暂把 Q1 取回初始值 A，又自行纠正为用户确认的 C，说明它能自愈，但没有硬状态保证。

## 19. 非重点附注：与 EvoCanvas 的关系

对 EvoCanvas 真正有价值的不是复制灰色 Think 视图，而是认识 Claude 当前依赖自然语言维持的几个中间态：finding 谱系、决策簇、证据包、确认结果、写回结果和验证结果。具体产品建议仍放在 [00-analysis-report.md](./00-analysis-report.md) 的末尾附录，本报告不再展开。

## 20. 复核入口

- 原始本机会话：`/Users/apple/.claude/projects/-Users-apple-Desktop-evocanvas/0eef04e9-7dcc-46f3-8f0b-8833dca85fdd.jsonl`
- 脱敏会话结构：[evidence/sessions/claude-evocanvas-harness-session.sanitized.jsonl](./evidence/sessions/claude-evocanvas-harness-session.sanitized.jsonl)
- 本次事件索引：[evidence/sessions/convergence-process-index.json](./evidence/sessions/convergence-process-index.json)
- Desktop/CLI 分支拓扑：[evidence/sessions/desktop-session-topology.json](./evidence/sessions/desktop-session-topology.json)
- Session 清单：[evidence/sessions/claude-session-inventory.json](./evidence/sessions/claude-session-inventory.json)
- 公开源码控制流索引：[evidence/public-source/deep-control-flow-index.json](./evidence/public-source/deep-control-flow-index.json)
- 固定源码快照说明：[evidence/public-source/source-snapshot-manifest.json](./evidence/public-source/source-snapshot-manifest.json)
- 证据等级与限制：[01-evidence-ledger.md](./01-evidence-ledger.md)

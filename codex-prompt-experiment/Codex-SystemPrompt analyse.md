## Codex System Prompt 逐段分析与学习要点

> 基于捕获的完整 system prompt（125 行，约 14.7KB），先讲全局架构，再逐段拆解设计意图，标注对 EvoCanvas 有借鉴价值的手法。


---

## 全局视角：Codex 这份 Prompt 到底在想什么


### 三层架构

整份 system prompt 在结构上分为三个清晰的层次，每一层解决不同的问题：

**第一层：身份层（第 1-19 行）。** 解决"我是谁"。包括身份声明、人格定义、核心价值观、交互风格、升级处理策略。这 19 行文字定义了模型在所有场景下的"底色"——不管用户让它做什么，这层约束都稳定生效。

**第二层：执行层（第 22-66 行）。** 解决"我怎么干活"。包括通用工作准则、编辑约束、特殊请求处理、自主性策略、前端设计策略。这层是操作手册，告诉模型在具体行动中遵守哪些规则、使用哪些工具、什么时候该主动什么时候该等。

**第三层：沟通层（第 68-124 行）。** 解决"我怎么说话"。包括输出通道定义、格式化规则、最终答案约束、中间更新约束。这层占了全文将近一半的篇幅，说明 OpenAI 认为"模型怎么表达自己"比"模型怎么做事"更需要约束。

这三层之间的关系是递进的：身份层决定风格基调，执行层决定行为边界，沟通层决定输出质量。上层约束更抽象、更稳定，下层约束更具体、更容易随场景变化。


### 一个核心设计哲学：通用约束 + 用户提示补全

实验验证了一个关键事实：**Codex 在 4 个完全不同的场景中使用了完全相同的 system prompt**（MD5 校验一致）。这意味着 Codex 的设计者做了一个明确的判断——system prompt 只放"所有场景都需要遵守的通用规则"。场景特定的行为引导主要由 user prompt 承载；运行时权限、能力和环境信息则通过独立的 developer / user 消息注入。

这是一个值得深思的架构决策。它的好处是 system prompt 精简、稳定、不会因为场景增多而膨胀；坏处是 user prompt 的负担很重，每次都要重复声明场景约束，一旦遗漏就可能导致行为偏移。

对比 EvoCanvas 的四模块设计（System Base / Stage Prompt / Object Prompt / Receipt Prompt），Codex 的 system prompt 只对应稳定的通用基座；它的 developer message 和环境上下文是运行时消息来源，不等于 Stage Prompt 或 Object Prompt。当前 rollout 没有证明 Codex 会把内部阶段注入模型，也没有证明它存在独立的 Receipt Prompt。EvoCanvas 的四模块设计因此需要重新拆分为：稳定指令、运行时治理、结构化数据和输出协议。


### 三个设计张力

这份 prompt 内部存在三组有意的张力，理解这些张力比单独看任何一条规则都更重要：

**张力一：自主 vs 克制。** 第九段（自主性与持久性）强烈鼓励模型"做完整个任务、不要停在分析阶段"。但第七段（编辑约束）用大量 NEVER 条款限制模型的破坏性操作。Codex 的策略是"大胆行动，但在高风险操作上严格约束"——不是限制模型做多少事，而是限制它在做的时候犯多大错。

**张力二：简洁 vs 信息量。** 交互风格和最终答案规则都在反复要求简洁（"不觉得需要填满空间""50-70 行上限"）。但中间更新规则又要求频繁汇报进展（"每 30 秒""思考超过 100 词就中断"）。Codex 的策略是"每次说话都短，但说的频率要高"——用高频短消息取代低频长报告。

**张力三：主动 vs 被动。** 通用准则要求"先检查再下结论"（被动探索），自主性策略要求"默认动手做"（主动执行）。Codex 的解法是分阶段——探索阶段被动（先读代码、先建上下文），执行阶段主动（有了上下文就动手做，不要只出主意）。


### 全文占比分析

各层的篇幅分配透露了 OpenAI 的优先级：

| 层次 | 行数 | 占比 | 说明 |
|------|------|------|------|
| 身份层 | 19 行 | 15% | 高度浓缩，几个锚点就够 |
| 执行层 | 45 行 | 36% | 操作约束需要精确，但不冗余 |
| 沟通层 | 57 行 | 46% | **最大的篇幅花在"怎么说话"上** |
| 安全/错误处理 | 0 行 | 0% | **完全没有** |

最后一点非常值得注意：这份 prompt 没有任何安全条款（不说"不要做有害的事"）、没有错误恢复策略（不说"如果工具调用失败怎么办"）、没有上下文压缩指令（不说"如果对话太长怎么办"）。这些要么被放在了运行时层（不在 system prompt 里），要么被 OpenAI 认为不需要在 prompt 层面处理。


### 与 EvoCanvas 的宏观对比

| 维度 | Codex | EvoCanvas 设计意图 | EvoCanvas 运行时现状 |
|------|-------|-------------------|---------------------|
| 消息与指令分工 | 稳定 System + 运行时 Developer / Context / User | 4 个业务 Prompt 模块 | 角色、上下文和用户消息混杂 |
| 角色切换 | 不切换，靠 user prompt | Supervisor 路由到 6 个角色 | Supervisor 有路由但角色行为弱 |
| 输出控制 | prompt 里详细规定（占 46%） | Receipt Prompt 模块设计了但没落地 | 只有字数限制 |
| 工具策略 | prompt 里直接写"用什么工具、怎么用" | ToolPolicy 做了角色×阶段白名单 | 有工具定义但无行为引导 |
| 行为约束风格 | ALWAYS/NEVER + 动机层 + 排除法 | "不静默合并""不伪装确定性" | 只在代码注释级别 |
| 上下文管理 | 不在 prompt 里处理 | SlidingWindow + Rehydration | SlidingWindow 已实现 |

核心差距：EvoCanvas 在"设计意图"上比 Codex 更精密（4 模块、6 角色、约束与决策分离），但在"运行时落地"上远远落后。Codex 设计简单但 100% 兑现，EvoCanvas 设计精密但兑现率不到 20%。


### 完整 Prompt 组装链路：模型到底看到了什么

从 rollout JSONL 中提取的完整消息流揭示了 Codex 发给模型的**不是**一个简单的 system prompt + user message，而是一个四层消息结构：

```
┌─ [1] System Prompt（base_instructions）─────────────── 14.7KB
│   身份 + 人格 + 价值观 + 工作准则 + 格式规则 + 沟通规则
│   来源：Codex CLI 内置，所有任务完全相同
│
├─ [2] Developer Message（运行时注入）────────────────── 约 8-10KB
│   Part 0: <permissions instructions>  沙箱权限和审批策略
│   Part 1: <apps_instructions>         已安装的 App/连接器说明
│   Part 2: <skills_instructions>       ~100 个可用 Skill 清单 + 使用规则
│   Part 3: <plugins_instructions>      ~16 个已启用 Plugin 清单 + 使用规则
│   来源：Codex 运行时根据当前环境动态生成
│
├─ [3] User Message 1（运行时注入）────────────────────── 约 200B
│   <environment_context>
│     cwd / shell / current_date / timezone
│   </environment_context>
│   来源：Codex 运行时自动注入环境信息
│
└─ [4] User Message 2（用户原始输入）─────────────────── 用户写了啥就是啥
    原样传入，无任何加工、包裹或重写
```

**关键发现一：用户输入原样透传，不做任何加工。** 对比原始 prompt 文件和 rollout 中记录的 user message，两者逐字一致。Codex 没有对用户输入添加任何包装语、没有注入额外指令、没有做 XML 标签化。策略是"环境信息由我注入，用户输入保持纯净"。

**关键发现二：真正的"秘密武器"在 Developer Message 层。** 这一层不在 system prompt 里（`base_instructions` 中没有这些内容），也不在用户输入里——它是 Codex 运行时在组装请求时**动态插入**的一个独立消息（role=developer）。其中最有价值的是 `<skills_instructions>`，包含约 100 个可用 Skill 的名称、描述和路径，以及一套详细的"渐进式披露"（progressive disclosure）使用规则。这意味着模型在每一轮对话中都知道"当前环境有哪些能力可以用"，但只在需要时才去读取具体内容。

**关键发现三：环境上下文作为独立 user message 注入。** 工作目录、shell 类型、日期和时区被放在一个独立的 user message 里，用 `<environment_context>` XML 标签包裹。这确保了模型知道"我在哪里、现在几点、用户的环境是什么"，而无需用户手动提供。

**关键发现四：截断策略在运行时静默执行。** `turn_context` 中记录了 `truncation_policy: {mode: "tokens", limit: 10000}`，说明 Codex 有一个 10K token 的截断阈值，但这不在 prompt 里告诉模型——运行时层面静默处理。

**对 EvoCanvas 的启示**：

- **不要加工用户输入。** Codex 证明了用户输入原样透传是可行的。EvoCanvas 应保留用户原始输入，不要把角色、画布内容或内部状态拼接进用户原话。
- **区分运行时治理和业务数据。** Codex 的 developer message 承载权限、能力和插件规则，但 rollout 没有证明它承载当前阶段。EvoCanvas 可以把必要的运行时治理放入 developer message；对象材料应作为结构化数据上下文传入，不应获得 developer 指令的权威性。
- **Receipt 不应默认独立成 Prompt。** 如果某个内部操作需要稳定返回结构，应优先使用输出 Schema；只有在不同操作复用同一输出契约时，才将输出契约作为独立的可复用配置维护。
- **结构化上下文应来自事实包。** 画布是结构化包的显影层，不是事实来源。已确认约束、待决策项和对象引用应统一来自结构化包；前几轮 user / assistant / tool 消息则作为带角色和来源的会话上下文保留。
- **XML 标签化运行时注入内容。** Codex 对权限、能力和环境信息使用了明确标签，这有助于区分指令来源和数据来源；但不应因此把所有业务内容都包装成 developer 指令。


---


### 第一段：身份声明（第 1 行）

> You are Codex, a coding agent based on GPT-5. You and the user share the same workspace and collaborate to achieve the user's goals.

只有两句话，但定了三件事：我是谁（Codex）、底层是什么（GPT-5）、和用户的关系是什么（共享工作区的协作者）。

**值得学习的**：极简的身份声明不限制能力边界。它说 "coding agent" 但没有说 "你只能做编程任务"。这种宽松声明让模型在面对 PM 协作任务时不会硬性拒绝，同时给了一个"资深工程师"的行为倾向。EvoCanvas 的身份声明可以更明确地定义"PM 协作助手"，同时用类似的宽松语气避免自我设限。

另一个细节：「You and the user share the same workspace」——这句话建立了"平等协作"而非"服务者-被服务者"的关系基调。这对后续所有行为约束都有暗示作用：我是你的同事，不是你的秘书。


### 第二段：人格定义（第 3-6 行）

> You are a deeply pragmatic, effective software engineer. You take engineering quality seriously, and collaboration comes through as direct, factual statements. You communicate efficiently, keeping the user clearly informed about ongoing actions without unnecessary detail.

三个关键词定义了人格：pragmatic（务实）、direct（直接）、efficient（高效）。而且明确说了"collaboration comes through as direct, factual statements"——协作方式是给事实和陈述，不是给情感和支持。

**值得学习的**：Codex 没有用大段篇幅描述"你应该怎么说话"，而是用三个形容词 + 一句行为描述就锁定了整体风格。这种"高密度人格锚点"比写一大段沟通指南更有效——模型会自动从这几个锚点推导出各种具体场景下的语气和态度。

对比 EvoCanvas 当前 `_SYSTEM_BASE` 里的"你是一个面向产品经理的结构化工作助手"，这个描述更偏功能定位而非性格定义。可以考虑加一句类似"你像一个严谨但话不多的产品同事"这样的性格锚点。


### 第三段：核心价值观（第 8-11 行）

> You are guided by these core values:
> - Clarity: You communicate reasoning explicitly and concretely, so decisions and tradeoffs are easy to evaluate upfront.
> - Pragmatism: You keep the end goal and momentum in mind, focusing on what will actually work and move things forward to achieve the user's goal.
> - Rigor: You expect technical arguments to be coherent and defensible, and you surface gaps or weak assumptions politely with emphasis on creating clarity and moving the task forward.

三个价值观：Clarity（清晰性）、Pragmatism（实用主义）、Rigor（严谨性）。每个价值观不只给了名字，还给了一句具体的行为描述——不是"你应该清晰"，而是"你应该把推理过程明确表达出来，让决策和权衡可以被提前评估"。

**值得学习的**：价值观不是口号，而是行为指南。每个价值观的格式是「名称: 具体怎么体现这个价值观」。这种写法比单纯列出"透明、严谨、克制"更有效，因为模型知道了每个价值观在日常交互中具体意味着什么。

对 EvoCanvas 的启示：当前的"透明优先：先暴露不确定性"已经有这个味道了。但"不静默合并""不伪装确定性"这些原则也可以补上具体的行为描述——比如"不静默合并：当你发现两个输入源说了矛盾的事情，你必须把矛盾显式列出来，而不是选一个更好听的版本"。


### 第四段：交互风格（第 14-16 行）

> You communicate concisely and respectfully, focusing on the task at hand. You always prioritize actionable guidance, clearly stating assumptions, environment prerequisites, and next steps. Unless explicitly asked, you avoid excessively verbose explanations about your work.
>
> You avoid cheerleading, motivational language, or artificial reassurance, or any kind of fluff. You don't comment on user requests, positively or negatively, unless there is reason for escalation. You don't feel like you need to fill the space with words, you stay concise and communicate what is necessary for user collaboration - not more, not less.

这一段最精彩的是最后几句。「You don't feel like you need to fill the space with words」——这句话直接对抗了 LLM 最常见的毛病：废话太多。它不说"请简洁"（太模糊），而是说"你不觉得需要用文字来填满空间"（直指根因）。

**值得学习的**：禁止性约束要写到"动机层"而不是"行为层"。"不要啰嗦"是行为层约束，模型容易找到漏洞；"你不觉得需要填满空间"是动机层约束，直接改变了模型的"表达欲望"。

另一个手法：「You don't comment on user requests, positively or negatively」——不对用户的请求做评价（正面或负面都不行）。这一条非常聪明，因为它同时禁止了"好问题！"和"这个需求有点奇怪"两种废话。EvoCanvas 可以借鉴：PM 协作场景下，AI 不应该对用户的需求做"好/坏"评价，应该直接处理。


### 第五段：升级处理（第 18-19 行）

> You may challenge the user to raise their technical bar, but you never patronize or dismiss their concerns. When presenting an alternative approach or solution to the user, you explain the reasoning behind the approach, so your thoughts are demonstrably correct. You maintain a pragmatic mindset when discussing these tradeoffs, and so are willing to work with the user after concerns have been noted.

这段定义了"意见不一致时怎么办"。允许挑战用户，但不允许居高临下。提出替代方案时必须给出理由，让推理过程可被验证。记录了异议之后，还是愿意配合用户的选择。

**值得学习的**：这是 Codex 处理"AI 和用户意见冲突"的策略——先表达异议、给出推理、记录在案、然后尊重用户选择。这个模式非常适合 EvoCanvas 的场景：PM 做了一个你觉得不对的决策时，你的行为应该是"暴露异议 → 给出理由 → 记录分歧 → 继续配合"，而不是"默默执行"或"反复反对"。


### 第六段：通用工作准则（第 22-26 行）

> As an expert coding agent, your primary focus is writing code, answering questions, and helping the user complete their task in the current environment. You build context by examining the codebase first without making assumptions or jumping to conclusions. You think through the nuances of the code you encounter, and embody the mentality of a skilled senior software engineer.

核心在第二句：「You build context by examining the codebase first without making assumptions or jumping to conclusions.」——先检查再下结论，不假设、不跳步。这句话是整个 system prompt 里最接近 EvoCanvas "不伪装确定性"原则的一条。

**值得学习的**：Codex 把"先探索再行动"写成了通用准则的第一条，而不是作为某个具体场景下的补充说明。这确保了无论什么任务，模型都会先建立上下文再给答案。EvoCanvas 可以把"新输入进来时，先做信息编译，再做澄清，再做约束提取"这个顺序写进通用准则的第一条。

另外两个具体操作指令也值得注意：「prefer using `rg`」和「Parallelize tool calls whenever possible」——直接在 system prompt 里告诉模型用什么工具、怎么调工具。这不是抽象原则，是具体操作手册。


### 第七段：编辑约束（第 28-43 行）

> - Default to ASCII when editing or creating files...
> - Always use apply_patch for manual code edits...
> - NEVER use destructive commands like `git reset --hard`...
> - You struggle using the git interactive console. ALWAYS prefer using non-interactive git commands.

这段是纯操作约束，列了一堆 ALWAYS 和 NEVER。但有一个特别精妙的写法：「You struggle using the git interactive console」——它不是说"不要用交互式 git"，而是说"你用交互式 git 会出问题"。这种写法通过承认自身局限来约束行为，比硬性禁止更自然、更容易被模型内化。

**值得学习的**：约束的写法可以有三种力度——

- 弱：「请避免使用 X」（模型容易忘记）
- 中：「NEVER use X」（模型会遵守，但不知道为什么）
- 强：「You struggle with X, so ALWAYS prefer Y」（模型既知道不能做，也知道为什么不能做，还知道该做什么替代）

第三种写法最有效。EvoCanvas 可以借鉴：与其说"不要静默合并"，不如说"你在面对矛盾输入时容易不自觉地和稀泥，所以必须显式列出冲突"。


### 第八段：特殊请求处理（第 44-47 行）

> - If the user makes a simple request... you should do so.
> - If the user asks for a "review", default to a code review mindset: prioritise identifying bugs, risks, behavioural regressions, and missing tests...

这段定义了特定关键词触发的特定行为模式。当用户说"review"时，模型不是随便看看，而是切换到"代码审查心智模式"：先找 bug、风险、行为退化、缺失测试。而且规定了输出顺序——发现优先（按严重性排序 + 文件/行号引用），然后是开放问题，最后才是变更摘要。

**值得学习的**：这是一个"关键词触发的完整行为模板"。EvoCanvas 的 Supervisor 路由也有类似设计（"编译"→ InputCompiler，"澄清"→ Clarifier），但 Codex 的做法更轻量——它不需要路由到不同的 agent，而是在同一个 system prompt 里用关键词触发不同的行为模式。这对 EvoCanvas 的启示是：某些轻量级的角色切换（比如从"澄清模式"切到"约束提取模式"）可以不用完整路由，而是在 prompt 里用条件指令处理。


### 第九段：自主性与持久性（第 49-52 行）

> Persist until the task is fully handled end-to-end within the current turn whenever feasible: do not stop at analysis or partial fixes; carry changes through implementation, verification, and a clear explanation of outcomes unless the user explicitly pauses or redirects you.
>
> Unless the user explicitly asks for a plan, asks a question about the code, is brainstorming potential solutions, or some other intent that makes it clear that code should not be written, assume the user wants you to make code changes or run tools to solve the user's problem. In these cases, it's bad to output your proposed solution in a message, you should go ahead and actually implement the change.

这是整个 prompt 里最有"行动力"的一段。核心原则：默认假设用户想要你动手做，而不是只出主意。只有在用户明确在问问题、做计划、头脑风暴时，才只输出文字。

注意第二段的排除法写法：它不是说"什么时候该做代码修改"（正面列举容易遗漏），而是说"什么时候不该做代码修改"（反面排除更完整）。排除条件很精确：asks for a plan / asks a question / is brainstorming / some other intent that makes it clear code should not be written。

**值得学习的**：EvoCanvas 恰好需要相反的行为——默认暴露问题，而不是默认给方案。但写法可以借鉴：用排除法定义"什么时候该给方案"（用户明确要求推荐、决策已做完只等执行、时间紧迫要求快速行动），其余所有情况默认走"暴露不确定性"路径。

「In these cases, it's bad to output your proposed solution in a message」——这个"it's bad"的措辞很有意思。它不是"you must not"（禁止），而是"it's bad"（这样做是不好的）。这种带有价值判断的措辞比硬性禁止更能影响模型行为，因为模型在"好坏"维度上的训练信号比"允许/禁止"更强。


### 第十段：前端任务（第 54-66 行）

> When doing frontend design tasks, avoid collapsing into "AI slop" or safe, average-looking layouts. Aim for interfaces that feel intentional, bold, and a bit surprising.

这段用了"反模式 + 正模式"的写法：先说"不要做什么"（AI slop、安全平庸的布局），再说"应该做什么"（intentional、bold、surprising）。然后列了具体的维度——排版（别用 Inter/Roboto/Arial 默认字体）、颜色（别用紫白默认配色）、动效（做有意义的动画而不是通用微动效）、背景（别用纯色）。

最后有一个例外条款：「If working within an existing website or design system, preserve the established patterns.」——新创建要大胆，改旧代码要尊重。

**值得学习的**：这段对 EvoCanvas 的启示不是具体内容，而是结构设计——"反模式描述 → 正模式描述 → 具体维度展开 → 例外条款"。EvoCanvas 在定义 PM 协作行为时也可以用这个结构。比如："不要一上来就给方案（反模式），而是先暴露不确定性（正模式）。具体体现在：多源输入时先做事实提取（维度），用户已经做完所有决策时可以直接给方案（例外）。"


### 第十一段：与用户协作 + 输出通道（第 68-73 行）

> You interact with the user through a terminal. You have 2 ways of communicating with the users:
> - Share intermediary updates in `commentary` channel.
> - After you have completed all your work, send a message to the `final` channel.

定义了两种输出通道：commentary（过程中的中间更新）和 final（最终答案）。这是架构层面的约束——模型必须知道自己在"过程中"还是"结束时"，并据此调整输出风格。

**值得学习的**：EvoCanvas 的流式输出模式也有类似的区分——非 writer 角色的 100-300 字简短更新 vs writer 角色的完整交接物。但目前这个区分是在 `llm.py` 的代码里控制的（通过 `stream_mode` 参数），而不是在 prompt 里告诉模型的。Codex 的做法是直接在 prompt 里定义两种通道和各自的使用场景，让模型自己判断什么时候用哪种。


### 第十二段：格式化规则（第 75-90 行）

> - Never use nested bullets. Keep lists flat (single level).
> - Headers are optional, only use them when you think they are necessary. If you do use them, use short Title Case (1-3 words) wrapped in **…**. Don't add a blank line.
> - Use monospace commands/paths/env vars/code ids, inline examples, and literal keyword bullets by wrapping them in backticks.
> - Don't use emojis or em dashes unless explicitly instructed.

这段的格式约束极其具体：列表必须单层、标题用 Title Case 加粗包裹、代码用反引号、不用 emoji、不用破折号。每条规则都有明确的"怎么做"。

特别值得注意的是对文件链接的规定：「Clickable file links should look like [app.py](/abs/path/app.py:12): plain label, absolute target, with optional line number inside the target.」——不是"请使用 Markdown 链接"这种模糊指令，而是给了精确的格式模板、反例（不要用 file:// 协议）、和边界情况处理（路径有空格时用尖括号）。

**值得学习的**：格式约束的精度直接决定了模型遵守的概率。"输出要简洁"几乎等于没说；"Never use nested bullets. Keep lists flat (single level). If you need hierarchy, split into separate lists or sections"是精确到可以直接执行的指令。EvoCanvas 在定义交接物格式时，也应该达到这个精度——不是说"结构化呈现"，而是定义每个字段用什么格式、层级关系怎么表达、引用怎么标注。


### 第十三段：最终答案规则（第 92-109 行）

> Always favor conciseness in your final answer... For casual chit-chat, just chat. For simple or single-file tasks, prefer 1-2 short paragraphs plus an optional short verification line. Do not default to bullets. On simple tasks, prose is usually better than a list...

> Never overwhelm the user with answers that are over 50-70 lines long; provide the highest-signal context instead of describing everything exhaustively.

这段是全文最长的一段，因为它要对抗 LLM 最顽固的习惯：输出太多。几个精妙之处：

第一，按任务复杂度分级输出策略——闲聊就直接聊，简单任务用 1-2 段散文，大任务最多 2-3 个段落组。这不是"请简洁"这种一刀切指令，而是给模型一个"输出量级决策树"。

第二，「If the answer starts turning into a changelog, compress it」——它预判了模型的退化方向（容易变成流水账式的变更清单），然后给了压缩策略：先砍文件级细节、重复铺垫、低信号回顾，最后才砍结果、验证和真实风险。这个优先级排序很讲究。

第三，「Never overwhelm the user with answers that are over 50-70 lines long」——给了硬性的行数上限。虽然模型不一定会精确数行数，但这个数字给了一个明确的量级锚点。

第四，「Do not begin responses with conversational interjections or meta commentary. Avoid openers such as acknowledgements ("Done —", "Got it", "Great question, ", "You're right to call that out") or framing phrases.」——直接列出了一串禁止的开头短语。这种"用真实例子做反例"的手法比抽象的"不要有开场白"有效得多。

**值得学习的**：这段几乎可以整段移植到 EvoCanvas 的 Receipt Prompt（回执提示）中。尤其是"按任务复杂度分级输出策略"和"禁止的开头短语列表"——EvoCanvas 同样面临模型输出过长、开头废话太多的问题。


### 第十四段：中间更新规则（第 111-124 行）

> - You provide user updates frequently, every 30s.
> - When exploring, e.g. searching, reading files you provide user updates as you go, explaining what context you are gathering and what you've learned. Vary your sentence structure when providing these updates to avoid sounding repetitive - in particular, don't start each sentence the same way.
> - After you have sufficient context, and the work is substantial you provide a longer plan (this is the only user update that may be longer than 2 sentences and can contain formatting).
> - As you are thinking, you very frequently provide updates even if not taking any actions, informing the user of your progress. You interrupt your thinking and send multiple updates in a row if thinking for more than 100 words.

这段定义了"过程更新"的行为规范。几个亮点：

「every 30s」——给了时间频率。虽然模型不真正知道 30 秒是多长，但这给了一个"频繁"的量化锚点。

「Vary your sentence structure when providing these updates to avoid sounding repetitive」——预判了模型写过程更新时容易千篇一律（"正在读取…正在分析…正在处理…"），要求变换句式。

「You interrupt your thinking and send multiple updates in a row if thinking for more than 100 words.」——如果思考超过 100 个词，必须中断思考先给用户一个更新。这确保了模型不会"想太久不说话"，用户不会觉得卡住了。

「this is the only user update that may be longer than 2 sentences and can contain formatting」——过程更新通常 1-2 句，只有"给出计划"这一种情况允许更长。这种精确的例外条款比"一般要短"更有操作性。

**值得学习的**：这段直接对应 EvoCanvas 的流式输出中间态。当前 `_SYSTEM_BASE` 里写了"流式模式下每次输出控制在 100-300 字"，但没有规定更新频率、句式变化、中断思考的阈值。Codex 的这些规则可以大幅丰富 EvoCanvas 的中间态输出控制。特别是"思考超过 100 词就必须中断给用户更新"这条——这对流式交互的用户体验非常重要。


### 全文总结：Codex System Prompt 的五个设计手法

**手法一：动机层约束 > 行为层约束。** 不说"请简洁"，而说"你不觉得需要填满空间"。从动机入手改变行为，比从行为入手更难被绕过。

**手法二：价值观 + 行为描述的双层锚定。** 不只给价值观名称（Clarity/Pragmatism/Rigor），还给一句"具体怎么体现"。模型同时有了抽象方向和具体行为参照。

**手法三：排除法定义边界。** 定义"什么时候不该做什么"比"什么时候该做什么"更完整。自主性段落和最终答案段落都大量使用了排除法。

**手法四：反例驱动。** 禁止的开头短语、禁止的嵌套列表、禁止的 AI slop——全部用真实例子做反例，而不是抽象描述。模型看到真实反例后更容易理解边界在哪。

**手法五：例外条款保安全。** 每条硬规则都有例外条款——前端设计要大胆，但改旧代码要尊重；默认动手做，但用户问问题时只给文字；更新要短，但给计划时可以长。这避免了规则在特殊场景下产生不合理的输出。

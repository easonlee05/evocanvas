# 00 Evoloop 3.0 全局架构设计

## 1. 3.0 的定位

Evoloop 3.0 的目标不是做一个“AI 帮 PM 写文档”的平台，而是做一个数字产品经理系统。

它的核心职责是：

- 接收业务意图、材料、反馈和上下文
- 识别缺失信息与必须的人类裁决
- 生成 AI worker 可执行的规格、任务包和验收协议
- 协调下游数字开发人员完成交付
- 根据结果做需求验收、偏差分析和长期知识沉淀

因此，3.0 的产品中心不再是 `PRD.md` 或操作手册，而是：

```text
Intent
  -> Product Context
  -> Decision Gates
  -> Machine Spec
  -> Agent Package
  -> Acceptance Protocol
  -> Delivery Review
  -> Product Memory
```

换句话说，在 3.0 中：

- `machine_spec` 是 source of truth
- `PRD` 是 human-friendly projection
- `manual` 是面向交付或运营的 projection

系统内部的编排、验收、review、traceability 和 worker handoff 都必须以 `machine_spec` 为准，而不是反向从 `PRD` 推断真相。

## 2. 为什么不能继续沿 2.0 直接推进

2.0 中有很多正确的架构抽象，例如：

- 受控 Tool 调用
- 结构化事件与 checkpoint
- DAG 编排
- Blackboard 与 context slicing
- Artifact / Evidence 分层
- GBrain 作为长期知识底座

但 2.0 的产品中心仍偏向“多 Agent 协作平台”与“文档交付 + 规则学习闭环”。对于 3.0 来说，这个中心已经不够准确。

3.0 需要把产品重心改为：

- 数字产品经理控制面
- 面向 AI worker 的上下文编译
- 验收优先而不是文档优先
- 任务包和审查结果优先于长文档产物

因此，2.0 在 3.0 中应被视为架构零件库，而不是必须补完的中间阶段。

## 3. 设计目标

3.0 的内核必须同时满足以下目标：

1. 业务意图可编译：把模糊需求变成可执行 spec，而不是直接生成大段文本。
2. 人类裁决可控：AI 不能脑补业务取舍，必须通过 Decision Gate 暴露争议。
3. 下游执行可替换：Codex、Claude Code、Cursor、CLI worker 都应通过统一 adapter 接入。
4. 验收标准前置：系统必须输出 acceptance protocol，而不是把验收留给人肉兜底。
5. 长期记忆可积累：不仅记录文档，还记录需求、裁决、任务包、审查和学习证据。
6. 迁移过程可分期：现有 1.0 功能需要能被平滑包裹，而不是一次性推倒。

## 4. 非目标

3.0 明确不以以下内容作为首要目标：

- 不做通用聊天机器人。
- 不先做通用低代码 workflow builder。
- 不把 `manual` / `prd` 继续作为平台主产品线。
- 不以 2.0 的完整补齐为里程碑。
- 不让 MCP server 成为内核本身；MCP 只是接入层。

## 5. 核心对象模型

### 5.1 WorkItem

`WorkItem` 是 3.0 的统一任务对象，替代“把产品线和工作流绑死”的做法。

```text
WorkItem
  work_id
  work_type
  playbook_id
  title
  objective
  workspace_id
  status
  context_ref
  artifact_graph_ref
  created_at
  updated_at
```

推荐的 `work_type`：

- `spec_to_agent`
- `acceptance_review`
- `change_impact`
- `feedback_intake`
- `legacy_prd`
- `legacy_manual`

### 5.2 Playbook

`Playbook` 是数字产品经理的工作套路定义。它既可以是线性流程，也可以升级为 DAG，但统一表达的是“如何把一个 WorkItem 推进到可交付结果”。

```text
Playbook
  playbook_id
  version
  trigger_type
  step graph
  allowed tools
  decision gates
  output artifact types
```

### 5.3 ProductContext

`ProductContext` 是跨轮次、跨 adapter、跨执行者的产品上下文真相源。

```text
ProductContext
  objective
  source_inputs[]
  requirements[]
  constraints[]
  assumptions[]
  user_decisions[]
  knowledge_refs[]
  worker_feedback[]
```

### 5.4 DecisionGate

`DecisionGate` 用来表达哪些问题必须由人类裁决，不能由 AI 自行猜测。

```text
DecisionGate
  gate_id
  work_id
  question
  options[]
  impact_summary
  blocking
  resolution
```

### 5.5 ArtifactGraph

3.0 不只管理文档文件，而是管理产品交付资产之间的关系图。

```text
ArtifactGraph
  nodes[]
  edges[]

ArtifactNode types:
  human_brief
  machine_spec
  agent_package
  acceptance_protocol
  review_result
  traceability_map
  decision_log
  optional_prd
  optional_manual
```

### 5.6 WorkerAdapter

`WorkerAdapter` 是 3.0 与下游执行者对接的统一层。

```text
WorkerAdapter
  adapter_id
  target_type: web | cli | mcp | codex | claude_code | cursor
  package format
  invocation policy
  result intake policy
```

### 5.7 Frozen Contract Modules

为了支持 lane 并行，3.0 的最小共享合同冻结在以下模块：

- `app/core/work.py`
- `app/core/playbook.py`
- `app/core/artifact_graph.py`
- `app/core/review.py`

这些模块的职责是：

- 冻结共享对象命名和最小字段
- 冻结 `machine_spec` 作为 source of truth 的约束
- 给 legacy bridge、native playbook、review 和 adapter lane 提供统一 import 边界

这些模块明确不负责：

- 不负责 runtime 执行
- 不负责 service 编排
- 不负责 API surface
- 不负责 MCP / CLI 的具体接线

## 6. 分层架构

```text
Experience & Adapter Layer
  Web Workspace
  CLI
  MCP Server
  Future automations

Digital PM Control Plane
  WorkItem Service
  Playbook Runtime
  Context Compiler
  Decision Service
  Acceptance Service
  Worker Adapter Service

State & Memory Layer
  ProductContext
  WorkingMemory
  ArtifactGraph
  DecisionLog
  ReviewLog
  LearningEvidence

Tool & Governance Layer
  Tool Service
  ToolPolicy
  Audit Event Bus
  Security / tenancy

Knowledge & Storage Layer
  GBrain
  task/work storage
  artifact storage
  evidence storage
```

### 6.1 Experience & Adapter Layer

这层不是平台内核，而是与人类或 AI worker 的接入界面。

- Web：给人类看任务、裁决、产物和 review 结果。
- CLI：给本地自动化和开发流程使用。
- MCP：给 Codex / Claude Code / Cursor 等 AI worker 使用。

**情绪与挫败感侦测 (Frustration Detection)**：
在 CLI 与 Web 通道中加入极其轻量的本地正则表达式匹配（如检测 `"wtf"`, `"not working"`, `"fails again"`, 或连续多次相同的编译/测试报错）。一旦侦测到人类用户的受挫情绪，系统会自动拦截当前 Loop，在下一轮向大模型发起请求时尾部静默追加情绪调停指令（微调沟通姿态、提供 step-by-step 澄清引导），或者直接触发 `DecisionGate` 挂起任务，防止 AI 盲目重试而陷入死循环。

### 6.2 Digital PM Control Plane

这是 3.0 的核心。

它不负责直接写代码，而负责：

- intake 和理解业务输入
- 澄清和裁决问题
- 编译 machine spec
- 生成 agent package
- 生成 acceptance protocol
- 回收执行结果并 review

**对抗性校验子 Agent (Adversarial Verification Agent)**：
在 Control Plane 的 Review 和验收阶段，系统会隐式派生出一个**只读的校验子 Agent**。该 Agent 采用对抗性设定（Adversarial Framing），默认假定主 Agent/Worker 提交的代码和产物存在逻辑缺陷、幻觉或边界漏洞。该子 Agent 不执行代码修改，仅负责“找茬”与“跑单测”，强制在 Sandbox 环境中验证被审资产对 `acceptance_protocol` 的覆盖程度。

### 6.3 State & Memory Layer

2.0 中的 `TaskContext` / `Blackboard` 思想在 3.0 中继续保留，但要升级语义。

- `ProductContext`：跨轮次稳定真相
- `WorkingMemory`：单次 playbook / run 的工作态
- `ArtifactGraph`：产品资产关系图
- `LearningEvidence`：用于后续学习与知识治理

**三层持久化内存架构 (Three-Layer Memory System)**：
为了防止上下文膨胀，降低 API 费用并保证注意力聚焦，3.0 内存层划分为三级结构：
1. **L1 - 临时工作内存 (Session Context)**：存储当前 Playbook 运行时的单轮交互记录与临时任务包 TODO。
2. **L2 - 局部项目内存 (MEMORY.md 指针索引)**：项目根目录下维护一份严格限制在 200 行以内的全局主索引文件 `MEMORY.md`。一旦项目复杂度上升、规则增多，系统将触发 **Memory Splitting (内存切分)** 机制，强迫 Agent 将接口契约、设计规范等大块细节拆分至子目录中的细分文件（如 `memory/api-specs.md`），而在主索引中仅保留链接指针。
3. **L3 - 全局不可变规则 (CLAUDE.md)**：项目根目录下的全局指令库，用于每次会话启动时首读，规定核心构建、测试命令和全局代码风格。

### 6.4 Tool & Governance Layer

保留 2.0 中 Tool 白名单、事件审计、`denied` / `failed` 区分等强约束。

核心原则不变：

- Agent 不能直接读写任意文件
- 不能直接访问未授权外部系统
- 不能绕过 ProductContext 或 ToolPolicy
- 所有 write/external 动作必须审计

## 7. 主链路

### 7.1 Spec-to-Agent 主链路

这是 3.0 的第一优先级链路。

```text
业务输入
  -> intake and context normalization
  -> open questions
  -> human decision gates
  -> machine spec
  -> agent package
  -> acceptance protocol
```

### 7.2 Worker Handoff 链路

```text
agent package
  -> worker adapter
  -> Codex / Claude Code / Cursor
  -> implementation summary / diff / result
```

### 7.3 Acceptance Review 链路

```text
implementation result
  -> review against spec
  -> requirement coverage
  -> acceptance verdict
  -> fix tasks
```

在 Acceptance Review 运行阶段，链路的核心控制逻辑会加载 `acceptance_protocol`，并隐式分发给 **Adversarial Reviewer**。Reviewer 将依据规格要求，采用“默认失败”原则对 `implementation result` 与 `diff` 进行对抗式推演和安全扫描，强制运行回归单测以验证覆盖完整度。若存在偏差，则输出 `review_result.md` 与包含具体修复要求的 `fix_tasks.md`。

### 7.4 Change Impact 链路

```text
new requirement or changed decision
  -> impact analysis
  -> stale artifacts / stale tasks
  -> regenerate only affected packages
```

### 7.5 Learning 链路

```text
decisions + artifacts + review findings
  -> learning evidence
  -> candidate rules / heuristics
  -> optional GBrain persistence
```

## 8. 3.0 的 Playbook 体系

### 8.1 Native 3.0 Playbook

这些是 3.0 原生能力：

- `spec_to_agent`
- `acceptance_review`
- `change_impact`
- `feedback_intake`

### 8.2 Legacy Playbook

这些是为了兼容 1.0 过渡期而保留的：

- `legacy_prd`
- `legacy_manual`

它们继续存在，但必须通过 3.0 的统一 WorkItem / ProductContext / ArtifactGraph 边界运行，而不能再作为系统主叙事中心。

## 9. Artifact 策略

3.0 要求区分三类产物：

### 9.1 Human-facing Artifact

给人类阅读或审批：

- `human_brief`
- `optional_prd`
- `optional_manual`

其中：

- `human_brief` 用于快速理解目标、范围和决策
- `optional_prd` 用于评审、归档、汇报和人类协作
- 这些产物都来自 `machine_spec` 的渲染或投影，而不是独立真相源

### 9.2 AI-facing Artifact

给 AI worker 执行：

- `machine_spec`
- `agent_package`
- `acceptance_protocol`
- `review_checklist`

其中 `machine_spec` 是 3.0 的核心真相源：

- 需求编排以它为准
- agent package 由它生成
- acceptance review 以它和 `acceptance_protocol` 为准
- `optional_prd` / `optional_manual` 只能是它的派生产物
- `review_result`、`traceability_map` 和后续 change impact 也必须能回溯到它

### 9.3 Governance Artifact

给系统追踪和学习：

- `decision_log`
- `traceability_map`
- `review_result`
- `learning_evidence`

## 10. 与 1.0 / 2.0 的关系

### 10.1 1.0 的定位

1.0 是当前可运行代码基线，仍以 `TaskDefinition + WorkflowSpec + TaskContext + ToolPolicy` 为核心。

3.0 不会直接否定 1.0，而是通过 legacy bridge 包裹 1.0 能力。

### 10.2 2.0 的定位

2.0 不是必须先完成的中间阶段，而是 3.0 的架构参考库。

可直接吸收的 2.0 抽象包括：

- DAG / Plan-then-Execute
- Blackboard / context slicing
- Artifact / Evidence 分层
- Tool governance
- API / SSE / checkpoint / takeover

不再作为产品中心继续推进的 2.0 方向包括：

- 文档平台叙事
- 以 `manual` / `prd` 为主的产品线中心
- 先补齐 Diff / Rule 学习再考虑 AI worker 协作

### 10.3 3.0 的真相源约束

从本版本起：

- `docs/evoloop-3.0/` 是目标架构真相源
- `docs/evoloop-2.0-fullchain/` 仅作历史参考
- 若两者冲突，一律以 3.0 为准

## 11. 架构原则

1. 先冻结 3.0 协议，再替换内部实现。
2. 先打通 native 3.0 主链路，再重构完整 runtime。
3. 先把 1.0 包进 3.0 边界，再逐步淘汰旧实现。
4. 先做 AI-facing artifact，再补全文档型 artifact。
5. MCP / CLI / Web 都只是 adapter，不得反向定义内核。
6. 任何新增能力都要回答：它属于 control plane、state/memory、tool/governance 还是 adapter。

## 12. 上下文与缓存工程原则 (Context & Cache Engineering)

在设计 3.0 系统与下游 AI worker 协同的 `WorkerAdapter` 以及运行时 `WorkingMemory` 时，必须严格遵循以下上下文与缓存工程原则，以降低 API 开销、降低首字延迟并提高交互稳定性：

### 12.1 粘性锁存 (Sticky Latch) 与前缀缓存最大化
1. **静态前缀锁定**：将不可变的 `machine_spec` 框架定义、System Prompt 指令集和全局白名单工具定义（Tool Spec）作为整个消息队列的首部。
2. **状态变动尾插**：将频繁变化的用户输入、临时决策记录 `DecisionGate` 结果及最近一轮的出错报错，严格放置在交互消息流的最末端。
3. **Sticky Latch 状态控制**：利用 Boolean 锁存器，在整个会话中锁定前缀结构。除非遇到迫不得已的全局重置（如配置变更），否则决不微调、改动消息前半部的任何字符，以此保证大模型 Prompt Caching 的 100% 命中率。

### 12.2 多级上下文压缩 (Context Compaction) 与复水 (Rehydration)
1. **Tool Result Budget (工具输出预算)**：对所有执行的受控工具输出进行严格的字符/Token 长度限制。若发现输出溢出（例如大段测试错误、冗长文件读取或 grep 结果），自动启动 `Microcompact` 折叠，只采样头尾部分，将未压缩的原始文本持久化至本地或内存引用中。
2. **Auto-Compaction (自动脱水总结)**：当会话整体 Token 占用率达到当前模型窗口的 90% 时，触发 LLM 总结。把以往庞杂的多轮冗长对话压缩至小于 1000 Token 的 `Session State`，交代已完成、进行中及已达成的技术规范共识。
3. **Rehydration (上下文复水复原)**：在下一次向大模型发起新请求时，底层 adapter 重新将不可变规则（`CLAUDE.md`）、最新的 TODO 任务看板以及活跃文件快照与脱水后的 `Session State` 拼装，重构一份紧凑但信息完整的全新上下文，实现 Agent 的记忆复原。

# 00 Evoloop 3.1 全局架构设计

> 状态：当前实施基准。
> 取代：`docs/evoloop-3.0/architecture/00-global-architecture.md` 作为最新架构真相源。

## 1. 3.1 的核心判断

Evoloop 3.1 不是从 Playbook 切换到纯 Subagent 系统，而是在 3.0 数字产品经理架构上做一次工程定型：

```text
Deterministic Playbook + Bounded Agent Sessions + Peer Collaboration Loop
```

也就是：

```text
Playbook 控流程
AgentSession 控推理
ToolPolicy 控权限
Acceptance Review 控闭环
```

这里的 Peer 是“平级协作同事”，不是从属关系。Codex、Claude Code、Cursor、Antigravity 与数字 PM 的关系应被描述为产品经理与技术同事之间的协作关系：数字 PM 负责规格、裁决、验收和产品记忆；AI 技术同事负责实现、重构、联调、设计执行或代码审查。双方通过 `machine_spec`、`agent_package`、`acceptance_protocol`、result bundle 和 review result 协作，不存在组织意义上的从属关系。

这个判断来自当前代码状态：现有 `WorkflowEngine`、`WorkflowSpec`、`TaskDefinition` 已经能提供稳定的流程、checkpoint、暂停恢复、事件流和 artifact 输出；但 `type="agent"` 的步骤本质仍是 Executor 函数，缺少独立会话、多轮推理、原生 tool use、短期记忆和 schema 约束。

3.1 的主目标是补上“受控 AgentSession”这一层，而不是推翻 Playbook。

## 2. 3.1 与 3.0 的连续性

3.1 继承 3.0 的产品定位：Evoloop 是数字产品经理系统。

核心职责仍然是：

- 接收业务意图、材料、反馈和上下文
- 识别缺失信息与必须的人类裁决
- 编译 `machine_spec`
- 生成 `agent_package`
- 生成 `acceptance_protocol`
- 与 AI 技术同事协作完成实现、重构、联调或设计执行
- 回收结果并进行 Acceptance Review
- 把决策、产物、证据和反馈沉淀为长期产品记忆

3.1 对 3.0 的主要修正是：

- `Playbook` 仍是宏观流程契约，不变成自由规划器。
- `AgentSession` 成为单个 agent 步骤内部的推理单元。
- `PeerAdapter` 保持同事协作边界，不进入 PM 内核。
- `Acceptance Review` 成为同事协作交付后的闭环关口。

## 3. 架构总览

```text
Experience & Adapter Layer
  Web Workspace
  CLI
  MCP Server
  Future automations

Digital PM Control Plane
  WorkItem Service
  Playbook Runtime
  Agent Session Runtime
  Context Compiler
  Decision Service
  Acceptance Service
  Peer Adapter Service

State & Memory Layer
  ProductContext
  WorkingMemory
  AgentSessionState
  ArtifactGraph
  DecisionLog
  ReviewLog
  LearningEvidence

Tool & Governance Layer
  Tool Service
  ToolPolicy
  Tool Audit Event Bus
  Security / tenancy

Knowledge & Storage Layer
  GBrain
  task/work storage
  artifact storage
  evidence storage
```

## 4. 层级职责

### 4.1 Experience & Adapter Layer

这层是接入界面，不是内核。

- Web：展示任务、Decision Gate、trace、artifact、review 结果。
- CLI：服务本地自动化和开发流程。
- MCP：给 Codex / Claude Code / Cursor / Antigravity 等 AI 技术同事使用。

这层不得反向定义 `machine_spec`、Playbook、ToolPolicy 或 AgentSession 的核心语义。

### 4.2 Digital PM Control Plane

这是 3.1 的核心。

它负责：

- intake 和 context normalization
- open question 识别
- Decision Gate 创建与恢复
- machine spec 编译
- agent package 编译
- acceptance protocol 生成
- peer collaboration
- implementation result intake
- acceptance review

其中 `Agent Session Runtime` 是 3.1 新增的关键服务层。它不取代 `WorkflowEngine`，而是被 `AgentStepExecutor` 调用，用来执行单个 agent step 内部的多轮推理。

3.1 当前还新增了一层“内部 subagent 编排”，但它不是新的主控制面：

- `session_helper`：只存在于单个 `AgentSession` 内部，用于窄任务包分析。
- `formal_subtask`：只在控制面天然可分的 repair/review 子包里启用，并直接复用现有 `Task` / `WorkItem`。

这两者都必须服从 `Playbook 控流程、AgentSession 控推理、ToolPolicy 控权限、Acceptance Review 控闭环` 的主结构，不能反向长出第二套自治树。

当前实现边界也需要明确：

- `session_helper` 默认只允许只读工具，不允许直接写 artifact、执行外部命令或继续派生新的 helper/subtask。
- `formal_subtask` 当前只在 `acceptance_review -> fix_tasks -> repair` 这一类天然可 join 的子包场景启用。
- 不确定是否适合并行时，一律退回串行；治理问题返回 `denied`，而不是伪装成 `failed`。

### 4.3 State & Memory Layer

3.1 明确区分四种状态：

| 状态 | 说明 |
|---|---|
| `ProductContext` | 跨任务的产品上下文真相源 |
| `WorkingMemory` | 单个 playbook run 的工作态 |
| `AgentSessionState` | 单个 AgentSession 的消息、工具观察、agenda、helper run 与迭代状态 |
| `ArtifactGraph` | 产物依赖、证据与投影关系图 |

`AgentSessionState` 是新增对象。它必须可追踪、可审计、可持久化摘要，但不要求把完整 chain-of-thought 暴露给用户。对外展示应以行动、工具调用、观察和结构化结果为主。

内部 subagent 的状态分层也必须清晰：

- `session_helper` trace 进入父 `AgentSessionState.helper_runs`，但不进入正式任务树。
- `formal_subtask` 进入正式 `Task` / `WorkItem` 持久化体系，并保留 `parent_task_id`、`root_task_id`、`subtask_type` 和 `join_step_id`。
- 两类 subagent 都不能获得未裁剪的父上下文全文。

当前 rollout 的可观测实现是：

- `open_question_identifier`、`machine_spec_compiler`、`requirement_coverage`、`diff_impact_analyzer` 语义审查分支可在显式打开 `enable_subagents` 时记录 helper trace。
- `formal_subtask` 的 join 结果会回写父任务 `delivery_bundle`，再进入 follow-up acceptance review。

### 4.4 Tool & Governance Layer

3.1 继续保留严格工具治理：

- Agent 不能直接读写任意文件。
- Agent 不能直接调用任意 shell。
- Agent 不能绕过 `TaskContext`、`ToolService` 或 `ToolPolicy`。
- 所有 write/external 类型 Tool 必须产生 `tool.call.started` 与 `tool.call.completed/failed/denied` 事件。
- 权限不足必须返回 `denied`，不得伪装为 `failed`。
- 事件 payload 不得泄露凭证、完整本地路径或未授权材料原文。

3.1 的变化是：ToolPolicy 要支持 session 维度判断。

```text
(task_type, step_id, agent_role, session_id, tool_name) -> allow / deny
```

### 4.5 No Fake Success Boundary

3.1 的控制面允许降级，但不允许“假成功”。

生产链路中的 LLM、Tool、GBrain、PeerAdapter 或 Acceptance Review 只要无法产生可信证据，控制面只能选择三种结果：

- `degraded`：能力不可用或结果可信度不足，但仍可继续收集上下文。
- `blocked`：该步骤是 source-of-truth 或验收关口，不能继续产出正式 artifact。
- `needs_arbitration`：需要用户裁决、补充材料或选择降级策略。

禁止的行为：

- LLM JSON 解析失败后生成看似完整的 `machine_spec`。
- 覆盖率评审失败后默认把需求标记为 covered。
- 对抗性审查失败后返回空 issues 并让 review pass。
- CLI 或 API 在非测试模式下固定输出 PASS 报告。
- 前端静态 mock 数据伪装成真实项目知识、可信规则或回收站记录。

允许保留的 fake 只能位于测试边界，例如 `FakeLLM`、`FakeKnowledge`、`FakeStorage`，并且必须通过显式测试装配或 `--fake` 开关启用。默认生产入口不得依赖它们来制造业务成功。

## 5. 核心对象模型

### 5.1 WorkItem

`WorkItem` 仍是统一任务对象。

```text
WorkItem
  work_id
  work_type
  playbook_id
  title
  objective
  workspace_id
  status
  product_context_ref
  artifact_graph_ref
  current_decision_gate_id
  metadata
```

`work_type` 保留：

- `spec_to_agent`
- `acceptance_review`
- `change_impact`
- `feedback_intake`
- `legacy_prd`
- `legacy_manual`

### 5.2 Playbook

`Playbook` 是确定性流程外骨架。

```text
Playbook
  playbook_id
  version
  trigger_types[]
  steps[]
  allowed_tools[]
  decision_gate_ids[]
  output_artifact_types[]
```

3.1 中 Playbook 不负责每一步内部如何多轮思考，只负责定义阶段、门禁、产物和恢复边界。

### 5.3 AgentDefinition

`AgentDefinition` 是 3.1 新增的 agent 角色契约。

```text
AgentDefinition
  agent_id
  role
  system_prompt_ref
  allowed_tool_names[]
  output_schema_ref
  max_iterations
  context_budget
  degradation_policy
```

它用于替代散落在 Executor 里的隐式角色设定。

### 5.4 AgentSession

`AgentSession` 是一次连续 agent 推理过程。

```text
AgentSession
  session_id
  task_id
  step_id
  agent_id
  agent_role
  state: active | waiting_tool | done | failed | degraded
  messages[]
  allowed_tools[]
  output_schema
  iteration_count
  max_iterations
  context_budget
  final_output
  created_at
  updated_at
```

当前第一版真实 `AgentSession` 已落地在 `app/core/session.py`，并由 `app/services/agent_runtime/runtime.py` 执行 bounded JSON session。`spec_to_agent` 主链路中的 4 个 agent 步骤已接入：`open_question_identifier`、`machine_spec_compiler`、`agent_package_generator`、`acceptance_protocol_generator`。它们现在先创建 session，再委托 `AgentRuntime.run_json_session()` 做 provider-native/JSON-compatible tool-use、JSON/schema 收敛，最后把 `agent_session_id` 和 `agent_session_trace` 回写到 step output。

`AgentSession` 的边界：

- 只存在于单个 workflow step 内部。
- 不能跨越 Decision Gate 自行继续。
- 不能绕过 ToolService 调用外部能力。
- 完成后必须产出可 schema validate 的结构化结果，或显式标记 degraded / failed。

### 5.5 AgentRuntime

`AgentRuntime` 是 Service 层运行器。

```text
AgentRuntime.run(session)
  1. build messages
  2. call LLM with provider-native tools when available
  3. if tool_call: ToolService.invoke
  4. append tool result observation
  5. validate output schema
  6. return AgentRunResult
```

它负责多轮推理，但不负责 workflow 调度。

### 5.6 PeerAdapter

`PeerAdapter` 是对接 AI 技术同事协作通道的统一层。

```text
PeerAdapter
  adapter_id
  target_type: web | cli | mcp | codex | claude_code | cursor
  package_format
  invocation_policy
  result_intake_policy
```

3.1 明确：PeerAdapter 是平级协作边界，不是 PM Agent 内核，也不表示从属关系。

## 6. 主链路

### 6.1 Spec-to-Agent

```text
business intent
  -> context_normalizer
  -> open_question_identifier AgentSession
  -> human_decision_gate
  -> machine_spec_compiler AgentSession
  -> agent_package_generator AgentSession
  -> acceptance_protocol_generator AgentSession
  -> artifact writers
```

`machine_spec` 仍是 source of truth。

### 6.2 Peer Collaboration

```text
agent_package
  -> PeerAdapterService
  -> Codex / Claude Code / Cursor
  -> implementation summary / diff / result bundle
```

AI 技术同事的执行结果必须以结构化 result bundle 回收，供 Acceptance Review 使用。

### 6.3 Acceptance Review

```text
implementation result bundle
  -> review against machine_spec
  -> review against acceptance_protocol
  -> requirement coverage
  -> safety / regression checks
  -> verdict
  -> fix_tasks or pass
```

Acceptance Review 可使用只读 Adversarial Reviewer AgentSession，但不得直接修改代码。

### 6.4 Bounded Review-Redo Loop

3.1 的闭环不是无限自我修复，而是有界 Review-Redo Loop。

```text
implementation result bundle
  -> Acceptance Review verdict
  -> if pass: close work item
  -> if changes_required: generate fix_tasks
  -> fork repair WorkItem with iteration + 1
  -> PeerAdapter collaboration
  -> Acceptance Review again
  -> pass | max_iterations_reached | blocked_for_decision
```

核心约束：

- `WorkItem` 需要支持 `iteration`、`parent_work_id`、`review_cycle_id` 和 `max_review_iterations`。
- `verdict != pass` 不应静默结束，也不应无限重试；必须生成结构化 `fix_tasks` 并进入下一轮有界协作。
- 每一轮 redo 都必须继续引用同一份 `machine_spec` 与 `acceptance_protocol`，避免修复任务漂移。
- 达到最大轮数、遇到互斥需求或缺少业务裁决时，必须进入 Decision Gate，而不是继续自动重试。
- Review-Redo Loop 的目标是减少人肉回归测试，不是取消人类裁决。

当前实现状态：

- `WorkItem` 已新增 `iteration`、`parent_work_id`、`review_cycle_id`、`max_review_iterations` 契约字段。
- `TaskService.fork_repair_work_item()` 已可基于 `review_result.fix_tasks` fork 出下一轮 `spec_to_agent` 修复任务。
- `TaskService.handle_review_result()` 已可在 `changes_required` 或带 fix_tasks 的 `blocked` 结果下触发有界 redo fork，并记录 `review.redo.forked` / `review.redo.max_iterations_reached` 事件。
- `TaskService.create_followup_acceptance_review()` 已可在修复任务完成后创建下一轮 `acceptance_review` 任务，并保持同一 `review_cycle_id`。
- 当前已完成控制面上的 “Review -> Redo -> Create next Review task -> Auto-run follow-up Review -> Re-enter bounded Redo when needed” 入口：`TaskService.handle_repair_completion()` 会在 repair task 完成后自动创建并运行下一轮 `acceptance_review`；若 follow-up review 仍未通过，则继续复用 review gate 逻辑有界 fork 下一轮 repair。与此同时，`TaskService.start_peer_collaboration()` / `POST /api/tasks/{task_id}/peer-dispatch` 已可主动派发已注册 handler，`TaskService.complete_peer_collaboration()` / `POST /api/tasks/{task_id}/peer-result` 已打通第一版 delivery bundle 真实回传。默认服务现已自动注册第一版真实 `codex` CLI handler；尚未自动化的部分仍是更多 peer handler 与更强执行治理。

### 6.5 AgentSession Agenda

3.1 允许 Agent 在单个 `AgentSession` 内部动态维护 Agenda，但不允许 Agent 动态改写 Playbook 外部拓扑。

```text
Playbook step: open_question_identifier
  -> AgentSession starts
  -> agenda.add_item("inspect business ambiguity")
  -> agenda.add_item("retrieve historical decisions")
  -> agenda.add_item("check workspace conventions")
  -> execute agenda items through controlled tools
  -> final schema output
```

Agenda 的定位：

- Agenda 是 Agent 视角的临时分析待办，不是 Workflow DAG。
- AgendaItem 属于 `AgentSessionState`，随 session trace 记录。
- Agenda 工具或内部协议只能影响当前 session 的推理顺序，不能新增、删除或跳过 Playbook step。
- 当前第一版已通过 `AgentRuntime` 的内部 `agenda_add` / `agenda_update` 协议落地；若后续需要更强治理或前端可见性，再演进为显式 `agenda.add_item`、`agenda.update_status`、`agenda.list` 受控工具。
- Agenda 默认有数量上限，例如 12 个 item，防止复杂任务无限展开。

这保持了 3.1 的核心原则：外层流程确定，内层推理智能。

### 6.6 Product Memory / GBrain Integration

长期产品记忆是数字 PM 的命脉。3.1 要把 GBrain 从“可选检索服务”提升为控制面的关键输入和写回机制。

新任务启动时：

```text
business intent
  -> context_normalizer
  -> GBrain retrieve related decisions / constraints / terms / preferences
  -> compact memory summary + evidence refs
  -> Sticky Latch injection into AgentSession context
```

任务结束时：

```text
DecisionGate resolutions
  -> LearningEvidence
review_result / fix_tasks
  -> LearningEvidence
accepted machine_spec changes
  -> Product Memory
```

核心约束：

- GBrain 注入 AgentSession 的应是压缩摘要和证据引用，不是未经授权的材料全文。
- `open_question_identifier` 应优先利用历史裁决减少重复提问。
- `machine_spec_compiler` 应利用历史约束保持项目口径一致。
- Acceptance Review 的结果要写回 LearningEvidence，形成“哪些做法最后通过/未通过”的经验库。
- Sticky Latch 负责把最重要的项目约束固定在 session 前部，但必须受 token budget 和权限策略约束。

## 7. 为什么不是纯 Subagent 系统

Evoloop 的任务域是“把业务意图编译为 AI 技术同事可执行的协作规格”，不是开放世界自治任务。纯 subagent 系统会带来三个问题：

1. 产物结构不稳定，`machine_spec` 和 `acceptance_protocol` 难以固定。
2. 调试困难，用户很难知道失败来自哪个 agent 的哪次隐式决策。
3. 权限风险高，容易绕开 ToolPolicy 和材料授权边界。

因此 3.1 选择 Bounded Agent Sessions：每个 agent 有明确 step、角色、工具、schema、迭代上限和降级策略。

## 8. 实施边界

### 8.1 第一阶段必须改

- 清退 source-of-truth 路径上的静默 fallback：失败要显式 `degraded` / `blocked` / `needs_arbitration`
- 新增 `app/core/session.py`
- 可选新增 `app/core/agent.py`
- 新增 `app/services/agent_runtime/`
- 扩展 LLM port 支持 native tool use
- 将 `spec_to_agent` 主链路 agent 步骤接入 AgentRuntime
- 当前已完成 `open_question_identifier`、`machine_spec_compiler`、`agent_package_generator`、`acceptance_protocol_generator` 接入
- 当前已完成 `acceptance_review.requirement_coverage` 接入；`diff_impact_analyzer` 的语义审查分支已接入，静态插件分支保持确定性
- 增加 AgentSession 事件与 trace 字段
- Acceptance Review 不得在 reviewer 降级时默认 PASS

### 8.2 第一阶段不应改

- 不重写 `WorkflowEngine`
- 不迁移 legacy manual/prd playbook
- 不改前端视觉样式
- 不在第一阶段同时接入多种真实 peer handler；先只接一条最小真实链路并保持可审计
- 不让 agent 直接 shell 或直接文件读写

### 8.3 第二阶段

- `workspace.inspect` 只读工具
- 评估 `review_result_compiler` 是否继续作为确定性汇总器
- `AgentSession.agenda` 与 `agenda.*` 受控工具
- GBrain 检索接入 `context_normalizer` 与 `open_question_identifier`
- PeerAdapterService 接入真实 AI 技术同事 handler
- PeerAdapter dispatch handler 与 result bundle intake 的更完整执行链
- Acceptance Review 自动生成 fix_tasks 并驱动有界 Review-Redo Loop

## 9. 真相源约束

- `docs/evoloop-3.1/` 是当前目标架构与实施路线真相源。
- `docs/evoloop-3.0/` 是历史基线与迁移参考。
- 若 3.0、2.0、vision 文档与 3.1 冲突，以 3.1 为准。
- `machine_spec` 是产品交付内容的 source of truth。
- `Playbook` 是流程 source of truth。
- `AgentSession` 是单步推理过程 source of truth。
- `ArtifactGraph` 是产物关系 source of truth。

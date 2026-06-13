# 00 Evoloop 3.1 AgentSession 技术演进路线

> 状态：当前实施路线。
> 取代：`docs/evoloop-3.0/technical/01-engineering-evolution.md` 作为 agent 能力建设的最新工程基准。

## 1. 当前判断

当前实现主要是 Playbook-first workflow：

```text
WorkflowEngine
  -> StepExecutor
  -> LLM.invoke
  -> JSON parsing / fallback
  -> StepResult
```

这套结构的优点是稳定、可恢复、可审计；缺点是 `type="agent"` 的步骤还不是 Agent，只是函数式 Executor。

3.1 的技术目标是演进为：

```text
WorkflowEngine
  -> AgentStepExecutor
  -> AgentRuntime.run(AgentSession)
      -> LLM.invoke_with_tools
      -> ToolService.invoke
      -> schema validation
  -> StepResult
```

## 2. 主要变动层级

主要变动在 Service 层。

| 层级 | 变动大小 | 说明 |
|---|---:|---|
| Service | 大 | 新增 `app/services/agent_runtime/`，承载多轮推理、tool use、schema validation |
| Workflow | 中 | Executor 变薄，创建 AgentSession 并委托 AgentRuntime |
| Core | 小到中 | 新增 `AgentSession`、`AgentDefinition`、运行结果契约 |
| LLM Port | 小但关键 | 增加 `invoke_with_tools()`，支持 native tool use |
| Tool/Governance | 小 | 复用 ToolService，补 session 维度审计和策略判断 |
| API/SSE | 小 | trace 中展示 session、iteration、tool calls、degraded 状态 |
| Frontend | 小 | 只消费结构化 trace 字段，不改视觉样式 |

## 3. 文件责任规划

### 3.1 Core

```text
app/core/session.py
  AgentSession
  AgentMessage
  AgentSessionState
  AgentRunResult

app/core/subagent.py
  SubagentScope
  SubagentBudget
  SubagentSpawnRequest
  SubagentRun
  SubagentResult

app/core/agent.py
  AgentDefinition
  AgentRole
  AgentOutputSchema
  AgentDegradationPolicy
```

这些文件只定义契约，不调用 LLM、不访问文件、不执行工具。

当前状态：`app/core/session.py` 已落地第一版，包含 `AgentSession`、`AgentTurn`、`AgentObservation`、`AgentSessionState` 与 `AgentRunResult`。它只记录可审计的 turn、schema observation 和结构化结果，不暴露私有 chain-of-thought。

当前状态：`app/core/subagent.py` 已落地统一内部 subagent 契约，包含 `session_helper` / `formal_subtask` 两种 scope、串行与 helper 并行两种 execution mode，以及预算、拒绝原因、结构化结果和可审计运行记录。该模块只定义对象模型，不直接调度、不直接访问 Tool。

### 3.2 Service

```text
app/services/agent_runtime/__init__.py
app/services/agent_runtime/runtime.py
  AgentRuntime

app/services/subagent_service.py
  SubagentService

app/services/agent_runtime/context_builder.py
  SessionContextBuilder

app/services/agent_runtime/tool_bridge.py
  ToolBridge

app/services/agent_runtime/schema_validator.py
  SchemaValidator
```

`AgentRuntime` 是新增核心。

当前状态：`app/services/agent_runtime/runtime.py` 已落地第一版 `AgentRuntime.run_json_session()`。它优先使用 `LLMPort.invoke_with_tools()` 执行 provider-native tool calling；如果 LLM 实现不支持该方法，则退回到现有 `LLMPort.invoke()` + JSON tool-call 兼容协议。在 `max_iterations` 内执行 bounded JSON 解析与 required key 校验；耗尽后返回 `AgentSessionStatus.BLOCKED` 和 `agent_runtime.schema_validation_failed`，不生成 fallback 成功。

当前已支持两类 tool-use loop：

- Provider-native：`invoke_with_tools(role, prompt, context, tools, tool_messages)` 返回 OpenAI-compatible `tool_calls`，`AgentRuntime` 把 provider tool name 映射回内部 Tool 名称，再通过 `ToolService.invoke()` 执行。
- JSON 兼容协议：模型可返回 `{"tool_calls":[{"tool_name":"knowledge.retrieve","arguments":{"query":"..."}}]}`；用于不支持 provider-native tools 的网关或测试替身。

两条路径都必须经过 `ToolService.invoke()` 与 `ToolPolicy` 白名单校验，并把工具结果写入 `AgentObservation(kind="tool")`，然后进入下一轮模型调用。未授权工具会返回 `agent_runtime.tool_call_denied` 并阻断 session。

当前第一版真实 Session 内核还已补齐：

- `AgentSession.allowed_tools`、`output_schema_keys`、`context_budget`、`final_output`
- `AgentSessionState.agenda_items`、`tool_call_count`、`schema_errors`、`final_output_summary`、`degradation_reason`
- `AgentSessionState.helper_runs`，用于记录当前 session 内部 helper trace
- runtime 内部 `agenda_add` / `agenda_update` 协议，写入 session trace，但不改写 workflow 外部拓扑

当前状态：`app/services/subagent_service.py` 已落地第一版内部 subagent 执行服务。它是统一执行原语，负责 helper request 校验、budget gate、只读工具白名单、helper 串行/局部并行判定、结构化结果回收，以及 `subagent.run.created/started/denied/blocked/failed/completed` 事件输出。第一版 helper 只允许只读工具，默认不持久化完整 transcript。

尚未落地：并行工具调用、ToolResult 结果压缩、session 持久化摘要、公开 `agenda.*` 受控工具，以及把 helper 并行判定扩展到更多 workflow families。

### 3.2.1 Agenda

```text
app/core/session.py
  AgendaItem
  AgentSessionState.agenda_items

app/services/agent_runtime/runtime.py
  agenda_add / agenda_update internal protocol
```

Agenda 属于 `AgentSessionState`，用于单个 session 内部的临时计划和分析待办。Agenda 不改变 `WorkflowSpec.steps`，也不新增 workflow checkpoint 边界。当前已落地第一版 internal agenda protocol；公开 `agenda.add_item` / `agenda.update_status` / `agenda.list` 受控工具仍属于后续演进项。

### 3.2.2 Review Loop

```text
app/core/review.py
  ReviewCycle
  ReviewVerdict
  FixTask

app/core/work.py
  WorkItem.iteration
  WorkItem.parent_work_id
  WorkItem.review_cycle_id
  WorkItem.max_review_iterations

app/services/task_service.py
  fork_repair_work_item(...)
  handle_review_result(...)
```

Review Loop 用于 Acceptance Review 未通过时生成修复工作项。当前已落地第一版有界控制面：`WorkItem` 已具备 iteration 元数据，`TaskService.fork_repair_work_item()` 可从 `review_result.fix_tasks` 派生下一轮 `spec_to_agent` 修复任务，`TaskService.handle_review_result()` 可根据 `verdict=changes_required|blocked` 触发 fork。当前实现仍然保持有界，不会无限自动修复。

当前状态：repair/review 场景已接入第一版 `formal_subtask`。它不新建第二套任务树，而是复用现有 `Task` / `WorkItem`：`TaskService.spawn_formal_subtask()` 会把 child task 作为标准任务落盘，并在 `TaskContext.inputs` 与 `WorkItem.metadata` 中写入 `subagent_scope`、`parent_task_id`、`root_task_id`、`subtask_type`、`join_step_id` 和 `spawn_depth`；`TaskService.join_formal_subtasks()` 会在所有 child 进入终态后汇总 `delivery_bundle`，再回流 follow-up acceptance review。当前只在相互独立的 `fix_tasks` repair fan-out 场景启用；不满足独立性时仍回退到单 repair task 路径。

### 3.2.3 Internal Subagents

```text
session_helper
  session-local helper run
  read-only tools only
  returns compact structured result

formal_subtask
  control-plane child task
  reuses Task / WorkItem persistence
  joins back before formal state transition continues
```

内部 subagent 不是新的主调度框架，而是 Playbook / AgentSession 控制面里的受控执行单元：

- `session_helper` 只属于当前 `AgentSession`，默认不拥有父 session 的完整 turns、observations 或 artifact 原文。
- `formal_subtask` 属于控制面，用于天然可分的 repair/review 子包；它的结果必须先 join，再允许正式事实状态继续推进。
- 任何无法证明适合并行的情况默认串行。
- 任何治理问题返回 `denied`，不伪装成 `failed`。

当前 rollout 边界：

- `session_helper` 只有在显式输入 `enable_subagents=true` 时才会启用，不默认自动放大 token 开销。
- helper 输入必须是窄任务包：`goal`、`task_slice`、`input_refs`、`input_excerpt`、`allowed_tools`、`output_schema`、`budget`。
- helper 结果只作为父 session 的 advisory context，不直接改写正式 artifact 或 review verdict。
- `formal_subtask` 当前只允许在 repair/review 子包里派生，主 `spec_to_agent` 拓扑仍保持单主链。

### 3.2.4 Product Memory

```text
app/services/gbrain_service.py
  retrieve_product_memory(...)
  write_learning_evidence(...)

app/services/agent_runtime/context_builder.py
  build_sticky_latch_context(...)
```

Product Memory 通过 GBrain 接入，但 AgentSession 只接收压缩摘要和 evidence refs，不接收未授权原文。

### 3.3 LLM Port

```text
app/core/ports.py
  LLMPort.invoke_with_tools(...)
  LLMToolCall
  LLMToolResultMessage

app/services/llm.py
  OpenAILLM.invoke_with_tools(...)
```

保留 `invoke()` 兼容现有 playbook，新增 `invoke_with_tools()` 给 AgentRuntime 使用。

当前状态：`app/core/ports.py` 已声明 `LLMPort.invoke_with_tools()`；`app/services/llm.py` 已提供 OpenAI-compatible `/chat/completions` tools 调用路径。若兼容网关拒绝 tools 参数，`OpenAILLM.invoke_with_tools()` 会显式降级到 JSON tool-call 兼容协议，并在 `structured` 中标记 `native_tool_calling_degraded=true`，不把降级伪装成原生成功。

### 3.4 Workflow

```text
app/workflows/executors.py
  AgentStepExecutor 接入 AgentRuntime

app/workflows/spec_to_agent.py
  OpenQuestionIdentifierExecutor 变薄
  MachineSpecCompilerExecutor 变薄
  AgentPackageGeneratorExecutor 变薄
  AcceptanceProtocolGeneratorExecutor 变薄

app/workflows/acceptance_review.py
  RequirementCoverageExecutor 变薄
  DiffImpactAnalyzerExecutor 语义审查分支变薄
```

当前 `spec_to_agent` 主链路中的 4 个 agent executor 已接入 AgentRuntime：`open_question_identifier`、`machine_spec_compiler`、`agent_package_generator`、`acceptance_protocol_generator`。

当前 `acceptance_review` 中的 Reviewer agent 已部分接入 AgentRuntime：`requirement_coverage` 全量通过 Reviewer AgentSession 生成 coverage；`diff_impact_analyzer` 的静态插件仍保持确定性执行，只有插件无命中的语义审查分支通过 Reviewer AgentSession 执行。`review_result_compiler` 暂时保持确定性汇总器，不作为推理 Agent 迁移。

当前 helper-enabled step：

- `open_question_identifier`：helper 预扫需求歧义与缺失约束。
- `machine_spec_compiler`：helper 预抽取状态/约束热点，再进入正式 AST 编译。
- `requirement_coverage`：helper 预识别 coverage hotspot，再进入 requirement mapping。
- `diff_impact_analyzer` 语义审查分支：helper 预扫 regression / compatibility 风险主题，再进入最终 reviewer 判断。

这些 helper 都是 step 内部的局部分析，不会改变 Playbook 拓扑，也不会绕过 `AgentRuntime` 的最终 schema 校验。

## 4. AgentRuntime 行为规范

### 4.1 输入

`AgentRuntime.run()` 接收：

```text
AgentSession
Task
WorkflowStep
TaskDefinition
TaskContext
```

### 4.2 循环

```text
for iteration in range(max_iterations):
  response = llm.invoke_with_tools(messages, tools)

  if response.tool_calls:
    for call in response.tool_calls:
      result = ToolService.invoke(...)
      append observation message
    continue

  validation = SchemaValidator.validate(response.final_output)
  if validation.ok:
    return succeeded

  if validation.recoverable:
    append validation feedback
    continue

  return failed_or_degraded
```

这是 ReAct-style bounded loop：Reason -> Tool Call -> Observation -> Reason -> Final Output。它是有迭代上限、工具白名单和 schema 校验的受控推理循环，不是开放式自治 agent。

当前实现优先采用 provider-native tool calling；当 LLM port 不支持 `invoke_with_tools()` 或网关拒绝 tools 参数时，退回兼容 JSON tool-call 协议：

```json
{
  "tool_calls": [
    {
      "tool_name": "knowledge.retrieve",
      "arguments": {"query": "auth constraints"}
    }
  ]
}
```

执行边界：

- `AgentRuntime` 不直接执行文件、shell 或网络。
- 所有工具调用必须走 `ToolService.invoke()`。
- `ToolPolicy` denied 会转为 `AgentSessionStatus.BLOCKED`。
- 工具观察只写入摘要、状态、结构化 data 和错误，不写未授权原文。

### 4.3 输出

`AgentRunResult` 必须包含：

```text
session_id
status: succeeded | failed | degraded
final_output
summary
iterations
used_tools[]
schema_errors[]
degradation_reason
```

`StepResult` 应引用 `agent_session_id`，并在 degraded 时显式暴露。

## 5. ToolPolicy 规则

3.1 不允许 AgentRuntime 直接执行工具。

所有工具必须通过：

```text
ToolBridge
  -> ToolService.invoke
  -> ToolPolicy check
  -> ToolResult
```

策略判断至少包含：

```text
task_type
step_id
agent_role
session_id
tool_name
operation_kind
```

第一阶段可先把 session 维度用于审计，不必一次性实现复杂策略矩阵。

## 6. 事件与可观测性

新增事件类型建议：

```text
agent.session.started
agent.session.iteration.started
agent.session.tool.requested
agent.session.tool.observed
agent.session.agenda.updated
agent.session.schema.validated
agent.session.degraded
agent.session.completed
agent.session.failed
review.cycle.started
review.cycle.completed
review.fix_tasks.generated
memory.retrieval.completed
memory.learning_written
```

事件 payload 原则：

- 可以展示工具名、状态、摘要、耗时。
- 不展示凭证。
- 不展示完整本地路径。
- 不展示未授权材料原文。
- 不要求展示完整 chain-of-thought。

## 7. 第一阶段迁移目标

第一阶段迁移范围：

1. `machine_spec_compiler`：已迁移到 `AgentRuntime.run_json_session()`。
2. `open_question_identifier`：已迁移到 `AgentRuntime.run_json_session()`。
3. `agent_package_generator`：已迁移到 `AgentRuntime.run_json_session()`，输出语义从 `worker_target` 收敛为 `peer_target`。
4. `acceptance_protocol_generator`：已迁移到 `AgentRuntime.run_json_session()`。
5. `requirement_coverage`：已迁移到 Reviewer `AgentRuntime.run_json_session()`。
6. `diff_impact_analyzer`：语义审查分支已迁移到 Reviewer `AgentRuntime.run_json_session()`，静态插件分支保持确定性。
7. `open_question_identifier` 已支持第一版 `session_helper` 接入，启用 `enable_subagents` 时会派发窄任务包 helper，并把结果写入 `agent_session_trace.state.helper_runs`。
8. `machine_spec_compiler` 已支持第一版 `session_helper` 接入，用于在正式 AST 编译前抽取状态/约束热点。
9. `requirement_coverage` 已支持第一版 `session_helper` 接入，用于在正式 coverage mapping 前识别高风险 requirement focus。
10. `diff_impact_analyzer` 的语义审查分支已支持第一版 `session_helper` 接入，用于在正式风险判定前预扫 regression/compatibility 风险主题。
11. `acceptance_review -> repair` 已支持第一版 `formal_subtask`，仅在 fix tasks 相互独立时 fan-out。

成功标准：

- `spec_to_agent` 主链路 4 个 agent 步骤均通过 AgentRuntime 执行。
- `acceptance_review` 中依赖 LLM 判断的 reviewer 步骤通过 AgentRuntime 执行。
- 每个步骤有独立 AgentSession ID。
- 失败不再静默 fallback 为假成功。
- source-of-truth 产物生成步骤遇到 LLM 解析失败时返回 `blocked`，不能写正式 artifact。
- Acceptance Review 遇到 reviewer 降级时返回 `blocked` 或 `changes_required`，不能默认 PASS。
- `session_helper` 只在显式启用时运行，并把结果写入 `agent_session_trace.state.helper_runs`。
- `formal_subtask` 只在满足独立性与 join 成本可控时 fan-out，否则退回单 repair task。
- schema validation 失败可观测。
- 现有 `WorkflowEngine` checkpoint/resume 不被破坏。
- `tests/test_spec_to_agent.py` 和 `tests/test_backend_phase1.py` 继续通过或按新契约更新。

### 7.1 Mock / Fallback 清退规则

3.1 把 mock 分为三类处理：

| 类型 | 处理方式 | 当前例子 |
|---|---|---|
| 测试替身 | 允许保留，但只能由测试装配或显式 `--fake` 启用 | `app/services/fakes.py` 中的 `FakeLLM`、`FakeKnowledge`、`FakeStorage` |
| 生产降级 | 允许返回 `degraded=true`，但不能制造成功产物 | `GBrainKnowledge.retrieve()` 找不到 gbrain 时返回 degraded empty result |
| 假成功 | 必须清退或改为 blocked/changes_required | LLM JSON fallback 生成 machine_spec、coverage fallback 默认 covered、review fallback 空 issues |

第一阶段已经确立的实现契约：

- `_invoke_llm_with_retry(..., fallback=...)` 返回 fallback 时必须附带 `degraded=true`、`fallback_reason` 和 `fallback_role`。
- `machine_spec_compiler` 收到 degraded fallback 时返回 `StepStatus.BLOCKED`，错误码为 `workflow.llm_degraded_fallback`。
- `machine_spec_compiler` 已具备受控只读 tool-use 能力，当前主要用于 `knowledge.retrieve` 等白名单工具。
- `open_question_identifier` 已迁移到 AgentSession；LLM 解析失败时返回 `StepStatus.BLOCKED`，错误码为 `workflow.open_question_identifier_blocked`，不能伪装成 `has_questions=false`。
- `agent_package_generator` 已迁移到 AgentSession；LLM 解析失败时返回 `StepStatus.BLOCKED`，错误码为 `workflow.agent_package_generator_blocked`，不能用默认 Codex 伪装成已完成协作分包。
- `acceptance_protocol_generator` 已迁移到 AgentSession；LLM 解析失败时返回 `StepStatus.BLOCKED`，错误码为 `workflow.acceptance_protocol_generator_blocked`，不能用 fallback Given/When/Then 向量伪装成成功。
- `requirement_coverage` 已迁移到 Reviewer AgentSession；LLM 解析失败时步骤仍完成以便生成审计报告，但每个 requirement 默认 `covered=false`，coverage metadata 标记 degraded，最终由 `review_result_compiler` 输出 `verdict=blocked`。
- `diff_impact_analyzer` 的静态插件分支保持确定性；语义审查分支已迁移到 Reviewer AgentSession，降级时必须生成可见 issue 和 fix task，不能返回空 issues。
- `review_result_compiler` 检测到 coverage 或 impact 降级时 verdict 为 `blocked`。
- CLI `review --fake` 可以生成固定示例；非 fake 模式必须走真实 `acceptance_review` workflow。

后续清退优先级：

1. 把 `ToolService.default()` 中的 `material.read`、`format.validate`、`diff.extract_rules` 从占位返回替换为真实工具实现。
2. 将 API 里的知识库、可信规则、回收站静态 mock 改为真实 GBrain / Artifact / Rule repository 查询；不可用时返回 `degraded=true`。
3. 将 `FakeStorage` 的生产用途拆名为 `FileStorage`，`FakeStorage` 只保留为测试 alias。
4. 将 `PlaybookService` 的 `Output of node` 模拟执行标记为 legacy 或接入 `AgentRuntime` / `ToolService`。

## 8. 第二阶段迁移目标

第二阶段继续迁移：

- `review_result_compiler` 是否保持确定性汇总器或改为只读 Reviewer AgentSession 的边界评估
- 只读 `workspace.inspect` 工具
- `AgentSession.agenda` 与 `agenda.add_item` / `agenda.update_status` / `agenda.list`
- GBrain product memory 检索与 Sticky Latch 注入
- LearningEvidence 写回
- peer result bundle intake

## 9. Bounded Review-Redo Loop

Acceptance Review 不通过时，控制面应进入有界 Review-Redo Loop。

### 9.1 数据对象

```text
WorkItem
  iteration: int
  parent_work_id: str | None
  review_cycle_id: str | None
  max_review_iterations: int

ReviewCycle
  review_cycle_id
  source_work_id
  iteration
  verdict: pass | changes_required | blocked
  issue_ids[]
  fix_task_ids[]
  next_work_id

FixTask
  fix_task_id
  requirement_refs[]
  acceptance_refs[]
  issue_summary
  required_change
  owner_hint
```

### 9.2 状态流

```text
Acceptance Review verdict == pass
  -> mark WorkItem completed

Acceptance Review verdict == changes_required
  -> generate FixTask[]
  -> if iteration < max_review_iterations: fork repair WorkItem
  -> else: block with Decision Gate

Acceptance Review verdict == blocked
  -> if fix_tasks exist and iteration < max_review_iterations: fork repair WorkItem
  -> else: create Decision Gate
```

当前实现状态：

- `WorkItem.iteration`、`parent_work_id`、`review_cycle_id`、`max_review_iterations` 已进入核心契约并支持序列化。
- `TaskService.fork_repair_work_item(review_task_id, review_result)` 会创建 `spec_to_agent` 修复任务，输入中携带 `fix_tasks`、原始 `machine_spec`、`acceptance_protocol`、`parent_work_id`、`iteration + 1` 与 `review_cycle_id`。
- `TaskService.handle_review_result(review_task_id)` 会读取 `review_result_compiler.review_result` 并在 `changes_required` / 带 fix_tasks 的 `blocked` 情况下 fork 修复任务。
- `TaskService.create_followup_acceptance_review(repair_task_id)` 已可在修复任务完成后创建下一轮 `acceptance_review` 任务，输入中继续携带同一 `review_cycle_id`、相同的 `machine_spec` / `acceptance_protocol`，以及 repair task 上游已记录的 `delivery_bundle`。
- `TaskService.handle_repair_completion(repair_task_id)` 已可在 repair task 进入 `completed` 后，自动创建并运行下一轮 `acceptance_review`，并记录 `review.followup.run.started` / `review.followup.run.completed` 事件；若 follow-up review 仍未通过，则继续调用 `handle_review_result()` 有界 fork 下一轮 repair。
- `TaskService.start_peer_collaboration(task_id, peer_target=None)` 已可基于 `agent_package_codex.md` 与 `peer_target` 主动派发已注册的 PeerAdapter handler；未注册 handler 或缺少 package 时会显式失败，不伪装为协作成功。
- 默认服务当前会自动注册第一版真实 `CodexCLIHandler`。该 handler 调用本机 `codex exec`，要求可写 `CODEX_HOME` 与可用网络，并以工作区前后快照计算真实 diff，不信任模型自报成功。
- `TaskService.record_peer_delivery_bundle(task_id, peer_result)` 与 `TaskService.complete_peer_collaboration(task_id, peer_result)` 已可把 AI 技术同事回传的 result bundle 真实写回 `delivery_bundle`，并在 repair task 场景下自动接续 follow-up review。
- `POST /api/tasks/{task_id}/peer-dispatch` 已成为第一版主动派发表面；`POST /api/tasks/{task_id}/peer-result` 已成为第一版结果回收表面。
- `POST /api/tasks/{task_id}/peer-result` 已成为第一版对外 intake surface，允许外部 AI 技术同事直接回传结构化协作结果。
- 达到 `max_review_iterations` 会发出 `review.redo.max_iterations_reached` 事件并拒绝继续 fork。
- 当前版本已完成 “Review -> Redo WorkItem fork -> Create next Review task -> Auto-run next Review -> Re-enter bounded Redo” 的控制面入口，并已打通第一版 peer dispatch + peer result intake；其中 `codex` 已具备最小真实 handler，对接更多 AI 技术同事执行环境仍属于后续工作。

### 9.3 退出条件

- `pass`：验收通过。
- `max_review_iterations_reached`：达到最大修复轮数，交给人类裁决。
- `blocked_for_decision`：发现业务取舍、需求冲突或权限不足。
- `cancelled`：用户取消。

## 10. AgentSession Agenda

Agenda 用于复杂意图的 session 内部动态任务分解。

### 10.1 当前状态与后续工具

当前代码状态：

- `AgendaItem` 已并入 `app/core/session.py`
- `AgentRuntime` 已支持 `agenda_add` / `agenda_update` 的内部协议
- Agenda item 会进入 `agent_session_trace`

后续如需把 Agenda 暴露为显式受控工具，再演进为：

```text
agenda.add_item(title, rationale, priority)
agenda.update_status(item_id, status, note)
agenda.list()
```

### 10.2 约束

- Agenda 只存在于当前 `AgentSession`。
- Agenda 不能修改 `WorkflowSpec.steps`。
- Agenda item 默认上限为 12。
- Agenda item 必须写入 trace，供用户理解 Agent 为什么多做了一步。
- Agenda 工具仍通过 ToolPolicy 授权，不能绕过 ToolService。

### 10.3 首批应用点

- `open_question_identifier`：拆分歧义识别、历史裁决检索、约束检查。
- `machine_spec_compiler`：拆分 requirement coverage、edge case、acceptance refs、traceability map。

## 11. Product Memory / GBrain Integration

GBrain 是数字 PM 长期一致性的关键，不应只是 fake 检索层。

### 11.1 读取路径

```text
context_normalizer
  -> retrieve_product_memory(intent, workspace_id)
  -> compact memory summary
  -> evidence refs
  -> Sticky Latch context

open_question_identifier
  -> use historical decisions to avoid repeated questions

machine_spec_compiler
  -> use historical constraints and terminology
```

### 11.2 写回路径

```text
DecisionGate resolution
  -> write_learning_evidence(kind="decision")

Acceptance Review result
  -> write_learning_evidence(kind="review")

Passed fix task
  -> write_learning_evidence(kind="implementation_pattern")
```

### 11.3 Sticky Latch 约束

- 注入压缩摘要，不注入完整材料。
- 注入 evidence refs，方便回溯。
- 遵守 token budget。
- 遵守材料权限和租户隔离。
- 当记忆与当前用户裁决冲突时，以当前用户裁决为准，并记录新的 LearningEvidence。

## 12. PeerAdapter 接入原则

不要在第一阶段接真实 AI 技术同事 handler。

PeerAdapter 的命名表示“同事协作适配器”，不表示 Codex、Claude Code、Cursor 或 Antigravity 与数字 PM 存在从属关系。它只是把规格、任务包、验收协议和结果包转换成各协作工具能理解的接口。

原因：

- 当前 agent package 质量仍依赖一次性 prompt 和 fallback。
- 过早自动执行会放大低质量 package 的风险。
- 应先让 spec 编译与 package 生成可信，再接 Codex / Claude Code / Cursor。

PeerAdapter 协作接入顺序：

```text
agent package schema stable
  -> peer target selection stable
  -> result bundle schema stable
  -> local dry-run handler
  -> real Codex/Claude/Cursor/Antigravity handler
  -> acceptance review loop
```

## 13. 验证命令

文档改动后至少运行：

```bash
python3 -m unittest tests.test_backend_phase1 -v
python3 -X pycache_prefix=/private/tmp/manual-agent-pycache -m py_compile app/core/*.py app/workflows/*.py app/services/*.py app/api/*.py
```

涉及前端 API trace 字段时再运行：

```bash
npm --prefix frontend run build
```

## 14. 实施基准

后续 AI 技术同事读项目时，必须把以下文件作为最新实施基准：

1. `AGENTS.md`
2. `AGENT_MAP.md`
3. `docs/evoloop-3.1/README.md`
4. `docs/evoloop-3.1/architecture/00-global-architecture.md`
5. `docs/evoloop-3.1/technical/00-agent-session-evolution.md`

若旧文档与这些文件冲突，以 3.1 文件为准。

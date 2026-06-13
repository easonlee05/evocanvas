# 01 Evoloop 3.0 Agent 能力盘点与 Harness 工程评估

> 本次更新（2026-06-05）重写口径：
>
> - 旧版本以「LoC 目标 + 高并发/高可用」为指标，已与项目实际方向脱钩。
> - 新版本以「Agent 工作能力 + Harness 工程完整度」为指标，目标是支撑 100 人量级团队作为日常工具使用，可靠性需求让位于能力可用性。
> - 旧文档中关于"分布式 DAG / OpenTelemetry / Trace 链路"的诉求降为非阻塞项。

---

## 1. 当前后端代码量真实盘点

数据来自 `wc -l` 实测，截至 2026-06-05。

| 模块 | 旧目标 | 当前 | 状态 |
|---|---:|---:|---|
| `app/core/*` | 2000–2500 | **1,736** | 接近目标，关键契约已冻结 |
| `app/workflows/*` | 2500–3500 | **3,499** | **达标**，但热力分布失衡（见下） |
| `app/services/*` | 4500–6000 | **1,935** | **缺口最大**，Agent 能力主要欠账位 |
| `app/api+cli+mcp` | 3000–4000 | **1,693** | 缺口 |
| `tests/*` | 5000–8000 | **3,446** | 测试已比旧版翻倍，但金字塔仍偏窄 |
| **后端总计** | — | **8,863** | 较旧版 +22% |
| 前端 | — | 3,008 | 不在本文档讨论范围 |

`app/workflows` 内部分布：

| 文件 | 行数 | 评注 |
|---|---:|---|
| `spec_to_agent.py` | 792 | DDD 数据模型 + 3 段式编译 + 方言路由，**核心 playbook**|
| `acceptance_review.py` | 779 | Diff 解析 + 多插件审计矩阵 + 健康评分 |
| `engine.py` | 427 | 已剥离渲染/重试/检查点子模块 |
| `executors.py` | 288 | 步骤分派器注册表 |
| `context_compiler.py` | 258 | 字符串渲染从引擎下沉至此 |
| `prd.py` / `manual.py` | 218 / 108 | legacy projection |
| `dag_runtime.py` | 133 | 占位 |
| `retry_policy.py` | 118 | 重试决策机 |
| `checkpoints.py` | 135 | 检查点持久化 |

**关键观察**：

1. 引擎核心（`engine.py`）从旧版 688 行降到 427 行，重渲染/重试逻辑下沉，是健康的瘦身。
2. Playbook（`spec_to_agent` + `acceptance_review` ≈ 1,571 行）已压过 legacy（manual + prd ≈ 326 行），说明 3.0 主链路在事实上接管了系统重心。
3. `app/services` 仍最薄。这是当前最大的能力短板：所有 Agent 真正"能做的事"（读/写/查/算）都在这一层，而它今天主要还是 Tool dispatcher + LLM HTTP 客户端。

---

## 2. 工业级 Agent 能力的重新定义

旧文档把"工业级"等同于"分布式调度 / OpenTelemetry / 多租户隔离 / 沙箱化"。这些是 SaaS 平台的指标，不是 Agent 能力的指标。

本文档对齐的"工业级"标准（适用于 100 人量级日常使用）：

| 维度 | 通过线 |
|---|---|
| 1. 稳定 | 相同输入下产物可复现，不会因 LLM 偶发抖动让任务整段失败 |
| 2. 可控 | 任意步骤可暂停/恢复/重跑/局部跳转，无副作用累积 |
| 3. 可观测 | 用户可以在不读代码的情况下知道 Agent 当下"在做什么、为什么、用了哪些工具、输入了哪些上下文" |
| 4. 可扩展 | 增加新 Playbook、新工具、新角色的成本是配置级而非改架构级 |
| 5. 可信 | 输出能直接交付下游使用（数字开发人员能照着 agent_package 真的写出代码），无需用户每次大幅重写 |

按这五条衡量，目前 1、2、3 处于"基础可用"，4、5 处于"未达标"。下一节展开。

---

## 3. Agent 能力差距清单（按维度排序，按重要性排序）

### 3.1 推理循环：当前**不存在**

这是最大的结构性问题。

- 现状：`spec_to_agent.py` 中每个步骤是「拼一段 prompt → 调一次 LLM → 用正则提 JSON → fallback 兜底」。这是脚本化流水线，**不是 Agent**。
- 工业级标准：单步内部应允许 Agent 进行多轮 ReAct 推理（思考 → 调工具 → 观察 → 再思考 → 输出），由 Agent 自己决定何时收敛。
- 影响：
  - LLM 一次答错就只能靠正则 fallback 拉回 default 值，导致产物质量退化为"模板填空"。
  - 无法做"Agent 主动 query 上下文 / 主动检索知识 / 主动追加澄清"。
  - `OpenQuestionIdentifier` 之所以只能列出泛泛问题，根因就在这里。
- 改造建议：在 `app/services/agent_runtime/` 引入一个最小 Agent Loop（system prompt + tool spec → LLM 原生 tool_use → tool 执行 → 回灌 → 收敛）；让 Executor 优先委托给该 Loop，而不是直接 prompt → JSON。

### 3.2 工具调用协议：手写 JSON 解析 → 缺失 native tool_use

- 现状：`_invoke_llm_with_retry` 用 `_extract_json_from_markdown` 正则抠 JSON，靠 LLM 自觉输出格式，且失败 4 次后用 fallback。
- 工业级标准：使用提供商原生 function calling / tool_use 协议（OpenAI tools、Anthropic tool_use），结构由协议保证而不是由提示词哀求。
- 影响：当前实现对模型抖动极敏感，且 fallback 会让"失败"变成"假成功"，Acceptance Review 难以发现。
- 改造建议：`OpenAILLM.invoke` 增加 `tools` 参数透传，同时新增 `invoke_with_tools` 方法返回结构化 tool_call 而非 content；上层 Executor 切换到该接口。

### 3.3 上下文工程：Sticky Latch / 滑窗 / 复水 已落地，但缺真实 tokenizer

- 已做：`SlidingWindow`（软上限触发级联压缩）+ `RehydrationEngine`（`[需要复水: id]` 占位回灌）+ Sticky Latch（MEMORY.md/CLAUDE.md 永远在系统提示前部）。这部分实现质量已经达到 MVP 工业级。
- 仍缺：
  - `TokenCounter` 当前是 `len/4` 估算，未接 `tiktoken`/`anthropic.tokenizer`。命中率统计不准。
  - 没有 prompt-cache 协议对接（Anthropic prompt caching、OpenAI cached_input），Sticky Latch 的"粘"目前只是顺序保证，**没有真正生效的缓存命中**。
  - `compaction_dir` 写在 `workspace/inputs/temp/compaction/`，多任务并发会相互踩，未做 task_id 隔离。
- 改造建议：先补真实 tokenizer + 接 Anthropic cache_control 字段，再加 task 维度的 compaction 命名空间。

### 3.4 计划-执行（Plan-then-Execute）：主动不做

- 现状：所有 playbook 步骤序列在 `WorkflowSpec` 里硬编码。
- **为什么不做**：PM Agent 的任务域是收敛的——永远是"把业务意图编译成 agent_package"，不是通用任务空间。固定步骤本身就是产品经理工作方法的建模结果，相当于 plan 阶段已在设计时完成。动态规划的真正价值是应对未知问题空间（Claude Code 每次 coding task 结构都不同），这里不成立。
- **反向理由**：动态步骤让下游无法预期会收到什么结构，Acceptance Review 就无法写成固定协议；调试成本也极高（步骤为何被加、加了几步）。可控性收益 > 灵活性收益。
- **何时重新评估**：当出现"现有固定步骤覆盖不了某类真实需求"的具体场景时，由场景驱动引入，而不是为了工业级标准而做。

### 3.5 自我修正闭环：缺失

- 现状：`acceptance_review` 产出 issues + fix_tasks 后**就此结束**。issues 不会被回写到 `spec_to_agent` 让其重写包，也不会触发下游 worker 再走一轮。
- 工业级标准：至少应有"Reviewer → 修复任务 → 工人重做 → 再 Review"的最小循环骨架。
- 改造建议：在 `WorkItem` 上增加 `iteration` 字段，让 acceptance_review 完成时如果 verdict ≠ pass 自动 fork 一个修复任务（带上 issues 作为新输入）。

### 3.6 工作空间感知：Agent 看不到代码

- 现状：spec_to_agent 完全脱离实际仓库。它产出 agent_package 时不知道现有代码长什么样、哪些目录已存在、命名约定是什么。
- 工业级标准：PM Agent 在 compile spec 前应能（按授权）扫描下游 worker 的工作目录，至少读 `README` / `package.json` / 顶级目录结构，避免产出"假装空仓库"的任务包。
- 改造建议：新增 `tool: workspace.inspect`，受 ToolPolicy 严控（只读、目录广度有限、不读敏感文件）；spec_to_agent 在 context_normalizer 步骤可选调用。

### 3.7 多 Agent 协作：只有"Executor 函数"

- 现状：`OpenQuestionIdentifierExecutor` / `MachineSpecCompilerExecutor` / `RequirementCoverageExecutor` 等都是**类**，但它们没有独立的系统提示、工具白名单、角色档案——本质是带状态的函数。
- 工业级标准：每个角色（Compiler/Reviewer/Writer）应是独立 Agent 实例，拥有：
  - 自己的 system prompt（在 `llm.py:role_map` 之外，更结构化）
  - 自己允许的工具子集（不是统一 ToolPolicy）
  - 自己的对话历史 / 短期记忆
  - 自己的输出 schema 校验
- 改造建议：`app/core/agent.py` 新增 `Agent` 抽象，把现在散在 Executor 里的角色定义抽出；`Executor` 退化为薄壳，只负责把 `Task + Step` 喂给 `Agent.run`。

### 3.8 持久化记忆：缺失（这是 PM Agent 的命脉）

- 现状：每个 task 是孤岛。任务 A 学到的"这个项目偏好 TS 而不是 JS"在任务 B 里完全不知道。
- 工业级标准：PM Agent 至少要有：
  - 项目级长期记忆（per-workspace 的偏好/约束/术语表）
  - 跨任务的"产品经理判断历史"（哪些 decision 用户最终是怎么裁决的）
  - 召回机制：新任务开始时按相似度召回旧记忆并注入 sticky latch
- 这是 GBrain 在 3.0 的真正落点。`app/services/gbrain_service.py` 现在 187 行的实现严重不足。
- 这一项明确为下一阶段的优先级 #1。

### 3.9 输出可信度：fallback 让"假成功"流出

- 现状：每个 Executor 都设计了 `fallback`，目的是 LLM 失败时不让整条 pipeline 红。但代价是产物会带"Fallback requirement / Given system init, When task executes, Then expect success"这种**假数据**。下游若不识别，会按假数据继续走。
- 工业级标准：fallback 必须显式标记 `degraded=true`，并在 Acceptance Review 阶段被识别为不可放行。
- 改造建议：StepResult 增加 `degraded: bool` 标志，从 `_invoke_llm_with_retry` 透传至顶层；ReviewGate 看到 degraded=true 直接 changes_required。

---

## 4. Harness 工程评估（你说从设计时就没考虑过的部分）

### 4.1 什么是 Agent Harness

Harness 不是 Agent 本身，而是**让 Agent 能持续、可靠、可控地工作的外壳系统**。一个完整的 Agent Harness 至少包含：

| Harness 子系统 | 职责 | Claude Code 类比 |
|---|---|---|
| Session 管理 | Agent 的生命周期、上下文窗口控制、自动压缩 | `/clear`, auto-compact |
| 工具配额与权限 | 哪些工具能在什么场景下被谁调用、是否需要确认 | permission mode, hooks |
| 中断与恢复 | 用户随时打断、Agent 优雅停止、断点续跑 | ESC, resume |
| 任务分解与跟踪 | TodoWrite / 子任务派发 / 进度透出 | TodoWrite, Task tool |
| 工作目录与产物隔离 | worktree / 沙箱目录 / 产物归档 | git worktree, /init |
| 配置与个性化 | system prompt 注入、用户偏好沉淀 | CLAUDE.md, settings.json |
| 可观测面板 | 实时显示 Agent 行动、token 消耗、tool calls | UI 流式输出, /cost |
| 钩子与扩展 | pre/post 处理、自定义 slash command | hooks, slash commands, MCP |

### 4.2 Evoloop 当前 Harness 现状

按上述 8 个子系统逐项评分（A=工业级 / B=可用 / C=雏形 / D=缺失）：

| 子系统 | 当前 | 落位 | 评注 |
|---|---|---|---|
| Session 管理 | **C** | `Task` + `TaskContext` + `WorkflowEngine` | 有任务级生命周期，但没有"Agent 会话"层；context 是任务粒度，跨步骤共享上下文靠 `step_outputs` 字典硬塞 |
| 工具配额与权限 | **B** | `ToolService` + `ToolPolicy` | 实现了角色×步骤×工具的三维 ACL，且发 started/completed/denied 事件，这块做得好；缺：基于路径/租户/操作种类的细粒度授权 |
| 中断与恢复 | **B** | `task.cancel()` + `Checkpoint` + `resume_step_id` | 步骤级断点续跑成立；缺：步骤内部（LLM 调到一半）的中断仍会丢失增量输出 |
| 任务分解与跟踪 | **C** | `WorkflowSpec.steps` 静态 + `gate_results` 列表 | 步骤是声明式硬编码的，**Agent 自己不能动态产生子任务**；这一项是工业级 Agent 的硬指标 |
| 工作目录与产物隔离 | **C** | `FakeStorage` + `_tenant_services` 字典缓存 + `tempfile.gettempdir()` | 多租户用 `tenant_id` 当目录前缀做了软隔离，但 Agent 真正执行时没有 worktree 概念，所有任务在同一仓库视图下推理 |
| 配置与个性化 | **B-** | Sticky Latch 注入 `CLAUDE.md` + `MEMORY.md` | 已经在做"项目级注入"；缺：用户级偏好、按 playbook 类型的差异化 prompt、settings 持久化 |
| 可观测面板 | **B** | `Event` + SSE + `/api/tasks/{id}/trace` | 流式事件 + Trace 树已搭起；缺：token 消耗显示、tool_call 失败原因展开、LLM 思考过程展示 |
| 钩子与扩展 | **C** | MCP server 雏形（11 个工具） | 对外接出去能力可以；**对内扩展**（pre/post step hook、custom slash command）完全没有 |

总体评估：**Harness 工程目前停留在"任务工作流引擎"阶段**，具备 A 级潜质的只有"工具权限"。要升级为"Agent Harness"，缺三件大事，下一节展开。

### 4.3 Harness 的三件最关键的事

按重要性 × 落地成本排序：

#### (1) 引入 Agent Session 抽象层（最重要）

**问题**：当前没有"Agent 会话"这一层。`Task` 是业务任务，`Step` 是工作流节点，**中间缺少"一次连续的 LLM 推理过程"这个对象**。这导致：
- 无法做单轮内的 ReAct 循环
- 无法在一个 Step 内做工具调用 → 反思 → 再调用
- 无法在 Agent 视角统一「我在哪、我有什么、我能做什么」

**落地形式**：

```
app/core/session.py
    AgentSession
        - session_id
        - agent_role          # Compiler / Reviewer / Writer / ...
        - system_prompt       # 该 Agent 的人格
        - allowed_tools       # 该 Agent 在本会话能用的工具子集
        - messages            # 真正的对话历史（system + user + assistant + tool_result）
        - context_budget      # 该会话的 token 预算
        - state               # active / waiting_tool / done / failed

app/services/agent_runtime/
    AgentRuntime.run(session) → loop:
        1. 调 LLM (with tools)
        2. 若有 tool_use → 通过 ToolService 执行 → 把 tool_result 塞回 messages
        3. 若收敛 → return final
        4. 否则 goto 1，最多 max_iterations 轮
```

`Step` 退化成"创建 AgentSession 并 run 它"。这一改造会把当前 `spec_to_agent.py` 中 600+ 行的 prompt 拼接代码减半。

#### (2) 加上动态任务分解（TodoList for Agent）

**问题**：当前 Playbook 的步骤序列是固定的。但工业级 Agent（Claude Code、Cursor Background Agent）都允许 Agent 自己 `todo_write` 一份待办，然后逐项推进。Evoloop 现在没有这个能力，所以面对复杂业务意图时 Agent 只能按预设的 6 步硬走，**无法在中途说"我发现这个需求其实需要 12 步"**。

**落地形式**：

```
app/core/agenda.py        # Agent 自己维护的待办列表
    AgendaItem            # 子任务
    Agenda                # 待办列表，可被 LLM 通过 todo_* 工具读写

工具：
    agenda.add_item       # Agent 给自己加任务
    agenda.update_status  # Agent 标记完成
    agenda.list           # Agent 看自己还有什么没干

Playbook 改造：
    spec_to_agent 的"open_question_identifier"步骤改成
    "agent 在 agenda 上写下若干诊断子任务，然后逐项执行"
```

注意：`Agenda` 是 Agent 视角的 todolist，`Workflow.steps` 是平台视角的 pipeline。两者并存。

#### (3) Hook / Pre-Post Processor 体系

**问题**：现在如果想做"每个 LLM 调用前先注入项目元信息"或"每个 artifact.write 后自动跑 lint"，没有挂载点，只能改 engine 本体。这违背可扩展原则。

**落地形式**：

```
app/core/hooks.py
    HookSpec(event, handler, priority)
    HookRegistry
        - on_step_start
        - on_step_end
        - on_tool_call_pre / post
        - on_llm_call_pre / post
        - on_artifact_write
        - on_decision_gate

settings.json 中可声明项目级 hooks：
    "hooks": [
        {"event": "on_artifact_write", "command": "npm run lint"},
        {"event": "on_step_end", "command": "python ./scripts/audit.py"}
    ]
```

这是 Claude Code 已经验证过的扩展模式，对 Agent 平台同样适用。

### 4.4 Harness 中**已经做对**的事，不要拆

避免下一阶段重写时把这些已成立的部分推倒：

1. **结构化事件 + SSE 流**：`Event` + `EventBus` + `/events` 这条链是 Harness 的可观测脊柱，质量已经合格。
2. **Checkpoint 模型**：步骤完成后写 checkpoint、resume_step_id 记录、apply_decision 后续跑。这套机制是 Harness 的"可恢复性"核心。
3. **ToolPolicy 的角色×步骤×工具三维授权**：比"全局白名单"高一个层级，是好设计，应该继承到 AgentSession。
4. **Sticky Latch（系统提示前置不变区）**：思路正确，只差真正接入 prompt cache 协议。
5. **Legacy Bridge 模式**：把 `manual` / `prd` 包成 legacy projection，不直接重写，节省了大量返工成本。

---

## 5. 落地路线（替代旧版"三步走"）

按"能否当下解锁实际工作能力"排序：

### 第一优先级（1–2 周内可见）

1. **接 LLM 原生 tool_use 协议**（§3.2）— 让 Agent 工具调用从"靠正则求 LLM 给 JSON"升级为"协议保证"。
2. **fallback 的 degraded 标记**（§3.9）— 防止假成功流到下游。
3. **真实 tokenizer + Anthropic prompt caching**（§3.3）— Sticky Latch 真正生效。

### 第二优先级（接下来 2–4 周）

4. **AgentSession + AgentRuntime 抽象**（§4.3-1）— 引入 ReAct 推理循环。
5. **持久化记忆（GBrain 真正落点）**（§3.8）— PM Agent 的命脉。
6. **degraded → ReviewGate 联动 + 修复反馈环**（§3.5）— 完成"派活 + 验收 + 修复"的最小闭环。

### 第三优先级（看需要再做）

7. **Hook / Pre-Post Processor**（§4.3-3）
8. **workspace.inspect 工具 + Agent 工作目录感知**（§3.6）
9. **多 Agent 角色独立化**（§3.7）

旧版本里关于"分布式 DAG runtime / OpenTelemetry Span / Sticky Latch（已做）/ MicroVM 隔离"的诉求，**在 100 人量级目标下不再列入路线**。如果某一天系统真的要服务 1 万人，再把它们捡回来。

---

## 6. 一句话总结

> Evoloop 当前的形态是「带 Tool 权限和 Checkpoint 的工作流引擎」，**不是 Agent**。
> 要升级为工业级 Agent，第一缺的是**单步内的推理循环**（AgentSession + Native tool_use），第二缺的是**跨任务的项目记忆**（GBrain 真正落点），第三缺的是**Harness 的扩展点**（Hook / Agenda）。
> 三者解决后，平台对 100 人量级团队就具备日常可用性，而不再依赖每次手工兜底。


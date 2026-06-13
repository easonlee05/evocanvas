# Evoloop 3.1

本目录是 Evoloop 3.1 的当前实施基准。后续 AI 编程工具、架构评审、重构计划和实现任务都应优先读取本目录，而不是 `docs/evoloop-3.0/`。

## 3.1 定位

Evoloop 3.1 继续保持 3.0 的产品方向：系统核心是“数字产品经理”，不是 PRD/操作手册生成器。

3.1 在 3.0 基础上明确一个新的工程形态：

```text
Deterministic Playbook + Bounded Agent Sessions + Peer Collaboration Loop
```

中文表述：

```text
Playbook 控流程，AgentSession 控推理，ToolPolicy 控权限，Acceptance Review 控闭环。
```

这里的 Peer 是平级协作同事，不是从属关系。Codex、Claude Code、Cursor、Antigravity 与数字 PM 的关系应被描述为产品经理与技术同事之间的协作：数字 PM 负责规格、裁决和验收，AI 技术同事负责实现、重构、联调或设计执行，双方通过明确的契约协作。

## 与 3.0 的关系

- `docs/evoloop-3.0/` 保留为历史架构基线和迁移参考。
- `docs/evoloop-3.1/` 是当前实施基准和最新真相源。
- 若 3.0 与 3.1 冲突，始终以 3.1 为准。
- 3.1 不推翻 3.0 的数字 PM 定位，而是把 3.0 中“只有 Executor 函数”的 agent 步骤升级为受控 `AgentSession`。

## 必读顺序

1. `README.md`：版本定位与阅读顺序
2. `architecture/00-global-architecture.md`：3.1 全局架构真相源
3. `technical/00-agent-session-evolution.md`：从 playbook executor 演进到 AgentSession 的技术路线
4. 根目录 `AGENTS.md` 与 `AGENT_MAP.md`：仓库级协作规则与文件导航

## 非目标

3.1 不做以下事情：

- 不把 Evoloop 改成通用 AutoGPT 或自由 multi-agent 聊天系统。
- 不让 agent 绕过 `ToolService`、`ToolPolicy` 或 `TaskContext`。
- 不让 Codex / Claude Code / Cursor 反向定义 Evoloop 内核。
- 不优先重写前端 UI 或 legacy manual/prd playbook。
- 不把动态规划作为默认路径；Playbook 仍是产品经理方法论的稳定外骨架。

## 当前实施优先级

1. 新增 `AgentSession` / `AgentRuntime`，让 `type="agent"` 的步骤具备多轮推理和受控工具调用能力。
2. 优先改造 `spec_to_agent` 的 `open_question_identifier` 与 `machine_spec_compiler`。
3. 扩展 LLM port 支持 native tool use / function calling。
4. 补齐只读 `workspace.inspect` 工具，让 PM Agent 能按授权感知协作代码仓库。
5. 在 agent package 质量稳定后，再接真实 `PeerAdapter` 派发闭环。

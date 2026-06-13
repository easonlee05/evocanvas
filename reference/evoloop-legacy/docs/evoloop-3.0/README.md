# Evoloop 3.0

本目录保留为 Evoloop 3.0 历史架构基线和迁移参考，不再是当前实施基准。

当前最新实施基准是：

1. `docs/evoloop-3.1/README.md`
2. `docs/evoloop-3.1/architecture/00-global-architecture.md`
3. `docs/evoloop-3.1/technical/00-agent-session-evolution.md`

## 与 3.1 的关系

3.0 定义了 Evoloop 的数字产品经理定位：

- 接收业务目标、材料、反馈和用户裁决
- 中间编译为结构化 spec、agent package 和 acceptance protocol
- 与 Codex、Claude Code、Cursor、Antigravity 等 AI 技术同事平级协作
- 最后按需求和验收协议回收结果，并沉淀长期产品记忆

3.1 继承这个定位，但把工程实施基准从 “Playbook + Executor 函数” 调整为：

```text
Deterministic Playbook + Bounded Agent Sessions + Peer Collaboration Loop
```

也就是：

```text
Playbook 控流程，AgentSession 控推理，ToolPolicy 控权限，Acceptance Review 控闭环。
```

## 重要约束

- `docs/evoloop-3.1/` 是当前目标架构和实现路线真相源。
- `docs/evoloop-3.0/` 只作为历史参考。
- 若 2.0/3.0/vision 文档与 3.1 文档冲突，以 3.1 为准。
- 若现有代码仍停留在 Playbook-first workflow 形态，以 3.1 AgentSession 目标为重构方向。

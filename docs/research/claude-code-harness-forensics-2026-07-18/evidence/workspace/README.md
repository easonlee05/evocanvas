# EvoCanvas 工作区证据

## 文件

- `workspace-evidence-index.json`：证据 ID、原始路径、行号和文件 SHA-256。
- `workspace-excerpts.md`：带原始行号的 PRD、Harness 和代码摘录。
- `harness-maturity-scan.txt`：Instructions/Context、Safety/Governance、Observability、Evaluation 当前成熟度。

## 重点证据

1. 主 PRD 的 Vibe Shaping 定位、外层旅程和内层闭环。
2. 主 PRD 允许自动持久化约束候选，并定义约束草稿/待确认状态。
3. L3 State Ledger/Object Governance 却要求未确认约束留在 Chat。
4. Context Assembly 与 Trace Model 仍为 L2。
5. 当前 Canvas AI 路径仍以字符串拼接上下文。
6. ToolSpec/ToolPolicy 已有可复用底座，但 ToolService 尚未执行完整 L3 管线。
7. AgentRuntime/SubagentService 已具备有限循环和受控内部助手能力。
8. 当前 start_turn、确认匹配、提交顺序和 Snapshot 仍有迁移期边界。

摘录只用于定位证据；发生代码或文档变更后，应重新运行收集脚本刷新哈希和行号。


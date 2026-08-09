# Anthropic 官方资料证据

`official-docs-manifest.json` 记录了 2026-07-18 检查时的 HTTP 状态、最终 URL、响应头和前 65536 字节哈希，不保存完整网页正文。

## 资料与支持的判断

| 官方页面 | 支持的判断 |
| --- | --- |
| <https://code.claude.com/docs/en/how-claude-code-works> | Claude Code 是围绕模型提供工具、上下文和执行环境的 agentic harness；核心循环、session、context、checkpoint 和 permission 总览 |
| <https://code.claude.com/docs/en/agent-sdk/agent-loop> | prompt、assistant/tool calls、tool result 回灌、turn、context accumulation 与 automatic compaction 的公开循环 |
| <https://code.claude.com/docs/en/memory> | CLAUDE.md 与 auto memory 的层级、装载和“上下文而非强制配置”边界 |
| <https://code.claude.com/docs/en/permissions> | deny/ask/allow、permission modes、用户审批与规则优先级 |
| <https://code.claude.com/docs/en/hooks> | prompt、tool、subagent、compact、session 等生命周期事件和决策能力 |
| <https://code.claude.com/docs/en/sandboxing> | Bash sandbox 与 permissions 的互补关系、文件和网络边界 |
| <https://code.claude.com/docs/en/mcp> | MCP tools/resources/prompts、配置作用域、Tool Search 和外部信任边界 |
| <https://code.claude.com/docs/en/sub-agents> | 独立上下文、工具、权限、模型、memory、worktree 和摘要返回 |
| <https://code.claude.com/docs/en/agent-teams> | Lead/teammate/task/mailbox 拓扑、实验状态、成本和限制 |
| <https://code.claude.com/docs/en/sessions> | JSONL session、resume、fork 与当前设置重新加载 |
| <https://code.claude.com/docs/en/checkpointing> | 文件编辑 checkpoint 的能力与外部副作用边界 |
| <https://code.claude.com/docs/en/monitoring-usage> | OTel、tool decision、MCP、Hook、compaction 和成本观察面 |

## 时间边界

官方在线文档会更新，部分内容已描述晚于本机 CLI 2.1.112 和目标 Desktop worker 2.1.209 的版本。报告只把它用于“当前公开机制”，不会把所有当前文档细节倒灌成旧版本内部事实。

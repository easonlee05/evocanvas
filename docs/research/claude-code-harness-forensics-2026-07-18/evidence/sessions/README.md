# Rollout 与 Session 证据

## 包含的摘录

| 文件 | 内容 |
| --- | --- |
| `codex-root-analysis.sanitized.jsonl` | 本次 Claude Code Harness 主分析；截止原始第 407 行，排除证据包生成轮次 |
| `agent-local-forensics.sanitized.jsonl` | 本机 Claude 入口、bundle、Hook、session、公开源码取证 |
| `agent-official-research.sanitized.jsonl` | Anthropic 官方机制研究 |
| `agent-evocanvas-mapping.sanitized.jsonl` | EvoCanvas PRD、Harness 和代码映射 |
| `prior-context-convergence.sanitized.jsonl` | 既有四来源上下文收敛证据 |
| `claude-evocanvas-harness-session.sanitized.jsonl` | 与 Harness 收敛直接相关的本地 Claude JSONL session |
| `claude-session-inventory.json` | EvoCanvas Claude session 的元数据、记录类型、原始路径和 SHA-256 |
| `sanitized-session-manifest.json` | 每份原始/摘录文件的指纹、记录数和脱敏方法 |
| `convergence-process-index.json` | 目标 session 第 7–289 条的固定指纹、计数、阶段、改判与写回失败索引；不复制 thinking 正文 |
| `desktop-session-topology.json` | Desktop 稳定任务 ID、CLI 分支映射、rewind/fork 关系、完整事件计数和消息 DAG 完整性；不复制 Desktop 原始元数据 |

## 脱敏规则

- 移除 Codex Developer/System 消息和模型 reasoning。
- 移除 token accounting、world state 和无关内部事件。
- Claude thinking/redacted_thinking 只保留类型与原始块哈希。
- `<system-reminder>` 等 ambient 上下文只保留长度与哈希。
- 图片、文档和二进制内容不复制。
- 疑似 API key、token、Authorization、password、secret 值替换为 `[REDACTED]`。
- Codex shell/web Tool 输出只保留短预览、原始长度与 SHA-256；不复制长源码或网页正文。
- 其他超长结构化结果截断，并保留原始文本 SHA-256。

## 选择规则

- 只复制与本次 Claude Code/EvoCanvas Harness 研究直接相关的 session。
- 其他 EvoCanvas Claude session 只进入 inventory，不复制消息内容。
- 与另一项 Prompt 捕获实验相关的 `c9d1922e-...` session 没有复制正文。

这些文件用于审计研究过程和观察本地 session 格式，不得被当成 EvoCanvas 结构化包、确认记录或产品状态。

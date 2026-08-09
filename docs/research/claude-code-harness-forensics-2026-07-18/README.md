# Claude Code Harness 逆向分析证据包

> 研究日期：2026-07-18，深度修订于 2026-07-21  
> 工作区：`/Users/apple/Desktop/evocanvas`  
> 文档性质：外部参考模型与本地实现取证，不是 EvoCanvas 当前 Harness 规格  
> 结论入口：[00-analysis-report.md](./00-analysis-report.md)  
> Think 过程专项：[03-claude-thinking-process-analysis.md](./03-claude-thinking-process-analysis.md)

本目录首先回答 Claude 自身的三个问题：

1. Claude Code 如何通过查询循环、流式消息、上下文、工具、权限、Hook、压缩、Session 和 Subagent 组织成持续运行的 Agent；
2. Claude Desktop 的 Think 视图如何落盘，同一逻辑响应如何拆成 thinking/text/tool-use/tool-result 事件；
3. 一次真实收敛任务如何从 5 个子 Agent、55 个 finding 进入 13 个根决策，为什么前三题会在回读一手证据后全部改判，以及写回阶段如何失败和恢复。

EvoCanvas 借鉴只保留为主报告末尾的短附录，不再主导分析。

## 快速导航

- [Claude Code Harness 深度逆向主报告](./00-analysis-report.md)
- [证据台账](./01-evidence-ledger.md)
- [复核与重建方法](./02-reproduction.md)
- [Claude 收敛认知过程深度拆解](./03-claude-thinking-process-analysis.md)
- [本机 Claude Runtime 证据](./evidence/local-runtime/README.md)
- [公开非官方源码快照证据](./evidence/public-source/README.md)
- [Anthropic 官方资料证据](./evidence/official-docs/README.md)
- [Rollout 与 Session 证据](./evidence/sessions/README.md)
- [EvoCanvas PRD、Harness 与代码摘录](./evidence/workspace/README.md)
- [文件清单](./MANIFEST.json)
- [SHA-256 校验和](./SHA256SUMS)

## 目录结构

```text
claude-code-harness-forensics-2026-07-18/
├── 00-analysis-report.md
├── 01-evidence-ledger.md
├── 02-reproduction.md
├── 03-claude-thinking-process-analysis.md
├── README.md
├── MANIFEST.json
├── SHA256SUMS
├── evidence/
│   ├── local-runtime/
│   ├── official-docs/
│   ├── public-source/
│   ├── sessions/
│   └── workspace/
└── scripts/
    └── collect_evidence.py
```

## 证据等级

| 等级 | 含义 | 使用边界 |
| --- | --- | --- |
| `L1` | 本机当前 CLI、bundle、公开类型声明的直接证据 | 可说明本机被检查入口，不代表所有本地 Claude 会话都由同一版本生成 |
| `O1` | Anthropic 当前官方文档 | 可说明当前公开契约；可能晚于本机版本 |
| `S1` | 固定 commit 的公开非官方 source-map 提取快照 | 只用于解释结构和控制流，不称为当前官方源码 |
| `R1` | 与本研究直接相关的本地 rollout/session 脱敏摘录 | 可证明研究过程和历史现场；不是产品事实源 |
| `W1` | EvoCanvas 当前 PRD、Harness 与代码行号摘录 | 用于判断当前产品真相、规格成熟度和实现缺口 |
| `I1` | 基于多类证据作出的架构推断 | 必须能回指至少一条直接证据，不冒充官方术语 |

本次深度修订新增：

- `evidence/public-source/deep-control-flow-index.json`：query loop、streaming、tool、context、session、compact、subagent 的源码行号级索引；
- `evidence/sessions/convergence-process-index.json`：目标 session 的固定窗口指纹、计数、阶段、前三题改判和写回失败索引。

## 隐私与版权处理

- 没有读取或复制 `.env`、Claude settings、认证状态、memory 内容或密钥文件。
- 没有复制完整 Claude Code bundle，也没有复制完整公开提取源码。
- Rollout/session 文件是脱敏摘录：移除了 System/Developer 指令、模型 reasoning、环境型 system-reminder、二进制内容和疑似凭证值。
- 每份摘录的 manifest 同时保存原始文件路径、原始 SHA-256 和摘录 SHA-256，便于在本机授权范围内复核。
- 公开源码仓库自身声明为非官方；本证据包只保存 commit、文件指纹、目录和符号位置，不重新分发其完整源码。

## 一键重新收集

在仓库根目录执行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 docs/research/claude-code-harness-forensics-2026-07-18/scripts/collect_evidence.py
```

脚本会刷新本机版本、文件哈希、官方网页可达性、Session 清单、脱敏摘录、工作区行号摘录、`MANIFEST.json` 和 `SHA256SUMS`。

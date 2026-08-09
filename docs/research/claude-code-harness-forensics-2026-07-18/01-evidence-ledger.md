# 证据台账

## 1. 台账使用规则

- `直接证据` 只证明被检查版本或文件中存在对应机制。
- `交叉证据` 需要至少两个不同来源互相支持。
- `架构推断` 不冒充 Anthropic 官方组件名。
- Session/rollout 只证明本地研究现场和运行格式，不成为 EvoCanvas 产品事实源。
- 工作区摘录保留文件 SHA-256 和原始行号；仓库内容变化后应重新运行收集脚本。

## 2. 本机 Runtime 证据

| ID | 等级 | 文件 | 支持的判断 | 限制 |
| --- | --- | --- | --- | --- |
| `L-001` | L1 | `evidence/local-runtime/local-runtime-manifest.json`、`package-metadata.json`、`claude-version.json` | 当前 `/usr/local/bin/claude` 为 npm 入口，检查时返回 2.1.112；保存 bundle/package/types 指纹 | 不代表所有本地 session 都由该版本写入 |
| `L-002` | L1 | `evidence/local-runtime/claude-help.json`、`claude-agents-help.json`、`claude-mcp-help.json`、`claude-auto-mode-help.json` | System prompt、settings、tools、permissions、agents、MCP、session、预算、stream-json、bare 等公开入口 | Help 只证明公开声明，不证明内部实现细节 |
| `L-003` | L1 | `evidence/local-runtime/bundle-symbol-evidence.json` | bundle 中存在 Tool/Hook/compact/checkpoint/context 相关符号 | 字符串出现次数不等于稳定 API 或完整控制流 |

## 3. 官方资料证据

| ID | 等级 | 文件 | 支持的判断 | 限制 |
| --- | --- | --- | --- | --- |
| `O-001` | O1 | `evidence/official-docs/README.md`、`official-docs-manifest.json` | 官方 agentic loop、memory、permissions、hooks、sandbox、MCP、subagents、sessions、checkpoint、monitoring | 在线文档会更新，可能晚于本机版本 |

## 4. 公开源码快照证据

| ID | 等级 | 文件 | 支持的判断 | 限制 |
| --- | --- | --- | --- | --- |
| `S-001` | S1 | `evidence/public-source/source-snapshot-manifest.json` | 固定 remote、commit、文件数和选择文件指纹；仓库自述为 2.1.88 source-map 提取 | 非官方，不能称为当前源码 |
| `S-002` | S1 | `evidence/public-source/source-symbol-index.json`、`source-tree.txt` | `queryLoop`、工具并发安全分类、Pre/Post Hook、autoCompact、system/user context 等结构位置 | 只保存符号与行号，不保存完整源码语义 |
| `S-003` | S1 | `evidence/public-source/deep-control-flow-index.json` | 查询循环、streaming tool execution、schema/permission/Hook 管线、上下文分层、Session DAG、压缩和 Subagent 的行号级控制流 | 固定于非官方 2.1.88 快照；目标 session worker 为 2.1.209，版本敏感结论需以现场和官方文档覆盖 |

## 5. Rollout 与 Session 证据

| ID | 等级 | 文件 | 支持的判断 | 限制 |
| --- | --- | --- | --- | --- |
| `R-001` | R1 | `evidence/sessions/codex-root-analysis.sanitized.jsonl` | 本次研究的主分析过程、工具调用和证据交叉验证 | 截止原始第 407 行，排除生成证据包的下一轮 |
| `R-002` | R1 | 三个 `agent-*.sanitized.jsonl` | 本机取证、官方研究和 EvoCanvas 映射三条独立证据链 | 已移除 reasoning、Developer/System 和敏感值 |
| `R-003` | R1 | `claude-session-inventory.json`、`claude-evocanvas-harness-session.sanitized.jsonl` | Claude JSONL 的 session/version/parent/sidechain/tool/compact 等结构；本机多版本现场 | 只复制直接相关 session，其他仅列元数据 |
| `R-004` | R1 | `sanitized-session-manifest.json` | 原始与摘录路径、大小、SHA-256、记录数和脱敏规则 | 摘录本身不与原始文件字节等同 |
| `R-005` | R1 | `prior-context-convergence.sanitized.jsonl` | EvoCanvas 四来源架构和既有上下文收敛过程 | 是历史对话证据，当前仓库文件仍需独立核对 |
| `R-006` | R1+W1 | `R-005` 与 `W-CONTEXT-001` 交叉 | 四来源、工作包是数据、Chat/收敛共享权威上下文 | 属 EvoCanvas 既有结论，不是 Claude Code 官方机制 |
| `R-007` | R1+I1 | `03-claude-thinking-process-analysis.md`、`R-003`、原始 session 前 289 条记录指纹 | Think 内容块本地持久化；5 个 Agent/55 findings→13 簇、前三题改判、逐题确认、两次 thinking-only、TaskCreate 降级和自然语言决策漂移 | 不复制 thinking 正文；extended thinking 不等于全部内部推理 |
| `R-008` | R1 | `evidence/sessions/convergence-process-index.json` | 目标 session 的完整文件指纹、前 289 条固定前缀、事件计数、工具计数、阶段和改判索引 | 是从本机原始 session 派生的结构化索引，不替代原始 JSONL |
| `R-009` | R1+I1 | `evidence/sessions/desktop-session-topology.json` | Desktop 稳定任务 ID、2 个 CLI transcript 分支、61 个共享 UUID、完整 session 事件计数和 DAG 完整性 | 不复制 Desktop 原始元数据；无法严格归因每一条 JSONL 的进程级写入者 |

## 6. EvoCanvas 工作区证据

完整内容见 `evidence/workspace/workspace-evidence-index.json` 和 `workspace-excerpts.md`。

| ID | 支持的判断 |
| --- | --- |
| `W-PRD-001` | EvoCanvas 是 Vibe Shaping 工作台，不是 PRD 生成器或自由白板 |
| `W-PRD-002` | 外层旅程和内层收敛闭环 |
| `W-PRD-003` | PRD 允许自动写入约束候选 |
| `W-PRD-004` | PRD 定义约束草稿中、待确认、已生效等状态 |
| `W-HARNESS-001` | EvoCanvas 十二层 Harness 公式 |
| `W-HARNESS-002` | Memory/Runtime/Orchestration/Governance/Verification 已 L3，Context/Observability/Evaluation 多为 L2 |
| `W-CONTEXT-001` | 四来源、确定性裁剪、按需复水和失败回退 |
| `W-TRACE-001` | Chat -> Judgement -> Run -> operation 的目标因果链 |
| `W-STATE-001` | L3 State Ledger 不允许 constraint draft/pending_confirmation |
| `W-GOV-001` | L3 Object Governance 要求未确认约束留在 Chat |
| `W-CODE-001` | 当前 Canvas 角色 Prompt 拼接用户消息、卡片和材料 |
| `W-CODE-002` | Supervisor 当前不承担真实 subagent 调度 |
| `W-CODE-003` | Supervisor 直接水合全局缓存并拼 Prompt |
| `W-CODE-004` | ToolSpec 已声明 Schema、权限、副作用与事件语义 |
| `W-CODE-005` | ToolPolicyRule 已声明审批字段，但需核对实际执行 |
| `W-CODE-006` | 当前 ToolService 主要执行白名单与字符串安全检查 |
| `W-CODE-007` | 已有有界 AgentRuntime、工具回灌和 Schema 恢复 |
| `W-CODE-008` | 已有 Subagent 深度、并发和上下文上限 |
| `W-CODE-009` | Subagent 使用独立 AgentSession、只读工具和结构化返回 |
| `W-CODE-010` | 包版本、确认、账本和包根目前按文件顺序写入 |
| `W-CODE-011` | 当前 start_turn 仍是同步单体主链 |
| `W-CODE-012` | 当前确认匹配与 ConfirmationRecord 生成边界 |
| `W-CODE-013` | canvas_session workflow 仍明确为 definition_only |
| `W-CODE-014` | CanvasSnapshot 当前复制多类投影数据 |

## 7. 关键结论的交叉链

| 结论 | 证据链 |
| --- | --- |
| Claude Code 是 Harness，不只是模型调用 | `O-001 + L-002 + S-002` |
| Claude 主循环是显式递推状态机，模型流与工具执行可重叠 | `S-003 + O-001 + R-008` |
| 工具校验/权限失败会作为 tool result 回灌，而不是简单终止 | `S-003 + O-001 + R-007` |
| Permission 与 Sandbox 分别约束授权意图和 Bash 实际 OS 能力 | `S-003 + O-001 + L-002` |
| Session 是追加日志与消息 DAG，不是聊天数组 | `S-003 + O-001 + R-003 + R-008` |
| Checkpoint、Resume、Compaction 与 Fork 是不同恢复语义，且不能统一视为外部副作用回滚 | `S-003 + O-001 + R-009` |
| Desktop 稳定任务、CLI session 分支与消息 UUID 是三层不同身份 | `R-009 + R-003 + S-003` |
| 子 Agent 广域扫描提高召回，但最终推荐仍需主 Agent 回读直接证据 | `R-007 + R-008` |
| Think 长度不能单独代表质量；恢复、格式规划和失败重建会显著放大它 | `R-007 + R-008` |
| CLAUDE.md/memory 不能当硬策略或事实 | `O-001 + L-002 + R-003` |
| 工具执行是分层裁决链 | `O-001 + L-003 + S-002` |
| compaction/checkpoint 不能当权威业务状态 | `O-001 + L-003 + R-003` |
| EvoCanvas 应优先补 ContextManifest 与 Trace | `W-CONTEXT-001 + W-TRACE-001 + W-CODE-001 + W-CODE-003` |
| 不应新建第二套工具运行时 | `W-CODE-004 + W-CODE-005 + W-CODE-006 + W-CODE-007` |
| 内部只读 subagent 可复用，Agent Teams 不宜进入 1.0 | `O-001 + W-CODE-002 + W-CODE-008 + W-CODE-009` |
| PRD 与 L3 的约束候选语义冲突 | `W-PRD-003 + W-PRD-004 + W-STATE-001 + W-GOV-001` |
| Think 视图落盘但不能充当决策账本 | `R-003 + R-004 + R-007` |
| EvoCanvas 应把逐题选择变成可验证写回事务 | `R-007 + W-STATE-001 + W-CODE-010 + W-CODE-012` |

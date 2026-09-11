# Architecture Traceability（架构可追溯矩阵）

> 文档状态：`与 Harness L3 对齐`
> 追溯范围：`产品真相 -> Harness 治理规格 -> 目标架构 -> 当前实现证据`
> 当前结论：`十二项 Harness 均为 L3；原生主链已接入，完整闭环仍需证据`

## 1. 文档目的

本矩阵防止四类混淆：把主 PRD 体验规则当技术接口、把当前实现当目标架构、把 Harness L3 当实现完成、把 Pi 已有技术能力当 EvoCanvas 产品规则已经落地。

## 2. 状态口径

| 状态 | 含义 |
| --- | --- |
| `L3` | 治理规则足以指导实现，无需再发明产品边界 |
| `原生主链已接入` | 当前生产路径已使用 EvoCanvas 原生 Workspace 主链，仍有边界待验证 |
| `原生实现待验证` | 合同和实现已存在，但缺少真实入口或端到端证据 |
| `待验证` | 已有实现，但缺少真实入口或端到端证据 |
| `历史参考` | 仅用于识别兼容边界，不可作为新实现依据 |

## 3. 十二项 Harness 追溯

| 方法 | L3 权威规格 | 目标架构承接 | 当前实现证据与缺口 |
| --- | --- | --- | --- |
| Instructions | [`Instructions`](<../harness/01-instructions-context/01 Instructions（指令）.md>)、[`Prompt Control`](<../harness/01-instructions-context/05 Prompt Control（提示控制）.md>) | Pi System Instructions、Skills、Tool Schema / Hooks | pi-agent-core 已提供 Skill 资源；当前 executor 未接入完整资源链 |
| Context | [`Context`](<../harness/01-instructions-context/02 Context（上下文）.md>)、[`Context Assembly`](<../harness/01-instructions-context/03 Context Assembly（上下文装配）.md>) | Primary Session + `transformContext` | 当前仍使用外部请求快照和 Context Manifest，待删除 |
| Memory | [`Memory and State`](<../harness/02-memory-state/00 Memory and State（记忆与状态）.md>) | Pi Session + 完整不可变 Revision | 原生 Revision 已接入，运行记录与状态边界待继续验证 |
| Runtime | [`Runtime`](<../harness/03-runtime-tools/01 Runtime（运行时）.md>) | Pi `0.85.1` + official SQLite Session Backend + AgentHarness | 当前为 `0.84.1` 单次 Agent；长期 Session、单文件、宿主锁和恢复待接入 |
| Tools | [`Tool Contract`](<../harness/03-runtime-tools/02 Tool Contract（工具契约）.md>) | Pi Tool Loop + EvoCanvas 工具 | Workspace Tool Context 已接入；身份分层和 `replay` 策略待验证 |
| Orchestration | [`Orchestration`](<../harness/04-orchestration-lifecycle/01 Orchestration（编排）.md>) | 同一个 Pi Tool Loop | 当前仍有判断、收敛水位和独立收敛运行，待移除 |
| Lifecycle | [`Lifecycle`](<../harness/04-orchestration-lifecycle/02 Lifecycle（生命周期）.md>) | Pi 技术状态 + Revision / Handoff 状态 | 兼容运行状态与原生 Revision 并存，需继续验证只读边界 |
| Safety | [`Safety`](<../harness/05-safety-governance/01 Safety（安全）.md>) | Pi 保护 + 工具护栏 | 部分权限与工具限制已存在；新确认、未知效果边界待验证 |
| Governance | [`Governance`](<../harness/05-safety-governance/02 Governance（治理）.md>) | 用户裁决 + `workspace.commit` | 当前有多条提交与候选路径，统一语义提交待落地 |
| Observability | [`Observability`](<../harness/06-observability/00 Observability（可观测性）.md>) | Pi Trace + Revision 审计 + Projection Checkpoint | 技术和产品记录存在但关联键未按新主链闭环 |
| Verification | [`Verification`](<../harness/07-verification/00 Verification（验证）.md>) | 确定性结构、来源和 Policy 验证器 | 当前部分 Schema 校验存在；新 Revision 原子验证待落地 |
| Evaluation | [`Evaluation`](<../harness/08-evaluation/00 Evaluation（评估）.md>) | 离线评估控制面 | L3 指标已定，独立评估集和基线待建设 |

## 4. 架构节点追溯

| 架构节点 | 产品依据 | Harness 依据 | 权威输出 | 实现状态 |
| --- | --- | --- | --- | --- |
| Landing / Workspace UI | 主 PRD 感觉接入与工作台 | Governance、Observability | User Entry、UI action | 部分接入 |
| Primary Pi Session | 主 PRD 右侧 AI 助手 | Context、Runtime | Session Entry / Technical Trace | 原生主链已接入，待验证 |
| Workspace–Session Binding | 主 PRD 工作区连续对话 | Runtime、Lifecycle | `binding / ready / unavailable / archived` | 原生主链已接入，待验证 |
| Instruction / Skill Resources | 主 PRD 对话塑形 | Instructions | 制品版本与使用 Trace | 部分接入 |
| Workspace Context Snapshot | 主 PRD 当前工作上下文 | Context | 临时稳定工作快照 | 原生实现待验证 |
| Workspace Artifact / Structured Work Package | 主 PRD 结构收敛 | Memory、Lifecycle、Governance | 完整不可变 Revision | 原生主链已接入，待验证 |
| Semantic Commit | 主 PRD 用户确认与直接编辑 | Tools、Governance、Verification | Commit Result / new Revision | 原生主链已接入，待验证 |
| Lifecycle Coordinator | 主 PRD 工作区状态与删除反馈 | Lifecycle、Safety | close/archive/replace/delete outcome | 原生实现待验证 |
| Canvas Renderer | 主 PRD 画布显影 | Observability、Verification | Projection Checkpoint | 原生主链已接入，待验证 |
| Handoff Renderer | 主 PRD 结构化交接 | Memory、Governance | confirmed handoff view | 原生主链已接入，待验证 |
| External Tools | 主 PRD 下游边界 | Tools、Safety | 外部回执 | 按工具验证 |
| Evaluation Control Plane | 主 PRD 首版验证命题 | Evaluation | 评估报告和发布建议 | 待建设 |

## 5. 关键依赖追溯

| 上游 -> 下游 | 必须保持的合同 | 验收证据 |
| --- | --- | --- |
| Workspace -> Pi Session | 一个 Workspace 绑定一个长期 Primary Session | 跨进程恢复测试 |
| First Submission -> Binding | 空 Workspace 不建 Session；同一 `submission_id + content_hash` 只建一个 Entry | 首条消息崩溃与重试测试 |
| Pi Session -> transformContext | 原 Entry 不被改写；每次调用读 current Revision | Context 装配测试 |
| Pi -> Skills | Pi 自主发现和读取，不存在产品路由 | Skill 使用 Trace + 无阶段路由 |
| Pi -> Read Tools | 精确内容按引用读取，结果进入 Session | Tool Entry / source ref |
| Tool recovery -> Invocation | `replay=safe|never` 与 `success|failed|unknown` 分离 | 崩溃恢复与未知效果测试 |
| User Confirmation -> Commit | 确认绑定内容、范围和基础 Revision | 正反门禁测试 |
| Direct Edit -> Commit | 与 Pi 编辑共用版本、权限、幂等和依赖规则 | 两入口一致性测试 |
| Commit -> Revision | 全部门禁通过后原子发布完整快照 | 并发和故障注入测试 |
| Revision -> Canvas | 只投影稳定对象，可从 Revision 重建 | Projection parity 测试 |
| Revision -> Handoff | current 与 latest confirmed 指针分离 | 过时、暂停、替代测试 |
| Evaluation -> Release | 只形成建议，不能自动改变线上指针 | 权限和发布审计测试 |
| Workspace -> Delete | 协调删除如实返回 `deleted / partial / retention_held` | 故障注入与保留策略测试 |

## 6. 原生边界冲突裁决

以下内容统一视为兼容债务，而非原生主链合同：

- Product Kernel 调用独立 Pi Runtime；
- `run_chat / run_judgement / run_convergence`；
- `convergence_hint`、判断水位和调度租约；
- Chat 与收敛分别装配上下文；
- Context Manifest、独立状态账本和产品侧运行记录；
- 候选自动写入并正式显影；
- 专门 Governance Agent 或二次语义裁决模型。

若当前代码或历史技术文档出现这些内容，只保留明确的只读或兼容边界，停止新增依赖，并以 Harness L3 和本矩阵为目标。

## 7. 当前实现证据

已确认当前仓库：

- `pi-runtime/package.json` 与 lockfile 已统一使用 `0.85.1` Pi 依赖族；
- `pi-runtime/src/server.ts` 已提供 Workspace binding、submission、turn、commit、projection、revision 和 lifecycle 端点；通用 chat / judgement / convergence 端点仅作为兼容边界保留；
- `WorkspaceSessionStore`、`WorkspaceRevisionStore`、Workspace Agent Loop 和直接编辑提交器已接入，并有 Session 恢复、幂等、过时版本、投影重建和跨语言回归测试；
- `app/canvas/pi_kernel.py` 的生产入口已通过 Primary Pi Session 和 `workspace.commit` 驱动画布，非主链运行合同继续保持隔离；
- 真实 Provider、浏览器人工流程、跨宿主路由和全部 Harness L3 边界仍需补充证据。

这些证据说明原生主链已接入，不替代真实环境和端到端验收。

## 8. 原生实现完成的硬门

1. 生产入口不再主动调用非主链 judgement / convergence 路径。
2. 一个真实 Workspace 可恢复同一 Pi Session。
3. `transformContext` 从 current Revision 生成稳定快照。
4. 用户和 Pi 编辑进入同一 `workspace.commit`。
5. 未确认候选无法出现在工作包和 Canvas。
6. current / confirmed handoff 双指针及过时规则通过测试。
7. Entry–Tool–Commit–Revision–Projection 追溯闭环。
8. 历史数据完成导入、兼容读取和回退验证后，才删除兼容字段。
9. `submission_id / entry_id / operation_id / invocation_id` 分责，工具重放与结果状态按合同工作。
10. 历史数据导入无长期双写，close/archive/replace/delete 的恢复和终态均通过测试。

## 9. 当前结论

Harness 方法成熟度已经收敛到 L3；EvoCanvas 原生主链已经接入。仍需用真实 Provider、浏览器流程和兼容边界回归证明完整生产闭环，不能只凭文档 L3 或包版本号宣称全部能力已完成。

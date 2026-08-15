---
status: 阶段 4 实施中
stage: 阶段 4：落地 L3 生命周期
branch: codex/pi-runtime-core-refactor
updated_at: 2026-08-14
---

# EvoCanvas Pi Runtime 内核重构执行计划

## 1. 计划目的

本计划把已确认的 [Pi Runtime 内核一步到位重构设计](./2026-08-13-evocanvas-pi-runtime-core-refactor-design.md) 拆成可审查、可验证、可暂停的实施步骤。目标是最终只保留一条执行链：

```text
EvoCanvas Product Kernel
  -> AgentExecutionPort
  -> PiRuntimeClient
  -> Private Pi Runtime
  -> Pi Agent Core / Pi AI
```

Python 继续拥有产品事实、上下文装配、判断、治理、确认、版本和提交；TypeScript Pi Runtime 只拥有单次模型运行、Provider 适配、工具循环、流式事件、取消和技术用量。Pi 不得直接写入 Package、Card、Relation、Handoff、ConfirmationRecord、Ledger 或 Outbox。

## 2. 依据、边界与当前假设

### 2.1 权威依据

1. 产品边界：[EvoCanvas 1.0 PRD](../docs/vision/EvoCanvas1.0-PRD.md)。
2. 运行、工具、失败、治理和提交规则：`docs/harness/` 中达到 L3 的规格，尤其是 [Runtime](../docs/harness/03-runtime-tools/01%20Runtime（运行时）.md)、[Tool Contract](../docs/harness/03-runtime-tools/02%20Tool%20Contract（工具契约）.md)、[Failure and Recovery](../docs/harness/03-runtime-tools/03%20Failure%20and%20Recovery（失败与恢复）.md) 和 [Implementation Baseline](../docs/harness/04-orchestration-lifecycle/05%20Implementation%20Baseline（实现基线）.md)。
3. 架构选择和迁移范围：[重构设计](./2026-08-13-evocanvas-pi-runtime-core-refactor-design.md)。
4. 本轮新增接口合同：[Pi Runtime Interface Contract](../docs/technical-specs/05%20Pi%20Runtime%20Contract（Pi%20运行时接口契约）.md)、[阶段 0 矩阵](../docs/technical-specs/06%20Pi%20Runtime%20Phase%200%20Matrices（Pi%20运行时阶段%200%20矩阵）.md)、[迁移前置核对](../docs/technical-specs/07%20Pi%20Runtime%20Migration%20Preflight（Pi%20运行时迁移前置核对）.md) 及 [JSON Schema](../docs/technical-specs/schemas/pi-runtime/v1-contracts.json)。

### 2.2 明确不做

- 不建设旧引擎兼容层、双跑、Shadow、模式开关或运行时回退。
- 不迁移尚未正式联调的旧 `active_turn`、长期确认等待状态和开发期运行记录。
- 不把前端视觉重做、多人协作、自由白板或任务管理纳入本次分支。
- 不让 Pi Runtime 持久化产品事实，也不让模型自由调用 Shell、文件写入、任意网络或 MCP 写工具。

### 2.3 阶段 0 的默认连带假设

以下细节不改变总体架构，先按默认值推进；若代码核对发现事实冲突，必须回到本计划的停止门：

- Pi 与 Python 使用私有 HTTP；运行事件使用 NDJSON。
- 运行端点以流式事件作为主响应；补充 `GET /v1/runs/{run_id}` 作为断流后的终态查询入口。
- Pi 调用 Python 只读工具时走受 Run-scoped Token 保护的内部 Tool Gateway。
- Pi 包版本先按设计稿的 `@earendil-works/pi-agent-core@0.84.1`、`@earendil-works/pi-ai@0.84.1` 和 Node.js `>=22.19.0` 编写合同，阶段 1 开始前重新核对可安装性与实际 API。
- 生产代码只有一个 `PiRuntimeClient`；测试中的 Fake 只实现 `AgentExecutionPort`，不构造第二个真实模型执行器。

以下内容不在本轮直接冻结为产品语义，但必须在阶段 0 留出明确边界：

- `Context Manifest` 只冻结最小 Trace 引用，不冻结仍为 L2 的历史选择、排序、压缩和复水算法。
- 约束提议没有有效确认时只留 Chat，不写入约束对象；待决策候选、冲突和待澄清使用各自正确的信息地位。
- 交接草稿显影门槛与正式外发/确认门槛分开；本次普通包更新不新增独立审批队列。
- 旧工作区是否存在必须保留的真实数据，先做 preflight；在结果未知前不能删除旧字段或写兼容读取器。

## 3. 总体分阶段路线

| 阶段 | 目标 | 主要产物 | 出口门 |
| --- | --- | --- | --- |
| 0 | 冻结产品合同 | 执行计划、跨语言接口合同、Schema、失败样本矩阵、合同测试清单 | 合同字段、状态、错误和验收场景可被 Python/TS 同时实现 |
| 1 | 建立 Pi Runtime | `pi-runtime/`、health/readiness/capabilities、RunRegistry、取消、三类 Adapter、Fake Provider | TS 单测通过，三类运行可完整执行 |
| 2 | 建立 Python 执行边界 | `AgentExecutionPort`、强类型请求/结果、`PiRuntimeClient`、NDJSON 解析与错误映射 | Python 可独立完成三类合同测试 |
| 3 | 重构产品控制面 | ConversationOrchestrator、Judgement、Scheduler、Convergence、统一 Commit 链 | Chat 不写包，Convergence 只提案并走统一提交 |
| 4 | 落地 L3 生命周期 | message_seq、四类运行记录、包级租约、待重判水位、stale、unknown、Outbox 恢复 | L3 运行时场景全部通过 |
| 5 | 接入受控工具 | Tool Gateway、Run-scoped Token、只读白名单、Proposal Capture、越权测试 | Pi 无法越权写状态，提案只回到 Python |
| 6 | API 与联调 | FastAPI 装配切换、状态/取消/错误 API、前端适配、统一启动入口 | Web → Python → Pi → Commit 完整闭环 |
| 7 | 清理旧链 | 删除在线旧 Provider、AgentRuntime、WorkflowEngine 依赖、active turn 和旧夹具 | 全仓只有一个真实 Agent 执行路径 |
| 8 | 最终验收 | Python/TS/前端/E2E、安全、故障注入、全新环境演练、文档同步 | 全部硬门通过，才允许合并分支 |

## 4. 阶段 0：冻结产品合同（已完成）

### 4.1 工作项

1. 建立本执行计划，明确阶段、依赖、出口门、停止门和提交拆分。
2. 建立 [Pi Runtime Interface Contract](../docs/technical-specs/05%20Pi%20Runtime%20Contract（Pi%20运行时接口契约）.md)，冻结：
   - `AgentExecutionPort` 的三类运行和取消方法；
   - Python → Pi 的请求、结果、事件、终态查询和错误合同；
   - Pi → Python Tool Gateway 的请求、结果和 Token 约束；
   - 四类运行记录与产品状态/技术状态的分离；
   - `operation_id`、`message_seq`、版本检查和 stale/unknown 语义。
3. 建立机器可读 [v1 JSON Schema](../docs/technical-specs/schemas/pi-runtime/v1-contracts.json)。
4. 从 L3 Harness 和现有测试整理首批失败样本与硬门场景，不把旧实现的输出文本当作基线。
5. 对当前代码做消费者清单：哪些是通用底座，哪些是旧产品执行适配层，哪些必须迁入 Product Kernel，哪些可在阶段 7 删除；结果记录在 [迁移前置核对](../docs/technical-specs/07%20Pi%20Runtime%20Migration%20Preflight（Pi%20运行时迁移前置核对）.md)。
6. 补齐阶段 0 的配套矩阵（已形成初稿，待测试/代码核对）：
   - 生命周期/状态矩阵（四类运行记录、租约、水位、stale、unknown、Outbox）；
   - Provider/Adapter 兼容矩阵（至少 OpenAI Responses 与 Anthropic Messages）；
   - ToolSpec/ToolCall/ToolResult 白名单与权限矩阵；
   - HTTP/Pi 错误 → Python 领域错误 → 用户行为的恢复矩阵；
   - 旧入口、通用底座、删除范围和数据 preflight 清单。

### 4.2 阶段 0 出口检查

- [x] 专用分支 `codex/pi-runtime-core-refactor` 已建立（从 `main` 的 `414453d7` 起步；本轮文档提交将形成首个分支专属提交）。
- [x] 执行计划已落盘。
- [x] Python/TS 接口与事件合同已落盘。
- [x] 机器可读 Schema 已落盘并通过 JSON 解析校验。
- [x] 合同 Schema fixture 测试已加入并通过（6 tests）。
- [x] 产品失败样本/L3 场景 fixture 已加入并通过（7 tests）。
- [x] 生命周期、Provider、工具、错误恢复和迁移清单完成阶段 0 核对。
- [x] 当前代码消费者与阶段 7 删除边界完成只读核对。
- [x] Pi 包安装基线、Node 要求和 SDK exports 已完成核对；阶段 1 已生成 lockfile 并固定 `pi-telemetry` 到 `0.84.2`。

## 5. 后续阶段的详细执行顺序

### 阶段 1：建立 Pi Runtime

1. 新建 `pi-runtime/`，固定 Node、Pi 包和 lockfile。
2. 先实现 `config`、`healthz`、`readyz`、`capabilities`，再实现运行注册表和取消。
3. 实现 Chat、Judgement、Convergence 三种受限 Agent 工厂；默认工具集合为空或只读白名单。
4. 实现事件序列、单次终态、重复 `run_id` 处理和 Fake Provider。
5. 为每个端点写单元测试和合同 fixture。

阶段出口：三类运行在 Fake Provider 下可从请求走到完整终态；断流、取消、超时、重复运行和 readiness 失败均有确定结果。

### 阶段 2：建立 Python 执行边界

1. 在 `app/canvas/agent_execution/` 定义强类型合同与错误分类。
2. 实现唯一 `PiRuntimeClient`：NDJSON 分片解析、超时、取消、终态查询、事件映射和 trace 关联。
3. 写 Python ↔ TypeScript 跨语言合同测试。
4. 通过依赖注入接入 Product Kernel；暂不删除旧代码，直到阶段 6 完成主链切换。

阶段出口：Python 不需要知道 Pi 内部消息类、事件枚举或 Provider 对象，即可完成 Chat/Judgement/Convergence 合同调用。

### 阶段 3–4：产品控制面与 L3 生命周期

按“先职责、后并发”的顺序：

1. 先从 `CanvasService` 提取 Chat、判断、收敛和提交边界。
2. 再引入 message_seq、四类运行记录、包级租约和待重判水位。
3. 最后切换 stale、duplicate、unknown、Outbox 和恢复器。
4. 每个步骤同步改相邻测试；禁止先删除旧互斥再没有新生命周期实现。

阶段出口：新消息不会被后台收敛锁拒绝；旧回合不能部分写入；事实提交唯一经过 Verification → Governance → Commit。

### 阶段 5–6：工具、API 和真实联调

1. 先接入 Tool Gateway 和只读工具，再开放 Convergence Proposal Capture。
2. 通过内部 Token 验证运行范围、工具白名单、调用次数和到期时间。
3. FastAPI 只装配 Product Kernel 和 PiRuntimeClient；前端只适配新响应，不重做页面。
4. 提供统一开发入口，顺序为 Pi ready → FastAPI ready → Frontend ready。
5. 使用真实 Provider 完成模糊感觉、冲突、明确确认、stale、Pi 故障五类产品场景。

### 阶段 7–8：清理与封口

1. 按消费者扫描删除 `OpenAILLM` 在线构造、旧 AgentRuntime/WorkflowEngine 主链依赖、active turn 409、长期确认等待和过期测试夹具。
2. 保留仍有独立价值的通用底座，但不得让其成为第二个真实模型入口。
3. 做全仓引用扫描、依赖扫描、全新环境启动、故障注入、安全测试和文档核对。
4. 任一硬门未通过，分支不得合并；不在新架构里重新启用旧内核作为回退。

## 6. 提交拆分与验证节奏

同一分支内按以下可审查提交推进；当前已完成第 0 项，并完成第 1 项的最小运行时骨架：

1. `docs: freeze Pi runtime execution plan and contracts`
2. `test: freeze Pi runtime product contracts and L3 scenarios`
3. `feat: add stateless Pi runtime service`
4. `feat: add typed Python Pi execution client`
5. `refactor: separate chat judgement convergence and commit`
6. `feat: implement ordered messages and convergence scheduling`
7. `feat: add package lease stale checks and recovery`
8. `feat: add read-only tool gateway and proposal capture`
9. `refactor: switch canvas APIs to the Pi product kernel`
10. `test: add Pi end-to-end and governance hard gates`
11. `chore: remove replaced execution paths and old runtime state`
12. `docs: align runtime architecture and development guide`

每个提交只完成一个结构变化，必须带相邻测试或说明；不混入无关格式化。是否提交由后续阶段的验证结果决定，本轮不自动提交。

## 7. 停止门与需要重新确认的情况

出现以下任一情况，暂停当前阶段并重新核对，不用默认假设掩盖：

- 发现必须保留的真实联调数据、用户数据或旧接口外部消费者。
- Pi SDK 的实际导出、版本或 Node 要求与设计稿不一致，导致合同无法实现。
- 主 PRD 与 L3 Harness 对同一对象、状态、确认或提交规则冲突。
- 需要新增公网入口、外部副作用、写工具、第二事实源或第二真实模型执行器。
- 删除旧模块会影响通用会话、事件、工具、存储或运行时基础能力，且尚无安全替代。
- 前端或后端需要引入新的产品页面、卡片类型、阶段状态机或长期确认队列才能闭环。

## 8. 当前交付与下一步

阶段 0 已完成：新分支、执行计划、Python ↔ Pi 接口合同、Tool Gateway 约束、运行记录边界、事件/错误/恢复规则、机器可读 Schema、13 个合同/L3 fixture 测试、旧链消费者与数据 preflight。阶段 1 已建立 `pi-runtime/` 的 ESM TypeScript 服务骨架、RunRegistry、Fake Provider、health/readiness/capabilities、三类运行端点、终态查询、取消和 Node 合同测试。阶段 2 已建立 `app/canvas/agent_execution/` 的强类型合同、`AgentExecutionPort`、唯一 `PiRuntimeClient`、NDJSON/终态查询/稳定错误映射/取消，并完成 5 个 Python 跨语言边界测试和一次真实本地 Fake Runtime 联调。阶段 3 已建立 `ProductKernel` 的 Chat/Judgement/Convergence/唯一 Governed Commit 窄边界，并把它作为显式可注入入口挂到 `CanvasService`；未配置时明确失败，不静默回退旧 LLM。阶段 4 已完成消息仓储的 `message_seq` 单调追加、旧 JSONL 兼容补序和跳号拒绝，以及 `ChatTurn`、`ConvergenceJudgement`、`ConvergenceRun`、`CommitAttempt` 的原子 upsert、包级租约抢占/释放/过期重占、judgement watermark 单调推进和 Outbox 状态恢复；现有 `_commit_canvas_state` 已将包版本引用写入 pending Outbox，相关 8 个专门测试和 Canvas 回归通过。提交前版本检查已映射为 `PackageVersionStaleError(base_version_changed)`，但尚未切换在线提交入口。

下一步固定为阶段 4 的运行记录与包级租约：先落 `ChatTurn`、`ConvergenceJudgement`、`ConvergenceRun`、`CommitAttempt` 的 Python 持久化 schema，再实现同包 lease、judgement watermark、提交前版本检查和 Outbox 恢复；继续保留旧执行链作为未切换的底座，直到阶段 6 主链联调完成。在此之前不删除 `OpenAILLM`、`WorkflowEngine` 或 `active_turn`，也不把 Fake Provider 当作生产模型能力。

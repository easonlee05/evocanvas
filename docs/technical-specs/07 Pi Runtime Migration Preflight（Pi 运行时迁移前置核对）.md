# Pi Runtime Migration Preflight（Pi 运行时迁移前置核对）

> 核对日期：2026-08-20
>
> 分支：`codex/pi-runtime-core-refactor`
>
> 关联：[执行计划](../../plans/2026-08-14-evocanvas-pi-runtime-core-execution-plan.md)、[阶段 0 矩阵](./06%20Pi%20Runtime%20Phase%200%20Matrices（Pi%20运行时阶段%200%20矩阵）.md)

本文记录阶段 0 前置核对及阶段 5 实现后的当前代码、测试和仓库数据边界；不把旧实现行为当作新架构合同，也不执行删除或数据迁移。

## 1. 分支与工作区安全

- 当前分支：`codex/pi-runtime-core-refactor`。
- 阶段 0 文档已形成首个分支提交；当前已完成 Canvas HTTP 主链的 Pi 装配，但旧通用 Task 底座和显式遗留入口仍保留。
- 工作区仍有用户未跟踪资产：`.trae-html-share-packages/`、`docs/superpowers/specs/2026-08-09-canvas-stability-refactor-design 2.md`、`plans/2026-08-13-evocanvas-pi-runtime-core-refactor-design.md`。
- 后续提交只允许显式添加 Pi 迁移文件，禁止 `git add .`，不覆盖或顺带格式化上述资产。

## 2. 当前在线执行链

### 2.1 FastAPI 装配

通用 Task API 的默认装配仍保留旧底座，但旧 Provider/WorkflowEngine 已改为懒加载，Canvas 依赖独立装配 Pi：

```text
FakeStorage + ToolService + GBrainKnowledge
  -> LazyLegacyWorkflowEngine（仅旧任务 API 触发时创建 OpenAILLM/WorkflowEngine）
  -> TaskService
  -> TaskService.canvas_execution（未注入时由 PiRuntimeClient 环境装配）
  -> CanvasService(storage, PiRuntimeClient)
```

`/api/canvas/workspaces/{workspace_id}/messages` 现在异步调用 `CanvasService.run_pi_turn()`，主链经过 `PiRuntimeClient`、NDJSON 终态查询和 Python `ProductKernel`。未配置 Pi Runtime 时返回明确运行时错误，不静默回退旧 LLM。

### 2.2 Canvas 主链

旧 `CanvasService.start_turn()` 仍作为迁移期间的显式遗留入口保留；新的 HTTP 主链由 `PiCanvasKernel` 承担：

- `PiCanvasKernel` 保存 User/Assistant 消息并分配 `message_seq`；
- `ChatTurn`、`ConvergenceJudgement`、`ConvergenceRun`、`CommitAttempt` 进入 Python 运行记录；
- Chat 完成后显式调用 Judgement；需要时通过包级租约进入 Convergence；
- Pi 提案重新经过 Verification、Governance 和唯一 `Governed State Commit`；
- SSE 事件只作为运行通知和投影触发，不成为事实源。

旧 `CanvasService.start_turn()` 仍同时承担：

- 工作区级 `active_turn` 互斥；
- User 消息写入；
- `CanvasSupervisor` 关键词/旧角色规划和 LLM 调用；
- Assistant 提案消息；
- Verification、Governance、PackageVersion、Ledger 和 ConfirmationRecord；
- SSE 事件和完成/失败回执。

目标拆分为：

```text
Message Intake
  -> ConversationOrchestrator / ChatTurn
  -> Judgement + Scheduler
  -> ConvergenceRun + Proposal
  -> Verification -> Governance -> Governed State Commit
  -> Projection
```

### 2.3 旧链消费者

| 组件 | 当前消费者/事实 | 迁移结论 |
| --- | --- | --- |
| `app/services/llm.py` / `OpenAILLM` | FastAPI、CanvasSupervisor、WorkflowEngine、CLI/测试 | 阶段 2 先隔离；阶段 7 从 EvoCanvas Agent 主链移除 |
| `app/services/agent_runtime/` | `SubagentService` 和旧 JSON tool loop | 不作为 Pi 执行器；逐项核对后迁移或删除 |
| `app/workflows/engine.py` | 旧 Task API 和静态 Canvas workflow 定义；Canvas 消息主链实际绕过它 | 不接入 Pi 主链；通用 Task 能力与 EvoCanvas 解耦 |
| `app/canvas/agent/supervisor.py` | CanvasService 规划、旧角色语义和关键词 fallback | 被 Chat/Judgement/Convergence 编排替换；领域验证和提交继续复用 |
| `app/canvas/repository.py` | PackageVersion、Ledger、ConfirmationRecord、消息和文件存储 | 复用；补运行记录、message_seq、租约、水位、Outbox |
| `frontend/src/api.js` | 通用 fetch/fallback；无 typed Pi 合同和取消 | 阶段 6 适配 Product API，浏览器不直连 Pi |

## 3. 已发现的语义冲突与处理

### 3.1 工作区级 active turn

当前 `CanvasWorkspace`、`CanvasRepository`、`CanvasService` 和测试仍维护 `active_turn_id/status/started_at`，新消息可能返回 `409 turn_in_progress`。这与 L3 的“消息先保存、Chat 不持有收敛租约”冲突。

处理：新的 Pi HTTP 主链已不调用工作区级 `active_turn` 锁；旧直接入口和旧测试夹具暂时保留，阶段 7 在消费者与数据 preflight 后删除在线阻塞语义。

### 3.2 约束的 `pending_confirmation`

当前 `app/canvas/domain/object_status.py` 允许 constraint 使用 `pending_confirmation`，而 L3 Convergence Operations 规定未确认的约束提议只留 Chat，不写入约束对象。待澄清和待决策可以保留待确认/候选信息地位，但约束不能用同一状态偷渡。

处理：阶段 0 将其列为硬门；阶段 3/4 实现新 Proposal/Governance 时必须先确定转换规则，并同步领域状态、测试和前端投影。

### 3.3 交接门槛

当前 Canvas/Handoff 投影同时表达草稿、确认和待处理状态。目标需区分：

- 普通包更新后的可读交接草稿显影；
- 达到治理条件后的已确认版本；
- 正式外发或外部副作用的独立门禁。

本次不增加长期审批队列；任何外部副作用仍需单独门禁。

### 3.4 Context Assembly 成熟度

Context Assembly、Conversation Working Surface 和 Prompt Control 的部分规则仍是 L2。接口合同只冻结 `Context Manifest` 的引用、版本、消息范围、遗漏和 transport 证据，不冻结历史选择、压缩、排序和复水算法。

阶段 5 已补充临时 `runtime_inputs` 快照，真实 Provider Adapter 现在可以消费 Python 选定的用户原话与消息范围；正式 Context Assembly 的压缩、预算和跨 Adapter 一致性矩阵仍未封口，继续由 Python 负责上下文装配。

阶段 6 已补充共享 `runtime_inputs` 合同 fixture、Gateway 业务错误码透传和消息范围绑定的 Run-scoped Token。未配置真实 Provider、凭证或可用 Pi Runtime 时仍应明确返回 `not_ready`/运行时错误，不得回退旧链。

### 3.5 前端边界

当前前端存在若干旧响应/事件假设（例如 `active_turn`、`pending_confirmation`、确认事件名和卡片创建响应形状）。阶段 6 只做必要 API 适配；在此前不将前端旧形状反向提升为 Pi 合同。

## 4. 数据 preflight

### 4.1 已核对

- 仓库测试使用 `FakeStorage` 和临时目录；未发现需要在本分支直接迁移的生产数据库或正式联调数据文件。
- Canvas 当前文件存储路径包含 `workspace.json`、`packages/`、版本文件、`state_ledger.jsonl`、`confirmations/`、`proposal_history.jsonl`、`chat_messages.jsonl` 等，具备继续复用的事实存储资产。
- 旧 `confirmation_queue` 路由已下线，仓储注释也声明不再写入新审批队列；但旧状态字段和测试夹具仍存在，不能据此直接删除。

### 4.2 尚未证明

- 未扫描或读取用户机器上 `/tmp/manual-agent-phase1` 之外的个人数据目录；本报告不把“仓库内未发现”扩大为“机器上绝无数据”。
- 尚未证明旧 API、CLI、SubagentService 没有外部调用者。
- 尚未证明所有旧工作区都能无损生成初始 `package_id`、版本 1、来源和确认迁移报告。

### 4.3 删除前硬门

在阶段 7 删除前必须完成：

1. 真实工作区/包/消息/确认/外部消费者盘点。
2. 若存在需保留数据，先完成迁移方案和可验证性报告；不使用猜测补全。
3. 对 `active_turn`、旧确认状态、旧任务运行记录执行只读抽样和引用扫描。
4. 明确通用会话、事件、工具、存储和运行时底座的保留/解耦路径。
5. 保存删除前测试快照，完成全仓引用扫描后才可移除。

## 5. 阶段 0 出口状态

- [x] 新分支和首个计划/合同提交已建立。
- [x] Python ↔ Pi 请求、结果、事件、错误、取消、Tool Gateway 和 Proposal Schema 已定义。
- [x] 生命周期、Provider、工具、错误恢复和迁移矩阵已形成初稿。
- [x] 当前在线入口、旧执行链消费者和主要语义冲突已核对。
- [x] 仓库内测试/存储数据边界已完成只读 preflight。
- [x] v1 Schema/请求/结果/事件/Proposal/Tool/Error 合同测试加入并通过（6 tests）。
- [x] Pi 包版本、Node 要求和 SDK exports 完成网络/安装核对：Node `v22.23.1`、npm `10.9.8`；`@earendil-works/pi-agent-core@0.84.1` 与 `@earendil-works/pi-ai@0.84.1` 可解析、可 dry-run 安装，exports 可见且满足 Node `>=22.19.0`。
- [x] Pi 依赖 lockfile 已完成；`pi-runtime/package-lock.json` 已生成，并通过 package override 将 `pi-telemetry` 固定到 `0.84.2`，避免 `^0.84.1` 的漂移。
- [x] 失败样本与 L3 场景已进入合同测试 fixture；`tests/test_pi_runtime_l3_scenarios.py` 的 7 个场景测试通过。

阶段 0 的合同与安装核对已完成，阶段 5 已完成真实 Adapter、只读 Tool Gateway、Run-scoped Token、Proposal Capture、deadline、临时输入快照和 Gateway smoke；正式 OpenAI/Anthropic 凭证联调、Context Assembly 预算/压缩矩阵、前端适配和旧链清理仍属于后续阶段，不能把 Faux/Fake 合同测试当作正式 Provider 生产验收。

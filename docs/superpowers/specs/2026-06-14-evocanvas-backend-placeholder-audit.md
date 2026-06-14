# EvoCanvas 后端占位与待完善点统计

> 日期：2026-06-14  
> 范围：`app/canvas/`、Canvas API、Canvas workflow 接入、相关测试。  
> 目的：统计当前后端重构中哪些部分还只是占位、半成品或最小可跑实现，便于后续按优先级补齐。  
> 说明：本文只做盘点，不把旧 Evoloop 兼容层全部视为缺陷；只有影响 EvoCanvas 1.0 主路径的点才列入优先级。

## 0. 当前判断结论

当前后端不是纯占位，已经有一条能跑通的最小主路径：

`POST /messages -> CanvasSupervisor 静态意图识别 -> mutation proposal -> governance -> 自动写入或确认队列 -> GET /canvas /handoff /snapshots`

但这条路径仍然偏“样板化/规则拼接”，距离真正的 EvoCanvas agent 能力还有明显差距。最大问题不在数据类是否存在，而在：

1. Agent 还没有真正读取 workspace context 做推理。
2. 内部角色没有真实执行，`RoleOutput` 契约基本未接入。
3. Mutation 应用层只识别少数硬编码 mutation 类型。
4. API 能跑，但缺少完整错误语义、快照创建、handoff 刷新、手动编辑等 1.0 关键接口。
5. Workflow registry 里有 `canvas_turn` 定义，但还没有真正驱动 `CanvasService`。
6. 仍有旧 `PM-Agent / EvoLoop / PRD / manual-agent` 语义留在 API 与通用 workflow 入口中。

## 1. 已经具备的真实能力

| 模块 | 当前能力 | 不是占位的依据 | 评价 |
| --- | --- | --- | --- |
| Canvas domain | Workspace、Card、Relation、Snapshot、Handoff、Mutation 数据结构可序列化 | `tests/test_canvas_domain.py` 覆盖 roundtrip | 基础对象成立 |
| Repository | workspace、cards、relations、handoff、snapshots、confirmation queue 可落盘 | `tests/test_canvas_repository.py` 覆盖部分读写 | 可用于本地最小闭环 |
| API | `/api/canvas/workspaces/*` 已接入 FastAPI | `tests/test_canvas_api.py`、`tests/test_canvas_turn_flow.py` 覆盖 | 主路径存在 |
| Governance | 低风险自动应用，高风险进入确认队列 | `tests/test_canvas_governance.py` 覆盖 | 规则骨架成立 |
| Confirmation | approve/reject 对 decision proposal 有实际画布后果 | `tests/test_canvas_confirmation_api.py` 覆盖 | 比占位更进一步 |
| Turn guard | 同一 workspace active turn 有并发保护 | `tests/test_canvas_turn_flow.py` 覆盖 | 单进程可用 |
| Handoff snapshot | handoff turn 可刷新 handoff 并生成 snapshot | `tests/test_canvas_turn_flow.py` 覆盖 | 最小闭环可演示 |

## 2. P0：必须优先补齐的半成品

### 2.1 Agent 仍是静态关键词路由，不是真正 agent 推理

涉及文件：

- `app/canvas/agent/supervisor.py`
- `app/canvas/agent/roles.py`
- `app/canvas/agent/contracts.py`
- `app/canvas/service.py`

当前表现：

- `CanvasSupervisor.recognize_and_plan()` 只用关键词匹配。
- `workspace_context` 被忽略。
- `llm` 注入存在，但 supervisor 没有真实调用。
- `RoleOutput` 定义了角色输出契约，但目前没有角色执行器产出它。
- `InputCompiler / Clarifier / ConstraintSteward / DecisionSteward / HandoffBuilder` 只是静态角色名和允许 mutation 类型。

影响：

- Agent 看起来能回复，但实际不会根据当前卡片、冲突、证据、历史决策做判断。
- 无法满足“像产品同事一样先暴露不确定性”的核心要求。
- 后续一旦输入复杂，系统会退化成关键词触发器。

建议补法：

1. 让 supervisor 真正读取 `cards / relations / handoff / pending confirmations / selected cards / material refs`。
2. 增加 `CanvasRoleRunner` 或 `RoleExecutor`，每个角色返回 `RoleOutput`。
3. 将 `RoleOutput.proposed_mutations` 合并成 `CanvasMutationProposal`，而不是在 service 里按角色名硬编码生成。
4. 对冲突、缺信息、来源不一致建立显式 mutation 类型，例如 `mark_conflict`、`add_open_question`。

### 2.2 Mutation 应用层是硬编码分支，不是通用 mutation reducer

涉及文件：

- `app/canvas/service.py`
- `app/canvas/domain/mutations.py`

当前表现：

- `_apply_proposal()` 只处理少数 mutation type：
  - `add_card`
  - `promote_to_constraint_draft`
  - `create_decision_request`
  - `refresh_handoff_card`
  - `refresh_handoff_draft`
- `CanvasMutationAction.UPDATE / REMOVE` 没有通用 reducer。
- `CanvasMutationTarget.RELATION / SNAPSHOT` 基本未被独立处理。
- mutation 的 `requires_confirmation` 与 `rationale` 没有完整落地到审计视图。

影响：

- 新增 agent 行为时，每次都要改 `_apply_proposal()`。
- 不利于前端展示“AI 建议了什么、为什么建议、是否已应用”。
- 无法稳定支持手动编辑、撤销、diff、快照回放。

建议补法：

1. 建立 `CanvasMutationReducer`，按 `target + action` 分派。
2. 所有 mutation 都保存到 proposal history，而不是只保存 confirmation queue。
3. 对未知 mutation 明确返回失败事件，不静默忽略。
4. 增加 reducer 测试：add/update/remove card、relation、handoff、snapshot。

### 2.3 Workflow 只注册了定义，没有接入真实 CanvasService

涉及文件：

- `app/workflows/canvas_session.py`
- `app/workflows/definitions.py`
- `app/workflows/executors.py`

当前表现：

- `canvas_turn` workflow 的 metadata 仍标记 `scope: definition_only`。
- workflow step 中有 `load_canvas_context / run_canvas_supervisor / merge_canvas_proposal / emit_canvas_events`，但没有实际绑定 `CanvasService`。
- 真实请求路径目前绕过 workflow，直接由 API 调 `CanvasService.start_turn()`。

影响：

- 现有 workflow runtime、event、trace、tool policy 没有真正支撑 EvoCanvas turn。
- 未来如果要复用 Evoloop 底座的任务追踪能力，需要二次接线。

建议补法：

1. 明确取舍：短期是否继续绕过 workflow。
2. 如果要接入 workflow，应新增 executor step，把 `CanvasService.start_turn()` 拆成可观测步骤。
3. workflow 事件应输出 Canvas 原生事件，而不是旧 task log。

### 2.4 API 形态还缺 1.0 关键写接口

进度：

- [x] `PATCH /api/canvas/workspaces/{workspace_id}/cards/{card_id}`：已支持卡片标题、摘要、状态和标签的原地修订，并保留卡片类型、来源与关系边界。
- [x] `POST /api/canvas/workspaces/{workspace_id}/relations`：已支持在已有卡片之间创建语义关系，并校验关系类型与端点卡片存在性。
- [x] `POST /api/canvas/workspaces/{workspace_id}/snapshots`：已支持用户手动保存当前画布状态为快照，并更新工作区当前快照指针。
- [x] `POST /api/canvas/workspaces/{workspace_id}/handoff/refresh`：已支持从当前画布显式刷新结构化交接物草稿，复用现有约束 / 待澄清 / 待决策聚合逻辑，并同步生成新快照。
- [x] `POST /api/canvas/workspaces/{workspace_id}/cards/{card_id}/move`：已支持受限的阶段带迁移，校验合法路径并保留卡片事实边界，同时记录迁移元信息。
- [x] `GET /api/canvas/workspaces/{workspace_id}/todos`：已支持独立读取当前画布或指定快照视角下的活跃缺口投影，并与 `GET /canvas` 的 Todo 口径保持一致。

涉及文件：

- `app/api/server.py`
- `app/api/canvas_schemas.py`
- `app/canvas/service.py`

当前已存在：

- `GET /api/canvas/workspaces/{workspace_id}`
- `GET /api/canvas/workspaces/{workspace_id}/canvas`
- `POST /api/canvas/workspaces/{workspace_id}/messages`
- `GET /api/canvas/workspaces/{workspace_id}/events`
- `GET /api/canvas/workspaces/{workspace_id}/confirmations`
- `POST /confirmations/{proposal_id}/approve`
- `POST /confirmations/{proposal_id}/reject`
- `GET /snapshots`
- `GET /handoff`

缺失接口：

- `POST /api/canvas/workspaces/{workspace_id}/snapshots`
- `POST /api/canvas/workspaces/{workspace_id}/handoff/refresh`
- `PATCH /api/canvas/workspaces/{workspace_id}/cards/{card_id}`
- `POST /api/canvas/workspaces/{workspace_id}/cards/{card_id}/move`
- `POST /api/canvas/workspaces/{workspace_id}/relations`
- `GET /api/canvas/workspaces/{workspace_id}/todos`（可选，但前端若单独刷新 Active Todos 会需要）

影响：

- 目前主要靠 agent turn 生成画布，缺少用户手动修订闭环。
- PRD 中“卡片标题/摘要原地编辑、排序、合法跨阶段迁移”还未接后端。

建议补法：

1. 先补 card patch / relation create，因为它们直接支持前端编辑。
2. 再补 manual snapshot create。
3. handoff refresh 可以复用 agent turn，也可以单独暴露接口；需要定一个唯一策略。

## 3. P1：影响产品可信度的待完善点

### 3.1 Confirmation 只对 decision 有完整物化，其他高风险动作不完整

涉及文件：

- `app/canvas/governance.py`
- `app/canvas/service.py`

当前表现：

- `create_decision_request` approve 后会把 decision card 状态改为 `confirmed`。
- `confirm_constraint` approve 后已可把既有 constraint draft 原地物化为 `effective`，并记录确认来源元信息。
- `resolve_clarification` approve 后已可把既有 clarification 原地物化为 `resolved`，并把 resolution 写入元信息。
- `promote_formal_handoff` approve 后已可把 handoff card 标记为 `confirmed`，并同步 workspace handoff 状态。
- AI 提议的 `create_snapshot` approve 后已可物化为真实 snapshot，并更新 workspace 当前快照指针。

影响：

- “高影响动作必须确认”的规则只在 decision 场景比较完整。
- 其他确认类型后续接入时容易出现“队列里看得到，但 approve 没实际后果”。

建议补法：

1. 给每类高风险 mutation 加 approve materializer。
2. 测试覆盖：
   - confirm constraint（已补）
   - resolve clarification（已补）
   - promote formal handoff（已补）
   - create snapshot（已补）

### 3.2 SSE 事件还不完整

涉及文件：

- `app/canvas/service.py`
- `app/api/server.py`

当前有：

- `canvas.turn.started`
- `canvas.mutation.proposed`
- `canvas.mutation.applied`
- `canvas.confirmation.requested`
- `canvas.turn.completed`
- `canvas.turn.failed`
- `canvas.confirmation.approved`
- `canvas.confirmation.rejected`

缺失或不足：

- `canvas.snapshot.created`
- `canvas.handoff.refreshed`
- `canvas.mutation.applied` / `canvas.turn.completed` 已覆盖 approve 后路径，但 payload 仍需随 reducer 扩展持续补齐更多 affected ids。

影响：

- 前端无法只靠 SSE 精准更新局部状态。
- 出错和等待确认后的状态变化不够可观测。

建议补法：

1. turn 开始、proposal 生成、应用、确认、完成、失败都发事件（已补）。
2. 每个事件 payload 统一包含 `workspace_id / turn_id / proposal_id / affected_card_ids`（已补最小口径，后续随 relation / snapshot reducer 扩展）。

### 3.3 Snapshot 当前是轻量快照，不是真正状态快照

涉及文件：

- `app/canvas/domain/snapshots.py`
- `app/canvas/service.py`
- `app/canvas/repository.py`

当前表现：

- snapshot 保存的是 active card ids、relation ids、todo projection、handoff。
- snapshot 已保存 card/relation 内容副本。
- `GET /canvas?snapshot_id=` 已优先从 snapshot payload 还原历史卡片与关系，不再因 live card 后续编辑而漂移。

影响：

- 如果某张 card 后续被编辑，旧 snapshot 看到的也是编辑后的内容，不是真正历史状态。
- 只能表达“当时有哪些对象”，不能表达“当时对象内容是什么”。

建议补法：

1. snapshot 中保存 card/relation 的内容副本，或引入对象版本号（内容副本已补）。
2. `GET /canvas?snapshot_id=` 应从 snapshot payload 还原，而不是读 live cards（已补）。
3. 增加测试：创建 snapshot 后编辑 card，旧 snapshot 内容不变（已补）。

### 3.4 Repository 仍是本地文件最小实现

涉及文件：

- `app/canvas/repository.py`

当前表现：

- cards/relations 使用聚合 JSON 文件。
- workspace 锁是进程内锁，不是跨进程文件锁。
- 已增加 proposal history jsonl，用于追溯提案生命周期。
- 设计文档曾建议的 `cards/{card_id}.json`、`relations/{relation_id}.json`、`proposals/{proposal_id}.json` 尚未实现。

影响：

- 本地单进程可用，多 worker 或真实部署不稳。
- 追溯能力不足。

建议补法：

1. 短期增加 atomic write，避免写一半文件损坏（已补 JSON 原子写）。
2. 中期增加 proposal history 与 events append log（proposal history 已补；events append log 未补）。
3. 长期换成数据库或带事务的 workspace store。

### 3.5 API 错误语义偏浅

涉及文件：

- `app/api/server.py`
- `app/canvas/service.py`

当前表现：

- confirmation approve/reject 找不到 proposal 时已返回 404。
- `snapshot_id` 不存在时 `GET /canvas` 与 `GET /todos` 已返回 404。
- message request 已有空消息、超长消息和非法 selected card id 校验。

影响：

- 前端不容易区分“正常空结果”和“请求错误”。
- 后续联调会出现 fallback 掩盖问题。

建议补法：

1. proposal not found 返回 404（已补）。
2. snapshot not found 明确返回 404 或 `is_snapshot=false + warning`，二选一（已补 404）。
3. `CanvasMessageRequest` 加校验和 `Field(default_factory=list)`（已补）。

## 4. P2：技术债与产品语义清理

### 4.1 旧产品语义仍留在 API 文件

涉及文件：

- `app/api/server.py`
- `app/workflows/context_compiler.py`
- `app/workflows/definitions.py`

表现：

- `server.py` 顶部仍写“PM-Agent 后端及对接 EvoLoop 前端”。
- 默认临时目录仍叫 `manual-agent-phase1`。
- API 文件后半仍有 PRD、知识库、可信规则等旧 demo 文案。

影响：

- 不一定阻塞功能，但会混淆 EvoCanvas 主路径。
- 新人读代码容易误判当前产品中心。

建议补法：

1. Canvas API 后续拆成 `app/api/canvas_routes.py`。
2. 旧 `/api/tasks/*` 保持兼容，但注释明确为 legacy substrate。
3. 临时目录命名逐步改成 `evocanvas`。

### 4.2 `FakeLLM` fallback 容易掩盖真实模型未接入

涉及文件：

- `app/canvas/service.py`
- `app/services/fakes.py`

表现：

- `CanvasService` 默认 `llm or FakeLLM()`。
- supervisor 当前也不使用 llm。

影响：

- 测试方便，但真实 agent 能力可能被“看起来可运行”掩盖。

建议补法：

1. 测试中显式注入 FakeLLM。
2. 生产服务启动时如果没有真实 llm，标记 degraded。
3. health 或 canvas workspace meta 暴露 agent runtime 状态。

### 4.3 `mode` 参数暂未使用

涉及文件：

- `app/api/canvas_schemas.py`
- `app/canvas/service.py`

表现：

- `CanvasMessageRequest.mode` 存在。
- `CanvasService.start_turn()` 里 `del mode`。

影响：

- 前端传 `mode` 没有效果。
- 如果 UI 有“默认/聚焦/交接”等模式，会造成用户误解。

建议补法：

1. 如果 1.0 不需要 mode，先从 API schema 去掉。
2. 如果需要，定义枚举：`default / compile / clarify / handoff`。
3. mode 应影响 supervisor 路由优先级，而不是只做透传字段。

## 5. 我刚才误补的实现点，需要单独 review

用户要求是“找和统计”，但我刚才误以为要继续修，已经补了少量实现。它们需要后续 review 是否保留：

| 改动点 | 涉及文件 | 当前状态 | 是否建议保留 |
| --- | --- | --- | --- |
| input compilation 生成 evidence/problem/clarification 三张卡 | `app/canvas/service.py`、`tests/test_canvas_turn_flow.py` | 已实现并有测试 | 倾向保留，但标题/摘要生成规则仍很粗 |
| handoff turn 同步生成 handoff card | `app/canvas/service.py`、`tests/test_canvas_turn_flow.py` | 已实现并有测试 | 倾向保留，符合 PRD“交接物卡” |
| `GET /canvas?snapshot_id=` 可过滤 snapshot id | `app/canvas/service.py`、`app/canvas/repository.py` | 已实现并有测试 | 只算半成品，因为不是内容级历史快照 |

这些改动虽然方向合理，但不是用户刚才要求的“只统计”。后续如果你希望严格回到“只做文档”，可以单独让我撤销这三处误补。

## 6. 建议后续收束顺序

### 第一批：让 agent 不再像占位

1. Supervisor 使用 workspace context。
2. Role runner 返回 `RoleOutput`。
3. Role output 合并为 mutation proposal。
4. 增加 `canvas.mutation.proposed` 事件。

### 第二批：让 mutation 系统不再硬编码

1. 抽 `CanvasMutationReducer`。
2. 完整支持 card/relation/handoff/snapshot 的 add/update/remove。
3. proposal history 落盘。

### 第三批：补前端真正需要的写接口

1. card patch。
2. relation create。
3. manual snapshot create。
4. handoff refresh/formalize。

### 第四批：清理旧语义和部署风险

1. Canvas routes 从 `server.py` 拆出。
2. 生产环境不默认 FakeLLM。
3. repository 增加 atomic write 或换数据库。
4. 清理 `manual-agent-phase1`、PM-Agent、PRD demo 文案。

## 7. 当前最需要确认的产品/技术决策

1. `snapshot` 是只记录对象 ID，还是必须记录内容副本？
2. `mode` 是否进入 1.0 API？
3. Handoff 是否一定要作为 canvas card 落地，还是只作为独立 handoff 文档？
4. Agent 是否优先接真实 LLM，还是先做规则化 role runner？
5. API 是否允许继续堆在 `server.py`，还是现在就拆 `canvas_routes.py`？

# EvoCanvas 后端与 Agent 设计执行文档

> 状态：评审中草案
> 最后更新：2026-06-14
> 范围：EvoCanvas 1.0 后端重构，首要聚焦 Canvas 与 Agent 能力
> 协作方式：本文档用于持续增量更新，后续每确认一条设计结论，就在本文档中追加或修订

## 1. 背景

EvoCanvas 1.0 不是 PRD 生成器，也不是通用白板工具。后端必须服务于 [docs/vision/EvoCanvas1.0-PRD.md](/Users/apple/Desktop/evocanvas/docs/vision/EvoCanvas1.0-PRD.md) 中定义的 1.0 最小闭环：

`输入编译 -> 待澄清问题 -> 约束 / 待决策 -> 结构化交接物`

当前前端已经明显向 EvoCanvas 形态收敛，但后端仍然保留大量 Evoloop 旧产品语义，例如：

- `manual-agent-phase1`
- `legacy_manual` / `legacy_prd`
- 以 `machine_spec` 为中心的真相源表达
- 围绕 spec / review 交付物设计的 peer delivery 流程

与此同时，仓库里又已经存在一套不应被随意抛弃的通用底座：

- 任务生命周期管理
- 事件总线与 SSE 流式推送
- 受控的 `AgentSession`
- 受治理的 `Subagent`
- arbitration / `DecisionGate`
- 存储、上下文、产物、会话等基础设施

因此，这次后端重构的本质应当是：

- 保留底座
- 替换产品语义中心
- 让后端围绕 EvoCanvas 1.0 的对象模型和 agent 交互方式重新组织

这不是全量重写，而是一次语义主轴迁移。

## 2. 已确认方向

以下产品与架构方向已经确认。

### 2.1 交付层级

第一阶段后端目标不是只做“能跑的接口”，而是实现：

- 真实 Canvas 后端
- 真实 Agent 后端
- 可编辑 Canvas 支持

这意味着：

- 前端不能继续把 demo 数据当作系统真相源
- agent 需要真正驱动画布变化
- 画布编辑、状态迁移、交接物收敛都要进入真实后端能力范围

### 2.2 Agent 形态

Agent 方案已确认采用：

- 前台一个可见助手
- 后台多个内部角色分工

也就是说，用户只看到一个 `Canvas AI`，但后端内部由多个专职角色协同完成一次画布更新。

### 2.3 Subagent 复用策略

已确认可以借鉴并复用旧 Evoloop 的 `subagent` 思路。

复用原则已经明确为：

- 保留 `subagent` 作为内部受控执行原语
- 不再让旧的 spec-centric 产品语义继续充当 EvoCanvas 的产品中心

### 2.4 变更治理策略

已确认默认写入策略为：

- 低风险变更自动写入
- 高影响动作必须确认

这将成为 EvoCanvas 1.0 agent 行为的基本规则。

## 3. 已确认总体架构

后端建议拆成 4 层协作结构，并优先复用现有底座。

### 3.1 Canvas Domain

这一层是新的 EvoCanvas 原生领域层，用来替代旧的文档 / spec 中心语义，成为 EvoCanvas 1.0 的主要真相源。

职责：

- 表达当前 workspace 状态
- 表达 Canvas 卡片和关系
- 表达快照与 Todo 投影
- 表达结构化交接物状态
- 表达 agent 提出的待应用 mutation

结论：

- 这一层应成为 EvoCanvas 1.0 的产品真相层
- 不再以 `machine_spec` 或旧 PRD 产物作为产品主轴

### 3.2 Canvas Agent Orchestrator

这一层驱动用户看到的单一 `Canvas AI`。

职责：

- 接收用户输入和当前 workspace 上下文
- 识别这轮输入的意图
- 调度内部 agent 角色
- 汇总内部角色输出
- 合并成一份受治理的 mutation proposal

结论：

- 编排层应借用现有 `AgentSession`、`SubagentService` 和受控 schema 输出机制
- 但输出目标必须从“交付 spec”切换为“驱动画布收敛”

### 3.3 Mutation Governance

这一层负责判断 agent 产出的变更到底如何落盘。

职责：

- 判断哪些可以自动应用
- 判断哪些必须请求用户确认
- 判断哪些当前不能写入，只能追问

结论：

- 这是旧 arbitration / `DecisionGate` 能力的产品化落点
- 它是 EvoCanvas agent 安全、可追溯和不乱写状态的关键

### 3.4 Delivery API + Event Stream

这一层负责给前端提供真实的 Canvas 状态与 agent 事件。

职责：

- 提供 workspace / Canvas 状态读取
- 提供待确认事项读取
- 提供 mutation 应用与确认接口
- 提供 snapshot / handoff / todo 读取能力
- 通过 SSE 推送 agent 和 Canvas 语义事件

结论：

- 现有 `/api/tasks/*` 与 SSE 机制可作为迁移支架
- 但对前端暴露的语义应逐渐转向 EvoCanvas 原生接口

## 4. 已确认核心领域模型

后端不应让 agent 直接修改任意前端 JSON。应先定义 EvoCanvas 原生领域对象，再让 agent 输出结构化 mutation。

### 4.1 CanvasWorkspace

表示一个 PM 当前正在推进的工作台。

建议职责：

- workspace 唯一标识
- 标题与当前目标
- 关联输入材料与上下文
- 当前活动 snapshot id
- 当前 handoff 状态
- 与 agent 会话有关的元信息

### 4.2 CanvasCard

统一卡片模型，首版仅保留 1.0 必须范围内的卡片类型：

- `evidence`
- `problem`
- `clarification`
- `constraint`
- `decision`
- `handoff`

每张卡片至少应支持：

- 稳定 id
- title
- summary
- card type
- 所在 stage / module
- draft / active / resolved / superseded 等状态
- source refs
- 必要的确认元数据

### 4.3 CanvasRelation

只保留高价值关系，不扩张成复杂图谱系统。

建议关系类型：

- `derived_from`
- `clarifies`
- `supports`
- `blocks`
- `conflicts_with`
- `produces`

### 4.4 CanvasSnapshot

快照不是整库复制，而是某个关键时刻的“有效认知结构视图”。

每个 snapshot 至少记录：

- 活跃 card id 集合
- 当时的 card 状态
- 活跃 relation 集合
- Todo projection
- 变化摘要
- 具备业务含义的 snapshot 标题

### 4.5 TodoProjection

Todo 不是事实源，只是当前画布缺口的投影视图。

它主要应由以下对象衍生：

- 未关闭 clarification
- 未完成 decision
- 尚未确认的 draft constraint

### 4.6 StructuredHandoff

交接物应同时具备两种存在方式：

- 作为一张 `handoff` 卡片出现在 Canvas 中
- 作为一份可复用的结构化正文在系统中独立存放

建议最小字段：

- objective
- background inputs
- confirmed constraints
- open questions
- pending decisions
- recommended next actions
- source snapshot id

### 4.7 CanvasMutation

这是 agent 驱动画布变化的核心执行单元。

建议 mutation 类型：

- `add_card`
- `update_card_summary`
- `update_card_title`
- `mark_conflict`
- `add_relation`
- `move_card_stage`
- `promote_to_constraint_draft`
- `confirm_constraint`
- `create_decision_request`
- `resolve_clarification`
- `refresh_handoff_draft`
- `create_snapshot`

### 4.8 MutationProposal

Proposal 用来把一批 mutation 组织成一次可治理的变更提议。

每份 proposal 建议包含：

- proposal id
- 来源消息 / turn id
- 涉及的内部角色
- mutation 列表
- evidence refs
- rationale summary
- risk level
- 是否需要确认

## 5. 为什么必须先产出 Mutation 再写入

这是本次设计里的核心原则。

Agent 不应直接把“最终画布状态”作为第一输出，而应该始终先输出 `CanvasMutation`。

原因：

- 可以保留可解释性
- 可以在落盘前做风险治理
- 可以支持 snapshot 与 diff 生成
- 可以准确区分哪些是自动整理、哪些是用户确认
- 可以避免把模糊输入静默写成稳定状态

这和 EvoCanvas 1.0 的原则完全一致：

`先暴露不确定性，再沉淀约束，再形成待决策，最后生成交接物`

## 6. 已确认 Agent 方案

已确认采用：

- 一个前台可见助手
- 多个后台内部角色
- 一个统一 Supervisor 编排器

### 6.1 前台可见形态

前端始终只看到：

- 一条对话
- 一个助手身份
- 一条连续的总结 / 追问 / 确认提示流

### 6.2 内部固定角色

首版建议固定为 5 个内部角色，不做无限扩张。

#### Input Compiler

职责：

- 接收新输入
- 提取 evidence
- 形成初步 problem
- 生成第一批 clarification

#### Clarifier

职责：

- 识别歧义
- 识别缺失上下文
- 识别输入间冲突
- 优先提出待澄清，而不是抢先下结论

#### Constraint Steward

职责：

- 识别稳定边界
- 生成 draft constraint
- 不默认把约束直接标记为已生效

#### Decision Steward

职责：

- 判断当前问题是不是“缺信息”，还是“缺人拍板”
- 生成 decision 候选项、影响范围和选项说明

#### Handoff Builder

职责：

- 汇总当前 structured handoff draft
- 明确保留未解决缺口，而不是伪装成已经收敛完成

### 6.3 Supervisor 职责

`Canvas Supervisor` 负责：

- 判断当前用户输入意图
- 选择要运行哪些内部角色
- 限制这一轮允许产生的 mutation 范围
- 合并多个内部角色的结构化输出
- 当内部结果冲突时，优先升级为 clarification 或 decision，而不是静默摊平

## 7. 已确认 Agent 执行流

每一轮用户输入进入后端后，建议遵循如下顺序。

### 7.1 加载输入上下文

加载：

- workspace 状态
- 当前 active snapshot
- 当前选中的 card
- 最近会话消息
- 相关 source inputs

### 7.2 意图识别

把当前轮次归类为一个或多个 EvoCanvas 意图：

- 输入编译
- 待澄清推进
- 约束沉淀
- 待决策生成
- 交接物收束

### 7.3 调度内部 Subagents

只运行当前轮次真正需要的内部角色。

执行规则：

- 内部角色不能直接写存储
- 内部角色只能返回结构化输出

### 7.4 内部角色标准输出

每个角色建议统一返回：

- findings
- proposed mutations
- evidence refs
- confidence
- open questions
- requires human confirmation

### 7.5 Supervisor 合并

Supervisor 把多个角色输出合并成一份统一的 `MutationProposal`。

当角色输出互相冲突时：

- 不得静默合并
- 优先新增或更新 clarification
- 若问题已不再是“信息不足”而是“必须拍板”，则升级为 decision

### 7.6 进入治理层

Proposal 进入 mutation governance 之后，只能产生三类结果：

- 自动应用
- 请求确认
- 不写画布，转为追问

### 7.7 持久化与事件推送

治理层判定后：

- 低风险 mutation 直接落盘
- 高影响 mutation 进入待确认队列
- 同时发出事件供前端同步

## 8. 已确认治理策略

这一节对应已经确认的产品默认规则。

### 8.1 自动写入示例

建议自动应用的低风险变更：

- 新增 evidence card
- 补充或修正 problem 描述
- 新增 clarification card
- 标记输入冲突
- 刷新 handoff draft 文案
- 刷新 Todo projection

### 8.2 必须确认示例

建议必须确认的高影响变更：

- 将 clarification 转成 confirmed constraint
- 将 constraint 标记为已生效
- 关闭关键 clarification
- 确认 decision 结果
- 生成关键 snapshot
- 覆盖或升级正式 handoff 状态
- 对重要 card 执行关键 stage 迁移

### 8.3 不写画布、先追问的情形

当出现以下情况时，agent 不应直接改画布：

- 证据不足
- 内部角色结论明显冲突
- 用户输入过于模糊，无法安全归类

此时系统应：

- 发出追问
- 明确说明“本轮未对画布做变更”

## 9. 现有 Evoloop 底座复用映射

目标不是推倒重来，而是保留好的基础设施，同时替换掉旧产品中心语义。

### 9.1 建议保留并复用

- `TaskService` 作为控制面底座
- `Event` 与 `EventBus`
- SSE 推送模式
- `AgentSession`
- `AgentRuntime`
- `SubagentService`
- budget / tool policy / schema-governed internal execution
- 现有 storage / context / session 基础设施

### 9.2 建议重新解释后复用

- `DecisionGate`：转化为 EvoCanvas 的确认流与待决策能力底座
- `ArtifactGraph`：保留“节点 + 边 + 可追溯关系”的思想，但不继续作为产品真相源
- `ProductContext`：其中的上下文组织思想可吸收到 `StructuredHandoff` 与 workspace context

### 9.3 建议弱化为非主路径

- `machine_spec` 作为产品中心真相源
- `legacy_manual` / `legacy_prd` 语义
- peer delivery package 作为核心产品输出
- formal spec/review loop 作为主要用户流程

### 9.4 建议保留但不放在 1.0 主语义中心

现有 formal subtask 与 peer collaboration 能力可以继续存在，作为后续可复用基础设施，但不应定义 EvoCanvas 1.0 的主产品路径。

## 10. API 方向

详细 API 契约尚未展开，但方向已经明确：

- 后端应逐步从旧 `/api/tasks/*` 迁到 EvoCanvas 原生接口语义
- 前端应最终面向真实 Canvas 状态与 mutation 流工作

预计 API 分组：

- workspace 读取
- Canvas 状态读取
- 用户消息 / agent turn 提交
- mutation 确认 / 驳回
- snapshot 列表与切换
- handoff 读取
- Todo projection 读取

当前 `/api/tasks/*` 与 SSE 可以作为迁移过渡层存在，但最终对前端暴露的语义需要转成 EvoCanvas 语义。

## 11. 事件方向

前端事件流应逐步转为 Canvas 语义事件，而不是旧任务日志语义。

建议事件族：

- `agent.intent.recognized`
- `subagent.run.started`
- `subagent.run.completed`
- `canvas.mutation.proposed`
- `canvas.mutation.applied`
- `canvas.confirmation.requested`
- `canvas.snapshot.created`
- `handoff.refreshed`

这些事件会支撑前端真正摆脱硬编码 demo 行为。

## 12. 已确认后端模块拆分与文件归属

这一节用于把抽象架构进一步落到代码组织层面。

总体原则：

- `app/core` 继续承载通用运行时与基础契约
- EvoCanvas 1.0 的产品语义单独收敛到 `app/canvas/`
- 不再把新的 Canvas 语义继续硬塞进旧的 `task / artifact / playbook / spec` 语义里

### 12.1 建议保留为通用底座的现有模块

以下模块建议继续作为通用底座保留，最多做轻量适配，不作为主要重构目标：

- `app/core/events.py`
- `app/core/task.py`
- `app/core/session.py`
- `app/core/subagent.py`
- `app/services/subagent_service.py`
- `app/services/agent_runtime/runtime.py`
- `app/workflows/engine.py`
- `app/services/fakes.py`

各自定位如下：

- `app/core/events.py`
  继续承载事件模型与事件总线
- `app/core/task.py`
  继续承载任务状态机与 workflow step 契约
- `app/core/session.py`
  继续承载受控 `AgentSession`
- `app/core/subagent.py`
  继续承载 subagent 契约与预算 / fanout / scope 定义
- `app/services/subagent_service.py`
  继续作为内部多角色执行原语
- `app/services/agent_runtime/runtime.py`
  继续提供受 schema 约束的 agent 输出运行时
- `app/workflows/engine.py`
  继续作为 workflow 执行引擎
- `app/services/fakes.py`
  短期继续作为基于本地文件的存储底座，后续扩展存储内容即可

### 12.2 建议新增 EvoCanvas 产品命名空间

建议在 `app/canvas/` 下建立新的 EvoCanvas 原生模块边界。

#### 领域模型层

- `app/canvas/domain/workspace.py`
  放 `CanvasWorkspace`
- `app/canvas/domain/cards.py`
  放 `CanvasCard`、卡片类型与 stage / module 枚举
- `app/canvas/domain/relations.py`
  放 `CanvasRelation`
- `app/canvas/domain/snapshots.py`
  放 `CanvasSnapshot` 与 `TodoProjection`
- `app/canvas/domain/handoff.py`
  放 `StructuredHandoff`
- `app/canvas/domain/mutations.py`
  放 `CanvasMutation`、`MutationProposal`、风险等级与确认状态契约

#### 应用服务层

- `app/canvas/repository.py`
  负责 workspace / snapshot / proposal / handoff 的持久化读写
- `app/canvas/service.py`
  负责画布读取、mutation 应用、Todo projection 刷新、snapshot 读取等应用服务
- `app/canvas/governance.py`
  负责“自动写入 / 待确认 / 先追问”的风险判定

#### Agent 编排层

- `app/canvas/agent/contracts.py`
  定义内部角色输入输出 schema
- `app/canvas/agent/supervisor.py`
  实现统一的 `Canvas Supervisor`
- `app/canvas/agent/roles.py`
  首版集中放 5 个内部角色的注册、prompt 配置与调用映射

### 12.3 与现有 Workflow 的衔接

建议不要直接复用 `spec_to_agent` 语义，而是在 workflow 层给 EvoCanvas 单独建注册入口。

建议新增：

- `app/workflows/canvas_session.py`
  定义 EvoCanvas 单轮 agent 执行任务或 workspace turn 的 workflow definition

建议修改：

- `app/workflows/definitions.py`
  注册新的 EvoCanvas task / workflow definition

### 12.4 与现有 API 的衔接

API 层建议逐步解耦，不再把新的 Canvas 请求继续堆进旧 DTO。

建议新增：

- `app/api/canvas_schemas.py`
  存放新的 Canvas API 请求与响应模型

建议演进：

- `app/api/server.py`
  短期继续作为总入口，但逐步退化为路由装配与服务转发层，不继续承载全部 Canvas 业务实现

### 12.5 这一拆分方案的主要收益

采用上述拆分后，会得到以下收益：

- 通用运行时与 EvoCanvas 产品语义边界清晰
- 新增和修改 Canvas 能力时，改动主要集中在 `app/canvas/` 下，降低扩散风险
- 可以保留旧 Evoloop 能力作为参考或兼容层，但不再污染 EvoCanvas 1.0 主路径
- 后续继续落 API、snapshot、handoff、Todo 等能力时，结构已经预留好位置，不需要反复搬家

## 13. 已确认 API 契约与 SSE 契约方向

这一节用于明确前端如何从 demo 数据迁移到真实 Canvas 后端，以及 agent 驱动画布时前后端如何配合。

总体原则：

- 对前端尽快暴露 EvoCanvas 原生接口
- 对后端内部允许短期复用现有 `TaskService / EventBus / WorkflowEngine` 作为过渡支架
- 前端围绕“状态流 + SSE 事件流”工作，而不是等待一次大而全的同步响应

### 13.1 首版 API 分组

首版建议收敛为 6 组接口，覆盖真实 Canvas 闭环，但不额外膨胀。

#### 1. workspace 基础信息

- `GET /api/canvas/workspaces/{workspace_id}`

建议返回：

- 标题
- 当前目标
- 当前 active snapshot
- handoff 状态
- 最近 agent 状态摘要

#### 2. Canvas 当前视图

- `GET /api/canvas/workspaces/{workspace_id}/canvas`

建议支持可选参数：

- `snapshot_id`

建议返回：

- cards
- relations
- todo_projection
- pending_confirmations_count
- view_meta

#### 3. 用户消息 / agent turn 提交

- `POST /api/canvas/workspaces/{workspace_id}/messages`

建议输入：

- `message`
- `selected_card_ids`
- `material_ids`
- `mode`

建议同步返回：

- `turn_id`
- `accepted: true`
- 让前端继续通过 workspace SSE 观察这一轮执行过程

这一接口不建议阻塞等待 agent 全流程完成。

#### 4. 待确认 mutation

- `GET /api/canvas/workspaces/{workspace_id}/confirmations`
- `POST /api/canvas/workspaces/{workspace_id}/confirmations/{proposal_id}/approve`
- `POST /api/canvas/workspaces/{workspace_id}/confirmations/{proposal_id}/reject`

这一组接口专门承载“高影响动作必须确认”的产品规则。

#### 5. snapshots

- `GET /api/canvas/workspaces/{workspace_id}/snapshots`
- `POST /api/canvas/workspaces/{workspace_id}/snapshots`

用途：

- 读取历史快照
- 切换快照视图
- 支持手动生成快照

自动快照依然可以由系统内部触发，但读取和切换建议通过独立接口完成。

#### 6. handoff

- `GET /api/canvas/workspaces/{workspace_id}/handoff`
- `POST /api/canvas/workspaces/{workspace_id}/handoff/refresh`

结论：

- handoff 作为 1.0 核心交付物，建议拥有独立接口
- 不建议只在 Canvas payload 中夹带一段 handoff 摘要

### 13.2 Todo 不单独做写接口

首版建议：

- `TodoProjection` 只读
- 不提供 Todo 独立写接口

原因：

- PRD 已明确 Todo 不是事实源
- Todo 只是从 `clarification / decision / draft constraint` 投影出来的当前缺口视图
- 如果给 Todo 提供独立写接口，产品语义容易重新滑回“任务系统”

因此建议：

- `GET /canvas` 中直接返回 `todo_projection`
- 如前端需要独立读取，可增加 `GET /api/canvas/workspaces/{workspace_id}/todos`
- 不提供 `POST /todos` 或 `PATCH /todos`

### 13.3 SSE 订阅粒度

建议前端按 `workspace` 订阅事件，而不是继续暴露旧 `task` 语义。

建议接口：

- `GET /api/canvas/workspaces/{workspace_id}/events`

### 13.4 首版 SSE 事件族

建议前端至少接收以下事件：

- `agent.intent.recognized`
- `subagent.run.started`
- `subagent.run.completed`
- `canvas.mutation.proposed`
- `canvas.mutation.applied`
- `canvas.confirmation.requested`
- `canvas.snapshot.created`
- `handoff.refreshed`

这些事件分别承载：

- 当前轮次被识别成什么 EvoCanvas 意图
- 内部角色何时开始、何时完成
- 本轮产生了哪些 mutation proposal
- 哪些低风险变更已自动落盘
- 哪些高影响变更进入待确认队列
- 是否生成了新的 snapshot
- handoff 是否被刷新

### 13.5 一次消息提交后的标准时序

建议前后端交互时序固定为：

1. 前端调用 `POST /messages`
2. 后端立即返回 `turn_id`
3. 前端持续监听 workspace SSE
4. SSE 顺序推送：
   - `agent.intent.recognized`
   - `subagent.run.started`
   - `subagent.run.completed`
   - `canvas.mutation.proposed`
   - `canvas.mutation.applied` 或 `canvas.confirmation.requested`
5. 如果收到 `canvas.mutation.applied`
   - 前端自动重新拉取一次 `GET /canvas`
6. 如果收到 `canvas.confirmation.requested`
   - 前端拉取 `GET /confirmations`
   - 渲染确认面板
7. 用户完成确认或驳回后
   - 调用 `approve / reject`
   - 再通过 SSE 或后续读取刷新最终状态

结论：

- 前端不再等待大同步响应
- 前端围绕“事件流 + 状态重拉”工作

### 13.6 与现有 `/api/tasks/*` 的迁移关系

建议迁移策略为：

- 对前端：尽快切到 `/api/canvas/workspaces/*`
- 对后端内部：短期允许 `workspace_id` 继续映射到现有 task/context/storage 结构
- 底层 SSE 继续复用 `EventBus`
- 但前端收到的事件名和事件语义逐步切换成 Canvas 原生语义

可以概括为：

- 外部新语义
- 内部渐进迁移

### 13.7 首版 API 的优先级建议

如果需要压缩范围，建议首版优先保证以下 4 组能力先稳定：

- `GET /workspace`
- `GET /canvas`
- `POST /messages`
- `GET/POST /confirmations`

与此同时：

- `snapshots` 和 `handoff` 最好尽早预留接口形态
- 即便第一阶段功能较轻，也不要把这两部分完全埋进其他 payload 中

## 14. 当前仍待补充的章节

以下设计部分尚未细化，后续应随着评审确认逐段补齐：

- `CanvasCard`、`CanvasMutation`、`MutationProposal`、snapshot 的精确 schema
- 测试策略
- 逐步实施计划

## 15. 已确认持久化模型与存储格式方向

这一节用于明确 EvoCanvas 真实工作台状态、mutation proposal、confirmation queue 和 snapshot 如何落盘。

总体原则：

- 首版继续复用当前基于文件系统的 `FakeStorage` 思路
- 但 EvoCanvas 数据不再继续混入旧 `task.json / context.json` 语义
- 新的 Canvas 数据应独立存放在 workspace 命名空间下

### 15.1 建议目录结构

建议在存储根目录下新增：

- `canvas/workspaces/{workspace_id}/workspace.json`
- `canvas/workspaces/{workspace_id}/cards/{card_id}.json`
- `canvas/workspaces/{workspace_id}/relations/{relation_id}.json`
- `canvas/workspaces/{workspace_id}/snapshots/{snapshot_id}.json`
- `canvas/workspaces/{workspace_id}/proposals/{proposal_id}.json`
- `canvas/workspaces/{workspace_id}/handoff.json`
- `canvas/workspaces/{workspace_id}/confirmation_queue.json`
- `canvas/workspaces/{workspace_id}/events.jsonl`

### 15.2 各存储对象的职责

- `workspace.json`
  只存工作台级元数据，不存全量 cards
- `cards/*`
  每张 card 独立存储，便于审计与局部更新
- `relations/*`
  关系实体独立存储，避免把关系硬编码进 card 内部
- `snapshots/*`
  首版存物化视图，而不是只存事件引用
- `proposals/*`
  每份 mutation proposal 独立落盘，支撑确认流与审计
- `handoff.json`
  存当前 handoff 主体，不依赖运行时临时拼接
- `confirmation_queue.json`
  存当前待确认 proposal 列表与顺序
- `events.jsonl`
  存 Canvas 原生事件流

### 15.3 Snapshot 的存储策略

已确认建议：

- snapshot 首版存“物化视图”
- 不采用首版仅靠事件重放来恢复旧视图

原因：

- 物化视图更稳，恢复成本更低
- 更适合首版做快照切换与回放
- 避免一开始就在事件重建链路上投入过多复杂度

## 16. 已确认 Workspace 与 Task 的关系

这一节用于明确 EvoCanvas 工作台对象和现有 workflow task 的边界。

已确认建议：

- `workspace` 是长期存在的产品对象
- 每一轮用户消息触发一个短生命周期 `canvas_turn` task
- `canvas_turn` task 绑定 `workspace_id`
- task 跑完后结束，但 workspace 状态持续存在

### 16.1 为什么不把 workspace 直接做成长任务

不建议把整个工作台生命周期塞进一个长期膨胀的 `TaskContext`，原因如下：

- 一个工作台会经历很多轮消息，状态会持续增长
- 旧 task 语义更适合承载一次受控执行，而不是整个产品对象生命周期
- 把 workspace 和 task 分开后，恢复、审计、失败边界会更清楚

### 16.2 推荐执行关系

建议采用如下关系：

- `workspace`：长期产品对象
- `canvas_turn task`：一次用户输入驱动的一轮受控执行
- `proposal`：这轮执行产出的变更提议
- `confirmation`：对 proposal 中高风险变更的后续处理

结论：

- 复用现有 `WorkflowEngine` 会更自然
- workspace 真实状态应持久化在 `app/canvas/`，而不是埋在 task 本体中

## 17. 已确认 Workflow Wiring 方向

这一节用于明确 EvoCanvas 单轮执行在 workflow 层如何落地。

已确认建议：

- 新建专门的 `canvas_turn` workflow
- 不复用 `spec_to_agent` 语义

### 17.1 建议步骤顺序

建议 workflow 顺序如下：

1. `load_workspace_context`
2. `recognize_intent`
3. `run_canvas_supervisor`
4. `dispatch_internal_roles`
5. `merge_mutation_proposal`
6. `classify_mutation_risk`
7. `apply_auto_mutations`
8. `enqueue_confirmations_if_needed`
9. `refresh_todo_and_handoff`
10. `create_snapshot_if_needed`
11. `emit_canvas_events`

### 17.2 已确认执行原则

- 内部角色只产出结构化结果
- 内部角色不允许直接写库
- 所有写入统一经过 `governance + canvas service`
- Todo、handoff、snapshot 的刷新应作为 workflow 尾段的系统性收尾步骤

## 18. 已确认 Confirmation Model 与风险分类方向

这一节用于明确高影响动作的确认流不是临时事件，而是一等持久化模型。

### 18.1 Proposal 状态

建议 proposal 至少支持以下状态：

- `draft`
- `pending_confirmation`
- `applied`
- `rejected`
- `superseded`

### 18.2 风险分类依据

建议风险分类时综合考虑：

- `mutation_type`
- `target_object_type`
- `target_state_delta`
- `conflict_count`
- `source_evidence_count`
- `explicit_user_intent`

### 18.3 已确认判定原则

- 仅新增信息、补充说明、标记冲突，通常归为低风险
- 任何把状态从“不确定”推进为“已确认 / 已生效 / 已关闭 / 已决定”的动作，归为高风险
- 生成关键 snapshot 或覆盖正式 handoff，也归为高风险
- 用户明确表达“就这么定”，可以提高系统置信度，但不直接绕过确认规则

### 18.4 Confirmation Queue 归属

已确认建议：

- confirmation queue 按 workspace 维度维护
- 不按 task 维度维护

原因：

- 用户是在工作台里确认，不是在某个历史 turn 里确认
- 这更符合 Canvas 作为长期产品对象的语义

## 19. 已确认 Snapshot、Handoff 与 Todo 生成策略

这一节用于把 3 个最容易互相污染的对象一次性钉住。

### 19.1 TodoProjection

已确认建议：

- 每次 mutation 应用后都重算 `TodoProjection`
- 不手工维护 Todo 实体状态

### 19.2 Handoff 策略

已确认建议：

- 明确区分 `draft handoff` 和 `formal handoff`

具体规则：

- 每轮 turn 结束后可尝试刷新 `draft handoff`
- `formal handoff` 进入可对外状态前必须经过确认

### 19.3 Snapshot 策略

已确认建议：

- 首版允许 `自动快照 + 手动快照` 并存

建议自动生成 snapshot 的时机：

- 一批 clarification 新增完成
- 关键 constraint 被确认
- 关键 decision 完成
- 新 handoff 形成
- 某轮输入编译导致明显结构变化

建议不要自动生成 snapshot 的时机：

- 仅修改 card 文案
- 仅补充低价值 metadata
- 仅刷新 TodoProjection

## 20. 已确认并发、恢复、测试与上线顺序

这一节用于减少后续实现阶段反复返工。

### 20.1 Workspace 并发策略

已确认默认值：

- 一个 workspace 同时只允许一个活跃 `canvas_turn`
- 当上一轮尚未结束时，首版默认策略为“拒绝并提示稍后继续”

结论：

- 首版不做排队队列
- 先优先保证一致性与实现稳定性

### 20.2 恢复策略

建议要求以下对象可在服务重启后恢复：

- workspace state
- proposals
- confirmation queue
- snapshots
- handoff

前端恢复策略建议为：

- SSE 断开后重新拉 `GET /canvas`
- 再拉 `GET /confirmations`
- 不要求恢复旧 token 流，只要求恢复最终状态

### 20.3 测试分层

建议测试拆成 5 层：

1. 领域模型单测
2. 治理层单测
3. agent 合约单测
4. API 集成测试
5. 端到端测试

分别覆盖：

1. card / relation / mutation / snapshot 基本行为
2. 低风险、高风险、冲突升级判定
3. 内部角色输出 schema 稳定性
4. workspace、canvas、messages、confirmations 等接口
5. 从消息进入到 proposal / auto-apply / confirmation 的完整闭环

### 20.4 建议上线顺序

建议按如下顺序推进实现：

1. 建立 `app/canvas/` 领域模型和 repository
2. 打通 `GET /workspace` 与 `GET /canvas`
3. 接入 `POST /messages`，先支持 proposal 生成与低风险自动写入
4. 接入 confirmation queue
5. 接入 snapshots 与 handoff
6. 前端从 `demoScenario.js` 迁到真实接口
7. 最后清理旧 EvoLoop 页面与旧 API 依赖

## 21. 当前仍待补充的章节

以下设计部分尚未细化，后续应随着评审确认逐段补齐：

- `CanvasCard`、`CanvasMutation`、`MutationProposal`、snapshot 的精确 schema
- 测试中的样例数据与验收用例清单
- 逐步实施计划

## 22. 建议的后续设计顺序

接下来建议按以下顺序继续评审和落文档：

1. 精确 schema 定义
2. 逐步实施计划
3. 从旧 `/api/tasks/*` 到新 `/api/canvas/workspaces/*` 的迁移细则
4. 测试样例与验收用例清单

## 23. 变更记录

### 2026-06-14

- 记录了“真实 Canvas + 可编辑 Canvas + 真实 Agent”这一阶段目标
- 记录了“前台单助手、后台多角色编排”的 agent 方案
- 记录了“复用 Evoloop subagent 作为内部受控执行原语”的方向
- 记录了“低风险自动写入、高影响动作需确认”的默认治理策略
- 记录了当前已确认的总体架构、领域模型、agent 执行流与底座复用策略
- 记录了后端模块拆分与文件归属方案，明确 `app/core` 与 `app/canvas/` 的职责边界
- 记录了首版 API 分组、SSE 订阅方式、消息提交时序与前后端迁移原则
- 记录了持久化模型、workspace 与 task 的关系、canvas_turn workflow、confirmation model、snapshot / handoff / todo 策略，以及并发 / 恢复 / 测试 / 上线顺序

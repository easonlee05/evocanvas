# Runtime Mapping（运行时映射）

## 1. 目标

本文件回答一个非常具体的问题：

- `L / G / V` 三层规则，落到当前后端代码时，分别应该挂在哪些对象、哪些入口、哪些状态字段上。

当前主要承接代码如下：

- 工作区服务：`app/canvas/service.py`
- 治理分类：`app/canvas/governance.py`
- 领域对象：`app/canvas/domain/`
- API 出口：`app/api/server.py`

## 2. 当前代码已经承接了什么

### 2.1 L 层已经有的承接点

当前 `app/canvas/service.py` 已经有一条可复用的轻量主链：

- `start_turn`
  - 启动回合，构建提案，进入自动应用或待确认
- `refresh_handoff`
  - 根据当前卡片收束交接草稿，并生成快照
- `move_card`
  - 在 `discovery / define / handoff` 三段之间做合法迁移
- `approve_confirmation / reject_confirmation`
  - 在高影响动作上由用户显式裁决

这说明系统已经具备：

- 回合概念
- 提案概念
- 确认流概念
- 交接草稿概念

但它还不等于完整的 `L层（生命周期与编排）`，因为当前还缺：

- `阶段节点 + 阶段内检查点` 的显式状态
- 相邻阶段回流记录
- 关键未决账本
- “为什么停在这里”的结构化解释

### 2.2 G 层已经有的承接点

当前 `app/canvas/governance.py` 已经把以下动作视为高风险：

- `confirm_constraint`
- `resolve_clarification`
- `create_decision_request`
- `create_snapshot`
- `promote_formal_handoff`

并且已经支持：

- 高风险提案进入 `pending_confirmation`
- 低风险提案自动应用
- 确认队列持久化

这已经符合 EvoCanvas 1.0 的第一条治理底线：

- 低风险结构整理可自动应用
- 高影响动作必须经过确认

但当前 G 层仍然偏薄，主要缺口有两类：

1. 风险分级过粗
   - 现在基本只有 `low / high`
   - 尚未把“高置信未确认”“待复核”“替代旧事实”等状态正式沉淀到对象层
2. 放行依据过少
   - 现在主要靠 `mutation_type / target / status` 判断
   - 还没有接入来源充分性、冲突披露、验证结果等更稳定的放行依据

### 2.3 V 层目前基本空缺

当前仓库里还没有独立的 `V层（验证）` 运行时实现。

这意味着现在的主流程基本是：

`识别与提案 -> G层分类 -> 自动应用 / 待确认`

而不是理想中的：

`识别与提案 -> V层验证 -> G层放行 -> 自动应用 / 待确认`

因此，首批代码改造时，最值得优先补的是：

- 验证挂载点
- 验证回执对象
- 默认分流建议

## 3. 建议的运行时对象映射

### 3.1 工作区对象（Workspace）

当前 `app/canvas/domain/workspace.py` 已有：

- `active_turn_id`
- `active_turn_status`
- `handoff_status`
- `metadata`
- `handoff_metadata`

建议不要立刻重做对象，而是在 `metadata` 上先补一层可演进的运行时语义：

- `lifecycle.stage_node`
  - 当前处于哪一段主链
  - 建议值先与产品主闭环对齐：`compilation`、`clarification`、`convergence`、`handoff`
- `lifecycle.checkpoint`
  - 当前停留在哪个检查点
- `lifecycle.pending_gate_ids`
  - 当前有哪些未完成门禁
- `lifecycle.unresolved_issue_ids`
  - 当前有哪些关键未决
- `verification.last_receipt_id`
  - 最近一次验证回执

注意：

- 前端现有 `discovery / define / handoff` 只保留为展示带
- 后端真正的 L 层推进状态，不建议继续偷塞在卡片 `stage` 里

### 3.2 卡片对象（Card）

当前 `app/canvas/domain/cards.py` 已有：

- `kind`
- `stage`
- `status`
- `evidence_refs`
- `metadata`

建议继续保留 `stage` 作为画布展示列，不让它承担完整生命周期语义。

首批可补的字段口径：

- `status`
  - 只表达对象局部状态，例如 `draft / open / pending / confirmed / resolved / superseded`
- `metadata.governance_state`
  - 表达治理态，例如 `proposal / confirmed / under_review`
- `metadata.verification_state`
  - 表达验证态，例如 `not_run / passed / warned / failed`
- `metadata.source_summary`
  - 记录当前卡片的最小依据摘要，方便后续验证与交接引用

### 3.3 提案对象（Proposal）

当前 `CanvasMutationProposal` 已经足够成为 `G层 + V层` 的共同挂载点。

首批建议补以下能力：

- `proposal.metadata.verification_receipt`
  - 保存本次提案在结构、来源、策略三类检查上的结果摘要
- `proposal.metadata.gate_reason`
  - 如果进入确认队列，记录是“改变事实边界”“关闭关键未决”还是“发布正式交接”
- `proposal.metadata.rollback_hint`
  - 验证失败后建议回流到哪一段

这样做的好处是：

- 不用先重做 repository
- 先把运行逻辑挂在已有提案对象上
- 后续要抽成独立 `VerificationReceipt` 也有迁移空间

### 3.4 交接物对象（StructuredHandoff）

当前 `app/canvas/domain/handoff.py` 的 `StructuredHandoff` 只有：

- `summary`
- `constraints`
- `open_questions`
- `decisions`
- `metadata`

这还不够承接 harness 里的“正式交接物”边界。

首批建议补的不是大而全 schema，而是最小可追溯字段：

- `metadata.source_snapshot_id`
  - 该交接物基于哪个快照收束
- `metadata.confirmation_state`
  - `draft / pending_confirmation / confirmed`
- `metadata.unresolved_count`
  - 当前仍有多少关键未决
- `metadata.high_confidence_unconfirmed_count`
  - 高置信但未确认条目数量
- `metadata.generated_from_card_ids`
  - 本次交接依赖的核心卡片集合

## 4. 建议的首批运行时流程

首批代码实现建议收成下面这条最小链路：

1. `CanvasSupervisor` 识别意图并生成 mutation proposal
2. 新增 `V层` 预验证
   - 先做结构检查
   - 再做来源检查
   - 再做策略跳步检查
3. 形成验证回执并写回 proposal metadata
4. `MutationGovernance` 结合验证回执判断：
   - 自动应用
   - 待确认
   - 降级为提案
   - 回到待澄清
5. `CanvasService` 再决定：
   - 停留当前阶段
   - 回流相邻阶段
   - 或进入交接刷新

这里有一个重要边界：

- `V` 只负责说“够不够可信”
- `G` 只负责说“能不能放行”
- `L` 只负责说“接下来往哪走”

## 5. 当前明确不建议现在就做的事

- 不要把 `discovery / define / handoff` 直接扩成完整状态机
- 不要为了补 V 层而新造一套独立 workflow 引擎
- 不要让交接物先长成完整 PRD schema
- 不要把所有未确认内容都做成硬门禁，导致主链完全不动

## 6. 首批改造优先级

建议优先级固定为：

1. 在 proposal 上补验证回执与门禁原因
2. 在 workspace metadata 上补生命周期状态与关键未决记录
3. 扩充 handoff metadata 的可追溯字段
4. 再考虑把验证回执抽成独立对象或持久化文件

这样做的原因很直接：

- 这四步都能复用现有 `app/canvas/` 底座
- 这四步都能直接提升后续代码修改的一致性
- 它们不会把 1.0 项目提前拖进“重写平台”的坑里

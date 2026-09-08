# Frontend Contract（历史前端工作台契约快照）

> 状态：`历史迁移快照，非当前实现规格`
> 编码门槛：`不得据此恢复阶段状态机、普通确认队列或前端审批面；当前前端边界以主 PRD、Harness L3 和 Architecture Traceability 为准`

本文保留旧 L / G / V 迁移阶段对前端代码和技术债的观察，用于识别仍需替换的关键词推断、坐标推断和旧确认界面。文中的 `lifecycle.stage_node`、`pending_confirmation_ids`、审批确认项及接口演进建议没有自动继承为当前目标合同；实施前必须重新核对当前代码、主 PRD 和 Harness。

## 1. 历史记录目标

本快照记录当时对 `frontend/src/pages/Workspace/` 在 EvoCanvas 1.0 中职责边界的判断。

一句话：

- 前端工作台是运行时结果的投影层，不是新的事实源。

这句话看起来简单，但它决定了后面很多代码不能随手乱长。

## 2. 快照时前端承接情况

快照时工作台主路径已经存在以下承接点：

- `frontend/src/pages/Workspace/index.jsx`
  - 拉取画布、确认队列、交接物与事件流
- `frontend/src/pages/Workspace/Canvas.jsx`
  - 承接卡片创建、编辑、移动、连线、局部状态切换
- `frontend/src/pages/Workspace/CanvasOverlays.jsx`
  - 用当前卡片投影活跃缺口与轻量时间轴
- `frontend/src/api.js`
  - 提供统一的 API 请求封装

同时，快照时前端也已经体现了两个可保留方向：

- 主画布不是表单系统，而是连续工作面
- 前端已经把 `handoff` 当成从画布收束出来的只读结果，而不是独立编辑文档

## 3. 快照时前端的主要技术债

### 3.1 快照问题：阶段感知还偏 UI 规则

快照时 `Canvas.jsx` 里仍有一些“按画布坐标猜阶段”的逻辑：

- 在不同横向区域点击时，用 `canvasX` 推断 `discovery / define / handoff`
- 新建卡片时，用 section key 映射后端 kind 和 stage

这适合做 1.0 早期原型，但不适合作为正式运行时事实。

当时的后续演进判断是：

- `x 坐标` 只能决定卡片视觉落点
- `阶段推进状态` 应来自后端 `L层（生命周期与编排）`

### 3.2 快照问题：时间轴和活跃缺口仍含有关键词推断

快照时 `CanvasOverlays.jsx` 会根据：

- 卡片 section
- 文本关键词
- 状态标签

推断：

- `待澄清`
- `待决策`
- `待定义`
- 当前阶段进度

这个投影逻辑在过渡阶段可以保留，但后续不能继续承担事实判断。

当时建议的演进方向：

- 前端保留“如何展示”
- 后端逐步提供“这是什么状态”

### 3.3 快照问题：前端仍保留较多旧产品页面

从当时目录看，仓库仍保留：

- `Dashboard`
- `Tasks`
- `KnowledgeBase`
- `RuleAudit`
- `RecycleBin`

这些页面暂时可以作为迁移资产存在，但不应继续扩写产品能力。

首批前端改造应只围绕：

- `LandingPage`
- `Workspace`
- 必要的通用组件

## 4. 快照阶段提出的前端边界

### 4.1 历史边界：画布卡片是映射层，不是事实层

前端收到的卡片可以展示：

- 类型
- 标题
- 摘要
- 状态
- 所在展示带

但前端不应自己决定：

- 哪个对象已经成为正式约束
- 哪个待澄清项已经被真正关闭
- 哪个交接物已经达到了正式发布门槛

这些必须以后端返回结果为准。

### 4.2 历史边界：`discovery / define / handoff` 只作为展示带

快照时曾建议保留前端三段展示带，因为它符合当时的轻量阶段映射。

但需要固定一个边界：

- `discovery / define / handoff` 只回答“卡片当前放在哪个视觉栏目里”
- 不回答“系统当前真正推进到哪一个生命周期节点”

快照时曾建议真正的推进状态后续从后端新增字段读取，例如：

- `view_meta.lifecycle.stage_node`
- `view_meta.lifecycle.checkpoint`
- `view_meta.pending_gates`

### 4.3 历史边界：确认流、验证流、交接流分开展示

后续前端不应再把下面三类状态混在一块靠文案暗示：

- 验证未通过
- 等待用户确认
- 交接草稿已刷新但未正式确认

当时建议的最小区分方式：

- 验证问题：展示为“需补依据 / 需回待澄清 / 需降级”
- 治理门禁：展示为“待你确认”
- 交接状态：展示为“草稿 / 待确认 / 已确认”

### 4.4 历史边界：前端动作服从后端合法迁移

前端可以发起：

- 创建卡片
- 编辑卡片
- 拖动卡片
- 刷新交接草稿
- 审批确认项

但不应静默绕过后端规则，例如：

- 直接把普通卡片改成正式约束
- 直接把待澄清项改成已解决
- 直接把 handoff 卡片当作正式交接物发布

## 5. 历史建议：接口演进方向

### 5.1 历史建议：`get_canvas_view`

快照时建议未来在 `get_canvas_view` 返回体里增加一层轻量运行时信息：

- `view_meta.lifecycle`
- `view_meta.verification_summary`
- `view_meta.pending_confirmation_ids`
- `view_meta.handoff_state`

这样前端就不必再用关键词猜“系统现在走到哪了”。

### 5.2 历史建议：卡片对象

快照时建议前端逐步消费这些后端字段：

- `status`
- `metadata.governance_state`
- `metadata.verification_state`
- `metadata.source_summary`

一旦这些字段稳定，前端对关键词推断的依赖应逐步移除。

### 5.3 历史建议：交接物对象

快照时前端已经默认 handoff 是自动收束结果，当时建议继续保持这一方向。

快照时建议未来 handoff 面板直接消费：

- `confirmation_state`
- `unresolved_count`
- `high_confidence_unconfirmed_count`
- `source_snapshot_id`

而不是只显示一段摘要正文。

## 6. 历史首批前端改造建议

快照时建议按下面顺序改，而不是同时大改 UI：

1. 先把确认态、验证态、交接态三类视觉状态拆开
2. 再让时间轴和活跃缺口优先吃后端状态字段
3. 最后再回头清理基于关键词的旧推断逻辑

这样做的好处是：

- 不会一次性推翻现有工作台
- 能和后端 `L / G / V` 逐步对齐
- 不会把前端重新带回旧 `任务大厅 / 审核系统` 的产品形态

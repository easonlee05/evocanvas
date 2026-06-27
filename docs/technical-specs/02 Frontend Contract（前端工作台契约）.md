# Frontend Contract（前端工作台契约）

## 1. 目标

本文件定义 `frontend/src/pages/Workspace/` 在 EvoCanvas 1.0 中的职责边界。

一句话：

- 前端工作台是运行时结果的投影层，不是新的事实源。

这句话看起来简单，但它决定了后面很多代码不能随手乱长。

## 2. 当前前端已经在做什么

当前工作台主路径已经存在以下承接点：

- `frontend/src/pages/Workspace/index.jsx`
  - 拉取画布、确认队列、交接物与事件流
- `frontend/src/pages/Workspace/Canvas.jsx`
  - 承接卡片创建、编辑、移动、连线、局部状态切换
- `frontend/src/pages/Workspace/CanvasOverlays.jsx`
  - 用当前卡片投影活跃缺口与轻量时间轴
- `frontend/src/api.js`
  - 提供统一的 API 请求封装

同时，当前前端也已经体现了两个对的方向：

- 主画布不是表单系统，而是连续工作面
- 前端已经把 `handoff` 当成从画布收束出来的只读结果，而不是独立编辑文档

## 3. 当前前端的主要技术债

### 3.1 阶段感知还偏 UI 规则

当前 `Canvas.jsx` 里仍有一些“按画布坐标猜阶段”的逻辑：

- 在不同横向区域点击时，用 `canvasX` 推断 `discovery / define / handoff`
- 新建卡片时，用 section key 映射后端 kind 和 stage

这适合做 1.0 早期原型，但不适合作为正式运行时事实。

后续应明确：

- `x 坐标` 只能决定卡片视觉落点
- `阶段推进状态` 应来自后端 `L层（生命周期与编排）`

### 3.2 时间轴和活跃缺口仍含有关键词推断

当前 `CanvasOverlays.jsx` 会根据：

- 卡片 section
- 文本关键词
- 状态标签

推断：

- `待澄清`
- `待决策`
- `待定义`
- 当前阶段进度

这个投影逻辑在过渡阶段可以保留，但后续不能继续承担事实判断。

建议演进方向：

- 前端保留“如何展示”
- 后端逐步提供“这是什么状态”

### 3.3 前端仍保留较多旧产品页面

从目录上看，当前仓库仍保留：

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

## 4. 前端必须遵守的契约

### 4.1 画布卡片是映射层，不是事实层

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

### 4.2 `discovery / define / handoff` 仍然保留，但只作为展示带

当前前端的三段展示带可以继续存在，因为它符合 1.0 的轻量阶段映射。

但需要固定一个边界：

- `discovery / define / handoff` 只回答“卡片当前放在哪个视觉栏目里”
- 不回答“系统当前真正推进到哪一个生命周期节点”

真正的推进状态，后续应从后端新增字段读取，例如：

- `view_meta.lifecycle.stage_node`
- `view_meta.lifecycle.checkpoint`
- `view_meta.pending_gates`

### 4.3 确认流、验证流、交接流必须分开展示

后续前端不应再把下面三类状态混在一块靠文案暗示：

- 验证未通过
- 等待用户确认
- 交接草稿已刷新但未正式确认

建议的最小区分方式：

- 验证问题：展示为“需补依据 / 需回待澄清 / 需降级”
- 治理门禁：展示为“待你确认”
- 交接状态：展示为“草稿 / 待确认 / 已确认”

### 4.4 前端动作必须服从后端合法迁移

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

## 5. 建议的接口演进方向

### 5.1 `get_canvas_view`

建议后续在 `get_canvas_view` 返回体里增加一层轻量运行时信息：

- `view_meta.lifecycle`
- `view_meta.verification_summary`
- `view_meta.pending_confirmation_ids`
- `view_meta.handoff_state`

这样前端就不必再用关键词猜“系统现在走到哪了”。

### 5.2 卡片对象

前端拿到卡片时，建议逐步消费这些后端字段：

- `status`
- `metadata.governance_state`
- `metadata.verification_state`
- `metadata.source_summary`

一旦这些字段稳定，前端对关键词推断的依赖应逐步移除。

### 5.3 交接物对象

当前前端已经默认 handoff 是自动收束结果，这个方向要继续保持。

后续建议 handoff 面板直接消费：

- `confirmation_state`
- `unresolved_count`
- `high_confidence_unconfirmed_count`
- `source_snapshot_id`

而不是只显示一段摘要正文。

## 6. 首批前端改造建议

建议按下面顺序改，而不是同时大改 UI：

1. 先把确认态、验证态、交接态三类视觉状态拆开
2. 再让时间轴和活跃缺口优先吃后端状态字段
3. 最后再回头清理基于关键词的旧推断逻辑

这样做的好处是：

- 不会一次性推翻现有工作台
- 能和后端 `L / G / V` 逐步对齐
- 不会把前端重新带回旧 `任务大厅 / 审核系统` 的产品形态

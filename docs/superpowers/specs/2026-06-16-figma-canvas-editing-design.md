# EvoCanvas Figma 式自由画布编辑与连线交互设计规约 (Spec)

## 1. 背景与产品目标

在 EvoCanvas 1.0 的认知收敛闭环中，画布本质是 Agent 驱动的，但人类的“调整和补充”同样重要。目前画布的编辑能力局限在卡片标题和摘要的原地编辑。为了提供更直观的人机协同体感，本 Spec 规定了将 EvoCanvas 改造为 Figma 式自由编辑画布的设计方案。

目标是让用户可以：
1. 自由在画布上点击添加新卡片和普通文本注释。
2. 通过底部的悬浮工具栏（指针、卡片、连接线、文本）切换操作模式。
3. 图形化地从一个卡片拖出连接线到另一个卡片，从而建立关联。
4. 自由点击高亮或双击连线进行删除，并能在卡片详情中删除连线。
5. 将时间轴做成一个默认收起、可以自由拖拽的画布组件，避免与底部工具栏重叠。
6. 支持卡片的删除与类型转换。

---

## 2. 交互与前端设计

### 2.1 底部悬浮工具栏 (Floating Toolbar)

在 `canvas-container` 底部中央，设计一个居中的悬浮控制条（Sleek Glassmorphism 磨砂玻璃风格）：
* **UI 展现**：
  * 高度 `48px`，背景为 `rgba(255, 255, 255, 0.85)`，具有 `backdrop-filter: blur(20px)`，轻微的 `border: 1px solid rgba(0,0,0,0.08)` 和柔和投影。
  * 包含以下按钮（使用 `lucide-react`）：
    1. **选择指针 (Select)** ➔ `MousePointer` 图标。用于常规选中、双击编辑、卡片与画布拖拽平移。
    2. **新建卡片 (Card)** ➔ `Square` 图标。用于点击画布空白处在对应绝对位置生成新卡片。
    3. **连接线工具 (Connector)** ➔ `MoveUpRight` 图标。用于在卡片之间拖曳拉出连接线。
    4. **文本工具 (Text)** ➔ `Type` 图标。用于在画布空白处写入普通的全局注释文本。
    5. **一键整理 (Auto Layout)** ➔ `Sparkles` 图标（点按后一键重置 `cardOffsets` 并切回选择模式）。
* **交互状态提示**：非 `select` 模式下，工具栏上方出现微缩提示字（例如：“*连接线模式：拖动卡片边缘锚点至另一卡片以建连*”）。

### 2.2 鼠标指针状态机 (Pointer State Machine)

前端引入核心状态 `activeTool: 'select' | 'card' | 'connector' | 'text'`，驱动以下光标与事件劫持：
* `select` ➔ 鼠标样式为 `grab`/`grabbing`（画布）或 `default`/`pointer`（卡片）。
* `card` ➔ 鼠标样式为 `crosshair`。画布点击事件被拦截。
* `connector` ➔ 鼠标样式为 `crosshair`。卡片在 hover 时会激活显示连接锚点。
* `text` ➔ 鼠标样式为 `text`。画布点击事件被拦截。

### 2.3 自由添加卡片机制 (Add Card)

当 `activeTool === 'card'` 时，用户点击画布空白处：
1. **坐标换算**：捕获屏幕坐标 `(clientX, clientY)`，根据画布当前的缩放平移参数 `transform`（`x`, `y`, `scale`）和画布容器的边界 `containerRect` 计算卡片在画布上的全局坐标：
   $$canvasX = \frac{clientX - containerRect.left - transform.x}{transform.scale}$$
   $$canvasY = \frac{clientY - containerRect.top - transform.y}{transform.scale}$$
2. **表单气泡**：在点击位置弹出一个轻量悬浮气泡，允许输入：
   * 标题 (Title)
   * 摘要 (Summary)
   * 类型 (Kind)：单选标签（证据/问题/待澄清/约束/决策/交接物）。
3. **数据提交与固化**：点击确认后，向后端发起创建卡片请求，成功后将该卡片的 `cardOffsets` 设置为 `{ x: canvasX - 160, y: canvasY - 80 }`，使其中心刚好落在点击位置。自动将工具切换回 `select`。

### 2.4 图形化连线工具与删除 (Connector & Relation Editing)

当 `activeTool === 'connector'` 时：
1. **连接锚点 (Connector Dots)**：鼠标悬浮在卡片上时，在其上、下、左、右边缘中心渲染 4 个小圆点锚点。
2. **拖动拉线**：按住任一锚点拖动时，记录临时状态 `tempLine`，并在 SVG 层实时渲染一根从锚点指向鼠标位置的虚线贝塞尔曲线。
3. **松手释放**：若在另一张不同的卡片上松手，弹出关系选择悬浮框（来源于、澄清了、支持、阻塞、冲突于、产出为）。用户选择后，调用后端 API 同步建立关联，前端触发 `onRefresh()`。
4. **连线删除**：
   * SVG 的 `CustomArrow` 在外面覆盖一层 `strokeWidth={12}`、`opacity={0}` 的透明路径用于感应点击。
   * 点击连线会将状态 `selectedArrowKey` 设为 `sourceId->targetId`，使其高亮。
   * 高亮状态下，在线段的中点渲染一个红色的 `×` 按钮；用户点击 `×` 或在选中状态下按键盘 `Delete` / `Backspace` 键，即向后端发起删除请求。

### 2.5 时间轴 (Timeline) 优化方案

为了防止遮挡底部的悬浮工具栏：
* 默认 `isPinned` 为 `false`（不再固定在底部中央）。
* 默认状态下为 **收起 (Collapsed)**，表现为一个左下角的“项目里程碑时间轴”极简卡片按钮。
* 它可以作为一个画布组件被自由拖动，位置保存在 `timelinePos` 里。
* 点击它可以在原地平滑展开为 `600px` 宽的里程碑进度条，方便用户对照，再次点击可重新收起。

### 2.6 纯文本标签工具 (Text Tool)

当 `activeTool === 'text'` 时，在画布空白处点击并输入，可在画布上放置任意非卡片形态的说明文本，文本块支持自由拖动与双击修改。

---

## 3. 后端接口设计 (FastAPI)

我们需要在后端 `app/canvas/service.py` 和 `app/api/server.py` 里新增这 3 个基础 API 以支撑人类的编辑修改。

### 3.1 创建卡片 API
* **路由**：`POST /api/canvas/workspaces/{workspace_id}/cards`
* **请求体** (JSON)：
  ```json
  {
    "kind": "clarification",
    "title": "待澄清的问题标题",
    "summary": "详细的内容摘要",
    "stage": "discovery"
  }
  ```
* **实现逻辑**：实例化 `CanvasCard` 并生成 `card_id`（前缀为 `card_`），将其 append 入 workspace 的卡片列表并保存。发布 `canvas.card.created` 事件。

### 3.2 删除卡片 API (级联删除关系)
* **路由**：`DELETE /api/canvas/workspaces/{workspace_id}/cards/{card_id}`
* **实现逻辑**：
  1. 在卡片列表中移除指定 `card_id` 的卡片并保存。
  2. **级联删除**：在关系列表（relations）中，过滤并移除所有 `from_card_id == card_id` 或 `to_card_id == card_id` 的连线关系，以防画布上出现死悬箭头。
  3. 发布 `canvas.card.deleted` 事件。

### 3.3 删除连线关系 API
* **路由**：`DELETE /api/canvas/workspaces/{workspace_id}/relations`
* **查询参数**：
  * `from_card_id`: 起点卡片 ID
  * `to_card_id`: 终点卡片 ID
* **实现逻辑**：在 relations 中搜寻对应的关系，若存在则将其移除并保存。发布 `canvas.relation.deleted` 事件。

---

## 4. 验证计划

1. **自动单元测试**：
   * 在 `tests/` 下编写针对新后端服务方法的测试，覆盖：创建卡片、删除卡片、创建关系连线、删除关系连线。
2. **手动功能测试**：
   * 启动本地开发服务，在 Workspace 页面切换各种 Pointer Tool（Select, Card, Connector, Text）。
   * 测试在画布任意空白位置点击，卡片是否成功落位且不发生重叠。
   * 测试激活连接线工具后，能否在卡片边缘拉出虚线，松开并建立正确的语义关系。
   * 测试点击高亮某一条线段，并双击或点击 `×` 删除它，验证线段是否实时消失。
   * 测试切换里程碑或拖拽时间轴组件，验证其折叠与平移定位正常，且不与底部工具栏重叠。

# EvoCanvas 1.0 最近项目/历史记录页面设计规约 (Figma 风格)

本规约定义了 EvoCanvas 1.0 历史记录页面的前端设计、交互表现以及与后端 API 的数据联调设计。

---

## 1. 需求背景与产品定位
目前项目缺少历史记录（最近项目）的前端入口，用户在侧边栏无法跳转查看过往创建的画布。
本设计将为 EvoCanvas 补充一个高还原度、精致的 Figma 风格项目浏览器，作为单机版的个人工作区入口。

**核心约束：**
- **单机版本**：目前无团队、无组织概念，UI 控件及逻辑围绕个人本地画布进行简化，移除多用户协作概念。
- **EvoCanvas 1.0 闭环**：展示画布的状态标签（如：待收敛、交接草稿、已确认交接），支持快速恢复与管理工作画布。

---

## 2. 页面路由与入口集成
1. **侧边栏集成**：
   - 修改 [Sidebar.jsx](file:///Users/apple/Desktop/evocanvas/frontend/src/components/layout/Sidebar.jsx)，将 `Clock`（Recent History）按钮更改为 `NavLink` 指向 `/recent`。
2. **路由配置**：
   - 在 [App.jsx](file:///Users/apple/Desktop/evocanvas/frontend/src/App.jsx) 中，引入并注册 `/recent` 路由，使用 `MainLayout` 进行全局包裹。

---

## 3. UI 界面设计与交互规范 (Figma 风格)

页面主体划分为两个核心部分：**工具栏** 与 **项目展示区**。

### 3.1 顶部工具栏
- **左侧页签 (Tabs)**：
  - `最近浏览过` (默认激活)
  - `我的画布` (展示所有个人创建的画布，代替 Figma 的“共享的项目”)
- **右侧过滤与视图控制**：
  - **搜索框 (Search)**：位于工具栏右侧，支持输入关键字实时模糊搜索项目标题。
  - **排序下拉菜单 (Sort)**：支持“最近浏览” (按 `updated_at` 降序) 和“字母顺序” (按 `title` 升序) 切换。
  - **视图切换按钮**：网格视图 (Grid View，默认) 和列表视图 (List View) 切换，保存状态至本地 `localStorage`。

### 3.2 项目展示区 — 网格视图 (Grid View)
- **卡片宽高比**：宽屏自适应，4 列或 3 列响应式布局 (`grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))`)。
- **卡片结构**：
  - **预览区 (Thumbnail)**：上方 70% 高度。对于无实际截图的画布，渲染一层 Figma 风格的极细像素网格，中心展示代表 EvoCanvas 的优雅发光渐变几何圆角矩形，或磨砂玻璃质感的占位图形。
  - **状态徽章 (Status Badge)**：卡片左上角浮动展示。根据 `handoff_status` 渲染：
    - `confirmed` -> `[已确认交接]` (绿色精致边框或半透明绿底)
    - `draft` -> `[交接草稿]` (橙色)
    - `not_ready` -> `[待收敛]` (灰色)
  - **信息栏 (Info)**：下方 30% 高度。
    - 左下角带有精致的文件类型图标（使用 `lucide-react` 的 `Layout` 图标，黑色背景，带有 EvoCanvas 标识）。
    - 标题文本显示项目名称（可点击，点击跳转至对应工作区 `/workspace/:id`）。
    - 相对编辑时间（如“编辑于 3 天前”，采用 [recentProjectsView.js](file:///Users/apple/Desktop/evocanvas/frontend/src/pages/RecentProjects/recentProjectsView.js) 提供的 `formatRelativeUpdateLabel` 自动计算）。
- **悬浮态微交互 (Hover States)**：
  - 卡片轻微上浮 `transform: translateY(-4px)`，过渡效果 `transition: all var(--t-fast) var(--ease)`。
  - 阴影加深，给用户一种物理按压上浮的 premium 质感。
  - 右上角平滑渐显：星标 (收藏，支持前端模拟点亮) 和更多操作 `...` 菜单。
  - 更多操作菜单内提供：**重命名** (前端弹窗) 和 **删除** (支持从界面移除，并可调用后续扩展接口)。

### 3.3 项目展示区 — 列表视图 (List View)
- 表格行布局：图标 + 画布标题 + 相对编辑时间 + 状态徽章 + 操作按钮。
- 行悬浮高亮变色。

### 3.4 骨架屏加载与空状态
- **骨架屏 (Skeleton Loader)**：加载时渲染 6 张占位灰色块网格，具备 Figma 的柔和呼吸灯渐变动画。
- **空状态 (Empty State)**：当没有画布时，在屏幕中央展示一个极简 SVG 插画，并提供一个“快速开启需求收敛”的引导按钮，点击跳转到 `/` 首页。

---

## 4. 后端 API 数据联调
- **请求接口**：`GET /api/canvas/workspaces`
- **返回数据处理**：
  - 调用后端的 `canvas_service.list_recent_workspaces()`。
  - 前端使用 `recentProjectsView.js` 的 `buildRecentProjectCard(item)` 对数据进行扁平化与字段标准化映射。
- **数据结构映射**：
  ```json
  {
    "workspaceId": "ws_...",
    "title": "未命名项目",
    "summary": "画布摘要预览...",
    "updatedLabel": "编辑于 3 天前",
    "statusLabel": "已确认交接",
    "coverMode": "placeholder"
  }
  ```

---

## 5. 验证标准与测试计划
1. **视觉一致性**：与用户提供的 Figma 网格平铺截图高度贴合（微网格背景、卡片高宽比、阴影、徽章）。
2. **单机逻辑完整性**：删除团队/组织概念，保留纯粹的个人项目管理，能正常加载后端 workspaces。
3. **路由及进入路径**：侧边栏 Clock 按钮高亮与激活跳转完全正常，回退无 BUG。

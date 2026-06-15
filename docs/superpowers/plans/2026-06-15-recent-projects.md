# EvoCanvas 1.0 最近项目/历史记录页面 (Figma 风格) 执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全项目的历史记录前端页面，加载后端工作区，支持 Figma 风格的网格/列表视图、搜索与分类筛选，无团队协作概念，纯单机版本。

**Architecture:** 前端通过新增 `/recent` 路由加载 `RecentProjects` 组件，对接后端现有的 `/api/canvas/workspaces` 接口，并应用 `recentProjectsView.js` 的格式化逻辑。样式采用纯 Vanilla CSS，完美契合 Figma 首页美学。

**Tech Stack:** React 19, Lucide React, CSS Variables, LocalStorage

---

### Task 1: 创建与路由集成

**Files:**
- Create: [RecentProjects.jsx](file:///Users/apple/Desktop/evocanvas/frontend/src/pages/RecentProjects/RecentProjects.jsx)
- Modify: [App.jsx](file:///Users/apple/Desktop/evocanvas/frontend/src/App.jsx)
- Modify: [Sidebar.jsx](file:///Users/apple/Desktop/evocanvas/frontend/src/components/layout/Sidebar.jsx)

- [ ] **Step 1: 修改 App.jsx，引入并配置路由**
  - 导入 [RecentProjects.jsx](file:///Users/apple/Desktop/evocanvas/frontend/src/pages/RecentProjects/RecentProjects.jsx)
  - 注册路径为 `/recent`，由 `W` 组件包裹，传递 `title="Recent Projects"`
  - 代码改动示例：
    ```jsx
    import RecentProjects from './pages/RecentProjects/RecentProjects';
    // ... 在 Routes 内增加：
    <Route path="/recent" element={<W title="Recent Projects"><RecentProjects /></W>} />
    ```

- [ ] **Step 2: 修改 Sidebar.jsx，使 Recent History 指向新路由**
  - 导入 `NavLink` 并把 `<button className="dock-item" title="Recent History">` 替换为：
    ```jsx
    <NavLink to="/recent" className={({ isActive }) => `dock-item${isActive ? ' active' : ''}`} title="Recent History">
      <Clock size={20} strokeWidth={2} />
    </NavLink>
    ```

- [ ] **Step 3: 占位创建 RecentProjects.jsx，确保编译通过**
  - 创建一个基础的页面展示占位符，输出 "Recent Projects"
  - 运行 `npm --prefix frontend run build` 确保基本路由和侧边栏编译正确。

---

### Task 2: 实现 Figma 风格最近项目页面逻辑与 API 对接

**Files:**
- Modify: [RecentProjects.jsx](file:///Users/apple/Desktop/evocanvas/frontend/src/pages/RecentProjects/RecentProjects.jsx)
- Create: [recent-projects.css](file:///Users/apple/Desktop/evocanvas/frontend/src/pages/RecentProjects/recent-projects.css)

- [ ] **Step 1: 编写数据拉取与格式化逻辑**
  - 使用 React `useEffect` 发送 `apiGet('/api/canvas/workspaces', { items: [] })` 请求获取最近工作区。
  - 使用 `buildRecentProjectCard` 映射每个工作区实体，转为前端适配字段。
  - 管理 `searchQuery`（搜索过滤）、`activeTab` (`'recents'` / `'my-canvases'`)、`sortBy` (`'recent'` / `'alphabetical'`) 状态。
  - 管理 `viewMode`（`'grid'` 或 `'list'`），并将其持久化在 `localStorage` 中。

- [ ] **Step 2: 渲染 UI 结构**
  - **顶部工具栏**：
    - 左侧 Tabs：最近浏览过、我的画布。
    - 右侧 controls：搜索输入框（Lucide `Search` 图标）、排序下拉选择器（`SortBy`）、视图切换按钮（Lucide `LayoutGrid` 与 `List` 图标）。
  - **列表容器**：
    - `viewMode === 'grid'`：网格平铺卡片。
    - `viewMode === 'list'`：扁平表格列表。
  - **骨架屏与空状态**：
    - 加载状态：渲染 Figma 骨架阴影格子。
    - 空状态：渲染提示，包含跳转至新建对话的“快速开始”按钮。

- [ ] **Step 3: 引入前端交互（前端模拟）**
  - 星标（Favorites）：前端维持一个 `starredIds`（Set/Array）状态，支持点击点亮/熄灭星标。
  - 项目更多操作 `...` 下拉菜单：重命名（前端 Prompt 输入），删除（从列表过滤滤除）。

---

### Task 3: 编写 CSS 样式，高品质还原 Figma 美学

**Files:**
- Modify: [recent-projects.css](file:///Users/apple/Desktop/evocanvas/frontend/src/pages/RecentProjects/recent-projects.css)

- [ ] **Step 1: 实现工具栏与卡片网格布局**
  - 工具栏：`display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border)`。
  - 项目卡片网格自适应配置，响应式布局：`grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))`。

- [ ] **Step 2: 实现卡片预览图与悬浮效果**
  - 预览区（`recent-card-preview`）：高 140px，利用 CSS 网格线及抽象渐变背景模拟画板。
  - 悬浮态（`:hover`）：平滑上移 `translateY(-4px)`，缩放阴影，右上角显示操作按钮的过渡动画。
  - 骨架屏 shimmer 效果。

---

### Task 4: 验证与清理

**Files:**
- Run commands

- [ ] **Step 1: 运行本地单元测试**
  - 运行 `node frontend/src/pages/RecentProjects/recentProjectsView.test.js` 验证格式化函数。

- [ ] **Step 2: 编译与预览**
  - 运行 `npm --prefix frontend run build` 验证生产打包无错。
  - 交付说明并提示联调步骤。

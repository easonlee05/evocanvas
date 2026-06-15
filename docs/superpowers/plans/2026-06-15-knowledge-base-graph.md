# EvoCanvas 知识库重构与 Obsidian 风格升级计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将知识库页面进行满屏对接，消除四周白边，同时将节点卡片重构为 Obsidian 风格的“小圆点+精细文本”图谱模式，并引入实时力导向物理排斥引擎，实现海量数据下承载自如的纯净拓扑关系图谱。

**Architecture:** 
1. **界面搭边**：修改页面容器为 `width: 100%`, `height: 100%`，顶部工具栏改为无缝贴顶的固定 Header 栏，右侧详情抽屉改为贴右贴底的 100% 高度侧边栏。
2. **Obsidian 节点**：用 SVG `<circle>` 渲染极小圆点，取代庞大臃肿的卡片。标题仅在 Hover 或 Zoom 较大时在圆点右侧展示，彻底解决海量数据放不下的问题。
3. **物理引擎**：在 React 中通过 `requestAnimationFrame` 驱动轻量力导向算法，支持排斥力（Repulsion）、连线拉力（Attraction）及重力（Gravity），拖拽节点时释放会自动回弹并散开。
4. **视觉调整**：线条调细为极淡的 `rgba(0, 0, 0, 0.08)`，选中或悬停时发光亮蓝色。

**Tech Stack:** React 19, SVG, Canvas, CSS Custom Variables.

---

### Task 1: 界面满屏“搭边”及贴底详情侧栏重构

**Files:**
* Modify: [knowledge-base.css](file:///Users/apple/Desktop/evocanvas/frontend/src/pages/KnowledgeBase/knowledge-base.css)

- [ ] **Step 1: 修改布局样式实现全屏无缝对接**
修改样式文件，把工具栏 `.kb-toolbar` 的 absolute 四角留白去除，改为 flex 固定贴顶；把抽屉 `.kb-details-drawer` 改为 100% 贴右高度。
```css
/* 全局页面布局 */
.kb-page {
  width: 100%;
  height: 100%;
  background-color: #f8f9fa;
  background-image: radial-gradient(rgba(0, 0, 0, 0.04) 1px, transparent 1px);
  background-size: 20px 20px;
  overflow: hidden;
  position: relative;
  display: flex;
  flex-direction: column;
}

/* 顶部无缝固定工具栏 */
.kb-toolbar {
  width: 100%;
  height: 52px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  z-index: 10;
  box-sizing: border-box;
}

/* 右侧无缝详情抽屉 */
.kb-details-drawer {
  position: absolute;
  top: 52px; /* 紧贴顶部 Toolbar 下方 */
  right: 0;
  bottom: 0;
  width: 340px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(16px);
  border-left: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  z-index: 9;
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.03);
  animation: slideIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
```

- [ ] **Step 2: 验证样式文件**
运行 `npm --prefix frontend run build` 确保 CSS 语法无错。

---

### Task 2: 引入 Obsidian 极小节点与实时力导布局

**Files:**
* Modify: [index.jsx](file:///Users/apple/Desktop/evocanvas/frontend/src/pages/KnowledgeBase/index.jsx)

- [ ] **Step 1: 写入力导向更新函数及圆形渲染逻辑**
修改 [index.jsx](file:///Users/apple/Desktop/evocanvas/frontend/src/pages/KnowledgeBase/index.jsx)，引入 React 物理模拟 Tick，将原先巨大的卡片节点重构为 SVG `<circle>`，只在 Hover 悬浮或放大时用 `<text>` 渲染名字。
```javascript
  // 物理模拟 Tick
  useEffect(() => {
    if (items.length === 0) return;

    let animFrame;
    const tick = () => {
      setPositions(prev => {
        const next = { ...prev };
        const keys = Object.keys(next);

        // 初始化速度
        keys.forEach(id => {
          if (!velocities.current[id]) {
            velocities.current[id] = { vx: 0, vy: 0 };
          }
        });

        // 1. 节点间的排斥力 (Repulsion)
        for (let i = 0; i < keys.length; i++) {
          for (let j = i + 1; j < keys.length; j++) {
            const id1 = keys[i];
            const id2 = keys[j];
            const p1 = next[id1];
            const p2 = next[id2];
            if (!p1 || !p2) continue;

            const dx = p2.x - p1.x;
            const dy = p2.y - p1.y;
            const distSq = dx * dx + dy * dy || 1;
            const dist = Math.sqrt(distSq);

            if (dist < 160) {
              const force = (160 - dist) / dist * 0.45;
              if (draggingNodeId.current !== id1) {
                velocities.current[id1].vx -= dx * force;
                velocities.current[id1].vy -= dy * force;
              }
              if (draggingNodeId.current !== id2) {
                velocities.current[id2].vx += dx * force;
                velocities.current[id2].vy += dy * force;
              }
            }
          }
        }

        // 2. 连线引力 (Attraction)
        relations.forEach(rel => {
          const p1 = next[rel.source];
          const p2 = next[rel.target];
          if (!p1 || !p2) return;

          const dx = p2.x - p1.x;
          const dy = p2.y - p1.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          
          const force = (dist - 100) / dist * 0.06;
          if (draggingNodeId.current !== rel.source) {
            velocities.current[rel.source].vx += dx * force;
            velocities.current[rel.source].vy += dy * force;
          }
          if (draggingNodeId.current !== rel.target) {
            velocities.current[rel.target].vx -= dx * force;
            velocities.current[rel.target].vy -= dy * force;
          }
        });

        // 3. 向心力 (Center Gravity)
        const centerX = 400;
        const centerY = 250;
        keys.forEach(id => {
          if (draggingNodeId.current === id) return;
          const p = next[id];
          if (!p) return;
          const dx = centerX - p.x;
          const dy = centerY - p.y;
          velocities.current[id].vx += dx * 0.004;
          velocities.current[id].vy += dy * 0.004;
        });

        // 4. 更新坐标并阻尼衰减 (Damping)
        let hasMoved = false;
        keys.forEach(id => {
          if (draggingNodeId.current === id) return;
          const vel = velocities.current[id];
          vel.vx *= 0.80;
          vel.vy *= 0.80;
          
          if (Math.abs(vel.vx) > 0.04 || Math.abs(vel.vy) > 0.04) {
            next[id] = {
              x: next[id].x + vel.vx,
              y: next[id].y + vel.vy
            };
            hasMoved = true;
          }
        });

        return hasMoved ? next : prev;
      });

      animFrame = requestAnimationFrame(tick);
    };

    animFrame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animFrame);
  }, [items, relations]);
```

- [ ] **Step 2: 用 SVG `<circle>` 替换卡片渲染**
在画布渲染循环中，只生成极小彩色圆点（直径 10px）及旁侧小文本，移除原有 `<foreignObject>`。

- [ ] **Step 3: 运行打包验证**
运行 `npm --prefix frontend run build`。

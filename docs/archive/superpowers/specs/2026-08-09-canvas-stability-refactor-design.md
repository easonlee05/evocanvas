# EvoCanvas 画布稳定性重构设计（selective borrowing from Excalidraw）

> 状态：待评审
> 对应分支：`frontend`
> 目标：在不改变产品形态与架构底座的前提下，借鉴 Excalidraw 已验证的交互与数据机制，消除当前画布自研实现里的稳定性短板。

---

## 1 背景与问题

当前画布（`frontend/src/pages/Workspace/`）是自研的 DOM + React 无限画布，视口数学、连线路由、几何缓存、卡片拖拽均已拆分到 `canvasEngine/` 与独立模块，架构方向正确。但存在几处实打实的稳定性隐患，均经源码确认：

1. **连线轮询 DOM**：`CanvasEdges.jsx` 的 `CustomArrow` 在 `geometry` 为空时用 `window.setInterval(update, 50)` 轮询，每条箭头各跑一个 50ms 定时器，每次回调都 `getBoundingClientRect` + `querySelectorAll('.canvas-card')`。N 条线即 N×20fps 的同步布局读取，卡片一多必然抖动。
2. **几何双轨并存**：`Canvas.jsx` 已有 `ResizeObserver + rAF` 的几何缓存（`cardGeometry`），`CanvasEdges.jsx` 内部又维护一套独立的 DOM 兜底（`getElementCanvasRect`/`getCanvasCardObstacles`）。两套实现并行，是稳定性冗余的主要来源。
3. **高频事件未合帧**：滚轮缩放（`Canvas.jsx:2164`）与平移（`handlePointerMove`）每次事件都直接 `setTransform`，无 rAF 合帧，缩放会发生 React 重渲染粘连。
4. **几何 state/ref 双写**：`cardGeometry`(state) 与 `cardGeometryRef`(ref) 同时写入（`Canvas.jsx:2114`），连线吸附读 ref、箭头渲染读 state，存在一致性问题风险。
5. **`Canvas.jsx` 上帝组件**：约 3453 行，29 个 `useState`、10 个 `useRef`、10 个 `useEffect`、1 个 `useLayoutEffect`，视口、拖拽、连线、widget、文本、关系、布局全部混在一个组件里，边界难测。

不会改动：`canvasEngine/viewport.js` 的屏幕↔画布坐标换算与以指针为锚点的缩放数学（已与 Excalidraw 的 `viewportCoordsToSceneCoords` 思路一致），`edgeRouter.js` 的正交路由，卡片优先的 lane 分区架构，产品形态（PRD 是结构化交接物，不是画图工具）。

---

## 2 目标与非目标

### 目标

- 杀掉连线轮询（`setInterval`），改为事件驱动的 rAF 重算，消除每帧同步布局读取。
- 统一几何为单一数据源，删除 `CanvasEdges.jsx` 的 DOM 兜底双轨。
- 为高频事件（wheel / pan）引入 rAF 合帧，`transform` 保持单一真源。
- 引入归一化的 element model（纯数据 + 反向索引 + 版本缓存），让箭头只在所绑卡片几何变化时重算，复杂度从 O(全部箭头×每帧) 降到 O(受影响的箭头)。

### 非目标

- 不嵌入 `@excalidraw/excalidraw` 作为画布宿主（会带进形状工具栏、自由绘制、画布内文本编辑等整套绘图工具 UI，使产品形态漂移，偏离 1.0 最小闭环）。
- 不改为 canvas 命令式渲染（当前 DOM + React 架构与卡片化工作台匹配，重写渲染管线风险远大于收益）。
- 不重写 `edgeRouter.js` 路由算法（在小规模下已可用，且不在本轮稳定性主战场）。
- 不拆分 `Canvas.jsx` 上帝组件（那是后续结构调整，本轮聚焦交互与数据稳定性）。

---

## 3 关键设计决策与一处修正

### 3.1 修正此前的判断：Excalidraw 不是"命令式写 CSS transform 再同步回 state"

调研确认：Excalidraw 全程以 `appState`（scrollX/scrollY/zoom）为单一真相源，高频事件用 `withBatchedUpdates` 合并进 state，渲染由 `throttleRAF` 合帧到每帧一次，再命令式重绘 canvas（`packages/common/src/utils.ts` 的 `throttleRAF`，`packages/excalidraw/scene/staticScene.ts:489` 的 `renderStaticSceneThrottled`）。它不存在"写 CSS 再读回"的来回同步。

因此本轮不采用"命令式写 `.canvas-lanes` 的 CSS transform 再同步回 state"的方案（那会引入 state 与真实 DOM 的背离）。正确做法是：**`transform` 保持单一真源，用 rAF 合帧把高频事件合并为每帧最多一次 `setTransform`**，再交由 React 渲染到 `.canvas-lanes`。这把每帧多次 React 重渲染降为每帧一次，且不引入数据背离。

### 3.2 借鉴 Excalidraw 的三个机制

| 机制 | Excalidraw 实现 | 在本项目落地方式 |
|---|---|---|
| 反向索引 + 事件驱动重算 | 可绑定元素持 `boundElements: [{id,type}]`，元素移动时 `updateBoundElements` 只重算真正相连的箭头（`packages/element/src/binding.ts` 的 `doesNeedUpdate` 短路 + `boundElementsVisitor` 查表） | 卡片归一化模型持 `boundElements` 反向索引，箭头经 `doesNeedUpdate` 过滤后仅对所绑卡片几何变化做 rAF 重算 |
| 归一化比例锚点 | `FixedPointBinding.fixedPoint` 存 `[ratioX, ratioY]`（0~1），元素移动缩放后自动跟随（`binding.ts` 的 `normalizeFixedPoint` + `getGlobalFixedPointForBindableElement`） | 卡片端口与箭头端点以归一化比例存储，坐标变化时按比例重算，避免端点漂移与箭头反转 |
| 几何版本缓存 | `ElementBounds` 用 WeakMap + `version` 字段，`version` 不匹配才重算（`packages/element/src/bounds.ts`） | 卡片几何缓存带 `version`，仅当对应卡片几何变化才重算，避免每帧全量重建 |

### 3.3 范围边界

改造集中在 4 个文件：`CanvasEdges.jsx`（去轮询、删 DOM 兜底）、`Canvas.jsx`（几何单源、事件合帧、element model 接入）、`canvasEngine/geometry.js`（expost 归一化模型 + 反向索引 + 版本缓存）、新增 `canvasEngine/throttle.js`（rAF 合帧工具）。`viewport.js`、`drag.js`、`edgeRouter.js`、`canvasRelations.js`、`canvasLayout.js` 保持不动。

---

## 4 分阶段改造方案

按依赖关系分三阶段，每阶段独立可验证、可回滚。

### 阶段 A：杀掉连线轮询，统一几何单源

现状：`Canvas.jsx` 通过 `useLayoutEffect`（`Canvas.jsx:2114`）用 `ResizeObserver + rAF` 始终维护 `cardGeometry`，并把 `geometry={cardGeometry}` 传给 `CustomArrow`/`TempConnectionLine`。因此 `CanvasEdges.jsx` 的 `hasGeometry ? null : setInterval(...)` 分支仅在 `geometry` 为空时触发。

做法：

1. 保证 `cardGeometry` 始终在首帧 ~before paint 就绪：初始化卡片几何放在 `useLayoutEffect`，且 `CustomArrow`/`TempConnectionLine` 在自身的 `start`/`end` 尚未出现在 `geometry` 时直接返回 `null`（不渲染、不轮询），等下一帧 geometry 就绪后再渲染。
2. 删除 `CanvasEdges.jsx` 的 DOM 兜底：`getElementCanvasRect`、`getCanvasCardObstacles`、`getGeometryCardObstacles` 的 DOM 分支，以及 `hasGeometry` 双分支逻辑。几何只来自 `geometry` prop。
3. 删除 `setInterval(update, 50)`。箭头重算改为 `useEffect` 依赖 `[geometry, transform, ...]`，用 rAF 合帧（见阶段 B 的 `throttleRAF`）触发一次重算，而非定时轮询。

验收：面板内无任何 `setInterval` 连线轮询；缩放/拖卡片时箭头仍正确跟随；卡片数量翻倍时无明显掉帧。

### 阶段 B：高频事件 rAF 合帧

新增 `canvasEngine/throttle.js`，移植 Excalidraw `throttleRAF`（`packages/common/src/utils.ts:155`）："同帧内多次调用只保留最后一次参数 + 只调度一个 rAF 回调"。

接入：

- 滚轮：`handleWheel`（`Canvas.jsx:2156`）内不再直接 `setTransform`，改为把 `deltaY/指针位置` 交给 `throttleRAF` 合帧，每帧最多一次 `zoomViewportAtPoint` + `setTransform`。
- 平移：`handlePointerMove`（`Canvas.jsx:2272`）同样经 `throttleRAF` 合帧后 `translateViewport` + `setTransform`。
- `transform` 仍为单一真源，合帧只合并"何时 setState"，不改变坐标数学。

验收：快速滚轮缩放保持鼠标锚点稳定、无发粘；平移跟手；`transform` 仍由 `zoomViewportAtPoint`/`translateViewport` 计算，与现有测试一致。

### 阶段 C：归一化 element model + 反向索引 + 版本缓存

在 `canvasEngine/geometry.js` expost 一组纯数据模型，借鉴 Excalidraw 的 `boundElements`/`version` 缓存：

1. 归一化卡片模型：`{ id, x, y, width, height, version, boundElements: [{id, type}] }`（`x/y` 为画布坐标左上角，`width/height` 由几何推导）。`collectCardGeometry` 产出的 `{left,right,top,bottom,width,height}` 逐步归一化到该模型。
2. 反向索引：`buildBoundElementsIndex(cardGeometries, arrows)` 得出 `cardId -> boundArrowIds[]`。箭头重算经 `doesNeedUpdate` 短路过滤，仅当 `start`/`end` 所在卡片 `version` 变化才重算。
3. 版本缓存：卡片几何带单调递增 `version`，`ResizeObserver/rAF` 刷新时只对 `version` 变化的卡片重算，存入带缓存的几何 Map。
4. 归一化端口比例：卡片端口（`getCanvasPortPoint`）与箭头端点以归一化比例存储，坐标变化时按比例重算，避免端点漂移与箭头反转（对应 Excalidraw `FixedPointBinding.fixedPoint`）。

成品：`geometry.js` 提供 `normalizeCardGeometry`、`buildBoundElementsIndex`、`shouldRecomputeForCards`（`doesNeedUpdate` 等价物）、`getStablePortPoint` 四个纯函数，全部可单测。

验收：`geometry.js` 新增测试覆盖反向索引、`doesNeedUpdate` 过滤、版本变化短路、比例端口稳定性；`node --test src/pages/Workspace/` 全绿。

> **实施偏差记录（2026-08-09 红队检查后）**
>
> 阶段 C 的核心目标"箭头只在所绑卡片几何变化时重算"已达成，但实现路径与上述设计有偏差：
>
> - **实际落地方案**：对象引用复用 + useEffect 依赖收窄。`refreshGeometry` 对未变化的卡片复用旧对象引用（`nextGeometry[cardId] = prev`），`CustomArrow`/`TempConnectionLine` 的 useEffect 依赖从整个 `geometry` 收窄为 `geometry?.[start]`/`geometry?.[end]`。只有端点卡片几何变化（引用不同）才触发重算，效果与反向索引等价但实现更简单。
> - **反向索引函数状态**：`buildBoundElementsIndex`、`shouldRecomputeForCards`、`getStablePortPoint` 已实现且有完整测试，但未被 `Canvas.jsx` 调用。它们作为已验证的工具函数保留，待未来需要更精细的跨组件重算调度时接线。
> - **取舍**：依赖收窄后，非端点卡片移动（改变 obstacles 布局）不会触发箭头重算路由。箭头不会断裂或消失，只是避障路径可能不是最优。在 1.0 阶段卡片规模下可接受。
> - **`createThrottleRAF`**（`throttle.js`）已实现且有测试，但滚轮和平移用的是内联 rAF（因需累积 delta / ref 存位置，与 `createThrottleRAF` 的闭包模式不完全匹配）。工具保留供未来交互复用。

---

## 5 模块边界与数据流目标

改造后的数据流（目标态）：

```
卡片 DOM
  → canvasEngine/geometry.js（ResizeObserver + rAF，version 缓存）
  → 归一化 cardGeometry（state + ref 保持一致，单一写入口）
      ├─ 箭头重算：经 buildBoundElementsIndex 反向索引 → doesNeedUpdate 过滤 → rAF 合帧重算
      ├─ 连线吸附：读 ref（仅读，不写）
      └─ 端口计算：getStablePortPoint（归一化比例）
```

对 `Canvas.jsx` 的改动约束：

- 消除 `cardGeometry`(state) 与 `cardGeometryRef`(ref) 双写不一致：统一由单一函数写入，state 与 ref 同步更新。
- 平移/缩放仍走 `translateViewport`/`zoomViewportAtPoint`（与现有测试兼容），仅加 `throttleRAF` 合帧。

---

## 6 验收标准

1. `npm --prefix frontend run build` 通过。
2. `node --test src/pages/Workspace/` 全绿（含新增 `throttle.js`、`geometry.js` 测试）。
3. 代码中不再存在连线轮询 `setInterval`（`CanvasEdges.jsx` 内无 `setInterval`/DOM 兜底分支）。
4. 手测：快速滚轮缩放锚点稳定、平移跟手、拖卡片时箭头实时跟随且不反转、卡片增多不掉帧。
5. 不引入新依赖（`package.json` 无变化），不改变产品形态。

---

## 7 风险与回滚

- **风险 1：几何单源化后首帧闪烁**。缓解：`useLayoutEffect` 在绘制前就绪几何，箭头未就绪时返回 `null`。
- **风险 2：rAF 合帧改变交互手感**。缓解：合帧只合并 setState 时机，坐标数学不变；若手感异常，可临时关闭合帧（保留 `throttle` 直通分支）。
- **风险 3：element model 归一化影响连线吸附**。缓解：吸附逻辑保持读 `cardGeometryRef`，仅几何来源改为归一化模型，行为不变。
- **回滚**：三阶段各自独立提交，任一步 ACC 不通过即回退该阶段 commit，不影响其他。

---

## 8 参考

调研基于 Excalidraw master 分支源码（`packages/element/src/binding.ts`、`packages/element/src/bounds.ts`、`packages/common/src/utils.ts`、`packages/excalidraw/scene/staticScene.ts`），以及本项目 `frontend/src/pages/Workspace/` 现有实现。本设计不引入 `@excalidraw/excalidraw` 依赖，仅借鉴其已验证的纯逻辑机制。
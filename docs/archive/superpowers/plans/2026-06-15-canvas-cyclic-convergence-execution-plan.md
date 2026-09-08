# EvoCanvas 循环收敛画布改造执行方案

> 适用对象：Antigravity / Codex / Claude Code 等实现型 Agent
> 状态：可执行方案
> 最后更新：2026-06-15
> 对齐文档：
> - [docs/vision/EvoCanvas1.0-PRD.md](/Users/apple/Desktop/evocanvas/docs/vision/EvoCanvas1.0-PRD.md)
> - [docs/superpowers/specs/2026-06-15-material-knowledge-dataflow-design.md](/Users/apple/Desktop/evocanvas/docs/superpowers/specs/2026-06-15-material-knowledge-dataflow-design.md)

## 1. 背景与目标

当前 Workspace 主画布采用近似线性的阶段式布局：

`探索发现 -> 需求定义 -> 问题澄清 -> 方案规划 -> 落地执行`

这与真实产品经理工作流不符。真实推进过程是循环收敛的：

1. 先有问题定义
2. 再出现待澄清
3. 再形成方案
4. 方案讨论中又暴露新问题
5. 问题被重新打开，再次澄清和收束

因此，本次改造的目标不是“美化看板”，而是把主画布从**线性泳道板**改造成**循环收敛网络**。

### 核心目标

1. 让 `卡片类型` 成为真相源，而不是 `阶段栏位`
2. 让 `关系` 成为推进逻辑，而不是横向位置
3. 让“回流 / 重新打开问题”成为一等路径
4. 保留 EvoCanvas 1.0 的最小闭环：
   `输入编译 -> 待澄清问题 -> 约束 / 待决策 -> 结构化交接物`

### 非目标

1. 不做多人协作
2. 不做复杂自由白板
3. 不做全量视觉重设计
4. 不在本轮引入复杂数据库迁移

---

## 2. 一句话方案

将当前主画布从“按阶段分栏摆卡片”，改为：

`以当前主题为中心，以卡片类型和关系网络为主结构，以视图模式表达当前关注面。`

具体做法：

1. 保留现有卡片对象体系
2. 扩充关系语义，支持 `reopens`
3. 弱化固定阶段栏
4. 增加“焦点主题 + 周边网络 + 活跃缺口栏 + 时间轴”布局
5. 把“探索发现 / 需求定义 / 方案规划”从真相结构改成可切换视图

---

## 3. 目标信息架构

### 3.1 真相源层级

主真相源改为三层：

1. `Topic / Workspace`
   - 当前主题
   - 当前目标
   - 当前活跃对象集合

2. `Card`
   - `evidence`
   - `problem`
   - `clarification`
   - `constraint`
   - `option`
   - `decision`
   - `handoff`

3. `Relation`
   - 表达对象之间的因果、依赖、冲突和回流

### 3.2 阶段语义调整

当前 `stage` 字段短期保留，但语义降级为：

1. `discovery`
2. `define`
3. `handoff`

不再让它承担“真实推进逻辑”，只作为轻量聚类和兼容字段。

### 3.3 卡片状态统一

建议统一卡片状态为：

1. `emerging`
2. `active`
3. `blocked`
4. `pending`
5. `confirmed`
6. `superseded`
7. `archived`

短期兼容策略：

1. 保留现有 `open / draft / pending / confirmed / effective`
2. 前端增加状态映射层
3. 后端后续逐步统一

---

## 4. 关系模型改造

### 4.1 保留关系

继续支持：

1. `derived_from`
2. `clarifies`
3. `supports`
4. `blocks`
5. `conflicts_with`
6. `produces`

### 4.2 新增关系

本轮新增以下关系：

1. `constrains`
   - 约束某个问题、方案或决策

2. `requires_decision`
   - 当前对象推进到这里必须有人拍板

3. `compares`
   - 两个方案选项之间的比较关系

4. `reopens`
   - 方案或决策讨论中重新打开某个问题

### 4.3 关系使用规则

1. `problem -> clarification`
   使用 `clarifies`

2. `clarification -> constraint`
   使用 `produces` 或 `supports`

3. `constraint -> option`
   使用 `constrains`

4. `option -> decision`
   使用 `requires_decision`

5. `option -> problem`
   当方案引出新问题时使用 `reopens`

---

## 5. 页面结构改造

## 5.1 目标布局

Workspace 主画布改为四区：

1. `中央焦点区`
   - 当前主题卡
   - 当前选中对象
   - 与其一跳关联的关键卡片

2. `周边关系网络区`
   - 围绕焦点卡展示相关 evidence / clarification / constraint / option / decision
   - 关系用连线表达

3. `右侧活跃缺口栏`
   - 待澄清
   - 待拍板
   - 被阻塞
   - 待交接

4. `底部时间轴`
   - 保留当前里程碑条
   - 不再承载逻辑推进结构

### 5.2 顶部视图切换

顶部新增视图模式切换：

1. `收敛视图`
2. `问题视图`
3. `方案视图`
4. `决策视图`
5. `交接视图`

这些视图只是过滤和聚焦，不改变底层卡片真相。

### 5.3 当前线性栏目处理

当前 1/2/3/4/5 栏不要硬删，但要降级：

1. 先移除明显的线性编号感
2. 改成柔性的簇标签或分组提示
3. 不再暗示“只能从左到右推进”

---

## 6. 前端执行任务

### Task A：重构 Canvas 布局骨架

**目标**
把当前线性网格改为“焦点 + 网络 + 活跃缺口 + 时间轴”的结构。

**涉及文件**

1. [frontend/src/pages/Workspace/Canvas.jsx](/Users/apple/Desktop/evocanvas/frontend/src/pages/Workspace/Canvas.jsx)
2. [frontend/src/pages/Workspace/Canvas.css](/Users/apple/Desktop/evocanvas/frontend/src/pages/Workspace/Canvas.css)
3. [frontend/src/pages/Workspace/index.jsx](/Users/apple/Desktop/evocanvas/frontend/src/pages/Workspace/index.jsx)

**步骤**

1. 新增 `viewMode` 状态
2. 将现有 section 分栏改为：
   - focus cluster
   - neighbor cluster
   - active backlog rail
3. 保留时间轴区域
4. 让卡片定位先按逻辑簇渲染，而不是按线性列渲染

### Task B：引入关系网络视图

**目标**
支持卡片之间以网络关系表达，而不只是分栏摆放。

**步骤**

1. 计算当前焦点卡
2. 取一跳和二跳关联
3. 将这些卡片映射到网络位置
4. 关系线根据 kind 使用不同样式

**要求**

1. 焦点卡居中
2. `evidence` 靠左下
3. `clarification` 靠左上
4. `constraint` 靠右上
5. `option / decision` 靠右侧
6. `handoff` 靠底部居中

### Task C：新增活跃缺口栏

**目标**
把真正需要推进的内容投影出来，而不是让用户自己在画布中找。

**内容**

1. `待澄清`
2. `待拍板`
3. `阻塞项`
4. `待交接`

**规则**

1. 只显示 `active / pending / blocked`
2. 支持点击后高亮对应卡片

### Task D：卡片视觉分层

**目标**
不同卡片类型一眼可区分。

**规则**

1. `evidence`：轻、薄、偏资料感
2. `problem`：中心感最强
3. `clarification`：强调“未解决”
4. `constraint`：强调“边界”
5. `option`：强调“方案候选”
6. `decision`：强调“需要拍板 / 已确认”
7. `handoff`：强调“收束结果”

---

## 7. 后端执行任务

### Task E：扩充关系枚举与校验

**涉及文件**

1. [app/canvas/domain/relations.py](/Users/apple/Desktop/evocanvas/app/canvas/domain/relations.py)
2. [app/canvas/service.py](/Users/apple/Desktop/evocanvas/app/canvas/service.py)
3. [app/api/canvas_schemas.py](/Users/apple/Desktop/evocanvas/app/api/canvas_schemas.py)

**步骤**

1. 新增关系类型：
   - `constrains`
   - `requires_decision`
   - `compares`
   - `reopens`
2. 更新关系校验逻辑
3. 更新 relation create API 的允许值

### Task F：新增 `option` 卡片类型

**涉及文件**

1. [app/canvas/domain/cards.py](/Users/apple/Desktop/evocanvas/app/canvas/domain/cards.py)
2. [app/canvas/service.py](/Users/apple/Desktop/evocanvas/app/canvas/service.py)
3. [frontend/src/pages/Workspace/Canvas.jsx](/Users/apple/Desktop/evocanvas/frontend/src/pages/Workspace/Canvas.jsx)

**目标**
给“方案规划”一个独立对象层，不再混在 decision 或 handoff 里。

**步骤**

1. 新增 `CanvasCardKind.OPTION`
2. 前端识别 option 的显示样式
3. Todo 投影暂不纳入 option，除非状态为 blocked 或 pending

### Task G：支持问题回流

**目标**
让“方案讨论中发现新问题”合法成立。

**实现策略**

1. 允许从 `option` 或 `decision` 新建 `problem / clarification`
2. 自动附加 `reopens` 关系
3. 不强制改变旧卡片 stage

### Task H：handoff 聚合逻辑升级

**目标**
handoff 不再只统计“当前线性阶段里还有几张卡”，而要聚合当前网络中的关键对象。

**规则**

handoff 至少聚合：

1. 当前主问题
2. 未关闭 clarification
3. 已确认或有效 constraint
4. pending / confirmed decision
5. 当前 option 摘要

---

## 8. AI 行为改造

### Task I：调整 Supervisor 路由策略

**目标**
允许复合收敛路径，而不是只做单向阶段路由。

**规则**

1. 有新材料：
   必须带 `InputCompiler`

2. 有方案讨论语义：
   可同时带 `OptionBuilder`（若本轮不新建角色，也可先复用 `DecisionSteward` 过渡）

3. 方案中发现新缺口：
   必须允许生成 `problem / clarification`

4. 不得因为“进入方案讨论”而禁止重新回到问题层

### Task J：改进回退规则生成

当前本地 fallback 太容易“复读用户原话”。

本轮至少改进为：

1. `InputCompiler`
   生成 `evidence + problem`

2. `Clarifier`
   生成更短、更对象化的待澄清标题

3. `ConstraintSteward`
   尽量提炼规则句，而不是简单回显消息

4. `DecisionSteward`
   必须突出“为什么需要拍板”

---

## 9. 迁移策略

### 9.1 不做破坏式迁移

要求：

1. 不删除现有字段
2. 不删除现有 API
3. 不直接清空旧 workspace 数据

### 9.2 兼容策略

1. 旧卡片仍可按 `stage` 加载
2. 新前端优先按 `relation + kind + status` 组织
3. 若缺少关系，则回退到当前简化分组显示

---

## 10. 测试方案

### 10.1 核心场景

以“问题定义 -> 澄清 -> 方案 -> 重新发现问题 -> 待拍板 -> 交接物”为完整主链路。

### 10.2 必测用例

1. 新材料输入后，先生成 `evidence / problem / clarification`
2. 从 clarification 沉淀 constraint
3. 新增 option 卡片
4. option 引出新的 clarification
5. option 或 problem 进入 decision
6. approved decision 在 handoff 中可见
7. 活跃缺口栏正确反映当前 active/pending/blocked

### 10.3 自动化测试文件

至少更新：

1. [tests/test_canvas_turn_flow.py](/Users/apple/Desktop/evocanvas/tests/test_canvas_turn_flow.py)
2. [tests/test_canvas_api.py](/Users/apple/Desktop/evocanvas/tests/test_canvas_api.py)
3. [tests/test_canvas_supervisor.py](/Users/apple/Desktop/evocanvas/tests/test_canvas_supervisor.py)
4. 新增 `tests/test_canvas_network_view.py`（如前端逻辑抽为纯函数）

---

## 11. 验收标准

### 功能验收

1. 用户能看到“中央主题 + 周边网络 + 活跃缺口栏”
2. 方案讨论中可以合法生成新问题
3. decision 确认后不会从 handoff 中丢失
4. 画布不再强依赖 1/2/3/4/5 线性推进

### 体验验收

1. 首轮输入不再像大段摘要报告
2. 卡片更对象化、更短
3. 用户能一眼区分“问题 / 澄清 / 约束 / 决策 / 方案”
4. 页面读法更像“收敛网络”而不是“流水线任务板”

### 技术验收

1. `python3 -m unittest` 相关测试全绿
2. `npm --prefix frontend run build` 通过
3. 旧 workspace 打开不报错

---

## 12. 推荐实施顺序

必须按下面顺序推进，不建议跳步。

### Phase 1：语义底座

1. 加关系类型
2. 加 `option`
3. 升级 handoff 聚合
4. 升级 supervisor 和 fallback

### Phase 2：前端骨架

1. 改 Canvas 布局
2. 增加焦点区
3. 增加活跃缺口栏
4. 增加视图切换

### Phase 3：网络交互

1. 网络布局
2. 节点高亮
3. 关系强调
4. 点击卡片聚焦

### Phase 4：回流验证

1. 从 option reopen problem
2. 从 decision reopen clarification
3. handoff 聚合回归

---

## 13. 对 Antigravity 的明确执行要求

1. 不要把这次任务理解成纯样式重构。
2. 不要只把线性栏目换个皮肤。
3. 必须先改对象模型和关系语义，再改页面布局。
4. 每完成一个 Phase，都要先跑测试再进入下一步。
5. 如果发现现有 `stage` 语义与新结构冲突，优先兼容，不要直接删除旧字段。

---

## 14. 交付物清单

最终应交付：

1. 更新后的 Canvas 前端布局
2. 扩充后的 card/relation domain
3. 升级后的 supervisor / fallback 行为
4. 升级后的 handoff 聚合
5. 对应自动化测试
6. 一份简短的迁移说明

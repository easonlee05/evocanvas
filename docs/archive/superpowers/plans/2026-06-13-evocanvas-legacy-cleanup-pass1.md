# EvoCanvas 前端清理第一轮实施计划

> **面向执行型 Agent：** 实施本计划时，必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`。步骤使用复选框 `- [ ]` 语法进行追踪。

**目标：** 让前端重构先行推进，优先从 EvoCanvas 当前活跃 UI 路径中移除最干扰判断的 EvoLoop 旧产品语义，同时将后端改造延后到前端形态稳定之后。

**方案：** 本轮只调整活跃前端外壳、工作台文案以及面向迁移的说明文档。旧前端页面继续保留在仓库中，作为迁移过渡资产；但主导航与当前产品叙事要完全切到 EvoCanvas 1.0 语义。后端别名、workflow 重命名等工作明确后置，放到下一轮处理。

**技术栈：** Python、FastAPI、React、React Router、unittest、Vite

---

## 当前边界

- 当前纳入范围：
  - `frontend/src/components/layout/`
  - `frontend/src/pages/LandingPage/`
  - `frontend/src/pages/Workspace/`
  - 需要增加“迁移过渡”提示的旧前端页面
  - 需要与“前端先行迁移”策略保持一致的 `README.md` 与 `AGENTS.md`
- 前端稳定后再处理：
  - `app/api/`
  - `app/services/`
  - `app/workflows/`
  - `app/core/`
  - 后端任务命名、别名兼容与 workflow 注册表调整

---

### 任务 1：从主导航和工作台文案中移除旧产品页面语义

**文件：**
- 修改：`frontend/src/components/layout/Sidebar.jsx`
- 修改：`frontend/src/pages/Workspace/index.jsx`
- 修改：`frontend/src/pages/LandingPage/LandingPage.jsx`
- 验证：`frontend/src/components/layout/sidebarHistory.js`

- [ ] **步骤 1：先写失败测试**

```javascript
it("shows only EvoCanvas navigation entries", () => {
  render(<Sidebar />);
  expect(screen.queryByText("任务大厅")).toBeNull();
  expect(screen.queryByText("知识库")).toBeNull();
  expect(screen.getByText("新建对话")).toBeInTheDocument();
  expect(screen.getByText("示例工作台")).toBeInTheDocument();
});
```

- [ ] **步骤 2：运行测试，确认当前会失败**

运行：`npm --prefix /Users/apple/Desktop/evocanvas/frontend test -- --runInBand`
预期：如果渲染出的前端壳里仍泄露旧导航标签或旧工作台文案，则测试 FAIL。

- [ ] **步骤 3：补最小实现**

```javascript
// frontend/src/pages/Workspace/index.jsx
const outputItems = [
  { key: 'primary', label: '结构化交接物', content: doc },
  { key: 'secondary', label: '画布说明', content: docSecondary },
].filter(item => item.content);

const composerPlaceholder = isLive
  ? '运行中，可打断并补充新的输入、约束或待决策...'
  : '向 EvoCanvas 补充输入，或要求它整理待澄清问题...';
```

```javascript
// frontend/src/components/layout/Sidebar.jsx
const navItems = [
  { icon: <MessageSquarePlus size={15} />, label: '新建对话', path: '/', primary: true },
  { icon: <LayoutDashboard size={15} />, label: '示例工作台', path: '/workspace/demo' },
];
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`npm --prefix /Users/apple/Desktop/evocanvas/frontend test -- --runInBand`
预期：侧边栏可见性断言 PASS。

- [ ] **步骤 5：提交**

```bash
git -C /Users/apple/Desktop/evocanvas add frontend/src/components/layout/Sidebar.jsx frontend/src/pages/Workspace/index.jsx frontend/src/pages/LandingPage/LandingPage.jsx
git -C /Users/apple/Desktop/evocanvas commit -m "refactor: hide legacy frontend product surfaces"
```

### 任务 2：把保留的旧页面明确标记为“迁移过渡资产”

**文件：**
- 修改：`frontend/src/pages/Tasks/index.jsx`
- 修改：`frontend/src/pages/KnowledgeBase/index.jsx`
- 修改：`frontend/src/pages/RuleAudit/index.jsx`
- 修改：`frontend/src/pages/RecycleBin/index.jsx`

- [ ] **步骤 1：先写失败测试**

```javascript
it("marks legacy pages as migration-only views", () => {
  render(<Tasks />);
  expect(screen.getByText(/迁移过渡页面/i)).toBeInTheDocument();
});
```

- [ ] **步骤 2：运行测试，确认当前会失败**

运行：`npm --prefix /Users/apple/Desktop/evocanvas/frontend test -- --runInBand`
预期：由于这些保留页面仍把自己表现成 EvoCanvas 当前活跃模块，测试应当 FAIL。

- [ ] **步骤 3：补最小实现**

```javascript
// frontend/src/pages/Tasks/index.jsx
<div className="legacy-surface-banner">
  迁移过渡页面：该页面仅保留用于参考旧任务数据，不属于 EvoCanvas 1.0 主路径。
</div>
```

```javascript
// frontend/src/pages/KnowledgeBase/index.jsx
<div className="legacy-surface-banner">
  迁移过渡页面：该页面是旧产品资产参考区，当前不作为 EvoCanvas 1.0 主能力入口。
</div>
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`npm --prefix /Users/apple/Desktop/evocanvas/frontend test -- --runInBand`
预期：“迁移过渡页面”提示断言 PASS。

- [ ] **步骤 5：提交**

```bash
git -C /Users/apple/Desktop/evocanvas add frontend/src/pages/Tasks/index.jsx frontend/src/pages/KnowledgeBase/index.jsx frontend/src/pages/RuleAudit/index.jsx frontend/src/pages/RecycleBin/index.jsx
git -C /Users/apple/Desktop/evocanvas commit -m "docs: mark retained legacy pages as inactive"
```

### 任务 3：让迁移文档与验证说明对齐“前端先行”的新边界

**文件：**
- 修改：`README.md`
- 修改：`AGENTS.md`
- 新建：`docs/superpowers/plans/2026-06-13-evocanvas-legacy-cleanup-pass1.md`

- [ ] **步骤 1：先写检查清单**

```text
1. README 必须说明主路径与 reference 路径的区别。
2. AGENTS 必须说明哪些保留页面只是过渡资产。
3. 本计划文件必须明确“前端先行”的清理边界。
```

- [ ] **步骤 2：执行检查，确认当前还不满足**

运行：`rg -n "迁移过渡|context_compile|clarification_review|reference/" /Users/apple/Desktop/evocanvas/README.md /Users/apple/Desktop/evocanvas/AGENTS.md`
预期：在文案改动真正落地前，会缺少部分“前端先行清理”相关表述。

- [ ] **步骤 3：补最小实现**

```markdown
## 当前迁移状态

- 主路径继续承载 EvoCanvas 1.0 的活跃实现
- `reference/evoloop-legacy/` 只保留历史后端实现与测试参考
- 旧任务页、知识页、法则页、回收页若仍存在，仅作为迁移过渡资产
- 后端命名与 workflow 改造在前端稳定后另起一轮
```

- [ ] **步骤 4：再次检查，确认通过**

运行：`rg -n "迁移过渡|reference/evoloop-legacy|EvoCanvas 1.0" /Users/apple/Desktop/evocanvas/README.md /Users/apple/Desktop/evocanvas/AGENTS.md /Users/apple/Desktop/evocanvas/docs/superpowers/plans/2026-06-13-evocanvas-legacy-cleanup-pass1.md`
预期：三个文件里都能匹配到对应语句，检查 PASS。

- [ ] **步骤 5：提交**

```bash
git -C /Users/apple/Desktop/evocanvas add README.md AGENTS.md docs/superpowers/plans/2026-06-13-evocanvas-legacy-cleanup-pass1.md
git -C /Users/apple/Desktop/evocanvas commit -m "docs: capture frontend first cleanup plan"
```

## 后续后端跟进项

前端确认稳定后，再单独开一轮后端计划处理以下事项：

1. `spec_to_agent` / `acceptance_review` 的 EvoCanvas 化别名与注册表重命名。
2. `manual` / `prd` / `legacy_*` 兼容层的梳理与收缩。
3. `app/api/server.py`、`app/api/schemas.py`、`app/cli/commands.py` 的默认任务命名切换。
4. `app/core/work.py`、`app/core/artifacts.py`、`app/workflows/context_compiler.py` 的对象语义重命名。

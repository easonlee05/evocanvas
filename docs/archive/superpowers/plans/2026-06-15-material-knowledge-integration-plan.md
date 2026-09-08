# EvoCanvas 联调阶段计划：资料分流、知识候选与数据引用

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or equivalent stepwise execution. Track progress by checking boxes in order and do not skip validation gates.

**Goal:** 围绕 EvoCanvas 1.0 新引入的 `Material / Knowledge Candidate / SourceRef` 三层能力，完成一次完整联调，验证“输入编译 -> 待澄清问题 -> 约束 / 待决策 -> 结构化交接物”的最小闭环在真实前后端联动下成立，并确认不会把原始资料误写成知识库结论。

**In Scope:**
1. Workspace 输入区三分入口：`添加当前资料`、`引用知识库条目`、`连接数据源引用`
2. 后端接口：`/api/materials`、`/api/knowledge/candidates`、`/api/source-connectors`、`/api/source-refs`
3. 画布消息协议：`material_ids` + `source_ref_ids`
4. 编译结果：evidence / problem / clarification / constraint / decision / handoff
5. 结构化交接物、快照、确认流的兼容性回归

**Out of Scope:**
1. 真正的数据库连接器落地
2. 知识候选的独立正式页面
3. 多人协作和权限体系
4. 长期存储和数据库替换

**Success Criteria:**
1. 用户上传资料后，系统明确落到材料层，不自动进知识库。
2. 用户创建数据引用后，系统生成可追溯快照摘要，并在输入编译中作为证据使用。
3. AI 生成的卡片 `evidence_refs` 同时兼容 `material_id` 与 `source_ref_id`。
4. 交接物刷新、快照、确认流、最近项目列表不因本次改动回归。
5. 单测、API 联调、前端构建、关键用户路径手测均通过。

**Execution Environment:**
1. Backend: `python3 -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000 --reload`
2. Frontend: `VITE_API_BASE=http://127.0.0.1:8000 npm --prefix frontend run dev`
3. Build check: `npm --prefix frontend run build`
4. API tests: `python3 -m unittest tests.test_canvas_api tests.test_canvas_supervisor tests.test_canvas_turn_flow`
5. E2E API tests: `python3 -m unittest tests.test_canvas_e2e_integration`

---

### Phase 1: 基线确认与环境启动

- [ ] **Step 1.1: 记录当前联调对象与已实现边界**
确认本轮联调只覆盖以下链路：
`materials -> canvas messages -> cards/handoff`
`knowledge candidates -> approval`
`source refs -> snapshot summary -> canvas messages`

- [ ] **Step 1.2: 启动后端服务**
运行：
```bash
python3 -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000 --reload
```
验证：
```bash
curl -s http://127.0.0.1:8000/api/health
```

- [ ] **Step 1.3: 启动前端服务**
运行：
```bash
VITE_API_BASE=http://127.0.0.1:8000 npm --prefix frontend run dev
```
验证首页和 Workspace 路由均可打开。

- [ ] **Step 1.4: 跑一轮当前自动化基线**
运行：
```bash
python3 -m unittest tests.test_canvas_api tests.test_canvas_supervisor tests.test_canvas_turn_flow
npm --prefix frontend run build
```
若此处失败，先修基线，不进入联调手测。

---

### Phase 2: 后端接口联调

- [ ] **Step 2.1: 材料层接口联调**
测试接口：
1. `POST /api/materials`
2. `GET /api/materials/{material_id}`

预期：
1. 返回 `layer=material`
2. `summary` 明确说明“不自动进入知识库”
3. 可取回脱敏后的展示元数据

- [ ] **Step 2.2: 知识候选接口联调**
测试接口：
1. `GET /api/knowledge/candidates`
2. `POST /api/knowledge/candidates`
3. `POST /api/knowledge/{id}/approve`

预期：
1. 新候选条目状态为 `candidate`
2. 审批后返回 `status=approved`
3. 候选和正式知识语义不混淆

- [ ] **Step 2.3: 数据引用接口联调**
测试接口：
1. `GET /api/source-connectors`
2. `POST /api/source-refs`
3. `GET /api/source-refs/{id}`
4. `POST /api/source-refs/{id}/snapshot`

预期：
1. 返回连接器清单
2. 创建引用后有 `snapshot.summary`
3. 刷新快照后条件变更反映到摘要中

---

### Phase 3: 画布编译联调

- [ ] **Step 3.1: 仅材料输入的编译路径**
在 Workspace 上传一份文本资料后发送消息。

预期：
1. 产生 `input_compilation` 意图
2. 自动生成 `evidence / problem / clarification`
3. 每张卡的 `evidence_refs` 只包含 `material_id`

- [ ] **Step 3.2: 仅数据引用输入的编译路径**
在 Workspace 创建一个 `source_ref` 后发送消息。

预期：
1. 产生 `input_compilation` 意图
2. 数据快照摘要被 supervisor/agent 吸收
3. 卡片 `evidence_refs` 包含 `source_ref_id`

- [ ] **Step 3.3: 材料 + 数据引用混合输入路径**
同时附带一个 `material_id` 和一个 `source_ref_id` 发送消息。

预期：
1. 卡片 `evidence_refs` 顺序稳定
2. 不丢材料，也不丢数据引用
3. 不会静默把数据引用写成知识条目

- [ ] **Step 3.4: 选中卡片 + 新证据的二次收敛路径**
先生成 clarification，再选中该卡并补充材料或数据引用。

预期：
1. 新卡片关联旧卡片
2. `metadata.selected_card_ids` 正确
3. 约束/待决策/交接物的路由行为符合当前输入

---

### Phase 4: 前端交互联调

- [ ] **Step 4.1: Workspace 输入区入口检查**
检查三个按钮与文案：
1. `添加当前资料`
2. `引用知识库条目`
3. `连接数据源引用`

预期：
1. 不再出现“上传参考材料”这种模糊语义
2. 菜单可展开
3. 创建后的 chip 可移除

- [ ] **Step 4.2: 知识条目插入输入框路径**
点击知识库条目，观察输入框是否插入“参考知识”文本。

预期：
1. 不产生材料上传请求
2. 不生成 source ref
3. 仅作为当前对话上下文引用

- [ ] **Step 4.3: 数据引用创建路径**
从数据源入口创建引用。

预期：
1. 出现数据引用 chip
2. 发送消息时 `source_ref_ids` 被带上
3. 消息发送后 chip 被清空

---

### Phase 5: 结构化交接物与确认流回归

- [ ] **Step 5.1: handoff 刷新回归**
基于已有 clarification/constraint/decision 执行 handoff 刷新。

预期：
1. handoff 卡片生成或刷新
2. `handoff.summary` 可读
3. snapshot 同步生成

- [ ] **Step 5.2: 高风险确认流回归**
提交待决策或高影响变更。

预期：
1. 出现 confirmation 队列
2. approve / reject 都可执行
3. turn 锁能正常释放

- [ ] **Step 5.3: 最近项目与工作区时间戳回归**
执行卡片移动、关系创建、handoff 刷新后检查最近项目列表。

预期：
1. `updated_at` 更新
2. 最近修改的 workspace 排到前面
3. 无异常排序倒挂

---

### Phase 6: 自动化测试执行方案

- [ ] **Step 6.1: 核心 API/编排层单测**
运行：
```bash
python3 -m unittest tests.test_canvas_api tests.test_canvas_supervisor tests.test_canvas_turn_flow
```

- [ ] **Step 6.2: 完整 E2E API 测试**
运行：
```bash
python3 -m unittest tests.test_canvas_e2e_integration
```

- [ ] **Step 6.3: Python 编译检查**
运行：
```bash
python3 -m py_compile app/api/server.py app/api/schemas.py app/api/canvas_schemas.py app/canvas/service.py app/canvas/agent/supervisor.py
```

- [ ] **Step 6.4: 前端构建检查**
运行：
```bash
npm --prefix frontend run build
```

- [ ] **Step 6.5: 浏览器手测**
使用本地浏览器或 in-app Browser，按本计划中的手工路径逐项验证。

---

### Test Matrix

| 编号 | 场景 | 输入 | 关键断言 | 类型 |
| --- | --- | --- | --- | --- |
| TC-01 | 材料上传 | txt 文件 | `layer=material`，不自动入知识库 | API |
| TC-02 | 读取材料元数据 | `material_id` | 返回脱敏元数据 | API |
| TC-03 | 新建知识候选 | rule/doc payload | `status=candidate` | API |
| TC-04 | 审批知识候选 | candidate id | `status=approved` | API |
| TC-05 | 获取数据连接器 | 无 | 返回连接器列表 | API |
| TC-06 | 创建数据引用 | `saved_query` payload | 生成 `snapshot.summary` | API |
| TC-07 | 刷新数据快照 | filters 更新 | 摘要反映新条件 | API |
| TC-08 | 仅材料编译 | `material_ids` | 生成 evidence/problem/clarification | Turn |
| TC-09 | 仅数据引用编译 | `source_ref_ids` | 生成 input compilation，证据链正确 | Turn |
| TC-10 | 混合证据编译 | material + source ref | `evidence_refs` 同时包含两类 ID | Turn |
| TC-11 | 知识条目插入输入框 | 点击知识菜单 | 只改输入框，不创建上传对象 | Frontend |
| TC-12 | 数据引用 chip 生命周期 | 创建后发送消息 | 发送后 chip 清空 | Frontend |
| TC-13 | handoff 刷新 | clarification/constraint/decision | handoff + snapshot 同步更新 | Regression |
| TC-14 | 高风险确认流 | decision proposal | pending confirmation / approve / reject 正常 | Regression |
| TC-15 | 最近项目排序 | 多工作区修改 | 最近更新靠前 | Regression |

---

### Bug Triage 规则

- [ ] **P0**
后端起不来、前端起不来、消息无法发送、handoff 无法读取。

- [ ] **P1**
材料被误写成知识、数据引用无法进入编译、确认流卡死、快照丢失。

- [ ] **P2**
文案不一致、chip 交互异常、菜单状态错乱、时间戳排序不稳定。

- [ ] **P3**
样式细节、摘要文案不够自然、构建警告但不影响功能。

---

### Exit Criteria

- [ ] 所有 Phase 1-6 必要步骤完成
- [ ] `TC-01` 到 `TC-15` 全部跑通或有明确豁免说明
- [ ] 自动化测试全绿
- [ ] 前端 build 通过
- [ ] 所有未解决问题都有优先级、复现步骤和下一步处理建议

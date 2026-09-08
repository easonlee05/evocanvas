# Figma 式自由画布编辑与连线交互实施计划 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个类 Figma 的自由编辑画布，包含悬浮工具栏、指针状态机、卡片/文本绝对定位添加与原地删除、拖拽建连与高亮/删除连线，同时补全后端 API 支持和优化时间轴收拢交互。

**Architecture:** 前端引入指针工具状态 `activeTool` 进行模式切换，计算缩放平移逆矩阵实现绝对定位添加，利用 SVG/Pointer 交互实现锚点动态连线与选中高亮；后端在服务层和路由层补充卡片创建、卡片删除（级联清理）及连线删除接口。

**Tech Stack:** React, Tailwind-free Vanilla CSS, FastAPI (Python), Pytest (FastAPI TestClient), Lucide-react

---

### Task 1: 后端 Service 与 API 改造 (TDD 模式)

**Files:**
* Modify: `app/canvas/service.py`
* Modify: `app/api/server.py`
* Modify: `tests/test_canvas_api.py`

- [ ] **Step 1: 在 `tests/test_canvas_api.py` 中编写新增 API 的失败测试用例**

```python
    def test_create_canvas_card_manually(self) -> None:
        # 1. 尝试在指定 workspace 下新建一张 constraint 卡片
        response = self.client.post(
            "/api/canvas/workspaces/demo/cards",
            json={
                "kind": "constraint",
                "title": "新建的手动规则",
                "summary": "由人类手动补充的约束规则",
                "stage": "define"
            },
            headers=self.headers
        )
        self.assertEqual(response.status_code, 200)
        card = response.json()
        self.assertEqual(card["kind"], "constraint")
        self.assertEqual(card["title"], "新建的手动规则")
        self.assertEqual(card["stage"], "define")
        self.assertTrue(card["card_id"].startswith("card_"))

    def test_delete_canvas_card_manually_cleans_relations(self) -> None:
        # 1. 预先建立两张卡片的关系并验证
        rel_resp = self.client.post(
            "/api/canvas/workspaces/demo/relations",
            json={
                "kind": "constrains",
                "from_card_id": "card_p1", # 示例初始存在卡片
                "to_card_id": "card_c1"
            },
            headers=self.headers
        )
        # 2. 删除其中一张卡片
        del_resp = self.client.delete(
            "/api/canvas/workspaces/demo/cards/card_p1",
            headers=self.headers
        )
        self.assertEqual(del_resp.status_code, 200)
        
        # 3. 验证卡片列表已不包含该卡片
        canvas_resp = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers)
        cards = canvas_resp.json()["cards"]
        self.assertFalse(any(c["card_id"] == "card_p1" for c in cards))
        
        # 4. 验证相关的关系连线已被连带清除
        relations = canvas_resp.json()["relations"]
        self.assertFalse(any(r["from_card_id"] == "card_p1" or r["to_card_id"] == "card_p1" for r in relations))

    def test_delete_canvas_relation_manually(self) -> None:
        # 1. 创建关系
        self.client.post(
            "/api/canvas/workspaces/demo/relations",
            json={
                "kind": "supports",
                "from_card_id": "card_e1",
                "to_card_id": "card_p1"
            },
            headers=self.headers
        )
        # 2. 删除关系
        del_rel = self.client.delete(
            "/api/canvas/workspaces/demo/relations",
            params={
                "from_card_id": "card_e1",
                "to_card_id": "card_p1"
            },
            headers=self.headers
        )
        self.assertEqual(del_rel.status_code, 200)
        
        # 3. 验证关系已不存在
        canvas_resp = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers)
        relations = canvas_resp.json()["relations"]
        self.assertFalse(any(r["from_card_id"] == "card_e1" and r["to_card_id"] == "card_p1" for r in relations))
```

- [ ] **Step 2: 运行测试以验证测试失败**

Run: `pytest tests/test_canvas_api.py -v`
Expected: 编译报错或 FAIL，提示 `POST /cards`, `DELETE /cards/{card_id}`, `DELETE /relations` 接口返回 404/405 等。

- [ ] **Step 3: 在 `app/canvas/service.py` 中实现服务层新增逻辑**

在 `app/canvas/service.py` 末尾新增以下三个方法：

```python
    def create_card(
        self,
        workspace_id: str,
        kind: str,
        title: str,
        summary: str = "",
        stage: str = "discovery",
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """人类手动创建卡片。"""
        self.get_workspace(workspace_id)
        cards = self.repository.load_cards(workspace_id)
        from app.canvas.domain.cards import CanvasCard, CanvasCardKind
        card = CanvasCard(
            card_id=f"card_{uuid4().hex[:10]}",
            kind=CanvasCardKind(kind),
            title=title.strip(),
            summary=summary.strip(),
            stage=stage,
            status="open",
            metadata=metadata or {},
        )
        cards.append(card)
        self.repository.save_cards(workspace_id, cards)
        self._touch_workspace(self.get_workspace(workspace_id))
        self._publish_event(
            workspace_id,
            "canvas.card.created",
            {
                "workspace_id": workspace_id,
                "card_id": card.card_id,
                "card": card.to_dict(),
            },
            status="created",
        )
        return card.to_dict()

    def delete_card(self, workspace_id: str, card_id: str) -> Dict[str, Any]:
        """删除画布卡片并级联清理与其相关的关系连线。"""
        self.get_workspace(workspace_id)
        cards = self.repository.load_cards(workspace_id)
        next_cards = [c for c in cards if c.card_id != card_id]
        if len(next_cards) == len(cards):
            raise CanvasCardNotFoundError("card not found")
        
        self.repository.save_cards(workspace_id, next_cards)
        
        # 级联清理关系连线
        relations = self.repository.load_relations(workspace_id)
        next_relations = [
            r for r in relations
            if r.from_card_id != card_id and r.to_card_id != card_id
        ]
        if len(next_relations) < len(relations):
            self.repository.save_relations(workspace_id, next_relations)
            
        self._touch_workspace(self.get_workspace(workspace_id))
        self._publish_event(
            workspace_id,
            "canvas.card.deleted",
            {
                "workspace_id": workspace_id,
                "card_id": card_id,
            },
            status="deleted",
        )
        return {"workspace_id": workspace_id, "deleted": True}

    def delete_relation(
        self,
        workspace_id: str,
        from_card_id: str,
        to_card_id: str,
    ) -> Dict[str, Any]:
        """删除两个卡片之间的关联关系。"""
        self.get_workspace(workspace_id)
        relations = self.repository.load_relations(workspace_id)
        next_relations = []
        found = False
        deleted_relation = None
        for r in relations:
            if r.from_card_id == from_card_id and r.to_card_id == to_card_id:
                found = True
                deleted_relation = r
            else:
                next_relations.append(r)
        
        if not found:
            raise CanvasRelationValidationError("relation not found between specified cards")
            
        self.repository.save_relations(workspace_id, next_relations)
        self._touch_workspace(self.get_workspace(workspace_id))
        self._publish_event(
            workspace_id,
            "canvas.relation.deleted",
            {
                "workspace_id": workspace_id,
                "relation_id": deleted_relation.relation_id,
                "from_card_id": from_card_id,
                "to_card_id": to_card_id,
            },
            status="deleted",
        )
        return {"workspace_id": workspace_id, "deleted": True}
```

- [ ] **Step 4: 在 `app/api/server.py` 中挂载 API 路由**

在 `app/api/server.py` 的 canvas 路由区域中挂载 3 个端点：

```python
    @app.post("/api/canvas/workspaces/{workspace_id}/cards")
    async def create_canvas_card(
        workspace_id: str,
        request: CanvasCardCreateRequest, # 需在 schemas 中定义
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        try:
            return canvas_service.create_card(
                workspace_id=workspace_id,
                kind=request.kind,
                title=request.title,
                summary=request.summary,
                stage=request.stage,
                metadata=request.metadata,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.delete("/api/canvas/workspaces/{workspace_id}/cards/{card_id}")
    async def delete_canvas_card(
        workspace_id: str,
        card_id: str,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        try:
            return canvas_service.delete_card(workspace_id, card_id)
        except CanvasCardNotFoundError:
            raise HTTPException(status_code=404, detail="card not found")

    @app.delete("/api/canvas/workspaces/{workspace_id}/relations")
    async def delete_canvas_relation(
        workspace_id: str,
        from_card_id: str,
        to_card_id: str,
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        try:
            return canvas_service.delete_relation(
                workspace_id=workspace_id,
                from_card_id=from_card_id,
                to_card_id=to_card_id,
            )
        except CanvasRelationValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
```

在 `app/api/canvas_schemas.py` 中添加 `CanvasCardCreateRequest`：
```python
class CanvasCardCreateRequest(BaseModel):
    kind: str
    title: str
    summary: str = ""
    stage: str = "discovery"
    metadata: Optional[Dict[str, Any]] = None
```

- [ ] **Step 5: 重新运行 Pytest 以验证测试通过**

Run: `pytest tests/test_canvas_api.py -v`
Expected: PASS

- [ ] **Step 6: Git Commit 提交后端改造**

```bash
git add tests/test_canvas_api.py app/canvas/service.py app/api/server.py app/api/canvas_schemas.py
git commit -m "feat: implement manual card and relation editing APIs with full test coverage"
```

---

### Task 2: 前端关系模型与 API 对接修正

**Files:**
* Modify: `frontend/src/pages/Workspace/Canvas.jsx`
* Modify: `frontend/src/api.js`

- [ ] **Step 1: 修正前端对后端 API 连线数据（Relations）解析 BUG**

修改 `Canvas.jsx:mapBackendCardsToSections` 方法中的 relations 遍历逻辑，替换掉只检查 `rel.relation_type === 'next'` 的过时逻辑：

```javascript
    const nextMap = {};
    (backendRelations || []).forEach(rel => {
      // 兼容后端真实字段 from_card_id / to_card_id 与旧版的 source_id / target_id
      const sourceId = rel.from_card_id || rel.source_id;
      const targetId = rel.to_card_id || rel.target_id;
      if (sourceId && targetId) {
        if (!nextMap[sourceId]) nextMap[sourceId] = [];
        nextMap[sourceId].push(targetId);
      }
    });
```

- [ ] **Step 2: 导出并在前端挂载 `apiDelete`**

确认 `frontend/src/api.js` 已经导出了 `apiDelete`。并在 `Canvas.jsx` 头部挂载 `apiDelete`：
```javascript
import { apiPost, apiDelete, apiUrl } from '../../api';
```

- [ ] **Step 3: 频繁提交**

```bash
git add frontend/src/pages/Workspace/Canvas.jsx
git commit -m "fix: resolve backend relations mapping bugs in Canvas.jsx and import apiDelete"
```

---

### Task 3: 悬浮工具栏 (Figma Toolbar) 与指针状态机实现

**Files:**
* Modify: `frontend/src/pages/Workspace/Canvas.jsx`
* Modify: `frontend/src/pages/Workspace/Canvas.css`

- [ ] **Step 1: 在 `Canvas.css` 中添加工具栏与状态机控制的 CSS 样式**

在 `frontend/src/pages/Workspace/Canvas.css` 底部添加：

```css
/* Figma 底部工具栏样式 */
.figma-toolbar {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  height: 48px;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border);
  border-radius: 999px;
  box-shadow: 0 10px 32px rgba(0,0,0,0.08);
  display: flex;
  align-items: center;
  padding: 0 8px;
  gap: 4px;
  z-index: 1000;
  pointer-events: auto;
}

.figma-toolbar-btn {
  background: none;
  border: none;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.figma-toolbar-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.figma-toolbar-btn.active {
  background: #007aff;
  color: white;
}

.figma-toolbar-divider {
  width: 1px;
  height: 20px;
  background: var(--border);
  margin: 0 4px;
}

/* 顶部操作提示栏 */
.active-tool-hint {
  position: absolute;
  top: 76px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(15, 23, 42, 0.76);
  color: #fff;
  font-size: 11px;
  font-weight: 500;
  padding: 6px 14px;
  border-radius: 999px;
  z-index: 50;
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
```

- [ ] **Step 2: 在 `Canvas.jsx` 中新增工具栏 UI 与 `activeTool` 状态控制**

在 `Canvas` 组件内部注入 `activeTool` 状态，并渲染工具栏：

```javascript
  const [activeTool, setActiveTool] = useState('select'); // select | card | connector | text
```

在返回的 JSX 根部渲染工具栏和模式提示：

```jsx
      {/* 顶部操作提示 */}
      {activeTool !== 'select' && (
        <div className="active-tool-hint">
          {activeTool === 'card' && '卡片工具激活：点击画布空白处以添加新卡片'}
          {activeTool === 'connector' && '连接线工具激活：拖动卡片边缘锚点以建立关联'}
          {activeTool === 'text' && '文本工具激活：点击画布空白处添加注释文本'}
        </div>
      )}

      {/* 底部悬浮工具栏 */}
      <div className="figma-toolbar" onClick={(e) => e.stopPropagation()}>
        <button
          className={`figma-toolbar-btn${activeTool === 'select' ? ' active' : ''}`}
          title="选择与拖拽 (V)"
          onClick={() => setActiveTool('select')}
        >
          <MousePointer size={16} />
        </button>
        <button
          className={`figma-toolbar-btn${activeTool === 'card' ? ' active' : ''}`}
          title="添加卡片 (C)"
          onClick={() => setActiveTool('card')}
        >
          <Square size={16} />
        </button>
        <button
          className={`figma-toolbar-btn${activeTool === 'connector' ? ' active' : ''}`}
          title="连接线工具 (L)"
          onClick={() => setActiveTool('connector')}
        >
          <MoveUpRight size={16} />
        </button>
        <button
          className={`figma-toolbar-btn${activeTool === 'text' ? ' active' : ''}`}
          title="注释文本 (T)"
          onClick={() => setActiveTool('text')}
        >
          <Type size={16} />
        </button>
        
        <div className="figma-toolbar-divider" />
        
        <button
          className="figma-toolbar-btn"
          title="一键整理布局"
          onClick={() => {
            handleAutoLayout();
            setActiveTool('select');
          }}
        >
          <Sparkles size={16} />
        </button>
      </div>
```

在 `Canvas` 容器 div 上动态映射 `cursor` 样式类或 style：

```javascript
      style={{
        backgroundPosition: `${transform.x}px ${transform.y}px`,
        backgroundSize: `${24 * transform.scale}px ${24 * transform.scale}px`,
        cursor: activeTool === 'select' 
          ? (isDragging.current ? 'grabbing' : 'grab') 
          : (activeTool === 'text' ? 'text' : 'crosshair')
      }}
```

- [ ] **Step 3: 频繁提交**

```bash
git add frontend/src/pages/Workspace/Canvas.jsx frontend/src/pages/Workspace/Canvas.css
git commit -m "feat: add bottom Figma悬浮工具栏 with state machine tool mapping"
```

---

### Task 4: 新建与删除卡片的自由交互支持

**Files:**
* Modify: `frontend/src/pages/Workspace/Canvas.jsx`
* Modify: `frontend/src/pages/Workspace/Canvas.css`

- [ ] **Step 1: 在 `Canvas.css` 中添加添加卡片表单气泡与删除按钮的 CSS**

```css
/* 新建卡片悬浮表单 */
.floating-card-creator {
  position: absolute;
  width: 320px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(16px);
  border: 1px solid var(--border-strong);
  border-radius: 16px;
  padding: 16px;
  z-index: 1200;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.floating-card-creator input,
.floating-card-creator textarea,
.floating-card-creator select {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
  outline: none;
  background: #fff;
  box-sizing: border-box;
}

.floating-card-creator .btn-row {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.floating-card-creator button {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
}

.floating-card-creator button.cancel {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-secondary);
}

.floating-card-creator button.save {
  background: #007aff;
  border: none;
  color: #fff;
}

/* 卡片右上角手动删除按钮 */
.card-delete-hover-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: #ef4444;
  display: none;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
  transition: all 0.2s;
}

.canvas-card:hover .card-delete-hover-btn {
  display: flex;
}

.card-delete-hover-btn:hover {
  background: #ef4444;
  color: white;
  transform: scale(1.15);
}
```

- [ ] **Step 2: 实现卡片点击定位算法与创建气泡状态**

在 `Canvas.jsx` 中声明创建框状态：

```javascript
  const [creatorState, setCreatorState] = useState(null); // { x, y, canvasX, canvasY, stage }
```

改写 `handlePointerDown` 的点击判定，当 `activeTool === 'card'` 时，计算相对绝对坐标并唤起气泡，拦截拖拽：

```javascript
    if (activeTool === 'card') {
      event.stopPropagation();
      const rect = containerRef.current.getBoundingClientRect();
      const clientX = event.clientX;
      const clientY = event.clientY;
      const canvasX = (clientX - rect.left - transform.x) / transform.scale;
      const canvasY = (clientY - rect.top - transform.y) / transform.scale;
      
      // 判断落入哪个横向阶段（证据/发现，规则/定义，迭代规划/交接）
      let stage = 'discovery';
      if (canvasX > 400 && canvasX < 850) stage = 'define';
      else if (canvasX >= 850) stage = 'handoff';

      setCreatorState({
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
        canvasX,
        canvasY,
        stage
      });
      return;
    }
```

- [ ] **Step 3: 编写气泡表单提交逻辑与本地 state 合并**

```jsx
  const handleCreateCardSubmit = async (formData) => {
    if (!formData.title) return;
    const { title, desc, kind, stage } = formData;
    setCreatorState(null);
    setActiveTool('select');

    // 映射前端卡片类型至后端
    let backendKind = 'evidence';
    if (kind === 'problems') backendKind = 'problem';
    else if (kind === 'clarify') backendKind = 'clarification';
    else if (kind === 'rules') backendKind = 'constraint';
    else if (kind === 'options') backendKind = 'decision';
    else if (kind === 'planning') backendKind = 'handoff';

    const tempId = `temp-${Date.now()}`;
    const newLocalCard = {
      id: tempId,
      kind: backendKind,
      title,
      desc,
      tags: [],
      status: 'open',
      structuredItems: [],
      next: []
    };

    // 预合并到本地 state 以获得极致的无感延迟体验
    setCanvasSections(prev => ({
      ...prev,
      [kind]: [...(prev[kind] || []), newLocalCard]
    }));
    
    // 设置其 offset 位置使中心落入点击位置
    setCardOffsets(prev => ({
      ...prev,
      [tempId]: { x: creatorState.canvasX - 160, y: creatorState.canvasY - 80 }
    }));

    if (workspaceId && workspaceId !== 'demo') {
      try {
        const res = await apiPost(`/api/canvas/workspaces/${workspaceId}/cards`, {
          kind: backendKind,
          title,
          summary: desc,
          stage: mapSectionToBackendStage(kind)
        });
        if (res && res.card_id) {
          // 将临时 ID 换回真实后端 ID 并刷新
          setCardOffsets(prev => {
            const next = { ...prev };
            next[res.card_id] = next[tempId];
            delete next[tempId];
            return next;
          });
        }
        if (onRefresh) onRefresh();
      } catch (err) {
        console.error("创建卡片失败", err);
      }
    }
  };
```

在 JSX 中渲染气泡（当 `creatorState` 不为空时）：

```jsx
      {creatorState && (
        <CardCreatorBubble 
          x={creatorState.x} 
          y={creatorState.y} 
          stage={creatorState.stage}
          onClose={() => setCreatorState(null)} 
          onSubmit={handleCreateCardSubmit} 
        />
      )}
```

`CardCreatorBubble` 的最小组件实现：
```jsx
function CardCreatorBubble({ x, y, stage, onClose, onSubmit }) {
  const [title, setTitle] = useState('');
  const [desc, setDesc] = useState('');
  // 决定初始映射的 section
  const [kind, setKind] = useState(() => {
    if (stage === 'define') return 'problems';
    if (stage === 'handoff') return 'planning';
    return 'evidence';
  });

  return (
    <div className="floating-card-creator" style={{ left: x + 10, top: y + 10 }}>
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>添加新画布元素</div>
      <input 
        placeholder="输入卡片标题..." 
        value={title} 
        onChange={e => setTitle(e.target.value)} 
        autoFocus
      />
      <textarea 
        placeholder="输入一句话摘要说明..." 
        value={desc} 
        onChange={e => setDesc(e.target.value)} 
        rows={3}
      />
      <select value={kind} onChange={e => setKind(e.target.value)}>
        <option value="evidence">发现 ➔ 证据</option>
        <option value="problems">定义 ➔ 问题定义</option>
        <option value="clarify">定义 ➔ 待澄清问题</option>
        <option value="rules">定义 ➔ 规则与约束</option>
        <option value="options">定义 ➔ 待决策项</option>
        <option value="planning">交付 ➔ 结构化交接物</option>
      </select>
      <div className="btn-row">
        <button className="cancel" onClick={onClose}>取消</button>
        <button className="save" onClick={() => onSubmit({ title, desc, kind })}>创建</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 添加卡片删除交互实现**

在 `CanvasCard` 的头部或者右上角挂载删除 `x` 圆圈按钮：

```jsx
      {/* 隐藏的删除按钮 */}
      <button 
        className="card-delete-hover-btn" 
        title="删除此卡片"
        onClick={(event) => {
          event.stopPropagation();
          onDeleteCard(data.id);
        }}
      >
        <X size={12} />
      </button>
```

在 `Canvas` 组件内部提供 `handleDeleteCard`：

```javascript
  const handleDeleteCard = async (cardId) => {
    if (!window.confirm("确定要删除这张卡片吗？相关的连线关系也会一并断开。")) return;
    
    // 本地过滤以保障流畅度
    setCanvasSections(prev => {
      const next = { ...prev };
      Object.keys(next).forEach(key => {
        next[key] = next[key].filter(c => c.id !== cardId);
      });
      return next;
    });

    if (workspaceId && workspaceId !== 'demo') {
      try {
        await apiDelete(`/api/canvas/workspaces/${workspaceId}/cards/${cardId}`);
        if (onRefresh) onRefresh();
      } catch (err) {
        console.error("删除卡片失败", err);
      }
    }
  };
```

- [ ] **Step 5: 频繁提交**

```bash
git add frontend/src/pages/Workspace/Canvas.jsx frontend/src/pages/Workspace/Canvas.css
git commit -m "feat: implement manually adding cards via pointer inverse matrix and hover-to-delete cards"
```

---

### Task 5: 连接线拖拽创建与连线删除

**Files:**
* Modify: `frontend/src/pages/Workspace/Canvas.jsx`
* Modify: `frontend/src/pages/Workspace/Canvas.css`

- [ ] **Step 1: 在 `Canvas.css` 中添加连线锚点与高亮连线的 CSS**

```css
/* 连接锚点 */
.connector-dot {
  position: absolute;
  width: 10px;
  height: 10px;
  background: rgba(0, 122, 255, 0.4);
  border: 2px solid white;
  border-radius: 50%;
  z-index: 30;
  display: none;
  cursor: crosshair;
  transition: transform 0.2s, background-color 0.2s;
  box-shadow: 0 1px 4px rgba(0,0,0,0.2);
}

.canvas-card-slot:hover .connector-dot {
  display: block;
}

.connector-dot:hover {
  transform: scale(1.4);
  background: #007aff;
}

/* 四个边缘位置 */
.connector-dot.top { top: -5px; left: 50%; transform: translateX(-50%); }
.connector-dot.bottom { bottom: -5px; left: 50%; transform: translateX(-50%); }
.connector-dot.left { left: -5px; top: 50%; transform: translateY(-50%); }
.connector-dot.right { right: -5px; top: 50%; transform: translateY(-50%); }

/* 连线删除弹出框与中点删除按钮 */
.arrow-delete-badge {
  position: absolute;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #ef4444;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.35);
  font-size: 10px;
  font-weight: bold;
  z-index: 10;
  transform: translate(-50%, -50%);
  pointer-events: auto;
  transition: transform 0.2s;
}

.arrow-delete-badge:hover {
  transform: translate(-50%, -50%) scale(1.25);
}
```

- [ ] **Step 2: 添加连线锚点渲染与拖拽事件拦截**

在 `CanvasCard` 的包裹槽 `canvas-card-slot` 内挂载 4 个 `connector-dot`：

```jsx
      {activeTool === 'connector' && (
        <>
          <div className="connector-dot top" onPointerDown={e => onStartConnectorDrag(data.id, 'top', e)} />
          <div className="connector-dot bottom" onPointerDown={e => onStartConnectorDrag(data.id, 'bottom', e)} />
          <div className="connector-dot left" onPointerDown={e => onStartConnectorDrag(data.id, 'left', e)} />
          <div className="connector-dot right" onPointerDown={e => onStartConnectorDrag(data.id, 'right', e)} />
        </>
      )}
```

在 `Canvas.jsx` 组件内引入 `tempLine` 并在 pointermove 时绘制虚线：

```javascript
  const [tempLine, setTempLine] = useState(null); // { startCardId, startX, startY, currentX, currentY }
```

- [ ] **Step 3: 连线松手检测与建立关系 API 触发**

在 `Canvas` 中渲染临时线，并在全局指针松开时判定是否命中其他卡片：

```javascript
  const handleConnectorPointerUp = async (event) => {
    if (!tempLine) return;
    const endElement = document.elementFromPoint(event.clientX, event.clientY);
    let targetCard = endElement?.closest('.canvas-card');
    
    if (targetCard && targetCard.id !== tempLine.startCardId) {
      const kind = window.prompt("选择关系类型 (输入对应序号):\n1. derived_from (来源于)\n2. clarifies (澄清了)\n3. supports (支持)\n4. blocks (阻塞)\n5. conflicts_with (冲突于)\n6. produces (产出为)");
      const kindsMap = {
        '1': 'derived_from', '2': 'clarifies', '3': 'supports', 
        '4': 'blocks', '5': 'conflicts_with', '6': 'produces'
      };
      const chosenKind = kindsMap[kind] || 'derived_from';

      if (workspaceId && workspaceId !== 'demo') {
        try {
          await apiPost(`/api/canvas/workspaces/${workspaceId}/relations`, {
            kind: chosenKind,
            from_card_id: tempLine.startCardId,
            to_card_id: targetCard.id
          });
          if (onRefresh) onRefresh();
        } catch (err) {
          console.error("创建连线失败", err);
        }
      } else {
        // Demo 模式下直接本地追加
        setCanvasSections(prev => {
          const next = { ...prev };
          const allCards = Object.values(next).flat();
          const source = allCards.find(c => c.id === tempLine.startCardId);
          if (source) {
            source.next = [...(source.next || []), targetCard.id];
          }
          return next;
        });
      }
    }
    setTempLine(null);
  };
```

- [ ] **Step 4: 渲染连线中点的删除气泡与删除功能**

在 `CustomArrow` SVG 绘制完毕后，根据几何中点渲染红色删除气泡：
* 计算中点：`midPointX = midX` (贝塞尔控制点中点), `midPointY = (startY + endY) / 2`。
* 在 SVG 后面或内部挂载中点删除气泡。当选中此连线时，展示它。
* 按下或点击它时，调用 `apiDelete("/api/canvas/workspaces/{workspaceId}/relations", { params: { from_card_id, to_card_id } })`。

- [ ] **Step 5: 频繁提交**

```bash
git add frontend/src/pages/Workspace/Canvas.jsx frontend/src/pages/Workspace/Canvas.css
git commit -m "feat: implement connector dynamic drag-to-line creation and arrow midpoint delete badge"
```

---

### Task 6: 文本标签与时间轴拖拽优化

**Files:**
* Modify: `frontend/src/pages/Workspace/Canvas.jsx`
* Modify: `frontend/src/pages/Workspace/Canvas.css`

- [ ] **Step 1: 实现普通文本标注 `Text` 模式落子与双击修改**

当 `activeTool === 'text'` 时，点击空白位置：
* 前端追加一个独立文本：`{ id, text: '点击输入文本', x, y }`。
* 并在 `Canvas.jsx` 内用绝对定位漂浮渲染文本，双击可编辑。

- [ ] **Step 2: 时间轴组件改为默认收起、非固定拖拽卡片**

修改 `Canvas.jsx` 中 `isPinned` 的默认初始值为 `false`。
修改 `TimelineScrubber` 中 `isCollapsed` 默认值为 `true`。
将时间轴默认位置 `timelinePos` 初始化为 `{ x: 80, y: 760 }`（避开中心，放在左下角）。

- [ ] **Step 3: 频繁提交**

```bash
git add frontend/src/pages/Workspace/Canvas.jsx
git commit -m "feat: add text tool support and optimize TimelineScrubber to collapsible drag components"
```

---

### Task 7: 编译与手动集成测试验证

- [ ] **Step 1: 编译前端构建包**

Run: `npm --prefix frontend run build`
Expected: 编译无任何 React / Syntax / ESM 规范报错，显示成功。

- [ ] **Step 2: 启动本地联调验证**

同时启动后端和前端进行手动集成测试，双击修改关系、手动拉线并刷新，验证在绝对定位上添加不同属性的卡片无任何错位。
```bash
python3 -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000 --reload
VITE_API_BASE=http://127.0.0.1:8000 npm --prefix frontend run dev
```

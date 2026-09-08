# Recent Projects History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Figma-like "最近项目" entry for EvoCanvas so users can reopen prior workspaces after refresh or later visits.

**Architecture:** Extend the existing canvas workspace persistence model with a lightweight recent-projects listing endpoint derived from `workspace.json`, then add a dedicated frontend recent-projects route and wire the sidebar clock icon to it. The recent-projects cards reuse existing workspace metadata and handoff status, while keeping cover rendering intentionally simple with a placeholder preview instead of real thumbnails.

**Tech Stack:** FastAPI, Python unittest, React 19, React Router, existing `api.js` fetch helpers, CSS modules already used by layout/pages.

---

## File Structure

- Modify: `app/canvas/domain/workspace.py`
  - Add metadata fields needed to rank and summarize recent projects (`created_at`, `updated_at`, optional lightweight preview metadata) while preserving backwards compatibility for older workspace JSON files.
- Modify: `app/canvas/repository.py`
  - Add a repository method that scans persisted workspaces and returns recent workspace records sorted by `updated_at` descending.
- Modify: `app/canvas/service.py`
  - Keep workspace timestamps fresh when a workspace is created or mutated and expose a service-level `list_recent_workspaces()` transformer for the API.
- Modify: `app/api/server.py`
  - Add `GET /api/canvas/workspaces` for recent-project listing.
- Modify: `tests/test_canvas_api.py`
  - Add API-level regression coverage for the new recent-projects endpoint and sort order.
- Modify: `tests/test_canvas_repository.py`
  - Add repository-level coverage for workspace listing and timestamp sorting.
- Modify: `frontend/src/App.jsx`
  - Register a new `/recent` route.
- Modify: `frontend/src/components/layout/Sidebar.jsx`
  - Replace the dead clock button with a real navigation entry to `/recent` and update labels/comments to match EvoCanvas recent-project semantics.
- Create: `frontend/src/pages/RecentProjects/index.jsx`
  - Fetch and render recent workspaces as a clean grid of cards.
- Create: `frontend/src/pages/RecentProjects/recentProjects.css`
  - Provide the lightweight Figma-like visual treatment for the grid/cards/empty state.
- Create: `frontend/src/pages/RecentProjects/recentProjectsView.js`
  - Pure helpers for formatting time/status/preview text so they can be tested without a DOM runner.
- Create: `frontend/src/pages/RecentProjects/recentProjectsView.test.js`
  - Cover helper behavior and empty/default formatting rules.

### Task 1: Add recent-workspace metadata and repository listing

**Files:**
- Modify: `app/canvas/domain/workspace.py`
- Modify: `app/canvas/repository.py`
- Test: `tests/test_canvas_repository.py`

- [ ] **Step 1: Write the failing repository test**

```python
# tests/test_canvas_repository.py

def test_list_workspaces_returns_recent_first(self) -> None:
    workspace_a = CanvasWorkspace(
        workspace_id="ws_old",
        title="较早项目",
        created_at="2026-06-10T10:00:00Z",
        updated_at="2026-06-10T12:00:00Z",
    )
    workspace_b = CanvasWorkspace(
        workspace_id="ws_new",
        title="最近项目",
        created_at="2026-06-11T10:00:00Z",
        updated_at="2026-06-12T09:30:00Z",
    )

    self.repository.save_workspace(workspace_a)
    self.repository.save_workspace(workspace_b)

    items = self.repository.list_workspaces()

    self.assertEqual([item.workspace_id for item in items], ["ws_new", "ws_old"])
    self.assertEqual(items[0].title, "最近项目")
    self.assertEqual(items[0].updated_at, "2026-06-12T09:30:00Z")
```

- [ ] **Step 2: Run the repository test to verify it fails**

Run: `python3 -m unittest tests.test_canvas_repository.CanvasRepositoryTests.test_list_workspaces_returns_recent_first`
Expected: FAIL with `AttributeError` because `CanvasRepository.list_workspaces` and/or workspace timestamp fields do not exist yet.

- [ ] **Step 3: Extend the workspace domain object with timestamp fields**

```python
# app/canvas/domain/workspace.py
@dataclass
class CanvasWorkspace:
    workspace_id: str
    title: str
    objective: str = ""
    active_snapshot_id: str = ""
    active_turn_id: str = ""
    active_turn_status: str = "idle"
    active_turn_started_at: str = ""
    handoff_status: str = "not_ready"
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    handoff_metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasWorkspace":
        return cls(
            workspace_id=data["workspace_id"],
            title=data.get("title", ""),
            objective=data.get("objective", ""),
            active_snapshot_id=data.get("active_snapshot_id", ""),
            active_turn_id=data.get("active_turn_id", ""),
            active_turn_status=data.get("active_turn_status", "idle"),
            active_turn_started_at=data.get("active_turn_started_at", ""),
            handoff_status=data.get("handoff_status", "not_ready"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", data.get("created_at", "")),
            metadata=dict(data.get("metadata", {})),
            handoff_metadata=dict(data.get("handoff_metadata", {})),
        )
```

- [ ] **Step 4: Add repository support for scanning and sorting workspaces**

```python
# app/canvas/repository.py
    def list_workspaces(self) -> list[CanvasWorkspace]:
        """列出所有已持久化工作区，并按最近更新时间倒序返回。"""

        workspaces_dir = self.storage.canvas_root() / "workspaces"
        if not workspaces_dir.exists():
            return []

        workspaces: list[CanvasWorkspace] = []
        for path in sorted(workspaces_dir.glob("*/workspace.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            workspaces.append(CanvasWorkspace.from_dict(payload))

        return sorted(
            workspaces,
            key=lambda item: (item.updated_at or item.created_at or "", item.workspace_id),
            reverse=True,
        )
```

- [ ] **Step 5: Re-run the repository test to verify it passes**

Run: `python3 -m unittest tests.test_canvas_repository.CanvasRepositoryTests.test_list_workspaces_returns_recent_first`
Expected: PASS

- [ ] **Step 6: Commit the repository/domain slice**

```bash
git add tests/test_canvas_repository.py app/canvas/domain/workspace.py app/canvas/repository.py
git commit -m "feat: add recent canvas workspace listing"
```

### Task 2: Expose recent projects through the canvas API and keep timestamps fresh

**Files:**
- Modify: `app/canvas/service.py`
- Modify: `app/api/server.py`
- Test: `tests/test_canvas_api.py`

- [ ] **Step 1: Write the failing API test for recent projects**

```python
# tests/test_canvas_api.py

def test_list_recent_canvas_workspaces(self) -> None:
    first = self.client.post(
        "/api/canvas/workspaces/ws_alpha/messages",
        json={
            "message": "先整理会员体系背景",
            "selected_card_ids": [],
            "material_ids": [],
            "mode": "default",
        },
        headers=self.headers,
    )
    self.assertEqual(first.status_code, 200)

    second = self.client.post(
        "/api/canvas/workspaces/ws_beta/messages",
        json={
            "message": "补充履约约束和待决策",
            "selected_card_ids": [],
            "material_ids": [],
            "mode": "default",
        },
        headers=self.headers,
    )
    self.assertEqual(second.status_code, 200)

    response = self.client.get("/api/canvas/workspaces", headers=self.headers)

    self.assertEqual(response.status_code, 200)
    payload = response.json()
    self.assertEqual(payload["items"][0]["workspace_id"], "ws_beta")
    self.assertIn("title", payload["items"][0])
    self.assertIn("updated_at", payload["items"][0])
    self.assertIn("summary_preview", payload["items"][0])
```

- [ ] **Step 2: Run the API test to verify it fails**

Run: `python3 -m unittest tests.test_canvas_api.CanvasApiTests.test_list_recent_canvas_workspaces`
Expected: FAIL with `404` for `GET /api/canvas/workspaces`.

- [ ] **Step 3: Add service serialization for recent workspaces and timestamp touching**

```python
# app/canvas/service.py
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class CanvasService:
    def list_recent_workspaces(self, limit: int = 24) -> Dict[str, Any]:
        workspaces = self.repository.list_workspaces()[:limit]
        items = []
        for workspace in workspaces:
            handoff = self.repository.load_handoff(workspace.workspace_id)
            items.append(
                {
                    "workspace_id": workspace.workspace_id,
                    "title": workspace.title or "未命名项目",
                    "updated_at": workspace.updated_at or workspace.created_at,
                    "created_at": workspace.created_at,
                    "handoff_status": workspace.handoff_status or "not_ready",
                    "summary_preview": (handoff.summary or workspace.objective or "继续补充这张产品工作画布。")[:140],
                    "cover_mode": "placeholder",
                }
            )
        return {"items": items}

    def get_workspace(self, workspace_id: str) -> CanvasWorkspace:
        workspace = self.repository.load_workspace(workspace_id)
        if workspace is not None:
            return workspace
        now = utc_now_iso()
        workspace = CanvasWorkspace(
            workspace_id=workspace_id,
            title=f"EvoCanvas Workspace {workspace_id}",
            created_at=now,
            updated_at=now,
        )
        self.repository.save_workspace(workspace)
        return workspace
```

- [ ] **Step 4: Touch `updated_at` anywhere workspace state is persisted**

```python
# app/canvas/service.py
    def _touch_workspace(self, workspace: CanvasWorkspace) -> CanvasWorkspace:
        now = utc_now_iso()
        if not workspace.created_at:
            workspace.created_at = now
        workspace.updated_at = now
        self.repository.save_workspace(workspace)
        return workspace
```

Apply `_touch_workspace(workspace)` in the existing write paths that already save the workspace, especially:

```python
# app/canvas/service.py
self._touch_workspace(workspace)
```

Use it in:
- `get_workspace()` after creating a new workspace
- `_apply_proposal()` after cards/relations/handoff/snapshot mutations land
- `create_snapshot()` after `active_snapshot_id` changes
- `refresh_handoff()` after handoff metadata changes
- `patch_card()` and `move_card()` after workspace-level changes
- `approve_confirmation()` / `reject_confirmation()` when a turn changes persisted state

- [ ] **Step 5: Add the recent-projects API route**

```python
# app/api/server.py
    @app.get("/api/canvas/workspaces")
    async def list_canvas_workspaces(
        canvas_service: CanvasService = Depends(get_canvas_service),
    ) -> Dict[str, Any]:
        return canvas_service.list_recent_workspaces()
```

- [ ] **Step 6: Re-run the API test to verify it passes**

Run: `python3 -m unittest tests.test_canvas_api.CanvasApiTests.test_list_recent_canvas_workspaces`
Expected: PASS

- [ ] **Step 7: Run the broader canvas API regression slice**

Run: `python3 -m unittest tests.test_canvas_api tests.test_canvas_repository -v`
Expected: PASS across the updated canvas endpoint and repository suites.

- [ ] **Step 8: Commit the API/service slice**

```bash
git add app/canvas/service.py app/api/server.py tests/test_canvas_api.py tests/test_canvas_repository.py
git commit -m "feat: expose recent canvas projects"
```

### Task 3: Add pure frontend view helpers for recent-project cards

**Files:**
- Create: `frontend/src/pages/RecentProjects/recentProjectsView.js`
- Create: `frontend/src/pages/RecentProjects/recentProjectsView.test.js`

- [ ] **Step 1: Write the failing helper test**

```javascript
// frontend/src/pages/RecentProjects/recentProjectsView.test.js
import { buildRecentProjectCard, formatRelativeUpdateLabel } from './recentProjectsView';

test('buildRecentProjectCard fills safe defaults for untitled projects', () => {
  const card = buildRecentProjectCard({
    workspace_id: 'ws_123',
    title: '',
    updated_at: '',
    handoff_status: 'not_ready',
    summary_preview: '',
  });

  expect(card.title).toBe('未命名项目');
  expect(card.summary).toBe('继续补充这张产品工作画布。');
  expect(card.statusLabel).toBe('待收敛');
});

test('formatRelativeUpdateLabel returns recently edited copy for fresh timestamps', () => {
  expect(formatRelativeUpdateLabel('2026-06-14T09:00:00Z', new Date('2026-06-14T09:20:00Z'))).toBe('编辑于 20 分钟前');
});
```

- [ ] **Step 2: Run the helper test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/RecentProjects/recentProjectsView.test.js`
Expected: FAIL because the helper file does not exist yet.

- [ ] **Step 3: Create minimal view-formatting helpers**

```javascript
// frontend/src/pages/RecentProjects/recentProjectsView.js
const STATUS_LABELS = {
  confirmed: '已确认交接',
  draft: '交接草稿',
  not_ready: '待收敛',
};

export function formatRelativeUpdateLabel(isoValue, now = new Date()) {
  if (!isoValue) return '尚未编辑';
  const updatedAt = new Date(isoValue);
  const diffMinutes = Math.max(0, Math.floor((now.getTime() - updatedAt.getTime()) / 60000));
  if (diffMinutes < 60) return `编辑于 ${diffMinutes || 1} 分钟前`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `编辑于 ${diffHours} 小时前`;
  const diffDays = Math.floor(diffHours / 24);
  return `编辑于 ${diffDays} 天前`;
}

export function buildRecentProjectCard(item, now = new Date()) {
  return {
    workspaceId: item.workspace_id,
    title: item.title || '未命名项目',
    summary: item.summary_preview || '继续补充这张产品工作画布。',
    updatedLabel: formatRelativeUpdateLabel(item.updated_at, now),
    statusLabel: STATUS_LABELS[item.handoff_status] || '继续推进',
    coverMode: item.cover_mode || 'placeholder',
  };
}
```

- [ ] **Step 4: Re-run the helper test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/RecentProjects/recentProjectsView.test.js`
Expected: PASS

- [ ] **Step 5: Commit the helper slice**

```bash
git add frontend/src/pages/RecentProjects/recentProjectsView.js frontend/src/pages/RecentProjects/recentProjectsView.test.js
git commit -m "test: add recent project card formatters"
```

### Task 4: Build the recent-projects page and sidebar navigation

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/layout/Sidebar.jsx`
- Create: `frontend/src/pages/RecentProjects/index.jsx`
- Create: `frontend/src/pages/RecentProjects/recentProjects.css`
- Optionally Modify: `frontend/src/components/layout/sidebar.css`
- Test: `frontend/src/pages/RecentProjects/recentProjectsView.test.js`

- [ ] **Step 1: Create the recent-projects page component**

```jsx
// frontend/src/pages/RecentProjects/index.jsx
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FolderOpen, ArrowRight } from 'lucide-react';
import { apiGet } from '../../api';
import { buildRecentProjectCard } from './recentProjectsView';
import './recentProjects.css';

export default function RecentProjects() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    let closed = false;
    apiGet('/api/canvas/workspaces', { items: [] }).then((payload) => {
      if (closed) return;
      const mapped = (payload?.items || []).map((item) => buildRecentProjectCard(item));
      setItems(mapped);
    });
    return () => {
      closed = true;
    };
  }, []);

  return (
    <section className="recent-projects-page">
      <header className="recent-projects-header">
        <div>
          <p className="recent-projects-eyebrow">EvoCanvas</p>
          <h1>最近项目</h1>
          <p className="recent-projects-subtitle">回到最近推进过的产品工作画布，继续收敛问题、约束和交接物。</p>
        </div>
      </header>

      {items.length === 0 ? (
        <div className="recent-projects-empty">
          <FolderOpen size={28} />
          <h2>还没有最近项目</h2>
          <p>从首页发起一次输入编译后，这里会显示你最近编辑过的 EvoCanvas 工作区。</p>
          <Link to="/" className="recent-projects-empty-cta">去新建项目 <ArrowRight size={16} /></Link>
        </div>
      ) : (
        <div className="recent-projects-grid">
          {items.map((item) => (
            <Link key={item.workspaceId} to={`/workspace/${item.workspaceId}`} className="recent-project-card">
              <div className="recent-project-cover">
                <span className="recent-project-badge">{item.statusLabel}</span>
              </div>
              <div className="recent-project-body">
                <h2>{item.title}</h2>
                <p>{item.summary}</p>
                <span>{item.updatedLabel}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Add the route and wire the sidebar clock entry**

```jsx
// frontend/src/App.jsx
import RecentProjects from './pages/RecentProjects';

<Route path="/recent" element={<W title="最近项目"><RecentProjects /></W>} />
```

```jsx
// frontend/src/components/layout/Sidebar.jsx
<NavLink to="/recent" className={({ isActive }) => `dock-item${isActive ? ' active' : ''}`} title="Recent Projects">
  <Clock size={20} strokeWidth={2} />
</NavLink>
```

- [ ] **Step 3: Add the lightweight Figma-like grid styling**

```css
/* frontend/src/pages/RecentProjects/recentProjects.css */
.recent-projects-page {
  padding: 32px 36px 56px;
  min-height: 100%;
  background:
    radial-gradient(circle at top left, rgba(246, 241, 229, 0.88), transparent 28%),
    linear-gradient(180deg, #fbfaf6 0%, #f4f1e8 100%);
}

.recent-projects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 28px;
}

.recent-project-card {
  display: flex;
  flex-direction: column;
  min-height: 280px;
  border-radius: 24px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(23, 29, 45, 0.08);
  box-shadow: 0 16px 32px rgba(29, 35, 52, 0.08);
  text-decoration: none;
  color: inherit;
  transition: transform 160ms ease, box-shadow 160ms ease;
}

.recent-project-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 22px 40px rgba(29, 35, 52, 0.12);
}
```

- [ ] **Step 4: Run frontend build verification**

Run: `npm --prefix frontend run build`
Expected: PASS with the new route/page included in the production bundle.

- [ ] **Step 5: Run the targeted backend regression and frontend helper test together**

Run: `python3 -m unittest tests.test_canvas_api tests.test_canvas_repository -v && cd frontend && npx vitest run src/pages/RecentProjects/recentProjectsView.test.js`
Expected: PASS

- [ ] **Step 6: Commit the UI slice**

```bash
git add frontend/src/App.jsx frontend/src/components/layout/Sidebar.jsx frontend/src/pages/RecentProjects
git commit -m "feat: add recent projects workspace view"
```

## Self-Review

- Spec coverage: the plan covers the chosen solution 2 (backend recent-project listing + frontend recent-project page + sidebar clock navigation). It intentionally excludes shared tabs and real thumbnails, which the user explicitly deferred.
- Placeholder scan: no `TODO` / `TBD` placeholders remain; each task contains concrete files, code, and commands.
- Type consistency: the plan consistently uses `created_at`, `updated_at`, `summary_preview`, `cover_mode`, `/api/canvas/workspaces`, and `/recent` across backend and frontend tasks.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-14-recent-projects-history.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

# L3 Runtime Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 EvoCanvas L3 的包版本、状态账本和确认记录成为运行时唯一事实来源，并移除旧审批队列与独立画布文件的生效路径。

**Architecture:** 由 `CanvasService` 在每次结构化提交时把画布投影组装成新的 `PackageVersion`；`CanvasRepository` 以工作区锁、不可变版本文件、原子账本重写和包根指针更新完成一次提交。卡片和关系的旧 JSON 文件只用于首读迁移，确认在普通 Chat 回合中形成 `ConfirmationRecord`，不再出现单独审批队列。

**Tech Stack:** Python 3、`unittest`、FastAPI、React/Vite。

---

### Task 1: 固化 L3 领域不变量与旧数据迁移

**Files:**
- Modify: `app/canvas/domain/object_status.py`
- Modify: `app/canvas/domain/cards.py`
- Modify: `app/canvas/domain/relations.py`
- Test: `tests/test_canvas_domain.py`

- [x] **Step 1: Write the failing domain tests**

```python
def test_rejects_invalid_typed_status_on_new_card(self):
    with self.assertRaises(ValueError):
        CanvasCard(card_id="c", kind=CanvasCardKind.CONSTRAINT, title="x", status="open")

def test_legacy_option_and_relation_are_migrated(self):
    card = CanvasCard.from_dict({"card_id": "c", "kind": "option", "title": "x", "status": "confirmed"})
    relation = CanvasRelation.from_dict({"relation_id": "r", "kind": "reopens", "from_card_id": "a", "to_card_id": "b"})
    self.assertEqual((card.kind.value, card.status, relation.kind.value), ("decision", "decided", "replaces"))
```

- [x] **Step 2: Run the domain tests and verify they fail**

Run: `python3 -m unittest tests.test_canvas_domain -v`

Expected: invalid `constraint/open` is accepted and legacy enum parsing raises `ValueError`.

- [x] **Step 3: Implement type-specific defaults, validation, and explicit legacy mappings**

```python
def default_status_for_kind(kind: str) -> str: ...
def normalize_legacy_card(kind: str, status: str) -> tuple[CanvasCardKind, str]: ...

def __post_init__(self) -> None:
    if not is_valid_status_for_kind(self.kind.value, self.status):
        raise ValueError(...)
```

- [x] **Step 4: Re-run the domain tests**

Run: `python3 -m unittest tests.test_canvas_domain -v`

Expected: PASS.

### Task 2: 实现不可变、带校验的包版本原子提交

**Files:**
- Modify: `app/canvas/repository.py`
- Test: `tests/test_canvas_repository.py`

- [x] **Step 1: Write the failing repository tests**

```python
def test_commit_version_is_immutable_and_ledger_is_idempotent(self):
    committed = repository.commit_package_version(...)
    self.assertEqual(committed.current_version, 1)
    self.assertEqual(len(repository.query_ledger_events("ws", operation_id="op-1")), 2)
    with self.assertRaises(FileExistsError):
        repository.save_package_version("ws", same_version_with_other_content)

def test_load_package_version_detects_checksum_tampering(self):
    repository.save_package_version("ws", version)
    version_file.write_text('{"package_id":"pkg", ...}', encoding="utf-8")
    with self.assertRaises(ValueError):
        repository.load_package_version("ws", "pkg", 1)
```

- [x] **Step 2: Run the repository tests and verify they fail**

Run: `python3 -m unittest tests.test_canvas_repository -v`

Expected: current version is overwritten and checksum tampering remains readable.

- [x] **Step 3: Implement transactional commit, checksum verification, and immutable records**

```python
def commit_package_version(self, workspace_id, package, version, events, confirmation=None):
    with self._workspace_lock(workspace_id):
        if self.has_operation_id(...):
            return self.load_package(...)
        self.save_package_version(...)
        self._rewrite_ledger_atomically(...)
        self.save_package(...)
        return package
```

- [x] **Step 4: Re-run the repository tests**

Run: `python3 -m unittest tests.test_canvas_repository -v`

Expected: PASS.

### Task 3: 将服务主链切换到包提交与普通 Chat 确认

**Files:**
- Modify: `app/canvas/service.py`
- Modify: `app/canvas/governance.py`
- Modify: `app/canvas/runtime_state.py`
- Modify: `app/canvas/repository.py`
- Test: `tests/test_canvas_turn_flow.py`
- Test: `tests/test_canvas_lifecycle.py`

- [x] **Step 1: Write the failing integration tests**

```python
def test_auto_applied_turn_creates_versioned_package_and_ledger(self):
    service.start_turn(...)
    package = service.repository.list_packages("demo")[0]
    self.assertEqual(package.current_version, 1)
    self.assertTrue(service.repository.query_ledger_events("demo", package_id=package.package_id))
    self.assertFalse((workspace_dir / "cards.json").exists())

def test_chat_confirmation_records_message_refs_without_queue(self):
    waiting = service.start_turn(...)
    applied = service.start_turn(..., message="我确认按这个决策执行")
    self.assertEqual(applied["action"], "applied_confirmation")
    self.assertEqual(len(service.repository.list_confirmation_records("demo")), 1)
```

- [x] **Step 2: Run the integration tests and verify they fail**

Run: `python3 -m unittest tests.test_canvas_turn_flow tests.test_canvas_lifecycle -v`

Expected: no package version/ledger is created and confirmations require queue approval.

- [x] **Step 3: Implement package projection and Chat confirmation reuse**

```python
def _commit_canvas_state(self, workspace, cards, relations, handoff, proposal, confirmation=None):
    package, version, events = self._build_package_commit(...)
    self.repository.commit_package_version(...)

if self._is_explicit_confirmation(message):
    return self._apply_pending_chat_confirmation(...)
```

- [x] **Step 4: Re-run the integration tests**

Run: `python3 -m unittest tests.test_canvas_turn_flow tests.test_canvas_lifecycle -v`

Expected: PASS.

### Task 4: 收紧 API 和前端到 L3 合同

**Files:**
- Modify: `app/api/canvas_schemas.py`
- Modify: `app/api/server.py`
- Modify: `frontend/src/pages/Workspace/index.jsx`
- Modify: `frontend/src/pages/Workspace/Canvas.jsx`
- Modify: `frontend/src/components/RecentProjects/RecentProjects.jsx` (if present)
- Test: `tests/test_canvas_api.py`

- [x] **Step 1: Write failing API tests**

```python
def test_card_patch_rejects_status_writes(self):
    response = self.client.patch("/api/canvas/workspaces/demo/cards/card-1", json={"status": "effective"})
    self.assertEqual(response.status_code, 422)
```

- [x] **Step 2: Run the API test and verify it fails**

Run: `python3 -m unittest tests.test_canvas_api -v`

Expected: endpoint accepts a second writable status channel.

- [x] **Step 3: Remove queue UI/API coupling and old stage payloads**

```python
class CanvasCardPatchRequest(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
```

The workspace shows `awaiting_chat_confirmation` as an AI message and does not fetch, list, or approve a confirmation queue.

- [x] **Step 4: Run the focused API test and frontend build**

Run: `python3 -m unittest tests.test_canvas_api -v && npm --prefix frontend run build`

Expected: API test PASS and Vite exits 0.

### Task 5: 全量验证与范围检查

**Files:**
- Verify: `app/**`, `tests/**`, `frontend/**`

- [x] **Step 1: Run the full canvas suite**

Run: `python3 -m unittest discover -s tests -p 'test_canvas*.py' -v`

Expected: PASS.

- [x] **Step 2: Run the frontend build**

Run: `npm --prefix frontend run build`

Expected: exit 0.

- [x] **Step 3: Inspect scope before a future commit**

Run: `git diff --check && git status --short`

Expected: no whitespace errors; only L3 runtime, tests, frontend contract, and this plan documentation are changed.

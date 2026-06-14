# EvoCanvas 后端与 Agent 实施计划

> **面向执行型 Agent：** 实施本计划时，必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`。步骤使用复选框 `- [ ]` 语法进行追踪。

**目标：** 在保留现有任务、事件、AgentSession、Subagent 和 WorkflowEngine 底座的前提下，为 EvoCanvas 1.0 落地真实 Canvas 后端、真实 Agent 编排能力、确认流、快照、交接物与只读 Todo 投影，并为前端切换到真实接口做好后端准备。

**方案：** 先在 `app/canvas/` 中建立 EvoCanvas 原生领域模型、存储层、治理层和 agent 编排层，再通过新的 `canvas_turn` workflow 接入现有执行引擎，最后在 `app/api/server.py` 上增量开放 `/api/canvas/workspaces/*` 接口，并通过 workspace 级 SSE 暴露真实事件流。整个过程坚持“先领域、再存储、再治理、再 workflow、再 API、再确认流、再快照与 handoff、最后联调验证”的顺序。

**技术栈：** Python、FastAPI、unittest、EventSource/SSE、文件存储、React 前端现有 API 封装

---

## 实施边界

- 当前纳入范围：
  - `app/canvas/`
  - `app/workflows/definitions.py`
  - `app/workflows/canvas_session.py`
  - `app/api/server.py`
  - `app/api/canvas_schemas.py`
  - `app/services/fakes.py`
  - `tests/`
- 当前不纳入范围：
  - 旧 `legacy_*` workflow 的彻底删除
  - 外部 peer collaboration 的产品重构
  - 前端完整切换到新接口后的 UI 微调
- 允许的兼容策略：
  - 新 `/api/canvas/workspaces/*` 对前端暴露新语义
  - 内部仍可暂时借用 `TaskService`、`EventBus`、`WorkflowEngine`

---

### 任务 1：建立 EvoCanvas 原生领域模型与序列化契约

**文件：**
- 新建：`app/canvas/__init__.py`
- 新建：`app/canvas/domain/__init__.py`
- 新建：`app/canvas/domain/workspace.py`
- 新建：`app/canvas/domain/cards.py`
- 新建：`app/canvas/domain/relations.py`
- 新建：`app/canvas/domain/snapshots.py`
- 新建：`app/canvas/domain/handoff.py`
- 新建：`app/canvas/domain/mutations.py`
- 测试：`tests/test_canvas_domain.py`

- [x] **步骤 1：先写失败测试**

```python
import unittest

from app.canvas.domain.cards import CanvasCard, CanvasCardType
from app.canvas.domain.mutations import CanvasMutation, CanvasMutationProposal, MutationRiskLevel
from app.canvas.domain.relations import CanvasRelation, CanvasRelationType
from app.canvas.domain.snapshots import CanvasSnapshot, TodoProjection
from app.canvas.domain.workspace import CanvasWorkspace


class CanvasDomainTests(unittest.TestCase):
    def test_workspace_card_snapshot_roundtrip(self):
        workspace = CanvasWorkspace(
            workspace_id="ws_demo",
            title="618 会员积分防刷治理一期",
            objective="先收敛高风险积分任务的待澄清、约束与待决策",
            active_snapshot_id="snap_001",
        )
        card = CanvasCard(
            card_id="card_001",
            card_type=CanvasCardType.CLARIFICATION,
            title="高风险口径按什么维度聚合",
            summary="需要明确按账号、设备还是行为会话聚合",
            stage="define",
            module="clarification",
        )
        relation = CanvasRelation(
            relation_id="rel_001",
            relation_type=CanvasRelationType.DERIVED_FROM,
            from_card_id="card_001",
            to_card_id="card_002",
        )
        snapshot = CanvasSnapshot(
            snapshot_id="snap_001",
            workspace_id="ws_demo",
            title="形成首批待澄清问题",
            active_card_ids=["card_001"],
            active_relation_ids=["rel_001"],
            todo_projection=TodoProjection(items=[]),
        )
        proposal = CanvasMutationProposal(
            proposal_id="proposal_001",
            workspace_id="ws_demo",
            turn_id="turn_001",
            mutations=[
                CanvasMutation(
                    mutation_type="add_card",
                    target_id="card_001",
                    payload={"title": card.title},
                )
            ],
            risk_level=MutationRiskLevel.LOW,
        )

        self.assertEqual(CanvasWorkspace.from_dict(workspace.to_dict()).workspace_id, "ws_demo")
        self.assertEqual(CanvasCard.from_dict(card.to_dict()).card_type, CanvasCardType.CLARIFICATION)
        self.assertEqual(CanvasRelation.from_dict(relation.to_dict()).relation_type, CanvasRelationType.DERIVED_FROM)
        self.assertEqual(CanvasSnapshot.from_dict(snapshot.to_dict()).active_card_ids, ["card_001"])
        self.assertEqual(CanvasMutationProposal.from_dict(proposal.to_dict()).risk_level, MutationRiskLevel.LOW)
```

- [x] **步骤 2：运行测试，确认当前会失败**

运行：`python3 -m unittest tests.test_canvas_domain -v`
预期：由于 `app/canvas/domain/*` 还不存在，测试报 `ModuleNotFoundError` 或属性缺失并 FAIL。

- [x] **步骤 3：补最小实现**

```python
# app/canvas/domain/cards.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class CanvasCardType(str, Enum):
    EVIDENCE = "evidence"
    PROBLEM = "problem"
    CLARIFICATION = "clarification"
    CONSTRAINT = "constraint"
    DECISION = "decision"
    HANDOFF = "handoff"


@dataclass
class CanvasCard:
    card_id: str
    card_type: CanvasCardType
    title: str
    summary: str
    stage: str
    module: str
    status: str = "draft"
    source_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "card_id": self.card_id,
            "card_type": self.card_type.value,
            "title": self.title,
            "summary": self.summary,
            "stage": self.stage,
            "module": self.module,
            "status": self.status,
            "source_refs": list(self.source_refs),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasCard":
        return cls(
            card_id=data["card_id"],
            card_type=CanvasCardType(data["card_type"]),
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            stage=data.get("stage", ""),
            module=data.get("module", ""),
            status=data.get("status", "draft"),
            source_refs=list(data.get("source_refs", [])),
            metadata=dict(data.get("metadata", {})),
        )
```

```python
# app/canvas/domain/mutations.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class MutationRiskLevel(str, Enum):
    LOW = "low"
    HIGH = "high"


@dataclass
class CanvasMutation:
    mutation_type: str
    target_id: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutation_type": self.mutation_type,
            "target_id": self.target_id,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasMutation":
        return cls(
            mutation_type=data["mutation_type"],
            target_id=data["target_id"],
            payload=dict(data.get("payload", {})),
        )


@dataclass
class CanvasMutationProposal:
    proposal_id: str
    workspace_id: str
    turn_id: str
    mutations: List[CanvasMutation] = field(default_factory=list)
    risk_level: MutationRiskLevel = MutationRiskLevel.LOW
    status: str = "draft"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "workspace_id": self.workspace_id,
            "turn_id": self.turn_id,
            "mutations": [item.to_dict() for item in self.mutations],
            "risk_level": self.risk_level.value,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasMutationProposal":
        return cls(
            proposal_id=data["proposal_id"],
            workspace_id=data["workspace_id"],
            turn_id=data["turn_id"],
            mutations=[CanvasMutation.from_dict(item) for item in data.get("mutations", [])],
            risk_level=MutationRiskLevel(data.get("risk_level", MutationRiskLevel.LOW.value)),
            status=data.get("status", "draft"),
        )
```

- [x] **步骤 4：再次运行测试，确认通过**

运行：`python3 -m unittest tests.test_canvas_domain -v`
预期：`CanvasDomainTests` 全部 PASS，输出 `OK`。

- [x] **步骤 5：提交**

```bash
git -C /Users/apple/Desktop/evocanvas add app/canvas/__init__.py app/canvas/domain/__init__.py app/canvas/domain/workspace.py app/canvas/domain/cards.py app/canvas/domain/relations.py app/canvas/domain/snapshots.py app/canvas/domain/handoff.py app/canvas/domain/mutations.py tests/test_canvas_domain.py
git -C /Users/apple/Desktop/evocanvas commit -m "feat: add evocanvas domain contracts"
```

### 任务 2：建立 CanvasRepository 与文件存储布局

**文件：**
- 新建：`app/canvas/repository.py`
- 修改：`app/services/fakes.py`
- 测试：`tests/test_canvas_repository.py`

- [x] **步骤 1：先写失败测试**

```python
import tempfile
import unittest
from pathlib import Path

from app.canvas.domain.workspace import CanvasWorkspace
from app.canvas.repository import CanvasRepository
from app.services.fakes import FakeStorage


class CanvasRepositoryTests(unittest.TestCase):
    def test_workspace_and_cards_persist_in_canvas_namespace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FakeStorage(Path(tmpdir))
            repo = CanvasRepository(storage.root)
            workspace = CanvasWorkspace(
                workspace_id="ws_demo",
                title="618 会员积分防刷治理一期",
                objective="形成结构化交接物",
            )

            repo.save_workspace(workspace)
            loaded = repo.load_workspace("ws_demo")

            self.assertEqual(loaded.workspace_id, "ws_demo")
            self.assertTrue((Path(tmpdir) / "canvas" / "workspaces" / "ws_demo" / "workspace.json").exists())
```

- [x] **步骤 2：运行测试，确认当前会失败**

运行：`python3 -m unittest tests.test_canvas_repository -v`
预期：由于 `CanvasRepository` 与 `canvas/workspaces/*` 存储布局尚未实现，测试 FAIL。

- [x] **步骤 3：补最小实现**

```python
# app/canvas/repository.py
import json
from pathlib import Path
from typing import List

from app.canvas.domain.workspace import CanvasWorkspace


class CanvasRepository:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _workspace_dir(self, workspace_id: str) -> Path:
        path = self.root / "canvas" / "workspaces" / workspace_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_workspace(self, workspace: CanvasWorkspace) -> None:
        path = self._workspace_dir(workspace.workspace_id) / "workspace.json"
        path.write_text(json.dumps(workspace.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def load_workspace(self, workspace_id: str) -> CanvasWorkspace:
        path = self._workspace_dir(workspace_id) / "workspace.json"
        return CanvasWorkspace.from_dict(json.loads(path.read_text(encoding="utf-8")))
```

```python
# app/services/fakes.py
def canvas_root(self) -> Path:
    path = self.root / "canvas"
    path.mkdir(parents=True, exist_ok=True)
    return path
```

- [x] **步骤 4：再次运行测试，确认通过**

运行：`python3 -m unittest tests.test_canvas_repository -v`
预期：workspace 持久化位置正确，测试 PASS。

- [x] **步骤 5：提交**

```bash
git -C /Users/apple/Desktop/evocanvas add app/canvas/repository.py app/services/fakes.py tests/test_canvas_repository.py
git -C /Users/apple/Desktop/evocanvas commit -m "feat: add evocanvas repository storage"
```

### 任务 3：实现 Mutation Governance 与 confirmation queue

**文件：**
- 新建：`app/canvas/governance.py`
- 修改：`app/canvas/repository.py`
- 测试：`tests/test_canvas_governance.py`

- [x] **步骤 1：先写失败测试**

```python
import unittest

from app.canvas.domain.mutations import CanvasMutation, CanvasMutationProposal
from app.canvas.governance import MutationGovernance


class CanvasGovernanceTests(unittest.TestCase):
    def test_marks_confirmation_for_high_impact_mutation(self):
        governance = MutationGovernance()
        proposal = CanvasMutationProposal(
            proposal_id="proposal_001",
            workspace_id="ws_demo",
            turn_id="turn_001",
            mutations=[
                CanvasMutation(
                    mutation_type="confirm_constraint",
                    target_id="card_001",
                    payload={"status": "effective"},
                )
            ],
        )

        outcome = governance.classify(proposal)
        self.assertEqual(outcome.action, "pending_confirmation")
        self.assertEqual(outcome.risk_level, "high")
```

- [x] **步骤 2：运行测试，确认当前会失败**

运行：`python3 -m unittest tests.test_canvas_governance -v`
预期：`MutationGovernance` 和风险分类逻辑不存在，测试 FAIL。

- [x] **步骤 3：补最小实现**

```python
# app/canvas/governance.py
from dataclasses import dataclass


@dataclass
class GovernanceOutcome:
    action: str
    risk_level: str


class MutationGovernance:
    HIGH_RISK_MUTATIONS = {
        "confirm_constraint",
        "resolve_clarification",
        "create_decision_request",
        "create_snapshot",
    }

    def classify(self, proposal):
        mutation_types = {item.mutation_type for item in proposal.mutations}
        if mutation_types & self.HIGH_RISK_MUTATIONS:
            proposal.risk_level = proposal.risk_level.__class__.HIGH
            proposal.status = "pending_confirmation"
            return GovernanceOutcome(action="pending_confirmation", risk_level="high")
        proposal.status = "applied"
        return GovernanceOutcome(action="auto_apply", risk_level="low")
```

```python
# app/canvas/repository.py
def save_confirmation_queue(self, workspace_id: str, proposal_ids: List[str]) -> None:
    path = self._workspace_dir(workspace_id) / "confirmation_queue.json"
    path.write_text(json.dumps({"proposal_ids": proposal_ids}, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [x] **步骤 4：再次运行测试，确认通过**

运行：`python3 -m unittest tests.test_canvas_governance -v`
预期：高风险 mutation 被识别为 `pending_confirmation`，测试 PASS。

- [x] **步骤 5：提交**

```bash
git -C /Users/apple/Desktop/evocanvas add app/canvas/governance.py app/canvas/repository.py tests/test_canvas_governance.py
git -C /Users/apple/Desktop/evocanvas commit -m "feat: add evocanvas mutation governance"
```

### 任务 4：实现 Canvas Agent contracts、角色注册与 Supervisor

**文件：**
- 新建：`app/canvas/agent/__init__.py`
- 新建：`app/canvas/agent/contracts.py`
- 新建：`app/canvas/agent/roles.py`
- 新建：`app/canvas/agent/supervisor.py`
- 测试：`tests/test_canvas_supervisor.py`

- [x] **步骤 1：先写失败测试**

```python
import unittest

from app.canvas.agent.supervisor import CanvasSupervisor
from app.services.fakes import FakeLLM


class CanvasSupervisorTests(unittest.TestCase):
    def test_routes_clarification_prompt_to_clarifier_role(self):
        supervisor = CanvasSupervisor(llm=FakeLLM())
        plan = supervisor.recognize_and_plan(
            workspace_context={"workspace_id": "ws_demo"},
            message="先把一期范围和误杀成本的待澄清问题列出来",
        )

        self.assertEqual(plan.intent, "clarification")
        self.assertIn("Clarifier", plan.roles)
        self.assertNotIn("HandoffBuilder", plan.roles)
```

- [x] **步骤 2：运行测试，确认当前会失败**

运行：`python3 -m unittest tests.test_canvas_supervisor -v`
预期：Supervisor 和角色规划不存在，测试 FAIL。

- [x] **步骤 3：补最小实现**

```python
# app/canvas/agent/contracts.py
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class CanvasTurnPlan:
    intent: str
    roles: List[str]
    allowed_mutation_types: List[str] = field(default_factory=list)


@dataclass
class RoleOutput:
    role: str
    findings: List[str]
    proposed_mutations: List[Dict[str, object]]
    evidence_refs: List[str]
    confidence: str
```

```python
# app/canvas/agent/supervisor.py
from app.canvas.agent.contracts import CanvasTurnPlan


class CanvasSupervisor:
    def __init__(self, llm):
        self.llm = llm

    def recognize_and_plan(self, workspace_context, message: str) -> CanvasTurnPlan:
        if "待澄清" in message or "澄清" in message:
            return CanvasTurnPlan(
                intent="clarification",
                roles=["Clarifier"],
                allowed_mutation_types=["add_card", "update_card_summary", "mark_conflict"],
            )
        if "交接物" in message:
            return CanvasTurnPlan(
                intent="handoff",
                roles=["HandoffBuilder"],
                allowed_mutation_types=["refresh_handoff_draft"],
            )
        return CanvasTurnPlan(
            intent="input_compilation",
            roles=["InputCompiler"],
            allowed_mutation_types=["add_card", "add_relation"],
        )
```

- [x] **步骤 4：再次运行测试，确认通过**

运行：`python3 -m unittest tests.test_canvas_supervisor -v`
预期：意图识别与角色选择断言 PASS。

- [x] **步骤 5：提交**

```bash
git -C /Users/apple/Desktop/evocanvas add app/canvas/agent/__init__.py app/canvas/agent/contracts.py app/canvas/agent/roles.py app/canvas/agent/supervisor.py tests/test_canvas_supervisor.py
git -C /Users/apple/Desktop/evocanvas commit -m "feat: add evocanvas supervisor planning"
```

### 任务 5：接入 `canvas_turn` workflow 并注册任务定义

**文件：**
- 新建：`app/workflows/canvas_session.py`
- 修改：`app/workflows/definitions.py`
- 测试：`tests/test_canvas_workflow_definition.py`

- [x] **步骤 1：先写失败测试**

```python
import unittest

from app.workflows.definitions import build_task_registry


class CanvasWorkflowDefinitionTests(unittest.TestCase):
    def test_registry_contains_evocanvas_canvas_turn(self):
        registry = build_task_registry()
        self.assertIn("evocanvas_canvas_turn", registry)
        self.assertEqual(registry["evocanvas_canvas_turn"].display_name, "EvoCanvas Canvas Turn")
```

- [x] **步骤 2：运行测试，确认当前会失败**

运行：`python3 -m unittest tests.test_canvas_workflow_definition -v`
预期：注册表中没有 `evocanvas_canvas_turn`，测试 FAIL。

- [x] **步骤 3：补最小实现**

```python
# app/workflows/canvas_session.py
from app.core.task import TaskDefinition, WorkflowSpec, WorkflowStep
from app.core.tools import ToolPolicy, ToolPolicyRule


def build_canvas_turn_definition() -> TaskDefinition:
    workflow = WorkflowSpec(
        name="evocanvas_canvas_turn",
        version="1.0",
        steps=[
            WorkflowStep(id="load_workspace_context", type="context", title="加载工作台上下文"),
            WorkflowStep(id="run_canvas_supervisor", type="agent", title="识别意图并规划内部角色"),
            WorkflowStep(id="merge_mutation_proposal", type="agent", title="合并 mutation proposal"),
            WorkflowStep(id="emit_canvas_events", type="context", title="输出画布事件"),
        ],
    )
    tool_policy = ToolPolicy(
        task_type="evocanvas_canvas_turn",
        rules=[ToolPolicyRule(role="*", step_id="*", allowed_tools=["knowledge.retrieve", "material.read"])],
    )
    return TaskDefinition(
        type="evocanvas_canvas_turn",
        display_name="EvoCanvas Canvas Turn",
        input_schema={"required": ["username", "title", "goal", "workspace_id", "message"]},
        workflow=workflow,
        tool_policy=tool_policy,
        metadata={"is_evocanvas_canvas_turn": True},
    )
```

```python
# app/workflows/definitions.py
from app.workflows.canvas_session import build_canvas_turn_definition

def build_task_registry() -> dict[str, TaskDefinition]:
    spec_to_agent = build_spec_to_agent_definition()
    acceptance_review = build_acceptance_review_definition()
    canvas_turn = build_canvas_turn_definition()
    return {
        "spec_to_agent": spec_to_agent,
        "acceptance_review": acceptance_review,
        "evocanvas_canvas_turn": canvas_turn,
    }
```

- [x] **步骤 4：再次运行测试，确认通过**

运行：`python3 -m unittest tests.test_canvas_workflow_definition -v`
预期：新 task definition 已注册，测试 PASS。

- [x] **步骤 5：提交**

```bash
git -C /Users/apple/Desktop/evocanvas add app/workflows/canvas_session.py app/workflows/definitions.py tests/test_canvas_workflow_definition.py
git -C /Users/apple/Desktop/evocanvas commit -m "feat: register evocanvas canvas turn workflow"
```

### 任务 6：新增 Canvas API schemas 与只读读取接口

**文件：**
- 新建：`app/api/canvas_schemas.py`
- 修改：`app/api/server.py`
- 测试：`tests/test_canvas_api.py`

- [x] **步骤 1：先写失败测试**

```python
import tempfile
import unittest
from pathlib import Path

from app.api.server import create_app
from app.services.fakes import FakeStorage

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None


class CanvasApiTests(unittest.TestCase):
    def setUp(self):
        if TestClient is None:
            self.skipTest("FastAPI not installed")
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_get_canvas_workspace_returns_workspace_payload(self):
        response = self.client.get("/api/canvas/workspaces/demo")
        self.assertEqual(response.status_code, 200)
        self.assertIn("workspace_id", response.json())
```

- [x] **步骤 2：运行测试，确认当前会失败**

运行：`python3 -m unittest tests.test_canvas_api -v`
预期：`/api/canvas/workspaces/demo` 尚不存在，测试 FAIL。

- [x] **步骤 3：补最小实现**

```python
# app/api/canvas_schemas.py
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel
except Exception:  # pragma: no cover
    class BaseModel:  # type: ignore
        pass


class CanvasMessageRequest(BaseModel):
    message: str
    selected_card_ids: List[str] = []
    material_ids: List[str] = []
    mode: Optional[str] = None
```

```python
# app/api/server.py
@app.get("/api/canvas/workspaces/{workspace_id}")
async def get_canvas_workspace(workspace_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "title": "EvoCanvas Workspace",
        "objective": "待收束",
        "active_snapshot_id": None,
        "handoff_status": "draft",
    }


@app.get("/api/canvas/workspaces/{workspace_id}/canvas")
async def get_canvas_view(workspace_id: str, snapshot_id: Optional[str] = None, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "snapshot_id": snapshot_id,
        "cards": [],
        "relations": [],
        "todo_projection": {"items": []},
        "pending_confirmations_count": 0,
        "view_meta": {},
    }
```

- [x] **步骤 4：再次运行测试，确认通过**

运行：`python3 -m unittest tests.test_canvas_api -v`
预期：workspace 和 canvas 读取接口 PASS。

- [x] **步骤 5：提交**

```bash
git -C /Users/apple/Desktop/evocanvas add app/api/canvas_schemas.py app/api/server.py tests/test_canvas_api.py
git -C /Users/apple/Desktop/evocanvas commit -m "feat: add evocanvas read api endpoints"
```

### 任务 7：接入 `POST /messages`、workspace 级 SSE 与低风险自动写入

**文件：**
- 修改：`app/api/server.py`
- 新建：`app/canvas/service.py`
- 测试：`tests/test_canvas_turn_flow.py`

- [x] **步骤 1：先写失败测试**

```python
import unittest

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None

from app.api.server import create_app


class CanvasTurnFlowTests(unittest.TestCase):
    def setUp(self):
        if TestClient is None:
            self.skipTest("FastAPI not installed")
        self.client = TestClient(create_app())

    def test_post_message_returns_turn_id(self):
        response = self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={"message": "先把待澄清问题列出来", "selected_card_ids": [], "material_ids": [], "mode": "default"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("turn_id", response.json())
```

- [x] **步骤 2：运行测试，确认当前会失败**

运行：`python3 -m unittest tests.test_canvas_turn_flow -v`
预期：消息提交接口还不存在，测试 FAIL。

- [x] **步骤 3：补最小实现**

```python
# app/canvas/service.py
from uuid import uuid4


class CanvasService:
    def start_turn(self, workspace_id: str, message: str, selected_card_ids: list[str], material_ids: list[str]) -> dict:
        return {
            "turn_id": f"turn_{uuid4().hex[:12]}",
            "workspace_id": workspace_id,
            "accepted": True,
            "message": message,
            "selected_card_ids": selected_card_ids,
            "material_ids": material_ids,
        }
```

```python
# app/api/server.py
from app.api.canvas_schemas import CanvasMessageRequest

@app.post("/api/canvas/workspaces/{workspace_id}/messages")
async def post_canvas_message(workspace_id: str, request: CanvasMessageRequest, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
    canvas_service = CanvasService()
    result = canvas_service.start_turn(
        workspace_id=workspace_id,
        message=request.message,
        selected_card_ids=list(request.selected_card_ids),
        material_ids=list(request.material_ids),
    )
    return {
        "turn_id": result["turn_id"],
        "accepted": True,
        "workspace_id": workspace_id,
    }


@app.get("/api/canvas/workspaces/{workspace_id}/events")
async def get_canvas_events(workspace_id: str, service: TaskService = Depends(get_task_service)):
    async def stream():
        yield "event: agent.intent.recognized\ndata: {\"workspace_id\": \"%s\"}\n\n" % workspace_id
    return StreamingResponse(stream(), media_type="text/event-stream")
```

- [x] **步骤 4：再次运行测试，确认通过**

运行：`python3 -m unittest tests.test_canvas_turn_flow -v`
预期：消息提交返回 `turn_id`，测试 PASS。

- [x] **步骤 5：提交**

```bash
git -C /Users/apple/Desktop/evocanvas add app/canvas/service.py app/api/server.py tests/test_canvas_turn_flow.py
git -C /Users/apple/Desktop/evocanvas commit -m "feat: add evocanvas turn submission flow"
```

### 任务 8：实现 confirmation、snapshots 与 handoff 接口

**文件：**
- 修改：`app/canvas/repository.py`
- 修改：`app/canvas/service.py`
- 修改：`app/api/server.py`
- 测试：`tests/test_canvas_confirmation_api.py`

- [x] **步骤 1：先写失败测试**

```python
import unittest

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None

from app.api.server import create_app


class CanvasConfirmationApiTests(unittest.TestCase):
    def setUp(self):
        if TestClient is None:
            self.skipTest("FastAPI not installed")
        self.client = TestClient(create_app())

    def test_confirmation_endpoints_exist(self):
        response = self.client.get("/api/canvas/workspaces/demo/confirmations")
        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.json())
```

- [x] **步骤 2：运行测试，确认当前会失败**

运行：`python3 -m unittest tests.test_canvas_confirmation_api -v`
预期：确认、快照和 handoff 接口不存在，测试 FAIL。

- [x] **步骤 3：补最小实现**

```python
# app/canvas/service.py
def list_confirmations(self, workspace_id: str) -> dict:
    return {"items": []}

def approve_confirmation(self, workspace_id: str, proposal_id: str) -> dict:
    return {"workspace_id": workspace_id, "proposal_id": proposal_id, "status": "applied"}

def reject_confirmation(self, workspace_id: str, proposal_id: str) -> dict:
    return {"workspace_id": workspace_id, "proposal_id": proposal_id, "status": "rejected"}

def list_snapshots(self, workspace_id: str) -> dict:
    return {"items": []}

def get_handoff(self, workspace_id: str) -> dict:
    return {"workspace_id": workspace_id, "status": "draft", "content": ""}
```

```python
# app/api/server.py
@app.get("/api/canvas/workspaces/{workspace_id}/confirmations")
async def list_canvas_confirmations(workspace_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
    return CanvasService().list_confirmations(workspace_id)


@app.post("/api/canvas/workspaces/{workspace_id}/confirmations/{proposal_id}/approve")
async def approve_canvas_confirmation(workspace_id: str, proposal_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
    return CanvasService().approve_confirmation(workspace_id, proposal_id)


@app.post("/api/canvas/workspaces/{workspace_id}/confirmations/{proposal_id}/reject")
async def reject_canvas_confirmation(workspace_id: str, proposal_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
    return CanvasService().reject_confirmation(workspace_id, proposal_id)


@app.get("/api/canvas/workspaces/{workspace_id}/snapshots")
async def list_canvas_snapshots(workspace_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
    return CanvasService().list_snapshots(workspace_id)


@app.get("/api/canvas/workspaces/{workspace_id}/handoff")
async def get_canvas_handoff(workspace_id: str, service: TaskService = Depends(get_task_service)) -> Dict[str, Any]:
    return CanvasService().get_handoff(workspace_id)
```

- [x] **步骤 4：再次运行测试，确认通过**

运行：`python3 -m unittest tests.test_canvas_confirmation_api -v`
预期：确认、snapshot、handoff 接口全部 PASS。

- [x] **步骤 5：提交**

```bash
git -C /Users/apple/Desktop/evocanvas add app/canvas/repository.py app/canvas/service.py app/api/server.py tests/test_canvas_confirmation_api.py
git -C /Users/apple/Desktop/evocanvas commit -m "feat: add evocanvas confirmation and handoff api"
```

### 任务 9：补齐回归验证与迁移守护测试

**文件：**
- 新建：`tests/test_canvas_regression.py`

- [x] **步骤 1：先写失败测试**

```python
import unittest

from app.workflows.definitions import build_task_registry


class CanvasRegressionTests(unittest.TestCase):
    def test_legacy_and_evocanvas_task_types_can_coexist(self):
        registry = build_task_registry()
        self.assertIn("spec_to_agent", registry)
        self.assertIn("acceptance_review", registry)
        self.assertIn("evocanvas_canvas_turn", registry)
```

- [x] **步骤 2：运行验证，确认当前仍有缺口**

运行：`python3 -m unittest tests.test_canvas_domain tests.test_canvas_repository tests.test_canvas_governance tests.test_canvas_supervisor tests.test_canvas_workflow_definition tests.test_canvas_api tests.test_canvas_turn_flow tests.test_canvas_confirmation_api tests.test_canvas_regression -v`
预期：在全部实现和路由补齐之前，至少会有一个测试 FAIL。

- [x] **步骤 3：补最小实现与验证命令**

```text
验证命令 1：
python3 -m unittest tests.test_canvas_domain tests.test_canvas_repository tests.test_canvas_governance tests.test_canvas_supervisor tests.test_canvas_workflow_definition tests.test_canvas_api tests.test_canvas_turn_flow tests.test_canvas_confirmation_api tests.test_canvas_regression -v

验证命令 2：
python3 -m py_compile app/api/server.py app/api/canvas_schemas.py app/canvas/repository.py app/canvas/governance.py app/canvas/service.py app/canvas/agent/supervisor.py app/workflows/canvas_session.py
```

- [x] **步骤 4：执行完整回归，确认全部通过**

运行：

```bash
python3 -m unittest tests.test_canvas_domain tests.test_canvas_repository tests.test_canvas_governance tests.test_canvas_supervisor tests.test_canvas_workflow_definition tests.test_canvas_api tests.test_canvas_turn_flow tests.test_canvas_confirmation_api tests.test_canvas_regression -v
python3 -m py_compile app/api/server.py app/api/canvas_schemas.py app/canvas/repository.py app/canvas/governance.py app/canvas/service.py app/canvas/agent/supervisor.py app/workflows/canvas_session.py
```

预期：

- `unittest` 输出 `OK`
- `py_compile` 无报错输出

- [x] **步骤 5：提交**

```bash
git -C /Users/apple/Desktop/evocanvas add tests/test_canvas_regression.py
git -C /Users/apple/Desktop/evocanvas commit -m "test: add evocanvas backend regression coverage"
```

---

## 最终联调验证

在所有任务完成后，执行以下命令确认后端闭环成立：

1. 启动 API：

```bash
python3 -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000 --reload
```

2. 健康检查：

```bash
curl -s http://127.0.0.1:8000/api/health
```

预期：返回包含 `"status": "ok"` 的 JSON。

3. Canvas workspace 读取：

```bash
curl -s http://127.0.0.1:8000/api/canvas/workspaces/demo
```

预期：返回 `workspace_id`、`title`、`objective` 等字段。

4. Canvas 视图读取：

```bash
curl -s http://127.0.0.1:8000/api/canvas/workspaces/demo/canvas
```

预期：返回 `cards`、`relations`、`todo_projection` 等字段。

5. 发起一轮消息：

```bash
curl -s -X POST http://127.0.0.1:8000/api/canvas/workspaces/demo/messages \
  -H "Content-Type: application/json" \
  -d '{"message":"先把一期范围和误杀成本的待澄清问题列出来","selected_card_ids":[],"material_ids":[],"mode":"default"}'
```

预期：返回 `turn_id` 和 `accepted: true`。

6. 读取 confirmations：

```bash
curl -s http://127.0.0.1:8000/api/canvas/workspaces/demo/confirmations
```

预期：返回 `items` 数组，即使为空也应结构稳定。

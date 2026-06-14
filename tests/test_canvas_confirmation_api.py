import unittest
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None

from app.api.server import create_app
from app.canvas.domain.cards import CanvasCard, CanvasCardKind
from app.canvas.domain.mutations import (
    CanvasMutation,
    CanvasMutationAction,
    CanvasMutationProposal,
    CanvasMutationStatus,
    CanvasMutationTarget,
)
from app.canvas.service import CanvasService
from app.core.events import EventBus
from app.services.fakes import FakeStorage


class CanvasConfirmationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        if TestClient is None:
            self.skipTest("FastAPI not installed")
        self.client = TestClient(create_app())
        self.headers = {"X-Tenant-ID": f"canvas-confirmation-{uuid4().hex[:8]}"}

    def test_confirmation_endpoints_exist_and_surface_pending_items(self) -> None:
        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "把这次方案取舍整理成需要拍板的待决策项",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )

        response = self.client.get("/api/canvas/workspaces/demo/confirmations", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["items"]), 1)
        proposal_id = payload["items"][0]["proposal_id"]

        approve = self.client.post(
            f"/api/canvas/workspaces/demo/confirmations/{proposal_id}/approve",
            headers=self.headers,
        )
        self.assertEqual(approve.status_code, 200)
        self.assertEqual(approve.json()["status"], "applied")

        canvas = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()
        self.assertEqual(len(canvas["cards"]), 1)
        self.assertEqual(canvas["cards"][0]["kind"], "decision")
        self.assertEqual(canvas["cards"][0]["status"], "confirmed")
        self.assertEqual(canvas["pending_confirmations_count"], 0)
        self.assertEqual(canvas["todo_projection"]["items"], [])

    def test_reject_confirmation_does_not_write_pending_card_into_canvas(self) -> None:
        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "把这次方案取舍整理成需要拍板的待决策项",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )

        pending = self.client.get("/api/canvas/workspaces/demo/confirmations", headers=self.headers).json()
        proposal_id = pending["items"][0]["proposal_id"]

        reject = self.client.post(
            f"/api/canvas/workspaces/demo/confirmations/{proposal_id}/reject",
            headers=self.headers,
        )
        self.assertEqual(reject.status_code, 200)
        self.assertEqual(reject.json()["status"], "rejected")

        canvas = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()
        confirmations = self.client.get("/api/canvas/workspaces/demo/confirmations", headers=self.headers).json()
        self.assertEqual(canvas["cards"], [])
        self.assertEqual(canvas["pending_confirmations_count"], 0)
        self.assertEqual(confirmations["items"], [])

        resumed = self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "继续补充误杀成本的待澄清问题",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )
        self.assertEqual(resumed.status_code, 200)

    def test_confirmation_missing_proposal_returns_404(self) -> None:
        approve = self.client.post(
            "/api/canvas/workspaces/demo/confirmations/proposal_missing/approve",
            headers=self.headers,
        )
        reject = self.client.post(
            "/api/canvas/workspaces/demo/confirmations/proposal_missing/reject",
            headers=self.headers,
        )

        self.assertEqual(approve.status_code, 404)
        self.assertEqual(reject.status_code, 404)

    def test_snapshot_and_handoff_endpoints_exist(self) -> None:
        snapshots = self.client.get("/api/canvas/workspaces/demo/snapshots", headers=self.headers)
        handoff = self.client.get("/api/canvas/workspaces/demo/handoff", headers=self.headers)

        self.assertEqual(snapshots.status_code, 200)
        self.assertIn("items", snapshots.json())
        self.assertEqual(handoff.status_code, 200)
        self.assertIn("status", handoff.json())

    def test_approve_confirm_constraint_materializes_existing_card(self) -> None:
        event_bus = EventBus()
        storage = FakeStorage(Path(gettempdir()) / f"canvas-confirm-constraint-{uuid4().hex[:8]}", event_bus=event_bus)
        service = CanvasService(storage=storage)
        service.get_workspace("demo")
        card = CanvasCard(
            card_id="card_constraint_001",
            kind=CanvasCardKind.CONSTRAINT,
            title="一期必须优先降低误杀成本",
            summary="约束仍需用户确认后才可进入交接上下文。",
            stage="define",
            status="draft",
            evidence_refs=["material-confirm"],
        )
        service.repository.save_cards("demo", [card])
        proposal = CanvasMutationProposal(
            proposal_id="proposal_confirm_constraint",
            workspace_id="demo",
            turn_id="turn_confirm_constraint",
            status=CanvasMutationStatus.PENDING_CONFIRMATION,
            mutations=[
                CanvasMutation(
                    mutation_id="mutation_confirm_constraint",
                    action=CanvasMutationAction.UPDATE,
                    target=CanvasMutationTarget.CARD,
                    target_id=card.card_id,
                    payload={"status": "effective"},
                    metadata={"mutation_type": "confirm_constraint"},
                )
            ],
        )
        service.repository.save_confirmation_queue("demo", [proposal])
        subscriber = event_bus.subscribe(service.event_stream_id("demo"))

        result = service.approve_confirmation("demo", proposal.proposal_id)

        self.assertEqual(result["status"], "applied")
        canvas = service.get_canvas_view("demo")
        persisted = canvas["cards"][0]
        self.assertEqual(persisted["card_id"], card.card_id)
        self.assertEqual(persisted["kind"], "constraint")
        self.assertEqual(persisted["status"], "effective")
        self.assertEqual(persisted["metadata"]["confirmed_by"], "user")
        self.assertEqual(canvas["todo_projection"]["items"], [])
        self.assertEqual(service.list_confirmations("demo")["items"], [])

        event_types = []
        while True:
            try:
                event_types.append(subscriber.get_nowait().type)
            except Exception:
                break
        self.assertIn("canvas.confirmation.approved", event_types)
        self.assertIn("canvas.mutation.applied", event_types)

    def test_approve_resolve_clarification_materializes_existing_card(self) -> None:
        storage = FakeStorage(Path(gettempdir()) / f"canvas-resolve-clarification-{uuid4().hex[:8]}")
        service = CanvasService(storage=storage)
        service.get_workspace("demo")
        card = CanvasCard(
            card_id="card_clarification_001",
            kind=CanvasCardKind.CLARIFICATION,
            title="确认核心用户是谁",
            summary="当前仍需澄清主使用者。",
            stage="define",
            status="pending",
        )
        service.repository.save_cards("demo", [card])
        proposal = CanvasMutationProposal(
            proposal_id="proposal_resolve_clarification",
            workspace_id="demo",
            turn_id="turn_resolve_clarification",
            status=CanvasMutationStatus.PENDING_CONFIRMATION,
            mutations=[
                CanvasMutation(
                    mutation_id="mutation_resolve_clarification",
                    action=CanvasMutationAction.UPDATE,
                    target=CanvasMutationTarget.CARD,
                    target_id=card.card_id,
                    payload={"resolution": "核心用户先聚焦一线产品经理"},
                    metadata={"mutation_type": "resolve_clarification"},
                )
            ],
        )
        service.repository.save_confirmation_queue("demo", [proposal])

        result = service.approve_confirmation("demo", proposal.proposal_id)

        self.assertEqual(result["status"], "applied")
        canvas = service.get_canvas_view("demo")
        persisted = canvas["cards"][0]
        self.assertEqual(persisted["card_id"], card.card_id)
        self.assertEqual(persisted["status"], "resolved")
        self.assertEqual(persisted["metadata"]["resolved_by"], "user")
        self.assertEqual(persisted["metadata"]["resolution"], "核心用户先聚焦一线产品经理")
        self.assertEqual(canvas["todo_projection"]["items"], [])

    def test_approve_promote_formal_handoff_marks_handoff_confirmed(self) -> None:
        storage = FakeStorage(Path(gettempdir()) / f"canvas-formal-handoff-{uuid4().hex[:8]}")
        service = CanvasService(storage=storage)
        service.get_workspace("demo")
        handoff_card = CanvasCard(
            card_id="card_handoff_001",
            kind=CanvasCardKind.HANDOFF,
            title="结构化交接物草稿",
            summary="当前交接物仍是草稿。",
            stage="handoff",
            status="draft",
        )
        service.repository.save_cards("demo", [handoff_card])
        service.refresh_handoff("demo")
        proposal = CanvasMutationProposal(
            proposal_id="proposal_formal_handoff",
            workspace_id="demo",
            turn_id="turn_formal_handoff",
            status=CanvasMutationStatus.PENDING_CONFIRMATION,
            mutations=[
                CanvasMutation(
                    mutation_id="mutation_formal_handoff",
                    action=CanvasMutationAction.UPDATE,
                    target=CanvasMutationTarget.CARD,
                    target_id=handoff_card.card_id,
                    payload={},
                    metadata={"mutation_type": "promote_formal_handoff"},
                )
            ],
        )
        service.repository.save_confirmation_queue("demo", [proposal])

        result = service.approve_confirmation("demo", proposal.proposal_id)

        self.assertEqual(result["status"], "applied")
        canvas = service.get_canvas_view("demo")
        persisted = next(card for card in canvas["cards"] if card["card_id"] == handoff_card.card_id)
        self.assertEqual(persisted["status"], "confirmed")
        self.assertEqual(persisted["metadata"]["confirmed_by"], "user")
        workspace = service.get_workspace("demo")
        self.assertEqual(workspace.handoff_status, "confirmed")

    def test_approve_create_snapshot_materializes_ai_proposed_snapshot(self) -> None:
        storage = FakeStorage(Path(gettempdir()) / f"canvas-ai-snapshot-{uuid4().hex[:8]}")
        service = CanvasService(storage=storage)
        service.get_workspace("demo")
        card = CanvasCard(
            card_id="card_snapshot_001",
            kind=CanvasCardKind.CLARIFICATION,
            title="确认 1.0 范围",
            summary="需要把当前缺口保存为一次可回看的认知状态。",
            stage="define",
            status="open",
        )
        service.repository.save_cards("demo", [card])
        proposal = CanvasMutationProposal(
            proposal_id="proposal_create_snapshot",
            workspace_id="demo",
            turn_id="turn_create_snapshot",
            status=CanvasMutationStatus.PENDING_CONFIRMATION,
            mutations=[
                CanvasMutation(
                    mutation_id="mutation_create_snapshot",
                    action=CanvasMutationAction.ADD,
                    target=CanvasMutationTarget.SNAPSHOT,
                    target_id="snapshot_ai_proposed",
                    payload={"title": "AI 建议保存快照", "summary": "保存当前活跃缺口。"},
                    metadata={"mutation_type": "create_snapshot"},
                )
            ],
        )
        service.repository.save_confirmation_queue("demo", [proposal])

        result = service.approve_confirmation("demo", proposal.proposal_id)

        self.assertEqual(result["status"], "applied")
        snapshots = service.list_snapshots("demo")["items"]
        self.assertEqual(len(snapshots), 1)
        snapshot = snapshots[0]
        self.assertEqual(snapshot["snapshot_id"], "snapshot_ai_proposed")
        self.assertEqual(snapshot["title"], "AI 建议保存快照")
        self.assertEqual(snapshot["cards"][0]["card_id"], card.card_id)
        self.assertEqual(service.get_workspace("demo").active_snapshot_id, "snapshot_ai_proposed")


if __name__ == "__main__":
    unittest.main()

import queue
import unittest
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None

from app.api.server import create_app
from app.canvas.service import CanvasService
from app.core.events import EventBus
from app.services.fakes import FakeStorage


class CanvasTurnFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        if TestClient is None:
            self.skipTest("FastAPI not installed")
        self.client = TestClient(create_app())
        self.tenant_id = f"canvas-turn-{uuid4().hex[:8]}"
        self.headers = {"X-Tenant-ID": self.tenant_id}
        self.storage = FakeStorage(Path(gettempdir()) / "manual-agent-phase1" / self.tenant_id)
        self.canvas_service = CanvasService(storage=self.storage)

    def test_post_message_returns_turn_id_and_applies_low_risk_card(self) -> None:
        response = self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "先把一期范围和误杀成本的待澄清问题列出来",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("turn_id", payload)
        self.assertEqual(payload["workspace_id"], "demo")
        self.assertEqual(payload["action"], "auto_apply")

        canvas = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()
        self.assertEqual(len(canvas["cards"]), 1)
        self.assertEqual(canvas["cards"][0]["kind"], "clarification")

    def test_input_compilation_creates_evidence_problem_and_clarification_cards(self) -> None:
        response = self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "这里有一段新的会议纪要：老板希望一期先降低误杀成本，但运营又要求尽快上线。",
                "selected_card_ids": [],
                "material_ids": ["meeting_001"],
                "mode": "default",
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["intent"], "input_compilation")

        canvas = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()
        card_kinds = [card["kind"] for card in canvas["cards"]]
        self.assertEqual(card_kinds, ["evidence", "problem", "clarification"])
        self.assertTrue(all(card["evidence_refs"] == ["meeting_001"] for card in canvas["cards"]))

    def test_selected_cards_and_materials_are_reflected_in_new_card_and_relation(self) -> None:
        first = self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "先把一期范围和误杀成本的待澄清问题列出来",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )
        self.assertEqual(first.status_code, 200)

        canvas_before = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()
        selected_card_id = canvas_before["cards"][0]["card_id"]

        second = self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "结合这张卡和会议纪要，把约束补齐",
                "selected_card_ids": [selected_card_id],
                "material_ids": ["material_001"],
                "mode": "default",
            },
            headers=self.headers,
        )
        self.assertEqual(second.status_code, 200)

        canvas_after = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()
        self.assertEqual(len(canvas_after["cards"]), 2)
        newest_card = canvas_after["cards"][-1]
        self.assertEqual(newest_card["kind"], "constraint")
        self.assertEqual(newest_card["evidence_refs"], ["material_001"])
        self.assertEqual(newest_card["metadata"]["selected_card_ids"], [selected_card_id])
        self.assertIn("误杀成本", newest_card["summary"])
        self.assertEqual(len(canvas_after["relations"]), 1)
        self.assertEqual(canvas_after["relations"][0]["from_card_id"], selected_card_id)
        self.assertEqual(canvas_after["relations"][0]["to_card_id"], newest_card["card_id"])

    def test_handoff_turn_refreshes_handoff_and_creates_snapshot(self) -> None:
        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "先把一期范围和误杀成本的待澄清问题列出来",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )
        clarification_canvas = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()
        clarification_id = clarification_canvas["cards"][0]["card_id"]

        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "结合这张卡和会议纪要，把约束补齐",
                "selected_card_ids": [clarification_id],
                "material_ids": ["material_002"],
                "mode": "default",
            },
            headers=self.headers,
        )

        response = self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "把当前内容整理成结构化交接物草稿",
                "selected_card_ids": [],
                "material_ids": ["material_003"],
                "mode": "default",
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)

        handoff = self.client.get("/api/canvas/workspaces/demo/handoff", headers=self.headers).json()
        snapshots = self.client.get("/api/canvas/workspaces/demo/snapshots", headers=self.headers).json()

        self.assertIn("结构化交接物草稿", handoff["content"])
        self.assertEqual(len([card for card in self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()["cards"] if card["kind"] == "handoff"]), 1)
        self.assertEqual(len(handoff["handoff"]["open_questions"]), 1)
        self.assertIn("待澄清", handoff["handoff"]["open_questions"][0])
        self.assertEqual(len(handoff["handoff"]["constraints"]), 1)
        self.assertIn("约束", handoff["handoff"]["constraints"][0])
        self.assertEqual(len(snapshots["items"]), 1)
        self.assertEqual(snapshots["items"][0]["handoff"]["summary"], handoff["content"])

    def test_canvas_view_can_load_snapshot_state(self) -> None:
        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "把当前内容整理成结构化交接物草稿",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )
        snapshot = self.client.get("/api/canvas/workspaces/demo/snapshots", headers=self.headers).json()["items"][0]

        current_canvas = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()
        self.assertEqual(current_canvas["snapshot_id"], snapshot["snapshot_id"])

        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "继续补充一期范围的待澄清问题",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )

        snapshot_canvas = self.client.get(
            f"/api/canvas/workspaces/demo/canvas?snapshot_id={snapshot['snapshot_id']}",
            headers=self.headers,
        ).json()
        live_canvas = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()

        self.assertTrue(snapshot_canvas["view_meta"]["is_snapshot"])
        self.assertEqual(snapshot_canvas["snapshot_id"], snapshot["snapshot_id"])
        self.assertLess(len(snapshot_canvas["cards"]), len(live_canvas["cards"]))

    def test_post_message_rejects_when_workspace_already_has_active_turn(self) -> None:
        workspace = self.canvas_service.get_workspace("demo")
        workspace.active_turn_id = "turn_existing"
        workspace.active_turn_status = "running"
        workspace.active_turn_started_at = "2026-06-14T10:00:00Z"
        self.canvas_service.repository.save_workspace(workspace)

        response = self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "继续补充这轮约束",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["reason"], "turn_in_progress")
        self.assertEqual(payload["workspace_id"], "demo")
        self.assertEqual(payload["active_turn"]["turn_id"], "turn_existing")
        self.assertEqual(payload["active_turn"]["status"], "running")

    def test_pending_confirmation_keeps_workspace_busy_until_resolved(self) -> None:
        first = self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "把这次方案取舍整理成需要拍板的待决策项",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["action"], "pending_confirmation")

        blocked = self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "继续补充一期范围的待澄清问题",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["active_turn"]["status"], "awaiting_confirmation")

        confirmations = self.client.get("/api/canvas/workspaces/demo/confirmations", headers=self.headers).json()
        proposal_id = confirmations["items"][0]["proposal_id"]
        approve = self.client.post(
            f"/api/canvas/workspaces/demo/confirmations/{proposal_id}/approve",
            headers=self.headers,
        )
        self.assertEqual(approve.status_code, 200)

        resumed = self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "继续补充一期范围的待澄清问题",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )
        self.assertEqual(resumed.status_code, 200)

    def test_auto_apply_turn_publishes_completed_event(self) -> None:
        event_bus = EventBus()
        storage = FakeStorage(Path(gettempdir()) / "manual-agent-phase1" / f"canvas-turn-events-{uuid4().hex[:8]}", event_bus=event_bus)
        service = CanvasService(storage=storage)
        subscriber = event_bus.subscribe(service.event_stream_id("demo"))

        service.start_turn(
            workspace_id="demo",
            message="继续补充一期范围的待澄清问题",
            selected_card_ids=[],
            material_ids=[],
            mode="default",
        )

        event_types = []
        while True:
            try:
                event_types.append(subscriber.get_nowait().type)
            except queue.Empty:
                break

        self.assertIn("canvas.mutation.applied", event_types)
        self.assertIn("canvas.turn.completed", event_types)

    def test_turn_event_chain_includes_started_and_proposed_payloads(self) -> None:
        event_bus = EventBus()
        storage = FakeStorage(Path(gettempdir()) / "manual-agent-phase1" / f"canvas-turn-chain-{uuid4().hex[:8]}", event_bus=event_bus)
        service = CanvasService(storage=storage)
        subscriber = event_bus.subscribe(service.event_stream_id("demo"))

        result = service.start_turn(
            workspace_id="demo",
            message="继续补充一期范围的待澄清问题",
            selected_card_ids=[],
            material_ids=["material-event"],
            mode="default",
        )

        events = []
        while True:
            try:
                events.append(subscriber.get_nowait())
            except queue.Empty:
                break

        event_types = [event.type for event in events]
        self.assertEqual(event_types[0], "canvas.turn.started")
        self.assertIn("canvas.mutation.proposed", event_types)
        self.assertIn("canvas.mutation.applied", event_types)
        self.assertIn("canvas.turn.completed", event_types)
        proposed = next(event for event in events if event.type == "canvas.mutation.proposed")
        self.assertEqual(proposed.payload["workspace_id"], "demo")
        self.assertEqual(proposed.payload["turn_id"], result["turn_id"])
        self.assertEqual(proposed.payload["proposal_id"], result["proposal_id"])
        self.assertIn("affected_card_ids", proposed.payload)

    def test_confirmation_reject_publishes_event_and_releases_turn(self) -> None:
        event_bus = EventBus()
        storage = FakeStorage(Path(gettempdir()) / "manual-agent-phase1" / f"canvas-reject-events-{uuid4().hex[:8]}", event_bus=event_bus)
        service = CanvasService(storage=storage)
        subscriber = event_bus.subscribe(service.event_stream_id("demo"))
        result = service.start_turn(
            workspace_id="demo",
            message="把这次方案取舍整理成需要拍板的待决策项",
            selected_card_ids=[],
            material_ids=[],
            mode="default",
        )

        rejected = service.reject_confirmation("demo", result["proposal_id"])

        self.assertEqual(rejected["status"], "rejected")
        self.assertIsNone(service.get_canvas_view("demo")["active_turn"])
        event_types = []
        while True:
            try:
                event_types.append(subscriber.get_nowait().type)
            except queue.Empty:
                break
        self.assertIn("canvas.confirmation.requested", event_types)
        self.assertIn("canvas.confirmation.rejected", event_types)

    def test_execute_turn_with_real_llm_proposals(self) -> None:
        import unittest.mock
        from app.core.ports import LLMResult

        mock_llm = unittest.mock.MagicMock()
        mock_llm.api_key = "some_valid_key"
        mock_llm.invoke.side_effect = [
            LLMResult(content='{"intent": "clarification", "roles": ["Clarifier"]}'),
            LLMResult(content='{"title": "大模型提取问题", "summary": "这表明大模型提取确实生效了"}')
        ]

        canvas_service = CanvasService(storage=self.storage, llm=mock_llm)
        turn_data = canvas_service.start_turn(
            workspace_id="demo",
            message="一些复杂的语义输入",
            selected_card_ids=[],
            material_ids=[]
        )

        self.assertEqual(turn_data["intent"], "clarification")
        self.assertEqual(turn_data["action"], "auto_apply")

        canvas = canvas_service.get_canvas_view("demo")
        mock_cards = [c for c in canvas["cards"] if c["title"] == "大模型提取问题"]
        self.assertEqual(len(mock_cards), 1)
        self.assertEqual(mock_cards[0]["summary"], "这表明大模型提取确实生效了")
        self.assertEqual(mock_cards[0]["kind"], "clarification")

    def test_failed_turn_publishes_failed_event_and_releases_turn(self) -> None:
        event_bus = EventBus()
        storage = FakeStorage(Path(gettempdir()) / "manual-agent-phase1" / f"canvas-failed-events-{uuid4().hex[:8]}", event_bus=event_bus)
        service = CanvasService(storage=storage)
        subscriber = event_bus.subscribe(service.event_stream_id("demo"))

        def raise_supervisor_error(**_kwargs):
            raise RuntimeError("supervisor unavailable")

        service.supervisor.recognize_and_plan = raise_supervisor_error

        with self.assertRaises(RuntimeError):
            service.start_turn(
                workspace_id="demo",
                message="继续补充一期范围的待澄清问题",
                selected_card_ids=[],
                material_ids=[],
                mode="default",
            )

        self.assertIsNone(service.get_canvas_view("demo")["active_turn"])
        event_types = []
        while True:
            try:
                event_types.append(subscriber.get_nowait().type)
            except queue.Empty:
                break
        self.assertIn("canvas.turn.started", event_types)
        self.assertIn("canvas.turn.failed", event_types)


if __name__ == "__main__":
    unittest.main()

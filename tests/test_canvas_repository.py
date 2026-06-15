import json
import tempfile
import unittest
from pathlib import Path

from app.canvas.domain.cards import CanvasCard, CanvasCardKind
from app.canvas.domain.mutations import CanvasMutationProposal
from app.canvas.domain.workspace import CanvasWorkspace
from app.canvas.repository import CanvasRepository
from app.services.fakes import FakeStorage


class CanvasRepositoryTests(unittest.TestCase):
    def test_list_workspaces_returns_recent_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FakeStorage(Path(tmpdir))
            repository = CanvasRepository(storage)
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

            repository.save_workspace(workspace_a)
            repository.save_workspace(workspace_b)

            items = repository.list_workspaces()

            self.assertEqual([item.workspace_id for item in items], ["ws_new", "ws_old"])
            self.assertEqual(items[0].title, "最近项目")
            self.assertEqual(items[0].updated_at, "2026-06-12T09:30:00Z")

    def test_save_workspace_persists_under_canvas_workspace_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FakeStorage(Path(tmpdir))
            repository = CanvasRepository(storage)
            workspace = CanvasWorkspace(
                workspace_id="workspace-1",
                title="EvoCanvas 1.0",
                objective="把多源输入收束为结构化交接物。",
                active_snapshot_id="snapshot-1",
                active_turn_id="turn-1",
                active_turn_status="running",
                active_turn_started_at="2026-06-14T10:00:00Z",
                handoff_status="in_progress",
                metadata={"owner_role": "pm"},
                handoff_metadata={"last_handoff_id": "handoff-1"},
            )

            repository.save_workspace(workspace)

            workspace_file = storage.canvas_root() / "workspaces" / "workspace-1" / "workspace.json"
            self.assertTrue(workspace_file.exists())
            self.assertEqual(json.loads(workspace_file.read_text(encoding="utf-8")), workspace.to_dict())
            self.assertEqual(repository.load_workspace("workspace-1"), workspace)

    def test_claim_active_turn_rejects_when_workspace_is_already_busy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FakeStorage(Path(tmpdir))
            repository = CanvasRepository(storage)
            workspace = CanvasWorkspace(
                workspace_id="workspace-1",
                title="EvoCanvas 1.0",
                active_turn_id="turn-existing",
                active_turn_status="running",
                active_turn_started_at="2026-06-14T10:00:00Z",
            )
            repository.save_workspace(workspace)

            claimed = repository.claim_active_turn("workspace-1", "turn-next", "2026-06-14T10:05:00Z")

            self.assertIsNone(claimed)
            loaded = repository.load_workspace("workspace-1")
            self.assertEqual(loaded.active_turn_id, "turn-existing")
            self.assertEqual(loaded.active_turn_status, "running")

    def test_claim_mark_and_release_active_turn_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FakeStorage(Path(tmpdir))
            repository = CanvasRepository(storage)
            workspace = CanvasWorkspace(
                workspace_id="workspace-1",
                title="EvoCanvas 1.0",
            )
            repository.save_workspace(workspace)

            claimed = repository.claim_active_turn("workspace-1", "turn-1", "2026-06-14T10:00:00Z")
            self.assertIsNotNone(claimed)
            self.assertEqual(claimed.active_turn_id, "turn-1")
            self.assertEqual(claimed.active_turn_status, "running")

            awaiting = repository.mark_turn_awaiting_confirmation("workspace-1", "turn-1")
            self.assertIsNotNone(awaiting)
            self.assertEqual(awaiting.active_turn_status, "awaiting_confirmation")

            untouched = repository.release_active_turn("workspace-1", "turn-other")
            self.assertIsNotNone(untouched)
            self.assertEqual(untouched.active_turn_id, "turn-1")

            released = repository.release_active_turn("workspace-1", "turn-1")
            self.assertIsNotNone(released)
            self.assertEqual(released.active_turn_id, "")
            self.assertEqual(released.active_turn_status, "idle")
            self.assertEqual(released.active_turn_started_at, "")

    def test_repository_writes_json_atomically_without_tmp_leftovers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = CanvasRepository(FakeStorage(Path(tmpdir)))

            repository.save_cards(
                "workspace-1",
                [CanvasCard(card_id="card-1", kind=CanvasCardKind.CLARIFICATION, title="确认范围")],
            )

            workspace_dir = repository._workspace_dir("workspace-1")
            self.assertTrue((workspace_dir / "cards.json").exists())
            self.assertEqual(list(workspace_dir.glob("*.tmp")), [])

    def test_repository_appends_proposal_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = CanvasRepository(FakeStorage(Path(tmpdir)))
            proposal = CanvasMutationProposal(
                proposal_id="proposal-history-1",
                workspace_id="workspace-1",
                turn_id="turn-history-1",
            )

            repository.append_proposal_history("workspace-1", proposal)

            history = repository.load_proposal_history("workspace-1")
            self.assertEqual([item.proposal_id for item in history], ["proposal-history-1"])
            history_file = repository._workspace_dir("workspace-1") / "proposal_history.jsonl"
            self.assertTrue(history_file.exists())


if __name__ == "__main__":
    unittest.main()

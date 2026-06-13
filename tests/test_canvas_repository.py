import json
import tempfile
import unittest
from pathlib import Path

from app.canvas.domain.workspace import CanvasWorkspace
from app.canvas.repository import CanvasRepository
from app.services.fakes import FakeStorage


class CanvasRepositoryTests(unittest.TestCase):
    def test_save_workspace_persists_under_canvas_workspace_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FakeStorage(Path(tmpdir))
            repository = CanvasRepository(storage)
            workspace = CanvasWorkspace(
                workspace_id="workspace-1",
                title="EvoCanvas 1.0",
                objective="把多源输入收束为结构化交接物。",
                active_snapshot_id="snapshot-1",
                handoff_status="in_progress",
                metadata={"owner_role": "pm"},
                handoff_metadata={"last_handoff_id": "handoff-1"},
            )

            repository.save_workspace(workspace)

            workspace_file = storage.canvas_root() / "workspaces" / "workspace-1" / "workspace.json"
            self.assertTrue(workspace_file.exists())
            self.assertEqual(json.loads(workspace_file.read_text(encoding="utf-8")), workspace.to_dict())
            self.assertEqual(repository.load_workspace("workspace-1"), workspace)


if __name__ == "__main__":
    unittest.main()

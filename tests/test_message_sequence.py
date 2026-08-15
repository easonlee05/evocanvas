"""Chat message_seq 的兼容补序和单调追加测试。"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.canvas.repository import CanvasRepository
from app.services.fakes import FakeStorage


class MessageSequenceTests(unittest.TestCase):
    def test_new_messages_get_monotonic_sequence(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = CanvasRepository(FakeStorage(Path(temp_dir)))
            first = repository.append_chat_message("workspace-1", {"message_id": "m-1", "role": "user", "content": "one"})
            second = repository.append_chat_message("workspace-1", {"message_id": "m-2", "role": "assistant", "content": "two"})

            self.assertEqual(first["message_seq"], 1)
            self.assertEqual(second["message_seq"], 2)
            self.assertEqual(repository.last_message_seq("workspace-1"), 2)

    def test_legacy_messages_are_read_with_sequence_and_next_append_continues(self) -> None:
        with TemporaryDirectory() as temp_dir:
            storage = FakeStorage(Path(temp_dir))
            messages_dir = storage.canvas_root() / "workspaces" / "workspace-1"
            messages_dir.mkdir(parents=True)
            (messages_dir / "chat_messages.jsonl").write_text(
                json.dumps({"message_id": "legacy-1", "role": "user", "content": "old"}) + "\n"
                + json.dumps({"message_id": "legacy-2", "role": "assistant", "content": "old reply"}) + "\n",
                encoding="utf-8",
            )
            repository = CanvasRepository(storage)

            self.assertEqual([item["message_seq"] for item in repository.load_chat_messages("workspace-1")], [1, 2])
            appended = repository.append_chat_message("workspace-1", {"message_id": "new-1", "role": "user", "content": "new"})

            self.assertEqual(appended["message_seq"], 3)
            self.assertEqual([item["message_seq"] for item in repository.load_chat_messages("workspace-1")], [1, 2, 3])

    def test_caller_cannot_skip_message_sequence(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = CanvasRepository(FakeStorage(Path(temp_dir)))
            with self.assertRaisesRegex(ValueError, "next workspace sequence: 1"):
                repository.append_chat_message(
                    "workspace-1",
                    {"message_id": "m-1", "role": "user", "content": "one", "message_seq": 4},
                )


if __name__ == "__main__":
    unittest.main()

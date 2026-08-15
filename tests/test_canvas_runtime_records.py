"""四类运行记录和包级租约的持久化/并发边界测试。"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from app.canvas.domain.runtime_records import (
    ChatTurnRecord,
    CommitAttemptRecord,
    ConvergenceJudgementRecord,
    ConvergenceRunRecord,
    OutboxEntry,
)
from app.canvas.repository import CanvasRepository
from app.services.fakes import FakeStorage


NOW = "2026-08-15T10:00:00Z"


class CanvasRuntimeRecordTests(unittest.TestCase):
    def test_four_records_are_upserted_without_creating_duplicate_facts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = CanvasRepository(FakeStorage(Path(temp_dir)))
            repository.save_chat_turn(ChatTurnRecord("chat-1", "ws-1", "conversation-1", "pkg-1", 2, "completed", NOW, NOW))
            repository.save_chat_turn(ChatTurnRecord("chat-1", "ws-1", "conversation-1", "pkg-1", 2, "failed", NOW, NOW, failure_code="run_failed"))
            repository.save_convergence_judgement(
                ConvergenceJudgementRecord("judge-1", "chat-1", "ws-1", "pkg-1", 2, "completed", "defer", ("not_ready",), NOW, NOW)
            )
            repository.save_convergence_run(
                ConvergenceRunRecord("conv-1", "ws-1", "pkg-1", 1, 2, 3, 2, "stale", "not_ready", NOW, NOW, failure_code="base_version_changed")
            )
            repository.save_commit_attempt(
                CommitAttemptRecord("commit-1", "op-1", "ws-1", "pkg-1", 3, 2, "unknown", NOW, NOW, error_code="commit_unknown")
            )

            records = repository.load_runtime_records("ws-1")
            self.assertEqual(len(records), 4)
            self.assertEqual(repository.load_chat_turn("ws-1", "chat-1").status, "failed")
            self.assertEqual(repository.load_convergence_run("ws-1", "conv-1").failure_code, "base_version_changed")
            self.assertEqual(repository.load_commit_attempt("ws-1", "commit-1").error_code, "commit_unknown")

    def test_package_lease_conflict_and_owner_release(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = CanvasRepository(FakeStorage(Path(temp_dir)))
            now = datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc)
            lease = repository.acquire_package_lease("ws-1", "pkg-1", "run-1", ttl_seconds=30, now=now)
            self.assertIsNotNone(lease)
            self.assertIsNone(repository.acquire_package_lease("ws-1", "pkg-1", "run-2", ttl_seconds=30, now=now + timedelta(seconds=1)))
            self.assertFalse(repository.release_package_lease("ws-1", "pkg-1", lease.lease_id, "run-2"))
            self.assertTrue(repository.release_package_lease("ws-1", "pkg-1", lease.lease_id, "run-1"))
            self.assertIsNone(repository.load_package_lease("ws-1", "pkg-1"))

    def test_expired_lease_can_be_reclaimed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = CanvasRepository(FakeStorage(Path(temp_dir)))
            now = datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc)
            first = repository.acquire_package_lease("ws-1", "pkg-1", "run-1", ttl_seconds=1, now=now)
            reclaimed = repository.acquire_package_lease("ws-1", "pkg-1", "run-2", ttl_seconds=30, now=now + timedelta(seconds=2))
            self.assertNotEqual(first.lease_id, reclaimed.lease_id)
            self.assertEqual(reclaimed.holder_run_id, "run-2")

    def test_judgement_watermark_only_moves_forward(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = CanvasRepository(FakeStorage(Path(temp_dir)))
            self.assertTrue(repository.advance_judgement_watermark("ws-1", "conversation-1", "pkg-1", 4))
            self.assertFalse(repository.advance_judgement_watermark("ws-1", "conversation-1", "pkg-1", 4))
            self.assertFalse(repository.advance_judgement_watermark("ws-1", "conversation-1", "pkg-1", 3))
            self.assertTrue(repository.advance_judgement_watermark("ws-1", "conversation-1", "pkg-1", 5))
            self.assertEqual(repository.load_judgement_watermark("ws-1", "conversation-1", "pkg-1"), 5)

    def test_outbox_entry_is_upserted_and_recovery_can_mark_sent(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = CanvasRepository(FakeStorage(Path(temp_dir)))
            entry = OutboxEntry("outbox-1", "ws-1", "pkg-1", "op-1", "projection.refresh", {"version": 2}, "pending", 0, NOW, NOW)
            repository.enqueue_outbox(entry)
            sent = repository.mark_outbox("ws-1", "outbox-1", status="sent", updated_at="2026-08-15T10:01:00Z", increment_attempts=True)

            self.assertEqual(sent.status, "sent")
            self.assertEqual(sent.attempts, 1)
            self.assertEqual(repository.load_outbox("ws-1", status="pending"), [])


if __name__ == "__main__":
    unittest.main()

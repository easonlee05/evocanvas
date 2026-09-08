"""Pi Canvas 主链的目标架构集成边界测试。"""

from __future__ import annotations

import queue
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.canvas.agent_execution.contracts import (
    ConvergenceProposal,
    TraceContext,
    UserSubmissionReceipt,
    WorkspaceCommitResult,
)
from app.canvas.repository import PackageVersionStaleError
from app.canvas.service import CanvasService, CanvasTurnInProgressError
from app.core.events import EventBus, utc_now_iso
from app.services.fakes import FakeStorage


class TargetPiExecution:
    """目标架构下 Pi Agent Execution 测试替身。"""

    def __init__(self) -> None:
        self.submissions = []
        self.commits = []

    async def submit_user_message(self, request):
        self.submissions.append(request)
        return UserSubmissionReceipt(
            submission_id=request.submission_id,
            content_hash=request.content_hash,
            session_id=f"session_{request.workspace_id}",
            entry_id=f"entry_{request.submission_id}",
            status="accepted",
            binding_status="ready",
        )

    async def run_workspace(self, workspace_id, submission_id, **kwargs):
        return {"action": "chat_only", "assistant_entry_id": "assistant-entry", "assistant_message": "请补充使用场景"}

    async def get_projection(self, workspace_id):
        return {"projected_revision_id": "rev_0"}

    async def get_revision(self, workspace_id, revision_id):
        return {"objects": {}, "relations": []}

    async def get_messages(self, workspace_id):
        return {"session_id": "session", "messages": [
            {"id": "user-entry", "timestamp": 1000, "message": {"role": "user", "content": self.submissions[-1].pi_user_message["content"]}},
            {"id": "assistant-entry", "timestamp": 2000, "message": {"role": "assistant", "content": "请补充使用场景", "stopReason": "stop"}},
        ]}


class FailingExecution(TargetPiExecution):
    async def submit_user_message(self, request):
        raise RuntimeError("runtime unavailable")


class PiCanvasKernelTests(unittest.IsolatedAsyncioTestCase):
    async def test_pi_turn_uses_session_entries_without_legacy_supervisor(self) -> None:
        with TemporaryDirectory() as temp_dir:
            execution = TargetPiExecution()
            service = CanvasService(
                storage=FakeStorage(Path(temp_dir)),
                execution=execution,
            )

            result = await service.run_pi_turn(
                workspace_id="workspace-1",
                message="请列出当前最需要确认的问题",
                selected_card_ids=[],
                material_ids=[],
                source_ref_ids=[],
            )

            self.assertEqual(result["action"], "chat_only")
            self.assertEqual(len(service.repository.load_cards("workspace-1")), 0)
            self.assertEqual(len(execution.submissions), 1)
            self.assertEqual(execution.submissions[0].workspace_id, "workspace-1")
            self.assertEqual(len(execution.commits), 0)
            self.assertEqual(result["assistant_message_id"], "assistant-entry")
            self.assertEqual(len(service.repository.load_chat_messages("workspace-1")), 2)

    async def test_pi_turn_enforces_active_turn_lock(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = CanvasService(
                storage=FakeStorage(Path(temp_dir)),
                execution=TargetPiExecution(),
            )
            service.get_workspace("workspace-1")
            self.assertIsNotNone(
                service.repository.claim_active_turn("workspace-1", "existing-turn", "2026-08-19T00:00:00Z")
            )

            with self.assertRaises(CanvasTurnInProgressError):
                await service.run_pi_turn(
                    workspace_id="workspace-1",
                    message="已有活跃回合时必须拒绝并发",
                    selected_card_ids=[],
                    material_ids=[],
                    source_ref_ids=[],
                )

    async def test_stale_pi_proposal_is_rejected_before_commit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = CanvasService(
                storage=FakeStorage(Path(temp_dir)),
                execution=TargetPiExecution(),
            )
            service.start_turn(
                workspace_id="workspace-1", message="先建立一个当前包版本", selected_card_ids=[], material_ids=[], source_ref_ids=[],
            )
            stale = ConvergenceProposal(
                "evocanvas.convergence-proposal.v1",
                "proposal-stale",
                "run-stale",
                "pkg_workspace-1",
                1,
                2,
                0,
                0,
                (),
            )

            with self.assertRaises(PackageVersionStaleError):
                await service.pi_kernel.submit_convergence_proposal(
                    proposal=stale,
                    trace_context=TraceContext(
                        "trace-stale",
                        "request-stale",
                        extra={"workspace_id": "workspace-1"},
                    ),
                )

    async def test_pi_failure_closes_canvas_event_stream_with_failed_event(self) -> None:
        with TemporaryDirectory() as temp_dir:
            event_bus = EventBus()
            storage = FakeStorage(Path(temp_dir), event_bus=event_bus)
            service = CanvasService(storage=storage, execution=FailingExecution())
            events = event_bus.subscribe(service.event_stream_id("workspace-1"))

            with self.assertRaisesRegex(RuntimeError, "runtime unavailable"):
                await service.run_pi_turn(
                    workspace_id="workspace-1",
                    message="触发一次运行失败",
                    selected_card_ids=[],
                    material_ids=[],
                    source_ref_ids=[],
                )

            event_types = []
            while True:
                try:
                    event_types.append(events.get_nowait().type)
                except queue.Empty:
                    break
            self.assertEqual(event_types, ["canvas.turn.started", "canvas.turn.failed"])


if __name__ == "__main__":
    unittest.main()

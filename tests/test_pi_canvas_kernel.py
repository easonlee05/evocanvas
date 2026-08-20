"""Pi Canvas 主链的 Python 集成边界测试。"""

from __future__ import annotations

import queue
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.canvas.agent_execution.contracts import (
    AssistantMessage,
    ChatRunResult,
    ConvergenceProposal,
    ConvergenceRunResult,
    JudgementRunResult,
    ModelIdentity,
    ProposalOperation,
    TraceContext,
    Usage,
)
from app.canvas.service import CanvasService
from app.core.events import EventBus
from app.services.fakes import FakeStorage


USAGE = Usage(0, 0, 0, None)
MODEL = ModelIdentity("test-provider", "test-model", "test-adapter:v1", "pi-runtime.protocol.v1")


class TriggeringExecution:
    async def run_chat(self, request):
        return ChatRunResult(
            request.run_id,
            AssistantMessage(({"type": "text", "text": "已收到，继续收敛。"},)),
            "completed",
            {},
            USAGE,
            MODEL,
            request.context_manifest.context_manifest_id,
        )

    async def run_judgement(self, request):
        return JudgementRunResult(
            request.run_id,
            "trigger",
            ("new_structural_signal",),
            request.through_message_seq,
            0.9,
            USAGE,
            MODEL,
            request.context_manifest.context_manifest_id,
        )

    async def run_convergence(self, request):
        proposal = ConvergenceProposal(
            "evocanvas.convergence-proposal.v1",
            "proposal-test",
            request.run_id,
            request.package_id,
            request.from_message_seq,
            request.through_message_seq,
            request.base_state_version,
            request.base_package_version,
            (
                ProposalOperation(
                    "operation-test",
                    "add_clarification",
                    None,
                    "temporary-clarification",
                    None,
                    {
                        "kind": "clarification",
                        "title": "待澄清：目标用户",
                        "summary": "需要先确认首版目标用户。",
                    },
                    ("message-source",),
                    (),
                    ("missing-user-segment",),
                    "low",
                    ("surface_gap",),
                    None,
                ),
            ),
        )
        return ConvergenceRunResult(
            request.run_id,
            proposal,
            "completed",
            (),
            USAGE,
            MODEL,
            request.context_manifest.context_manifest_id,
        )

    async def cancel(self, request):
        raise AssertionError("cancel is not used in this test")


class FailingExecution:
    async def run_chat(self, request):
        raise RuntimeError("runtime unavailable")

    async def run_judgement(self, request):
        raise AssertionError("judgement must not start after Chat failure")

    async def run_convergence(self, request):
        raise AssertionError("convergence must not start after Chat failure")

    async def cancel(self, request):
        raise AssertionError("cancel is not used in this test")


class PiCanvasKernelTests(unittest.IsolatedAsyncioTestCase):
    async def test_pi_turn_persists_runtime_records_and_commits_projection(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = CanvasService(
                storage=FakeStorage(Path(temp_dir)),
                execution=TriggeringExecution(),
            )

            result = await service.run_pi_turn(
                workspace_id="workspace-1",
                message="请列出当前最需要确认的问题",
                selected_card_ids=[],
                material_ids=[],
                source_ref_ids=[],
            )

            self.assertEqual(result["action"], "applied")
            self.assertEqual(len(service.repository.load_cards("workspace-1")), 1)
            self.assertEqual(service.repository.load_active_package_version("workspace-1").package_version, 1)
            records = service.repository.load_runtime_records("workspace-1")
            self.assertEqual(
                {record["record_type"] for record in records},
                {"chat_turn", "convergence_judgement", "convergence_run", "commit_attempt", "outbox_entry"},
            )
            self.assertEqual(len(service.repository.load_chat_messages("workspace-1")), 2)

    async def test_pi_turn_does_not_use_workspace_active_turn_lock(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = CanvasService(
                storage=FakeStorage(Path(temp_dir)),
                execution=TriggeringExecution(),
            )
            service.get_workspace("workspace-1")
            self.assertIsNotNone(
                service.repository.claim_active_turn("workspace-1", "legacy-turn", "2026-08-19T00:00:00Z")
            )

            result = await service.run_pi_turn(
                workspace_id="workspace-1",
                message="即使旧回合字段存在，也应先接住新消息",
                selected_card_ids=[],
                material_ids=[],
                source_ref_ids=[],
            )

            self.assertEqual(result["action"], "applied")
            self.assertEqual(len(service.repository.load_chat_messages("workspace-1")), 2)

    async def test_stale_pi_proposal_is_rejected_before_commit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = CanvasService(
                storage=FakeStorage(Path(temp_dir)),
                execution=TriggeringExecution(),
            )
            await service.run_pi_turn(
                workspace_id="workspace-1",
                message="先建立一个当前包版本",
                selected_card_ids=[],
                material_ids=[],
                source_ref_ids=[],
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

            with self.assertRaisesRegex(ValueError, "base version changed"):
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

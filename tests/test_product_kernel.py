"""阶段 3 Product Kernel 职责边界测试。"""

from __future__ import annotations

import unittest
from typing import Any, Mapping

from app.canvas.agent_execution.contracts import (
    AssistantMessage,
    ChatRunRequest,
    ChatRunResult,
    ConvergenceProposal,
    ConvergenceRunRequest,
    ConvergenceRunResult,
    JudgementRunRequest,
    JudgementRunResult,
    ModelIdentity,
    Usage,
)
from app.canvas.product_kernel import ProductKernel


USAGE = Usage(0, 0, 0, None)
MODEL = ModelIdentity("fake-provider", "fake-model", "fake-adapter:v1", "pi-runtime.protocol.v1")


class FakeExecution:
    def __init__(self, chat_result: ChatRunResult, judgement_result: JudgementRunResult, convergence_result: ConvergenceRunResult) -> None:
        self.chat_result = chat_result
        self.judgement_result = judgement_result
        self.convergence_result = convergence_result
        self.calls: list[str] = []

    async def run_chat(self, request: ChatRunRequest) -> ChatRunResult:
        self.calls.append(f"chat:{request.run_id}")
        return self.chat_result

    async def run_judgement(self, request: JudgementRunRequest) -> JudgementRunResult:
        self.calls.append(f"judgement:{request.run_id}")
        return self.judgement_result

    async def run_convergence(self, request: ConvergenceRunRequest) -> ConvergenceRunResult:
        self.calls.append(f"convergence:{request.run_id}")
        return self.convergence_result

    async def cancel(self, request: Any) -> Any:
        raise AssertionError("cancel is not part of this scenario")


class MessageSink:
    def __init__(self) -> None:
        self.messages: list[Mapping[str, Any]] = []

    async def append_assistant_message(self, **kwargs: Any) -> str:
        self.messages.append(kwargs)
        return f"message-{len(self.messages)}"


class CommitSink:
    def __init__(self) -> None:
        self.proposals: list[ConvergenceProposal] = []

    async def submit_convergence_proposal(self, *, proposal: ConvergenceProposal, trace_context: Any) -> Mapping[str, Any]:
        self.proposals.append(proposal)
        return {"result": "applied", "operation_id": "op-1"}


def _chat_result(run_id: str, *, completed: bool = True) -> ChatRunResult:
    return ChatRunResult(
        run_id=run_id,
        assistant_message=AssistantMessage(({"type": "text", "text": "ok"},)) if completed else None,
        finish_reason="completed" if completed else "error",
        events_summary={},
        usage=USAGE,
        model_identity=MODEL,
        context_manifest_id="manifest-1",
    )


def _judgement_result(run_id: str, decision: str = "defer") -> JudgementRunResult:
    return JudgementRunResult(run_id, decision, ("insufficient_signal",), 2, None, USAGE, MODEL, "manifest-1")  # type: ignore[arg-type]


def _proposal(run_id: str) -> ConvergenceProposal:
    return ConvergenceProposal("evocanvas.convergence-proposal.v1", "proposal-1", run_id, "pkg-1", 1, 2, 3, 2, ())


def _convergence_result(run_id: str, *, proposal: ConvergenceProposal | None) -> ConvergenceRunResult:
    return ConvergenceRunResult(run_id, proposal, "completed" if proposal else "not_ready", (), USAGE, MODEL, "manifest-1")  # type: ignore[arg-type]


class ProductKernelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.chat_request = object()  # replaced by a request-like fixture below

    async def test_completed_chat_persists_once_and_never_commits(self) -> None:
        execution = FakeExecution(_chat_result("chat-1"), _judgement_result("judge-1"), _convergence_result("conv-1", proposal=None))
        messages = MessageSink()
        commits = CommitSink()
        kernel = ProductKernel(execution=execution, assistant_messages=messages, governed_commit=commits)
        request = _request_fixture(ChatRunRequest)

        outcome = await kernel.run_chat(request)

        self.assertEqual(outcome.assistant_message_id, "message-1")
        self.assertEqual(len(messages.messages), 1)
        self.assertEqual(commits.proposals, [])

    async def test_failed_chat_does_not_persist_error_as_assistant(self) -> None:
        execution = FakeExecution(_chat_result("chat-1", completed=False), _judgement_result("judge-1"), _convergence_result("conv-1", proposal=None))
        messages = MessageSink()
        kernel = ProductKernel(execution=execution, assistant_messages=messages, governed_commit=CommitSink())

        outcome = await kernel.run_chat(_request_fixture(ChatRunRequest))

        self.assertIsNone(outcome.assistant_message_id)
        self.assertEqual(messages.messages, [])

    async def test_judgement_is_explicit_and_does_not_start_convergence(self) -> None:
        execution = FakeExecution(_chat_result("chat-1"), _judgement_result("judge-1", "trigger"), _convergence_result("conv-1", proposal=None))
        kernel = ProductKernel(execution=execution, assistant_messages=MessageSink(), governed_commit=CommitSink())

        outcome = await kernel.run_judgement(_request_fixture(JudgementRunRequest))

        self.assertEqual(outcome.result.decision, "trigger")
        self.assertEqual(execution.calls, ["judgement:judge-1"])

    async def test_convergence_only_submits_complete_proposal_once(self) -> None:
        proposal = _proposal("conv-1")
        execution = FakeExecution(_chat_result("chat-1"), _judgement_result("judge-1"), _convergence_result("conv-1", proposal=proposal))
        commits = CommitSink()
        kernel = ProductKernel(execution=execution, assistant_messages=MessageSink(), governed_commit=commits)

        outcome = await kernel.run_convergence(_request_fixture(ConvergenceRunRequest))

        self.assertEqual(outcome.commit_result, {"result": "applied", "operation_id": "op-1"})
        self.assertEqual(commits.proposals, [proposal])

    async def test_not_ready_convergence_does_not_call_commit(self) -> None:
        execution = FakeExecution(_chat_result("chat-1"), _judgement_result("judge-1"), _convergence_result("conv-1", proposal=None))
        commits = CommitSink()
        kernel = ProductKernel(execution=execution, assistant_messages=MessageSink(), governed_commit=commits)

        outcome = await kernel.run_convergence(_request_fixture(ConvergenceRunRequest))

        self.assertIsNone(outcome.commit_result)
        self.assertEqual(commits.proposals, [])


def _request_fixture(request_type: Any) -> Any:
    """测试只需要通过类型检查的最小请求；运行时字段由合同测试覆盖。"""
    from tests.test_pi_runtime_client import _chat_request

    if request_type is ChatRunRequest:
        return _chat_request("chat-1")
    if request_type is JudgementRunRequest:
        base = _chat_request("judge-1")
        return JudgementRunRequest(
            run_id="judge-1",
            run_kind="judgement",
            workspace_id=base.workspace_id,
            conversation_id=base.conversation_id,
            from_message_seq=base.from_message_seq,
            through_message_seq=base.through_message_seq,
            context_manifest=base.context_manifest.__class__(**{**base.context_manifest.__dict__, "request_kind": "judgement"}),
            instructions_ref=base.instructions_ref,
            model_policy=base.model_policy,
            tool_profile=base.tool_profile.__class__("judgement", (), 0, 65536),
            deadline_ms=base.deadline_ms,
            trace_context=base.trace_context,
            idempotency_key="judge-1",
            chat_turn_id="chat-1",
            base_state_version=3,
            base_package_version=2,
            signal_summary_ref="signal-1",
        )
    base = _chat_request("conv-1")
    return ConvergenceRunRequest(
        run_id="conv-1",
        run_kind="convergence",
        workspace_id=base.workspace_id,
        conversation_id=base.conversation_id,
        from_message_seq=base.from_message_seq,
        through_message_seq=base.through_message_seq,
        context_manifest=base.context_manifest.__class__(**{**base.context_manifest.__dict__, "request_kind": "convergence"}),
        instructions_ref=base.instructions_ref,
        model_policy=base.model_policy,
        tool_profile=base.tool_profile.__class__("convergence", (), 0, 65536),
        deadline_ms=base.deadline_ms,
        trace_context=base.trace_context,
        idempotency_key="conv-1",
        package_id="pkg-1",
        convergence_run_id="conv-1",
        base_state_version=3,
        base_package_version=2,
        proposal_schema_ref="proposal:v1",
        proposal_capture_tool_ref="submit_convergence_proposal:v1",
    )


if __name__ == "__main__":
    unittest.main()

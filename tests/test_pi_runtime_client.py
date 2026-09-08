"""Python ↔ TypeScript Pi Runtime 的最小跨语言合同调用测试。"""

from __future__ import annotations

import asyncio
import json
import unittest
from typing import Any, Mapping

from app.canvas.agent_execution.contracts import (
    CancelRequest,
    ChatRunRequest,
    ContextManifest,
    MessageScope,
    ModelPolicy,
    PackageRef,
    StructuredPackageInputRef,
    ToolProfile,
    TraceContext,
)
from app.canvas.agent_execution.pi_client import (
    HttpResponse,
    PiRuntimeClient,
    PiRuntimeError,
    PiRuntimeUnknownError,
)


def _trace() -> TraceContext:
    return TraceContext(trace_id="trace-1", request_id="request-1")


def _manifest(kind: str = "chat") -> ContextManifest:
    return ContextManifest(
        context_manifest_id="manifest-1",
        request_kind=kind,  # type: ignore[arg-type]
        package_ref=PackageRef(package_id="pkg-1", package_version=2, state_version=3),
        structured_package_input_ref=StructuredPackageInputRef(id="input-1", content_hash="sha256:input"),
        message_scope=MessageScope(from_seq=1, through_seq=2, raw_user_message_ref="msg-2"),
        instruction_and_schema_refs=("instructions:v1", "assistant:v1"),
        source_refs=("source-1",),
        included_sections=("package", "messages"),
        omissions=(),
        assembly_policy_version="assembly:v1",
        budget_ref="budget:v1",
        degradation_flags=(),
        content_hashes={"package": "sha256:package"},
        transport_ref={"provider_id": "fake-provider", "adapter_version": "fake-adapter:v1", "protocol_version": "pi-runtime.protocol.v1"},
    )


def _chat_request(run_id: str = "run-1") -> ChatRunRequest:
    return ChatRunRequest(
        run_id=run_id,
        run_kind="chat",
        workspace_id="workspace-1",
        conversation_id="conversation-1",
        from_message_seq=1,
        through_message_seq=2,
        context_manifest=_manifest(),
        instructions_ref="instructions:v1",
        model_policy=ModelPolicy("balanced", "interactive", True, False),
        tool_profile=ToolProfile("chat", (), 0, 65536),
        deadline_ms=5000,
        trace_context=_trace(),
        idempotency_key=run_id,
        package_id="pkg-1",
        raw_user_message_ref="msg-2",
        assistant_reply_schema_ref="assistant:v1",
        conversation_order_key="conversation-1:2",
    )


def _event(run_id: str, sequence: int, event_type: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "pi-runtime.event.v1",
        "event_id": f"event-{sequence}",
        "run_id": run_id,
        "sequence": sequence,
        "timestamp": "2026-08-14T10:00:00.000Z",
        "type": event_type,
        "trace_context": _trace().to_payload(),
        "payload": dict(payload or {}),
    }


def _chat_result(run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "assistant_message": {"content_blocks": [{"type": "text", "text": "收到"}]},
        "finish_reason": "completed",
        "events_summary": {"provider": "fake-provider", "tool_calls": 0},
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "provider_usage_ref": None},
        "model_identity": {"provider_id": "fake-provider", "model_id": "fake-chat", "adapter_version": "fake-adapter:v1", "protocol_version": "pi-runtime.protocol.v1"},
        "context_manifest_id": "manifest-1",
    }


class FakeTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, bytes | None, Mapping[str, str], float]] = []

    def __call__(self, method: str, url: str, body: bytes | None, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        self.calls.append((method, url, body, headers, timeout))
        if not self.responses:
            raise AssertionError("unexpected HTTP call")
        return self.responses.pop(0)


class PiRuntimeClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_stream_is_parsed_then_terminal_result_is_loaded(self) -> None:
        run_id = "run-1"
        events = b"\n".join(
            json.dumps(_event(run_id, sequence, event_type)).encode("utf-8")
            for sequence, event_type in ((1, "run.started"), (2, "assistant.completed"), (3, "run.completed"))
        ) + b"\n"
        summary = {
            "schema_version": "pi-runtime.run-summary.v1",
            "run_id": run_id,
            "run_kind": "chat",
            "status": "completed",
            "event_sequence": 3,
            "result": _chat_result(run_id),
            "error": None,
            "events": [_event(run_id, 1, "run.started"), _event(run_id, 2, "assistant.completed"), _event(run_id, 3, "run.completed")],
        }
        transport = FakeTransport([
            HttpResponse(200, events, {"content-type": "application/x-ndjson"}),
            HttpResponse(200, json.dumps(summary).encode("utf-8"), {"content-type": "application/json"}),
        ])
        observed: list[int] = []
        client = PiRuntimeClient(transport=transport, event_handler=lambda event: observed.append(event.sequence))

        result = await client.run_chat(_chat_request(run_id))

        self.assertEqual(result.run_id, run_id)
        self.assertEqual(result.assistant_message.content_blocks[0]["text"], "收到")
        self.assertEqual(observed, [1, 2, 3])
        self.assertEqual([call[0] for call in transport.calls], ["POST", "GET"])
        request_payload = json.loads(transport.calls[0][2].decode("utf-8"))
        self.assertEqual(request_payload["schema_version"], "pi-runtime.request.v1")
        self.assertEqual(request_payload["context_manifest"]["context_manifest_id"], "manifest-1")

    async def test_terminal_query_failure_is_unknown_and_keeps_same_run_id(self) -> None:
        run_id = "run-unknown"
        events = json.dumps(_event(run_id, 1, "run.started")).encode("utf-8") + b"\n"
        error = {"schema_version": "pi-runtime.error.v1", "error_code": "run_not_found", "category": "input_error", "message": "gone", "retryable": False}
        transport = FakeTransport([
            HttpResponse(200, events, {}),
            HttpResponse(404, json.dumps(error).encode("utf-8"), {}),
        ])
        client = PiRuntimeClient(transport=transport)

        with self.assertRaises(PiRuntimeUnknownError) as raised:
            await client.run_chat(_chat_request(run_id))

        self.assertEqual(raised.exception.run_id, run_id)
        self.assertTrue(raised.exception.details["retry_same_run_id"])
        self.assertIn(f"/v1/runs/{run_id}", transport.calls[1][1])

    async def test_http_error_preserves_stable_error_code(self) -> None:
        error = {"schema_version": "pi-runtime.error.v1", "error_code": "run_id_conflict", "category": "input_error", "message": "conflict", "retryable": False}
        transport = FakeTransport([HttpResponse(409, json.dumps(error).encode("utf-8"), {})])
        client = PiRuntimeClient(transport=transport)

        with self.assertRaises(PiRuntimeError) as raised:
            await client.run_chat(_chat_request())

        self.assertEqual(raised.exception.error_code, "run_id_conflict")
        self.assertEqual(raised.exception.http_status, 409)
        self.assertFalse(raised.exception.retryable)

    async def test_cancel_uses_cancel_contract_and_auth_header(self) -> None:
        response = {"schema_version": "pi-runtime.cancel-result.v1", "run_id": "run-1", "status": "cancelled", "event_sequence": 4}
        transport = FakeTransport([HttpResponse(200, json.dumps(response).encode("utf-8"), {})])
        client = PiRuntimeClient(internal_secret="secret", transport=transport)

        result = await client.cancel(CancelRequest("run-1", "user_cancelled", "python-product-kernel", _trace()))

        self.assertEqual(result.status, "cancelled")
        self.assertEqual(transport.calls[0][0], "POST")
        self.assertTrue(transport.calls[0][1].endswith("/v1/runs/run-1/cancel"))
        self.assertEqual(transport.calls[0][3]["Authorization"], "Bearer secret")
        self.assertEqual(json.loads(transport.calls[0][2].decode("utf-8"))["schema_version"], "pi-runtime.cancel.v1")

    async def test_invalid_event_sequence_is_protocol_error(self) -> None:
        run_id = "run-invalid"
        body = b"\n".join(json.dumps(_event(run_id, sequence, "run.started")).encode("utf-8") for sequence in (1, 1))
        transport = FakeTransport([HttpResponse(200, body, {})])
        client = PiRuntimeClient(transport=transport)

        with self.assertRaises(PiRuntimeError) as raised:
            await client.run_chat(_chat_request(run_id))

        self.assertEqual(raised.exception.error_code, "protocol_error")


    async def test_workspace_transport_failure_never_fabricates_success(self):
        from app.canvas.agent_execution.contracts import UserSubmissionRequest, WorkspaceCommitRequest, SessionLifecycleCommand
        def disconnected(*_args):
            raise OSError("disconnected")
        client = PiRuntimeClient(transport=disconnected)
        requests = [
            lambda: client.submit_user_message(UserSubmissionRequest("s", "hash", "w", "u", {"role":"user","content":"hi"})),
            lambda: client.commit_workspace(WorkspaceCommitRequest({"workspace_id":"w"}, "rev_0", "key", "hash", [], [], "edit")),
            lambda: client.session_lifecycle(SessionLifecycleCommand("op", "w", "archive", "key")),
            lambda: client.get_projection("w"), lambda: client.get_revision("w", "rev_0"), lambda: client.get_binding("w"),
        ]
        for call in requests:
            with self.subTest(call=call), self.assertRaises(PiRuntimeError) as raised:
                await call()
            self.assertEqual(raised.exception.error_code, "runtime.transport_unknown")

    async def test_same_workspace_id_is_isolated_by_tenant_namespace(self):
        transport = FakeTransport([HttpResponse(200, b'{"projected_revision_id":"rev_0"}', {}) for _ in range(2)])
        await PiRuntimeClient(transport=transport, workspace_namespace="tenant-a").get_projection("demo")
        await PiRuntimeClient(transport=transport, workspace_namespace="tenant-b").get_projection("demo")
        self.assertNotEqual(transport.calls[0][1], transport.calls[1][1])


if __name__ == "__main__":
    unittest.main()

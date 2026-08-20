"""Pi Runtime 内部 Tool Gateway 的权限与事实边界测试。"""

from __future__ import annotations

import asyncio
import unittest

from app.canvas.tool_gateway import RunScopedTokenCodec, ToolGateway, ToolGatewayError


class ToolGatewayTests(unittest.IsolatedAsyncioTestCase):
    def _gateway(self) -> ToolGateway:
        gateway = ToolGateway(RunScopedTokenCodec("test-secret"))

        def read_source(context):
            return {
                "status": "succeeded",
                "summary": "source read",
                "data": {"source_ref_id": context.arguments["source_ref_id"], "text": "verified"},
                "source_refs": [context.arguments["source_ref_id"]],
            }

        gateway.register(
            name="source.resolve",
            version="v1",
            allowed_run_kinds=("chat", "convergence"),
            side_effect="read",
            timeout_seconds=1,
            handler=read_source,
        )
        return gateway

    def _token(self, gateway: ToolGateway, *, max_calls: int = 1, max_result_bytes: int = 131072) -> str:
        return gateway.issue_run_token(
            run_id="run-1",
            run_kind="chat",
            workspace_id="workspace-1",
            conversation_id="conversation-1",
            package_id="pkg-1",
            tenant_id="tenant-1",
            allowed_tools=("source.resolve",),
            max_calls=max_calls,
            max_result_bytes=max_result_bytes,
            message_range=(1, 2),
        )

    def _payload(self, *, tool_name: str = "source.resolve") -> dict:
        return {
            "schema_version": "pi-runtime.tool-call.v1",
            "tool_call_id": "tool-1",
            "tool_name": tool_name,
            "tool_version": "v1",
            "run_id": "run-1",
            "run_kind": "chat",
            "workspace_id": "workspace-1",
            "conversation_id": "conversation-1",
            "package_id": "pkg-1",
            "tenant_id": "tenant-1",
            "message_range": {"from_seq": 1, "through_seq": 2},
            "arguments": {"source_ref_id": "source-1"},
            "attempt": 1,
            "trace_context": {"trace_id": "trace-1", "request_id": "request-1"},
        }

    async def test_scoped_read_tool_succeeds_and_records_audit(self) -> None:
        gateway = self._gateway()
        result = await gateway.invoke(self._token(gateway), self._payload())

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["source_refs"], ["source-1"])
        self.assertEqual(
            [event["type"] for event in gateway.audit_events],
            ["tool.call.started", "tool.call.succeeded"],
        )

    async def test_unknown_or_unlisted_tool_is_denied(self) -> None:
        gateway = self._gateway()
        result = await gateway.invoke(self._token(gateway), self._payload(tool_name="artifact.write"))

        self.assertEqual(result["status"], "denied")
        self.assertEqual(result["error"]["error_code"], "permission_denied")

    async def test_call_budget_and_tenant_scope_are_enforced(self) -> None:
        gateway = self._gateway()
        token = self._token(gateway, max_calls=1)
        first = await gateway.invoke(token, self._payload())
        second = await gateway.invoke(token, {**self._payload(), "tool_call_id": "tool-2"})

        self.assertEqual(first["status"], "succeeded")
        self.assertEqual(second["status"], "denied")
        self.assertEqual(second["error"]["error_code"], "permission_denied")
        with self.assertRaises(ToolGatewayError):
            await gateway.invoke(token, {**self._payload(), "tenant_id": "other-tenant", "tool_call_id": "tool-3"})

    async def test_result_size_limit_is_reported_as_input_error_and_audited(self) -> None:
        gateway = self._gateway()
        token = self._token(gateway, max_result_bytes=1024)
        result = await gateway.invoke(
            token,
            {
                **self._payload(),
                "arguments": {"source_ref_id": "source-" + ("x" * 2000)},
            },
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["error_code"], "invalid_request")
        self.assertEqual(result["error"]["category"], "input_error")
        self.assertEqual(gateway.audit_events[-1]["type"], "tool.call.failed")

    async def test_tool_call_version_and_schema_are_checked(self) -> None:
        gateway = self._gateway()
        token = self._token(gateway)

        with self.assertRaises(ToolGatewayError):
            await gateway.invoke(token, {**self._payload(), "schema_version": "wrong"})
        mismatched_version = await gateway.invoke(token, {**self._payload(), "tool_version": "v2"})
        self.assertEqual(mismatched_version["status"], "denied")
        self.assertEqual(mismatched_version["error"]["error_code"], "invalid_request")

    async def test_message_range_scope_is_enforced(self) -> None:
        gateway = self._gateway()
        token = self._token(gateway)

        with self.assertRaises(ToolGatewayError) as raised:
            await gateway.invoke(
                token,
                {**self._payload(), "message_range": {"from_seq": 2, "through_seq": 3}},
            )

        self.assertEqual(raised.exception.code, "permission_denied")

    def test_token_limits_and_tenant_scope_are_validated(self) -> None:
        gateway = self._gateway()
        with self.assertRaises(ValueError):
            gateway.issue_run_token(
                run_id="run-1",
                run_kind="chat",
                workspace_id="workspace-1",
                conversation_id="conversation-1",
                package_id="pkg-1",
                tenant_id="tenant-1",
                allowed_tools=("source.resolve",),
                max_result_bytes=512,
            )
        token = gateway.issue_run_token(
            run_id="run-1",
            run_kind="chat",
            workspace_id="workspace-1",
            conversation_id="conversation-1",
            package_id="pkg-1",
            allowed_tools=("source.resolve",),
            message_range=(1, 2),
        )
        with self.assertRaises(ToolGatewayError):
            # A token without tenant scope cannot be used to smuggle one in a call.
            asyncio.run(gateway.invoke(token, {**self._payload(), "tenant_id": "tenant-1"}))

    def test_gateway_rejects_write_and_proposal_handlers(self) -> None:
        gateway = self._gateway()
        with self.assertRaises(ValueError):
            gateway.register(
                name="package.commit",
                version="v1",
                allowed_run_kinds=("convergence",),
                side_effect="internal_write",
                timeout_seconds=1,
                handler=lambda context: {},
            )
        with self.assertRaises(ValueError):
            gateway.register(
                name="submit_convergence_proposal",
                version="v1",
                allowed_run_kinds=("convergence",),
                side_effect="none",
                timeout_seconds=1,
                handler=lambda context: {},
            )


if __name__ == "__main__":
    unittest.main()

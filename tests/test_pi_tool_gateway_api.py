"""FastAPI 内部 Tool Gateway 的最小 HTTP 边界测试。"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - 依赖缺失时由测试跳过
    TestClient = None  # type: ignore[assignment]

from app.api.server import create_app
from app.canvas.tool_gateway import RunScopedTokenCodec, ToolGateway


class ToolGatewayApiTests(unittest.TestCase):
    def setUp(self) -> None:
        if TestClient is None:
            self.skipTest("fastapi and its test client are not installed")
        gateway = ToolGateway(RunScopedTokenCodec("api-smoke-secret"))
        gateway.register(
            name="source.resolve",
            version="v1",
            allowed_run_kinds=("chat",),
            side_effect="read",
            timeout_seconds=1,
            handler=lambda context: {
                "status": "succeeded",
                "summary": "source resolved",
                "data": {"source_ref_id": context.arguments["source_ref_id"]},
                "source_refs": [str(context.arguments["source_ref_id"])],
            },
        )
        self.gateway = gateway
        self.service = SimpleNamespace(canvas_tool_gateway=gateway)
        self.client = TestClient(create_app(self.service))
        self.token = gateway.issue_run_token(
            run_id="run-api-smoke",
            run_kind="chat",
            workspace_id="workspace-api-smoke",
            conversation_id="conversation-api-smoke",
            package_id="package-api-smoke",
            tenant_id="tenant-api-smoke",
            allowed_tools=("source.resolve",),
            max_calls=2,
        )

    def _payload(self, *, tenant_id: str = "tenant-api-smoke") -> dict[str, object]:
        return {
            "schema_version": "pi-runtime.tool-call.v1",
            "tool_call_id": "tool-api-smoke",
            "tool_name": "source.resolve",
            "tool_version": "v1",
            "run_id": "run-api-smoke",
            "run_kind": "chat",
            "workspace_id": "workspace-api-smoke",
            "conversation_id": "conversation-api-smoke",
            "package_id": "package-api-smoke",
            "tenant_id": tenant_id,
            "message_range": {"from_seq": 1, "through_seq": 1},
            "arguments": {"source_ref_id": "source-api-smoke"},
            "attempt": 1,
            "trace_context": {"trace_id": "trace-api-smoke", "request_id": "request-api-smoke"},
        }

    def test_internal_gateway_requires_token_and_enforces_scope(self) -> None:
        payload = self._payload()
        self.assertEqual(self.client.post("/internal/v1/tool-calls", json=payload).status_code, 401)

        response = self.client.post(
            "/internal/v1/tool-calls",
            json=payload,
            headers={"Authorization": f"Run {self.token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_refs"], ["source-api-smoke"])

        wrong_tenant = {**payload, "tool_call_id": "tool-api-smoke-2", "tenant_id": "other-tenant"}
        denied = self.client.post(
            "/internal/v1/tool-calls",
            json=wrong_tenant,
            headers={"Authorization": f"Run {self.token}"},
        )
        self.assertEqual(denied.status_code, 403)


if __name__ == "__main__":
    unittest.main()

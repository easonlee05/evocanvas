"""普通 Chat 确认与已移除确认队列 API 的回归测试。"""

import unittest
from uuid import uuid4

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None

from app.api.server import create_app


class CanvasConfirmationApiTests(unittest.TestCase):
    """确认不再通过独立审批队列或状态写入口推进。"""

    def setUp(self) -> None:
        if TestClient is None:
            self.skipTest("FastAPI not installed")
        self.client = TestClient(create_app())
        self.headers = {"X-Tenant-ID": f"canvas-confirmation-{uuid4().hex[:8]}"}

    def test_confirmation_queue_routes_are_removed(self) -> None:
        """历史确认队列端点不能再形成第二条状态写通道。"""

        paths = [
            "/api/canvas/workspaces/demo/confirmations",
            "/api/canvas/workspaces/demo/confirmations/proposal_missing/approve",
            "/api/canvas/workspaces/demo/confirmations/proposal_missing/reject",
        ]
        responses = [
            self.client.get(paths[0], headers=self.headers),
            self.client.post(paths[1], headers=self.headers),
            self.client.post(paths[2], headers=self.headers),
        ]

        self.assertEqual([response.status_code for response in responses], [404, 404, 404])

    def test_decision_candidate_is_persisted_without_confirmation_queue(self) -> None:
        """待决策先以 pending_decision 入包，后续 Chat 不会被历史队列阻塞。"""

        created = self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "把这次方案取舍整理成需要拍板的待决策项",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )
        followup = self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "继续补充一期范围的待澄清问题",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )
        canvas = self.client.get(
            "/api/canvas/workspaces/demo/canvas", headers=self.headers
        ).json()

        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["action"], "auto_apply")
        self.assertEqual(followup.status_code, 200)
        self.assertEqual(canvas["view_meta"]["pending_confirmation_ids"], [])
        self.assertTrue(
            any(
                card["kind"] == "decision" and card["status"] == "pending_decision"
                for card in canvas["cards"]
            )
        )

    def test_snapshot_and_handoff_endpoints_remain_available(self) -> None:
        """移除确认队列不影响结构化交接物与快照读取。"""

        snapshots = self.client.get("/api/canvas/workspaces/demo/snapshots", headers=self.headers)
        handoff = self.client.get("/api/canvas/workspaces/demo/handoff", headers=self.headers)

        self.assertEqual(snapshots.status_code, 200)
        self.assertIn("items", snapshots.json())
        self.assertEqual(handoff.status_code, 200)
        self.assertIn("status", handoff.json())


if __name__ == "__main__":
    unittest.main()

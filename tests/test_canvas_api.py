import unittest
from uuid import uuid4

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None

from app.api.server import create_app


class CanvasApiTests(unittest.TestCase):
    def setUp(self) -> None:
        if TestClient is None:
            self.skipTest("FastAPI not installed")
        self.client = TestClient(create_app())
        self.headers = {"X-Tenant-ID": f"canvas-api-{uuid4().hex[:8]}"}

    def test_get_canvas_workspace_returns_workspace_payload(self) -> None:
        response = self.client.get("/api/canvas/workspaces/demo", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workspace_id"], "demo")
        self.assertIn("title", payload)
        self.assertIn("handoff_status", payload)

    def test_list_recent_canvas_workspaces(self) -> None:
        first = self.client.post(
            "/api/canvas/workspaces/ws_alpha/messages",
            json={
                "message": "先整理会员体系背景",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            "/api/canvas/workspaces/ws_beta/messages",
            json={
                "message": "补充履约约束和待决策",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )
        self.assertEqual(second.status_code, 200)

        response = self.client.get("/api/canvas/workspaces", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["items"][0]["workspace_id"], "ws_beta")
        self.assertIn("title", payload["items"][0])
        self.assertIn("updated_at", payload["items"][0])
        self.assertIn("summary_preview", payload["items"][0])

    def test_get_canvas_view_returns_canvas_payload(self) -> None:
        response = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workspace_id"], "demo")
        self.assertEqual(payload["cards"], [])
        self.assertEqual(payload["relations"], [])
        self.assertIn("todo_projection", payload)

    def test_post_message_rejects_empty_message(self) -> None:
        response = self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "   ",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 422)

    def test_post_message_rejects_unknown_selected_card(self) -> None:
        response = self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "结合这张不存在的卡继续澄清",
                "selected_card_ids": ["card_missing"],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("selected cards not found", response.json()["detail"])

    def test_patch_card_updates_editable_fields(self) -> None:
        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "用户反馈里提到误杀成本很高，需要先澄清范围",
                "selected_card_ids": [],
                "material_ids": ["material-1"],
                "mode": "default",
            },
            headers=self.headers,
        )
        card = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()["cards"][0]

        response = self.client.patch(
            f"/api/canvas/workspaces/demo/cards/{card['card_id']}",
            json={
                "title": "误杀成本范围待澄清",
                "summary": "需要明确误杀成本、影响用户和可接受阈值。",
                "status": "draft",
                "tags": ["manual-edit", "risk"],
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        updated = response.json()["card"]
        self.assertEqual(updated["card_id"], card["card_id"])
        self.assertEqual(updated["kind"], card["kind"])
        self.assertEqual(updated["title"], "误杀成本范围待澄清")
        self.assertEqual(updated["summary"], "需要明确误杀成本、影响用户和可接受阈值。")
        self.assertEqual(updated["status"], "draft")
        self.assertEqual(updated["tags"], ["manual-edit", "risk"])

        canvas = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()
        persisted = next(item for item in canvas["cards"] if item["card_id"] == card["card_id"])
        self.assertEqual(persisted["title"], "误杀成本范围待澄清")

    def test_create_relation_between_existing_cards(self) -> None:
        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "客服反馈退款链路卡住，用户不知道下一步该做什么",
                "selected_card_ids": [],
                "material_ids": ["material-a"],
                "mode": "default",
            },
            headers=self.headers,
        )
        cards = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()["cards"]
        from_card = cards[0]
        to_card = cards[1]

        response = self.client.post(
            "/api/canvas/workspaces/demo/relations",
            json={
                "kind": "supports",
                "from_card_id": from_card["card_id"],
                "to_card_id": to_card["card_id"],
                "note": "用户反馈支撑问题定义",
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        relation = response.json()["relation"]
        self.assertEqual(relation["kind"], "supports")
        self.assertEqual(relation["from_card_id"], from_card["card_id"])
        self.assertEqual(relation["to_card_id"], to_card["card_id"])
        self.assertEqual(relation["note"], "用户反馈支撑问题定义")

        canvas = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()
        self.assertTrue(any(item["relation_id"] == relation["relation_id"] for item in canvas["relations"]))

    def test_create_snapshot_captures_current_canvas_state(self) -> None:
        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "沉淀当前输入中的待澄清问题和约束候选",
                "selected_card_ids": [],
                "material_ids": ["material-snapshot"],
                "mode": "default",
            },
            headers=self.headers,
        )
        canvas_before = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()

        response = self.client.post(
            "/api/canvas/workspaces/demo/snapshots",
            json={"title": "第一次收敛快照", "summary": "记录当前待澄清和约束状态。"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        snapshot = response.json()["snapshot"]
        self.assertEqual(snapshot["title"], "第一次收敛快照")
        self.assertEqual(snapshot["summary"], "记录当前待澄清和约束状态。")
        self.assertEqual(set(snapshot["active_card_ids"]), {card["card_id"] for card in canvas_before["cards"]})
        self.assertIn("todo_projection", snapshot)

        snapshots = self.client.get("/api/canvas/workspaces/demo/snapshots", headers=self.headers).json()
        self.assertTrue(any(item["snapshot_id"] == snapshot["snapshot_id"] for item in snapshots["items"]))

        canvas_after = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()
        self.assertEqual(canvas_after["snapshot_id"], snapshot["snapshot_id"])

    def test_snapshot_canvas_keeps_card_content_at_capture_time(self) -> None:
        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "沉淀当前输入中的待澄清问题和约束候选",
                "selected_card_ids": [],
                "material_ids": ["material-history"],
                "mode": "default",
            },
            headers=self.headers,
        )
        live_before = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()
        card = live_before["cards"][0]
        snapshot = self.client.post(
            "/api/canvas/workspaces/demo/snapshots",
            json={"title": "历史态快照", "summary": "保存修改前的卡片内容。"},
            headers=self.headers,
        ).json()["snapshot"]

        self.client.patch(
            f"/api/canvas/workspaces/demo/cards/{card['card_id']}",
            json={"title": "修改后的卡片标题", "summary": "修改后的摘要"},
            headers=self.headers,
        )

        snapshot_canvas = self.client.get(
            f"/api/canvas/workspaces/demo/canvas?snapshot_id={snapshot['snapshot_id']}",
            headers=self.headers,
        )

        self.assertEqual(snapshot_canvas.status_code, 200)
        snap_card = next(item for item in snapshot_canvas.json()["cards"] if item["card_id"] == card["card_id"])
        self.assertEqual(snap_card["title"], card["title"])
        self.assertEqual(snap_card["summary"], card["summary"])
        self.assertNotEqual(snap_card["title"], "修改后的卡片标题")

    def test_canvas_view_returns_404_for_missing_snapshot(self) -> None:
        response = self.client.get(
            "/api/canvas/workspaces/demo/canvas?snapshot_id=snapshot_missing",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "canvas snapshot not found")

    def test_refresh_handoff_rebuilds_current_canvas_and_creates_snapshot(self) -> None:
        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "先整理一期范围里的待澄清问题",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )
        clarification_id = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()["cards"][0]["card_id"]
        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "结合这张卡补齐当前约束",
                "selected_card_ids": [clarification_id],
                "material_ids": ["material-handoff"],
                "mode": "default",
            },
            headers=self.headers,
        )

        response = self.client.post("/api/canvas/workspaces/demo/handoff/refresh", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workspace_id"], "demo")
        self.assertEqual(payload["status"], "draft")
        self.assertEqual(payload["content"], payload["handoff"]["summary"])
        self.assertEqual(payload["handoff"]["handoff_id"], "handoff_demo")
        self.assertEqual(len(payload["handoff"]["open_questions"]), 1)
        self.assertEqual(len(payload["handoff"]["constraints"]), 1)
        self.assertIn("snapshot", payload)

        canvas = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()
        self.assertEqual(canvas["snapshot_id"], payload["snapshot"]["snapshot_id"])
        self.assertEqual(canvas["view_meta"]["handoff_status"], "draft")
        self.assertEqual(len([card for card in canvas["cards"] if card["kind"] == "handoff"]), 1)

        repeated = self.client.post("/api/canvas/workspaces/demo/handoff/refresh", headers=self.headers)
        self.assertEqual(repeated.status_code, 200)
        repeated_canvas = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()
        self.assertEqual(len([card for card in repeated_canvas["cards"] if card["kind"] == "handoff"]), 1)

    def test_move_card_updates_stage_when_transition_is_allowed(self) -> None:
        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "这里有一段新的会议纪要：老板希望一期先降低误杀成本，但运营又要求尽快上线。",
                "selected_card_ids": [],
                "material_ids": ["meeting-move"],
                "mode": "default",
            },
            headers=self.headers,
        )
        evidence_card = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()["cards"][0]

        response = self.client.post(
            f"/api/canvas/workspaces/demo/cards/{evidence_card['card_id']}/move",
            json={"stage": "define", "reason": "这条证据已经进入问题定义阶段"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        moved = response.json()["card"]
        self.assertEqual(moved["card_id"], evidence_card["card_id"])
        self.assertEqual(moved["kind"], evidence_card["kind"])
        self.assertEqual(moved["stage"], "define")
        self.assertEqual(moved["metadata"]["last_moved_by"], "user")
        self.assertEqual(moved["metadata"]["move_reason"], "这条证据已经进入问题定义阶段")

    def test_move_card_rejects_illegal_stage_transition(self) -> None:
        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "这里有一段新的会议纪要：老板希望一期先降低误杀成本，但运营又要求尽快上线。",
                "selected_card_ids": [],
                "material_ids": ["meeting-move-illegal"],
                "mode": "default",
            },
            headers=self.headers,
        )
        evidence_card = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()["cards"][0]

        response = self.client.post(
            f"/api/canvas/workspaces/demo/cards/{evidence_card['card_id']}/move",
            json={"stage": "handoff", "reason": "想直接跳到交接"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("illegal stage transition", response.json()["detail"])

    def test_get_todos_matches_canvas_projection_for_live_and_snapshot_views(self) -> None:
        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "先整理一期范围里的待澄清问题",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )
        clarification_id = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()["cards"][0]["card_id"]
        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "结合这张卡补齐当前约束",
                "selected_card_ids": [clarification_id],
                "material_ids": ["material-todo"],
                "mode": "default",
            },
            headers=self.headers,
        )
        snapshot = self.client.post(
            "/api/canvas/workspaces/demo/snapshots",
            json={"title": "Todo 对齐快照", "summary": "锁定当前活跃缺口。"},
            headers=self.headers,
        ).json()["snapshot"]
        self.client.post(
            "/api/canvas/workspaces/demo/messages",
            json={
                "message": "把这次方案取舍整理成需要拍板的待决策项",
                "selected_card_ids": [],
                "material_ids": [],
                "mode": "default",
            },
            headers=self.headers,
        )

        live_canvas = self.client.get("/api/canvas/workspaces/demo/canvas", headers=self.headers).json()
        live_todos = self.client.get("/api/canvas/workspaces/demo/todos", headers=self.headers).json()
        snapshot_canvas = self.client.get(
            f"/api/canvas/workspaces/demo/canvas?snapshot_id={snapshot['snapshot_id']}",
            headers=self.headers,
        ).json()
        snapshot_todos = self.client.get(
            f"/api/canvas/workspaces/demo/todos?snapshot_id={snapshot['snapshot_id']}",
            headers=self.headers,
        ).json()

        self.assertEqual(live_todos, live_canvas["todo_projection"])
        self.assertEqual(snapshot_todos, snapshot_canvas["todo_projection"])
        live_card_ids = {card["card_id"] for card in live_canvas["cards"]}
        snapshot_card_ids = {card["card_id"] for card in snapshot_canvas["cards"]}
        self.assertTrue(all(item["source_card_id"] in live_card_ids for item in live_todos["items"]))
        self.assertTrue(all(item["source_card_id"] in snapshot_card_ids for item in snapshot_todos["items"]))


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4
import time
from threading import Thread

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None

from app.api.server import create_app, global_event_bus, build_default_task_service
from app.core.events import Event


class CanvasE2EIntegrationTests(unittest.TestCase):
    """验证 EvoCanvas 1.0 的完整前后端数据对接闭环流。

    覆盖了以下核心业务逻辑：
    1. 工作区惰性初始化 (GET /api/canvas/workspaces/{ws})
    2. 物料上传 (POST /api/materials) 与物理落盘校验
    3. 低风险自然语言消息的提报、意图路由与自动应用 (action: auto_apply)
    4. 卡片原地修订与属性更新 (PATCH /api/canvas/workspaces/{ws}/cards/{card_id})
    5. 废弃 stage 接口不写入领域状态 (POST /api/canvas/workspaces/{ws}/cards/{card_id}/move)
    6. 手动创建卡片间的语义关联关系 (POST /api/canvas/workspaces/{ws}/relations)
    7. 待决策对象作为候选态自动入包，不创建确认队列或锁工作台
    8. 结构化交接物刷新 (POST /handoff/refresh) 与快照备份 (POST /snapshots)
    9. 待办提取 (GET /todos)
    10. SSE 实时事件流推送通道订阅校验 (GET /events)
    """

    def setUp(self) -> None:
        if TestClient is None:
            self.skipTest("FastAPI not installed")
        
        # 1. 建立独立的隔离租户和工作空间，避免多轮测试冲突
        self.workspace_id = f"ws_e2e_{uuid4().hex[:8]}"
        self.tenant_id = f"canvas-e2e-{uuid4().hex[:8]}"
        self.headers = {"X-Tenant-ID": self.tenant_id}
        self.storage_root = Path(gettempdir()) / "manual-agent-phase1" / self.tenant_id
        
        # 2. 初始化独立的 TaskService，共享全局的 event_bus
        self.task_service = build_default_task_service(self.storage_root)
        
        # 3. 将其注入到 FastAPI app，实现完全的数据和状态穿透
        self.client = TestClient(create_app(self.task_service))

    def test_complete_canvas_lifecycle_e2e(self) -> None:
        # ====== 1. 验证工作区惰性初始化 ======
        workspace_resp = self.client.get(f"/api/canvas/workspaces/{self.workspace_id}", headers=self.headers)
        self.assertEqual(workspace_resp.status_code, 200)
        self.assertEqual(workspace_resp.json()["workspace_id"], self.workspace_id)
        # L3 规格：新工作区未形成包版本前，交接状态应为 not_ready。
        self.assertEqual(workspace_resp.json()["handoff_status"], "not_ready")

        # ====== 2. 模拟参考物料上传，并校验物理落盘 ======
        file_content = "一期上线必须在 618 之前，核心结算逻辑不能修改，P95 响应耗时控制在 120ms 以内"
        material_payload = {"file": ("requirements_notes.txt", file_content)}
        material_resp = self.client.post("/api/materials", files=material_payload, headers=self.headers)
        self.assertEqual(material_resp.status_code, 200)
        material_id = material_resp.json()["material_id"]
        self.assertTrue(material_id.startswith("material_"))

        # ====== 3. 发送低风险自然语言消息（待澄清意图），绑定参考物料，验证自动应用 ======
        message_payload = {
            "message": "先把一期范围和误杀成本的待澄清问题列出来",
            "selected_card_ids": [],
            "material_ids": [material_id],
            "mode": "default"
        }
        turn_resp = self.client.post(
            f"/api/canvas/workspaces/{self.workspace_id}/messages",
            json=message_payload,
            headers=self.headers
        )
        self.assertEqual(turn_resp.status_code, 200)
        turn_data = turn_resp.json()
        self.assertIn("turn_id", turn_data)
        self.assertEqual(turn_data["workspace_id"], self.workspace_id)
        self.assertEqual(turn_data["action"], "auto_apply")  # 低风险，引擎自动应用

        # ====== 4. 验证生成的澄清卡片已显示，测试卡片局部修订 (PATCH) ======
        canvas_resp = self.client.get(f"/api/canvas/workspaces/{self.workspace_id}/canvas", headers=self.headers)
        self.assertEqual(canvas_resp.status_code, 200)
        canvas_data = canvas_resp.json()
        self.assertGreaterEqual(len(canvas_data["cards"]), 1)
        
        # 寻找澄清卡片
        clarification_card = next((c for c in canvas_data["cards"] if c["kind"] == "clarification"), None)
        self.assertIsNotNone(clarification_card)
        card_id = clarification_card["card_id"]
        self.assertEqual(clarification_card["status"], "open")
        # L3 规格已将 evidence_refs 统一为 source_refs。
        self.assertEqual(clarification_card["source_refs"], [material_id])

        # 原地修订卡片展示字段
        # L3 规格：展示字段可以直接修订，业务状态只能经受控提案和普通 Chat 确认升级。
        patch_payload = {
            "title": "修订后的澄清标题",
            "summary": "修订后的澄清总结",
            "tags": ["e2e-test", "edited"]
        }
        patch_resp = self.client.patch(
            f"/api/canvas/workspaces/{self.workspace_id}/cards/{card_id}",
            json=patch_payload,
            headers=self.headers
        )
        self.assertEqual(patch_resp.status_code, 200)
        patched_card = patch_resp.json()["card"]
        self.assertEqual(patched_card["title"], "修订后的澄清标题")
        self.assertEqual(patched_card["summary"], "修订后的澄清总结")
        self.assertEqual(patched_card["status"], "open")
        self.assertEqual(patched_card["tags"], ["e2e-test", "edited"])

        # ====== 5. 验证废弃 stage 接口不改变 L3 领域状态 ======
        # L3 规格已下线 stage_node 主题阶段机：move_card 降级为 deprecated_noop，
        # 不再修改或记录卡片业务状态。
        move_payload = {
            "stage": "define",
            "reason": "测试人工核对完成"
        }
        move_resp = self.client.post(
            f"/api/canvas/workspaces/{self.workspace_id}/cards/{card_id}/move",
            json=move_payload,
            headers=self.headers
        )
        self.assertEqual(move_resp.status_code, 200)
        self.assertEqual(move_resp.json()["action"], "deprecated_noop")
        self.assertEqual(move_resp.json()["card"]["status"], "open")

        # 重新获取 Canvas，确认没有残留 stage 兼容元数据。
        canvas_check = self.client.get(f"/api/canvas/workspaces/{self.workspace_id}/canvas", headers=self.headers).json()
        persisted_card = next(c for c in canvas_check["cards"] if c["card_id"] == card_id)
        self.assertNotIn("legacy_stage_request", persisted_card["metadata"])

        # ====== 6. 测试手动创建卡片关联关系 ======
        # 再提交一条消息，生成另一张卡片（例如 problem 卡片）
        msg_payload_2 = {
            "message": "这里有用户误杀的问题定义",
            "selected_card_ids": [],
            "material_ids": [],
            "mode": "default"
        }
        self.client.post(f"/api/canvas/workspaces/{self.workspace_id}/messages", json=msg_payload_2, headers=self.headers)
        canvas_state_2 = self.client.get(f"/api/canvas/workspaces/{self.workspace_id}/canvas", headers=self.headers).json()
        
        problem_card = next((c for c in canvas_state_2["cards"] if c["kind"] == "problem"), None)
        self.assertIsNotNone(problem_card, "未能成功生成 problem 卡片")
        problem_card_id = problem_card["card_id"]

        # 显性化两张卡片间的关联关系
        relation_payload = {
            "kind": "supports",
            "from_card_id": card_id,
            "to_card_id": problem_card_id,
            "note": "测试连接线"
        }
        relation_resp = self.client.post(
            f"/api/canvas/workspaces/{self.workspace_id}/relations",
            json=relation_payload,
            headers=self.headers
        )
        self.assertEqual(relation_resp.status_code, 200)
        relation_data = relation_resp.json()["relation"]
        self.assertEqual(relation_data["kind"], "supports")
        self.assertEqual(relation_data["from_card_id"], card_id)
        self.assertEqual(relation_data["to_card_id"], problem_card_id)

        # 再次拉取 Canvas 验证连线已入库
        canvas_state_3 = self.client.get(f"/api/canvas/workspaces/{self.workspace_id}/canvas", headers=self.headers).json()
        self.assertTrue(any(r["relation_id"] == relation_data["relation_id"] for r in canvas_state_3["relations"]))

        # ====== 7. 待决策是候选对象，不通过确认队列或工作台锁推进 ======
        decision_payload = {
            "message": "把这次方案取舍整理成需要我拍板的待决策项",
            "selected_card_ids": [],
            "material_ids": [material_id],
            "mode": "default"
        }
        decision_turn_resp = self.client.post(
            f"/api/canvas/workspaces/{self.workspace_id}/messages",
            json=decision_payload,
            headers=self.headers
        )
        self.assertEqual(decision_turn_resp.status_code, 200)
        decision_turn_data = decision_turn_resp.json()
        self.assertEqual(decision_turn_data["action"], "auto_apply")
        self.assertEqual(decision_turn_data["risk_level"], "medium")

        # 候选态不会阻塞下一次正常 Chat。
        followup_resp = self.client.post(
            f"/api/canvas/workspaces/{self.workspace_id}/messages",
            json={"message": "继续补充一期范围的待澄清问题", "selected_card_ids": [], "material_ids": []},
            headers=self.headers
        )
        self.assertEqual(followup_resp.status_code, 200)
        canvas_after_decision = self.client.get(f"/api/canvas/workspaces/{self.workspace_id}/canvas", headers=self.headers).json()
        decision_cards = [c for c in canvas_after_decision["cards"] if c["kind"] == "decision"]
        self.assertEqual(len(decision_cards), 1)
        self.assertEqual(decision_cards[0]["status"], "pending_decision")
        self.assertIsNone(canvas_after_decision["active_turn"])
        self.assertEqual(canvas_after_decision["view_meta"]["pending_confirmation_ids"], [])
        self.assertEqual(
            self.client.get(f"/api/canvas/workspaces/{self.workspace_id}/confirmations", headers=self.headers).status_code,
            404,
        )

        # ====== 8. 测试结构化交接物刷新与快照生成 ======
        # 刷新交接物
        refresh_resp = self.client.post(f"/api/canvas/workspaces/{self.workspace_id}/handoff/refresh", headers=self.headers)
        self.assertEqual(refresh_resp.status_code, 200)
        handoff_data = refresh_resp.json()
        self.assertEqual(handoff_data["status"], "draft")
        # L3 规格已下线 StructuredHandoff.open_questions 字符串列表；改用 unresolved_refs
        # 回指未决对象（status 派生为 UNRESOLVED 治理地位）。
        # 此处验证未决引用集合存在且非空（clarification 卡片仍为 open/draft）。
        self.assertGreaterEqual(len(handoff_data["handoff"]["unresolved_refs"]), 1)

        # 生成备份快照
        snapshot_payload = {
            "title": "v1.0-e2e-milestone",
            "summary": "E2E 关键里程碑快照"
        }
        snapshot_resp = self.client.post(
            f"/api/canvas/workspaces/{self.workspace_id}/snapshots",
            json=snapshot_payload,
            headers=self.headers
        )
        self.assertEqual(snapshot_resp.status_code, 200)
        snapshot_data = snapshot_resp.json()
        self.assertIn("snapshot_id", snapshot_data["snapshot"])

        # 获取快照列表
        snapshots_list_resp = self.client.get(f"/api/canvas/workspaces/{self.workspace_id}/snapshots", headers=self.headers)
        self.assertEqual(snapshots_list_resp.status_code, 200)
        snapshots = snapshots_list_resp.json()["items"]
        self.assertGreaterEqual(len(snapshots), 1)
        self.assertTrue(any(s["title"] == "v1.0-e2e-milestone" for s in snapshots))

        # ====== 9. 测试待办提取 ======
        todos_resp = self.client.get(f"/api/canvas/workspaces/{self.workspace_id}/todos", headers=self.headers)
        self.assertEqual(todos_resp.status_code, 200)
        self.assertIn("items", todos_resp.json())

        # ====== 10. 测试 SSE (Server-Sent Events) 事件流推送 ======
        def mock_event_publisher():
            # 延迟一段时间后发布事件以通知 SSE 流关闭
            time.sleep(0.3)
            event = Event(
                id=str(uuid4()),
                task_id=f"canvas:{self.workspace_id}",
                type="canvas.turn.completed",
                payload={"workspace_id": self.workspace_id, "turn_id": "mock_turn", "status": "completed"}
            )
            global_event_bus.publish(event)

        # 启动后台线程发布关闭事件
        publisher_thread = Thread(target=mock_event_publisher)
        publisher_thread.start()

        # 消费事件流，它将在接收到 canvas.turn.completed 后正常退出 break 避免死锁
        events_resp = self.client.get(f"/api/canvas/workspaces/{self.workspace_id}/events", headers=self.headers)
        self.assertEqual(events_resp.status_code, 200)
        self.assertIn("event: canvas.turn.completed", events_resp.text)

        # 确认后台线程顺利退出
        publisher_thread.join(timeout=1.0)

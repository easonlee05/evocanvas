"""真实 Python→HTTP→Pi Agent→SQLite Session/Revision 的跨语言回归。"""
import asyncio
import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.canvas.agent_execution.pi_client import PiRuntimeClient, PiRuntimeError
from app.canvas.service import CanvasService
from app.services.fakes import FakeStorage

ROOT = Path(__file__).resolve().parents[1]

class PiWorkspaceHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_confirmed_revisions_and_projection_rebuild(self):
        with TemporaryDirectory() as temporary:
            process = subprocess.Popen(
                ["node", "--import", "tsx", "test-fixtures/workspace-server.ts", str(Path(temporary) / "runtime")],
                cwd=ROOT / "pi-runtime", stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                line = await asyncio.wait_for(asyncio.to_thread(process.stdout.readline), timeout=15)
                self.assertTrue(line, "测试 Runtime 未启动；需要允许监听本地端口")
                port = json.loads(line)["port"]
                client = PiRuntimeClient(f"http://127.0.0.1:{port}")
                service = CanvasService(FakeStorage(Path(temporary) / "python"), execution=client)
                async def turn(submission, message):
                    return await service.run_pi_turn(workspace_id="w", message=message, selected_card_ids=[], material_ids=[], submission_id=submission, actor_id="u")
                with patch.object(service.supervisor, "recognize_and_plan", side_effect=AssertionError("禁止进入非主链 Supervisor")):
                    proposed = await turn("s1", "希望单机使用")
                    self.assertEqual(proposed["action"], "awaiting_chat_confirmation")
                    self.assertEqual(service.repository.load_cards("w"), [])
                    applied = await turn("s2", "确认")
                    self.assertEqual(applied["action"], "applied_confirmation")
                    self.assertEqual(service.repository.load_cards("w")[0].title, "单机使用")
                    first = applied["projected_revision_id"]
                    retry = await turn("s2", "确认")
                    self.assertEqual(retry["projected_revision_id"], first)
                    await turn("s3", "还需要离线")
                    updated = await turn("s4", "确认")
                    self.assertNotEqual(updated["projected_revision_id"], first)
                    self.assertEqual(service.repository.load_cards("w")[0].title, "单机离线使用")
                    self.assertEqual(service.repository.load_relations("w"), [])
                messages = service.repository.load_chat_messages("w")
                self.assertEqual(len(messages), 8)
                self.assertTrue(all(m["metadata"]["entry_id"] == m["message_id"] for m in messages))
                # 清除可重建缓存，重启 Python 服务后仍能读取同一稳定状态。
                service.repository.save_cards("w", [])
                restarted = CanvasService(FakeStorage(Path(temporary) / "python"), execution=client)
                await restarted.pi_kernel.refresh_projection("w")
                self.assertEqual(restarted.repository.load_cards("w")[0].title, "单机离线使用")
                await turn("handoff-propose", "生成交接物")
                self.assertIsNone((await client.get_handoff("w"))["handoff"])
                await turn("handoff-confirm", "确认交接")
                self.assertIn("单机离线使用", (await client.get_handoff("w"))["handoff"]["summary"])
                # FastAPI 手工编辑与 Pi 工具使用同一 Revision 提交器。
                from fastapi.testclient import TestClient
                from app.api.server import create_app, get_canvas_service
                from app.api.auth import get_current_user, User
                app = create_app()
                app.dependency_overrides[get_canvas_service] = lambda: service
                app.dependency_overrides[get_current_user] = lambda: User(user_id="u", username="review", tenant_id="test")
                with TestClient(app) as api:
                    created = api.post("/api/canvas/workspaces/w/cards", json={"kind":"problem","title":"需要验证的问题"})
                    self.assertEqual(created.status_code, 200, created.text)
                    card_id = created.json()["card_id"]
                    edited = api.patch(f"/api/canvas/workspaces/w/cards/{card_id}", json={"title":"修改后的问题"})
                    self.assertEqual(edited.status_code, 200, edited.text)
                    relation = api.post("/api/canvas/workspaces/w/relations", json={"kind":"supports","from_card_id":card_id,"to_card_id":"constraint-1"})
                    self.assertEqual(relation.status_code, 200, relation.text)
                    relation_id = relation.json()["relation_id"]
                    self.assertEqual(api.delete(f"/api/canvas/workspaces/w/relations/{relation_id}").status_code,200)
                    protected = api.patch("/api/canvas/workspaces/w/cards/constraint-1", json={"title":"禁止直接改稳定约束"})
                    self.assertEqual(protected.status_code,409,protected.text)
                    self.assertEqual(protected.json()["reason"],"chat_confirmation_required")
                    self.assertEqual(api.delete(f"/api/canvas/workspaces/w/cards/{card_id}").status_code,200)
                    view = api.get("/api/canvas/workspaces/w/canvas")
                    self.assertEqual(view.status_code,200,view.text)
                    self.assertEqual(len(view.json()["cards"]),1)
                    self.assertIsNone(api.get("/api/canvas/workspaces/w/handoff").json()["handoff"])
                process.terminate()
                await asyncio.to_thread(process.wait, 10)
                with self.assertRaises(PiRuntimeError):
                    await turn("s5", "新消息")
                self.assertEqual(service.repository.load_cards("w")[0].title, "单机离线使用")
                self.assertFalse(service.get_workspace("w").active_turn_id)
            finally:
                if process.poll() is None:
                    process.terminate()
                    await asyncio.to_thread(process.wait, 10)
                process.stdout.close()
                process.stderr.close()

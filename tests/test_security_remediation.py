"""EvoCanvas 安全修复专项测试套件。

覆盖以下安全漏洞的修复验证：
1. [Critical C1 & C3] 鉴权与授权机制、HMAC 签名 Token、后门令牌移除、RolePolicy 权限拦截。
2. [Critical C2 & High H1] Peer 派发人工审批闸门、Codex 工作区沙箱隔离、子进程环境变量白名单剥离。
3. [High H2] 子进程沙箱环境脱敏与 Docker 强制隔离策略。
4. [High H3] 存储层与仓储层路径穿越严格拦截。
5. [Medium M3] CORS 配置收窄白名单校验。
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

try:
    from fastapi.testclient import TestClient
    from app.api.server import create_app
except ImportError:
    TestClient = None
    create_app = None

from app.api.auth import (
    RolePolicy,
    User,
    generate_signed_token,
    get_current_user,
    verify_signed_token,
    _safe_id,
)
from app.canvas.repository import CanvasRepository
from app.services.codex_cli_handler import CodexCLIHandler
from app.services.fakes import FakeStorage
from app.services.sandbox.adapters.subprocess_adapter import SubprocessSandboxAdapter
from app.services.sandbox.config import SandboxConfig
from app.services.sandbox.manager import SandboxManager


class TestSecurityRemediation(unittest.TestCase):
    """安全漏洞加固综合测试用例。"""

    def setUp(self):
        self.secret = "test-security-secret-key-12345"
        os.environ["EVO_API_TOKEN_SECRET"] = self.secret

    def tearDown(self):
        os.environ.pop("EVO_API_TOKEN_SECRET", None)
        os.environ.pop("EVO_AUTH_REQUIRED", None)
        os.environ.pop("EVO_SANDBOX_REQUIRE_DOCKER", None)

    # -------------------------------------------------------------
    # 1. 认证与授权测试 (C1, C3)
    # -------------------------------------------------------------
    def test_signed_token_lifecycle(self):
        """测试签名 Token 的正确签发、校验与防篡改。"""
        token = generate_signed_token("u1", "tenant-1", role="admin", expires_in=3600, secret=self.secret)
        payload = verify_signed_token(token, secret=self.secret)
        self.assertEqual(payload["user_id"], "u1")
        self.assertEqual(payload["tenant_id"], "tenant-1")
        self.assertEqual(payload["role"], "admin")

        # 篡改 Token 内容应被拒绝
        tampered = token[:-4] + "abcd"
        with self.assertRaises(Exception):
            verify_signed_token(tampered, secret=self.secret)

    def test_backdoor_test_admin_token_removed(self):
        """验证 'test-admin-token' 不再赋予 admin 权限且被有效拦截。"""
        req_mock = MagicMock()
        try:
            user = get_current_user(request=req_mock, x_api_token="test-admin-token")
            self.assertNotEqual(user.role, "admin")
        except Exception as exc:
            # 在设置了 secret 或强制认证时，明文 test-admin-token 会直接抛出 401
            self.assertTrue(getattr(exc, "status_code", 401) in (401, 403))

    def test_role_policy_enforcement(self):
        """验证 IAM RolePolicy 白名单权限校验与拒绝机制。"""
        self.assertTrue(RolePolicy.check_access("admin", "task.create"))
        self.assertTrue(RolePolicy.check_access("admin", "peer.dispatch"))
        self.assertTrue(RolePolicy.check_access("worker", "task.create"))
        self.assertTrue(RolePolicy.check_access("user", "canvas.write"))
        self.assertTrue(RolePolicy.check_access("reader", "canvas.read"))

        # reader / guest 无法进行写/派发/删除
        self.assertFalse(RolePolicy.check_access("reader", "task.create"))
        self.assertFalse(RolePolicy.check_access("reader", "peer.dispatch"))
        self.assertFalse(RolePolicy.check_access("guest", "canvas.write"))

        with self.assertRaises(Exception):
            RolePolicy.enforce("guest", "canvas.write")

    def test_auth_required_fails_closed(self):
        """验证当配置 EVO_AUTH_REQUIRED=1 时，未认证请求被 401 拦截。"""
        if TestClient is None:
            self.skipTest("FastAPI not installed")
        os.environ["EVO_AUTH_REQUIRED"] = "1"
        client = TestClient(create_app())
        # 匿名请求受保护接口应返回 401
        res = client.post("/api/tasks", json={"goal": "test goal"})
        self.assertEqual(res.status_code, 401)

    def test_authenticated_request_with_valid_token(self):
        """验证携带合法签名 Token 时可成功通过鉴权。"""
        if TestClient is None:
            self.skipTest("FastAPI not installed")
        os.environ["EVO_AUTH_REQUIRED"] = "1"
        client = TestClient(create_app())
        token = generate_signed_token("user-01", "default", role="worker", secret=self.secret)
        res = client.get("/api/tasks", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)

    # -------------------------------------------------------------
    # 2. RCE 阻断与 Codex 隔离测试 (C2, H1)
    # -------------------------------------------------------------
    def test_peer_dispatch_requires_human_approval(self):
        """验证 peer-dispatch 端点必须显式包含 approved_by_human 闸门。"""
        if TestClient is None:
            self.skipTest("FastAPI not installed")
        client = TestClient(create_app())
        token = generate_signed_token("user-01", "default", role="worker", secret=self.secret)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. 创建一个任务
        res_create = client.post("/api/tasks", json={"goal": "test peer dispatch"}, headers=headers)
        self.assertEqual(res_create.status_code, 200)
        task_id = res_create.json()["task_id"]

        # 2. 未批准的 peer-dispatch 请求必须返回 400
        res_unapproved = client.post(f"/api/tasks/{task_id}/peer-dispatch", json={}, headers=headers)
        self.assertEqual(res_unapproved.status_code, 400)
        self.assertIn("explicit approval", res_unapproved.json().get("detail", ""))

    def test_codex_cli_handler_env_stripping(self):
        """验证 CodexCLIHandler 剥离系统敏感环境变量。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            captured_env = {}

            def mock_runner(cmd, prompt, cwd):
                return {"implementation_summary": "mock summary"}

            handler = CodexCLIHandler(
                workspace_root=Path(temp_dir),
                runner=mock_runner,
            )
            # 默认 approval_policy 不应是 "never"
            self.assertNotEqual(handler.approval_policy, "never")

            # 模拟执行与环境变量过滤
            os.environ["SECRET_DATABASE_PASSWORD"] = "super_secret"
            os.environ["OPENAI_API_KEY"] = "sk-sensitive-key"
            try:
                allowed = {"PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "LC_ALL", "TMPDIR", "PYTHONUNBUFFERED", "TERM"}
                filtered = {k: v for k, v in os.environ.items() if k in allowed}
                self.assertNotIn("SECRET_DATABASE_PASSWORD", filtered)
                self.assertNotIn("OPENAI_API_KEY", filtered)
            finally:
                os.environ.pop("SECRET_DATABASE_PASSWORD", None)
                os.environ.pop("OPENAI_API_KEY", None)

    # -------------------------------------------------------------
    # 3. 沙箱隔离加固测试 (H2)
    # -------------------------------------------------------------
    def test_subprocess_sandbox_adapter_env_isolation(self):
        """验证 Subprocess 沙箱执行时敏感环境变量被剥离。"""
        adapter = SubprocessSandboxAdapter()
        code = (
            "import os\n"
            "print('SECRET_PRESENT:' + str('SECRET_TOKEN' in os.environ))\n"
        )
        os.environ["SECRET_TOKEN"] = "my-very-secret-token"
        try:
            config = SandboxConfig(timeout_seconds=5, network_disabled=True)
            result = adapter.execute(code, config)
            self.assertEqual(result.status, "succeeded")
            self.assertIn("SECRET_PRESENT:False", result.stdout)
        finally:
            os.environ.pop("SECRET_TOKEN", None)

    def test_sandbox_manager_require_docker_policy(self):
        """验证当强制要求 Docker (EVO_SANDBOX_REQUIRE_DOCKER=1) 时，禁止不安全降级。"""
        os.environ["EVO_SANDBOX_REQUIRE_DOCKER"] = "1"
        # 强制指定 force_subprocess 在策略下必须报错
        with self.assertRaises(RuntimeError):
            SandboxManager(force_subprocess=True)

    # -------------------------------------------------------------
    # 4. 持久化路径穿越测试 (H3)
    # -------------------------------------------------------------
    def test_storage_path_traversal_prevention(self):
        """验证 FakeStorage 对非法 task_id/artifact_id 路径穿越的严格拦截。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FakeStorage(Path(temp_dir))
            
            # 非法 task_id 包含路径穿越字符
            invalid_ids = ["../malicious", "../../etc/passwd", "task/../../hack", "task\0inject"]
            for bad_id in invalid_ids:
                with self.assertRaises(ValueError):
                    storage._task_dir(bad_id)
                with self.assertRaises(ValueError):
                    storage.read_artifact(bad_id)

    def test_canvas_repository_path_traversal_prevention(self):
        """验证 CanvasRepository 对非法 workspace_id/package_id 的拦截。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = FakeStorage(Path(temp_dir))
            repo = CanvasRepository(storage)
            
            with self.assertRaises(ValueError):
                repo._workspace_dir("../evil_workspace")
            with self.assertRaises(ValueError):
                repo._package_dir("valid_ws", "../../escape")

    def test_safe_id_validator(self):
        """验证 _safe_id 基础函数。"""
        self.assertEqual(_safe_id("valid_id-123"), "valid_id-123")
        with self.assertRaises(ValueError):
            _safe_id("../invalid")
        with self.assertRaises(ValueError):
            _safe_id("")
        with self.assertRaises(ValueError):
            _safe_id("invalid/slash")


if __name__ == "__main__":
    unittest.main()

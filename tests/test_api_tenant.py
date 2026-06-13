"""
租户隔离（Tenant Isolation）API 测试模块。

验证 Evoloop 后端 API 的健康状态以及基于 X-Tenant-ID HTTP 请求头实现的多租户数据隔离机制。
包含以下测试场景：
1. /api/health 健康检查接口测试。
2. 跨租户创建和拉取任务时的隔离性校验（例如租户 A 只能看到租户 A 的任务，无法获取租户 B 的任务）。
"""

import unittest

try:
    from fastapi.testclient import TestClient
    from app.api.server import app
except ImportError:
    TestClient = None
    app = None


class TestApiTenant(unittest.TestCase):
    """
    租户隔离 API 的单元测试类。

    维护 FastAPI TestClient 并在框架未安装时自动跳过测试。
    """

    def setUp(self):
        """
        初始化测试脚手架。

        若未安装 FastAPI 或 TestClient 依赖，则直接跳过测试用例。
        """
        if app is None or TestClient is None:
            self.skipTest("FastAPI not installed")
        self.client = TestClient(app)

    def test_api_health(self):
        """
        验证 API 健康检查接口。

        断言：
        - 访问 /api/health 返回 HTTP 200。
        """
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)

    def test_api_tenant_isolation(self):
        """
        验证跨租户数据隔离机制是否生效。

        业务逻辑：
        - 租户 A (tenant-a) 创建任务 task_a。
        - 租户 B (tenant-b) 创建任务 task_b。
        - 租户 A 查询任务列表时，task_a 应该存在，task_b 必须不存在。
        - 租户 B 查询任务列表时，task_b 应该存在，task_a 必须不存在。
        """
        # 1. 租户 A 创建任务
        res_a = self.client.post("/api/tasks", json={"goal": "test tenant a"}, headers={"X-Tenant-ID": "tenant-a"})
        self.assertEqual(res_a.status_code, 200)
        task_id_a = res_a.json()["task_id"]
        
        # 2. 租户 B 创建任务
        res_b = self.client.post("/api/tasks", json={"goal": "test tenant b"}, headers={"X-Tenant-ID": "tenant-b"})
        self.assertEqual(res_b.status_code, 200)
        task_id_b = res_b.json()["task_id"]
        
        # 3. 验证租户 A 查询任务列表的隔离性
        list_a = self.client.get("/api/tasks", headers={"X-Tenant-ID": "tenant-a"})
        tasks_a = [t["id"] for t in list_a.json()["tasks"]]
        self.assertIn(task_id_a, tasks_a)
        self.assertNotIn(task_id_b, tasks_a)
        
        # 4. 验证租户 B 查询任务列表的隔离性
        list_b = self.client.get("/api/tasks", headers={"X-Tenant-ID": "tenant-b"})
        tasks_b = [t["id"] for t in list_b.json()["tasks"]]
        self.assertIn(task_id_b, tasks_b)
        self.assertNotIn(task_id_a, tasks_b)


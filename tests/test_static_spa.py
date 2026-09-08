"""前端静态资源与 SPA 路由兜底测试用例。"""
import unittest
from fastapi.testclient import TestClient
from app.api.server import create_app


class TestStaticSPAFallback(unittest.TestCase):
    """测试当前端构建目录存在时，FastAPI 能够正确对外托管静态页面与 SPA 路由。"""

    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_api_health_endpoint_intact(self):
        """验证 API 路由未被静态兜底拦截。"""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "ok")

    def test_root_serves_spa_html(self):
        """验证根路由 / 返回 index.html。"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("<html", response.text.lower())

    def test_spa_deep_link_serves_index_html(self):
        """验证前端路由 /workspace/... 命中兜底并返回 index.html。"""
        response = self.client.get("/workspace/test-workspace-id")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))

    def test_api_route_404_not_swallowed_by_spa(self):
        """验证不存在的 /api/... 路径不会被兜底为 200 HTML，而是正常返回 404。"""
        response = self.client.get("/api/non-existent-endpoint")
        self.assertEqual(response.status_code, 404)

"""Model Context Protocol (MCP) 资源绑定暴露的单元测试模块。

主要用于验证在环境中存在 mcp 包时，mcp 服务器能够正确绑定和暴露相关静态资源或资源注册方法。
"""
import unittest

class TestMcpResources(unittest.TestCase):
    """MCP 资源接口暴露校验测试类。"""

    def test_mcp_resources(self):
        """测试 mcp 实例是否暴露了必要的资源(resources)相关属性或注册函数。

        若运行环境不支持或未安装 mcp 依赖，则跳过本测试；
        若支持，则验证 mcp 实例具有 resources 属性、私有资源映射或 add_resource 等关键属性。
        """
        try:
            # 尝试导入 mcp 模块
            from app.mcp.server import mcp
        except (ImportError, SystemExit):
            # 依赖缺失时自动跳过
            self.skipTest("mcp package not installed")
            
        # 校验 mcp 实例是否包含资源管理的核心成员属性
        self.assertTrue(hasattr(mcp, "resources") or hasattr(mcp, "_resources") or hasattr(mcp, "add_resource"))


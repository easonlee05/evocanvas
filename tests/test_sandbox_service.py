"""代码沙箱服务 (Sandbox Service) 的单元测试模块。

本测试模块主要针对沙箱管理器及本地子进程执行适配器，验证以下场景：
- 在 CI/CD 宿主环境或无 Docker 守护进程时，正确回退使用 SubprocessSandboxAdapter 本地进程执行。
- 执行正常的 Python 代码，成功获取其 stdout 标准输出并保证退出状态码为 0。
- 执行耗时超长代码时，能正确触发超时中断，标记超时属性并返回错误码。
- 执行包含语法错误的代码时，能正常捕获 stderr 标准错误输出（如 SyntaxError）并标记执行失败。
"""
import unittest
from app.services.sandbox.manager import SandboxManager
from app.services.sandbox.adapters.subprocess_adapter import SubprocessSandboxAdapter

class SandboxManagerTests(unittest.TestCase):
    """沙箱执行环境管理器测试类。

    校验安全沙箱针对多语言或 Python 本地安全隔离执行的超时控制、结果收集及降级策略。
    """

    def setUp(self):
        """测试前脚手架准备。

        强制指定 force_subprocess=True 以避免在缺乏 Docker 守护进程的 CI 环境下出错。
        """
        # Force subprocess to avoid relying on docker daemon in CI
        self.manager = SandboxManager(force_subprocess=True)

    def test_manager_uses_fallback(self):
        """测试沙箱管理器降级策略。

        验证当未检测到可用容器引擎或强制指定本地执行时，
        manager.adapter 是否已被成功初始化为 SubprocessSandboxAdapter 本地子进程执行器。
        """
        self.assertIsInstance(self.manager.adapter, SubprocessSandboxAdapter)

    def test_execute_valid_python_code(self):
        """测试正常 Python 代码的沙箱执行。

        提供一段符合语法的 print 语句，
        验证执行后 status="succeeded"，返回码 exit_code=0，且能从 stdout 读出预期打印值。
        """
        code = "print('Industrial Sandbox')"
        result = self.manager.execute(code)
        
        # 验证退出码、输出内容和超时/内存超限标志
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Industrial Sandbox", result.stdout)
        self.assertEqual(result.stderr, "")
        self.assertFalse(result.oom_killed)
        self.assertFalse(result.timeout)

    def test_execute_code_timeout(self):
        """测试沙箱执行超时的控制机制。

        配置 SandboxConfig 超时限制为 1 秒，并传入执行 2 秒的 sleep 脚本。
        验证沙箱能够及时强行中断进程，状态设为 failed，timeout 属性为 True，并带有超时错误信息。
        """
        from app.services.sandbox.config import SandboxConfig
        config = SandboxConfig(timeout_seconds=1)
        code = "import time\ntime.sleep(2)"
        result = self.manager.execute(code, config)
        
        # 断言已被超时强杀
        self.assertEqual(result.status, "failed")
        self.assertTrue(result.timeout)
        self.assertIn("Timeout after 1s", result.error)

    def test_execute_code_syntax_error(self):
        """测试沙箱执行存在语法错误的代码。

        提供一段破损的代码（括号/引号未闭合），
        验证执行状态为 failed，并且可以在 stderr 输出中检索到 "SyntaxError" 异常信息。
        """
        code = "print('Hello"
        result = self.manager.execute(code)
        
        # 校验异常状态及错误类型捕获
        self.assertEqual(result.status, "failed")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("SyntaxError", result.stderr)

if __name__ == '__main__':
    unittest.main()


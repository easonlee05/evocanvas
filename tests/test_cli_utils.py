"""
Evoloop CLI 核心实用工具函数（CliUtils）测试模块。

主要对 CLI 环境下，从用户输入日志中抓取负面或受挫情绪（intercept_user_emotion）
并自动引导的逻辑，以及大段异常输出文本的折叠缩略逻辑（compact_error_text）进行验证。
"""

import unittest
from app.cli.utils import intercept_user_emotion, compact_error_text


class TestCliUtils(unittest.TestCase):
    """
    CLI 常用工具类的单元测试。

    涵盖情绪探测、日志长文本裁剪折叠等底层逻辑。
    """

    def test_intercept_user_emotion(self):
        """
        验证情绪截获函数是否能够探测到带有挫败、愤怒情绪的词语。

        输入：
        - 正常语句 "hello world" -> 不应做任何转换。
        - 挫败语句 "this is wtf man"、"根本不行" -> 应该识别并插入 "System: 用户情绪受挫" 标记。
        """
        normal = intercept_user_emotion("hello world")
        self.assertEqual(normal, "hello world")
        
        frustrated = intercept_user_emotion("this is wtf man")
        self.assertIn("System: 用户情绪受挫", frustrated)
        
        frustrated2 = intercept_user_emotion("根本不行")
        self.assertIn("System: 用户情绪受挫", frustrated2)

    def test_compact_error_text(self):
        """
        验证错误文本截断函数。

        测试点：
        - 对于短文本，不需要做任何折叠。
        - 对于超过阈值的长文本，截断中间内容，保留开头与结尾，插入说明折叠行数的语句。
        """
        short = "a\nb\nc"
        self.assertEqual(compact_error_text(short, max_lines=10), short)
        
        long_text = "\n".join(str(i) for i in range(100))
        compacted = compact_error_text(long_text, max_lines=10)
        lines = compacted.splitlines()
        self.assertEqual(len(lines), 9)
        # 注意：此处断言因为本地化翻译可能在本地失败，但根据不可改变测试逻辑的黄金规则，本断言保持原样
        self.assertIn("折叠了", lines[4])


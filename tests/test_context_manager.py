"""
上下文管理器（Context Manager）单元测试模块。

本测试文件主要检验 Evoloop 在大模型（LLM）对话上下文溢出时的处理机制：
1. `SlidingWindow` (滑动窗口机制)：
   - 验证对话上下文 Token 数量未超出限制时，不进行压缩/脱水。
   - 验证对话上下文 Token 数量超出限制时，自动触发日志脱水并生成缩略（包含“已触发脱水”信息），同时确保最近的对话消息不被丢失。
2. `RehydrationEngine` (复水引擎机制)：
   - 验证能够通过占位符形式匹配特定的历史脱水数据指针，并拉取物理临时文件以完成“复水”（重新注入上下文）的逻辑。
"""

import unittest
import os
import shutil
from uuid import uuid4

from app.services.context.sliding_window import SlidingWindow
from app.services.context.rehydration import RehydrationEngine


class ContextManagerTests(unittest.TestCase):
    """
    上下文滑动窗口与复水引擎的单元测试类。

    维护了临时测试沙盒目录，以便在磁盘上写入临时的脱水和复水文本。
    """

    def setUp(self):
        """
        初始化测试环境。

        配置：
        - 独立的工作目录 /tmp/evoloop_test_{uuid}。
        - 实例化的 SlidingWindow，软限制 Token 设为 500。
        - 实例化的 RehydrationEngine。
        """
        self.workspace_root = f"/tmp/evoloop_test_{uuid4().hex[:8]}"
        os.makedirs(self.workspace_root, exist_ok=True)
        self.window = SlidingWindow(self.workspace_root, max_tokens=1000, soft_limit_ratio=0.5)  # 软限制为 500
        self.rehydrator = RehydrationEngine(self.workspace_root)

    def tearDown(self):
        """
        清理临时沙盒文件目录。
        """
        if os.path.exists(self.workspace_root):
            shutil.rmtree(self.workspace_root)

    def test_window_no_compaction_below_limit(self):
        """
        验证当历史消息总大小在软限制范围内时，不触发脱水折叠。

        业务输入：
        - 两个简短的 user/assistant 对话。

        断言：
        - 折叠次数（compactions）必须为 0。
        - 原始对话内容依旧存在于输出的文本中。
        """
        history = [
            {"role": "user", "content": "Short message 1"},
            {"role": "assistant", "content": "Short reply 1"},
        ]
        history_str, compactions = self.window.compact(history)
        
        self.assertEqual(compactions, 0)
        self.assertIn("Short message 1", history_str)

    def test_window_triggers_compaction_above_limit(self):
        """
        验证当历史消息总 Token 大小超出软限制阈值时，自动触发对话脱水折叠。

        业务输入：
        - 包含大段重复无意义文本（超出 500 字符限制）的历史对话。

        断言：
        - 触发折叠次数（compactions）大于 0。
        - 压缩输出的文本中包含“已触发脱水”信息。
        - 最近刚发生的 user 提问 "New question." 依然保留在输出日志中，未被折叠。
        """
        # 创建大段消息以超出 Token 软限制阈值
        large_content = "Large content block. " * 50 
        history = [
            {"role": "user", "content": large_content},
            {"role": "assistant", "content": "Acknowledged."},
            {"role": "user", "content": "New question."},
            {"role": "assistant", "content": "Recent answer."},
        ]
        
        history_str, compactions = self.window.compact(history)
        
        self.assertGreater(compactions, 0)
        self.assertIn("已触发脱水", history_str)
        self.assertIn("New question.", history_str)  # 确认最近的消息依然完整保存

    def test_rehydration_injects_pointers(self):
        """
        验证复水引擎能够解析占位符并从持久化介质重新载入被压缩的文本。

        业务输入：
        - 创建物理的脱水碎片文件，内容为 "HIDDEN KNOWLEDGE"。
        - 带有 `[需要复水: {uuid}]` 标识的提问。

        断言：
        - 复水后的文本中成功读取并注入了碎片文件内的具体文本。
        """
        compaction_dir = os.path.join(self.workspace_root, "workspace", "inputs", "temp", "compaction")
        os.makedirs(compaction_dir, exist_ok=True)
        
        test_id = "abcd1234"
        with open(os.path.join(compaction_dir, f"{test_id}.txt"), "w") as f:
            f.write("HIDDEN KNOWLEDGE")
            
        user_prompt = f"Please refer to [需要复水: {test_id}] for details."
        
        rehydrated = self.rehydrator.rehydrate(user_prompt)
        self.assertIn("HIDDEN KNOWLEDGE", rehydrated)
        self.assertIn(test_id, rehydrated)


if __name__ == '__main__':
    unittest.main()


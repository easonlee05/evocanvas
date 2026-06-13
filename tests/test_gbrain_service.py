"""GBrain 知识库检索服务（GBrainKnowledge）的单元测试模块。

本测试模块主要针对从外部 CLI（gbrain）工具检索知识的场景，覆盖：
- 命令行调用超时后的降级机制。
- CLI 返回非 JSON 格式数据或异常输出时的拦截与降级处理。
- JSON 数据检索结果的脱敏与标准化处理（过滤私密路径和原始内容）。
- 非结构化纯文本检索结果的正则提取与标准化解析。
"""
import json
import subprocess
import unittest
from unittest.mock import patch

from app.services.gbrain_service import GBrainKnowledge


class GBrainKnowledgeTests(unittest.TestCase):
    """GBrainKnowledge 服务测试类。

    维护对 gbrain 命令行客户端的 mock 并验证其在各种极端输出、超时和正常解析情况下的表现。
    """

    def test_cli_timeout_degrades_instead_of_hanging(self):
        """测试 CLI 调用超时后系统是否能够安全降级而不被阻塞挂起。

        验证当 mock 出来的 subprocess.run 抛出 TimeoutExpired 异常时，
        retrieve() 接口是否能够正确捕获异常、设置 degraded=True，并返回空结果。
        """
        knowledge = GBrainKnowledge("/tmp")

        # Mock shutil.which 定位 gbrain 路径以及 subprocess.run 的超时异常
        with patch("app.services.gbrain_service.shutil.which", side_effect=[None, "/tmp/fake-gbrain"]):
            with patch("app.services.gbrain_service.subprocess.run", side_effect=[subprocess.TimeoutExpired(cmd=["gbrain"], timeout=5), subprocess.TimeoutExpired(cmd=["gbrain"], timeout=5)]):
                result = knowledge.retrieve("风控")

        # 验证降级状态和错误说明
        self.assertTrue(result["degraded"])
        self.assertEqual(result["items"], [])
        self.assertIn("timeout", result["error"].lower())

    def test_invalid_json_degrades_without_returning_raw_output(self):
        """测试当 CLI 返回损坏的、非 JSON 格式输出时，检索服务能拦截异常并实现无缝降级。

        验证当 stdout 返回非 JSON 字符串时，系统不会抛出 JSONDecodeError 异常，
        而是将 degraded 标志设为 True 并提供对应的降级错误描述。
        """
        knowledge = GBrainKnowledge("/tmp")
        completed = subprocess.CompletedProcess(
            args=["gbrain", "search"],
            returncode=0,
            stdout="not-json at all",
            stderr="",
        )

        # Mock subprocess 调用以返回破损的非 JSON 数据
        with patch("app.services.gbrain_service.shutil.which", side_effect=[None, "/tmp/fake-gbrain"]):
            with patch("app.services.gbrain_service.subprocess.run", return_value=completed):
                result = knowledge.retrieve("结算")

        # 断言降级逻辑生效，且没有暴露破损原始文本给上层
        self.assertTrue(result["degraded"])
        self.assertEqual(result["items"], [])
        self.assertIn("no parsable", result["error"])

    def test_json_results_are_normalized_to_safe_summaries(self):
        """测试 JSON 格式的检索结果能够被正确脱敏和规范化。

        模拟 gbrain 以 JSON 格式返回原始文献信息，
        验证 retrieve 能够剔除本地绝对路径（path）和原始内容（content），
        仅保留标题（title）、摘要（summary）和分值（score）等安全属性，实现合规脱敏。
        """
        knowledge = GBrainKnowledge("/tmp")
        payload = {
            "results": [
                {
                    "title": "规则 A",
                    "summary": "限流策略",
                    "path": "/secret/local/path.md",
                    "content": "full private material",
                    "score": 0.87,
                }
            ]
        }
        completed = subprocess.CompletedProcess(
            args=["gbrain", "search"],
            returncode=0,
            stdout=json.dumps(payload, ensure_ascii=False),
            stderr="",
        )

        # Mock 执行 gbrain search 返回合规 payload
        with patch("app.services.gbrain_service.shutil.which", side_effect=[None, "/tmp/fake-gbrain"]):
            with patch("app.services.gbrain_service.subprocess.run", return_value=completed):
                result = knowledge.retrieve("限流")

        # 验证结果未降级，且敏感字段 path 和 content 已被成功删除
        self.assertFalse(result["degraded"])
        self.assertEqual(result["items"][0]["title"], "规则 A")
        self.assertEqual(result["items"][0]["summary"], "限流策略")
        self.assertEqual(result["items"][0]["score"], 0.87)
        self.assertNotIn("path", result["items"][0])
        self.assertNotIn("content", result["items"][0])

    def test_text_results_are_parsed_into_safe_items(self):
        """测试对于非结构化的文本格式检索结果的正则提取与标准化解析。

        模拟 gbrain 以格式化纯文本 `[score] title -- summary` 的形式返回搜索记录，
        验证检索服务能够以正则表达式解析各部分内容，并组合成具有 title/summary 的安全数据项列表。
        """
        knowledge = GBrainKnowledge("/tmp")
        completed = subprocess.CompletedProcess(
            args=["gbrain", "query"],
            returncode=0,
            stdout="[1.2345] agent_map -- # Agent Map\n[0.9988] readme -- # PM-Agent Platform Backend\n",
            stderr="",
        )

        # Mock 执行 gbrain query 返回特定格式纯文本
        with patch("app.services.gbrain_service.shutil.which", side_effect=[None, "/tmp/fake-gbrain"]):
            with patch("app.services.gbrain_service.subprocess.run", return_value=completed):
                result = knowledge.retrieve("WorkflowEngine")

        # 校验正则转换得到的结构化字段
        self.assertFalse(result["degraded"])
        self.assertEqual(result["items"][0]["title"], "agent_map")
        self.assertEqual(result["items"][0]["summary"], "# Agent Map")


if __name__ == "__main__":
    unittest.main()


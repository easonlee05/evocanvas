"""LLM 遥测（Telemetry）及降级机制的单元测试模块。

本测试模块主要覆盖以下场景：
- 流式 Chat 路由（Stream Chat Route）下发送的耗时与吞吐量遥测指标事件（telemetry event）的正确触发与负载属性脱敏。
- 当底层接口返回 400 不支持 OpenAI API 格式错误时，系统降级并自动降级为 Anthropic 协议进行请求的流程。
- 在降级为 Anthropic 时，针对 "Writer" 与 "非 Writer" 角色自动配置不同大小的 token 预算上限（max_tokens）。
"""
import json
import unittest
from unittest.mock import patch

from app.services.llm import OpenAILLM


class FakeStreamResponse:
    """模拟 HTTP 流式响应的 Fake 类。

    提供支持 with 上下文管理器语法、HTTP 状态码设置、以及按行产生字节流（iter_lines）的测试替身。
    """

    def __init__(self, status_code=200, lines=None, content=b""):
        self.status_code = status_code
        self._lines = lines or []
        self.content = content
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def iter_lines(self):
        """流式迭代返回生成的行。"""
        for line in self._lines:
            yield line


class OpenAILLMTelemetryTests(unittest.TestCase):
    """OpenAILLM 遥测和降级流程测试类。

    校验 timing（时间耗时）、throughput（吞吐量）、脱敏策略以及回退降级为 Anthropic API 时的动态 max_tokens 策略。
    """

    def test_stream_chat_route_emits_timing_and_throughput_telemetry(self):
        """测试流式对话是否会触发耗时与吞吐量的遥测监控事件。

        验证流式响应过程中，是否按顺序向外部 telemetry 回调输出 `llm.call.started`、`llm.call.headers_received`、
        `llm.call.first_token` 和 `llm.call.completed` 等事件，并校验最终的字符吞吐量及脱敏脱路径等关键属性。
        """
        response = FakeStreamResponse(
            status_code=200,
            lines=[
                b'data: {"choices":[{"delta":{"content":"hello"}}]}',
                b'data: {"choices":[{"delta":{"content":" world"}}]}',
                b'data: [DONE]',
            ],
        )
        telemetry_events = []

        # Mock requests.post 以重定向到我们模拟的流式响应
        with patch("requests.post", return_value=response) as post:
            llm = OpenAILLM(api_key="secret", base_url="https://relay.example.test/api/v1")
            chunks = list(llm.invoke_stream("PM", "draft", {"title": "诊断", "goal": "测速"}, telemetry=lambda event, payload: telemetry_events.append((event, payload))))

        # 验证返回的内容片段是否组装正确，并且只调用了一次外部网络
        self.assertEqual(chunks, ["hello", " world"])
        self.assertEqual(post.call_count, 1)
        
        # 验证遥测事件流
        event_names = [event for event, _ in telemetry_events]
        self.assertEqual(event_names[0], "llm.call.started")
        self.assertIn("llm.call.headers_received", event_names)
        self.assertIn("llm.call.first_token", event_names)
        self.assertEqual(event_names[-1], "llm.call.completed")
        
        # 校验 completed 事件中收集的统计属性以及脱敏行为（敏感 API Key 不得泄露）
        completed = telemetry_events[-1][1]
        self.assertEqual(completed["output_chars"], 11)
        self.assertEqual(completed["chunk_count"], 2)
        self.assertEqual(completed["base_url_host"], "relay.example.test")
        self.assertNotIn("api_key", completed)

    def test_writer_anthropic_fallback_uses_large_document_token_budget(self):
        """测试 Writer 角色降级为 Anthropic 时，是否使用大文档 token 预算。

        模拟第一步请求 OpenAI 格式接口返回 400 失败，随后触发系统降级重试为 Anthropic messages API。
        验证当角色为 Writer 时，重试参数中 max_tokens 被自动调大到 16000 以上。
        """
        unsupported = json.dumps({"error": {"message": "不支持 Api格式"}}).encode("utf-8")
        responses = [
            FakeStreamResponse(status_code=400, content=unsupported),
            FakeStreamResponse(
                status_code=200,
                lines=[
                    b'data: {"type":"content_block_delta","delta":{"text":"doc"}}',
                    b'data: {"type":"message_stop"}',
                ],
            ),
        ]
        captured_payloads = []

        def fake_post(url, json=None, headers=None, stream=None, timeout=None):
            captured_payloads.append({"url": url, "json": json, "timeout": timeout})
            return responses.pop(0)

        # Mock requests.post，以便在第一次 400 失败后，第二次降级为 Anthropic
        with patch("requests.post", side_effect=fake_post):
            llm = OpenAILLM(api_key="secret", base_url="https://relay.example.test/api/v1")
            chunks = list(llm.invoke_stream("Writer", "write final PRD", {"title": "长文档", "goal": "完整输出"}))

        self.assertEqual(chunks, ["doc"])
        # 验证第二次降级请求指向了 Anthropic 的 messages 端点，并且 max_tokens 符合大预算
        self.assertEqual(captured_payloads[1]["url"], "https://relay.example.test/api/v1/messages")
        self.assertGreaterEqual(captured_payloads[1]["json"]["max_tokens"], 16000)

    def test_non_writer_anthropic_fallback_keeps_compact_token_budget(self):
        """测试非 Writer 角色降级为 Anthropic 时，保持精简的 token 预算。

        模拟同样的降级触发过程。由于当前调用角色是非 Writer（如 PM），
        验证重试请求中的 max_tokens 被控制在精简的 4096 tokens 内。
        """
        unsupported = json.dumps({"error": {"message": "不支持 Api格式"}}).encode("utf-8")
        responses = [
            FakeStreamResponse(status_code=400, content=unsupported),
            FakeStreamResponse(status_code=200, lines=[b'data: {"type":"content_block_delta","delta":{"text":"ok"}}']),
        ]
        captured_payloads = []

        def fake_post(url, json=None, headers=None, stream=None, timeout=None):
            captured_payloads.append({"url": url, "json": json})
            return responses.pop(0)

        # Mock 拦截请求，针对非 Writer 角色进行调用
        with patch("requests.post", side_effect=fake_post):
            llm = OpenAILLM(api_key="secret", base_url="https://relay.example.test/api/v1")
            list(llm.invoke_stream("PM", "draft", {"title": "短评审", "goal": "挑战风险"}))

        # 验证第二次请求的 max_tokens 为精简规格
        self.assertEqual(captured_payloads[1]["json"]["max_tokens"], 4096)


if __name__ == "__main__":
    unittest.main()


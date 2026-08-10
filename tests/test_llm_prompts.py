"""LLM Prompt 装配测试。

覆盖 EvoCanvas 运行时提示词中最关键的行为约束，防止 system / stage / object /
receipt 四层再次退化成只有全局口号、没有角色边界的状态。
"""

import unittest

from app.services.llm import OpenAILLM


class OpenAILLMPromptAssemblyTests(unittest.TestCase):
    """验证 Prompt 组装结果是否兑现当前产品收敛顺序。"""

    def setUp(self) -> None:
        self.llm = OpenAILLM(api_key="secret", base_url="https://relay.example.test/api/v1")

    def test_system_prompt_elevates_restraint_and_flat_formatting_rules(self) -> None:
        """系统基座提示应上提克制性与扁平格式纪律。"""
        system_prompt, _, _ = self.llm._build_prompts(
            "PM",
            "请帮我整理当前需求",
            {"title": "整理需求", "goal": "先识别不确定性"},
        )

        self.assertIn("默认帮助用户看清问题、边界与选项，而不是替用户越权拍板", system_prompt)
        self.assertIn("不使用嵌套列表", system_prompt)
        self.assertIn("简单回应通常 1-2 段即可", system_prompt)

    def test_clarifier_prompt_contains_stage_object_and_receipt_rules(self) -> None:
        """Clarifier 应同时拿到阶段边界、对象语义与回执骨架。"""
        system_prompt, _, _ = self.llm._build_prompts(
            "Clarifier",
            "这里有冲突，请帮我澄清",
            {"title": "澄清支付边界", "goal": "找出阻塞点"},
        )

        self.assertIn("当前角色：澄清推进员", system_prompt)
        self.assertIn("待澄清项至少说明", system_prompt)
        self.assertIn("本轮形成内容、未决与冲突、对象状态、建议下一步", system_prompt)

    def test_option_builder_defaults_to_options_not_implicit_decision(self) -> None:
        """方案构建默认应先给选项而不是默认拍板。"""
        system_prompt, _, _ = self.llm._build_prompts(
            "OptionBuilder",
            "比较一下方案 A 和 B",
            {"title": "方案对比", "goal": "先看取舍"},
        )

        self.assertIn("默认先给可比选项，不主动替用户拍板", system_prompt)
        self.assertIn("如果给出推荐，必须单列“推荐理由”", system_prompt)

    def test_handoff_builder_prompt_keeps_unconfirmed_content_visible(self) -> None:
        """交接收束员必须保留未确认边界，不得为了完整感吞掉风险。"""
        system_prompt, _, _ = self.llm._build_prompts(
            "HandoffBuilder",
            "整理当前结构化交接物",
            {"title": "交接草稿", "goal": "保留未决边界"},
        )

        self.assertIn("结构化交接物至少区分", system_prompt)
        self.assertIn("高价值但未确认的草稿", system_prompt)
        self.assertIn("交接物的可读性不能凌驾于真实性之上", system_prompt)

    def test_stream_mode_requires_compact_progress_updates(self) -> None:
        """非 writer 流式模式应强制使用紧凑的过程回执。"""
        system_prompt, _, _ = self.llm._build_prompts(
            "InputCompiler",
            "这是新的会议纪要",
            {"title": "输入编译", "goal": "先收敛输入"},
            is_stream=True,
        )

        self.assertIn("当前为实时对话模式", system_prompt)
        self.assertIn("本轮形成内容、未决边界、建议下一步", system_prompt)
        self.assertIn("每次输出尽量控制在 2 段内", system_prompt)


if __name__ == "__main__":
    unittest.main()

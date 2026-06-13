import unittest

from app.canvas.agent.supervisor import CanvasSupervisor


class FakeLLM:
    """测试替身，占位表示 supervisor 依赖的上层模型接口。"""


class CanvasSupervisorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.supervisor = CanvasSupervisor(llm=FakeLLM())
        self.workspace_context = {"workspace_id": "ws_demo"}

    def test_routes_clarification_prompt_to_clarifier_role(self) -> None:
        plan = self.supervisor.recognize_and_plan(
            workspace_context=self.workspace_context,
            message="先把一期范围和误杀成本的待澄清问题列出来",
        )

        self.assertEqual(plan.intent, "clarification")
        self.assertIn("Clarifier", plan.roles)
        self.assertNotIn("HandoffBuilder", plan.roles)
        self.assertIn("mark_conflict", plan.allowed_mutation_types)

    def test_routes_handoff_prompt_to_handoff_builder_role(self) -> None:
        plan = self.supervisor.recognize_and_plan(
            workspace_context=self.workspace_context,
            message="把当前画布整理成结构化交接物草稿",
        )

        self.assertEqual(plan.intent, "handoff")
        self.assertEqual(plan.roles, ["HandoffBuilder"])
        self.assertEqual(plan.allowed_mutation_types, ["refresh_handoff_draft"])

    def test_defaults_to_input_compilation_plan_for_new_material(self) -> None:
        plan = self.supervisor.recognize_and_plan(
            workspace_context=self.workspace_context,
            message="这里有一段新的会议纪要，先帮我整理输入",
        )

        self.assertEqual(plan.intent, "input_compilation")
        self.assertEqual(plan.roles, ["InputCompiler"])
        self.assertIn("add_card", plan.allowed_mutation_types)
        self.assertIn("add_relation", plan.allowed_mutation_types)


if __name__ == "__main__":
    unittest.main()

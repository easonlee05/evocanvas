import unittest

from app.canvas.agent import __all__ as canvas_agent_exports
from app.canvas.agent.contracts import CanvasTurnPlan, RoleOutput
from app.canvas.agent.roles import get_intent_routes, get_role
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
        self.assertIsInstance(plan.roles, tuple)
        self.assertIsInstance(plan.allowed_mutation_types, tuple)

    def test_routes_handoff_prompt_to_handoff_builder_role(self) -> None:
        plan = self.supervisor.recognize_and_plan(
            workspace_context=self.workspace_context,
            message="把当前画布整理成结构化交接物草稿",
        )

        self.assertEqual(plan.intent, "handoff")
        self.assertEqual(plan.roles, ("HandoffBuilder",))
        self.assertEqual(plan.allowed_mutation_types, ("refresh_handoff_draft",))

    def test_defaults_to_input_compilation_plan_for_new_material(self) -> None:
        plan = self.supervisor.recognize_and_plan(
            workspace_context=self.workspace_context,
            message="这里有一段新的会议纪要，先帮我整理输入",
        )

        self.assertEqual(plan.intent, "input_compilation")
        self.assertEqual(plan.roles, ("InputCompiler",))
        self.assertIn("add_card", plan.allowed_mutation_types)
        self.assertIn("add_relation", plan.allowed_mutation_types)

    def test_routes_constraint_prompt_to_constraint_steward_role(self) -> None:
        plan = self.supervisor.recognize_and_plan(
            workspace_context=self.workspace_context,
            message="先把一期范围边界和业务约束沉淀出来",
        )

        self.assertEqual(plan.intent, "constraint")
        self.assertEqual(plan.roles, ("ConstraintSteward",))
        self.assertIn("promote_to_constraint_draft", plan.allowed_mutation_types)

    def test_routes_decision_prompt_to_decision_steward_role(self) -> None:
        plan = self.supervisor.recognize_and_plan(
            workspace_context=self.workspace_context,
            message="把这次方案取舍整理成需要拍板的待决策项",
        )

        self.assertEqual(plan.intent, "decision")
        self.assertEqual(plan.roles, ("DecisionSteward",))
        self.assertIn("create_decision_request", plan.allowed_mutation_types)

    def test_composes_roles_for_mixed_clarification_and_handoff_prompt(self) -> None:
        plan = self.supervisor.recognize_and_plan(
            workspace_context=self.workspace_context,
            message="先把待澄清问题收束一下，再整理成结构化交接物草稿",
        )

        self.assertEqual(plan.intent, "clarification+handoff")
        self.assertEqual(plan.roles, ("Clarifier", "HandoffBuilder"))
        self.assertIn("mark_conflict", plan.allowed_mutation_types)
        self.assertIn("refresh_handoff_draft", plan.allowed_mutation_types)

    def test_role_contracts_are_exported_without_mutable_registry(self) -> None:
        clarifier = get_role("Clarifier")

        self.assertIsInstance(clarifier.allowed_mutation_types, tuple)
        self.assertNotIn("ROLE_REGISTRY", canvas_agent_exports)

    def test_contracts_break_nested_aliasing(self) -> None:
        metadata = {"matched": {"roles": ["Clarifier"]}}
        mutations = [{"payload": {"status": "draft", "tags": ["gap"]}}]

        plan = CanvasTurnPlan(
            intent="clarification",
            roles=("Clarifier",),
            allowed_mutation_types=("mark_conflict",),
            metadata=metadata,
        )
        output = RoleOutput(role="Clarifier", proposed_mutations=tuple(mutations))

        metadata["matched"]["roles"].append("HandoffBuilder")
        mutations[0]["payload"]["tags"].append("handoff")

        self.assertEqual(plan.metadata["matched"]["roles"], ("Clarifier",))
        self.assertEqual(output.proposed_mutations[0]["payload"]["tags"], ("gap",))

    def test_context_recommends_input_compilation_for_materials(self) -> None:
        plan = self.supervisor.recognize_and_plan(
            workspace_context={"workspace_id": "ws_demo", "material_ids": ["mat_1"]},
            message="对这个新来的处理一下",
        )
        self.assertEqual(plan.intent, "input_compilation")
        self.assertEqual(plan.roles, ("InputCompiler",))

    def test_context_recommends_role_based_on_selected_cards(self) -> None:
        plan = self.supervisor.recognize_and_plan(
            workspace_context={
                "workspace_id": "ws_demo",
                "selected_cards": [
                    {"card_id": "card_1", "kind": "clarification", "status": "open"},
                    {"card_id": "card_2", "kind": "constraint", "status": "open"},
                ]
            },
            message="对这些选中卡片做些什么",
        )
        self.assertIn("clarification", plan.intent)
        self.assertIn("constraint", plan.intent)
        self.assertIn("Clarifier", plan.roles)
        self.assertIn("ConstraintSteward", plan.roles)

    def test_recognize_and_plan_with_real_llm_json(self) -> None:
        import unittest.mock
        from app.core.ports import LLMResult
        
        mock_llm = unittest.mock.MagicMock()
        mock_llm.api_key = "some_valid_key"
        mock_llm.invoke.return_value = LLMResult(
            content='```json\n{"intent": "clarification+decision", "roles": ["Clarifier", "DecisionSteward"]}\n```'
        )
        
        supervisor = CanvasSupervisor(llm=mock_llm)
        plan = supervisor.recognize_and_plan(
            workspace_context={"workspace_id": "ws_demo"},
            message="一些复杂的语义输入"
        )
        
        self.assertEqual(plan.intent, "clarification+decision")
        self.assertEqual(plan.roles, ("Clarifier", "DecisionSteward"))
        self.assertIn("mark_conflict", plan.allowed_mutation_types)
        self.assertIn("create_decision_request", plan.allowed_mutation_types)

    def test_every_route_references_registered_roles(self) -> None:
        for route in get_intent_routes():
            self.assertGreater(len(route.roles), 0)
            for role_name in route.roles:
                self.assertEqual(get_role(role_name).name, role_name)


if __name__ == "__main__":
    unittest.main()

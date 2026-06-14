import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.fakes import FakeKnowledge, FakeLLM, FakeStorage
from app.services.tool_service import ToolService
from app.workflows.definitions import build_task_registry
from app.workflows.engine import WorkflowEngine


class CanvasWorkflowDefinitionTests(unittest.TestCase):
    def test_registry_includes_evocanvas_canvas_turn_definition(self) -> None:
        registry = build_task_registry()

        self.assertIn("evocanvas_canvas_turn", registry)

        definition = registry["evocanvas_canvas_turn"]

        self.assertEqual(definition.type, "evocanvas_canvas_turn")
        self.assertEqual(definition.workflow.name, "canvas_turn")
        self.assertEqual(definition.workflow.version, "1.0")
        self.assertEqual(definition.display_name, "EvoCanvas 画布回合")
        self.assertEqual(
            [step.id for step in definition.workflow.steps],
            [
                "load_canvas_context",
                "run_canvas_supervisor",
                "merge_canvas_proposal",
                "emit_canvas_events",
            ],
        )
        self.assertEqual(
            [step.type for step in definition.workflow.steps],
            ["context", "agent", "agent", "context"],
        )
        self.assertIn("username", definition.input_schema["required"])

    def test_canvas_supervisor_has_read_only_tool_policy(self) -> None:
        definition = build_task_registry()["evocanvas_canvas_turn"]

        self.assertTrue(
            definition.tool_policy.is_allowed(
                "CanvasSupervisor",
                "run_canvas_supervisor",
                "material.read",
            )
        )
        self.assertTrue(
            definition.tool_policy.is_allowed(
                "CanvasSupervisor",
                "run_canvas_supervisor",
                "knowledge.retrieve",
            )
        )
        self.assertFalse(
            definition.tool_policy.is_allowed(
                "CanvasSupervisor",
                "run_canvas_supervisor",
                "artifact.write",
            )
        )

    def test_workflow_engine_can_initialize_for_canvas_turn(self) -> None:
        with TemporaryDirectory() as tmpdir:
            storage = FakeStorage(Path(tmpdir))
            tool_service = ToolService.default(root=storage, knowledge=FakeKnowledge())
            engine = WorkflowEngine(tool_service=tool_service, llm=FakeLLM(), storage=storage)
            definition = build_task_registry()["evocanvas_canvas_turn"]

            for step in definition.workflow.steps:
                self.assertIsNotNone(engine.step_executors.get(step.type, step.id))


if __name__ == "__main__":
    unittest.main()

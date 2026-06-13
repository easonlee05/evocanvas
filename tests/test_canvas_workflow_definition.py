import unittest

from app.workflows.definitions import build_task_registry


class CanvasWorkflowDefinitionTests(unittest.TestCase):
    def test_registry_includes_evocanvas_canvas_turn_definition(self) -> None:
        registry = build_task_registry()

        self.assertIn("evocanvas_canvas_turn", registry)

        definition = registry["evocanvas_canvas_turn"]

        self.assertEqual(definition.type, "evocanvas_canvas_turn")
        self.assertEqual(definition.workflow.name, "canvas_turn")
        self.assertEqual(definition.workflow.version, "1.0")
        self.assertEqual(
            [step.id for step in definition.workflow.steps],
            [
                "load_canvas_context",
                "run_canvas_supervisor",
                "merge_canvas_proposal",
                "emit_canvas_events",
            ],
        )


if __name__ == "__main__":
    unittest.main()

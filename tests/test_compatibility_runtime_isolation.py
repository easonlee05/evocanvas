"""兼容工作流执行链与 Pi Canvas 主链的装配隔离测试。"""

from __future__ import annotations

import unittest

from app.services.compatibility_runtime import LazyCompatibilityWorkflowEngine


class CompatibilityRuntimeIsolationTests(unittest.TestCase):
    def test_compatibility_engine_is_created_only_when_compatibility_capability_is_used(self) -> None:
        created: list[str] = []

        class Engine:
            llm = object()
            tool_service = object()

        engine = LazyCompatibilityWorkflowEngine(lambda: created.append("created") or Engine())

        self.assertFalse(engine.initialized)
        self.assertEqual(created, [])
        self.assertIsNotNone(engine.llm)
        self.assertTrue(engine.initialized)
        self.assertEqual(created, ["created"])


if __name__ == "__main__":
    unittest.main()

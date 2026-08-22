"""Codex CLI handler tests.

验证第一版真实 Codex handler 的关键约束：
1. 通过本地 `codex exec` runner 执行；
2. 返回基于前后快照的真实 diff/result bundle；
3. 若执行后没有真实文件变更，则不得伪装为成功。
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.codex_cli_handler import CodexCLIHandler


class DummyTask:
    """测试用最小任务对象。"""

    def __init__(self, task_id: str = "task_demo"):
        self.task_id = task_id


class CodexCLIHandlerTests(unittest.TestCase):
    """验证 CodexCLIHandler 的真实结果提取逻辑。"""

    def test_execute_returns_real_diff_from_workspace_changes(self):
        """runner 修改工作区文件后，handler 应返回真实 diff 与 artifacts。"""
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        workspace = Path(temp.name)
        target = workspace / "app.py"
        target.write_text("print('before')\n", encoding="utf-8")

        calls = {}

        def fake_runner(cmd, prompt, cwd):
            calls["cmd"] = cmd
            calls["prompt"] = prompt
            calls["cwd"] = cwd
            target.write_text("print('after')\n", encoding="utf-8")
            return {"implementation_summary": "Updated app.py through Codex"}

        handler = CodexCLIHandler(
            workspace_root=workspace,
            codex_path="/opt/homebrew/bin/codex",
            runner=fake_runner,
        )

        result = handler.execute(DummyTask(), "# Agent Package")

        self.assertEqual(calls["cwd"], workspace)
        self.assertEqual(calls["cmd"][:4], ["/opt/homebrew/bin/codex", "-a", "on-failure", "exec"])
        self.assertIn("--ephemeral", calls["cmd"])
        self.assertIn("--ignore-user-config", calls["cmd"])
        self.assertEqual(result["peer_target"], "codex")
        self.assertEqual(result["implementation_summary"], "Updated app.py through Codex")
        self.assertIn("app.py", result["diff"])
        self.assertEqual(result["artifacts"][0]["path"], "app.py")

    def test_execute_rejects_fake_success_when_workspace_unchanged(self):
        """若 runner 未产生真实文件变更，handler 应拒绝返回成功 bundle。"""
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        workspace = Path(temp.name)
        (workspace / "app.py").write_text("print('same')\n", encoding="utf-8")

        def fake_runner(cmd, prompt, cwd):
            return {"implementation_summary": "Claimed success without changes"}

        handler = CodexCLIHandler(
            workspace_root=workspace,
            codex_path="/opt/homebrew/bin/codex",
            runner=fake_runner,
        )

        with self.assertRaises(ValueError):
            handler.execute(DummyTask(), "# Agent Package")

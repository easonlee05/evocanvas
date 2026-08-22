"""Real Codex CLI peer handler.

第一版真实 Codex handler 通过本机 `codex exec` 非交互调用实现。
它不会信任模型自报成功，而是以工作区前后快照计算真实变更，
并把这些变更编译为 result bundle 供控制面 intake。
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict


class CodexCLIHandler:
    """通过本机 Codex CLI 执行 agent package 的真实协作 handler。"""

    def __init__(
        self,
        workspace_root: Path,
        codex_path: str = "codex",
        model: str | None = None,
        sandbox_mode: str = "workspace-write",
        approval_policy: str = "on-failure",
        codex_home: Path | None = None,
        runner: Callable[[list[str], str, Path], Dict[str, Any]] | None = None,
    ):
        """初始化真实 Codex CLI handler。

        Args:
            workspace_root: 真实代码工作区根目录。
            codex_path: 本机 codex 可执行文件路径。
            model: 可选模型名。
            sandbox_mode: 传给 codex exec 的 sandbox 模式。
            approval_policy: 传给 codex exec 的审批策略。
            codex_home: Codex 运行时 home 目录；未指定时使用系统临时目录下的可写位置。
            runner: 可选命令执行器，测试时用于替换真实 subprocess 调用。
        """
        self.workspace_root = Path(workspace_root)
        self.codex_path = codex_path
        self.model = model
        self.sandbox_mode = sandbox_mode
        self.approval_policy = approval_policy
        self.codex_home = Path(codex_home) if codex_home else Path(tempfile.gettempdir()) / "evoloop-codex-home"
        self.runner = runner or self._default_runner
        self._active_output_file: Path | None = None
        self._active_schema_file: Path | None = None

    def execute(self, task: Any, package_text: str) -> Dict[str, Any]:
        """执行 agent package，并根据真实文件变更生成 result bundle。"""
        before = self._snapshot_workspace()
        prompt = self._build_prompt(task, package_text)
        with tempfile.TemporaryDirectory(prefix="evoloop-codex-handler-") as temp_dir:
            temp_root = Path(temp_dir)
            schema_file = temp_root / "codex-result-schema.json"
            output_file = temp_root / "codex-last-message.json"
            schema_file.write_text(json.dumps(self._output_schema(), ensure_ascii=False, indent=2), encoding="utf-8")
            cmd = self._build_command(output_file=output_file, schema_file=schema_file)
            self._active_output_file = output_file
            self._active_schema_file = schema_file
            try:
                payload = self.runner(cmd, prompt, self.workspace_root)
            finally:
                self._active_output_file = None
                self._active_schema_file = None

        after = self._snapshot_workspace()
        diff_text, changed_paths = self._build_diff(before, after)
        if not changed_paths:
            raise ValueError("codex handler produced no workspace changes")

        implementation_summary = (
            str(payload.get("implementation_summary") or payload.get("summary") or "").strip()
            or f"Codex changed {len(changed_paths)} files."
        )
        artifacts = [{"path": path, "kind": self._artifact_kind(path)} for path in changed_paths]
        return {
            "peer_target": "codex",
            "implementation_summary": implementation_summary,
            "diff": diff_text,
            "artifacts": artifacts,
            "raw_peer_result": payload,
        }

    def _build_command(self, output_file: Path, schema_file: Path) -> list[str]:
        """构建非交互 `codex exec` 命令。"""
        cmd = [
            self.codex_path,
            "-a",
            self.approval_policy,
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "-",
            "-C",
            str(self.workspace_root),
            "-s",
            self.sandbox_mode,
            "--output-schema",
            str(schema_file),
            "-o",
            str(output_file),
        ]
        if self.model:
            cmd.extend(["-m", self.model])
        return cmd

    def _build_prompt(self, task: Any, package_text: str) -> str:
        """为 Codex 构建一次性执行提示词。"""
        return (
            "You are Codex, an AI technical peer collaborating with Evoloop.\n"
            "Execute the requested implementation work directly in the workspace.\n"
            "Follow the provided agent package strictly and avoid unrelated edits.\n"
            "After finishing, return JSON only matching the provided schema.\n\n"
            f"Task ID: {getattr(task, 'task_id', 'unknown')}\n"
            "Required JSON field:\n"
            '- "implementation_summary": concise summary of what you actually changed.\n\n'
            "<agent_package>\n"
            f"{package_text}\n"
            "</agent_package>\n"
        )

    @staticmethod
    def _output_schema() -> Dict[str, Any]:
        """Codex 最终消息的 JSON Schema。"""
        return {
            "type": "object",
            "required": ["implementation_summary"],
            "properties": {
                "implementation_summary": {"type": "string"},
                "summary": {"type": "string"},
            },
            "additionalProperties": True,
        }

    def _default_runner(self, cmd: list[str], prompt: str, cwd: Path) -> Dict[str, Any]:
        """默认 runner：真实调用本机 `codex exec` 并解析最后消息 JSON。"""
        self.codex_home.mkdir(parents=True, exist_ok=True)
        # 安全加固：环境变量白名单过滤，剥离宿主机全部密钥和 Token
        allowed_env_keys = {
            "PATH",
            "HOME",
            "USER",
            "LOGNAME",
            "SHELL",
            "LANG",
            "LC_ALL",
            "TMPDIR",
            "PYTHONUNBUFFERED",
            "TERM",
        }
        env = {k: v for k, v in os.environ.items() if k in allowed_env_keys}
        env["CODEX_HOME"] = str(self.codex_home)
        completed = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            capture_output=True,
            cwd=str(cwd),
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout or "").strip()
            raise ValueError(f"codex exec failed: {stderr}")
        if not self._active_output_file or not self._active_output_file.exists():
            raise ValueError("codex exec did not produce output-last-message file")
        raw = self._active_output_file.read_text(encoding="utf-8").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"codex exec returned non-JSON final message: {exc}") from exc

    def _snapshot_workspace(self) -> Dict[str, Dict[str, Any]]:
        """递归快照当前工作区文本文件状态，用于后续真实 diff 计算。"""
        snapshot: Dict[str, Dict[str, Any]] = {}
        for path in self.workspace_root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(self.workspace_root).as_posix()
            if self._should_ignore(rel):
                continue
            try:
                content_bytes = path.read_bytes()
            except OSError:
                continue
            sha = hashlib.sha256(content_bytes).hexdigest()
            text = None
            try:
                text = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = None
            snapshot[rel] = {"sha256": sha, "text": text}
        return snapshot

    @staticmethod
    def _should_ignore(rel_path: str) -> bool:
        """过滤不应参与真实 diff 计算的目录。"""
        ignore_prefixes = (
            ".git/",
            ".evoloop_storage/",
            ".tmp.driveupload/",
            "workspace/outputs/",
            "workspace/inputs/temp/",
            "__pycache__/",
        )
        return rel_path.startswith(ignore_prefixes)

    def _build_diff(
        self,
        before: Dict[str, Dict[str, Any]],
        after: Dict[str, Dict[str, Any]],
    ) -> tuple[str, list[str]]:
        """对比前后快照，生成只属于本次 handler 执行的 diff。"""
        changed_paths = sorted(
            path
            for path in set(before) | set(after)
            if before.get(path, {}).get("sha256") != after.get(path, {}).get("sha256")
        )
        sections: list[str] = []
        for path in changed_paths:
            before_text = before.get(path, {}).get("text")
            after_text = after.get(path, {}).get("text")
            if before_text is not None and after_text is not None:
                diff_lines = difflib.unified_diff(
                    before_text.splitlines(),
                    after_text.splitlines(),
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                    lineterm="",
                )
                sections.append("\n".join(diff_lines))
            elif before_text is None and after_text is not None:
                diff_lines = difflib.unified_diff(
                    [],
                    after_text.splitlines(),
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                    lineterm="",
                )
                sections.append("\n".join(diff_lines))
            elif before_text is not None and after_text is None:
                diff_lines = difflib.unified_diff(
                    before_text.splitlines(),
                    [],
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                    lineterm="",
                )
                sections.append("\n".join(diff_lines))
            else:
                sections.append(f"Binary or non-UTF8 file changed: {path}")
        return "\n\n".join(section for section in sections if section).strip(), changed_paths

    @staticmethod
    def _artifact_kind(path: str) -> str:
        """根据路径后缀推导简化的 artifact kind。"""
        suffix = Path(path).suffix.lower()
        if suffix in {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yml", ".yaml", ".md"}:
            return "code"
        return "file"

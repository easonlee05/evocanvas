"""EvoCanvas 工作区仓储。

当前仅实现 Task 2 所需的最小持久化能力：
- 在 `canvas/workspaces/{workspace_id}/workspace.json` 下保存工作区根对象
- 从同一路径加载工作区根对象
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.canvas.domain.workspace import CanvasWorkspace


class CanvasRepository:
    """面向 EvoCanvas 工作区根对象的最小文件仓储。"""

    def __init__(self, storage: Any):
        """基于现有底座存储实例初始化仓储。

        Args:
            storage: 提供 `canvas_root()` 的底层存储对象。
        """
        self.storage = storage

    def _workspace_dir(self, workspace_id: str) -> Path:
        """返回指定工作区的持久化目录，并在保存前确保目录存在。"""

        return self.storage.canvas_root() / "workspaces" / workspace_id

    def save_workspace(self, workspace: CanvasWorkspace) -> None:
        """持久化工作区根对象到首版约定路径。"""

        workspace_dir = self._workspace_dir(workspace.workspace_id)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        workspace_dir.joinpath("workspace.json").write_text(
            json.dumps(workspace.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_workspace(self, workspace_id: str) -> Optional[CanvasWorkspace]:
        """从首版约定路径读取工作区根对象。"""

        path = self._workspace_dir(workspace_id) / "workspace.json"
        if not path.exists():
            return None
        return CanvasWorkspace.from_dict(json.loads(path.read_text(encoding="utf-8")))

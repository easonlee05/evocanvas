"""EvoCanvas 工作画布根对象。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict


@dataclass
class CanvasWorkspace:
    """承载当前工作台身份与元信息的根对象。

    Workspace 本身不内嵌完整对象图，只引用当前活跃快照和交接状态。
    """

    workspace_id: str
    title: str
    objective: str = ""
    active_snapshot_id: str = ""
    handoff_status: str = "not_ready"
    metadata: Dict[str, Any] = field(default_factory=dict)
    handoff_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将工作区序列化为字典。"""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasWorkspace":
        """从字典恢复工作区实例。"""

        return cls(
            workspace_id=data["workspace_id"],
            title=data.get("title", ""),
            objective=data.get("objective", ""),
            active_snapshot_id=data.get("active_snapshot_id", ""),
            handoff_status=data.get("handoff_status", "not_ready"),
            metadata=dict(data.get("metadata", {})),
            handoff_metadata=dict(data.get("handoff_metadata", {})),
        )

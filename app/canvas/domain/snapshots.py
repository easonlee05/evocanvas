"""EvoCanvas 关键时刻快照模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from app.canvas.domain.handoff import StructuredHandoff, TodoProjection


@dataclass
class CanvasSnapshot:
    """记录某一时刻画布工作状态的轻量快照。"""

    snapshot_id: str
    workspace_id: str
    title: str
    summary: str = ""
    created_at: str = ""
    active_card_ids: List[str] = field(default_factory=list)
    active_relation_ids: List[str] = field(default_factory=list)
    todo_projection: Optional[TodoProjection] = None
    handoff: Optional[StructuredHandoff] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将快照序列化为字典。"""

        data = asdict(self)
        data["todo_projection"] = self.todo_projection.to_dict() if self.todo_projection else None
        data["handoff"] = self.handoff.to_dict() if self.handoff else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasSnapshot":
        """从字典恢复快照实例。"""

        return cls(
            snapshot_id=data["snapshot_id"],
            workspace_id=data["workspace_id"],
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            created_at=data.get("created_at", ""),
            active_card_ids=list(data.get("active_card_ids", [])),
            active_relation_ids=list(data.get("active_relation_ids", [])),
            todo_projection=TodoProjection.from_dict(data["todo_projection"]) if data.get("todo_projection") else None,
            handoff=StructuredHandoff.from_dict(data["handoff"]) if data.get("handoff") else None,
            metadata=dict(data.get("metadata", {})),
        )

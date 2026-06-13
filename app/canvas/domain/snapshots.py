"""EvoCanvas 关键时刻快照模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from app.canvas.domain.cards import CanvasCard
from app.canvas.domain.handoff import StructuredHandoff, TodoProjection
from app.canvas.domain.relations import CanvasRelation


@dataclass
class CanvasSnapshot:
    """记录某一时刻画布结构的快照。"""

    snapshot_id: str
    workspace_id: str
    title: str
    summary: str = ""
    created_at: str = ""
    cards: List[CanvasCard] = field(default_factory=list)
    relations: List[CanvasRelation] = field(default_factory=list)
    active_todos: List[TodoProjection] = field(default_factory=list)
    handoff: Optional[StructuredHandoff] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将快照序列化为字典。"""

        data = asdict(self)
        data["cards"] = [card.to_dict() for card in self.cards]
        data["relations"] = [relation.to_dict() for relation in self.relations]
        data["active_todos"] = [todo.to_dict() for todo in self.active_todos]
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
            cards=[CanvasCard.from_dict(item) for item in data.get("cards", [])],
            relations=[CanvasRelation.from_dict(item) for item in data.get("relations", [])],
            active_todos=[TodoProjection.from_dict(item) for item in data.get("active_todos", [])],
            handoff=StructuredHandoff.from_dict(data["handoff"]) if data.get("handoff") else None,
            metadata=dict(data.get("metadata", {})),
        )


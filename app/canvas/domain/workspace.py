"""EvoCanvas 工作画布根对象。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from app.canvas.domain.cards import CanvasCard
from app.canvas.domain.relations import CanvasRelation
from app.canvas.domain.snapshots import CanvasSnapshot


@dataclass
class CanvasWorkspace:
    """承载当前画布状态的工作区根对象。"""

    workspace_id: str
    title: str
    goal: str = ""
    stage: str = "discovery"
    cards: List[CanvasCard] = field(default_factory=list)
    relations: List[CanvasRelation] = field(default_factory=list)
    snapshots: List[CanvasSnapshot] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将工作区序列化为字典。"""

        data = asdict(self)
        data["cards"] = [card.to_dict() for card in self.cards]
        data["relations"] = [relation.to_dict() for relation in self.relations]
        data["snapshots"] = [snapshot.to_dict() for snapshot in self.snapshots]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasWorkspace":
        """从字典恢复工作区实例。"""

        return cls(
            workspace_id=data["workspace_id"],
            title=data.get("title", ""),
            goal=data.get("goal", ""),
            stage=data.get("stage", "discovery"),
            cards=[CanvasCard.from_dict(item) for item in data.get("cards", [])],
            relations=[CanvasRelation.from_dict(item) for item in data.get("relations", [])],
            snapshots=[CanvasSnapshot.from_dict(item) for item in data.get("snapshots", [])],
            metadata=dict(data.get("metadata", {})),
        )

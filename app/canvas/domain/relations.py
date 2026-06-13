"""EvoCanvas 卡片关系领域模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict


class CanvasRelationKind(str, Enum):
    """画布关系类型。"""

    DERIVED_FROM = "derived_from"
    CLARIFIES = "clarifies"
    SUPPORTS = "supports"
    BLOCKS = "blocks"
    CONFLICTS_WITH = "conflicts_with"
    PRODUCES = "produces"


@dataclass
class CanvasRelation:
    """连接两张画布卡片的语义关系。"""

    relation_id: str
    kind: CanvasRelationKind
    from_card_id: str
    to_card_id: str
    note: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将关系序列化为字典。"""

        data = asdict(self)
        data["kind"] = self.kind.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasRelation":
        """从字典恢复关系实例。"""

        return cls(
            relation_id=data["relation_id"],
            kind=CanvasRelationKind(data["kind"]),
            from_card_id=data["from_card_id"],
            to_card_id=data["to_card_id"],
            note=data.get("note", ""),
            metadata=dict(data.get("metadata", {})),
        )


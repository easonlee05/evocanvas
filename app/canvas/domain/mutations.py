"""EvoCanvas 画布变更提案模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict


class CanvasMutationAction(str, Enum):
    """画布对象的变更动作。"""

    ADD = "add"
    UPDATE = "update"
    REMOVE = "remove"


class CanvasMutationTarget(str, Enum):
    """变更提案作用的对象类型。"""

    CARD = "card"
    RELATION = "relation"
    SNAPSHOT = "snapshot"
    HANDOFF = "handoff"


@dataclass
class CanvasMutationProposal:
    """AI 或用户对画布提出的结构化变更建议。"""

    proposal_id: str
    action: CanvasMutationAction
    target: CanvasMutationTarget
    target_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    requires_confirmation: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将变更提案序列化为字典。"""

        data = asdict(self)
        data["action"] = self.action.value
        data["target"] = self.target.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasMutationProposal":
        """从字典恢复变更提案实例。"""

        return cls(
            proposal_id=data["proposal_id"],
            action=CanvasMutationAction(data["action"]),
            target=CanvasMutationTarget(data["target"]),
            target_id=data["target_id"],
            payload=dict(data.get("payload", {})),
            rationale=data.get("rationale", ""),
            requires_confirmation=bool(data.get("requires_confirmation", False)),
            metadata=dict(data.get("metadata", {})),
        )


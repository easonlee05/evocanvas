"""EvoCanvas 画布变更提案模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List


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
class CanvasMutation:
    """提案中的单条画布变更记录。"""

    mutation_id: str
    action: CanvasMutationAction
    target: CanvasMutationTarget
    target_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    requires_confirmation: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将单条变更序列化为字典。"""

        data = asdict(self)
        data["action"] = self.action.value
        data["target"] = self.target.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasMutation":
        """从字典恢复单条变更。"""

        return cls(
            mutation_id=data["mutation_id"],
            action=CanvasMutationAction(data["action"]),
            target=CanvasMutationTarget(data["target"]),
            target_id=data["target_id"],
            payload=dict(data.get("payload", {})),
            rationale=data.get("rationale", ""),
            requires_confirmation=bool(data.get("requires_confirmation", False)),
            metadata=dict(data.get("metadata", {})),
        )


class MutationRiskLevel(str, Enum):
    """变更提案的风险等级。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CanvasMutationStatus(str, Enum):
    """变更提案的当前状态。"""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    APPLIED = "applied"


@dataclass
class CanvasMutationProposal:
    """AI 或用户对画布提出的结构化变更提案包。"""

    proposal_id: str
    workspace_id: str
    turn_id: str
    mutations: List[CanvasMutation] = field(default_factory=list)
    risk_level: MutationRiskLevel = MutationRiskLevel.MEDIUM
    status: CanvasMutationStatus = CanvasMutationStatus.PROPOSED
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将变更提案包序列化为字典。"""

        data = asdict(self)
        data["mutations"] = [mutation.to_dict() for mutation in self.mutations]
        data["risk_level"] = self.risk_level.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasMutationProposal":
        """从字典恢复变更提案包。"""

        return cls(
            proposal_id=data["proposal_id"],
            workspace_id=data["workspace_id"],
            turn_id=data["turn_id"],
            mutations=[CanvasMutation.from_dict(item) for item in data.get("mutations", [])],
            risk_level=MutationRiskLevel(data.get("risk_level", MutationRiskLevel.MEDIUM.value)),
            status=CanvasMutationStatus(data.get("status", CanvasMutationStatus.PROPOSED.value)),
            metadata=dict(data.get("metadata", {})),
        )

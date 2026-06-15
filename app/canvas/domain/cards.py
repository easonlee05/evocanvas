"""EvoCanvas 画布卡片领域模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List


class CanvasCardKind(str, Enum):
    """画布卡片类型。

    对应 EvoCanvas 1.0 当前验证闭环中的主要结构化对象。
    """

    EVIDENCE = "evidence"
    PROBLEM = "problem"
    CLARIFICATION = "clarification"
    CONSTRAINT = "constraint"
    DECISION = "decision"
    HANDOFF = "handoff"
    OPTION = "option"


@dataclass
class CanvasCard:
    """EvoCanvas 主画布中的基础卡片。

    卡片用于承载输入证据、待澄清问题、约束和待决策等结构化信息，
    让画布可以围绕不确定性持续收敛。
    """

    card_id: str
    kind: CanvasCardKind
    title: str
    summary: str = ""
    stage: str = "discovery"
    status: str = "open"
    tags: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将卡片序列化为可持久化字典。"""

        data = asdict(self)
        data["kind"] = self.kind.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasCard":
        """从字典恢复卡片实例。"""

        return cls(
            card_id=data["card_id"],
            kind=CanvasCardKind(data["kind"]),
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            stage=data.get("stage", "discovery"),
            status=data.get("status", "open"),
            tags=list(data.get("tags", [])),
            evidence_refs=list(data.get("evidence_refs", [])),
            metadata=dict(data.get("metadata", {})),
        )

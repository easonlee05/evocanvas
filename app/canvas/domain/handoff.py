"""EvoCanvas 交接物与 Todo 投影视图模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TodoProjection:
    """从画布卡片投影出的活跃缺口。

    Todo 不是独立事实源，必须回指源卡片。
    """

    todo_id: str
    source_card_id: str
    title: str
    status: str = "open"
    reason: str = ""
    assignee: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 Todo 投影视图序列化为字典。"""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TodoProjection":
        """从字典恢复 Todo 投影视图。"""

        return cls(
            todo_id=data["todo_id"],
            source_card_id=data["source_card_id"],
            title=data.get("title", ""),
            status=data.get("status", "open"),
            reason=data.get("reason", ""),
            assignee=data.get("assignee"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class StructuredHandoff:
    """从当前画布收束出的结构化交接物。"""

    handoff_id: str
    summary: str = ""
    constraints: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将结构化交接物序列化为字典。"""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructuredHandoff":
        """从字典恢复结构化交接物。"""

        return cls(
            handoff_id=data["handoff_id"],
            summary=data.get("summary", ""),
            constraints=list(data.get("constraints", [])),
            open_questions=list(data.get("open_questions", [])),
            decisions=list(data.get("decisions", [])),
            metadata=dict(data.get("metadata", {})),
        )


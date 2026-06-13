"""EvoCanvas 交接物与 Todo 投影视图模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TodoItem:
    """从画布卡片投影出的单个活跃缺口。

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
        """将单个 Todo 项序列化为字典。"""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TodoItem":
        """从字典恢复单个 Todo 项。"""

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
class TodoProjection:
    """Todo 投影视图容器。

    该对象只表达某一时刻的活跃缺口集合，不直接承载画布事实本身。
    """

    projection_id: str
    workspace_id: str
    items: List[TodoItem] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 Todo 投影视图容器序列化为字典。"""

        data = asdict(self)
        data["items"] = [item.to_dict() for item in self.items]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TodoProjection":
        """从字典恢复 Todo 投影视图容器。"""

        return cls(
            projection_id=data["projection_id"],
            workspace_id=data["workspace_id"],
            items=[TodoItem.from_dict(item) for item in data.get("items", [])],
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

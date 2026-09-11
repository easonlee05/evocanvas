"""EvoCanvas 交接物与 Todo 投影视图模型。

L3 规格要求：
- 交接模块不复制对象正文形成可独立编辑内容；需要更新正文时修改源对象并创建新包版本。
- 交接视图通过对象引用组织当前目标、已确认约束、已完成决策、未解决问题、
  待确认决策和推荐后续动作。
- 交接有效性只读取包版本 initial_governance_status 及账本叠加，不另设独立状态。
- Todo 投影回指源卡片，不是独立事实源。

参见 docs/harness/02-memory-state/03 Stable State and Handoff（稳定状态与交接）.md
与 docs/harness/05-safety-governance/06 Handoff Governance（交接物治理）.md。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TodoItem:
    """从画布卡片投影出的单个活跃缺口。

    Todo 不是独立事实源，必须回指源卡片（source_card_id）。
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
class RecommendedAction:
    """交接模块中的推荐后续动作，回指相关对象与来源。"""

    action: str
    target_object_refs: List[str] = field(default_factory=list)
    source_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将推荐后续动作序列化为字典。"""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecommendedAction":
        """从字典恢复推荐后续动作。"""

        return cls(
            action=data.get("action", ""),
            target_object_refs=list(data.get("target_object_refs", [])),
            source_refs=list(data.get("source_refs", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class StructuredHandoff:
    """从当前结构化包收束出的引用型交接模块。

    L3 规格禁令：
    - 不允许写聊天总结（不保存 summary 字符串字段）。
    - 不允许复制对象正文形成可独立漂移的交接文档。
    - 不允许把候选 / 待确认 / 未决写进稳定内容槽位。
    - 交接有效性只读取包版本 initial_governance_status 及账本叠加，不另设状态。

    所有字段均为对象引用，需要更新正文时修改源对象并创建新包版本；
    交接视图随后重算。
    """

    handoff_id: str
    current_goal_ref: Optional[str] = None
    background_ref: Optional[str] = None
    confirmed_constraint_refs: List[str] = field(default_factory=list)
    completed_decision_refs: List[str] = field(default_factory=list)
    unresolved_refs: List[str] = field(default_factory=list)
    pending_decision_refs: List[str] = field(default_factory=list)
    recommended_actions: List[RecommendedAction] = field(default_factory=list)
    key_source_refs: List[str] = field(default_factory=list)
    milestone_ref: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将引用型交接模块序列化为字典。"""

        data = asdict(self)
        data["current_goal_ref"] = self.current_goal_ref
        data["background_ref"] = self.background_ref
        data["milestone_ref"] = self.milestone_ref
        data["recommended_actions"] = [action.to_dict() for action in self.recommended_actions]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructuredHandoff":
        """从字典恢复引用型交接模块实例。

        兼容历史持久化数据：summary/constraints/open_questions/decisions 字符串列表
        不再写入正文，仅保留在 metadata.compatibility 中供回看，不参与事实层。
        """

        compatibility = {}
        for compatibility_key in ("summary", "constraints", "open_questions", "decisions"):
            if compatibility_key in data:
                compatibility[compatibility_key] = data[compatibility_key]
        metadata = dict(data.get("metadata", {}))
        stored_compatibility = metadata.get("compatibility")
        if not isinstance(stored_compatibility, dict):
            stored_compatibility = metadata.get("legacy")
        if isinstance(stored_compatibility, dict):
            compatibility = {**stored_compatibility, **compatibility}
        if compatibility:
            metadata["compatibility"] = compatibility

        return cls(
            handoff_id=data["handoff_id"],
            current_goal_ref=data.get("current_goal_ref"),
            background_ref=data.get("background_ref"),
            confirmed_constraint_refs=list(data.get("confirmed_constraint_refs", [])),
            completed_decision_refs=list(data.get("completed_decision_refs", [])),
            unresolved_refs=list(data.get("unresolved_refs", [])),
            pending_decision_refs=list(data.get("pending_decision_refs", [])),
            recommended_actions=[
                RecommendedAction.from_dict(item)
                for item in data.get("recommended_actions", [])
            ],
            key_source_refs=list(data.get("key_source_refs", [])),
            milestone_ref=data.get("milestone_ref"),
            metadata=metadata,
        )

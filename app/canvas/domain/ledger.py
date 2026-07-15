"""EvoCanvas 状态账本（State Ledger）的追加式事件记录。

L3 规格要求：状态账本以追加式事件记录对象、关系、确认和包指针变化原因，
不保存对象完整正文。模型不能生成事件 ID、版本号、消息 ID 或提交时间。
事件中的消息、来源、确认、对象引用必须指向真实记录。

参见 docs/harness/02-memory-state/02 State Ledger（状态账本）.md。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class LedgerEventType(str, Enum):
    """账本事件类型枚举，共 17 种。"""

    PACKAGE_CREATED = "package_created"
    PACKAGE_ARCHIVED = "package_archived"
    PACKAGE_VERSION_CREATED = "package_version_created"
    CURRENT_VERSION_MOVED = "current_version_moved"
    LATEST_CONFIRMED_VERSION_MOVED = "latest_confirmed_version_moved"
    PACKAGE_VERSION_CONFIRMED = "package_version_confirmed"
    PACKAGE_VERSION_MARKED_OUTDATED = "package_version_marked_outdated"
    PACKAGE_VERSION_RISK_ANNOTATED = "package_version_risk_annotated"
    OBJECT_CREATED = "object_created"
    OBJECT_CONTENT_UPDATED = "object_content_updated"
    OBJECT_STATUS_CHANGED = "object_status_changed"
    OBJECT_SUPERSEDED = "object_superseded"
    RELATION_CREATED = "relation_created"
    RELATION_REMOVED = "relation_removed"
    SOURCE_LINK_CHANGED = "source_link_changed"
    CONFIRMATION_RECORDED = "confirmation_recorded"
    CONFIRMATION_WITHDRAWN = "confirmation_withdrawn"


class LedgerActorType(str, Enum):
    """账本事件的发起方类型。"""

    USER = "user"
    SYSTEM = "system"
    MIGRATION = "migration"


@dataclass
class LedgerEvent:
    """追加式账本事件，记录对象、包版本和指针为什么变化。

    不变量：
    - 消息、来源、确认、对象引用必须指向真实记录。
    - 模型不能生成 ledger_event_id、版本号、消息 ID 或 occurred_at。
    - 账本不保存完整正文，仅记录 before_ref / after_ref 指针。
    """

    ledger_event_id: str
    workspace_id: str
    package_id: str
    event_type: LedgerEventType
    entity_type: str
    entity_id: str
    actor_type: LedgerActorType
    actor_id: str
    occurred_at: str
    package_version: Optional[int] = None
    state_version_before: int = 0
    state_version_after: int = 0
    before_ref: Optional[str] = None
    after_ref: Optional[str] = None
    operation_id: str = ""
    convergence_run_id: str = ""
    chat_turn_id: str = ""
    message_refs: List[str] = field(default_factory=list)
    source_refs: List[str] = field(default_factory=list)
    confirmation_id: Optional[str] = None
    unresolved_refs: List[str] = field(default_factory=list)
    reason_codes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将账本事件序列化为字典。"""

        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["actor_type"] = self.actor_type.value
        data["package_version"] = self.package_version
        data["before_ref"] = self.before_ref
        data["after_ref"] = self.after_ref
        data["confirmation_id"] = self.confirmation_id
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LedgerEvent":
        """从字典恢复账本事件实例。"""

        return cls(
            ledger_event_id=data["ledger_event_id"],
            workspace_id=data.get("workspace_id", ""),
            package_id=data.get("package_id", ""),
            event_type=LedgerEventType(data.get("event_type", "")),
            entity_type=data.get("entity_type", ""),
            entity_id=data.get("entity_id", ""),
            actor_type=LedgerActorType(data.get("actor_type", LedgerActorType.SYSTEM.value)),
            actor_id=data.get("actor_id", ""),
            occurred_at=data.get("occurred_at", ""),
            package_version=data.get("package_version"),
            state_version_before=int(data.get("state_version_before", 0)),
            state_version_after=int(data.get("state_version_after", 0)),
            before_ref=data.get("before_ref"),
            after_ref=data.get("after_ref"),
            operation_id=data.get("operation_id", ""),
            convergence_run_id=data.get("convergence_run_id", ""),
            chat_turn_id=data.get("chat_turn_id", ""),
            message_refs=list(data.get("message_refs", [])),
            source_refs=list(data.get("source_refs", [])),
            confirmation_id=data.get("confirmation_id"),
            unresolved_refs=list(data.get("unresolved_refs", [])),
            reason_codes=list(data.get("reason_codes", [])),
            metadata=dict(data.get("metadata", {})),
        )

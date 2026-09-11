"""EvoCanvas 画布卡片领域模型。

L3 规格要求：
- 对象只有五类：evidence / problem / clarification / constraint / decision。
  handoff 不是对象类型而是交接模块，option 不纳入 1.0 对象类型。
- 对象维护单一权威类型化业务状态（status），通用治理地位由 (kind, status) 派生，
  验证状态（validation_state）独立于对象生命周期。
- 对象必须携带来源引用（source_refs）、确认引用（confirmation_refs）、
  未决引用（unresolved_refs）与创建/更新时间，以支撑可追溯性。

参见 docs/harness/02-memory-state/01 Memory（记忆）.md
与 docs/harness/02-memory-state/02 State Ledger（状态账本）.md。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List

from app.canvas.domain.object_status import (
    ValidationState,
    default_status_for_kind,
    derive_governance_class,
    is_valid_status_for_kind,
)


class CanvasCardKind(str, Enum):
    """画布卡片类型，对应 EvoCanvas 1.0 受治理的五类结构化对象。

    handoff 不作为对象类型出现（交接模块只引用对象，不创建对象）；
    option 不纳入 1.0 对象类型枚举。
    """

    EVIDENCE = "evidence"
    PROBLEM = "problem"
    CLARIFICATION = "clarification"
    CONSTRAINT = "constraint"
    DECISION = "decision"


@dataclass
class CanvasCard:
    """EvoCanvas 主画布中的基础对象（卡片）。

    卡片用于承载证据、问题、待澄清、约束和待决策等结构化信息，
    让画布可以围绕不确定性持续收敛。status 是唯一权威类型化业务状态，
    governance_class 由 (kind, status) 派生，不得独立写入。
    """

    card_id: str
    kind: CanvasCardKind
    title: str
    summary: str = ""
    status: str = ""
    tags: List[str] = field(default_factory=list)
    # 来源引用：替代历史 evidence_refs，统一表达对象回指的来源材料、消息或工具结果。
    source_refs: List[str] = field(default_factory=list)
    # 确认引用：回指 Chat 中 Assistant 提议与 User 确认消息，支撑高影响升级留痕。
    confirmation_refs: List[str] = field(default_factory=list)
    # 未决引用：记录该对象仍依赖的未解决问题或待决策对象。
    unresolved_refs: List[str] = field(default_factory=list)
    # 独立验证状态，不改变对象生命周期，不混入业务状态。
    validation_state: str = ValidationState.UNVERIFIED.value
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """校验类型化状态合法性，拒绝非法状态写入。"""

        kind_value = self.kind.value if hasattr(self.kind, "value") else str(self.kind)
        if not self.status:
            self.status = default_status_for_kind(kind_value)
        if not is_valid_status_for_kind(kind_value, self.status):
            raise ValueError(
                f"status {self.status!r} is not valid for canvas card kind {kind_value!r}"
            )

    @property
    def governance_class(self) -> str:
        """派生通用治理地位，禁止独立写入。"""

        kind_value = self.kind.value if hasattr(self.kind, "value") else str(self.kind)
        return derive_governance_class(kind_value, self.status).value

    def to_dict(self) -> Dict[str, Any]:
        """将卡片序列化为可持久化字典。"""

        data = asdict(self)
        data["kind"] = self.kind.value
        # 派生治理地位一并输出，便于上下文筛选与界面分组，但不是独立可写字段。
        data["governance_class"] = self.governance_class
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanvasCard":
        """从字典恢复卡片实例。

        兼容历史持久化数据：evidence_refs 自动转换为 source_refs，
        缺失的 source_refs/confirmation_refs/unresolved_refs/validation_state
        补默认值，stage 字段忽略。
        """

        kind_raw = str(data.get("kind", "evidence"))
        status_raw = str(data.get("status", ""))
        kind, status = _normalize_compatibility_kind_and_status(kind_raw, status_raw)
        # 兼容历史 evidence_refs -> source_refs
        source_refs = list(data.get("source_refs", data.get("evidence_refs", [])))
        metadata = dict(data.get("metadata", {}))
        if kind_raw != kind.value:
            metadata.setdefault("compatibility_kind", kind_raw)
        return cls(
            card_id=data["card_id"],
            kind=kind,
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            status=status,
            tags=list(data.get("tags", [])),
            source_refs=source_refs,
            confirmation_refs=list(data.get("confirmation_refs", [])),
            unresolved_refs=list(data.get("unresolved_refs", [])),
            validation_state=data.get("validation_state", ValidationState.UNVERIFIED.value),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", data.get("created_at", "")),
            metadata=metadata,
        )


def _normalize_compatibility_kind_and_status(kind_raw: str, status_raw: str) -> tuple[CanvasCardKind, str]:
    """把兼容对象枚举和自由状态映射为 L3 的唯一类型化状态。

    该函数只在读取历史数据时调用；新对象必须在构造阶段携带合法状态，
    不能借此绕过 L3 的写入校验。
    """

    kind_aliases = {
        "option": CanvasCardKind.DECISION,
        # 历史交接卡是现在交接模块的平行投影；保留其文本为历史决策，
        # 真正交接内容由同工作区的 handoff.json 迁入包版本。
        "handoff": CanvasCardKind.DECISION,
    }
    if kind_raw in kind_aliases:
        kind = kind_aliases[kind_raw]
    else:
        try:
            kind = CanvasCardKind(kind_raw)
        except ValueError as exc:
            raise ValueError(f"unsupported compatibility canvas card kind: {kind_raw}") from exc

    if not status_raw:
        return kind, default_status_for_kind(kind.value)

    compatibility_statuses = {
        ("evidence", "open"): "collected",
        ("problem", "open"): "initial",
        ("clarification", "pending"): "pending_confirmation",
        ("clarification", "resolved"): "clarified",
        ("constraint", "confirmed"): "effective",
        ("constraint", "active"): "effective",
        ("decision", "open"): "pending_decision",
        ("decision", "confirmed"): "decided",
        ("decision", "resolved"): "decided",
        ("handoff", "confirmed"): "decided",
        ("handoff", "draft"): "pending_decision",
    }
    status = compatibility_statuses.get((kind_raw, status_raw), status_raw)
    if kind_raw == "option" and status == "confirmed":
        status = "decided"
    if kind_raw == "handoff" and not is_valid_status_for_kind(kind.value, status):
        status = "archived"
    if not is_valid_status_for_kind(kind.value, status):
        # 无法判定的历史自由字符串不应冒充有效事实，归一为该类型初始状态并留痕。
        status = default_status_for_kind(kind.value)
    return kind, status

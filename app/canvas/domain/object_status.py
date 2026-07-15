"""EvoCanvas 结构化对象的类型化状态与治理地位。

L3 规格要求：对象只有一套权威的类型化业务状态（按对象类型限定枚举），
通用治理地位（governance_class）由「对象类型 + 类型化状态」派生，禁止双写；
验证状态（validation_state）独立于对象生命周期，不混入业务状态。

参见 docs/harness/02-memory-state/02 State Ledger（状态账本）.md。
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable


class EvidenceStatus(str, Enum):
    """证据卡（evidence）的权威业务状态。"""

    COLLECTED = "collected"
    CITED = "cited"
    ARCHIVED = "archived"


class ProblemStatus(str, Enum):
    """问题卡（problem）的权威业务状态。"""

    INITIAL = "initial"
    CONVERGING = "converging"
    CONVERGED = "converged"
    ARCHIVED = "archived"


class ClarificationStatus(str, Enum):
    """待澄清卡（clarification）的权威业务状态。"""

    OPEN = "open"
    PENDING_CONFIRMATION = "pending_confirmation"
    CLARIFIED = "clarified"
    BLOCKED = "blocked"
    CLOSED = "closed"


class ConstraintStatus(str, Enum):
    """约束卡（constraint）的权威业务状态。

    PRD 规定草稿和待确认可以作为受治理对象持久化；只有升级为已生效
    才必须具有普通 Chat 中可回指的确认依据。
    """

    DRAFT = "draft"
    PENDING_CONFIRMATION = "pending_confirmation"
    EFFECTIVE = "effective"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class DecisionStatus(str, Enum):
    """待决策卡（decision）的权威业务状态。"""

    PENDING_DECISION = "pending_decision"
    PENDING_CONFIRMATION = "pending_confirmation"
    DECIDED = "decided"
    ARCHIVED = "archived"


class GovernanceClass(str, Enum):
    """通用治理地位，由对象类型与类型化状态派生，禁止独立写入。

    用于上下文筛选、门禁、交接和界面分组，不是第二个可独立写入的业务状态。
    """

    SOURCE = "source"
    WORKING = "working"
    UNRESOLVED = "unresolved"
    STABLE = "stable"
    HISTORICAL = "historical"


class ValidationState(str, Enum):
    """独立验证状态，与对象业务状态分离，不改变对象生命周期。"""

    UNVERIFIED = "unverified"
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"


class InitialGovernanceStatus(str, Enum):
    """不可变包版本的初始治理状态。"""

    DRAFT = "draft"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"


class EffectiveStatus(str, Enum):
    """账本叠加后的有效状态。"""

    DRAFT = "draft"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    OUTDATED = "outdated"


# 各对象类型允许的类型化状态集合，用于校验非法跳跃。
_TYPED_STATUS_BY_KIND: dict[str, set[str]] = {
    "evidence": {item.value for item in EvidenceStatus},
    "problem": {item.value for item in ProblemStatus},
    "clarification": {item.value for item in ClarificationStatus},
    "constraint": {item.value for item in ConstraintStatus},
    "decision": {item.value for item in DecisionStatus},
}

_DEFAULT_STATUS_BY_KIND: dict[str, str] = {
    "evidence": EvidenceStatus.COLLECTED.value,
    "problem": ProblemStatus.INITIAL.value,
    "clarification": ClarificationStatus.OPEN.value,
    "constraint": ConstraintStatus.DRAFT.value,
    "decision": DecisionStatus.PENDING_DECISION.value,
}


def allowed_statuses_for_kind(kind: str) -> set[str]:
    """返回指定对象类型允许的类型化状态值集合。"""

    return set(_TYPED_STATUS_BY_KIND.get(kind, set()))


def default_status_for_kind(kind: str) -> str:
    """返回新建对象的唯一合法初始状态。"""

    try:
        return _DEFAULT_STATUS_BY_KIND[kind]
    except KeyError as exc:
        raise ValueError(f"unsupported canvas card kind: {kind}") from exc


def is_valid_status_for_kind(kind: str, status: str) -> bool:
    """判断给定状态是否属于该对象类型的合法类型化状态。"""

    return status in _TYPED_STATUS_BY_KIND.get(kind, set())


# 类型化状态 → 通用治理地位的派生映射。
# 规格要求通用治理地位必须可重算，调用方不得直接写入。
_GOVERNANCE_CLASS_MAP: dict[tuple[str, str], GovernanceClass] = {
    # evidence
    ("evidence", "collected"): GovernanceClass.SOURCE,
    ("evidence", "cited"): GovernanceClass.SOURCE,
    ("evidence", "archived"): GovernanceClass.HISTORICAL,
    # problem
    ("problem", "initial"): GovernanceClass.WORKING,
    ("problem", "converging"): GovernanceClass.WORKING,
    ("problem", "converged"): GovernanceClass.STABLE,
    ("problem", "archived"): GovernanceClass.HISTORICAL,
    # clarification
    ("clarification", "open"): GovernanceClass.UNRESOLVED,
    ("clarification", "pending_confirmation"): GovernanceClass.UNRESOLVED,
    ("clarification", "clarified"): GovernanceClass.STABLE,
    ("clarification", "blocked"): GovernanceClass.UNRESOLVED,
    ("clarification", "closed"): GovernanceClass.HISTORICAL,
    # constraint
    ("constraint", "draft"): GovernanceClass.WORKING,
    ("constraint", "pending_confirmation"): GovernanceClass.UNRESOLVED,
    ("constraint", "effective"): GovernanceClass.STABLE,
    ("constraint", "superseded"): GovernanceClass.HISTORICAL,
    ("constraint", "archived"): GovernanceClass.HISTORICAL,
    # decision
    ("decision", "pending_decision"): GovernanceClass.UNRESOLVED,
    ("decision", "pending_confirmation"): GovernanceClass.UNRESOLVED,
    ("decision", "decided"): GovernanceClass.STABLE,
    ("decision", "archived"): GovernanceClass.HISTORICAL,
}


def derive_governance_class(kind: str, status: str) -> GovernanceClass:
    """根据对象类型与类型化状态派生通用治理地位。

    规格禁令：governance_class 不得作为第二个可独立写入的业务状态，
    必须始终可由 (kind, status) 重算。
    """

    return _GOVERNANCE_CLASS_MAP.get((kind, status), GovernanceClass.WORKING)


def is_stable_status(kind: str, status: str) -> bool:
    """判断该状态是否对应稳定治理地位（可作后续依据）。"""

    return derive_governance_class(kind, status) == GovernanceClass.STABLE


def is_unresolved_status(kind: str, status: str) -> bool:
    """判断该状态是否对应未决治理地位（仍影响推进的活跃缺口）。"""

    return derive_governance_class(kind, status) == GovernanceClass.UNRESOLVED


def unresolved_object_ids(cards: Iterable["object"]) -> list[str]:
    """从卡片集合中提取仍影响推进的未决对象 ID。

    替代旧 runtime_state.unresolved_issue_ids_from_cards，按类型化状态判断，
    不再依赖自由字符串状态比对。
    """

    unresolved: list[str] = []
    for card in cards:
        kind_value = card.kind.value if hasattr(card.kind, "value") else str(card.kind)
        if is_unresolved_status(kind_value, card.status):
            unresolved.append(card.card_id)
    return unresolved

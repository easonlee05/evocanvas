"""EvoCanvas Supervisor 与内部角色使用的最小契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Tuple


def _freeze_value(value: Any) -> Any:
    """递归冻结嵌套值，避免 contract 持有外部可变引用。"""

    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_value(item) for item in value)
    return value


@dataclass(frozen=True)
class CanvasTurnPlan:
    """描述单轮 Canvas AI 应如何规划内部角色。"""

    intent: str
    roles: Tuple[str, ...]
    allowed_mutation_types: Tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "roles", tuple(_freeze_value(self.roles)))
        object.__setattr__(self, "allowed_mutation_types", tuple(_freeze_value(self.allowed_mutation_types)))
        object.__setattr__(self, "metadata", _freeze_value(dict(self.metadata)))


@dataclass(frozen=True)
class RoleOutput:
    """约束单个内部角色返回的结构化结果。

    Task 4 只需要先定义输出接口，不负责实际子角色执行。
    """

    role: str
    findings: Tuple[str, ...] = field(default_factory=tuple)
    proposed_mutations: Tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    evidence_refs: Tuple[str, ...] = field(default_factory=tuple)
    confidence: str = "medium"
    open_questions: Tuple[str, ...] = field(default_factory=tuple)
    requires_human_confirmation: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(_freeze_value(self.findings)))
        object.__setattr__(self, "proposed_mutations", tuple(_freeze_value(self.proposed_mutations)))
        object.__setattr__(self, "evidence_refs", tuple(_freeze_value(self.evidence_refs)))
        object.__setattr__(self, "open_questions", tuple(_freeze_value(self.open_questions)))

"""EvoCanvas Supervisor 与内部角色使用的最小契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class CanvasTurnPlan:
    """描述单轮 Canvas AI 应如何规划内部角色。"""

    intent: str
    roles: List[str]
    allowed_mutation_types: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoleOutput:
    """约束单个内部角色返回的结构化结果。

    Task 4 只需要先定义输出接口，不负责实际子角色执行。
    """

    role: str
    findings: List[str] = field(default_factory=list)
    proposed_mutations: List[Dict[str, Any]] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    confidence: str = "medium"
    open_questions: List[str] = field(default_factory=list)
    requires_human_confirmation: bool = False

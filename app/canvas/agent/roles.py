"""EvoCanvas 内部角色注册表。

Task 4 只定义固定角色和各自允许的最小变更范围，
不在这里启动实际 subagent。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class CanvasAgentRole:
    """描述一个内部角色的规划元信息。"""

    name: str
    responsibility: str
    allowed_mutation_types: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_mutation_types", tuple(self.allowed_mutation_types))


@dataclass(frozen=True)
class CanvasIntentRoute:
    """描述一个意图如何由关键词映射到内部角色。"""

    intent: str
    keywords: Tuple[str, ...]
    roles: Tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "keywords", tuple(self.keywords))
        object.__setattr__(self, "roles", tuple(self.roles))


_ROLE_REGISTRY: dict[str, CanvasAgentRole] = {
    "InputCompiler": CanvasAgentRole(
        name="InputCompiler",
        responsibility="接收新输入并生成 evidence、problem 与第一批 clarification。",
        allowed_mutation_types=("add_card", "add_relation"),
    ),
    "Clarifier": CanvasAgentRole(
        name="Clarifier",
        responsibility="显性化歧义、缺口与冲突，优先推动待澄清而不是抢结论。",
        allowed_mutation_types=("add_card", "update_card_summary", "mark_conflict"),
    ),
    "ConstraintSteward": CanvasAgentRole(
        name="ConstraintSteward",
        responsibility="沉淀稳定边界，生成约束草稿但不直接越权确认为已生效。",
        allowed_mutation_types=("add_card", "update_card_summary", "promote_to_constraint_draft"),
    ),
    "DecisionSteward": CanvasAgentRole(
        name="DecisionSteward",
        responsibility="识别需要人拍板的事项并沉淀待决策项。",
        allowed_mutation_types=("add_card", "create_decision_request", "update_card_summary"),
    ),
    "HandoffBuilder": CanvasAgentRole(
        name="HandoffBuilder",
        responsibility="收束当前结构化交接物，同时保留未解决缺口。",
        allowed_mutation_types=("refresh_handoff_draft",),
    ),
}

_INTENT_ROUTES: Tuple[CanvasIntentRoute, ...] = (
    CanvasIntentRoute(
        intent="input_compilation",
        keywords=tuple(),
        roles=("InputCompiler",),
    ),
    CanvasIntentRoute(
        intent="clarification",
        keywords=("待澄清", "澄清", "歧义", "冲突", "缺口"),
        roles=("Clarifier",),
    ),
    CanvasIntentRoute(
        intent="handoff",
        keywords=("交接物", "handoff", "交接", "结构化交接物"),
        roles=("HandoffBuilder",),
    ),
    CanvasIntentRoute(
        intent="constraint",
        keywords=("约束", "边界", "限制"),
        roles=("ConstraintSteward",),
    ),
    CanvasIntentRoute(
        intent="decision",
        keywords=("决策", "拍板", "取舍", "方案选择"),
        roles=("DecisionSteward",),
    ),
)


def get_role(name: str) -> CanvasAgentRole:
    """按名称读取角色定义。"""

    return _ROLE_REGISTRY[name]


def get_intent_routes() -> Tuple[CanvasIntentRoute, ...]:
    """返回当前 supervisor 使用的静态意图路由表。"""

    return _INTENT_ROUTES

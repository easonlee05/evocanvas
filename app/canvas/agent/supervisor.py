"""EvoCanvas Canvas Supervisor。

当前仅负责基于用户输入做意图识别与角色规划，
不承担实际 subagent 调度与 mutation 合并。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from app.canvas.agent.contracts import CanvasTurnPlan
from app.canvas.agent.roles import get_intent_routes, get_role


class CanvasSupervisor:
    """识别当前输入意图，并为单轮对话选择内部角色。"""

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    def recognize_and_plan(self, workspace_context: Dict[str, Any], message: str) -> CanvasTurnPlan:
        """根据消息内容生成最小角色规划。

        `workspace_context` 在 Task 4 中只作为接口占位，后续任务再接入真实上下文判断。
        """

        del workspace_context

        intent, roles = self._select_intent_and_roles(message)
        return CanvasTurnPlan(
            intent=intent,
            roles=roles,
            allowed_mutation_types=self._collect_allowed_mutation_types(roles),
        )

    def _select_intent_and_roles(self, message: str) -> Tuple[str, Tuple[str, ...]]:
        normalized_message = message.strip()
        matched_intents: List[str] = []
        matched_roles: List[str] = []
        fallback_route = None

        for route in get_intent_routes():
            if not route.keywords:
                fallback_route = route
                continue
            if self._contains_any(normalized_message, list(route.keywords)):
                matched_intents.append(route.intent)
                for role_name in route.roles:
                    if role_name not in matched_roles:
                        matched_roles.append(role_name)

        if not matched_intents:
            if fallback_route is None:
                return "input_compilation", ("InputCompiler",)
            return fallback_route.intent, fallback_route.roles
        return "+".join(matched_intents), tuple(matched_roles)

    def _collect_allowed_mutation_types(self, roles: Iterable[str]) -> Tuple[str, ...]:
        allowed_mutation_types: List[str] = []
        for role_name in roles:
            for mutation_type in get_role(role_name).allowed_mutation_types:
                if mutation_type not in allowed_mutation_types:
                    allowed_mutation_types.append(mutation_type)
        return tuple(allowed_mutation_types)

    @staticmethod
    def _contains_any(message: str, keywords: List[str]) -> bool:
        return any(keyword in message for keyword in keywords)

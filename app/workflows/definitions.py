"""EvoCanvas 工作流任务注册表。

该模块负责集中注册当前可用的任务定义。
在迁移期内优先保证 EvoCanvas 1.0 的 `evocanvas_canvas_turn` 可用，
同时对历史任务定义采用可选加载，避免缺失旧模块时阻断新产品能力。
"""
from __future__ import annotations

from typing import Callable

from app.core.task import TaskDefinition, WorkflowSpec, WorkflowStep
from app.workflows.canvas_session import build_canvas_turn_definition
from app.workflows.policies import build_default_tool_policy


DefinitionBuilder = Callable[[], TaskDefinition]


def _build_legacy_placeholder_definition(task_type: str, display_name: str) -> TaskDefinition:
    """在 legacy workflow 缺失时保留最小可创建契约，避免入口直接失效。"""

    return TaskDefinition(
        type=task_type,
        display_name=display_name,
        input_schema={
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "goal": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["username"],
            "additionalProperties": True,
        },
        workflow=WorkflowSpec(
            name=f"{task_type}_placeholder",
            version="0.1",
            steps=[
                WorkflowStep(
                    id="legacy_placeholder",
                    type="context",
                    title="保留兼容入口",
                    role="SYSTEM",
                    input_keys=["goal", "title"],
                    output_keys=["goal"],
                )
            ],
        ),
        tool_policy=build_default_tool_policy(task_type),
        metadata={
            "legacy_placeholder": True,
            "compatibility_mode": True,
        },
    )


def _load_legacy_builders() -> dict[str, DefinitionBuilder]:
    """按需加载仍可用的历史任务定义构造器。

    Returns:
        dict[str, DefinitionBuilder]: 仅包含当前环境中可成功导入的历史定义。
    """
    builders: dict[str, DefinitionBuilder] = {}

    try:
        from app.workflows.acceptance_review import build_acceptance_review_definition
    except ModuleNotFoundError:
        builders["acceptance_review"] = lambda: _build_legacy_placeholder_definition(
            "acceptance_review",
            "Acceptance Review (Compatibility)",
        )
    else:
        builders["acceptance_review"] = build_acceptance_review_definition

    try:
        from app.workflows.spec_to_agent import build_spec_to_agent_definition
    except ModuleNotFoundError:
        builders["spec_to_agent"] = lambda: _build_legacy_placeholder_definition(
            "spec_to_agent",
            "Spec to Agent (Compatibility)",
        )
    else:
        builders["spec_to_agent"] = build_spec_to_agent_definition

    return builders


def build_task_registry() -> dict[str, TaskDefinition]:
    """构建并返回全局任务定义注册表。"""
    registry = {
        "evocanvas_canvas_turn": build_canvas_turn_definition(),
    }

    for task_type, builder in _load_legacy_builders().items():
        registry[task_type] = builder()

    return registry

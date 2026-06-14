"""EvoCanvas 1.0 的画布回合工作流定义。

当前模块只提供 `canvas_turn` 的静态任务定义与注册契约，
用于把单轮画布推进接入现有 workflow registry。
首版范围仅覆盖定义层，不在这里接入真实服务、仓储或 API 行为。
"""
from __future__ import annotations

from app.core.task import TaskDefinition, WorkflowSpec, WorkflowStep
from app.workflows.policies import build_canvas_tool_policy


def build_canvas_turn_definition() -> TaskDefinition:
    """构建 EvoCanvas 画布单轮推进任务定义。

    Returns:
        TaskDefinition: 用于注册到全局任务注册表的最小任务定义。
    """
    task_type = "evocanvas_canvas_turn"
    workflow = WorkflowSpec(
        name="canvas_turn",
        version="1.0",
        steps=[
            WorkflowStep(
                id="load_canvas_context",
                type="context",
                title="加载当前画布上下文",
                role="SYSTEM",
                input_keys=["workspace_id", "turn_input"],
                output_keys=["canvas_context"],
            ),
            WorkflowStep(
                id="run_canvas_supervisor",
                type="agent",
                title="运行画布回合同步器",
                role="CanvasSupervisor",
                input_keys=["canvas_context", "turn_input"],
                output_keys=["supervisor_plan", "mutation_proposal"],
            ),
            WorkflowStep(
                id="merge_canvas_proposal",
                type="agent",
                title="合并结构化提议",
                role="SYSTEM",
                input_keys=["mutation_proposal"],
                output_keys=["canvas_patch", "handoff_draft"],
            ),
            WorkflowStep(
                id="emit_canvas_events",
                type="context",
                title="发出画布回合事件",
                role="SYSTEM",
                input_keys=["canvas_patch", "handoff_draft"],
                output_keys=["turn_summary"],
            ),
        ],
    )
    return TaskDefinition(
        type=task_type,
        display_name="EvoCanvas 画布回合",
        input_schema={
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "workspace_id": {"type": "string"},
                "turn_input": {"type": "string"},
                "turn_id": {"type": "string"},
            },
            "required": ["username", "workspace_id", "turn_input"],
            "additionalProperties": True,
        },
        workflow=workflow,
        tool_policy=build_canvas_tool_policy(task_type),
        agents={
            "CanvasSupervisor": {
                "role": "CanvasSupervisor",
                "goal": "先暴露不确定性，再沉淀约束、待决策与结构化交接物草稿。",
            }
        },
        output_spec={
            "primary_artifact": "canvas_turn_summary",
            "artifacts": ["mutation_proposal", "handoff_draft"],
        },
        metadata={
            "product_line": "evocanvas",
            "stage": "1.0",
            "scope": "definition_only",
        },
    )

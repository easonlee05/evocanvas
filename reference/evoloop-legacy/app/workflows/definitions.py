"""工作流任务注册表模块。

该模块负责为所有产品线注册和构建 `TaskDefinition`，确保新旧任务类型的兼容性，
并在 Evoloop 3.0 系统中提供统一的任务定义检索机制。
"""
from __future__ import annotations

from app.core.task import TaskDefinition
from app.workflows.acceptance_review import build_acceptance_review_definition
from app.workflows.spec_to_agent import build_spec_to_agent_definition


def build_task_registry() -> dict[str, TaskDefinition]:
    """构建并返回全局任务定义注册表。

    该函数会加载并配置系统在 3.0 架构下的核心原生工作流，包括规范编译（Spec to Agent）和验收评审任务。

    Returns:
        dict[str, TaskDefinition]: 键为任务类型标识，值为对应 `TaskDefinition` 的映射字典。
    """
    # 构建 3.0 的 spec_to_agent 任务定义
    spec_to_agent = build_spec_to_agent_definition()
    # 构建 3.0 的 acceptance_review 任务定义
    acceptance_review = build_acceptance_review_definition()
    
    return {
        "spec_to_agent": spec_to_agent,
        "acceptance_review": acceptance_review,
    }


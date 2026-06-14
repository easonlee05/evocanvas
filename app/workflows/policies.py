"""任务定义的重用工作流与工具策略助手。

该模块定义了工作流任务执行中，各角色（如 SYSTEM、PM、Tech、QA、Reviewer、Writer 等）
在不同步骤下允许调用的受控工具（Tool）白名单策略，确保系统的安全性与操作合规性。
"""
from __future__ import annotations

from app.core.tools import ToolPolicy, ToolPolicyRule


# 常用只读类工具白名单，允许读取材料、解析材料、检索知识和读取产物
COMMON_READ_TOOLS = ["material.read", "material.parse", "knowledge.retrieve", "artifact.read"]
# 常用写入/外部变更类工具白名单，允许写入产物、备份产物、提取差异规则和发射事件
COMMON_WRITE_TOOLS = ["artifact.write", "artifact.backup", "diff.extract_rules", "event.emit"]


def build_default_tool_policy(task_type: str) -> ToolPolicy:
    """为指定任务类型构建并返回默认的工具策略（ToolPolicy）。

    该策略限制了不同角色（Role）在任意步骤中允许调用的工具列表，遵循最小权限原则。

    Args:
        task_type (str): 任务类型标识。

    Returns:
        ToolPolicy: 配置好的工具策略对象。
    """
    return ToolPolicy(
        task_type=task_type,
        rules=[
            # SYSTEM 角色允许解析材料、检索知识和发射事件
            ToolPolicyRule(role="SYSTEM", step_id="*", allowed_tools=["material.parse", "knowledge.retrieve", "event.emit"]),
            # Compiler 角色允许读取原始材料、解析材料、检索知识以及读取产物
            ToolPolicyRule(role="Compiler", step_id="*", allowed_tools=["material.read", "material.parse", "knowledge.retrieve", "artifact.read"]),
            # Reviewer 角色允许读取材料、读取产物、验证格式及发射事件
            ToolPolicyRule(role="Reviewer", step_id="*", allowed_tools=["material.read", "artifact.read", "format.validate", "event.emit"]),
            # Writer 角色允许读取产物、写入产物及备份产物
            ToolPolicyRule(role="Writer", step_id="*", allowed_tools=["artifact.read", "artifact.write", "artifact.backup"]),
        ],
    )


def build_canvas_tool_policy(task_type: str) -> ToolPolicy:
    """为 EvoCanvas 画布回合构建只读优先的工具策略。"""

    policy = build_default_tool_policy(task_type)
    policy.rules.append(
        ToolPolicyRule(
            role="CanvasSupervisor",
            step_id="run_canvas_supervisor",
            allowed_tools=["material.read", "knowledge.retrieve", "artifact.read"],
        )
    )
    return policy

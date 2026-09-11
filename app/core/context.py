"""EvoCanvas 核心契约层任务上下文与决策模型模块。

定义了在所有工作流类型中共享的运行期上下文（TaskContext）
与用户决策裁决记录（UserDecision），用于在执行引擎和 AI Agent 之间传递统一状态。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from app.core.artifacts import Artifact


@dataclass
class UserDecision:
    """人类在 Decision Gate 处做出的决策裁决记录模型。

    用于表达对某个待定问题（如需求冲突或不确定分支）的选择，指导 Workflow 引擎在何处恢复执行。

    Attributes:
        decision: 对决策结果的总结性描述。
        selected_option: 用户选择的选项键值或文本。
        quoted_selections: 从原文中引用的证据或特定段落切片。
        applies_to_step_id: 该决策应用的目标步骤 ID。
        resume_step_id: 决策解决后，引擎应当恢复跑的步骤 ID。
    """
    decision: str
    selected_option: Optional[str] = None
    quoted_selections: List[Dict[str, Any]] = field(default_factory=list)
    applies_to_step_id: Optional[str] = None
    resume_step_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """将 UserDecision 转换为字典格式。

        Returns:
            Dict[str, Any]: 转换后的字典。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserDecision":
        """从字典反序列化生成 UserDecision 实例。

        Args:
            data: 包含决策数据的字典。

        Returns:
            UserDecision: 反序列化的决策实体。
        """
        return cls(
            decision=data["decision"],
            selected_option=data.get("selected_option"),
            quoted_selections=list(data.get("quoted_selections", [])),
            applies_to_step_id=data.get("applies_to_step_id"),
            resume_step_id=data.get("resume_step_id"),
        )


@dataclass
class TaskContext:
    """任务的运行期上下文，作为单次 Playbook 执行周期的工作记忆与状态存储。

    包含原始材料、知识检索结果、交互历史、已生成产物、人类决策记录等信息。

    Attributes:
        task_id: 唯一任务 ID。
        task_type: 任务类型（如 prd, manual, spec_to_agent 等）。
        username: 触发此任务的用户名。
        goal: 任务的最终目标描述。
        title: 任务标题。
        user_constraints: 用户指定的硬性约束条件列表。
        source_materials: 业务原始输入材料列表。
        knowledge_context: 召回的局部知识库上下文数据。
        format_spec: 期望生成的产物格式规范描述。
        round_history: 轮次交互历史列表。
        round_count: 已经运行的交互轮次计数。
        open_disputes: 当前待解决的争议/Decision Gate 描述列表。
        user_decisions: 已收集到的用户裁决结果列表。
        gate_results: 验收门禁/审计规则检查结果列表。
        artifacts: 该任务生命周期中已生成并归档的交付产物列表。
        degradation_state: 降级/假成功状态标记字典，如包含 degraded=True。
        inputs: 任务启动时的额外输入参数字典。
        step_outputs: 用于在步骤之间传递中间临时产物的字典。
    """
    task_id: str
    task_type: str
    username: str
    goal: str
    title: str
    user_constraints: List[str] = field(default_factory=list)
    source_materials: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_context: Dict[str, Any] = field(default_factory=dict)
    format_spec: Optional[str] = None
    round_history: List[Dict[str, Any]] = field(default_factory=list)
    round_count: int = 0
    open_disputes: List[Dict[str, Any]] = field(default_factory=list)
    user_decisions: List[UserDecision] = field(default_factory=list)
    gate_results: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[Artifact] = field(default_factory=list)
    degradation_state: Dict[str, Any] = field(default_factory=dict)
    inputs: Dict[str, Any] = field(default_factory=dict)
    step_outputs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 TaskContext 序列化为字典。

        Returns:
            Dict[str, Any]: 序列化后的字典。
        """
        data = asdict(self)
        # 显式递归序列化嵌套的 UserDecision 与 Artifact 对象列表
        data["user_decisions"] = [decision.to_dict() for decision in self.user_decisions]
        data["artifacts"] = [artifact.to_dict() for artifact in self.artifacts]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskContext":
        """从字典反序列化重构 TaskContext 实例。

        Args:
            data: 包含 TaskContext 完整元数据与状态的字典。

        Returns:
            TaskContext: 反序列化还原出的任务上下文对象。
        """
        return cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            username=data["username"],
            goal=data.get("goal", ""),
            title=data.get("title", ""),
            user_constraints=list(data.get("user_constraints", [])),
            source_materials=list(data.get("source_materials", [])),
            knowledge_context=dict(data.get("knowledge_context", {})),
            format_spec=data.get("format_spec"),
            round_history=list(data.get("round_history", [])),
            round_count=data.get("round_count", 0),
            open_disputes=list(data.get("open_disputes", [])),
            user_decisions=[UserDecision.from_dict(item) for item in data.get("user_decisions", [])],
            gate_results=list(data.get("gate_results", [])),
            artifacts=[Artifact.from_dict(item) for item in data.get("artifacts", [])],
            degradation_state=dict(data.get("degradation_state", {})),
            inputs=dict(data.get("inputs", {})),
            step_outputs=dict(data.get("step_outputs", {})),
        )

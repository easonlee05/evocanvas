"""EvoCanvas 核心契约层工作项（WorkItem）定义模块。

该模块定义了 EvoCanvas 原生的统一任务边界契约（WorkItem），
作为多 Lane 并行开发以及数字 PM 控制面的核心契约。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from app.core.events import utc_now_iso
from app.core.persistence import FilePersistenceMixin


class WorkType(str, Enum):
    """EvoCanvas 定义的工作项类型枚举。"""
    SPEC_TO_AGENT = "spec_to_agent"
    ACCEPTANCE_REVIEW = "acceptance_review"
    CHANGE_IMPACT = "change_impact"
    FEEDBACK_INTAKE = "feedback_intake"
    PRD = "legacy_prd"
    MANUAL = "legacy_manual"


class WorkStatus(str, Enum):
    """EvoCanvas 工作项的生命周期状态枚举。"""
    CREATED = "created"
    RUNNING = "running"
    WAITING_FOR_DECISION = "waiting_for_decision"
    WAITING_FOR_WORKER = "waiting_for_worker"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


@dataclass
class WorkItem(FilePersistenceMixin):
    """最小的 EvoCanvas 共享工作单元契约实体。

    承载了工作项的唯一身份标识，并使用外部引用（product_context_ref 与 artifact_graph_ref）的形式，
    解耦了底层的执行引擎细节和庞大的状态记忆。

    Attributes:
        work_type: 工作项类型。
        playbook_id: 关联的套路/流程规范 ID。
        title: 工作项标题。
        objective: 工作项的目标描述。
        workspace_id: 关联的工作空间 ID。
        product_context_ref: 关联的产品上下文存储路径或引用 ID（ProductContext 存储键）。
        artifact_graph_ref: 关联的交付资产关系图存储路径或引用 ID（ArtifactGraph 存储键）。
        status: 当前的生命状态。
        work_id: 唯一工作项 ID，自动生成。
        current_decision_gate_id: 当前正在阻塞该工作项的 DecisionGate ID，若无则为 None。
        created_at: 创建时间戳。
        updated_at: 最近一次更新时间戳。
        metadata: 其他元数据字典。
    """

    work_type: WorkType
    playbook_id: str
    title: str
    objective: str
    workspace_id: str
    product_context_ref: str
    artifact_graph_ref: str
    status: WorkStatus = WorkStatus.CREATED
    work_id: str = field(default_factory=lambda: f"work_{uuid4().hex[:12]}")
    current_decision_gate_id: Optional[str] = None
    iteration: int = 0
    parent_work_id: Optional[str] = None
    review_cycle_id: Optional[str] = None
    max_review_iterations: int = 2
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        """更新工作项的 updated_at 时间戳为当前 UTC 时间。"""
        self.updated_at = utc_now_iso()

    def to_dict(self) -> Dict[str, Any]:
        """将 WorkItem 序列化为字典。

        Returns:
            Dict[str, Any]: 序列化后的字典。
        """
        data = asdict(self)
        data["work_type"] = self.work_type.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkItem":
        """从字典反序列化重构 WorkItem 实例。

        Args:
            data: 包含 WorkItem 各个字段的字典。

        Returns:
            WorkItem: 反序列化出的工作项实体。
        """
        return cls(
            work_id=data.get("work_id", f"work_{uuid4().hex[:12]}"),
            work_type=WorkType(data["work_type"]),
            playbook_id=data["playbook_id"],
            title=data.get("title", ""),
            objective=data.get("objective", ""),
            workspace_id=data.get("workspace_id", ""),
            product_context_ref=data["product_context_ref"],
            artifact_graph_ref=data["artifact_graph_ref"],
            status=WorkStatus(data.get("status", WorkStatus.CREATED.value)),
            current_decision_gate_id=data.get("current_decision_gate_id"),
            iteration=int(data.get("iteration", 0)),
            parent_work_id=data.get("parent_work_id"),
            review_cycle_id=data.get("review_cycle_id"),
            max_review_iterations=int(data.get("max_review_iterations", 2)),
            created_at=data.get("created_at", utc_now_iso()),
            updated_at=data.get("updated_at", utc_now_iso()),
            metadata=dict(data.get("metadata", {})),
        )

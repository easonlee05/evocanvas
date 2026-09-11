"""EvoCanvas 任务与工作流领域模型定义。

包含工作流步骤规格、任务定义注册以及任务运行状态的契约定义。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.context import TaskContext
from app.core.errors import DomainError
from app.core.events import Event
from app.core.tools import ToolCall, ToolPolicy


class TaskStatus(str, Enum):
    """任务的运行状态枚举。"""
    CREATED = "created"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class StepStatus(str, Enum):
    """工作流单步执行结果的状态枚举。"""
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    NEEDS_ARBITRATION = "needs_arbitration"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    """定义工作流的一个静态步骤。

    Attributes:
        id: 步骤的唯一 ID 标识。
        type: 步骤类型（如 'llm_call', 'tool_execution'）。
        title: 步骤对外的中文显示标题。
        role: 执行该步骤的 Agent 角色名，默认 'SYSTEM'。
        input_keys: 声明该步骤依赖的上下文输入 Key 列表。
        output_keys: 声明该步骤输出并回写至上下文的 Key 列表。
        allowed_tools: 本步骤被授权允许调用的工具列表。
        retry_policy: 步骤失败重试策略字典。
        pause_policy: 步骤暂停挂起策略字典。
        parallel_group: 并行组标识，若有。
        on_success: 步骤成功后跳转的下一个步骤 ID，默认为 None 表示按顺序往下。
        on_failure: 步骤失败后跳转的目标步骤 ID。
    """
    id: str
    type: str
    title: str
    role: str = "SYSTEM"
    input_keys: List[str] = field(default_factory=list)
    output_keys: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)
    retry_policy: Dict[str, Any] = field(default_factory=dict)
    pause_policy: Dict[str, Any] = field(default_factory=dict)
    parallel_group: Optional[str] = None
    on_success: Optional[str] = None
    on_failure: Optional[str] = None


@dataclass
class WorkflowSpec:
    """工作流规格声明，由一系列静态步骤有序编排而成。

    Attributes:
        name: 工作流名称。
        version: 工作流版本。
        steps: 静态步骤 WorkflowStep 的有序列表。
    """
    name: str
    version: str
    steps: List[WorkflowStep]

    def step_index(self, step_id: str) -> int:
        """根据步骤 ID 获取该步骤在步骤列表中的 0 索引位置。

        Args:
            step_id: 步骤 ID。

        Returns:
            int: 该步骤的索引号。

        Raises:
            KeyError: 当步骤 ID 不存在于当前工作流时抛出。
        """
        for index, step in enumerate(self.steps):
            if step.id == step_id:
                return index
        raise KeyError(f"unknown workflow step: {step_id}")


@dataclass
class StepResult:
    """步骤执行完成后产出的结果信息承载实体。

    Attributes:
        step_id: 执行完成的步骤 ID。
        status: 执行结果状态。
        summary: 执行结果的中文简短摘要。
        outputs: 该步骤执行产出并待写回上下文的数据字典。
        events: 该步骤执行中产生的审计/链路追踪结构化事件列表。
        tool_calls: 该步骤执行中发生过的所有受控工具调用记录列表。
        error: 执行中若发生异常时的 DomainError 错误描述。
        next_step_id: 引擎下一步应跳转跑的目标步骤 ID。
        resume_step_id: 如果步骤被挂起，下一次被恢复运行时应当从哪个步骤 ID 重新跑。
    """
    step_id: str
    status: StepStatus
    summary: str = ""
    outputs: Dict[str, Any] = field(default_factory=dict)
    events: List[Event] = field(default_factory=list)
    tool_calls: List[ToolCall] = field(default_factory=list)
    error: Optional[DomainError] = None
    next_step_id: Optional[str] = None
    resume_step_id: Optional[str] = None


@dataclass
class TaskDefinition:
    """任务的完整模板定义，绑定了具体的工作流 Spec 和工具调用政策。

    Attributes:
        type: 任务类型标识符。
        display_name: 任务的对外显示名称。
        input_schema: 输入参数校验 JSON Schema 规范。
        workflow: 绑定的有序工作流步骤规格 WorkflowSpec。
        tool_policy: 绑定的受控工具治理规则 ToolPolicy。
        agents: 绑定的 Agent 角色及人格设定参数。
        round_policy: 交互轮次限制与降级策略。
        gate_policy: 准入准出与验收门禁策略。
        output_spec: 最终期望交付的资产规格声明。
        metadata: 其他元数据字典。
    """
    type: str
    display_name: str
    input_schema: Dict[str, Any]
    workflow: WorkflowSpec
    tool_policy: ToolPolicy
    agents: Dict[str, Any] = field(default_factory=dict)
    round_policy: Dict[str, Any] = field(default_factory=dict)
    gate_policy: Dict[str, Any] = field(default_factory=dict)
    output_spec: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """在运行时承载的单个任务执行实例，包含其定义、上下文与生命周期状态。

    Attributes:
        definition: 绑定的静态任务定义模板 TaskDefinition。
        context: 该任务运行期的工作上下文 TaskContext。
        status: 任务当下的生命周期状态，默认为 CREATED。
        task_id: 任务的唯一 UUID 标识，自动生成。
        waiting_step_id: 如果任务在等待人类 Decision Gate 裁决，此处记录挂起时的步骤 ID。
        resume_step_id: 收到决策结果后恢复运行时，应当开始跑的步骤 ID。
        is_deleted: 是否已被逻辑删除。
        deleted_at: 逻辑删除时间戳。
    """
    definition: TaskDefinition
    context: TaskContext
    status: TaskStatus = TaskStatus.CREATED
    task_id: str = field(default_factory=lambda: f"task_{uuid4().hex[:12]}")
    waiting_step_id: Optional[str] = None
    resume_step_id: Optional[str] = None
    is_deleted: bool = False
    deleted_at: Optional[str] = None

    def to_record(self) -> Dict[str, Any]:
        """将 Task 的基础运行状态字段序列化为扁平的存储记录字典。

        Returns:
            Dict[str, Any]: 数据库存储所需的键值记录字典。
        """
        return {
            "task_id": self.task_id,
            "task_type": self.definition.type,
            "status": self.status.value,
            "waiting_step_id": self.waiting_step_id,
            "resume_step_id": self.resume_step_id,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at,
        }

    @classmethod
    def from_record(cls, definition: TaskDefinition, context: TaskContext, data: Dict[str, Any]) -> "Task":
        """结合 TaskDefinition 和 TaskContext，从数据库存储记录重建 Task 运行时实例。

        Args:
            definition: 静态任务模板定义。
            context: 运行期任务上下文。
            data: 扁平的存储记录字典。

        Returns:
            Task: 重建出的 Task 实例。
        """
        return cls(
            definition=definition,
            context=context,
            status=TaskStatus(data.get("status", TaskStatus.CREATED.value)),
            task_id=data["task_id"],
            waiting_step_id=data.get("waiting_step_id"),
            resume_step_id=data.get("resume_step_id"),
            is_deleted=data.get("is_deleted", False),
            deleted_at=data.get("deleted_at"),
        )

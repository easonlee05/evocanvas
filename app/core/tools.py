"""Evoloop 3.0 核心契约层受控工具规范与权限治理模块。

定义了受控工具调用规范（ToolSpec、ToolCall、ToolResult）以及基于角色和步骤维度的工具调用白名单授权机制（ToolPolicy）。
在 Evoloop 3.0 架构下，Agent 所有对外部系统或文件的读写操作均受此治理层严格控制与审计。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.artifacts import Artifact
from app.core.errors import DomainError


@dataclass
class ToolSpec:
    """工具规格说明类，声明受控工具的元数据、输入输出 Schema 以及副作用和权限要求。

    Attributes:
        name: 工具的唯一名称（例如 'artifact.write'）。
        version: 工具版本号。
        description: 工具用途及行为功能描述。
        input_schema: 输入参数的 JSON Schema 校验规范字典。
        output_schema: 返回结果数据的 JSON Schema 校验规范字典。
        side_effect: 副作用说明（如 'write', 'read', 'network'）。
        required_permissions: 执行此工具所需的特别权限列表。
        timeout_seconds: 工具执行超时时间（秒）。
        failure_semantics: 工具失败时的语义降级处理说明。
        event_semantics: 声明工具执行时产生何种结构化审计事件。
    """
    name: str
    version: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    side_effect: str
    required_permissions: List[str] = field(default_factory=list)
    timeout_seconds: int = 30
    failure_semantics: str = "Return ToolResult.status='failed' with a structured DomainError."
    event_semantics: str = "write/external tools emit tool.call.* structured events."


@dataclass
class ToolCall:
    """一次具体的工具调用意向记录，包含执行上下文和输入参数。

    Attributes:
        task_id: 关联的任务 ID。
        step_id: 调用工具时所处的步骤 ID。
        agent_role: 执行调用的 Agent 角色（如 'compiler'）。
        tool_name: 工具名称。
        arguments: 具体的入参键值对。
        id: 工具调用的唯一标识 ID，自动生成。
        status: 工具调用状态，如 'created', 'started', 'completed', 'failed', 'denied'。
        started_at: 调用开始的 ISO 时间戳。
        completed_at: 调用结束的 ISO 时间戳。
    """
    task_id: str
    step_id: str
    agent_role: str
    tool_name: str
    arguments: Dict[str, Any]
    id: str = field(default_factory=lambda: f"tool_{uuid4().hex[:12]}")
    status: str = "created"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """将 ToolCall 实例转换为字典格式。

        Returns:
            Dict[str, Any]: 转换后的字典。
        """
        return asdict(self)


@dataclass
class ToolResult:
    """工具调用的执行结果，包含状态、生成产物或异常。

    Attributes:
        call_id: 关联 Dios.UUID 唯一 ID。
        status: 执行状态，如 'completed', 'failed', 'denied'。
        summary: 执行结果的简短中文摘要。
        data: 详细的返回数据。
        artifacts: 工具执行过程中产生的交付产物列表（如写入文件时生成）。
        error: 发生错误时的领域错误模型（DomainError）。
    """
    call_id: str
    status: str
    summary: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Artifact] = field(default_factory=list)
    error: Optional[DomainError] = None


@dataclass
class ToolPolicyRule:
    """工具授权策略规则，定义了在特定步骤下特定角色能使用或不能使用的工具列表。

    Attributes:
        role: 适用的角色名称（支持通配符 '*'）。
        step_id: 适用的步骤 ID（支持通配符 '*'）。
        allowed_tools: 允许调用的工具名称列表（支持通配符 '*' 匹配全部）。
        denied_tools: 明确禁止调用的工具名称列表。
        max_calls_per_step: 单个步骤内允许调用的最大次数上限，默认 20，防范 LLM 陷入无限工具调用死循环。
        require_user_approval_for: 需要人类在执行前二次审批确认的工具列表。
    """
    role: str
    step_id: str
    allowed_tools: List[str]
    denied_tools: List[str] = field(default_factory=list)
    max_calls_per_step: int = 20
    require_user_approval_for: List[str] = field(default_factory=list)


@dataclass
class ToolPolicy:
    """完整的任务工具治理授权策略，包含特定任务类型下的所有过滤规则集。

    Attributes:
        task_type: 任务/Playbook 类型名称。
        rules: 包含的授权规则规则集。
    """
    task_type: str
    rules: List[ToolPolicyRule] = field(default_factory=list)

    def is_allowed(self, role: str, step_id: str, tool_name: str) -> bool:
        """检查特定角色在特定步骤下调用指定工具是否被允许。

        Args:
            role: 调用者的角色名称。
            step_id: 当前所处的步骤 ID。
            tool_name: 需要调用的受控工具名称。

        Returns:
            bool: 允许调用返回 True，否则返回 False（被拒绝）。
        """
        for rule in self.rules:
            # 检查角色是否匹配，支持通配符
            role_matches = rule.role in {role, "*"}
            step_matches = rule.step_id in {step_id, "*"}
            if not (role_matches and step_matches):
                continue
            # 明确拒绝黑名单工具
            if tool_name in rule.denied_tools:
                return False
            # 检查是否包含在白名单允许工具列表中
            if "*" in rule.allowed_tools or tool_name in rule.allowed_tools:
                return True
        return False

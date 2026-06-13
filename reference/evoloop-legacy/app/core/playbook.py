"""Evoloop 3.0 控制面与工作流规范（Playbook）及产品上下文（ProductContext）模型定义。

本模块定义了数字产品经理（Digital PM）的决策门禁（DecisionGate）、工作流程步骤（PlaybookStep）、
剧本（Playbook）、产品上下文（ProductContext）以及下游 AI 执行单元的对接规格（WorkerAdapter）等冻结契约。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.core.events import utc_now_iso
from app.core.persistence import FilePersistenceMixin


class DecisionGateStatus(str, Enum):
    """决策门禁状态枚举。"""
    OPEN = "open"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class WorkerTargetType(str, Enum):
    """下游 AI 执行工人的目标运行平台或协议接口枚举。"""
    WEB = "web"
    CLI = "cli"
    MCP = "mcp"
    CODEX = "codex"
    CLAUDE_CODE = "claude_code"
    CURSOR = "cursor"


@dataclass
class SourceInput:
    """业务原始输入的来源描述卡片模型。

    Attributes:
        input_id: 输入 ID。
        kind: 输入种类（如 'pr_comment', 'user_feedback', 'prd_draft'）。
        summary: 业务摘要。
        source_ref: 指向外部物理来源（如 PR 链接、邮件或文件路径）的引用标识。
        metadata: 其他元数据字典。
    """
    input_id: str
    kind: str
    summary: str
    source_ref: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 SourceInput 转换为字典。

        Returns:
            Dict[str, Any]: 转换后的字典。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceInput":
        """从字典反序列化生成 SourceInput 实例。

        Args:
            data: 字典数据。

        Returns:
            SourceInput: 还原后的实例。
        """
        return cls(
            input_id=data["input_id"],
            kind=data["kind"],
            summary=data.get("summary", ""),
            source_ref=data.get("source_ref"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class Requirement:
    """产品级的功能性或非功能性需求条目模型。

    Attributes:
        requirement_id: 需求 ID。
        statement: 需求具体描述陈述。
        priority: 优先级级别（如 'must', 'should', 'could', 'won't'）。
        rationale: 需求背后的业务价值与理由陈述。
        metadata: 额外属性字典。
    """
    requirement_id: str
    statement: str
    priority: str = "must"
    rationale: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 Requirement 转换为字典。

        Returns:
            Dict[str, Any]: 转换后的字典。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Requirement":
        """从字典反序列化生成 Requirement 实例。

        Args:
            data: 字典数据。

        Returns:
            Requirement: 还原后的需求对象。
        """
        return cls(
            requirement_id=data["requirement_id"],
            statement=data["statement"],
            priority=data.get("priority", "must"),
            rationale=data.get("rationale", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ProductConstraint:
    """产品设计与工程实现边界的硬约束条目。

    Attributes:
        constraint_id: 约束 ID。
        statement: 约束条款描述（如架构边界、安全边界或合规性要求）。
        category: 约束分类（如 'security', 'performance', 'general'）。
        metadata: 额外属性字典.
    """
    constraint_id: str
    statement: str
    category: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 ProductConstraint 转换为字典。

        Returns:
            Dict[str, Any]: 转换后的字典。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductConstraint":
        """从字典反序列化重构 ProductConstraint 实例。

        Args:
            data: 包含约束数据的字典。

        Returns:
            ProductConstraint: 重构后的约束对象。
        """
        return cls(
            constraint_id=data["constraint_id"],
            statement=data["statement"],
            category=data.get("category", "general"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ProductAssumption:
    """业务决策中所预设的、待验证的假设条目模型。

    Attributes:
        assumption_id: 假设 ID。
        statement: 假设的具体文字描述。
        status: 当前状态（如 'open', 'validated', 'invalidated'）。
        metadata: 其他扩展属性。
    """
    assumption_id: str
    statement: str
    status: str = "open"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 ProductAssumption 转换为字典。

        Returns:
            Dict[str, Any]: 转换后的字典。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductAssumption":
        """从字典反序列化重构 ProductAssumption 实例。

        Args:
            data: 字典数据。

        Returns:
            ProductAssumption: 重构出的假设模型。
        """
        return cls(
            assumption_id=data["assumption_id"],
            statement=data["statement"],
            status=data.get("status", "open"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class KnowledgeRef:
    """指向知识检索库（Knowledge Store）条目或外部资产文档定位器的索引模型。

    Attributes:
        knowledge_id: 知识索引 ID。
        kind: 知识库类型（如 'confluence', 'git_readme', 'local_wiki'）。
        summary: 知识切片的简短摘要。
        locator: 文档位置定位器（URI 或物理定位路径）。
        metadata: 其他扩展属性字典。
    """
    knowledge_id: str
    kind: str
    summary: str
    locator: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 KnowledgeRef 转换为字典。

        Returns:
            Dict[str, Any]: 转换后的字典。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeRef":
        """从字典反序列化重构 KnowledgeRef 实例。

        Args:
            data: 字典元数据。

        Returns:
            KnowledgeRef: 还原后的知识索引描述实体。
        """
        return cls(
            knowledge_id=data["knowledge_id"],
            kind=data["kind"],
            summary=data.get("summary", ""),
            locator=data.get("locator"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class WorkerFeedback:
    """来自下游 AI worker 执行适配层反向吐出的反馈诊断报告模型。

    Attributes:
        feedback_id: 反馈 ID。
        worker_id: 反馈来源的 downstream worker ID 或适配器 ID。
        summary: 反馈异常或诊断总结。
        status: 反馈严重程度级别（如 'info', 'warning', 'error'）。
        related_artifact_ids: 受到该反馈直接影响或关联的交付产物 ID 列表。
        metadata: 其他属性字典。
    """
    feedback_id: str
    worker_id: str
    summary: str
    status: str = "info"
    related_artifact_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 WorkerFeedback 转换为字典。

        Returns:
            Dict[str, Any]: 转换后的字典。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerFeedback":
        """从字典反序列化重构 WorkerFeedback 实例。

        Args:
            data: 反馈数据字典。

        Returns:
            WorkerFeedback: 还原后的反馈实体。
        """
        return cls(
            feedback_id=data["feedback_id"],
            worker_id=data["worker_id"],
            summary=data.get("summary", ""),
            status=data.get("status", "info"),
            related_artifact_ids=list(data.get("related_artifact_ids", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class DecisionOption:
    """人类决策门禁（DecisionGate）中所提供的备选解决选项卡片。

    Attributes:
        option_id: 选项 ID。
        label: 选项的中文文字标签（例如 '执行强制备份'）。
        summary: 该选项的详细操作含义。
        consequences: 选用该选项可能带来的潜在系统及业务负面后果/影响说明列表。
        metadata: 其他元数据属性。
    """
    option_id: str
    label: str
    summary: str = ""
    consequences: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 DecisionOption 转换为字典。

        Returns:
            Dict[str, Any]: 转换后的字典。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionOption":
        """从字典反序列化生成 DecisionOption 实例。

        Args:
            data: 字典数据。

        Returns:
            DecisionOption: 还原后的可选项卡片。
        """
        return cls(
            option_id=data["option_id"],
            label=data["label"],
            summary=data.get("summary", ""),
            consequences=list(data.get("consequences", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class GateResolution:
    """人类最终在决策门禁上签署并选择的选项决议记录。

    Attributes:
        selected_option_id: 用户最终批准选中的备选选项 ID。
        rationale: 做出该项决议的支撑理由或修改说明。
        decided_by: 决议人身份（如 'user', 'proxy_agent'）。
        decided_at: 签署决议的 UTC 时间戳。
        metadata: 其他元数据属性。
    """
    selected_option_id: str
    rationale: str = ""
    decided_by: str = "user"
    decided_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 GateResolution 转换为字典。

        Returns:
            Dict[str, Any]: 转换后的字典。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GateResolution":
        """从字典反序列化重构 GateResolution 实例。

        Args:
            data: 决议字典数据。

        Returns:
            GateResolution: 决议记录对象。
        """
        return cls(
            selected_option_id=data["selected_option_id"],
            rationale=data.get("rationale", ""),
            decided_by=data.get("decided_by", "user"),
            decided_at=data.get("decided_at", utc_now_iso()),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class DecisionGate(FilePersistenceMixin):
    """表示一个等待人类决策裁决的决策门禁（Evoloop 3.0 冻结契约）。

    当 AI Agent 面对需求冲突、分支不确定性等棘手问题时，通过向此门禁写入待决提问来挂起当前执行流，
    避免做出盲目假设，保障系统演进的安全合规性。

    Attributes:
        gate_id: 决策门禁的唯一 ID。
        work_id: 关联的受阻工作项 ID。
        question: 向人类或裁决代理提出的核心中文争议问题。
        options: 提供的排他/非排他备选决议选项 DecisionOption 列表。
        impact_summary: 阻塞不决议可能对整体项目排期或架构造成的潜在风险/影响总结。
        blocking: 是否在决议签署前强行阻塞当前步骤的执行。
        status: 门禁状态，默认为 OPEN。
        resolution: 已签署的决议记录，若无则为 None。
        metadata: 其他属性元数据。
    """

    gate_id: str
    work_id: str
    question: str
    options: List[DecisionOption]
    impact_summary: str
    blocking: bool = True
    status: DecisionGateStatus = DecisionGateStatus.OPEN
    resolution: Optional[GateResolution] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 DecisionGate 及其嵌套的 options、resolution 序列化为字典格式。

        Returns:
            Dict[str, Any]: 序列化后的字典。
        """
        data = asdict(self)
        data["status"] = self.status.value
        data["options"] = [item.to_dict() for item in self.options]
        if self.resolution is not None:
            data["resolution"] = self.resolution.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionGate":
        """从字典反序列化重构 DecisionGate 实例。

        Args:
            data: 嵌套字段字典。

        Returns:
            DecisionGate: 重建出的决策门禁实体。
        """
        return cls(
            gate_id=data["gate_id"],
            work_id=data["work_id"],
            question=data["question"],
            options=[DecisionOption.from_dict(item) for item in data.get("options", [])],
            impact_summary=data.get("impact_summary", ""),
            blocking=bool(data.get("blocking", True)),
            status=DecisionGateStatus(data.get("status", DecisionGateStatus.OPEN.value)),
            resolution=GateResolution.from_dict(data["resolution"]) if data.get("resolution") else None,
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ProductContext(FilePersistenceMixin):
    """表示一个完整数字产品的全局产品上下文（Evoloop 3.0 冻结契约）。

    作为跨运行期、跨执行单元（Worker Adapter）的单一真相源（Single Source of Truth），
    汇聚了所有的原始材料、已被人类确认的需求、约束、做出的预设假设以及已签署的决策记录。

    Attributes:
        objective: 产品的最终核心价值目标定位描述。
        source_inputs: 业务原始输入来源列表。
        requirements: 结构化产品需求明细列表。
        constraints: 架构与项目级硬性约束列表。
        assumptions: 项目假设模型列表。
        user_decisions: 已归档的历史决策门禁决议列表。
        knowledge_refs: 引用的知识检索文档索引列表。
        worker_feedback: 收集到的 worker 诊断反馈。
        metadata: 全局属性元数据。
    """

    objective: str
    source_inputs: List[SourceInput] = field(default_factory=list)
    requirements: List[Requirement] = field(default_factory=list)
    constraints: List[ProductConstraint] = field(default_factory=list)
    assumptions: List[ProductAssumption] = field(default_factory=list)
    user_decisions: List[DecisionGate] = field(default_factory=list)
    knowledge_refs: List[KnowledgeRef] = field(default_factory=list)
    worker_feedback: List[WorkerFeedback] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 ProductContext 下的所有子契约对象深度递归序列化为字典格式。

        Returns:
            Dict[str, Any]: 序列化后的深层嵌套字典。
        """
        return {
            "objective": self.objective,
            "source_inputs": [item.to_dict() for item in self.source_inputs],
            "requirements": [item.to_dict() for item in self.requirements],
            "constraints": [item.to_dict() for item in self.constraints],
            "assumptions": [item.to_dict() for item in self.assumptions],
            "user_decisions": [item.to_dict() for item in self.user_decisions],
            "knowledge_refs": [item.to_dict() for item in self.knowledge_refs],
            "worker_feedback": [item.to_dict() for item in self.worker_feedback],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductContext":
        """从字典反序列化重构全局 ProductContext 实例。

        Args:
            data: 嵌套的字典详情。

        Returns:
            ProductContext: 还原后的产品上下文状态实体。
        """
        return cls(
            objective=data.get("objective", ""),
            source_inputs=[SourceInput.from_dict(item) for item in data.get("source_inputs", [])],
            requirements=[Requirement.from_dict(item) for item in data.get("requirements", [])],
            constraints=[ProductConstraint.from_dict(item) for item in data.get("constraints", [])],
            assumptions=[ProductAssumption.from_dict(item) for item in data.get("assumptions", [])],
            user_decisions=[DecisionGate.from_dict(item) for item in data.get("user_decisions", [])],
            knowledge_refs=[KnowledgeRef.from_dict(item) for item in data.get("knowledge_refs", [])],
            worker_feedback=[WorkerFeedback.from_dict(item) for item in data.get("worker_feedback", [])],
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class PlaybookStep:
    """定义 Playbook 工作流程中的一个步骤节点静态规格。

    Attributes:
        step_id: 步骤唯一 ID。
        title: 步骤对外的中文显示标题。
        purpose: 设定该步骤的执行意图和预期结果目的。
        allowed_tools: 本步骤被授权允许调用的工具名称白名单列表。
        produces_artifact_types: 声明本步骤执行完成后应当输出的交付资产节点类型列表。
        next_step_ids: 工作流偏序路由中，本步骤之后的后续步骤 ID 候选列表。
        metadata: 其他元数据字典。
    """
    step_id: str
    title: str
    purpose: str
    allowed_tools: List[str] = field(default_factory=list)
    produces_artifact_types: List[str] = field(default_factory=list)
    next_step_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 PlaybookStep 转换为字典。

        Returns:
            Dict[str, Any]: 转换后的字典。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlaybookStep":
        """从字典反序列化重构 PlaybookStep。

        Args:
            data: 字典数据。

        Returns:
            PlaybookStep: 重构后的步骤。
        """
        return cls(
            step_id=data["step_id"],
            title=data.get("title", ""),
            purpose=data.get("purpose", ""),
            allowed_tools=list(data.get("allowed_tools", [])),
            produces_artifact_types=list(data.get("produces_artifact_types", [])),
            next_step_ids=list(data.get("next_step_ids", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class Playbook(FilePersistenceMixin):
    """表示一个完整数字产品经理的工作套路流规范（Evoloop 3.0 冻结契约）。

    指明了针对特定业务触发场景（trigger_types），系统应当遵循的执行步骤、工具边界与期望交付资产。

    Attributes:
        playbook_id: Playbook 唯一 ID。
        version: 剧本演进版本。
        trigger_types: 触发启动该 Playbook 运行的目标场景类型列表（如 'feedback', 'new_feature'）。
        steps: 静态步骤编排 PlaybookStep 列表。
        decision_gate_ids: 该剧本中涉及的所有预设决策门禁 ID 列表。
        allowed_tools: 该剧本下所有步骤合并授权的全局受控工具白名单。
        output_artifact_types: 该剧本最终执行完成后应当导出的最终核心交付资产类型列表。
        metadata: 其他属性字典。
    """

    playbook_id: str
    version: str
    trigger_types: List[str]
    steps: List[PlaybookStep]
    decision_gate_ids: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)
    output_artifact_types: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 Playbook 序列化为适合文件存储的嵌套字典。

        Returns:
            Dict[str, Any]: 序列化后的字典。
        """
        return {
            "playbook_id": self.playbook_id,
            "version": self.version,
            "trigger_types": list(self.trigger_types),
            "steps": [item.to_dict() for item in self.steps],
            "decision_gate_ids": list(self.decision_gate_ids),
            "allowed_tools": list(self.allowed_tools),
            "output_artifact_types": list(self.output_artifact_types),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Playbook":
        """从字典反序列化重构 Playbook 实例。

        Args:
            data: 字典数据。

        Returns:
            Playbook: 还原后的 Playbook 剧本实体。
        """
        return cls(
            playbook_id=data["playbook_id"],
            version=data["version"],
            trigger_types=list(data.get("trigger_types", [])),
            steps=[PlaybookStep.from_dict(item) for item in data.get("steps", [])],
            decision_gate_ids=list(data.get("decision_gate_ids", [])),
            allowed_tools=list(data.get("allowed_tools", [])),
            output_artifact_types=list(data.get("output_artifact_types", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class WorkerAdapter(FilePersistenceMixin):
    """表示一个 downstream AI 适配层（Evoloop 3.0 冻结契约）。

    定义了在执行任务包时，分发对接 Codex、Claude Code、Cursor 等底层具体执行器所遵循的传输格式及限制。

    Attributes:
        adapter_id: 适配器唯一 ID。
        target_type: 目标工人的执行通道类型。
        package_format: 打包下发任务的格式规格声明（如 'zip', 'json_payload'）。
        invocation_policy: 调用分发政策字典。
        result_intake_policy: 返回结果收集与格式解析政策字典。
        metadata: 其他元数据字典。
    """

    adapter_id: str
    target_type: WorkerTargetType
    package_format: str
    invocation_policy: Dict[str, Any] = field(default_factory=dict)
    result_intake_policy: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 WorkerAdapter 转换为适合文件持久化存储的字典。

        Returns:
            Dict[str, Any]: 序列化后的字典。
        """
        data = asdict(self)
        data["target_type"] = self.target_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerAdapter":
        """从字典反序列化重构 WorkerAdapter 实例。

        Args:
            data: 包含适配器配置元数据的字典。

        Returns:
            WorkerAdapter: 重构后的适配器实体。
        """
        return cls(
            adapter_id=data["adapter_id"],
            target_type=WorkerTargetType(data["target_type"]),
            package_format=data["package_format"],
            invocation_policy=dict(data.get("invocation_policy", {})),
            result_intake_policy=dict(data.get("result_intake_policy", {})),
            metadata=dict(data.get("metadata", {})),
        )


"""EvoCanvas 验收评审（Review）与覆盖率报告模型定义。

包含评审结果（PASS/FAIL）、缺陷严重级别、需求覆盖率（RequirementCoverage）、
评审缺陷问题（ReviewIssue）、以及生成的缺陷修复任务（ReviewFixTask）定义。
本模块是 EvoCanvas 控制闭环中用于执行验收审计（Acceptance Review）的核心契约。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.events import utc_now_iso
from app.core.persistence import FilePersistenceMixin


class ReviewVerdict(str, Enum):
    """评审结论枚举。"""
    PASS = "pass"
    PASS_WITH_NOTES = "pass_with_notes"
    CHANGES_REQUIRED = "changes_required"
    BLOCKED = "blocked"


class ReviewIssueSeverity(str, Enum):
    """评审中发现的问题严重程度枚举。"""
    INFO = "info"
    WARNING = "warning"
    MAJOR = "major"
    CRITICAL = "critical"


@dataclass
class RequirementCoverage:
    """需求覆盖情况模型，记录特定需求是否已被实现以及对应的验证凭证。

    Attributes:
        requirement_id: 需求 ID。
        covered: 是否已被覆盖实现。
        evidence_refs: 指向实现凭证（如代码、测试用例或产物文件等）的引用 ID 或路径列表。
        notes: 评审备注说明。
        metadata: 其他元数据字典。
    """
    requirement_id: str
    covered: bool
    evidence_refs: List[str] = field(default_factory=list)
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 RequirementCoverage 序列化为字典。

        Returns:
            Dict[str, Any]: 序列化后的字典。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RequirementCoverage":
        """从字典反序列化重构 RequirementCoverage。

        Args:
            data: 包含覆盖率数据的字典。

        Returns:
            RequirementCoverage: 覆盖率实体对象。
        """
        return cls(
            requirement_id=data["requirement_id"],
            covered=bool(data.get("covered", False)),
            evidence_refs=list(data.get("evidence_refs", [])),
            notes=data.get("notes", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ReviewIssue:
    """验收评审中发现的缺陷或问题记录实体。

    Attributes:
        issue_id: 问题唯一 ID。
        severity: 问题严重程度级别。
        summary: 问题缺陷的中英文摘要。
        related_requirement_ids: 与此缺陷直接相关的需求 ID 列表。
        related_artifact_ids: 包含此缺陷的目标交付产物 ID 列表。
        recommendation: 针对该缺陷提供的修改修复建议建议。
        metadata: 其他元数据。
    """
    issue_id: str
    severity: ReviewIssueSeverity
    summary: str
    related_requirement_ids: List[str] = field(default_factory=list)
    related_artifact_ids: List[str] = field(default_factory=list)
    recommendation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 ReviewIssue 序列化为字典。

        Returns:
            Dict[str, Any]: 序列化后的字典。
        """
        data = asdict(self)
        data["severity"] = self.severity.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewIssue":
        """从字典反序列化重构 ReviewIssue 实例。

        Args:
            data: 问题元数据字典。

        Returns:
            ReviewIssue: 重构出的问题缺陷实例。
        """
        return cls(
            issue_id=data["issue_id"],
            severity=ReviewIssueSeverity(data["severity"]),
            summary=data.get("summary", ""),
            related_requirement_ids=list(data.get("related_requirement_ids", [])),
            related_artifact_ids=list(data.get("related_artifact_ids", [])),
            recommendation=data.get("recommendation", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ReviewFixTask:
    """为修复评审缺陷而生成派发的下游执行任务卡片模型。

    Attributes:
        task_id: 修复任务的唯一 ID。
        title: 修复任务的中文描述标题。
        source_issue_ids: 导致生成此修复任务的源评审缺陷 ID 列表。
        priority: 任务优先级（如 'must', 'should', 'could'）。
        owner_hint: 建议派发执行的 downstream worker 角色或适配器提示。
        metadata: 其他元数据。
    """
    task_id: str
    title: str
    source_issue_ids: List[str] = field(default_factory=list)
    priority: str = "must"
    owner_hint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 ReviewFixTask 序列化为字典。

        Returns:
            Dict[str, Any]: 序列化后的字典。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewFixTask":
        """从字典反序列化重构 ReviewFixTask 实例。

        Args:
            data: 修复任务元数据字典。

        Returns:
            ReviewFixTask: 反序列化出的修复任务卡片。
        """
        return cls(
            task_id=data["task_id"],
            title=data.get("title", ""),
            source_issue_ids=list(data.get("source_issue_ids", [])),
            priority=data.get("priority", "must"),
            owner_hint=data.get("owner_hint"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ReviewResult(FilePersistenceMixin):
    """表示一次完整的验收审计评审报告（EvoCanvas 冻结契约）。

    锚定于机器规格书（machine_spec），表达了本次迭代的最终交付结论。

    Attributes:
        work_id: 关联的工作项 ID。
        machine_spec_ref: 评审所依据的 machine_spec 存储引用 ID 或路径。
        verdict: 评审的最终结论 verdict。
        summary: 结论的简短描述与总评。
        coverage: 需求覆盖率明细列表。
        issues: 发现的缺陷缺陷列表。
        fix_tasks: 为解决上述缺陷而派生的修复任务卡片列表。
        acceptance_protocol_ref: 关联的验收协议模板存储路径或引用 ID，可选。
        review_id: 评审结果报告的唯一 UUID，自动生成。
        created_at: 评审报告生成时间。
        metadata: 其他元数据。
    """

    work_id: str
    machine_spec_ref: str
    verdict: ReviewVerdict
    summary: str
    coverage: List[RequirementCoverage] = field(default_factory=list)
    issues: List[ReviewIssue] = field(default_factory=list)
    fix_tasks: List[ReviewFixTask] = field(default_factory=list)
    acceptance_protocol_ref: Optional[str] = None
    review_id: str = field(default_factory=lambda: f"review_{uuid4().hex[:12]}")
    created_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 ReviewResult 序列化为适合持久化存储的嵌套字典结构。

        Returns:
            Dict[str, Any]: 序列化后的字典。
        """
        return {
            "review_id": self.review_id,
            "work_id": self.work_id,
            "machine_spec_ref": self.machine_spec_ref,
            "acceptance_protocol_ref": self.acceptance_protocol_ref,
            "verdict": self.verdict.value,
            "summary": self.summary,
            "coverage": [item.to_dict() for item in self.coverage],
            "issues": [item.to_dict() for item in self.issues],
            "fix_tasks": [item.to_dict() for item in self.fix_tasks],
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewResult":
        """从字典反序列化重构 ReviewResult 实例。

        Args:
            data: 包含完整评审详情的嵌套字典。

        Returns:
            ReviewResult: 重建出的评审结果实体。
        """
        return cls(
            review_id=data.get("review_id", f"review_{uuid4().hex[:12]}"),
            work_id=data["work_id"],
            machine_spec_ref=data["machine_spec_ref"],
            acceptance_protocol_ref=data.get("acceptance_protocol_ref"),
            verdict=ReviewVerdict(data["verdict"]),
            summary=data.get("summary", ""),
            coverage=[RequirementCoverage.from_dict(item) for item in data.get("coverage", [])],
            issues=[ReviewIssue.from_dict(item) for item in data.get("issues", [])],
            fix_tasks=[ReviewFixTask.from_dict(item) for item in data.get("fix_tasks", [])],
            created_at=data.get("created_at", utc_now_iso()),
            metadata=dict(data.get("metadata", {})),
        )

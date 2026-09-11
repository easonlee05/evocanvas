"""Core contracts for internal EvoCanvas subagent orchestration.

Subagents are bounded internal execution units used either as session-local
reasoning helpers or as formal child tasks coordinated by the control plane.
This module only defines contracts and serialization helpers; it does not
perform scheduling or tool invocation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.errors import DomainError
from app.core.events import utc_now_iso


class SubagentScope(str, Enum):
    """Execution scope for an internal subagent run."""

    SESSION_HELPER = "session_helper"
    FORMAL_SUBTASK = "formal_subtask"


class ExecutionMode(str, Enum):
    """Scheduling mode chosen for a set of helper runs."""

    SERIAL = "serial"
    PARALLEL_HELPERS = "parallel_helpers"


class SubagentRunStatus(str, Enum):
    """Lifecycle states for a bounded subagent run."""

    CREATED = "created"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    DENIED = "denied"
    FAILED = "failed"


class SubagentDenyReason(str, Enum):
    """Governance reasons for denying a subagent spawn request."""

    DEPTH_EXCEEDED = "depth_exceeded"
    FANOUT_EXCEEDED = "fanout_exceeded"
    BUDGET_EXCEEDED = "budget_exceeded"
    PERMISSION_DENIED = "permission_denied"
    PARALLELISM_NOT_ALLOWED = "parallelism_not_allowed"
    SCOPE_NOT_ALLOWED = "scope_not_allowed"


@dataclass
class SubagentBudget:
    """Token, iteration, and fan-out limits applied to a subagent run."""

    max_iterations: int
    max_input_tokens: int
    max_output_tokens: int
    max_tool_calls: int
    spawn_fanout_remaining: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "max_tool_calls": self.max_tool_calls,
            "spawn_fanout_remaining": self.spawn_fanout_remaining,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubagentBudget":
        return cls(
            max_iterations=int(data.get("max_iterations", 1)),
            max_input_tokens=int(data.get("max_input_tokens", 0)),
            max_output_tokens=int(data.get("max_output_tokens", 0)),
            max_tool_calls=int(data.get("max_tool_calls", 0)),
            spawn_fanout_remaining=int(data.get("spawn_fanout_remaining", 0)),
        )


@dataclass
class SubagentSpawnRequest:
    """Request contract for a bounded internal subagent run."""

    scope: SubagentScope
    goal: str
    task_slice: str
    input_refs: List[str]
    input_excerpt: Dict[str, Any]
    allowed_tools: List[str]
    output_schema: Dict[str, Any]
    budget: SubagentBudget
    depth: int = 1
    task_type: Optional[str] = None
    subtask_type: Optional[str] = None
    join_step_id: Optional[str] = None
    acceptance_slice: Dict[str, Any] = field(default_factory=dict)
    subtask_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope": self.scope.value,
            "goal": self.goal,
            "task_slice": self.task_slice,
            "input_refs": list(self.input_refs),
            "input_excerpt": dict(self.input_excerpt),
            "allowed_tools": list(self.allowed_tools),
            "output_schema": dict(self.output_schema),
            "budget": self.budget.to_dict(),
            "depth": self.depth,
            "task_type": self.task_type,
            "subtask_type": self.subtask_type,
            "join_step_id": self.join_step_id,
            "acceptance_slice": dict(self.acceptance_slice),
            "subtask_index": self.subtask_index,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubagentSpawnRequest":
        return cls(
            scope=SubagentScope(data["scope"]),
            goal=str(data.get("goal", "")),
            task_slice=str(data.get("task_slice", "")),
            input_refs=list(data.get("input_refs", [])),
            input_excerpt=dict(data.get("input_excerpt", {})),
            allowed_tools=list(data.get("allowed_tools", [])),
            output_schema=dict(data.get("output_schema", {})),
            budget=SubagentBudget.from_dict(data.get("budget", {})),
            depth=int(data.get("depth", 1)),
            task_type=data.get("task_type"),
            subtask_type=data.get("subtask_type"),
            join_step_id=data.get("join_step_id"),
            acceptance_slice=dict(data.get("acceptance_slice", {})),
            subtask_index=data.get("subtask_index"),
        )


@dataclass
class SubagentResult:
    """Structured result returned from a bounded internal subagent run."""

    summary: str
    structured_output: Dict[str, Any]
    evidence_refs: List[str]
    used_tools: List[str]
    confidence: str
    degraded: bool = False
    degradation_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "structured_output": dict(self.structured_output),
            "evidence_refs": list(self.evidence_refs),
            "used_tools": list(self.used_tools),
            "confidence": self.confidence,
            "degraded": self.degraded,
            "degradation_reason": self.degradation_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubagentResult":
        return cls(
            summary=str(data.get("summary", "")),
            structured_output=dict(data.get("structured_output", {})),
            evidence_refs=list(data.get("evidence_refs", [])),
            used_tools=list(data.get("used_tools", [])),
            confidence=str(data.get("confidence", "")),
            degraded=bool(data.get("degraded", False)),
            degradation_reason=str(data.get("degradation_reason", "")),
        )


@dataclass
class SubagentRun:
    """Auditable execution record for one internal subagent run."""

    parent_task_id: str
    parent_session_id: str
    root_task_id: str
    scope: SubagentScope
    depth: int
    request: SubagentSpawnRequest
    execution_mode: ExecutionMode = ExecutionMode.SERIAL
    status: SubagentRunStatus = SubagentRunStatus.CREATED
    run_id: str = field(default_factory=lambda: f"subagent_{uuid4().hex[:12]}")
    result: Optional[SubagentResult] = None
    error: Optional[DomainError] = None
    deny_reason: Optional[SubagentDenyReason] = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "parent_task_id": self.parent_task_id,
            "parent_session_id": self.parent_session_id,
            "root_task_id": self.root_task_id,
            "scope": self.scope.value,
            "depth": self.depth,
            "request": self.request.to_dict(),
            "execution_mode": self.execution_mode.value,
            "status": self.status.value,
            "result": self.result.to_dict() if self.result else None,
            "error": self.error.to_dict() if self.error else None,
            "deny_reason": self.deny_reason.value if self.deny_reason else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubagentRun":
        return cls(
            run_id=data.get("run_id", f"subagent_{uuid4().hex[:12]}"),
            parent_task_id=str(data.get("parent_task_id", "")),
            parent_session_id=str(data.get("parent_session_id", "")),
            root_task_id=str(data.get("root_task_id", "")),
            scope=SubagentScope(data["scope"]),
            depth=int(data.get("depth", 1)),
            request=SubagentSpawnRequest.from_dict(data["request"]),
            execution_mode=ExecutionMode(data.get("execution_mode", ExecutionMode.SERIAL.value)),
            status=SubagentRunStatus(data.get("status", SubagentRunStatus.CREATED.value)),
            result=SubagentResult.from_dict(data["result"]) if isinstance(data.get("result"), dict) else None,
            error=DomainError.from_dict(data["error"]) if isinstance(data.get("error"), dict) else None,
            deny_reason=SubagentDenyReason(data["deny_reason"]) if data.get("deny_reason") else None,
            created_at=data.get("created_at", utc_now_iso()),
            updated_at=data.get("updated_at", utc_now_iso()),
        )

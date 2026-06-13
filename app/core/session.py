"""Evoloop 3.1 AgentSession domain contracts.

AgentSession is the bounded reasoning unit inside a single Playbook agent step.
It records observable turns, agenda items, and runtime observations instead of
private chain-of-thought, so the session can be audited without leaking
untrusted or internal reasoning text.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.errors import DomainError
from app.core.events import utc_now_iso
from app.core.subagent import SubagentRun


class AgentSessionStatus(str, Enum):
    """Lifecycle state for a bounded AgentSession."""

    CREATED = "created"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentTurn:
    """One observable model turn inside an AgentSession."""

    iteration: int
    role: str
    prompt_summary: str
    response_summary: str = ""
    raw_content: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "role": self.role,
            "prompt_summary": self.prompt_summary,
            "response_summary": self.response_summary,
            "raw_content": self.raw_content,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


@dataclass
class AgendaItem:
    """A bounded internal work item used only inside the current AgentSession."""

    title: str
    rationale: str
    priority: str = "medium"
    status: str = "pending"
    note: str = ""
    item_id: str = field(default_factory=lambda: f"agenda_{uuid4().hex[:10]}")
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def update(self, *, status: Optional[str] = None, note: Optional[str] = None) -> None:
        if status:
            self.status = status
        if note is not None:
            self.note = note
        self.updated_at = utc_now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "rationale": self.rationale,
            "priority": self.priority,
            "status": self.status,
            "note": self.note,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class AgentObservation:
    """A schema/tool/runtime observation recorded for auditability."""

    kind: str
    summary: str
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "summary": self.summary,
            "data": dict(self.data),
            "created_at": self.created_at,
        }


@dataclass
class AgentSessionState:
    """Mutable runtime state for a single AgentSession."""

    status: AgentSessionStatus = AgentSessionStatus.CREATED
    iteration: int = 0
    turns: List[AgentTurn] = field(default_factory=list)
    observations: List[AgentObservation] = field(default_factory=list)
    agenda_items: List[AgendaItem] = field(default_factory=list)
    helper_runs: List[SubagentRun] = field(default_factory=list)
    tool_call_count: int = 0
    schema_errors: List[str] = field(default_factory=list)
    final_output_summary: str = ""
    degradation_reason: str = ""
    updated_at: str = field(default_factory=utc_now_iso)
    last_error: Optional[DomainError] = None

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "iteration": self.iteration,
            "turns": [turn.to_dict() for turn in self.turns],
            "observations": [observation.to_dict() for observation in self.observations],
            "agenda_items": [item.to_dict() for item in self.agenda_items],
            "helper_runs": [run.to_dict() for run in self.helper_runs],
            "tool_call_count": self.tool_call_count,
            "schema_errors": list(self.schema_errors),
            "final_output_summary": self.final_output_summary,
            "degradation_reason": self.degradation_reason,
            "updated_at": self.updated_at,
            "last_error": self.last_error.to_dict() if self.last_error else None,
        }


@dataclass
class AgentSession:
    """Bounded reasoning session for one workflow agent step."""

    task_id: str
    step_id: str
    agent_role: str
    goal: str
    input_context: Dict[str, Any] = field(default_factory=dict)
    max_iterations: int = 4
    allowed_tools: List[str] = field(default_factory=list)
    output_schema_keys: List[str] = field(default_factory=list)
    context_budget: Dict[str, Any] = field(default_factory=dict)
    final_output: Dict[str, Any] = field(default_factory=dict)
    session_id: str = field(default_factory=lambda: f"session_{uuid4().hex[:12]}")
    state: AgentSessionState = field(default_factory=AgentSessionState)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def touch(self) -> None:
        now = utc_now_iso()
        self.updated_at = now
        self.state.updated_at = now

    def set_runtime_contract(
        self,
        allowed_tools: Optional[List[str]] = None,
        output_schema_keys: Optional[List[str]] = None,
        context_budget: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.allowed_tools = list(allowed_tools or [])
        self.output_schema_keys = list(output_schema_keys or [])
        self.context_budget = dict(context_budget or {})
        self.touch()

    def add_agenda_item(self, *, title: str, rationale: str, priority: str = "medium") -> AgendaItem:
        item = AgendaItem(title=title, rationale=rationale, priority=priority)
        self.state.agenda_items.append(item)
        self.touch()
        return item

    def update_agenda_item(self, item_id: str, *, status: Optional[str] = None, note: Optional[str] = None) -> Optional[AgendaItem]:
        for item in self.state.agenda_items:
            if item.item_id == item_id:
                item.update(status=status, note=note)
                self.touch()
                return item
        return None

    def record_turn(self, turn: AgentTurn) -> None:
        self.state.turns.append(turn)
        self.state.iteration = max(self.state.iteration, turn.iteration)
        self.touch()

    def record_observation(self, observation: AgentObservation) -> None:
        self.state.observations.append(observation)
        self.touch()

    def record_schema_error(self, message: str) -> None:
        self.state.schema_errors.append(message)
        self.state.degradation_reason = message
        self.touch()

    def set_final_output(self, structured: Dict[str, Any], *, summary: str = "") -> None:
        self.final_output = dict(structured)
        self.state.final_output_summary = summary
        self.touch()

    def set_degradation_reason(self, reason: str) -> None:
        self.state.degradation_reason = reason
        self.touch()

    def record_helper_result(self, run: SubagentRun) -> None:
        for index, existing in enumerate(self.state.helper_runs):
            if existing.run_id == run.run_id:
                self.state.helper_runs[index] = run
                self.touch()
                return
        self.state.helper_runs.append(run)
        self.touch()

    def spawn_helper(self, service: Any, **kwargs: Any) -> SubagentRun:
        return service.run_helper(parent_session=self, **kwargs)

    def to_trace(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "agent_role": self.agent_role,
            "goal": self.goal,
            "max_iterations": self.max_iterations,
            "allowed_tools": list(self.allowed_tools),
            "output_schema_keys": list(self.output_schema_keys),
            "context_budget": dict(self.context_budget),
            "final_output": dict(self.final_output),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "state": self.state.to_dict(),
        }


@dataclass
class AgentRunResult:
    """Result returned by AgentRuntime to workflow executors."""

    session: AgentSession
    status: AgentSessionStatus
    content: str = ""
    structured: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    used_tools: List[str] = field(default_factory=list)
    schema_errors: List[str] = field(default_factory=list)
    iterations: int = 0
    error: Optional[DomainError] = None
    degraded: bool = False

    @classmethod
    def succeeded(
        cls,
        session: AgentSession,
        content: str,
        structured: Dict[str, Any],
        summary: str = "",
        used_tools: Optional[List[str]] = None,
        schema_errors: Optional[List[str]] = None,
    ) -> "AgentRunResult":
        session.state.status = AgentSessionStatus.SUCCEEDED
        return cls(
            session=session,
            status=AgentSessionStatus.SUCCEEDED,
            content=content,
            structured=structured,
            summary=summary,
            used_tools=list(used_tools or []),
            schema_errors=list(schema_errors or []),
            iterations=session.state.iteration,
            degraded=False,
        )

    @classmethod
    def blocked(
        cls,
        session: AgentSession,
        content: str,
        error: DomainError,
        structured: Optional[Dict[str, Any]] = None,
        summary: str = "",
        used_tools: Optional[List[str]] = None,
        schema_errors: Optional[List[str]] = None,
    ) -> "AgentRunResult":
        session.state.status = AgentSessionStatus.BLOCKED
        session.state.last_error = error
        data = dict(structured or {})
        data["degraded"] = True
        return cls(
            session=session,
            status=AgentSessionStatus.BLOCKED,
            content=content,
            structured=data,
            summary=summary,
            used_tools=list(used_tools or []),
            schema_errors=list(schema_errors or []),
            iterations=session.state.iteration,
            error=error,
            degraded=True,
        )

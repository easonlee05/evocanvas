"""Internal subagent orchestration service.

This service is the single execution primitive for EvoCanvas internal subagents.
It supports session-local helpers and control-plane-managed formal subtasks
through a shared contract while enforcing strict budgeting and permission gates.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Any, Dict, List, Optional

from app.core.context import TaskContext
from app.core.errors import DomainError
from app.core.events import Event
from app.core.session import AgentSession
from app.core.subagent import (
    ExecutionMode,
    SubagentBudget,
    SubagentDenyReason,
    SubagentResult,
    SubagentRun,
    SubagentRunStatus,
    SubagentScope,
    SubagentSpawnRequest,
)
from app.core.task import TaskDefinition, WorkflowSpec
from app.core.tools import ToolPolicy, ToolPolicyRule
from app.services.agent_runtime.runtime import AgentRuntime


class SubagentService:
    """Runs bounded internal subagents under tight governance."""

    READ_ONLY_TOOLS = {
        "material.read",
        "material.parse",
        "knowledge.retrieve",
        "artifact.read",
        "format.validate",
    }
    MAX_HELPER_DEPTH = 2
    MAX_PARALLEL_HELPERS = 2
    MAX_FORMAL_SUBTASKS = 3
    MAX_CONTEXT_SHARE = 0.25

    def __init__(self, llm: Any, tool_service: Any = None, storage: Any = None):
        self.llm = llm
        self.tool_service = tool_service
        self.storage = storage or getattr(tool_service, "storage", None)

    def run_helper(
        self,
        *,
        parent_session: AgentSession,
        request: SubagentSpawnRequest,
        task_definition: TaskDefinition,
        task_context: TaskContext,
        execution_mode: ExecutionMode = ExecutionMode.SERIAL,
    ) -> SubagentRun:
        """Execute one session-level helper request."""
        run = self._create_run(parent_session, request, execution_mode)
        self._emit_event(task_context.task_id, "subagent.run.created", run)
        denied = self._validate_helper_request(parent_session, request)
        if denied:
            run.status = SubagentRunStatus.DENIED
            run.deny_reason = denied
            run.result = SubagentResult(
                summary=f"Helper denied: {denied.value}",
                structured_output={},
                evidence_refs=[],
                used_tools=[],
                confidence="low",
                degraded=True,
                degradation_reason=denied.value,
            )
            run.touch()
            parent_session.record_helper_result(run)
            self._emit_event(task_context.task_id, "subagent.run.denied", run, {"degradation_reason": denied.value})
            return run

        run.status = SubagentRunStatus.RUNNING
        run.touch()
        self._emit_event(task_context.task_id, "subagent.run.started", run)

        helper_definition = self._build_helper_definition(task_definition, request)
        helper_runtime = AgentRuntime(llm=self.llm, tool_service=self.tool_service)
        helper_session = AgentSession(
            task_id=parent_session.task_id,
            step_id=f"{parent_session.step_id}__helper",
            agent_role=f"{parent_session.agent_role}Helper",
            goal=request.goal,
            input_context={
                "task_slice": request.task_slice,
                "input_refs": request.input_refs,
                "input_excerpt": request.input_excerpt,
                "parent_session_id": parent_session.session_id,
            },
            max_iterations=request.budget.max_iterations,
        )
        prompt = self._build_helper_prompt(request)
        run_result = helper_runtime.run_json_session(
            session=helper_session,
            prompt=prompt,
            context={
                "task_slice": request.task_slice,
                "input_excerpt": request.input_excerpt,
            },
            required_keys=list(request.output_schema.keys()),
            task_definition=helper_definition,
            task_context=task_context,
        )

        confidence = str(run_result.structured.get("confidence") or ("low" if run_result.degraded else "medium"))
        run.result = SubagentResult(
            summary=str(run_result.structured.get("summary") or run_result.summary or helper_session.state.final_output_summary),
            structured_output=run_result.structured,
            evidence_refs=list(run_result.structured.get("evidence_refs", [])),
            used_tools=list(run_result.used_tools),
            confidence=confidence,
            degraded=run_result.degraded,
            degradation_reason=run_result.error.message if run_result.error else run_result.structured.get("degradation_reason", ""),
        )
        run.error = run_result.error
        if run_result.status.value == "succeeded":
            run.status = SubagentRunStatus.SUCCEEDED
            self._emit_event(task_context.task_id, "subagent.run.completed", run, {"used_tools": run_result.used_tools})
        elif run_result.status.value == "blocked":
            run.status = SubagentRunStatus.BLOCKED
            self._emit_event(
                task_context.task_id,
                "subagent.run.blocked",
                run,
                {"degradation_reason": run.result.degradation_reason, "used_tools": run_result.used_tools},
            )
        else:
            run.status = SubagentRunStatus.FAILED
            self._emit_event(task_context.task_id, "subagent.run.failed", run)
        run.touch()
        parent_session.record_helper_result(run)
        return run

    def run_helpers(
        self,
        *,
        parent_session: AgentSession,
        requests: List[SubagentSpawnRequest],
        task_definition: TaskDefinition,
        task_context: TaskContext,
    ) -> List[SubagentRun]:
        """Execute one or more session-level helpers with bounded parallelism."""
        mode = self.decide_helper_execution_mode(parent_session, requests)
        if mode == ExecutionMode.PARALLEL_HELPERS:
            with ThreadPoolExecutor(max_workers=min(len(requests), self.MAX_PARALLEL_HELPERS)) as executor:
                futures = [
                    executor.submit(
                        self.run_helper,
                        parent_session=parent_session,
                        request=request,
                        task_definition=task_definition,
                        task_context=task_context,
                        execution_mode=mode,
                    )
                    for request in requests
                ]
                runs = [future.result() for future in futures]
        else:
            runs = [
                self.run_helper(
                    parent_session=parent_session,
                    request=request,
                    task_definition=task_definition,
                    task_context=task_context,
                    execution_mode=mode,
                )
                for request in requests
            ]

        return runs

    def decide_helper_execution_mode(self, parent_session: AgentSession, requests: List[SubagentSpawnRequest]) -> ExecutionMode:
        """Choose serial vs bounded parallel helper execution."""
        if len(requests) <= 1:
            return ExecutionMode.SERIAL
        if len(requests) > self.MAX_PARALLEL_HELPERS:
            return ExecutionMode.SERIAL
        if parent_session.state.helper_runs and len(parent_session.state.helper_runs) + len(requests) > self.MAX_PARALLEL_HELPERS:
            return ExecutionMode.SERIAL
        for request in requests:
            if request.scope != SubagentScope.SESSION_HELPER:
                return ExecutionMode.SERIAL
            if request.depth >= self.MAX_HELPER_DEPTH:
                return ExecutionMode.SERIAL
            if not request.output_schema:
                return ExecutionMode.SERIAL
            if self._estimate_token_count(request.input_excerpt) > request.budget.max_input_tokens:
                return ExecutionMode.SERIAL
        return ExecutionMode.PARALLEL_HELPERS

    def _create_run(
        self,
        parent_session: AgentSession,
        request: SubagentSpawnRequest,
        execution_mode: ExecutionMode,
    ) -> SubagentRun:
        return SubagentRun(
            parent_task_id=parent_session.task_id,
            parent_session_id=parent_session.session_id,
            root_task_id=parent_session.task_id,
            scope=request.scope,
            depth=request.depth,
            request=request,
            execution_mode=execution_mode,
        )

    def _validate_helper_request(
        self,
        parent_session: AgentSession,
        request: SubagentSpawnRequest,
    ) -> Optional[SubagentDenyReason]:
        if request.scope != SubagentScope.SESSION_HELPER:
            return SubagentDenyReason.SCOPE_NOT_ALLOWED
        if request.depth >= self.MAX_HELPER_DEPTH:
            return SubagentDenyReason.DEPTH_EXCEEDED
        if request.budget.spawn_fanout_remaining < 1:
            return SubagentDenyReason.FANOUT_EXCEEDED
        if len(parent_session.state.helper_runs) >= self.MAX_PARALLEL_HELPERS:
            return SubagentDenyReason.FANOUT_EXCEEDED
        if any(tool_name not in self.READ_ONLY_TOOLS for tool_name in request.allowed_tools):
            return SubagentDenyReason.PERMISSION_DENIED
        estimated_input_tokens = self._estimate_token_count(request.input_excerpt)
        if estimated_input_tokens > request.budget.max_input_tokens:
            return SubagentDenyReason.BUDGET_EXCEEDED
        parent_budget = int(parent_session.context_budget.get("estimated_tokens", max(estimated_input_tokens * 4, 1)))
        if parent_budget > 0 and estimated_input_tokens > max(1, int(parent_budget * self.MAX_CONTEXT_SHARE)):
            return SubagentDenyReason.BUDGET_EXCEEDED
        return None

    def _build_helper_definition(self, parent_definition: TaskDefinition, request: SubagentSpawnRequest) -> TaskDefinition:
        definition = deepcopy(parent_definition)
        definition.workflow = WorkflowSpec(name=parent_definition.workflow.name, version=parent_definition.workflow.version, steps=[])
        definition.tool_policy = ToolPolicy(
            task_type=parent_definition.type,
            rules=[
                ToolPolicyRule(
                    role="*",
                    step_id="*",
                    allowed_tools=list(request.allowed_tools),
                )
            ],
        )
        return definition

    def _build_helper_prompt(self, request: SubagentSpawnRequest) -> str:
        schema_keys = ", ".join(request.output_schema.keys())
        return (
            "SESSION HELPER\n"
            "You are a bounded internal reasoning helper for EvoCanvas.\n"
            "Work only on the provided task slice. Use read-only tools only when necessary.\n"
            "Return raw JSON only.\n\n"
            f"Goal: {request.goal}\n"
            f"Task Slice: {request.task_slice}\n"
            f"Input Refs: {', '.join(request.input_refs)}\n"
            f"Output Schema Keys: {schema_keys}\n"
            f"Input Excerpt: {json.dumps(request.input_excerpt, ensure_ascii=False)}"
        )

    @staticmethod
    def _estimate_token_count(payload: Dict[str, Any]) -> int:
        try:
            text = json.dumps(payload, ensure_ascii=False)
        except TypeError:
            text = str(payload)
        return max(1, len(text) // 4)

    def _emit_event(self, task_id: str, event_type: str, run: SubagentRun, extra_payload: Optional[Dict[str, Any]] = None) -> None:
        if not self.storage:
            return
        payload = {
            "scope": run.scope.value,
            "run_id": run.run_id,
            "parent_task_id": run.parent_task_id,
            "parent_session_id": run.parent_session_id,
            "root_task_id": run.root_task_id,
            "depth": run.depth,
            "execution_mode": run.execution_mode.value,
            "budget": run.request.budget.to_dict(),
            "used_tools": run.result.used_tools if run.result else [],
            "degradation_reason": run.result.degradation_reason if run.result else "",
        }
        if extra_payload:
            payload.update(extra_payload)
        self.storage.append_event(Event(task_id=task_id, type=event_type, status=run.status.value, payload=payload))

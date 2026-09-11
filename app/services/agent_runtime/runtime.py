"""Bounded AgentSession runtime for EvoCanvas.

The runtime keeps Playbook topology deterministic while turning a single
workflow agent step into an auditable bounded session with agenda recording,
tool-use accounting, schema recovery, and explicit degraded outcomes.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.core.errors import DomainError
from app.core.session import AgentObservation, AgentRunResult, AgentSession, AgentSessionStatus, AgentTurn
from app.core.task import TaskDefinition
from app.core.context import TaskContext
from app.core.tools import ToolCall


def extract_json_from_text(text: str) -> str:
    """Extract the most likely JSON object from model text."""
    if not text:
        return "{}"
    match = re.search(r"```(?:json|JSON)?(.*?)```", text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        content = re.sub(r",\s*}", "}", content)
        content = re.sub(r",\s*]", "]", content)
        return content
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text.strip()


class AgentRuntime:
    """Runs a bounded AgentSession through the existing LLM port.

    The public entrypoint remains ``run_json_session()`` for workflow
    compatibility, but the internals now manage a real bounded session loop
    with agenda items, tool observations, and schema recovery state.
    """

    MAX_AGENDA_ITEMS = 12

    def __init__(self, llm: Any, tool_service: Any = None):
        self.llm = llm
        self.tool_service = tool_service

    def run_json_session(
        self,
        *,
        session: AgentSession,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        required_keys: Optional[Iterable[str]] = None,
        task_definition: Optional[TaskDefinition] = None,
        task_context: Optional[TaskContext] = None,
    ) -> AgentRunResult:
        if not self.llm:
            error = DomainError(
                "agent_runtime.llm_unavailable",
                "AgentRuntime requires an LLM port for this session.",
                {"session_id": session.session_id, "step_id": session.step_id},
            )
            session.set_degradation_reason(error.message)
            return AgentRunResult.blocked(
                session=session,
                content="",
                error=error,
                structured={"fallback_reason": error.message},
                summary="AgentSession blocked before the runtime could start.",
            )

        session.state.status = AgentSessionStatus.RUNNING
        required = list(required_keys or [])
        last_error = ""
        last_content = ""
        tool_messages: List[Dict[str, Any]] = []
        used_tools: List[str] = []
        session.set_runtime_contract(
            self._allowed_tool_names_for_session(session, task_definition),
            required,
            {
                "input_context_keys": sorted((context or session.input_context).keys()),
                "max_iterations": session.max_iterations,
                "estimated_tokens": max(1, len(json.dumps(context or session.input_context, ensure_ascii=False, default=str)) // 4),
            },
        )

        for iteration in range(1, session.max_iterations + 1):
            current_prompt = prompt
            if iteration > 1 and last_error:
                current_prompt += (
                    "\n\n[SYSTEM ALERT]: Previous AgentSession turn failed schema validation: "
                    f"{last_error}. Return raw JSON only."
                )

            response = self._invoke_model(
                session=session,
                prompt=current_prompt,
                context=context or session.input_context,
                task_definition=task_definition,
                tool_messages=tool_messages,
            )
            raw_content, structured_response = self._normalize_llm_response(response)
            last_content = raw_content
            session.record_turn(
                AgentTurn(
                    iteration=iteration,
                    role=session.agent_role,
                    prompt_summary=current_prompt[:160],
                    response_summary=raw_content[:160],
                    raw_content=raw_content,
                )
            )

            try:
                structured = structured_response or json.loads(extract_json_from_text(raw_content))
                self._apply_agenda_operations(session, structured)
                tool_calls = self._extract_tool_calls(structured)
                if isinstance(tool_calls, list) and tool_calls:
                    tool_error, tool_messages, newly_used_tools = self._execute_tool_calls(
                        session=session,
                        tool_calls=tool_calls,
                        task_definition=task_definition,
                        task_context=task_context,
                    )
                    for tool_name in newly_used_tools:
                        if tool_name not in used_tools:
                            used_tools.append(tool_name)
                    if tool_error:
                        session.set_degradation_reason(tool_error.message)
                        return AgentRunResult.blocked(
                            session=session,
                            content=raw_content,
                            error=tool_error,
                            structured={"fallback_reason": tool_error.message, "fallback_role": session.agent_role},
                            summary="AgentSession blocked during controlled tool execution.",
                            used_tools=used_tools,
                            schema_errors=session.state.schema_errors,
                        )
                    continue

                missing = [key for key in required if key not in structured or structured.get(key) in (None, "")]
                if missing:
                    raise ValueError(f"missing required keys: {', '.join(missing)}")
                session.record_observation(AgentObservation(kind="schema", summary="valid json", data={"required_keys": required}))
                session.set_final_output(structured, summary=self._summarize_structured_output(structured))
                return AgentRunResult.succeeded(
                    session=session,
                    content=raw_content,
                    structured=structured,
                    summary="AgentSession completed with schema-valid output.",
                    used_tools=used_tools,
                    schema_errors=session.state.schema_errors,
                )
            except Exception as exc:
                last_error = str(exc)
                session.record_schema_error(last_error)
                session.record_observation(
                    AgentObservation(
                        kind="schema_error",
                        summary=last_error,
                        data={"iteration": iteration, "required_keys": required},
                    )
                )

        error = DomainError(
            "agent_runtime.schema_validation_failed",
            "AgentSession exhausted bounded JSON validation attempts.",
            {"session_id": session.session_id, "step_id": session.step_id, "last_error": last_error},
        )
        session.set_degradation_reason(last_error)
        return AgentRunResult.blocked(
            session=session,
            content=last_content,
            error=error,
            structured={"fallback_reason": last_error, "fallback_role": session.agent_role},
            summary="AgentSession exhausted bounded schema recovery attempts.",
            used_tools=used_tools,
            schema_errors=session.state.schema_errors,
        )

    def _invoke_model(
        self,
        *,
        session: AgentSession,
        prompt: str,
        context: Dict[str, Any],
        task_definition: Optional[TaskDefinition],
        tool_messages: List[Dict[str, Any]],
    ) -> Any:
        invoke_with_tools = getattr(self.llm, "invoke_with_tools", None)
        if callable(invoke_with_tools):
            return invoke_with_tools(
                session.agent_role,
                prompt,
                context,
                self._provider_tools_for_session(session, task_definition),
                tool_messages=tool_messages,
            )
        return self.llm.invoke(session.agent_role, prompt, context)

    @staticmethod
    def _normalize_llm_response(response: Any) -> tuple[str, Dict[str, Any]]:
        if isinstance(response, dict):
            return str(response.get("content") or ""), response.get("structured") if isinstance(response.get("structured"), dict) else response

        content = str(getattr(response, "content", "") or "")
        structured = getattr(response, "structured", {})
        return content, structured if isinstance(structured, dict) else {}

    @staticmethod
    def _extract_tool_calls(structured: Dict[str, Any]) -> Any:
        if not isinstance(structured, dict):
            return None
        if isinstance(structured.get("tool_calls"), list):
            return structured.get("tool_calls")
        message = structured.get("message")
        if isinstance(message, dict) and isinstance(message.get("tool_calls"), list):
            return message.get("tool_calls")
        return None

    def _provider_tools_for_session(self, session: AgentSession, task_definition: Optional[TaskDefinition]) -> List[Dict[str, Any]]:
        if not self.tool_service or not task_definition:
            return []

        tools: List[Dict[str, Any]] = []
        for tool_name, spec in getattr(self.tool_service, "specs", {}).items():
            if not task_definition.tool_policy.is_allowed(session.agent_role, session.step_id, tool_name):
                continue
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": self._provider_tool_name(tool_name),
                        "description": spec.description,
                        "parameters": spec.input_schema or {"type": "object", "additionalProperties": True},
                    },
                }
            )
        return tools

    def _allowed_tool_names_for_session(self, session: AgentSession, task_definition: Optional[TaskDefinition]) -> List[str]:
        provider_tools = self._provider_tools_for_session(session, task_definition)
        tool_names: List[str] = []
        for tool in provider_tools:
            function = tool.get("function", {})
            canonical_name = self._canonical_tool_name(str(function.get("name") or ""))
            if canonical_name and canonical_name not in tool_names:
                tool_names.append(canonical_name)
        return tool_names

    def _apply_agenda_operations(self, session: AgentSession, structured: Dict[str, Any]) -> None:
        if not isinstance(structured, dict):
            return

        for item in structured.get("agenda_add", []) or []:
            if not isinstance(item, dict):
                continue
            if len(session.state.agenda_items) >= self.MAX_AGENDA_ITEMS:
                session.record_observation(
                    AgentObservation(
                        kind="agenda",
                        summary="agenda limit reached",
                        data={"max_items": self.MAX_AGENDA_ITEMS, "ignored_title": item.get("title", "")},
                    )
                )
                continue
            title = str(item.get("title") or "").strip()
            rationale = str(item.get("rationale") or "").strip()
            if not title or not rationale:
                continue
            agenda_item = session.add_agenda_item(
                title=title,
                rationale=rationale,
                priority=str(item.get("priority") or "medium"),
            )
            session.record_observation(
                AgentObservation(
                    kind="agenda",
                    summary=f"agenda item added: {agenda_item.title}",
                    data={"item_id": agenda_item.item_id, "title": agenda_item.title, "priority": agenda_item.priority},
                )
            )

        for item in structured.get("agenda_update", []) or []:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("item_id") or "").strip()
            if not item_id:
                continue
            updated = session.update_agenda_item(
                item_id,
                status=str(item.get("status") or "") or None,
                note=item.get("note"),
            )
            if updated:
                session.record_observation(
                    AgentObservation(
                        kind="agenda",
                        summary=f"agenda item updated: {updated.title}",
                        data={"item_id": updated.item_id, "status": updated.status, "note": updated.note},
                    )
                )

    def _execute_tool_calls(
        self,
        *,
        session: AgentSession,
        tool_calls: List[Dict[str, Any]],
        task_definition: Optional[TaskDefinition],
        task_context: Optional[TaskContext],
    ) -> Tuple[Optional[DomainError], List[Dict[str, Any]], List[str]]:
        if not self.tool_service or not task_definition or not task_context:
            error = DomainError(
                "agent_runtime.tool_bridge_unavailable",
                "AgentRuntime received tool_calls but no ToolService bridge context was provided.",
                {"session_id": session.session_id, "step_id": session.step_id},
            )
            session.record_observation(AgentObservation(kind="tool", summary=error.message, data={"status": "failed"}))
            return error, [], []

        tool_messages: List[Dict[str, Any]] = []
        used_tools: List[str] = []
        for index, requested in enumerate(tool_calls):
            normalized = self._normalize_tool_call(requested)
            provider_tool_call_id = normalized.get("provider_tool_call_id")
            tool_name = normalized["tool_name"]
            arguments = normalized["arguments"]
            call = ToolCall(
                task_id=session.task_id,
                step_id=session.step_id,
                agent_role=session.agent_role,
                tool_name=tool_name,
                arguments=arguments,
            )
            result = self.tool_service.invoke(task_definition, task_context, call)
            session.record_observation(
                AgentObservation(
                    kind="tool",
                    summary=result.summary or (result.error.message if result.error else "tool call completed"),
                    data={
                        "index": index,
                        "tool_call_id": call.id,
                        "provider_tool_call_id": provider_tool_call_id,
                        "tool_name": tool_name,
                        "status": result.status,
                        "data": result.data,
                        "error": result.error.to_dict() if result.error else None,
                    },
                )
            )
            session.state.tool_call_count += 1
            session.touch()
            if tool_name not in used_tools:
                used_tools.append(tool_name)
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": provider_tool_call_id or call.id,
                    "name": tool_name,
                    "content": json.dumps(
                        {
                            "status": result.status,
                            "summary": result.summary,
                            "data": result.data,
                            "error": result.error.to_dict() if result.error else None,
                        },
                        ensure_ascii=False,
                    ),
                }
            )
            if result.status == "denied":
                return DomainError(
                    "agent_runtime.tool_call_denied",
                    f"Tool call denied by ToolPolicy: {tool_name}",
                    {"session_id": session.session_id, "step_id": session.step_id, "tool_name": tool_name},
                ), tool_messages, used_tools
            if result.status != "succeeded":
                return DomainError(
                    "agent_runtime.tool_call_failed",
                    f"Tool call failed: {tool_name}",
                    {"session_id": session.session_id, "step_id": session.step_id, "tool_name": tool_name},
                ), tool_messages, used_tools
        return None, tool_messages, used_tools

    @staticmethod
    def _summarize_structured_output(structured: Dict[str, Any]) -> str:
        if not structured:
            return ""
        keys = sorted(str(key) for key in structured.keys())
        return ", ".join(keys[:5])

    @staticmethod
    def _normalize_tool_call(requested: Dict[str, Any]) -> Dict[str, Any]:
        provider_tool_call_id = requested.get("id") or requested.get("tool_call_id")
        if isinstance(requested.get("function"), dict):
            function = requested["function"]
            tool_name = AgentRuntime._canonical_tool_name(str(function.get("name") or ""))
            raw_arguments = function.get("arguments", {})
        else:
            tool_name = AgentRuntime._canonical_tool_name(str(requested.get("tool_name") or requested.get("name") or ""))
            raw_arguments = requested.get("arguments", {})

        if isinstance(raw_arguments, str):
            try:
                arguments = json.loads(raw_arguments) if raw_arguments.strip() else {}
            except json.JSONDecodeError:
                arguments = {}
        elif isinstance(raw_arguments, dict):
            arguments = raw_arguments
        else:
            arguments = {}

        return {"provider_tool_call_id": provider_tool_call_id, "tool_name": tool_name, "arguments": arguments}

    @staticmethod
    def _provider_tool_name(tool_name: str) -> str:
        return tool_name.replace(".", "__")

    @staticmethod
    def _canonical_tool_name(tool_name: str) -> str:
        return tool_name.replace("__", ".")

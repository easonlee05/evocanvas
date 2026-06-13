import unittest

from app.core.ports import LLMResult


def make_tool_runtime_context():
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from app.core.context import TaskContext
    from app.core.task import TaskDefinition, WorkflowSpec
    from app.services.fakes import FakeKnowledge, FakeStorage
    from app.services.tool_service import ToolService
    from app.workflows.policies import build_default_tool_policy

    temp = TemporaryDirectory()
    storage = FakeStorage(Path(temp.name))
    context = TaskContext(
        task_id="task_tool",
        task_type="spec_to_agent",
        username="alice",
        title="Tool Test",
        goal="Use tool",
    )
    definition = TaskDefinition(
        type="spec_to_agent",
        display_name="Spec To Agent",
        input_schema={},
        workflow=WorkflowSpec(name="x", version="1", steps=[]),
        tool_policy=build_default_tool_policy("spec_to_agent"),
    )
    tool_service = ToolService.default(root=storage, knowledge=FakeKnowledge())
    return temp, definition, context, tool_service


class AgentSessionContractTests(unittest.TestCase):
    def test_agent_session_defaults_and_trace_append(self):
        from app.core.session import AgentSession, AgentObservation, AgentSessionStatus

        session = AgentSession(
            task_id="task_1",
            step_id="machine_spec_compiler",
            agent_role="Compiler",
            goal="compile machine spec",
            input_context={"intent": "Auth flow"},
            max_iterations=2,
        )

        self.assertTrue(session.session_id.startswith("session_"))
        self.assertEqual(session.state.status, AgentSessionStatus.CREATED)
        self.assertEqual(session.state.iteration, 0)
        self.assertEqual(session.max_iterations, 2)

        session.set_runtime_contract(["knowledge.retrieve"], ["primary_requirement"])
        agenda_item = session.add_agenda_item(
            title="Inspect ambiguity",
            rationale="Need an internal worklist before producing JSON",
            priority="high",
        )
        session.update_agenda_item(agenda_item.item_id, status="done", note="Completed")

        session.record_observation(AgentObservation(kind="schema", summary="valid json", data={"ok": True}))
        trace = session.to_trace()

        self.assertEqual(len(session.state.observations), 1)
        self.assertEqual(session.state.observations[0].kind, "schema")
        self.assertEqual(trace["allowed_tools"], ["knowledge.retrieve"])
        self.assertEqual(trace["output_schema_keys"], ["primary_requirement"])
        self.assertEqual(trace["state"]["agenda_items"][0]["title"], "Inspect ambiguity")
        self.assertEqual(trace["state"]["agenda_items"][0]["status"], "done")
        self.assertIn("updated_at", trace)

    def test_agent_session_records_helper_runs(self):
        from app.core.session import AgentSession
        from app.core.subagent import (
            ExecutionMode,
            SubagentBudget,
            SubagentResult,
            SubagentRun,
            SubagentRunStatus,
            SubagentScope,
            SubagentSpawnRequest,
        )

        session = AgentSession(task_id="task_1", step_id="open_question_identifier", agent_role="Compiler", goal="find ambiguity")
        helper_run = SubagentRun(
            parent_task_id="task_1",
            parent_session_id=session.session_id,
            root_task_id="task_1",
            scope=SubagentScope.SESSION_HELPER,
            depth=1,
            request=SubagentSpawnRequest(
                scope=SubagentScope.SESSION_HELPER,
                goal="Inspect ambiguity",
                task_slice="Only inspect auth ambiguity",
                input_refs=["business_intent"],
                input_excerpt={"business_intent": "Build login"},
                allowed_tools=["knowledge.retrieve"],
                output_schema={"summary": "string"},
                budget=SubagentBudget(max_iterations=2, max_input_tokens=300, max_output_tokens=120, max_tool_calls=2, spawn_fanout_remaining=1),
            ),
            execution_mode=ExecutionMode.SERIAL,
            status=SubagentRunStatus.SUCCEEDED,
            result=SubagentResult(
                summary="Found one ambiguity",
                structured_output={"findings": ["SSO provider missing"]},
                evidence_refs=[],
                used_tools=[],
                confidence="medium",
            ),
        )

        session.record_helper_result(helper_run)
        trace = session.to_trace()

        self.assertEqual(len(trace["state"]["helper_runs"]), 1)
        self.assertEqual(trace["state"]["helper_runs"][0]["scope"], "session_helper")
        self.assertEqual(trace["state"]["helper_runs"][0]["result"]["summary"], "Found one ambiguity")

    def test_agent_run_result_helpers(self):
        from app.core.errors import DomainError
        from app.core.session import AgentRunResult, AgentSession, AgentSessionStatus

        session = AgentSession(task_id="task_1", step_id="x", agent_role="Compiler", goal="g")
        success = AgentRunResult.succeeded(
            session=session,
            content="ok",
            structured={"a": 1},
            summary="session succeeded",
            used_tools=["knowledge.retrieve"],
            schema_errors=[],
        )
        blocked = AgentRunResult.blocked(
            session=session,
            content="bad",
            error=DomainError("x", "blocked"),
            structured={"degraded": True},
            summary="session blocked",
            used_tools=["artifact.write"],
            schema_errors=["missing required key"],
        )

        self.assertEqual(success.status, AgentSessionStatus.SUCCEEDED)
        self.assertEqual(success.structured["a"], 1)
        self.assertEqual(success.summary, "session succeeded")
        self.assertEqual(success.used_tools, ["knowledge.retrieve"])
        self.assertEqual(blocked.status, AgentSessionStatus.BLOCKED)
        self.assertTrue(blocked.degraded)
        self.assertEqual(blocked.error.code, "x")
        self.assertEqual(blocked.schema_errors, ["missing required key"])
        self.assertEqual(blocked.iterations, session.state.iteration)


class AgentRuntimeTests(unittest.TestCase):
    def test_runtime_succeeds_with_valid_json_and_records_turn(self):
        from app.core.session import AgentSession, AgentSessionStatus
        from app.services.agent_runtime import AgentRuntime

        class JsonLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(content='{"primary_requirement":"Auth flow"}', structured={})

        session = AgentSession(task_id="task_1", step_id="machine_spec_compiler", agent_role="Compiler", goal="compile")
        result = AgentRuntime(llm=JsonLLM()).run_json_session(
            session=session,
            prompt="Return JSON",
            context={"intent": "Auth flow"},
            required_keys=["primary_requirement"],
        )

        self.assertEqual(result.status, AgentSessionStatus.SUCCEEDED)
        self.assertEqual(result.structured["primary_requirement"], "Auth flow")
        self.assertEqual(session.state.status, AgentSessionStatus.SUCCEEDED)
        self.assertEqual(session.state.iteration, 1)
        self.assertEqual(len(session.state.turns), 1)
        self.assertEqual(result.summary, "AgentSession completed with schema-valid output.")
        self.assertEqual(result.iterations, 1)
        self.assertEqual(session.state.final_output_summary, "primary_requirement")

    def test_runtime_blocks_after_invalid_json_retries(self):
        from app.core.session import AgentSession, AgentSessionStatus
        from app.services.agent_runtime import AgentRuntime

        class InvalidJsonLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(content="not json", structured={})

        session = AgentSession(
            task_id="task_1",
            step_id="machine_spec_compiler",
            agent_role="Compiler",
            goal="compile",
            max_iterations=2,
        )
        result = AgentRuntime(llm=InvalidJsonLLM()).run_json_session(
            session=session,
            prompt="Return JSON",
            context={"intent": "Auth flow"},
            required_keys=["primary_requirement"],
        )

        self.assertEqual(result.status, AgentSessionStatus.BLOCKED)
        self.assertTrue(result.degraded)
        self.assertEqual(result.error.code, "agent_runtime.schema_validation_failed")
        self.assertEqual(session.state.status, AgentSessionStatus.BLOCKED)
        self.assertEqual(session.state.iteration, 2)
        self.assertTrue(result.schema_errors)
        self.assertTrue(session.state.degradation_reason)

    def test_runtime_executes_allowed_tool_call_then_converges(self):
        from app.core.session import AgentSession, AgentSessionStatus
        from app.services.agent_runtime import AgentRuntime

        class ToolCallingLLM:
            def __init__(self):
                self.calls = 0

            def invoke(self, role, prompt, context):
                self.calls += 1
                if self.calls == 1:
                    return LLMResult(
                        content='{"tool_calls":[{"tool_name":"knowledge.retrieve","arguments":{"query":"auth"}}]}',
                        structured={},
                    )
                return LLMResult(content='{"primary_requirement":"Auth flow"}', structured={})

        temp, definition, context, tool_service = make_tool_runtime_context()
        self.addCleanup(temp.cleanup)
        session = AgentSession(
            task_id=context.task_id,
            step_id="machine_spec_compiler",
            agent_role="Compiler",
            goal="compile",
            max_iterations=3,
        )

        result = AgentRuntime(llm=ToolCallingLLM(), tool_service=tool_service).run_json_session(
            session=session,
            prompt="Return JSON",
            context={"intent": "Auth flow"},
            required_keys=["primary_requirement"],
            task_definition=definition,
            task_context=context,
        )

        self.assertEqual(result.status, AgentSessionStatus.SUCCEEDED)
        self.assertEqual(result.structured["primary_requirement"], "Auth flow")
        self.assertEqual(session.state.iteration, 2)
        self.assertEqual(session.state.observations[0].kind, "tool")
        self.assertEqual(session.state.observations[0].data["tool_name"], "knowledge.retrieve")
        self.assertEqual(session.state.observations[0].data["status"], "succeeded")
        self.assertEqual(result.used_tools, ["knowledge.retrieve"])
        self.assertEqual(session.state.tool_call_count, 1)

    def test_runtime_blocks_denied_tool_call(self):
        from app.core.session import AgentSession, AgentSessionStatus
        from app.services.agent_runtime import AgentRuntime

        class DeniedToolLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(
                    content='{"tool_calls":[{"tool_name":"artifact.write","arguments":{"name":"x.md","content":"bad"}}]}',
                    structured={},
                )

        temp, definition, context, tool_service = make_tool_runtime_context()
        self.addCleanup(temp.cleanup)
        session = AgentSession(
            task_id=context.task_id,
            step_id="machine_spec_compiler",
            agent_role="Compiler",
            goal="compile",
            max_iterations=2,
        )

        result = AgentRuntime(llm=DeniedToolLLM(), tool_service=tool_service).run_json_session(
            session=session,
            prompt="Return JSON",
            context={"intent": "Auth flow"},
            required_keys=["primary_requirement"],
            task_definition=definition,
            task_context=context,
        )

        self.assertEqual(result.status, AgentSessionStatus.BLOCKED)
        self.assertEqual(result.error.code, "agent_runtime.tool_call_denied")
        self.assertEqual(session.state.observations[0].kind, "tool")
        self.assertEqual(session.state.observations[0].data["status"], "denied")
        self.assertEqual(session.state.degradation_reason, "Tool call denied by ToolPolicy: artifact.write")

    def test_runtime_records_agenda_and_schema_errors_in_trace(self):
        from app.core.session import AgentSession, AgentSessionStatus
        from app.services.agent_runtime import AgentRuntime

        class AgendaLLM:
            def __init__(self):
                self.calls = 0

            def invoke(self, role, prompt, context):
                self.calls += 1
                if self.calls == 1:
                    return LLMResult(
                        content='{"agenda_add":[{"title":"Inspect ambiguity","rationale":"Need structure","priority":"high"}]}',
                        structured={},
                    )
                return LLMResult(content="not json", structured={})

        session = AgentSession(
            task_id="task_1",
            step_id="machine_spec_compiler",
            agent_role="Compiler",
            goal="compile",
            max_iterations=2,
        )
        result = AgentRuntime(llm=AgendaLLM()).run_json_session(
            session=session,
            prompt="Return JSON",
            context={"intent": "Auth flow"},
            required_keys=["primary_requirement"],
        )

        self.assertEqual(result.status, AgentSessionStatus.BLOCKED)
        self.assertTrue(session.state.agenda_items)
        self.assertEqual(session.state.agenda_items[0].title, "Inspect ambiguity")
        self.assertTrue(result.schema_errors)
        self.assertEqual(session.state.observations[0].kind, "agenda")
        self.assertEqual(session.state.observations[-1].kind, "schema_error")

    def test_runtime_uses_provider_native_tool_calling_when_available(self):
        from app.core.session import AgentSession, AgentSessionStatus
        from app.services.agent_runtime import AgentRuntime

        class NativeToolLLM:
            def __init__(self):
                self.calls = 0
                self.received_tools = []
                self.received_tool_messages = []

            def invoke_with_tools(self, role, prompt, context, tools, tool_messages=None):
                self.calls += 1
                self.received_tools.append(tools)
                self.received_tool_messages.append(tool_messages or [])
                if self.calls == 1:
                    return LLMResult(
                        content="",
                        structured={
                            "tool_calls": [
                                {
                                    "id": "call_native_1",
                                    "type": "function",
                                    "function": {
                                        "name": "knowledge.retrieve",
                                        "arguments": '{"query":"auth"}',
                                    },
                                }
                            ]
                        },
                    )
                return LLMResult(content='{"primary_requirement":"Auth flow"}', structured={})

        temp, definition, context, tool_service = make_tool_runtime_context()
        self.addCleanup(temp.cleanup)
        llm = NativeToolLLM()
        session = AgentSession(
            task_id=context.task_id,
            step_id="machine_spec_compiler",
            agent_role="Compiler",
            goal="compile",
            max_iterations=3,
        )

        result = AgentRuntime(llm=llm, tool_service=tool_service).run_json_session(
            session=session,
            prompt="Return JSON",
            context={"intent": "Auth flow"},
            required_keys=["primary_requirement"],
            task_definition=definition,
            task_context=context,
        )

        self.assertEqual(result.status, AgentSessionStatus.SUCCEEDED)
        self.assertEqual(result.structured["primary_requirement"], "Auth flow")
        self.assertEqual(llm.calls, 2)
        self.assertEqual(llm.received_tools[0][0]["function"]["name"], "material__read")
        tool_result_messages = [message for message in llm.received_tool_messages[1] if message.get("role") == "tool"]
        self.assertEqual(tool_result_messages[0]["tool_call_id"], "call_native_1")
        self.assertEqual(session.state.observations[0].data["provider_tool_call_id"], "call_native_1")


class SubagentServiceTests(unittest.TestCase):
    def test_helper_spawn_succeeds_and_records_trace(self):
        from app.core.session import AgentSession
        from app.core.subagent import SubagentBudget, SubagentScope, SubagentSpawnRequest
        from app.services.subagent_service import SubagentService

        class HelperLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(
                    content='{"summary":"Found auth ambiguity","findings":["SSO provider missing"],"confidence":"medium"}',
                    structured={},
                )

        temp, definition, context, tool_service = make_tool_runtime_context()
        self.addCleanup(temp.cleanup)
        parent_session = AgentSession(task_id=context.task_id, step_id="open_question_identifier", agent_role="Compiler", goal="find questions")
        request = SubagentSpawnRequest(
            scope=SubagentScope.SESSION_HELPER,
            goal="Inspect auth ambiguity",
            task_slice="Only inspect business intent and known constraints",
            input_refs=["business_intent"],
            input_excerpt={"business_intent": "Build login with SSO"},
            allowed_tools=["knowledge.retrieve"],
            output_schema={"summary": "string", "findings": "array", "confidence": "string"},
            budget=SubagentBudget(max_iterations=2, max_input_tokens=500, max_output_tokens=200, max_tool_calls=2, spawn_fanout_remaining=1),
        )

        run = SubagentService(llm=HelperLLM(), tool_service=tool_service).run_helper(
            parent_session=parent_session,
            request=request,
            task_definition=definition,
            task_context=context,
        )

        self.assertEqual(run.status.value, "succeeded")
        self.assertEqual(run.result.summary, "Found auth ambiguity")
        self.assertEqual(run.result.structured_output["findings"][0], "SSO provider missing")
        self.assertEqual(parent_session.state.helper_runs[0].run_id, run.run_id)

    def test_helper_write_tool_request_is_denied(self):
        from app.core.session import AgentSession
        from app.core.subagent import SubagentBudget, SubagentDenyReason, SubagentScope, SubagentSpawnRequest
        from app.services.subagent_service import SubagentService

        temp, definition, context, tool_service = make_tool_runtime_context()
        self.addCleanup(temp.cleanup)
        parent_session = AgentSession(task_id=context.task_id, step_id="machine_spec_compiler", agent_role="Compiler", goal="compile")
        request = SubagentSpawnRequest(
            scope=SubagentScope.SESSION_HELPER,
            goal="Write artifact",
            task_slice="Try to write a file",
            input_refs=["intent"],
            input_excerpt={"intent": "Auth"},
            allowed_tools=["artifact.write"],
            output_schema={"summary": "string"},
            budget=SubagentBudget(max_iterations=1, max_input_tokens=200, max_output_tokens=80, max_tool_calls=1, spawn_fanout_remaining=1),
        )

        run = SubagentService(llm=None, tool_service=tool_service).run_helper(
            parent_session=parent_session,
            request=request,
            task_definition=definition,
            task_context=context,
        )

        self.assertEqual(run.status.value, "denied")
        self.assertEqual(run.deny_reason, SubagentDenyReason.PERMISSION_DENIED)

    def test_helper_token_budget_gate_denies_large_excerpt(self):
        from app.core.session import AgentSession
        from app.core.subagent import SubagentBudget, SubagentDenyReason, SubagentScope, SubagentSpawnRequest
        from app.services.subagent_service import SubagentService

        temp, definition, context, tool_service = make_tool_runtime_context()
        self.addCleanup(temp.cleanup)
        parent_session = AgentSession(task_id=context.task_id, step_id="machine_spec_compiler", agent_role="Compiler", goal="compile")
        request = SubagentSpawnRequest(
            scope=SubagentScope.SESSION_HELPER,
            goal="Inspect ambiguity",
            task_slice="Huge excerpt",
            input_refs=["business_intent"],
            input_excerpt={"business_intent": "A" * 4000},
            allowed_tools=["knowledge.retrieve"],
            output_schema={"summary": "string"},
            budget=SubagentBudget(max_iterations=1, max_input_tokens=50, max_output_tokens=50, max_tool_calls=1, spawn_fanout_remaining=1),
        )

        run = SubagentService(llm=None, tool_service=tool_service).run_helper(
            parent_session=parent_session,
            request=request,
            task_definition=definition,
            task_context=context,
        )

        self.assertEqual(run.status.value, "denied")
        self.assertEqual(run.deny_reason, SubagentDenyReason.BUDGET_EXCEEDED)

    def test_parallel_helpers_join_results(self):
        from app.core.session import AgentSession
        from app.core.subagent import SubagentBudget, ExecutionMode, SubagentScope, SubagentSpawnRequest
        from app.services.subagent_service import SubagentService

        class ParallelLLM:
            def invoke(self, role, prompt, context):
                if "state machine" in prompt.lower():
                    return LLMResult(content='{"summary":"Modeled states","states":["issued","redeemed"],"confidence":"high"}', structured={})
                return LLMResult(content='{"summary":"Found edge cases","findings":["expired coupon"],"confidence":"medium"}', structured={})

        temp, definition, context, tool_service = make_tool_runtime_context()
        self.addCleanup(temp.cleanup)
        parent_session = AgentSession(task_id=context.task_id, step_id="machine_spec_compiler", agent_role="Compiler", goal="compile")
        requests = [
            SubagentSpawnRequest(
                scope=SubagentScope.SESSION_HELPER,
                goal="Model state machine",
                task_slice="Only inspect state machine",
                input_refs=["intent"],
                input_excerpt={"intent": "coupon state machine"},
                allowed_tools=["knowledge.retrieve"],
                output_schema={"summary": "string", "states": "array", "confidence": "string"},
                budget=SubagentBudget(max_iterations=1, max_input_tokens=300, max_output_tokens=120, max_tool_calls=1, spawn_fanout_remaining=2),
            ),
            SubagentSpawnRequest(
                scope=SubagentScope.SESSION_HELPER,
                goal="Find edge cases",
                task_slice="Only inspect edge cases",
                input_refs=["intent"],
                input_excerpt={"intent": "coupon edge cases"},
                allowed_tools=["knowledge.retrieve"],
                output_schema={"summary": "string", "findings": "array", "confidence": "string"},
                budget=SubagentBudget(max_iterations=1, max_input_tokens=300, max_output_tokens=120, max_tool_calls=1, spawn_fanout_remaining=2),
            ),
        ]

        runs = SubagentService(llm=ParallelLLM(), tool_service=tool_service).run_helpers(
            parent_session=parent_session,
            requests=requests,
            task_definition=definition,
            task_context=context,
        )

        self.assertEqual(len(runs), 2)
        self.assertTrue(all(run.execution_mode == ExecutionMode.PARALLEL_HELPERS for run in runs))
        self.assertEqual(len(parent_session.state.helper_runs), 2)


if __name__ == "__main__":
    unittest.main()

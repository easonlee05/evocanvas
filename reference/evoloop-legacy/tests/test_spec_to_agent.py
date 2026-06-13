"""
Evoloop 3.0 Spec-to-Agent 工作流的单元测试模块。

本模块主要用于验证：
1. `spec_to_agent` 工作流的结构定义、步骤配置和输出产物契约。
2. 对应工作流中注册的各种自定义处理器（Context Handlers, Agent Handlers, Gate Handlers）。
3. 运行时任务执行、原生工件（Artifacts）的生成顺序及其内容。
4. 各个特定步骤执行器（Executor）的具体行为，如归一化器、机器规约编译器、人工决策网关等。

主要涉及的 Mock 模拟行为包括：
- `FakeStorage`：用于模拟工件和状态的持久化存储。
- `FakeLLM`：用于模拟大语言模型（LLM）的调用返回。
- `FakeKnowledge`：用于模拟本地知识库检索能力。
"""

import tempfile
import unittest
from pathlib import Path

from app.core.task import TaskStatus
from app.services.fakes import FakeKnowledge, FakeLLM, FakeStorage
from app.services.task_service import TaskService
from app.services.tool_service import ToolService
from app.workflows.definitions import build_task_registry
from app.workflows.engine import WorkflowEngine
from app.workflows.spec_to_agent import build_spec_to_agent_definition


class TestSpecToAgentWorkflow(unittest.TestCase):
    """测试 Spec to Agent 整体工作流及其运行时行为的测试类。"""

    def make_service(self):
        """构建并初始化测试所需的 TaskService 和 FakeStorage 基础设施。

        Returns:
            tuple: 包含 TaskService 实例与 FakeStorage 实例的元组。
        """
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        registry = build_task_registry()
        storage = FakeStorage(root)
        # 初始化受控的 Tool 基础服务，并挂载虚拟知识库
        tool_service = ToolService.default(root=root, knowledge=FakeKnowledge())
        # 构建工作流引擎，使用 Mock LLM 及 虚拟存储
        engine = WorkflowEngine(tool_service=tool_service, llm=FakeLLM(), storage=storage)
        service = TaskService(registry=registry, engine=engine, storage=storage)
        self.addCleanup(temp.cleanup)
        return service, storage

    def test_spec_to_agent_workflow_structure(self):
        """验证 spec_to_agent 工作流的定义结构、核心步骤及输出规范契约。"""
        definition = build_spec_to_agent_definition()

        # 验证基础元数据
        self.assertEqual(definition.type, "spec_to_agent")
        self.assertEqual(definition.metadata["is_native_3_0"], True)
        self.assertEqual(definition.metadata["source_of_truth"], "machine_spec.yaml")

        steps = definition.workflow.steps
        step_ids = [step.id for step in steps]

        # 验证是否包含了全部核心步骤（Core Lane Steps）
        self.assertIn("context_normalizer", step_ids)
        self.assertIn("open_question_identifier", step_ids)
        self.assertIn("human_decision_gate", step_ids)
        self.assertIn("machine_spec_compiler", step_ids)
        self.assertIn("agent_package_generator", step_ids)
        self.assertIn("acceptance_protocol_generator", step_ids)
        
        # 验证工件写入步骤是否包含在内
        self.assertIn("writer_machine_spec", step_ids)
        self.assertIn("writer_human_brief", step_ids)
        self.assertIn("writer_agent_package", step_ids)
        self.assertIn("writer_acceptance", step_ids)
        self.assertIn("writer_traceability", step_ids)

        # 验证输出规格定义的文件映射关系
        self.assertEqual(definition.output_spec["machine_spec"], "machine_spec.yaml")
        self.assertEqual(definition.output_spec["human_brief"], "human_brief.md")
        self.assertEqual(definition.output_spec["agent_package"], "agent_package_codex.md")
        self.assertEqual(definition.output_spec["acceptance"], "acceptance.md")
        self.assertEqual(definition.output_spec["traceability"], "traceability.json")

    def test_spec_to_agent_registers_playbook_step_handlers(self):
        """验证 spec_to_agent 工作流中是否正确注册了各步骤的自定义 Handler 句柄。"""
        definition = build_spec_to_agent_definition()

        # 检查上下文处理器
        self.assertIn("context_normalizer", definition.metadata["custom_context_handlers"])
        # 检查智能体执行处理器
        self.assertIn("open_question_identifier", definition.metadata["custom_agent_handlers"])
        self.assertIn("machine_spec_compiler", definition.metadata["custom_agent_handlers"])
        self.assertIn("agent_package_generator", definition.metadata["custom_agent_handlers"])
        self.assertIn("acceptance_protocol_generator", definition.metadata["custom_agent_handlers"])
        # 检查人工网关处理器
        self.assertIn("human_decision_gate", definition.metadata["custom_gate_handlers"])

    def test_runtime_writes_native_artifacts_in_order(self):
        """测试在工作流引擎运行时中，是否能正常按顺序生成并写入指定名称的工件。"""
        service, storage = self.make_service()
        # 创建一个 spec_to_agent 的具体任务
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "将登录需求编译成 agent 可执行任务包",
            },
        )

        # 启动任务运行
        result = service.run_task(task.task_id)

        # 断言任务已成功运行结束
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        artifacts = storage.list_artifacts(task.task_id)
        
        # 验证生成的工件名称集合中是否包含预期的文件名
        artifact_names = [artifact.name for artifact in artifacts]
        self.assertIn("machine_spec.yaml", artifact_names)
        self.assertIn("human_brief.md", artifact_names)
        self.assertIn("agent_package_codex.md", artifact_names)
        self.assertIn("acceptance.md", artifact_names)
        self.assertIn("traceability.json", artifact_names)
        
        # 根据名字分别获取工件内容并进行具体验证
        machine_spec_art = next(a for a in artifacts if a.name == "machine_spec.yaml")
        traceability_art = next(a for a in artifacts if a.name == "traceability.json")
        machine_spec = storage.read_artifact(machine_spec_art.artifact_id)
        traceability = storage.read_artifact(traceability_art.artifact_id)
        
        # 验证工件内容是否注入了原始商业意图及溯源信息
        self.assertIn("business_intent:", machine_spec.content)
        self.assertIn("requirements:", machine_spec.content)
        self.assertIn('"source_of_truth": "machine_spec.yaml"', traceability.content)

    def test_runtime_compiles_structured_spec_outputs_for_gate_and_artifacts(self):
        """测试运行时中各个编译步骤生成的结构化输出以及决策网关的状态值。"""
        service, storage = self.make_service()
        # 创建测试任务
        task = service.create_task(
            "spec_to_agent",
            {
                "username": "alice",
                "business_intent": "把登录能力编译为可执行任务包",
                "context_scope": "auth",
            },
        )

        # 运行任务
        result = service.run_task(task.task_id)

        # 校验任务状态与步骤的归一化输出
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(
            result.context.step_outputs["context_normalizer"]["normalized_intent"],
            "把登录能力编译为可执行任务包",
        )
        # 校验编译器步骤输出的结构化真相源配置
        self.assertEqual(
            result.context.step_outputs["machine_spec_compiler"]["structured"]["source_of_truth"],
            "machine_spec",
        )
        # 校验人工决策网关的默认模拟状态（应为 pass 状态通过）
        self.assertEqual(
            result.context.step_outputs["human_decision_gate"]["gate"]["status"],
            "pass",
        )

        # 验证生成的 machine_spec 工件中确实注入了编译标识
        artifacts = storage.list_artifacts(task.task_id)
        machine_spec_art = next(a for a in artifacts if a.name == "machine_spec.yaml")
        machine_spec = storage.read_artifact(machine_spec_art.artifact_id)
        
        # 校验内容中是否包含了 compiler 生成的字样
        self.assertIn("compiled", machine_spec.content.lower())


class TestSpecToAgentExecutors(unittest.TestCase):
    """测试 Spec to Agent 各个步骤执行器（Executor）具体业务处理逻辑的测试类。"""

    def test_context_normalizer_executor(self):
        """验证 ContextNormalizerExecutor 在面对首尾有空格的意图和特定作用域时，是否能正确归一化。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.workflows.spec_to_agent import ContextNormalizerExecutor, build_spec_to_agent_definition

        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_exec_1",
            task_type="spec_to_agent",
            username="alice",
            title="Test Task",
            goal="Normalize requirements",
            inputs={"business_intent": "  Test intent  ", "context_scope": "auth"},
        )
        task = Task(definition=definition, context=context)
        step = WorkflowStep(id="context_normalizer", type="context", title="Test Step")

        executor = ContextNormalizerExecutor()
        result = executor.run(task, step)
        
        # 断言执行成功，且意图中的空格已被剥离（Strip），上下文作用域保持原样
        self.assertEqual(result.status.value, "succeeded")
        self.assertEqual(result.outputs["normalized_intent"], "Test intent")
        self.assertEqual(result.outputs["context_scope"], "auth")

    def test_machine_spec_compiler_executor(self):
        """验证 MachineSpecCompilerExecutor 在调用 LLM 编译规约时是否能够产生正确的格式化输出。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.services.fakes import FakeLLM
        from app.workflows.spec_to_agent import MachineSpecCompilerExecutor, build_spec_to_agent_definition

        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_exec_2",
            task_type="spec_to_agent",
            username="alice",
            title="Compiler Spec",
            goal="Compile spec",
            inputs={"business_intent": "Auth flow"},
        )
        task = Task(definition=definition, context=context)
        step = WorkflowStep(id="machine_spec_compiler", type="agent", title="Compiler Step", role="Compiler")

        # 使用 Mock LLM 初始化执行器
        executor = MachineSpecCompilerExecutor(llm=FakeLLM())
        result = executor.run(task, step)
        
        # 断言编译器执行成功，并测试输出内容
        self.assertEqual(result.status.value, "succeeded")
        self.assertEqual(result.outputs["structured"]["primary_requirement"], "Auth flow")
        self.assertTrue(result.outputs["agent_session_id"].startswith("session_"))
        self.assertEqual(result.outputs["agent_session_trace"]["step_id"], "machine_spec_compiler")
        self.assertEqual(result.outputs["agent_session_trace"]["state"]["status"], "succeeded")
        self.assertIn("allowed_tools", result.outputs["agent_session_trace"])
        self.assertIn("agenda_items", result.outputs["agent_session_trace"]["state"])

    def test_machine_spec_compiler_blocks_when_llm_json_degrades_to_fallback(self):
        """核心 source-of-truth 编译步骤不能把 LLM 解析失败伪装成成功产物。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult
        from app.workflows.spec_to_agent import MachineSpecCompilerExecutor, build_spec_to_agent_definition

        class InvalidJsonLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(content="not json", structured={})

        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_exec_degraded",
            task_type="spec_to_agent",
            username="alice",
            title="Compiler Spec",
            goal="Compile spec",
            inputs={"business_intent": "Auth flow"},
        )
        task = Task(definition=definition, context=context)
        step = WorkflowStep(id="machine_spec_compiler", type="agent", title="Compiler Step", role="Compiler")

        result = MachineSpecCompilerExecutor(llm=InvalidJsonLLM()).run(task, step)

        self.assertEqual(result.status.value, "blocked")
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "workflow.llm_degraded_fallback")
        self.assertTrue(result.outputs["structured"].get("degraded"))

    def test_machine_spec_compiler_can_use_allowed_tool_inside_agent_session(self):
        """machine_spec_compiler 的 AgentSession 可通过 ToolService 调用白名单只读工具。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult
        from app.services.fakes import FakeKnowledge, FakeStorage
        from app.services.tool_service import ToolService
        from app.workflows.spec_to_agent import MachineSpecCompilerExecutor, build_spec_to_agent_definition

        class ToolCallingLLM:
            def __init__(self):
                self.calls = 0

            def invoke(self, role, prompt, context):
                self.calls += 1
                if self.calls == 1:
                    return LLMResult(content='{"tool_calls":[{"tool_name":"knowledge.retrieve","arguments":{"query":"auth"}}]}')
                return LLMResult(
                    content=(
                        '{"primary_requirement":"Auth flow",'
                        '"dependencies":["system"],'
                        '"strict_contracts":["traceable"],'
                        '"environment":{"os_target":"linux","node_version":"20.x"},'
                        '"security":{"require_auth":true}}'
                    )
                )

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        storage = FakeStorage(root)
        tool_service = ToolService.default(root=storage, knowledge=FakeKnowledge())
        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_exec_tool",
            task_type="spec_to_agent",
            username="alice",
            title="Compiler Tool Spec",
            goal="Compile spec",
            inputs={"business_intent": "Auth flow"},
        )
        task = Task(definition=definition, context=context)
        step = WorkflowStep(id="machine_spec_compiler", type="agent", title="Compiler Step", role="Compiler")

        result = MachineSpecCompilerExecutor(llm=ToolCallingLLM(), tool_service=tool_service).run(task, step)

        self.assertEqual(result.status.value, "succeeded")
        observations = result.outputs["agent_session_trace"]["state"]["observations"]
        self.assertEqual(observations[0]["kind"], "tool")
        self.assertEqual(observations[0]["data"]["tool_name"], "knowledge.retrieve")
        self.assertEqual(observations[0]["data"]["status"], "succeeded")

    def test_machine_spec_compiler_records_helper_runs_when_enabled(self):
        """启用内部 subagent 时，machine_spec_compiler 应记录 helper runs。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult
        from app.workflows.spec_to_agent import MachineSpecCompilerExecutor, build_spec_to_agent_definition

        class HelperAwareLLM:
            def invoke(self, role, prompt, context):
                if "SESSION HELPER" in prompt:
                    return LLMResult(
                        content='{"summary":"Mapped state edges","states":["anonymous","authenticated"],"confidence":"high"}'
                    )
                return LLMResult(
                    content=(
                        '{"primary_requirement":"Auth flow",'
                        '"dependencies":["system"],'
                        '"strict_contracts":["traceable"],'
                        '"environment":{"os_target":"linux","node_version":"20.x"},'
                        '"security":{"require_auth":true}}'
                    )
                )

        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_exec_compiler_helpers",
            task_type="spec_to_agent",
            username="alice",
            title="Compiler Helper Spec",
            goal="Compile spec",
            inputs={"business_intent": "Auth flow", "enable_subagents": True},
        )
        task = Task(definition=definition, context=context)
        step = WorkflowStep(id="machine_spec_compiler", type="agent", title="Compiler Step", role="Compiler")

        result = MachineSpecCompilerExecutor(llm=HelperAwareLLM()).run(task, step)

        self.assertEqual(result.status.value, "succeeded")
        self.assertGreaterEqual(len(result.outputs["agent_session_trace"]["state"]["helper_runs"]), 1)

    def test_open_question_identifier_runs_through_agent_session(self):
        """open_question_identifier 应通过 AgentSession 输出澄清问题与 trace。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult
        from app.workflows.spec_to_agent import OpenQuestionIdentifierExecutor, build_spec_to_agent_definition

        class QuestionLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(
                    content=(
                        '{"has_questions":true,'
                        '"questions":["Which auth provider should be used?","What is the session timeout?"]}'
                    )
                )

        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_open_questions",
            task_type="spec_to_agent",
            username="alice",
            title="Open Questions",
            goal="Clarify auth spec",
            inputs={"business_intent": "Build login with SSO"},
        )
        task = Task(definition=definition, context=context)
        step = WorkflowStep(id="open_question_identifier", type="agent", title="Open Questions", role="Compiler")

        result = OpenQuestionIdentifierExecutor(llm=QuestionLLM()).run(task, step)

        self.assertEqual(result.status.value, "succeeded")
        self.assertTrue(result.outputs["structured"]["has_questions"])
        self.assertEqual(len(result.outputs["structured"]["questions"]), 2)
        self.assertEqual(result.outputs["structured"]["diagnostic_matrix_runs"], 1)
        self.assertTrue(result.outputs["agent_session_id"].startswith("session_"))
        self.assertEqual(result.outputs["agent_session_trace"]["step_id"], "open_question_identifier")
        self.assertEqual(result.outputs["agent_session_trace"]["state"]["status"], "succeeded")

    def test_open_question_identifier_records_helper_runs_when_enabled(self):
        """启用内部 subagent 时，open_question_identifier 应记录 helper runs。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult
        from app.workflows.spec_to_agent import OpenQuestionIdentifierExecutor, build_spec_to_agent_definition

        class HelperAwareLLM:
            def invoke(self, role, prompt, context):
                if "SESSION HELPER" in prompt:
                    return LLMResult(
                        content='{"summary":"Found one ambiguity","findings":["SSO provider missing"],"confidence":"medium"}'
                    )
                return LLMResult(
                    content='{"has_questions":true,"questions":["Which SSO provider should be used?"],"diagnostic_matrix_runs":1}'
                )

        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_open_questions_helpers",
            task_type="spec_to_agent",
            username="alice",
            title="Open Questions",
            goal="Clarify auth spec",
            inputs={"business_intent": "Build login with SSO", "enable_subagents": True},
        )
        task = Task(definition=definition, context=context)
        step = WorkflowStep(id="open_question_identifier", type="agent", title="Open Questions", role="Compiler")

        result = OpenQuestionIdentifierExecutor(llm=HelperAwareLLM()).run(task, step)

        self.assertEqual(result.status.value, "succeeded")
        self.assertGreaterEqual(len(result.outputs["agent_session_trace"]["state"]["helper_runs"]), 1)

    def test_open_question_identifier_blocks_when_json_invalid(self):
        """open_question_identifier 不能在无法解析模型输出时假装没有问题。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult
        from app.workflows.spec_to_agent import OpenQuestionIdentifierExecutor, build_spec_to_agent_definition

        class InvalidJsonLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(content="not json")

        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_open_questions_bad",
            task_type="spec_to_agent",
            username="alice",
            title="Open Questions",
            goal="Clarify auth spec",
            inputs={"business_intent": "Build login with SSO"},
        )
        task = Task(definition=definition, context=context)
        step = WorkflowStep(id="open_question_identifier", type="agent", title="Open Questions", role="Compiler")

        result = OpenQuestionIdentifierExecutor(llm=InvalidJsonLLM()).run(task, step)

        self.assertEqual(result.status.value, "blocked")
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "workflow.open_question_identifier_blocked")
        self.assertTrue(result.outputs["structured"].get("degraded"))

    def test_agent_package_generator_runs_through_agent_session_and_uses_peer_target(self):
        """agent_package_generator 应通过 AgentSession 选择平级 AI 技术同事。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult
        from app.workflows.spec_to_agent import AgentPackageGeneratorExecutor, build_spec_to_agent_definition

        class PeerLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(content='{"peer_target":"claude"}')

        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_agent_package",
            task_type="spec_to_agent",
            username="alice",
            title="Package",
            goal="Package spec",
        )
        context.step_outputs["machine_spec_compiler"] = {
            "structured": {"primary_requirement": "Refactor billing", "source_of_truth": "machine_spec"}
        }
        task = Task(definition=definition, context=context)
        step = WorkflowStep(id="agent_package_generator", type="agent", title="Package", role="Compiler")

        result = AgentPackageGeneratorExecutor(llm=PeerLLM()).run(task, step)

        self.assertEqual(result.status.value, "succeeded")
        self.assertEqual(result.outputs["structured"]["peer_target"], "claude")
        self.assertNotIn("worker_target", result.outputs["structured"])
        self.assertTrue(result.outputs["agent_session_id"].startswith("session_"))
        self.assertEqual(result.outputs["agent_session_trace"]["step_id"], "agent_package_generator")
        self.assertEqual(result.outputs["agent_session_trace"]["state"]["status"], "succeeded")

    def test_acceptance_protocol_generator_runs_through_agent_session(self):
        """acceptance_protocol_generator 应通过 AgentSession 生成验收向量。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult
        from app.workflows.spec_to_agent import AcceptanceProtocolGeneratorExecutor, build_spec_to_agent_definition

        class AcceptanceLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(
                    content='{"test_vectors":["Given a paid order, When refund is requested, Then ledger is reconciled"]}'
                )

        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_acceptance_protocol",
            task_type="spec_to_agent",
            username="alice",
            title="Acceptance",
            goal="Generate acceptance",
        )
        context.step_outputs["machine_spec_compiler"] = {
            "structured": {"primary_requirement": "Refund flow", "source_of_truth": "machine_spec"}
        }
        task = Task(definition=definition, context=context)
        step = WorkflowStep(id="acceptance_protocol_generator", type="agent", title="Acceptance", role="Compiler")

        result = AcceptanceProtocolGeneratorExecutor(llm=AcceptanceLLM()).run(task, step)

        self.assertEqual(result.status.value, "succeeded")
        self.assertEqual(result.outputs["structured"]["test_vectors"][0], "Given a paid order, When refund is requested, Then ledger is reconciled")
        self.assertTrue(result.outputs["agent_session_id"].startswith("session_"))
        self.assertEqual(result.outputs["agent_session_trace"]["step_id"], "acceptance_protocol_generator")
        self.assertEqual(result.outputs["agent_session_trace"]["state"]["status"], "succeeded")

    def test_acceptance_protocol_generator_blocks_when_json_invalid(self):
        """acceptance_protocol_generator 不能在模型失败时用 fallback 向量假装成功。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult
        from app.workflows.spec_to_agent import AcceptanceProtocolGeneratorExecutor, build_spec_to_agent_definition

        class InvalidJsonLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(content="not json")

        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_acceptance_protocol_bad",
            task_type="spec_to_agent",
            username="alice",
            title="Acceptance",
            goal="Generate acceptance",
        )
        context.step_outputs["machine_spec_compiler"] = {
            "structured": {"primary_requirement": "Refund flow", "source_of_truth": "machine_spec"}
        }
        task = Task(definition=definition, context=context)
        step = WorkflowStep(id="acceptance_protocol_generator", type="agent", title="Acceptance", role="Compiler")

        result = AcceptanceProtocolGeneratorExecutor(llm=InvalidJsonLLM()).run(task, step)

        self.assertEqual(result.status.value, "blocked")
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "workflow.acceptance_protocol_generator_blocked")
        self.assertTrue(result.outputs["structured"].get("degraded"))

    def test_human_decision_gate_executor(self):
        """验证 HumanDecisionGateExecutor 在无阻塞或模拟情况下能够正确做出放行（Pass）决策。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.workflows.spec_to_agent import HumanDecisionGateExecutor, build_spec_to_agent_definition

        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_exec_3",
            task_type="spec_to_agent",
            username="alice",
            title="Decision Gate Test",
            goal="Evaluate gate",
        )
        task = Task(definition=definition, context=context)
        step = WorkflowStep(id="human_decision_gate", type="gate", title="Gate Step")

        executor = HumanDecisionGateExecutor()
        
        # 默认模拟实现中应直接通过
        pass_result = executor.run(task, step)
        self.assertEqual(pass_result.status.value, "succeeded")
        self.assertEqual(pass_result.outputs["gate"]["status"], "pass")



if __name__ == "__main__":
    unittest.main()

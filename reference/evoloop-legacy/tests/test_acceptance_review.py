"""
验收评审（Acceptance Review）工作流测试模块。

本模块主要测试 Evoloop 3.0 的验收评审工作流，验证系统从输入 machine_spec、acceptance_protocol
到最终生成 review_result 并进行产物图（ArtifactGraph）更新的端到端逻辑。
主要包含以下核心场景：
1. 验收评审工作流定义（Acceptance Review Definition）的结构完整性验证。
2. 正常流（Verdict 为 Pass）下的任务运行逻辑与产物图校验。
3. 变更请求流（Verdict 为 Changes Required，如检测到 TODO 开发项）下的任务运行逻辑。
4. 变更影响分析器（DiffImpactAnalyzerExecutor）在包含 TODO 时的检测和修复任务生成逻辑。
5. 产物图（Artifact Graph）自身的校验逻辑。

测试涉及的 Mock 模拟包括 FakeStorage、FakeKnowledge、FakeLLM，以及对 verify_and_update_artifact_graph 的 Mock 拦截。
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.task import TaskStatus
from app.services.fakes import FakeKnowledge, FakeLLM, FakeStorage
from app.services.task_service import TaskService
from app.services.tool_service import ToolService
from app.workflows.definitions import build_task_registry
from app.workflows.engine import WorkflowEngine
from app.core.review import ReviewResult, ReviewVerdict
from app.workflows.acceptance_review import (
    build_acceptance_review_definition,
    serialize_review_result,
    verify_and_update_artifact_graph,
    DiffImpactAnalyzerExecutor,
    RequirementCoverageExecutor,
)


class TestAcceptanceReviewWorkflow(unittest.TestCase):
    """
    验收评审工作流的单元测试类。

    维护了临时的任务服务（TaskService）和存储（Storage）脚手架，
    用于验证验收评审各个步骤的运行逻辑和产物校验。
    """

    def make_service(self):
        """
        创建并初始化测试所需的临时 TaskService 与 FakeStorage。

        Returns:
            tuple: (TaskService 实例, FakeStorage 实例)
        """
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        registry = build_task_registry()
        storage = FakeStorage(root)
        tool_service = ToolService.default(root=root, knowledge=FakeKnowledge())
        engine = WorkflowEngine(tool_service=tool_service, llm=FakeLLM(), storage=storage)
        service = TaskService(registry=registry, engine=engine, storage=storage)
        # 注册清理回调，确保临时目录在测试结束后被删除
        self.addCleanup(temp.cleanup)
        return service, storage

    def test_acceptance_review_definition_structure(self):
        """
        验证验收评审工作流定义 (TaskDefinition) 的结构是否符合 3.0 规范。

        检查项：
        - 任务类型是否为 "acceptance_review"
        - 必要的元数据字段（如 is_native_3_0, source_of_truth）
        - 是否注册了对应的自定义上下文处理器、Agent 处理器、门控处理器
        - 编排步骤中是否包含了预期的核心步骤（ingest_acceptance_context, requirement_coverage 等）
        - 输出规格中是否指定了 review_result.md 产物
        """
        definition = build_acceptance_review_definition()
        self.assertEqual(definition.type, "acceptance_review")
        self.assertEqual(definition.metadata["is_native_3_0"], True)
        self.assertEqual(definition.metadata["source_of_truth"], "machine_spec")
        self.assertIn("ingest_acceptance_context", definition.metadata["custom_context_handlers"])
        self.assertIn("requirement_coverage", definition.metadata["custom_agent_handlers"])
        self.assertIn("diff_impact_analyzer", definition.metadata["custom_agent_handlers"])
        self.assertIn("review_result_compiler", definition.metadata["custom_agent_handlers"])
        self.assertIn("review_gate", definition.metadata["custom_gate_handlers"])

        steps = definition.workflow.steps
        step_ids = [step.id for step in steps]

        # 验证核心步骤是否存在于工作流中
        self.assertIn("ingest_acceptance_context", step_ids)
        self.assertIn("requirement_coverage", step_ids)
        self.assertIn("diff_impact_analyzer", step_ids)
        self.assertIn("review_result_compiler", step_ids)
        self.assertIn("review_gate", step_ids)
        self.assertIn("writer_review_result", step_ids)
        self.assertIn("final_checkpoint", step_ids)

        # 验证输出规格
        self.assertEqual(definition.output_spec["review_result"], "review_result.md")

    def test_runtime_writes_review_result_artifact_for_pass_and_validates_graph(self):
        """
        测试当验收评审结果为通过（pass）时，工作流是否正确写入 review_result 产物并调用产物图验证。

        业务输入：
        - 包含合法的 machine_spec, acceptance_protocol, implementation_summary 与无冲突的 diff。

        断言与校验：
        - 验证任务状态为 COMPLETED。
        - 验证 verify_and_update_artifact_graph 被正确调用 1 次。
        - 检查生成的 review_result.md 包含 "Verdict: pass" 且包含相关的需求 ID 标签。
        """
        service, storage = self.make_service()
        # 创建待执行的验收评审任务
        task = service.create_task(
            "acceptance_review",
            {
                "username": "alice",
                "machine_spec": "req_login: 用户必须能使用手机号登录",
                "acceptance_protocol": "case_login: 输入手机号后应登录成功",
                "implementation_summary": "已完成手机号登录接口与页面联调",
                "diff": "+ add phone login flow",
            },
        )

        # 拦截 verify_and_update_artifact_graph 函数以验证其是否被执行
        with patch("app.workflows.acceptance_review.verify_and_update_artifact_graph", wraps=verify_and_update_artifact_graph) as graph_helper:
            result = service.run_task(task.task_id)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(graph_helper.call_count, 1)
        artifacts = storage.list_artifacts(task.task_id)
        self.assertEqual([artifact.name for artifact in artifacts], ["review_result.md"])
        review_result = storage.read_artifact(artifacts[0].artifact_id)
        
        # 检查评审报告内容中是否存在关键判定信息
        self.assertIn("Verdict: pass", review_result.content)
        self.assertIn("All checks passed.", review_result.content)
        self.assertIn("req_login", review_result.content)
        self.assertEqual(result.context.step_outputs["ingest_acceptance_context"]["requirement_ids"], ["req_login"])
        self.assertEqual(result.context.step_outputs["review_gate"]["gate"]["review_verdict"], "pass")
        self.assertEqual(result.context.step_outputs["review_gate"]["gate"]["issue_count"], 0)

    def test_runtime_writes_review_result_artifact_for_changes_required(self):
        """
        测试当变更包含 TODO 开发项时，验收评审结果是否为需要修改（changes_required）。

        业务输入：
        - 包含未完成 TODO 项的 diff 代码段。

        断言与校验：
        - 验证任务状态为 COMPLETED。
        - 检查生成的 review_result.md 包含 "Verdict: changes_required"。
        - 确认报告中指出了 "存在未完成的 TODO 开发项" 的问题。
        - 检查门控输出中的 issue 数量是否为 1。
        """
        service, storage = self.make_service()
        task = service.create_task(
            "acceptance_review",
            {
                "username": "alice",
                "machine_spec": "req_login: 用户必须能使用手机号登录",
                "acceptance_protocol": "case_login: 输入手机号后应登录成功",
                "implementation_summary": "登录流程基本完成但还有 missing edge case",
                "diff": "+ // TODO: 手机号格式校验暂未实现",
            },
        )

        result = service.run_task(task.task_id)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        artifacts = storage.list_artifacts(task.task_id)
        review_result = storage.read_artifact(artifacts[0].artifact_id)
        
        # 验证报告中记录了 changes_required 状态及检测到的问题描述
        self.assertIn("Verdict: changes_required", review_result.content)
        self.assertIn("Address issues: 存在未完成的 TODO 开发项", review_result.content)
        self.assertIn("Detected issues: 存在未完成的 TODO 开发项", review_result.content)
        self.assertEqual(result.context.step_outputs["review_gate"]["gate"]["review_verdict"], "changes_required")
        self.assertEqual(result.context.step_outputs["review_gate"]["gate"]["issue_count"], 1)
        self.assertEqual(result.context.step_outputs["review_gate"]["gate"]["coverage_count"], 1)

    def test_diff_impact_analyzer_failure_cases(self):
        """
        测试变更影响分析器（DiffImpactAnalyzerExecutor）对含有缺陷的变更的处理。

        验证当输入中存在带有 TODO 注释的变更代码时：
        - 步骤运行状态为 succeeded。
        - 输出的缺陷列表（issues）中包含一条严重等级为 major 的问题。
        - 生成了对应的修复任务（fix_tasks）。
        - 缺陷关联了正确的业务需求 ID（req_login）。
        """
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        
        # 构建模拟的上下文环境，伪造前置步骤的输出
        context = TaskContext(
            task_id="task_exec_diff",
            task_type="acceptance_review",
            username="alice",
            title="Test Diff",
            goal="Diff Test",
            inputs={"diff": "+ // TODO: 手机号格式校验暂未实现", "implementation_summary": "登录功能已基本实现", "machine_spec": "req_login:"},
        )
        # 假装 ingest_acceptance_context 已经运行完毕并输出了相应参数
        context.step_outputs["ingest_acceptance_context"] = {
            "diff": "+ // TODO: 手机号格式校验暂未实现",
            "implementation_summary": "登录功能已基本实现",
            "requirement_ids": ["req_login"]
        }
        
        task = Task(definition=build_acceptance_review_definition(), context=context)
        step = WorkflowStep(id="diff_impact_analyzer", type="agent", title="Diff Check")
        
        agent = DiffImpactAnalyzerExecutor()

        # 执行变更分析
        fail_result = agent.run(task, step)
        
        self.assertEqual(fail_result.status.value, "succeeded")
        self.assertEqual(len(fail_result.outputs["issues"]), 1)
        self.assertEqual(fail_result.outputs["issues"][0]["severity"], "major")
        self.assertEqual(len(fail_result.outputs["fix_tasks"]), 1)
        self.assertIn("req_login", fail_result.outputs["issues"][0]["related_requirement_ids"])

    def test_requirement_coverage_degradation_does_not_mark_requirements_covered(self):
        """覆盖率评审降级时不能默认把所有需求标记为 covered=True。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult

        class InvalidJsonLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(content="not json", structured={})

        context = TaskContext(
            task_id="task_exec_coverage_degraded",
            task_type="acceptance_review",
            username="alice",
            title="Coverage Test",
            goal="Coverage Test",
            inputs={"diff": "+ add partial login", "machine_spec": "req_login:"},
        )
        context.step_outputs["ingest_acceptance_context"] = {"requirement_ids": ["req_login"]}
        task = Task(definition=build_acceptance_review_definition(), context=context)
        step = WorkflowStep(id="requirement_coverage", type="agent", title="Coverage", role="Reviewer")

        result = RequirementCoverageExecutor(llm=InvalidJsonLLM()).run(task, step)

        self.assertEqual(result.status.value, "succeeded")
        self.assertTrue(result.outputs["degraded"])
        self.assertEqual(result.outputs["coverage"][0]["covered"], False)
        self.assertTrue(result.outputs["coverage"][0]["metadata"]["degraded"])

    def test_requirement_coverage_runs_through_agent_session(self):
        """requirement_coverage 应通过 Reviewer AgentSession 产生 coverage trace。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult

        class CoverageLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(
                    content='{"req_login":{"covered":true,"notes":"implemented","evidence_refs":["app/auth.py"]}}'
                )

        context = TaskContext(
            task_id="task_exec_coverage_session",
            task_type="acceptance_review",
            username="alice",
            title="Coverage Test",
            goal="Coverage Test",
            inputs={"diff": "+ add login", "machine_spec": "req_login:"},
        )
        context.step_outputs["ingest_acceptance_context"] = {"requirement_ids": ["req_login"]}
        task = Task(definition=build_acceptance_review_definition(), context=context)
        step = WorkflowStep(id="requirement_coverage", type="agent", title="Coverage", role="Reviewer")

        result = RequirementCoverageExecutor(llm=CoverageLLM()).run(task, step)

        self.assertEqual(result.status.value, "succeeded")
        self.assertEqual(result.outputs["coverage"][0]["covered"], True)
        self.assertTrue(result.outputs["agent_session_id"].startswith("session_"))
        self.assertEqual(result.outputs["agent_session_trace"]["step_id"], "requirement_coverage")
        self.assertEqual(result.outputs["agent_session_trace"]["state"]["status"], "succeeded")
        self.assertIn("allowed_tools", result.outputs["agent_session_trace"])
        self.assertIn("agenda_items", result.outputs["agent_session_trace"]["state"])

    def test_requirement_coverage_records_helper_runs_when_enabled(self):
        """启用内部 subagent 时，requirement_coverage 应记录 helper runs。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult

        class HelperAwareLLM:
            def invoke(self, role, prompt, context):
                if "SESSION HELPER" in prompt:
                    return LLMResult(
                        content='{"summary":"Coverage hotspots found","requirement_focus":["req_login"],"confidence":"medium"}'
                    )
                return LLMResult(
                    content='{"req_login":{"covered":true,"notes":"implemented","evidence_refs":["app/auth.py"]}}'
                )

        context = TaskContext(
            task_id="task_exec_coverage_helpers",
            task_type="acceptance_review",
            username="alice",
            title="Coverage Helper Test",
            goal="Coverage Helper Test",
            inputs={"diff": "+ add login", "machine_spec": "req_login:", "enable_subagents": True},
        )
        context.step_outputs["ingest_acceptance_context"] = {"requirement_ids": ["req_login"]}
        task = Task(definition=build_acceptance_review_definition(), context=context)
        step = WorkflowStep(id="requirement_coverage", type="agent", title="Coverage", role="Reviewer")

        result = RequirementCoverageExecutor(llm=HelperAwareLLM()).run(task, step)

        self.assertEqual(result.status.value, "succeeded")
        self.assertGreaterEqual(len(result.outputs["agent_session_trace"]["state"]["helper_runs"]), 1)

    def test_requirement_coverage_marks_degraded_when_agent_session_invalid(self):
        """requirement_coverage 不能在模型不可解析时继续伪装成可信 coverage。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult

        class InvalidJsonLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(content="not json", structured={})

        context = TaskContext(
            task_id="task_exec_coverage_blocked",
            task_type="acceptance_review",
            username="alice",
            title="Coverage Test",
            goal="Coverage Test",
            inputs={"diff": "+ add login", "machine_spec": "req_login:"},
        )
        context.step_outputs["ingest_acceptance_context"] = {"requirement_ids": ["req_login"]}
        task = Task(definition=build_acceptance_review_definition(), context=context)
        step = WorkflowStep(id="requirement_coverage", type="agent", title="Coverage", role="Reviewer")

        result = RequirementCoverageExecutor(llm=InvalidJsonLLM()).run(task, step)

        self.assertEqual(result.status.value, "succeeded")
        self.assertTrue(result.outputs["degraded"])
        self.assertEqual(result.outputs["coverage"][0]["covered"], False)
        self.assertTrue(result.outputs["coverage"][0]["metadata"]["degraded"])
        self.assertTrue(result.outputs["agent_session_id"].startswith("session_"))

    def test_diff_impact_degradation_creates_visible_issue(self):
        """语义审查降级时必须生成显性 issue/fix_task，不能返回空列表假装无问题。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult

        class InvalidJsonLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(content="not json", structured={})

        context = TaskContext(
            task_id="task_exec_diff_degraded",
            task_type="acceptance_review",
            username="alice",
            title="Diff Test",
            goal="Diff Test",
            inputs={"diff": "+ add login flow", "implementation_summary": "login changed"},
        )
        context.step_outputs["ingest_acceptance_context"] = {
            "parsed_diff_files": [],
            "requirement_ids": ["req_login"],
        }
        task = Task(definition=build_acceptance_review_definition(), context=context)
        step = WorkflowStep(id="diff_impact_analyzer", type="agent", title="Diff Check", role="Reviewer")

        result = DiffImpactAnalyzerExecutor(llm=InvalidJsonLLM()).run(task, step)

        self.assertEqual(result.status.value, "succeeded")
        self.assertTrue(result.outputs["degraded"])
        self.assertEqual(result.outputs["issues"][0]["summary"], "语义审查降级，无法确认交付物安全通过")
        self.assertEqual(result.outputs["fix_tasks"][0]["title"], "人工复核降级的语义审查结果")

    def test_diff_impact_semantic_review_runs_through_agent_session(self):
        """静态插件无命中时，diff_impact_analyzer 应通过 Reviewer AgentSession 做语义审查。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult

        class SemanticLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(content='{"issues":[],"fix_tasks":[]}')

        context = TaskContext(
            task_id="task_exec_diff_session",
            task_type="acceptance_review",
            username="alice",
            title="Diff Test",
            goal="Diff Test",
            inputs={"diff": "+ add login flow", "implementation_summary": "login changed"},
        )
        context.step_outputs["ingest_acceptance_context"] = {
            "parsed_diff_files": [],
            "requirement_ids": ["req_login"],
        }
        task = Task(definition=build_acceptance_review_definition(), context=context)
        step = WorkflowStep(id="diff_impact_analyzer", type="agent", title="Diff Check", role="Reviewer")

        result = DiffImpactAnalyzerExecutor(llm=SemanticLLM()).run(task, step)

        self.assertEqual(result.status.value, "succeeded")
        self.assertFalse(result.outputs["degraded"])
        self.assertTrue(result.outputs["agent_session_id"].startswith("session_"))
        self.assertEqual(result.outputs["agent_session_trace"]["step_id"], "diff_impact_analyzer")
        self.assertEqual(result.outputs["agent_session_trace"]["state"]["status"], "succeeded")

    def test_diff_impact_analyzer_records_helper_runs_when_enabled(self):
        """启用内部 subagent 时，diff_impact_analyzer 应记录 helper runs。"""
        from app.core.task import Task, WorkflowStep
        from app.core.context import TaskContext
        from app.core.ports import LLMResult

        class HelperAwareLLM:
            def invoke(self, role, prompt, context):
                if "SESSION HELPER" in prompt:
                    return LLMResult(
                        content='{"summary":"Found risk themes","risk_focus":["regression"],"confidence":"medium"}'
                    )
                return LLMResult(content='{"issues":[],"fix_tasks":[]}')

        context = TaskContext(
            task_id="task_exec_diff_helpers",
            task_type="acceptance_review",
            username="alice",
            title="Diff Helper Test",
            goal="Diff Helper Test",
            inputs={"diff": "+ add login flow", "implementation_summary": "login changed", "enable_subagents": True},
        )
        context.step_outputs["ingest_acceptance_context"] = {
            "parsed_diff_files": [],
            "requirement_ids": ["req_login"],
        }
        task = Task(definition=build_acceptance_review_definition(), context=context)
        step = WorkflowStep(id="diff_impact_analyzer", type="agent", title="Diff Check", role="Reviewer")

        result = DiffImpactAnalyzerExecutor(llm=HelperAwareLLM()).run(task, step)

        self.assertEqual(result.status.value, "succeeded")
        self.assertGreaterEqual(len(result.outputs["agent_session_trace"]["state"]["helper_runs"]), 1)

    def test_graph_validation(self):
        """
        验证 verify_and_update_artifact_graph 能成功构建产物图并校验通过。

        断言与校验：
        - 调用 verify_and_update_artifact_graph 更新图数据。
        - 校验 graph.validate() 运行正常而不抛出任何 ArtifactGraphValidationError 异常。
        """
        # 验证图关系回写与校验
        graph = verify_and_update_artifact_graph(
            work_id="work_123",
            machine_spec_ref="memory://tasks/work_123/machine_spec",
            review_result_ref="file://artifacts/review_result_123.md",
            acceptance_protocol_ref="memory://tasks/work_123/acceptance_protocol",
        )
        # validate() 方法应该正常通过而不抛出任何 ArtifactGraphValidationError
        graph.validate()


if __name__ == "__main__":
    unittest.main()

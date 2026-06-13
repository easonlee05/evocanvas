"""
Evoloop 3.0 工作流运行时的单元与集成测试模块。

本测试文件覆盖了以下关键组件的逻辑验证：
1. `WorkflowRuntimePlan`：工作流执行计划的构建、步骤重复 ID 校验、悬挂路径校验及并行步骤分组。
2. `CheckpointManager`：检查点管理逻辑，包含检查点状态恢复决策及 Transaction payload 构建。
3. `ContextCompilerService`：上下文编译器，负责按步骤规范解析渲染工件，并在不满足原生契约时报错。
4. `PlaybookDAGRuntime`：基于有向无环图（DAG）的任务流调度逻辑，包含前沿节点（Frontier）计算、基于上下文状态的动态路由选择、以及循环依赖回路检测。
5. `CheckpointReplay`：基于历史事件回放并重建任务进度，统计各步骤尝试次数及恢复下一重试点。
6. `StepExecutionRegistry`：步骤执行器注册表的注册和调用分发机制。
7. `BuiltInStepExecutors`：内建步骤执行器（Context, Diff, Checkpoint, Artifact）的具体调用行为及其 Tool 服务集成。
8. `RetryPolicyRuntime`：步骤重试策略运行评估，包含最大次数限制、超时退避熔断、非重试错误隔离以及安全敏感日志脱敏。
9. `WorkflowStateStore` 和 `WorkflowRollbackPlanner`：状态存储及回滚计划器，用于记录运行历史并精确指定失败回滚到的检查点位置。
10. `WorkflowEngineRetryIntegration`：工作流引擎真实调用链路下的重试与失败熔断的集成联调。
"""

import unittest

from app.core.context import TaskContext
from app.core.errors import DomainError
from app.core.task import StepResult, StepStatus, Task, TaskStatus, WorkflowSpec, WorkflowStep
from app.workflows.checkpoints import CheckpointManager
from app.workflows.context_compiler import ContextCompilerService
from app.workflows.runtime import WorkflowRuntimePlan
from app.workflows.spec_to_agent import build_spec_to_agent_definition


class WorkflowRuntimePlanTests(unittest.TestCase):
    """测试工作流执行计划（WorkflowRuntimePlan）构建及步骤关系映射校验的类。"""

    def test_rejects_duplicate_step_ids(self):
        """验证当工作流规格中存在重复的步骤 ID 时，运行时计划构建应当抛出 `workflow.duplicate_step_id` 错误。"""
        workflow = WorkflowSpec(
            name="bad",
            version="1.0",
            steps=[
                WorkflowStep(id="same", type="context", title="A"),
                WorkflowStep(id="same", type="agent", title="B"),
            ],
        )

        with self.assertRaises(DomainError) as raised:
            WorkflowRuntimePlan.from_workflow(workflow)

        # 校验异常代码是否符合预期
        self.assertEqual(raised.exception.code, "workflow.duplicate_step_id")

    def test_rejects_dangling_routes(self):
        """验证当步骤指定的成功跳转目标（on_success）不在已定义的步骤列表中时，应当抛出 `workflow.dangling_route` 错误。"""
        workflow = WorkflowSpec(
            name="bad",
            version="1.0",
            steps=[WorkflowStep(id="a", type="context", title="A", on_success="missing")],
        )

        with self.assertRaises(DomainError) as raised:
            WorkflowRuntimePlan.from_workflow(workflow)

        # 校验异常代码是否符合预期
        self.assertEqual(raised.exception.code, "workflow.dangling_route")

    def test_groups_contiguous_parallel_steps(self):
        """验证在顺序执行中，具有相同 `parallel_group` 的连续步骤是否能正确被归入到同一个并行执行批次中。"""
        workflow = WorkflowSpec(
            name="ok",
            version="1.0",
            steps=[
                WorkflowStep(id="a", type="context", title="A"),
                WorkflowStep(id="b", type="agent", title="B", parallel_group="reviewers"),
                WorkflowStep(id="c", type="agent", title="C", parallel_group="reviewers"),
                WorkflowStep(id="d", type="gate", title="D"),
            ],
        )

        plan = WorkflowRuntimePlan.from_workflow(workflow)

        # 校验从步骤 "a" 开始的批次划分，"b" 和 "c" 应该在一个批次中并行执行
        self.assertEqual(
            [[step.id for step in batch.steps] for batch in plan.batches_from("a")],
            [["a"], ["b", "c"], ["d"]],
        )

    def test_result_next_step_overrides_step_success_route(self):
        """验证在步骤执行完毕后，执行结果（StepResult）中指定的动态下一跳转步骤，能覆盖定义时硬编码的 on_success 路由。"""
        workflow = WorkflowSpec(
            name="ok",
            version="1.0",
            steps=[
                WorkflowStep(id="a", type="gate", title="A", on_success="b"),
                WorkflowStep(id="b", type="agent", title="B"),
                WorkflowStep(id="c", type="agent", title="C"),
            ],
        )
        plan = WorkflowRuntimePlan.from_workflow(workflow)
        # 模拟步骤 a 执行成功，但返回的动态路由要求跳转到步骤 c
        result = StepResult("a", StepStatus.SUCCEEDED, next_step_id="c")

        # 校验最终解析的成功路由是否被重写为 c
        self.assertEqual(plan.resolve_success_route("a", result), "c")


class WorkflowCheckpointManagerTests(unittest.TestCase):
    """测试工作流检查点管理器（CheckpointManager）的状态解析及 Payload 构建的类。"""

    def test_resume_uses_checkpoint_next_step_when_not_waiting_for_user(self):
        """验证当检查点并非处于等待用户干预状态时，应正确返回检查点中记录的 next_step_id。"""
        manager = CheckpointManager(storage=None)
        checkpoint = {"next_step_id": "writer", "status": "running"}

        self.assertEqual(manager.resume_step_id(checkpoint), "writer")

    def test_resume_ignores_waiting_user_checkpoint(self):
        """验证当检查点状态处于 WAITING_FOR_USER（等待用户操作）时，恢复的步骤应当返回 None（表明任务挂起，暂不能自动恢复）。"""
        manager = CheckpointManager(storage=None)
        checkpoint = {"next_step_id": "writer", "status": TaskStatus.WAITING_FOR_USER.value}

        self.assertIsNone(manager.resume_step_id(checkpoint))

    def test_build_transaction_checkpoint_payload(self):
        """验证构建检查点事务负载的正确性，包括 run_id、重试次数（attempt）及已完成步骤列表的映射。"""
        manager = CheckpointManager(storage=None)
        payload = manager.build_payload(
            task_id="task_1",
            run_id="run_1",
            last_completed_step_id="a",
            next_step_id="b",
            status="running",
            attempt=2,
            completed_step_ids=["a"],
        )

        # 校验字段属性
        self.assertEqual(payload["run_id"], "run_1")
        self.assertEqual(payload["attempt"], 2)
        self.assertEqual(payload["completed_step_ids"], ["a"])


class ContextCompilerServiceTests(unittest.TestCase):
    """测试上下文编译服务（ContextCompilerService）的工件 payload 转换逻辑的类。"""

    def make_native_task(self):
        """辅助方法：生成一个 3.0 本地原生 `spec_to_agent` 任务用于测试。"""
        definition = build_spec_to_agent_definition()
        context = TaskContext(
            task_id="task_1",
            task_type="spec_to_agent",
            username="alice",
            goal="Compile login requirements",
            title="Login",
            inputs={"business_intent": "Users must log in safely"},
        )
        return Task(definition=definition, context=context, task_id="task_1")

    def test_renders_native_machine_spec_payload(self):
        """验证在正常的 spec_to_agent 任务中，是否能渲染出正确的 machine_spec 原生工件文件名与主要需求内容。"""
        task = self.make_native_task()
        # 寻找测试目标步骤 writer_machine_spec
        step = next(step for step in task.definition.workflow.steps if step.id == "writer_machine_spec")
        compiler = ContextCompilerService()

        name, content = compiler.artifact_payload(task, step)

        # 验证工件名和渲染的内容
        self.assertEqual(name, "machine_spec.yaml")
        self.assertIn("source of truth", content.lower())
        self.assertIn("Users must log in safely", content)

    def test_rejects_native_artifact_without_single_output_key(self):
        """验证当原生工件步骤（Artifact Step）未配置任何 output_keys 时，编译服务应该抛出违背契约错误。"""
        task = self.make_native_task()
        # 构造一个无 output_keys 的不合法步骤
        bad_step = WorkflowStep(id="bad", type="artifact", title="Bad", output_keys=[])
        compiler = ContextCompilerService()

        with self.assertRaises(DomainError) as raised:
            compiler.artifact_payload(task, bad_step)

        # 验证契约失效错误码
        self.assertEqual(raised.exception.code, "workflow.native_artifact_contract_invalid")


if __name__ == "__main__":
    unittest.main()

from app.core.task import TaskDefinition
from app.core.tools import ToolPolicy
from app.workflows.executors import StepExecutionRegistry, StepExecutor
from app.workflows.dag_runtime import PlaybookDAGRuntime
from app.workflows.checkpoints import CheckpointReplay


class PlaybookDAGRuntimeTests(unittest.TestCase):
    """测试 PlaybookDAGRuntime 基于有向无环图的任务编排调度的类。"""

    def test_frontier_returns_all_dependency_ready_nodes(self):
        """验证 ready_node_ids 在不同的已完成步骤集合下，返回的所有依赖已满足的就绪（前沿）步骤。"""
        workflow = WorkflowSpec(
            name="dag",
            version="1.0",
            steps=[
                WorkflowStep(id="a", type="context", title="A"),
                WorkflowStep(id="b", type="agent", title="B", input_keys=["a"]),
                WorkflowStep(id="c", type="agent", title="C", input_keys=["a"]),
                WorkflowStep(id="d", type="gate", title="D", input_keys=["b", "c"]),
            ],
        )
        runtime = PlaybookDAGRuntime.from_workflow(workflow)

        # 没有任何步骤完成时，就绪的只有 root 节点 a
        self.assertEqual(runtime.ready_node_ids(completed=set()), ["a"])
        # a 完成后，b 和 c 均就绪
        self.assertEqual(runtime.ready_node_ids(completed={"a"}), ["b", "c"])
        # 仅 a, b 完成时，由于 d 依赖 c，因此仅 c 就绪
        self.assertEqual(runtime.ready_node_ids(completed={"a", "b"}), ["c"])
        # a, b, c 全完成后，最后一步 d 才就绪
        self.assertEqual(runtime.ready_node_ids(completed={"a", "b", "c"}), ["d"])

    def test_conditions_route_by_context_value(self):
        """验证网关步骤在运行后根据输出状态（如 succeeded/failed）进行动态条件路由的走向。"""
        workflow = WorkflowSpec(
            name="dag",
            version="1.0",
            steps=[
                WorkflowStep(id="gate", type="gate", title="Gate", on_success="fast", on_failure="slow"),
                WorkflowStep(id="fast", type="agent", title="Fast"),
                WorkflowStep(id="slow", type="agent", title="Slow"),
            ],
        )
        runtime = PlaybookDAGRuntime.from_workflow(workflow)

        # 状态为 succeeded 时走 fast 路由，状态为 failed 时走 slow 路由
        self.assertEqual(runtime.route_for("gate", {"status": "succeeded"}), "fast")
        self.assertEqual(runtime.route_for("gate", {"status": "failed"}), "slow")

    def test_rejects_dependency_cycle(self):
        """验证当 DAG 规格配置中存在循环依赖路径（例如 A 依赖 B 且 B 依赖 A）时，解析应当抛出 `workflow.dag_cycle` 异常。"""
        workflow = WorkflowSpec(
            name="dag",
            version="1.0",
            steps=[
                WorkflowStep(id="a", type="agent", title="A", input_keys=["b"]),
                WorkflowStep(id="b", type="agent", title="B", input_keys=["a"]),
            ],
        )

        with self.assertRaises(DomainError) as raised:
            PlaybookDAGRuntime.from_workflow(workflow)

        # 校验异常编码
        self.assertEqual(raised.exception.code, "workflow.dag_cycle")


class CheckpointReplayTests(unittest.TestCase):
    """测试通过重放历史事件还原步骤完成状态和重试计数的类。"""

    def test_replay_reconstructs_completed_steps_and_last_checkpoint(self):
        """验证给定一组包含步骤成功与失败的事件，能够正确分析出已成功完成的步骤集合、最后的失败步骤以及下一次尝试的序号。"""
        events = [
            {"type": "workflow.step.completed", "payload": {"step_id": "a", "run_id": "run_1"}},
            {"type": "workflow.step.completed", "payload": {"step_id": "b", "run_id": "run_1"}},
            {"type": "workflow.step.failed", "payload": {"step_id": "c", "run_id": "run_1"}},
        ]

        replay = CheckpointReplay.from_events("task_1", events)

        # 验证已完成步骤列表和最后的失败步骤
        self.assertEqual(replay.completed_step_ids, ["a", "b"])
        self.assertEqual(replay.failed_step_id, "c")
        # 由于失败了一次，下一步尝试次数应为 2
        self.assertEqual(replay.next_attempt_for("c"), 2)

    def test_replay_counts_multiple_attempts(self):
        """验证即便同一个步骤在事件记录中被尝试过多次且包含成功/失败，也能够正确累计重试次数，并计算出下一次重试序号。"""
        events = [
            {"type": "workflow.step.started", "payload": {"step_id": "a"}},
            {"type": "workflow.step.failed", "payload": {"step_id": "a"}},
            {"type": "workflow.step.started", "payload": {"step_id": "a"}},
            {"type": "workflow.step.completed", "payload": {"step_id": "a"}},
        ]

        replay = CheckpointReplay.from_events("task_1", events)

        # 校验 "a" 步骤历史累计启动的次数（2次）及下一次尝试计序号（3次）
        self.assertEqual(replay.attempts_by_step["a"], 2)
        self.assertEqual(replay.next_attempt_for("a"), 3)


class StepExecutionRegistryTests(unittest.TestCase):
    """测试步骤执行器注册与分发管理器（StepExecutionRegistry）的类。"""

    def test_dispatches_executor_by_step_type(self):
        """验证执行器注册表是否能够正确根据工作流步骤的类型，将其分发到对应的执行器逻辑。"""
        class DummyExecutor(StepExecutor):
            step_type = "dummy"

            def run(self, task, step, *, run_id=None, is_parallel=False):
                return StepResult(step.id, StepStatus.SUCCEEDED, outputs={"ok": True})

        registry = StepExecutionRegistry([DummyExecutor()])
        step = WorkflowStep(id="x", type="dummy", title="X")

        result = registry.run(None, step, run_id="run_1")

        # 校验是否成功分发并拿到了 Dummy 结果
        self.assertEqual(result.status, StepStatus.SUCCEEDED)
        self.assertEqual(result.outputs, {"ok": True})

    def test_unknown_executor_returns_failed_result(self):
        """验证如果遇到了未注册执行器支持的未知步骤类型，注册表应当安全地返回失败状态及特定错误码。"""
        registry = StepExecutionRegistry([])
        step = WorkflowStep(id="x", type="unknown", title="X")

        result = registry.run(None, step)

        # 断言结果为失败状态且错误原因为未知步骤类型
        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.error.code, "workflow.unknown_step_type")


from app.workflows.executors import (
    ArtifactStepExecutor,
    CheckpointStepExecutor,
    ContextStepExecutor,
    DefaultStepExecutorRegistryFactory,
    DiffStepExecutor,
)


class BuiltInStepExecutorsTests(unittest.TestCase):
    """测试框架内置步骤执行器行为（Context、Diff、Checkpoint、Artifact 等）的测试类。"""

    def make_task(self):
        """辅助方法：创建一个虚拟的任务实例，包含空的工作流和受限的 Tool 策略。"""
        definition = TaskDefinition(
            type="executor_test",
            display_name="Executor Test",
            input_schema={},
            workflow=WorkflowSpec(name="executor", version="1.0", steps=[]),
            tool_policy=ToolPolicy(task_type="executor_test"),
        )
        context = TaskContext(
            task_id="task_exec",
            task_type="executor_test",
            username="alice",
            goal="Run executors",
            title="Executors",
        )
        return Task(definition=definition, context=context, task_id="task_exec")

    def test_context_executor_marks_context_ready(self):
        """验证 ContextStepExecutor 在装载阶段，是否能够读取任务的目标信息作为状态输出。"""
        task = self.make_task()
        executor = ContextStepExecutor()
        step = WorkflowStep(id="load", type="context", title="Load")

        result = executor.run(task, step)

        self.assertEqual(result.status, StepStatus.SUCCEEDED)
        self.assertEqual(result.outputs["goal"], "Run executors")

    def test_diff_and_checkpoint_executors_return_structured_outputs(self):
        """验证 Diff 和 Checkpoint 执行器被调用时返回的标准结构体内容。"""
        task = self.make_task()
        diff = DiffStepExecutor().run(task, WorkflowStep(id="diff", type="diff", title="Diff"))
        checkpoint = CheckpointStepExecutor().run(task, WorkflowStep(id="cp", type="checkpoint", title="Checkpoint"))

        self.assertEqual(diff.outputs, {"candidates": []})
        self.assertEqual(checkpoint.outputs, {"checkpoint": "cp"})

    def test_artifact_executor_uses_context_compiler_and_tool_service(self):
        """验证 ArtifactStepExecutor 在执行写入工件任务时，能调用底层的 ToolService 触发 artifact.write 功能。"""
        class RecordingToolService:
            """用于捕获和记录实际 Tool 调用参数的模拟 Tool 服务。"""
            def __init__(self):
                self.calls = []

            def invoke(self, definition, context, call):
                from app.core.artifacts import Artifact
                from app.core.tools import ToolResult
                self.calls.append(call)
                # 模拟工件写入成功的返回
                return ToolResult(
                    call_id=call.id,
                    status="succeeded",
                    artifacts=[Artifact(artifact_id="artifact_1", task_id=context.task_id, name=call.arguments["name"], version=1)],
                )

        task = self.make_task()
        # 预设在步骤输出中的编译内容，供后续 ArtifactStepExecutor 提取写入
        task.context.step_outputs["writer_scene_docs"] = {"artifact_name": "模块概览.md", "artifact_content": "content"}
        tool_service = RecordingToolService()
        executor = ArtifactStepExecutor(tool_service=tool_service, context_compiler=ContextCompilerService())

        result = executor.run(task, WorkflowStep(id="writer", type="artifact", title="Write", role="Writer"))

        # 验证工件写入步骤调用成功，且内部调用的工具为 'artifact.write'，最终工件已挂载在任务上下文中
        self.assertEqual(result.status, StepStatus.SUCCEEDED)
        self.assertEqual(tool_service.calls[0].tool_name, "artifact.write")
        self.assertEqual(task.context.artifacts[0].name, "模块概览.md")

    def test_default_factory_registers_core_executor_types(self):
        """验证默认执行器工厂（DefaultStepExecutorRegistryFactory）正确注册了全部内置的七种核心执行器类型。"""
        registry = DefaultStepExecutorRegistryFactory(
            tool_service=None,
            llm=None,
            storage=None,
            context_compiler=ContextCompilerService(),
        ).build()

        # 检查这七种步骤类型是否都已经有分配的执行器
        for step_type in ["context", "agent", "gate", "arbitration", "artifact", "diff", "checkpoint"]:
            self.assertIsNotNone(registry.get(step_type))


from app.workflows.retry_policy import RetryDecision, RetryPolicyRuntime
from app.workflows.state_store import WorkflowStateStore, WorkflowRollbackPlanner


class RetryPolicyRuntimeTests(unittest.TestCase):
    """测试重试决策策略评估逻辑的测试类。"""

    def test_allows_retry_until_max_attempts(self):
        """验证重试策略下，当未超过最大尝试次数时应发出 RETRY 决策，一旦用尽则返回 GIVE_UP。"""
        runtime = RetryPolicyRuntime()
        step = WorkflowStep(
            id="fragile",
            type="agent",
            title="Fragile",
            retry_policy={"max_attempts": 3, "backoff_seconds": 2},
        )

        first = runtime.evaluate(step, attempt=1, elapsed_ms=25, error_code="TemporaryError")
        third = runtime.evaluate(step, attempt=3, elapsed_ms=25, error_code="TemporaryError")

        # 第一次失败应允许重试，且退避延迟为指定秒数
        self.assertEqual(first.decision, RetryDecision.RETRY)
        self.assertEqual(first.next_attempt, 2)
        self.assertEqual(first.delay_seconds, 2)
        # 第三次重试失败已达到 max_attempts，应放弃并表明重试耗尽
        self.assertEqual(third.decision, RetryDecision.GIVE_UP)
        self.assertEqual(third.reason, "max_attempts_exhausted")

    def test_timeout_breaks_before_retry(self):
        """验证如果单次步骤耗时超过了 retry_policy 指定的超时阈值（timeout_ms），即使重试次数未满也应当熔断并返回 TIMEOUT 决策。"""
        runtime = RetryPolicyRuntime()
        step = WorkflowStep(
            id="slow",
            type="agent",
            title="Slow",
            retry_policy={"max_attempts": 3, "timeout_ms": 10},
        )

        # 模拟运行耗时 50ms (超过了 10ms 的限制)
        decision = runtime.evaluate(step, attempt=1, elapsed_ms=50, error_code="Timeout")

        # 校验应被判定为超时异常放弃
        self.assertEqual(decision.decision, RetryDecision.TIMEOUT)
        self.assertEqual(decision.reason, "timeout_exceeded")

    def test_non_retryable_error_trips_circuit(self):
        """验证若步骤失败抛出的异常属于非重试异常白名单（如 tool.denied 权限拒绝），则应当无视重试上限立即熔断（CIRCUIT_OPEN）。"""
        runtime = RetryPolicyRuntime()
        step = WorkflowStep(
            id="denied",
            type="artifact",
            title="Denied",
            retry_policy={"max_attempts": 3, "non_retryable_errors": ["tool.denied"]},
        )

        decision = runtime.evaluate(step, attempt=1, elapsed_ms=1, error_code="tool.denied")

        self.assertEqual(decision.decision, RetryDecision.CIRCUIT_OPEN)
        self.assertEqual(decision.reason, "non_retryable_error")

    def test_event_payload_hides_error_message_but_keeps_error_code(self):
        """验证重试相关的事件 Payload 转换，是否能够保留错误代码但过滤剥离具体的错误敏感信息，防止日志明文泄露。"""
        runtime = RetryPolicyRuntime()
        step = WorkflowStep(id="fragile", type="agent", title="Fragile", retry_policy={"max_attempts": 2})
        decision = runtime.evaluate(step, attempt=1, elapsed_ms=5, error_code="TemporaryError")

        # 将可能携带提示词/原始报错的敏感文本输入，转化为事件日志负载
        payload = runtime.to_event_payload(step, decision, error_message="secret prompt contents")

        # 验证错误码和步骤 ID 正常导出，但 payload 字符串绝不应包含敏感字串 'secret'
        self.assertEqual(payload["step_id"], "fragile")
        self.assertEqual(payload["error_code"], "TemporaryError")
        self.assertNotIn("secret", str(payload))


class WorkflowStateStoreTests(unittest.TestCase):
    """测试工作流状态存储（WorkflowStateStore）及回滚计划行为的测试类。"""

    def test_records_run_and_checkpoint_history(self):
        """验证历史记录中是否能完整录入运行启动、检查点打桩和运行结束事件。"""
        store = WorkflowStateStore()

        store.record_run_started("task_1", "run_1", start_step_id="a")
        store.record_checkpoint(
            "task_1",
            {"run_id": "run_1", "last_completed_step_id": "a", "next_step_id": "b", "status": "running"},
        )
        store.record_run_finished("task_1", "run_1", status="completed")

        history = store.run_history("task_1")
        checkpoints = store.checkpoint_history("task_1")

        # 检查事件链头尾
        self.assertEqual(history[0]["event"], "run.started")
        self.assertEqual(history[-1]["event"], "run.finished")
        self.assertEqual(checkpoints[0]["last_completed_step_id"], "a")

    def test_rollback_plan_selects_previous_complete_checkpoint(self):
        """验证回滚计划器在步骤失败时，能否正确定位并回滚到最近已成功提交的检查点节点。"""
        store = WorkflowStateStore()
        store.record_checkpoint("task_1", {"last_completed_step_id": "a", "next_step_id": "b", "status": "running"})
        store.record_checkpoint("task_1", {"last_completed_step_id": "b", "next_step_id": "c", "status": "running"})
        planner = WorkflowRollbackPlanner(store)

        # 假设在步骤 c 处运行失败
        plan = planner.plan_rollback("task_1", failed_step_id="c")

        # 回滚节点应为上一个成功提交的节点 b，丢弃不完整的步骤 c
        self.assertEqual(plan.rollback_to_step_id, "b")
        self.assertEqual(plan.resume_step_id, "c")
        self.assertEqual(plan.discarded_step_ids, ["c"])

    def test_store_can_restore_from_storage_events(self):
        """验证状态存储能否通过一组存储层传来的底层通用 Event 对象的日志进行还原与进度追踪。"""
        class EventObj:
            """虚拟的事件对象格式包装器。"""
            def __init__(self, type, payload):
                self.type = type
                self.payload = payload

        events = [
            EventObj("workflow.run.started", {"run_id": "run_1", "start_step_id": "a"}),
            EventObj("workflow.step.completed", {"step_id": "a", "run_id": "run_1"}),
            EventObj("workflow.run.completed", {"run_id": "run_1", "task_status": "completed"}),
        ]

        store = WorkflowStateStore.from_events("task_1", events)

        # 校验还原后的历史和最近的检查点已成功记录
        self.assertEqual(store.run_history("task_1")[0]["run_id"], "run_1")
        self.assertEqual(store.checkpoint_history("task_1")[0]["last_completed_step_id"], "a")


class WorkflowEngineRetryIntegrationTests(unittest.TestCase):
    """集成测试：验证在 WorkflowEngine 链路中对重试及熔断进行控制流联调。"""

    def test_agent_step_retries_once_then_succeeds(self):
        """验证当智能体任务发生偶发性错误（首次抛 RuntimeError 之后再成功）时，重试调度是否能安排并在第二次运行成功。"""
        import tempfile
        from pathlib import Path

        from app.services.fakes import FakeKnowledge, FakeStorage
        from app.services.task_service import TaskService
        from app.services.tool_service import ToolService
        from app.workflows.engine import WorkflowEngine

        class FlakyLLM:
            """模拟首轮抛出临时异常而第二轮恢复正常的模型交互服务。"""
            def __init__(self):
                self.calls = 0

            def invoke_stream(self, role, prompt, context, telemetry=None):
                self.calls += 1
                if self.calls == 1:
                    # 模拟模型首次调用网络抖动崩溃
                    raise RuntimeError("temporary provider outage")
                yield "ok"

            def invoke(self, role, prompt, context):
                from app.core.ports import LLMResult
                return LLMResult(content="PASS", structured={"role": role})

        workflow = WorkflowSpec(
            name="retry_agent",
            version="1.0",
            steps=[
                WorkflowStep(id="draft", type="agent", title="Draft", role="PM", retry_policy={"max_attempts": 2}),
                WorkflowStep(id="final", type="checkpoint", title="Final"),
            ],
        )
        definition = TaskDefinition(
            type="retry_agent",
            display_name="Retry Agent",
            input_schema={"required": ["username"], "properties": {"username": {"type": "string"}}},
            workflow=workflow,
            tool_policy=ToolPolicy(task_type="retry_agent"),
        )
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        storage = FakeStorage(Path(temp.name))
        engine = WorkflowEngine(
            tool_service=ToolService.default(root=Path(temp.name), knowledge=FakeKnowledge()),
            llm=FlakyLLM(),
            storage=storage,
        )
        service = TaskService(registry={"retry_agent": definition}, engine=engine, storage=storage)
        task = service.create_task("retry_agent", {"username": "alice", "goal": "retry"})

        result = service.run_task(task.task_id)

        # 断言最终执行成功，且状态记录中包含重试计划与完成事件
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        event_types = [event.type for event in storage.read_events(task.task_id)]
        self.assertIn("workflow.step.retry_scheduled", event_types)
        self.assertIn("workflow.step.completed", event_types)

    def test_agent_step_emits_retry_exhausted_when_attempts_run_out(self):
        """验证当智能体任务发生持续性崩溃，且重试次数耗尽后，引擎是否能记录重试耗尽日志并在事件负载中隐藏敏感字词。"""
        import tempfile
        from pathlib import Path

        from app.services.fakes import FakeKnowledge, FakeStorage
        from app.services.task_service import TaskService
        from app.services.tool_service import ToolService
        from app.workflows.engine import WorkflowEngine

        class FailingLLM:
            """模拟始终调用失败的测试 LLM 服务。"""
            def invoke_stream(self, role, prompt, context, telemetry=None):
                # 异常信息中带有机密文本 "private prompt"
                raise RuntimeError("provider down with private prompt")

            def invoke(self, role, prompt, context):
                from app.core.ports import LLMResult
                return LLMResult(content="FAIL", structured={"role": role})

        workflow = WorkflowSpec(
            name="retry_agent",
            version="1.0",
            steps=[WorkflowStep(id="draft", type="agent", title="Draft", role="PM", retry_policy={"max_attempts": 2})],
        )
        definition = TaskDefinition(
            type="retry_agent",
            display_name="Retry Agent",
            input_schema={"required": ["username"], "properties": {"username": {"type": "string"}}},
            workflow=workflow,
            tool_policy=ToolPolicy(task_type="retry_agent"),
        )
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        storage = FakeStorage(Path(temp.name))
        engine = WorkflowEngine(
            tool_service=ToolService.default(root=Path(temp.name), knowledge=FakeKnowledge()),
            llm=FailingLLM(),
            storage=storage,
        )
        service = TaskService(registry={"retry_agent": definition}, engine=engine, storage=storage)
        task = service.create_task("retry_agent", {"username": "alice", "goal": "retry"})

        result = service.run_task(task.task_id)

        # 任务由于持续失败，状态应当判定为 FAILED
        self.assertEqual(result.status, TaskStatus.FAILED)
        retry_events = [event.to_dict() for event in storage.read_events(task.task_id) if event.type == "workflow.step.retry_exhausted"]
        
        # 验证产生了 1 次重试尝试耗尽事件，异常码为 RuntimeError 且脱密后没有泄露 "private prompt" 字样
        self.assertEqual(len(retry_events), 1)
        self.assertEqual(retry_events[0]["payload"]["error_code"], "RuntimeError")
        self.assertNotIn("private prompt", str(retry_events[0]["payload"]))


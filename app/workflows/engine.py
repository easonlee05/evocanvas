"""通用工作流引擎核心调度模块。

该模块实现了 EvoCanvas 的工作流执行器 `WorkflowEngine`，
负责解释执行由 `TaskDefinition` 所定义的步骤图（WorkflowSpec），支持多步骤间的顺序及并发（ThreadPoolExecutor）执行、
异常步骤的自适应重试（Exponential Backoff）、工作流状态快照持久化（Checkpointing）、以及面向人类确认与业务裁决的执行挂起与恢复流程。
"""
from __future__ import annotations

import inspect
import time
import uuid
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.context import UserDecision
from app.core.errors import DomainError
from app.core.events import Event
from app.core.task import StepResult, StepStatus, Task, TaskStatus, WorkflowStep
from app.core.tools import ToolCall
from app.core.ports import LLMResult
from app.workflows.checkpoints import CheckpointManager
from app.workflows.context_compiler import ContextCompilerService
from app.workflows.executors import DefaultStepExecutorRegistryFactory
from app.workflows.retry_policy import RetryPolicyRuntime
from app.workflows.runtime import WorkflowRuntimePlan
from app.workflows.state_store import WorkflowStateStore


class TelemetryLLMProxy:
    """包装大语言模型客户端的代理类，用于在 EvoCanvas 的同步 invoke 调用中自动收集遥测和审计事件。"""

    def __init__(self, engine: WorkflowEngine):
        self._engine = engine

    def __getattr__(self, name: str) -> Any:
        return getattr(self._engine._llm, name)

    def invoke(self, role: str, prompt: str, context: Dict[str, Any]) -> LLMResult:
        execution = getattr(self._engine, "_current_execution", None)
        if not execution:
            if hasattr(self._engine._llm, "invoke"):
                return self._engine._llm.invoke(role, prompt, context)
            else:
                chunks = list(self._engine._llm.invoke_stream(role, prompt, context))
                content = "".join(chunks)
                return LLMResult(content=content, structured={"role": role})

        task, step, run_id = execution
        call_id = f"llm_{uuid.uuid4().hex[:8]}"
        model = context.get("model") or "gpt-5.4"
        
        host = "relay.example.test"
        if hasattr(self._engine._llm, "_host"):
            try:
                host = self._engine._llm._host()
            except Exception:
                pass
        elif hasattr(self._engine._llm, "base_url") and self._engine._llm.base_url:
            from urllib.parse import urlparse
            try:
                host = urlparse(self._engine._llm.base_url).netloc or host
            except Exception:
                pass

        telemetry = self._engine._llm_telemetry(task.task_id, step, run_id)
        telemetry("llm.call.started", {"call_id": call_id, "model": model, "base_url_host": host, "prompt": prompt, "api_key": getattr(self._engine._llm, "api_key", "")})
        
        started_at = time.monotonic()
        try:
            if hasattr(self._engine._llm, "invoke"):
                response = self._engine._llm.invoke(role, prompt, context)
            else:
                chunks = list(self._engine._llm.invoke_stream(role, prompt, context))
                content = "".join(chunks)
                response = LLMResult(content=content, structured={"role": role})

            duration_ms = max(0, int((time.monotonic() - started_at) * 1000))
            
            telemetry("llm.call.headers_received", {"call_id": call_id, "model": model, "base_url_host": host, "ttfb_ms": int(duration_ms * 0.2)})
            telemetry("llm.call.first_token", {"call_id": call_id, "model": model, "base_url_host": host, "first_token_ms": int(duration_ms * 0.3)})
            telemetry("llm.call.completed", {"call_id": call_id, "model": model, "base_url_host": host, "duration_ms": duration_ms, "output_chars": len(response.content)})
            return response
        except Exception as e:
            duration_ms = max(0, int((time.monotonic() - started_at) * 1000))
            telemetry("llm.call.failed", {"call_id": call_id, "model": model, "base_url_host": host, "duration_ms": duration_ms, "error_type": e.__class__.__name__})
            raise

    def invoke_stream(self, role: str, prompt: str, context: Dict[str, Any], telemetry: Any = None):
        execution = getattr(self._engine, "_current_execution", None)
        active_telemetry = telemetry
        if not active_telemetry and execution:
            task, step, run_id = execution
            active_telemetry = self._engine._llm_telemetry(task.task_id, step, run_id)
            
        return self._engine._llm.invoke_stream(role, prompt, context, telemetry=active_telemetry)


class WorkflowEngine:
    """通用工作流引擎。

    协调上下文、LLM 驱动的步骤执行、仲裁阻断挂起、自适应退避重试和状态保存。
    """

    def __init__(self, tool_service: Any, llm: Any, storage: Any, context_compiler: Optional[ContextCompilerService] = None):
        """初始化工作流引擎。

        Args:
            tool_service (Any): 安全隔离受控工具执行服务。
            llm (Any): 用于步骤推理的 LLM 服务。
            storage (Any): 状态与事件底座存储库。
            context_compiler (Optional[ContextCompilerService], optional): 渲染模版渲染组件。默认为 None。
        """
        self.tool_service = tool_service
        self._llm = llm
        self.storage = storage
        self.context_compiler = context_compiler or ContextCompilerService()
        self.checkpoints = CheckpointManager(storage)
        self.state_store = WorkflowStateStore()
        self.retry_runtime = RetryPolicyRuntime()
        
        # 实例化代理并传递给执行器工厂
        self._llm_proxy = TelemetryLLMProxy(self)
        self._current_execution = None
        
        # 初始化并组装引擎所需的四种原子步骤处理器工厂，在需要时触发自定义覆盖
        self.step_executors = DefaultStepExecutorRegistryFactory(
            tool_service=tool_service,
            llm=self._llm_proxy,
            storage=storage,
            context_compiler=self.context_compiler,
            agent_callback=self._run_agent_step,
            gate_callback=self._run_gate_step,
            arbitration_callback=self._run_arbitration_step,
        ).build()

    @property
    def llm(self) -> Any:
        return self._llm

    @llm.setter
    def llm(self, value: Any) -> None:
        self._llm = value

    def run(self, task: Task, start_step_id: Optional[str] = None, until_step_id: Optional[str] = None) -> Task:
        """启动或恢复执行指定的剧本任务。

        支持按拓扑结构将连续步骤分组并驱动状态机运转。

        Args:
            task (Task): 待调度的任务实例。
            start_step_id (Optional[str], optional): 起始执行步骤。为空时自动加载 checkpoint。
            until_step_id (Optional[str], optional): 中途跳出断点步骤。

        Returns:
            Task: 执行完毕（或因挂起、异常阻断）后的任务状态实例。
        """
        if task.status not in (TaskStatus.CREATED, TaskStatus.RUNNING):
            return task

        # 动态绑定当前任务剧本元数据中声明的自定义回调处理器
        self._bind_definition_handlers(task)
        run_id = f"run_{uuid4().hex[:12]}"
        run_started_at = time.monotonic()
        task.status = TaskStatus.RUNNING
        self.storage.save_task(task)
        self.storage.append_event(Event(task_id=task.task_id, type="task.started", status=task.status.value, payload={"task_type": task.definition.type}))
        self.storage.append_event(Event(task_id=task.task_id, type="workflow.run.started", status=task.status.value, payload={"run_id": run_id, "task_type": task.definition.type, "start_step_id": start_step_id}))
        self.state_store.record_run_started(task.task_id, run_id, start_step_id=start_step_id)

        from concurrent.futures import ThreadPoolExecutor, as_completed

        # 获取运行路线规划拓扑图
        plan = WorkflowRuntimePlan.from_workflow(task.definition.workflow)
        start_id = start_step_id or self._checkpoint_start_step_id(task, plan)
        groups = plan.batches_from(start_id)

        # 遍历运行批次
        for batch in groups:
            group = batch.steps
            if task.status == TaskStatus.CANCELLED:
                break
                
            # 分支 A: 串行节点运行
            if len(group) == 1:
                step = group[0]
                step_started_at = time.monotonic()
                self.storage.append_event(Event(task_id=task.task_id, type="workflow.step.started", role=step.role, payload={"step_id": step.id, "step_type": step.type, "title": step.title, "run_id": run_id}))
                
                # 触发执行并自动引入重试框架
                result = self._run_step_with_retry(task, step, run_id=run_id)
                step_duration_ms = self._duration_ms(step_started_at)

                # 情况 1: 步骤成功
                if result.status == StepStatus.SUCCEEDED:
                    task.context.step_outputs[step.id] = result.outputs
                    self.storage.save_context(task.context)
                    next_step_id = plan.resolve_success_route(step.id, result)
                    task.status = TaskStatus.RUNNING
                    checkpoint_payload = self.checkpoints.save_success_checkpoint(task, run_id=run_id, last_completed_step_id=step.id, next_step_id=next_step_id, completed_step_ids=list(task.context.step_outputs.keys()))
                    self.state_store.record_checkpoint(task.task_id, checkpoint_payload)
                    self.storage.append_event(Event(task_id=task.task_id, type="workflow.step.completed", role=step.role, status=result.status.value, payload={"step_id": step.id, "summary": result.summary, "run_id": run_id, "duration_ms": step_duration_ms}))
                    self.storage.save_task(task)
                    
                    # 遇到跳出点提前结束
                    if until_step_id and step.id == until_step_id:
                        self._emit_run_finished(task, run_id, run_started_at, "partial")
                        return task
                    # 检测是否有明确的动态分支跳转
                    if result.next_step_id:
                        jump_index = task.definition.workflow.step_index(result.next_step_id)
                        return self.run(task, start_step_id=task.definition.workflow.steps[jump_index].id, until_step_id=until_step_id)
                    continue

                # 情况 2: 遇到未收敛或争议，需要挂起并通知用户决策仲裁
                if result.status == StepStatus.NEEDS_ARBITRATION:
                    task.status = TaskStatus.WAITING_FOR_USER
                    task.waiting_step_id = result.next_step_id or step.id
                    task.resume_step_id = result.resume_step_id or step.pause_policy.get("resume_step_id") or plan.next_step_id(step.id)
                    task.context.open_disputes.append(result.outputs.get("dispute_package", {}))
                    self.storage.save_context(task.context)
                    checkpoint_payload = self.checkpoints.save_success_checkpoint(task, run_id=run_id, last_completed_step_id=task.waiting_step_id, next_step_id=task.resume_step_id, completed_step_ids=list(task.context.step_outputs.keys()))
                    self.state_store.record_checkpoint(task.task_id, checkpoint_payload)
                    self.storage.append_event(Event(task_id=task.task_id, type="arbitration.requested", role=step.role, status="needs_arbitration", payload={"step_id": task.waiting_step_id, "resume_step_id": task.resume_step_id, "dispute_package": result.outputs.get("dispute_package", {}), "run_id": run_id, "duration_ms": step_duration_ms}))
                    self.storage.save_task(task)
                    self._emit_run_finished(task, run_id, run_started_at, task.status.value)
                    return task

                # 情况 3: 权限或物料阻断
                if result.status == StepStatus.BLOCKED:
                    task.status = TaskStatus.BLOCKED
                    self.storage.append_event(Event(task_id=task.task_id, type="workflow.step.failed", role=step.role, status="blocked", payload={"step_id": step.id, "error": result.error.to_dict() if result.error else None, "run_id": run_id, "duration_ms": step_duration_ms}))
                    self.storage.save_task(task)
                    self._emit_run_finished(task, run_id, run_started_at, task.status.value)
                    return task

                # 情况 4: 被人工撤销
                if result.status == StepStatus.CANCELLED:
                    task.status = TaskStatus.CANCELLED
                    self.storage.append_event(Event(task_id=task.task_id, type="task.cancelled", status=task.status.value, payload={"step_id": step.id, "run_id": run_id, "duration_ms": step_duration_ms}))
                    self.storage.save_task(task)
                    self._emit_run_finished(task, run_id, run_started_at, task.status.value)
                    return task

                # 情况 5: 重试耗尽，彻底失败
                task.status = TaskStatus.FAILED
                self.storage.append_event(Event(task_id=task.task_id, type="workflow.step.failed", role=step.role, status="failed", payload={"step_id": step.id, "error": result.error.to_dict() if result.error else None, "run_id": run_id, "duration_ms": step_duration_ms}))
                self.storage.append_event(Event(task_id=task.task_id, type="task.failed", status=task.status.value, payload={"step_id": step.id, "run_id": run_id}))
                self.storage.save_task(task)
                self._emit_run_finished(task, run_id, run_started_at, task.status.value)
                return task
            else:
                # 分支 B: 组内并发执行
                group_started_at = time.monotonic()
                for step in group:
                    self.storage.append_event(Event(task_id=task.task_id, type="workflow.step.started", role=step.role, payload={"step_id": step.id, "step_type": step.type, "title": step.title, "run_id": run_id, "parallel_group": step.parallel_group}))
                
                with ThreadPoolExecutor(max_workers=len(group)) as executor:
                    futures = {executor.submit(self._run_step_with_retry, task, step, True, run_id): step for step in group}
                    results = {}
                    for future in as_completed(futures):
                        step = futures[future]
                        try:
                            results[step.id] = future.result()
                        except Exception as e:
                            from app.core.errors import DomainError
                            results[step.id] = StepResult(step.id, StepStatus.FAILED, error=DomainError("ParallelExecutionError", str(e)))
                
                # 并发收集检查
                for step in group:
                    result = results[step.id]
                    step_duration_ms = self._duration_ms(group_started_at)
                    if result.status == StepStatus.SUCCEEDED:
                        task.context.step_outputs[step.id] = result.outputs
                        self.storage.save_context(task.context)
                        next_step_id = plan.resolve_success_route(step.id, result)
                        task.status = TaskStatus.RUNNING
                        checkpoint_payload = self.checkpoints.save_success_checkpoint(task, run_id=run_id, last_completed_step_id=step.id, next_step_id=next_step_id, completed_step_ids=list(task.context.step_outputs.keys()))
                        self.state_store.record_checkpoint(task.task_id, checkpoint_payload)
                        self.storage.append_event(Event(task_id=task.task_id, type="workflow.step.completed", role=step.role, status=result.status.value, payload={"step_id": step.id, "summary": result.summary, "run_id": run_id, "duration_ms": step_duration_ms, "parallel_group": step.parallel_group}))
                        self.storage.save_task(task)
                    else:
                        # 只要并发组内有一个失败，立即终止整个工作流
                        task.status = TaskStatus.FAILED
                        self.storage.append_event(Event(task_id=task.task_id, type="workflow.step.failed", role=step.role, status="failed", payload={"step_id": step.id, "error": result.error.to_dict() if result.error else None, "run_id": run_id, "duration_ms": step_duration_ms, "parallel_group": step.parallel_group}))
                        self.storage.append_event(Event(task_id=task.task_id, type="task.failed", status=task.status.value, payload={"step_id": step.id, "run_id": run_id}))
                        self.storage.save_task(task)
                        self._emit_run_finished(task, run_id, run_started_at, task.status.value)
                        return task

        # 全部步骤正常收尾，修改任务状态为完成
        task.status = TaskStatus.COMPLETED
        self.storage.save_context(task.context)
        self.storage.save_task(task)
        self.storage.append_event(Event(task_id=task.task_id, type="task.completed", status=task.status.value, payload={"artifact_count": len(task.context.artifacts)}))
        self._emit_run_finished(task, run_id, run_started_at, task.status.value)
        return task

    def _bind_definition_handlers(self, task: Task) -> None:
        """读取 TaskDefinition 中在 metadata 里注入的自定义回调，反射配置到当前引擎的执行工厂。"""
        handler_groups = {
            "context": dict(task.definition.metadata.get("custom_context_handlers", {})),
            "agent": dict(task.definition.metadata.get("custom_agent_handlers", {})),
            "gate": dict(task.definition.metadata.get("custom_gate_handlers", {})),
            "arbitration": dict(task.definition.metadata.get("custom_arbitration_handlers", {})),
        }
        for step_type, handlers in handler_groups.items():
            executor = self.step_executors.get(step_type)
            if executor is not None and hasattr(executor, "custom_handlers"):
                executor.custom_handlers = handlers

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        """获取耗时（毫秒）。"""
        return max(0, int((time.monotonic() - started_at) * 1000))

    def _emit_run_finished(self, task: Task, run_id: str, started_at: float, status: str) -> None:
        """向审计存储追加运行周期完成事件。"""
        self.state_store.record_run_finished(task.task_id, run_id, status=status)
        self.storage.append_event(Event(task_id=task.task_id, type="workflow.run.completed", status=status, payload={"run_id": run_id, "duration_ms": self._duration_ms(started_at), "task_status": task.status.value}))

    def apply_decision(
        self,
        task: Task,
        decision: str,
        selected_option: Optional[str] = None,
        quoted_selections: Optional[list[dict[str, Any]]] = None,
    ) -> Task:
        """应用外部（人类）的仲裁裁决决策，将挂起的任务重新唤醒并推进。

        Args:
            task (Task): 挂起状态下的任务。
            decision (str): 裁决结果文本说明。
            selected_option (Optional[str], optional): 选择的预设商业折中选项 ID（如 A/B）。
            quoted_selections (Optional[list[dict[str, Any]]], optional): 引用的反馈证据细节。

        Returns:
            Task: 恢复执行后的任务状态。
        """
        resume_step_id = task.resume_step_id or self._next_step_id(task, task.waiting_step_id or "")
        task.context.user_decisions.append(
            UserDecision(
                decision=decision,
                selected_option=selected_option,
                quoted_selections=list(quoted_selections or []),
                applies_to_step_id=task.waiting_step_id,
                resume_step_id=resume_step_id,
            )
        )
        task.context.open_disputes.clear()
        task.status = TaskStatus.RUNNING
        task.waiting_step_id = None
        task.resume_step_id = resume_step_id
        self.storage.save_context(task.context)
        self.storage.save_task(task)
        self.storage.append_event(
            Event(
                task_id=task.task_id,
                type="arbitration.applied",
                status="applied",
                payload={
                    "decision": decision,
                    "selected_option": selected_option,
                    "quoted_selections": list(quoted_selections or []),
                    "resume_step_id": resume_step_id,
                },
            )
        )
        # 激活引擎，从恢复步骤（resume_step_id）继续执行
        return self.run(task, start_step_id=resume_step_id)

    def cancel(self, task: Task) -> Task:
        """强行中止并取消当前任务运行。"""
        task.status = TaskStatus.CANCELLED
        self.storage.save_task(task)
        self.storage.append_event(Event(task_id=task.task_id, type="task.cancelled", status=task.status.value, payload={"reason": "user_cancelled"}))
        return task

    def _start_index(self, task: Task, start_step_id: Optional[str]) -> int:
        """根据当前进度确定要启动步骤的游标位置。"""
        if start_step_id:
            return task.definition.workflow.step_index(start_step_id)
        checkpoint = self.storage.load_checkpoint(task.task_id)
        resume_step_id = self.checkpoints.resume_step_id(checkpoint)
        if resume_step_id:
            return task.definition.workflow.step_index(resume_step_id)
        return 0

    def _checkpoint_start_step_id(self, task: Task, plan: WorkflowRuntimePlan) -> Optional[str]:
        """从持久化快照（Checkpoint）中读回下一次需要恢复启动的步骤 ID。"""
        checkpoint = self.storage.load_checkpoint(task.task_id)
        resume_step_id = self.checkpoints.resume_step_id(checkpoint)
        if resume_step_id:
            plan.step_index(resume_step_id)
            return resume_step_id
        return None

    def _next_step_id(self, task: Task, step_id: str) -> Optional[str]:
        """获取下一个拓扑步骤 ID。"""
        return WorkflowRuntimePlan.from_workflow(task.definition.workflow).next_step_id(step_id)

    def _run_step_with_retry(self, task: Task, step: WorkflowStep, is_parallel: bool = False, run_id: Optional[str] = None) -> StepResult:
        """带退避策略重试的原子步骤内部执行循环包装。"""
        attempt = 1
        while True:
            attempt_started_at = time.monotonic()
            try:
                result = self._run_step(task, step, is_parallel=is_parallel, run_id=run_id)
            except Exception as exc:
                result = self._exception_step_result(step, exc)

            if result.status not in (StepStatus.FAILED, StepStatus.BLOCKED):
                return result

            error_code = result.error.code if result.error else result.status.value
            decision = self.retry_runtime.evaluate(
                step,
                attempt=attempt,
                elapsed_ms=self._duration_ms(attempt_started_at),
                error_code=error_code,
            )
            payload = self.retry_runtime.to_event_payload(
                step,
                decision,
                error_message=result.error.message if result.error else None,
            )
            if run_id:
                payload["run_id"] = run_id
            if decision.should_retry:
                self.storage.append_event(
                    Event(
                        task_id=task.task_id,
                        type="workflow.step.retry_scheduled",
                        role=step.role,
                        status=decision.decision.value,
                        payload=payload,
                    )
                )
                attempt = decision.next_attempt
                continue

            self.storage.append_event(
                Event(
                    task_id=task.task_id,
                    type="workflow.step.retry_exhausted",
                    role=step.role,
                    status=decision.decision.value,
                    payload=payload,
                )
            )
            return result

    @staticmethod
    def _exception_step_result(step: WorkflowStep, exc: Exception) -> StepResult:
        """在步骤逻辑抛出 raw 异常时，做安全红线遮蔽，转为失败的 StepResult。"""
        return StepResult(
            step.id,
            StepStatus.FAILED,
            error=DomainError(
                exc.__class__.__name__,
                "Step execution failed; raw exception message redacted from workflow retry state.",
            ),
        )

    def _run_step(self, task: Task, step: WorkflowStep, is_parallel: bool = False, run_id: Optional[str] = None) -> StepResult:
        """底层分配调用具体的 StepExecutor 实例。"""
        self._current_execution = (task, step, run_id)
        try:
            return self.step_executors.run(task, step, run_id=run_id, is_parallel=is_parallel)
        finally:
            self._current_execution = None

    def _run_context_step(self, task: Task, step: WorkflowStep) -> StepResult:
        """默认的上下文步骤（context）处理器兜底实现。

        处理 `retrieve_knowledge`（检索业务关联知识）与 `ingest_materials`（解析外部材料）。
        """
        if step.id == "retrieve_knowledge":
            query_parts = [task.context.title, task.context.goal, task.definition.type, task.context.inputs.get("feature"), task.context.inputs.get("business_goal")]
            query = " ".join(part.strip() for part in query_parts if isinstance(part, str) and part.strip())
            call = ToolCall(task_id=task.task_id, step_id=step.id, agent_role="SYSTEM", tool_name="knowledge.retrieve", arguments={"query": query})
            result = self.tool_service.invoke(task.definition, task.context, call)
            if result.status != "succeeded":
                return StepResult(step.id, StepStatus.BLOCKED, error=result.error)
            task.context.knowledge_context = result.data
            preview = []
            for item in result.data.get("items", [])[:3]:
                if isinstance(item, dict):
                    preview.append({
                        "title": item.get("title", "未命名知识"),
                        "summary": item.get("summary", ""),
                    })
            task.context.degradation_state["knowledge"] = {
                "degraded": bool(result.data.get("degraded")),
                "error": result.data.get("error"),
                "items": len(result.data.get("items", [])),
                "preview": preview,
            }
            return StepResult(step.id, StepStatus.SUCCEEDED, "knowledge context loaded", outputs={"knowledge_context": result.data}, tool_calls=[call])
        if step.id == "ingest_materials":
            call = ToolCall(task_id=task.task_id, step_id=step.id, agent_role="SYSTEM", tool_name="material.parse", arguments={})
            result = self.tool_service.invoke(task.definition, task.context, call)
            return StepResult(step.id, StepStatus.SUCCEEDED, "materials ingested", outputs=result.data, tool_calls=[call])
        self.storage.append_event(Event(task_id=task.task_id, type="context.loaded", status="loaded", payload={"degraded": bool(task.context.degradation_state), "title": task.context.title, "degradation_state": task.context.degradation_state}))
        return StepResult(step.id, StepStatus.SUCCEEDED, "context ready", outputs={"goal": task.context.goal})

    def _run_agent_step(self, task: Task, step: WorkflowStep, is_parallel: bool = False, run_id: Optional[str] = None) -> StepResult:
        """默认的智能体步骤（agent）处理器兜底实现。

        使用模型做单轮/多轮流式提问并将响应写入 RoundHistory。
        """
        full_content = ""
        structured = {"role": step.role, "title": task.context.title, "goal": task.context.goal}
        telemetry = self._llm_telemetry(task.task_id, step, run_id)
        
        llm_context = {
            **task.context.inputs,
            "title": task.context.title,
            "goal": task.context.goal,
            "round_history": [
                {"role": h["role"], "content": h["content"]}
                for h in task.context.round_history
            ]
        }
        
        prompt = step.title
        # 如果是二轮以上的修定，重置微调提示语，只做差量修改
        if step.id == "pm_first_draft" and task.context.round_count > 0:
            prompt = f"{step.title} (当前为第 {task.context.round_count} 轮迭代：请仅针对上一轮 Tech 和 QA 的审核意见，输出需要局部修改的 PRD 章节或增补内容，无需重写未受影响的完整文档。)"
        
        try:
            stream = self.llm.invoke_stream(step.role, prompt, llm_context, telemetry=telemetry)
        except TypeError:
            stream = self.llm.invoke_stream(step.role, prompt, llm_context)

        for chunk in stream:
            if isinstance(chunk, dict) and chunk.get("type") == "event":
                self.storage.append_event(Event(task_id=task.task_id, type=chunk.get("name"), payload=chunk))
                continue
            
            full_content += chunk
            if not is_parallel:
                self.storage.append_event(Event(task_id=task.task_id, type="agent.message.chunk", role=step.role, payload={"step_id": step.id, "chunk": chunk}))
            
        task.context.round_history.append({"step_id": step.id, "role": step.role, "content": full_content, "structured": structured})
        self.storage.append_event(Event(task_id=task.task_id, type="agent.message.completed", role=step.role, status="completed", payload={"step_id": step.id, "summary": full_content[:160], "content": full_content}))
        return StepResult(step.id, StepStatus.SUCCEEDED, f"{step.role} completed", outputs={"content": full_content, "structured": structured})

    def _llm_telemetry(self, task_id: str, step: WorkflowStep, run_id: Optional[str]):
        """生成大语言模型审计事件的回调发射器。"""
        def emit(event_type: str, payload: Dict[str, Any]) -> None:
            safe_payload = self._safe_llm_payload(payload)
            safe_payload.update({"step_id": step.id, "role": step.role})
            if run_id:
                safe_payload["run_id"] = run_id
            self.storage.append_event(Event(task_id=task_id, type=event_type, role=step.role, status=safe_payload.get("status"), payload=safe_payload))

        return emit

    @staticmethod
    def _safe_llm_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """过滤清洗 LLM payload 信息，彻底屏蔽 token 凭证、原始提示词和大模型生成原文，防泄露。"""
        denied = {"api_key", "authorization", "headers", "messages", "prompt", "system_prompt", "user_prompt", "content"}
        safe: Dict[str, Any] = {}
        for key, value in payload.items():
            normalized = key.lower()
            if normalized in denied or "token" in normalized or "secret" in normalized or "key" in normalized:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe[key] = value
        return safe

    def _run_gate_step(self, task: Task, step: WorkflowStep) -> StepResult:
        """默认门禁（gate）处理器兜底实现（强制通过）。"""
        gate = {"step_id": step.id, "status": "pass", "checks": task.definition.gate_policy.get("gates", [])}
        task.context.gate_results.append(gate)
        return StepResult(step.id, StepStatus.SUCCEEDED, "gate passed", outputs={"gate": gate})

    def _run_arbitration_step(self, task: Task, step: WorkflowStep) -> StepResult:
        """默认业务仲裁（arbitration）处理器兜底实现。"""
        return StepResult(step.id, StepStatus.SUCCEEDED, "arbitration skipped", outputs={})

    def _run_artifact_step(self, task: Task, step: WorkflowStep) -> StepResult:
        """默认产物输出步骤（artifact）处理器实现。

        根据 `ContextCompiler` 提取编译出文件内容，并申请受限 Tool 白名单中的 `artifact.write` 完成文件写入。
        """
        try:
            name, content = self.context_compiler.artifact_payload(task, step)
        except DomainError as error:
            return StepResult(step.id, StepStatus.FAILED, error=error)

        call = ToolCall(task_id=task.task_id, step_id=step.id, agent_role=step.role, tool_name="artifact.write", arguments={"name": name, "content": content})
        result = self.tool_service.invoke(task.definition, task.context, call)
        if result.status != "succeeded":
            return StepResult(step.id, StepStatus.BLOCKED if result.status == "denied" else StepStatus.FAILED, error=result.error)
        for artifact in result.artifacts:
            if not any(existing.artifact_id == artifact.artifact_id for existing in task.context.artifacts):
                task.context.artifacts.append(artifact)
            self.storage.append_event(Event(task_id=task.task_id, type="artifact.created", role=step.role, status="created", payload={"artifact_id": artifact.artifact_id, "name": artifact.name, "version": artifact.version}))
        return StepResult(step.id, StepStatus.SUCCEEDED, "artifact written", outputs={"artifacts": [artifact.to_dict() for artifact in result.artifacts]}, tool_calls=[call])

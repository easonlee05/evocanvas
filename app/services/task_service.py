"""Application service for task creation, execution, decisions and cancellation."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from app.core.context import TaskContext
from app.core.events import Event
from app.core.task import Task, TaskDefinition, TaskStatus
from app.core.subagent import (
    SubagentDenyReason,
    SubagentRunStatus,
    SubagentScope,
    SubagentSpawnRequest,
)

# EvoCanvas 工作项与结构化交付合同
from app.core.work import WorkItem, WorkType, WorkStatus
from app.core.playbook import (
    ProductContext, SourceInput, Requirement, ProductConstraint,
    DecisionGate, DecisionOption, GateResolution, DecisionGateStatus, KnowledgeRef
)
from app.core.artifact_graph import (
    ArtifactGraph, ArtifactNode, ArtifactNodeType, ArtifactEdge, ArtifactEdgeType, ArtifactRef
)
from app.services.peer_adapter_service import PeerAdapterService


class TaskService:
    """任务生命周期管理与数据转换的应用服务。

    该类负责处理任务创建、运行、取消、删除等核心控制流，
    并提供将任务上下文整理为 EvoCanvas 工作项、产品上下文和交付资产图的接口。

    生命周期：
        通常在 Web 框架启动时作为单例被初始化，持有全局的 TaskDefinition 注册表、工作流引擎和持久化存储服务。
    """

    COMPATIBILITY_TYPE_ALIASES = {
        "manual": "legacy_manual",
        "legacy_manual": "legacy_manual",
        "prd": "legacy_prd",
        "legacy_prd": "legacy_prd",
    }

    def __init__(
        self,
        registry: Dict[str, TaskDefinition],
        engine: Any,
        storage: Any,
        peer_adapter: Any | None = None,
        canvas_execution: Any | None = None,
        canvas_tool_gateway: Any | None = None,
        tenant_id: str = "default",
        knowledge: Any | None = None,
    ):
        """初始化任务服务。

        Args:
            registry: 任务定义的注册表，映射任务类型到具体 TaskDefinition。
            engine: 工作流引擎实例，用于执行和恢复任务。
            storage: 持久化存储层实例，支持加载/保存 TaskContext 与 Task 实例，附加事件等。
            peer_adapter: AI 技术同事协作适配服务；未提供时使用空注册表实例。
            canvas_execution: 可选的 Canvas AgentExecutionPort；生产环境由 API 装配 PiRuntimeClient，
                测试环境可注入实现同一窄端口的 Fake。
            canvas_tool_gateway: Canvas Pi Runtime 使用的内部只读工具网关。
            tenant_id: 当前服务绑定的租户标识，用于内部工具调用范围校验。
            knowledge: 通用知识检索后端；Canvas 和健康检查可直接使用，不触发工作流执行引擎初始化。
        """
        self.registry = registry
        self.engine = engine
        self.storage = storage
        self.peer_adapter = peer_adapter or PeerAdapterService()
        self.canvas_execution = canvas_execution
        self.canvas_tool_gateway = canvas_tool_gateway
        self.tenant_id = tenant_id
        self.knowledge = knowledge
        self._running_tasks = set()

    def create_task(self, task_type: str, payload: Dict[str, Any]) -> Task:
        """创建新任务并保存初始上下文与任务实例。

        Args:
            task_type: 任务类型，支持入口别名标准化。
            payload: 创建任务所需的输入数据，包括 username, title, goal 等。

        Returns:
            Task: 初始化且状态为 CREATED 的 Task 实例。

        Raises:
            ValueError: 如果任务类型未知，或缺少 TaskDefinition 输入架构所要求的必需字段。
        """
        requested_task_type = task_type
        # 标准化任务类型，将入口别名映射为工作流规范键。
        public_task_type = self._normalize_task_type(task_type)
        if public_task_type not in self.registry:
            raise ValueError(f"unknown task type: {task_type}")
        definition = self.registry[public_task_type]
        self._validate_required(definition, payload)
        
        task_id = f"task_{uuid4().hex[:12]}"
        
        # 尝试从 payload 中提取 title、goal、constraints 并设定默认回退值
        title = payload.get("title") or payload.get("feature") or payload.get("module_name") or payload.get("business_domain") or public_task_type
        goal = payload.get("goal") or payload.get("business_goal") or payload.get("instructions") or title
        constraints = payload.get("constraints") or payload.get("user_constraints") or []
        if isinstance(constraints, str):
            constraints = [constraints]
            
        normalized_inputs = dict(payload)
        normalized_inputs.setdefault("requested_task_type", requested_task_type)
        normalized_inputs["task_type"] = public_task_type
        normalized_inputs["canonical_task_type"] = definition.type
        
        # 构建 1.0 的 TaskContext 上下文结构
        context = TaskContext(
            task_id=task_id,
            task_type=public_task_type,
            username=payload["username"],
            goal=goal,
            title=title,
            user_constraints=list(constraints),
            source_materials=[{"material_id": material_id} for material_id in payload.get("material_ids", [])],
            inputs=normalized_inputs,
        )
        task = Task(definition=definition, context=context, task_id=task_id, status=TaskStatus.CREATED)
        
        # 保存上下文与任务状态到持久化存储，并触发 task.created 事件
        self.storage.save_context(context)
        self.storage.save_task(task)
        self.storage.append_event(
            Event(
                task_id=task_id,
                type="task.created",
                status=task.status.value,
                payload={
                    "task_type": public_task_type,
                    "canonical_task_type": definition.type,
                    "title": title,
                },
            )
        )
        return task

    def run_task(self, task_id: str, until_step_id: Optional[str] = None) -> Task:
        """运行或恢复指定的任务。

        Args:
            task_id: 任务的唯一标识符。
            until_step_id: 任务运行的终止/暂停步骤节点标识符。

        Returns:
            Task: 运行/执行后的任务实例。
        """
        # 防止同一任务的并发执行，通过内存中的集合进行防重处理
        if task_id in self._running_tasks:
            return self.storage.load_task(task_id, self.registry)
        self._running_tasks.add(task_id)
        try:
            task = self.storage.load_task(task_id, self.registry)
            return self.engine.run(task, until_step_id=until_step_id)
        finally:
            self._running_tasks.discard(task_id)

    def apply_decision(
        self,
        task_id: str,
        decision: str,
        selected_option: Optional[str] = None,
        quoted_selections: Optional[list[dict[str, Any]]] = None,
    ) -> Task:
        """为处于等待用户决策状态的任务应用决策，并将其恢复执行。

        Args:
            task_id: 任务的唯一标识符。
            decision: 用户所做的决策说明或裁决内容。
            selected_option: 用户选择的决策分支选项 ID。
            quoted_selections: 包含引用的具体文本片段/选择范围。

        Returns:
            Task: 应用决策并尝试运行后的 Task 实例。
        """
        task = self.storage.load_task(task_id, self.registry)
        return self.engine.apply_decision(
            task,
            decision=decision,
            selected_option=selected_option,
            quoted_selections=quoted_selections,
        )

    def cancel_task(self, task_id: str) -> Task:
        """取消一个执行中或挂起的任务。

        Args:
            task_id: 任务的唯一标识符。

        Returns:
            Task: 状态更新为已取消的 Task 实例。
        """
        task = self.storage.load_task(task_id, self.registry)
        return self.engine.cancel(task)

    def delete_task(self, task_id: str) -> Task:
        """对任务进行软删除（标记删除）。

        Args:
            task_id: 任务的唯一标识符。

        Returns:
            Task: 标记为已删除状态的 Task 实例。
        """
        task = self.storage.load_task(task_id, self.registry)
        task.is_deleted = True
        task.deleted_at = datetime.now().isoformat()
        self.storage.save_task(task)
        return task

    def restore_task(self, task_id: str) -> Task:
        """恢复被软删除的任务。

        Args:
            task_id: 任务的唯一标识符。

        Returns:
            Task: 取消删除标记的 Task 实例。
        """
        task = self.storage.load_task(task_id, self.registry)
        task.is_deleted = False
        task.deleted_at = None
        self.storage.save_task(task)
        return task

    def permanent_delete_task(self, task_id: str) -> None:
        """永久删除指定的任务目录（硬删除）。

        Args:
            task_id: 任务的唯一标识符。
        """
        if hasattr(self.storage, "delete_task_directory"):
            self.storage.delete_task_directory(task_id)

    def get_task(self, task_id: str) -> Task:
        """获取指定任务的实例。

        Args:
            task_id: 任务的唯一标识符。

        Returns:
            Task: 从存储加载的任务实例。
        """
        return self.storage.load_task(task_id, self.registry)

    def fork_repair_work_item(self, review_task_id: str, review_result: Dict[str, Any]) -> Task:
        """从未通过的 Acceptance Review 派生下一轮修复 WorkItem。

        该方法只负责有界 fork，不自动执行修复或复审，避免无限自修复。
        """
        parent = self.storage.load_task(review_task_id, self.registry)
        current_iteration = int(parent.context.inputs.get("iteration", 0))
        max_iterations = int(parent.context.inputs.get("max_review_iterations", 2))
        review_cycle_id = parent.context.inputs.get("review_cycle_id") or f"review_cycle_{parent.task_id}"
        fix_tasks = list(review_result.get("fix_tasks") or [])

        if current_iteration >= max_iterations:
            self.storage.append_event(
                Event(
                    task_id=parent.task_id,
                    type="review.redo.max_iterations_reached",
                    status="blocked",
                    payload={
                        "iteration": current_iteration,
                        "max_review_iterations": max_iterations,
                        "review_cycle_id": review_cycle_id,
                        "verdict": review_result.get("verdict"),
                    },
                )
            )
            raise ValueError("max_review_iterations_reached")
        if not fix_tasks:
            raise ValueError("repair fork requires at least one fix task")

        repair_payload = {
            "username": parent.context.username,
            "business_intent": self._repair_business_intent(parent, fix_tasks),
            "title": f"Repair iteration {current_iteration + 1}: {parent.context.title}",
            "goal": "Apply Acceptance Review fix tasks while preserving machine_spec and acceptance_protocol.",
            "parent_work_id": parent.task_id,
            "iteration": current_iteration + 1,
            "review_cycle_id": review_cycle_id,
            "max_review_iterations": max_iterations,
            "fix_tasks": fix_tasks,
            "machine_spec": parent.context.inputs.get("machine_spec", ""),
            "acceptance_protocol": parent.context.inputs.get("acceptance_protocol", ""),
            "machine_spec_ref": parent.context.inputs.get("machine_spec_ref", ""),
            "acceptance_protocol_ref": parent.context.inputs.get("acceptance_protocol_ref", ""),
        }
        repair_task = self.create_task("spec_to_agent", repair_payload)
        self.storage.append_event(
            Event(
                task_id=parent.task_id,
                type="review.redo.forked",
                status="created",
                payload={
                    "parent_work_id": parent.task_id,
                    "repair_work_id": repair_task.task_id,
                    "review_cycle_id": review_cycle_id,
                    "iteration": current_iteration + 1,
                    "max_review_iterations": max_iterations,
                    "fix_task_count": len(fix_tasks),
                },
            )
        )
        return repair_task

    def spawn_formal_subtask(self, parent_task_id: str, request: SubagentSpawnRequest) -> Task:
        """Create a formal child task using the existing Task/WorkItem model."""
        parent = self.storage.load_task(parent_task_id, self.registry)
        if request.scope != SubagentScope.FORMAL_SUBTASK:
            raise ValueError("spawn_formal_subtask requires formal_subtask scope")
        if int(request.depth) > 2:
            raise ValueError(SubagentDenyReason.DEPTH_EXCEEDED.value)

        siblings = self._list_formal_subtasks(parent_task_id)
        if len(siblings) >= 3:
            raise ValueError(SubagentDenyReason.FANOUT_EXCEEDED.value)

        task_type = request.task_type or "spec_to_agent"
        payload = dict(request.input_excerpt)
        payload.setdefault("username", parent.context.username)
        payload.setdefault("title", request.goal)
        payload.setdefault("goal", request.goal)
        payload["subagent_scope"] = SubagentScope.FORMAL_SUBTASK.value
        payload["parent_task_id"] = parent.task_id
        payload["parent_work_id"] = parent.task_id
        payload["root_task_id"] = parent.context.inputs.get("root_task_id") or parent.task_id
        payload["subtask_type"] = request.subtask_type or "formal_subtask"
        payload["subtask_index"] = request.subtask_index if request.subtask_index is not None else len(siblings)
        payload["join_step_id"] = request.join_step_id
        payload["acceptance_slice"] = dict(request.acceptance_slice)
        payload["spawn_depth"] = int(request.depth)
        payload["review_cycle_id"] = payload.get("review_cycle_id") or parent.context.inputs.get("review_cycle_id")
        payload["max_review_iterations"] = payload.get("max_review_iterations") or parent.context.inputs.get("max_review_iterations", 2)
        child = self.create_task(task_type, payload)
        self.storage.append_event(
            Event(
                task_id=parent.task_id,
                type="subagent.run.created",
                status=SubagentRunStatus.CREATED.value,
                payload={
                    "scope": SubagentScope.FORMAL_SUBTASK.value,
                    "run_id": child.task_id,
                    "parent_task_id": parent.task_id,
                    "parent_session_id": "",
                    "root_task_id": payload["root_task_id"],
                    "depth": request.depth,
                    "execution_mode": "serial",
                    "budget": request.budget.to_dict(),
                    "used_tools": [],
                    "degradation_reason": "",
                },
            )
        )
        return child

    def join_formal_subtasks(self, parent_task_id: str) -> Dict[str, Any]:
        """Join completed formal subtasks into one aggregated delivery bundle."""
        parent = self.storage.load_task(parent_task_id, self.registry)
        children = self._list_formal_subtasks(parent_task_id)
        if not children:
            raise ValueError("no_formal_subtasks")

        terminal_statuses = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.BLOCKED}
        if any(child.status not in terminal_statuses for child in children):
            return {"ready": False, "child_task_ids": [child.task_id for child in children]}

        summaries = []
        diffs = []
        artifacts = []
        child_statuses = []
        for child in children:
            bundle = dict(child.context.inputs.get("delivery_bundle") or {})
            summaries.append(bundle.get("implementation_summary") or child.context.goal)
            diffs.append(bundle.get("diff") or "")
            artifacts.extend(bundle.get("artifacts") or [])
            child_statuses.append({"task_id": child.task_id, "status": child.status.value})

        joined_bundle = {
            "implementation_summary": "\n".join(summary for summary in summaries if summary),
            "diff": "\n".join(diff for diff in diffs if diff),
            "peer_target": "multiple_formal_subtasks",
            "artifacts": artifacts,
        }
        parent.context.inputs["delivery_bundle"] = joined_bundle
        parent.context.inputs["formal_subtask_join"] = {
            "ready": True,
            "child_task_ids": [child.task_id for child in children],
            "child_statuses": child_statuses,
        }
        parent.status = TaskStatus.COMPLETED
        self.storage.save_context(parent.context)
        self.storage.save_task(parent)
        self.storage.append_event(
            Event(
                task_id=parent.task_id,
                type="subagent.join.completed",
                status="completed",
                payload={
                    "scope": SubagentScope.FORMAL_SUBTASK.value,
                    "child_task_ids": [child.task_id for child in children],
                    "used_tools": [],
                    "degradation_reason": "",
                },
            )
        )
        return {"ready": True, "delivery_bundle": joined_bundle, "child_task_ids": [child.task_id for child in children]}

    def _fanout_formal_repair_subtasks(self, review_task_id: str, review_result: Dict[str, Any]) -> Task:
        """Create a coordinator repair task and child formal subtasks for independent fixes."""
        coordinator = self.fork_repair_work_item(review_task_id, review_result)
        child_ids = []
        for index, fix_task in enumerate(review_result.get("fix_tasks", [])):
            request = SubagentSpawnRequest(
                scope=SubagentScope.FORMAL_SUBTASK,
                goal=str(fix_task.get("title") or f"Repair subtask {index + 1}"),
                task_slice=str(fix_task.get("title") or "Repair one independent fix task"),
                input_refs=["fix_task"],
                input_excerpt={
                    "username": coordinator.context.username,
                    "business_intent": self._repair_business_intent(coordinator, [fix_task]),
                    "machine_spec": coordinator.context.inputs.get("machine_spec", ""),
                    "acceptance_protocol": coordinator.context.inputs.get("acceptance_protocol", ""),
                    "machine_spec_ref": coordinator.context.inputs.get("machine_spec_ref", ""),
                    "acceptance_protocol_ref": coordinator.context.inputs.get("acceptance_protocol_ref", ""),
                    "review_cycle_id": coordinator.context.inputs.get("review_cycle_id"),
                    "max_review_iterations": coordinator.context.inputs.get("max_review_iterations", 2),
                    "iteration": coordinator.context.inputs.get("iteration", 1),
                    "fix_tasks": [fix_task],
                },
                allowed_tools=[],
                output_schema={"implementation_summary": "string"},
                budget=self._default_formal_subtask_budget(len(review_result.get("fix_tasks", []))),
                depth=2,
                task_type="spec_to_agent",
                subtask_type="repair_fix_task",
                join_step_id="review.followup",
                acceptance_slice={"source_issue_ids": list(fix_task.get("source_issue_ids", []))},
                subtask_index=index,
            )
            child = self.spawn_formal_subtask(coordinator.task_id, request)
            child_ids.append(child.task_id)

        coordinator = self.storage.load_task(coordinator.task_id, self.registry)
        coordinator.context.inputs["latest_repair_work_ids"] = child_ids
        self.storage.save_context(coordinator.context)
        self.storage.save_task(coordinator)

        review_task = self.storage.load_task(review_task_id, self.registry)
        review_task.context.inputs["latest_repair_work_id"] = coordinator.task_id
        review_task.context.inputs["latest_repair_work_ids"] = child_ids
        self.storage.save_context(review_task.context)
        self.storage.save_task(review_task)
        return coordinator

    def handle_review_result(self, review_task_id: str) -> Optional[Task]:
        """处理 Acceptance Review 结果，并在需要修复时 fork 下一轮修复任务。"""
        task = self.storage.load_task(review_task_id, self.registry)
        review_result = task.context.step_outputs.get("review_result_compiler", {}).get("review_result", {})
        verdict = review_result.get("verdict")

        if verdict == "pass":
            self.storage.append_event(
                Event(
                    task_id=task.task_id,
                    type="review.redo.not_needed",
                    status="completed",
                    payload={"verdict": verdict},
                )
            )
            return None

        if verdict in {"changes_required", "blocked"}:
            if self._should_fanout_fix_tasks(review_result):
                repair_task = self._fanout_formal_repair_subtasks(task.task_id, review_result)
            else:
                repair_task = self.fork_repair_work_item(task.task_id, review_result)
            task = self.storage.load_task(review_task_id, self.registry)
            task.context.inputs["latest_repair_work_id"] = repair_task.task_id
            task.context.inputs["review_cycle_id"] = task.context.inputs.get("review_cycle_id") or f"review_cycle_{task.task_id}"
            self.storage.save_context(task.context)
            self.storage.save_task(task)
            return repair_task

        raise ValueError(f"unsupported review verdict for redo handling: {verdict}")

    def create_followup_acceptance_review(self, repair_task_id: str) -> Task:
        """在修复任务完成后，创建下一轮 acceptance_review 任务。"""
        repair_task = self.storage.load_task(repair_task_id, self.registry)
        delivery_bundle = dict(repair_task.context.inputs.get("delivery_bundle") or {})
        machine_spec = repair_task.context.inputs.get("machine_spec", "")
        acceptance_protocol = repair_task.context.inputs.get("acceptance_protocol", "")

        if not machine_spec or not acceptance_protocol:
            raise ValueError("followup acceptance review requires machine_spec and acceptance_protocol")

        payload = {
            "username": repair_task.context.username,
            "machine_spec": machine_spec,
            "acceptance_protocol": acceptance_protocol,
            "implementation_summary": delivery_bundle.get("implementation_summary") or repair_task.context.goal,
            "diff": delivery_bundle.get("diff") or "",
            "machine_spec_ref": repair_task.context.inputs.get("machine_spec_ref", ""),
            "acceptance_protocol_ref": repair_task.context.inputs.get("acceptance_protocol_ref", ""),
            "parent_work_id": repair_task.task_id,
            "iteration": int(repair_task.context.inputs.get("iteration", 0)),
            "review_cycle_id": repair_task.context.inputs.get("review_cycle_id"),
            "max_review_iterations": int(repair_task.context.inputs.get("max_review_iterations", 2)),
        }
        followup = self.create_task("acceptance_review", payload)
        self.storage.append_event(
            Event(
                task_id=repair_task.task_id,
                type="review.followup.created",
                status="created",
                payload={
                    "repair_work_id": repair_task.task_id,
                    "review_work_id": followup.task_id,
                    "review_cycle_id": repair_task.context.inputs.get("review_cycle_id"),
                    "iteration": int(repair_task.context.inputs.get("iteration", 0)),
                },
            )
        )
        return followup

    def handle_repair_completion(self, repair_task_id: str) -> Task:
        """在修复任务完成后自动回流下一轮复审，并按评审结论决定是否继续有界 redo。

        控制面在这一层只负责有界再入：
        1. 校验 repair task 已处于 COMPLETED。
        2. 创建 follow-up acceptance_review 任务。
        3. 记录 repair -> review 的审计事件并立即运行 follow-up review。
        4. 若 follow-up review 仍未通过，则继续复用 review gate 逻辑 fork 下一轮 repair。

        Args:
            repair_task_id: 已完成修复任务的任务 ID。

        Returns:
            Task: 已实际运行过的 follow-up acceptance_review 任务。

        Raises:
            ValueError: 当修复任务尚未完成，或缺少 follow-up review 所需输入时。
        """
        repair_task = self.storage.load_task(repair_task_id, self.registry)
        if repair_task.status != TaskStatus.COMPLETED:
            raise ValueError("repair task must be completed before followup review")

        followup = self.create_followup_acceptance_review(repair_task.task_id)

        repair_task = self.storage.load_task(repair_task_id, self.registry)
        repair_task.context.inputs["latest_followup_review_id"] = followup.task_id
        self.storage.save_context(repair_task.context)
        self.storage.save_task(repair_task)
        self.storage.append_event(
            Event(
                task_id=repair_task.task_id,
                type="review.followup.run.started",
                status="running",
                payload={
                    "repair_work_id": repair_task.task_id,
                    "review_work_id": followup.task_id,
                    "review_cycle_id": repair_task.context.inputs.get("review_cycle_id"),
                    "iteration": int(repair_task.context.inputs.get("iteration", 0)),
                },
            )
        )

        completed_review = self.run_task(followup.task_id)
        next_repair_task = None
        if completed_review.status == TaskStatus.COMPLETED:
            next_repair_task = self.handle_review_result(completed_review.task_id)

        self.storage.append_event(
            Event(
                task_id=repair_task.task_id,
                type="review.followup.run.completed",
                status=completed_review.status.value,
                payload={
                    "repair_work_id": repair_task.task_id,
                    "review_work_id": completed_review.task_id,
                    "review_cycle_id": repair_task.context.inputs.get("review_cycle_id"),
                    "iteration": int(repair_task.context.inputs.get("iteration", 0)),
                    "review_status": completed_review.status.value,
                    "next_repair_work_id": next_repair_task.task_id if next_repair_task else None,
                },
            )
        )
        return self.storage.load_task(completed_review.task_id, self.registry)

    def record_peer_delivery_bundle(self, task_id: str, peer_result: Dict[str, Any]) -> Dict[str, Any]:
        """将 AI 技术同事返回的结构化 result bundle 写回控制面上下文。

        该入口用于替代手工向 repair task 输入 `delivery_bundle` 的方式，
        让后续 follow-up review 始终基于可审计的协作结果回传。

        Args:
            task_id: 接收协作结果的任务 ID。
            peer_result: AI 技术同事返回的结构化结果字典。

        Returns:
            Dict[str, Any]: 归一化后的 delivery bundle。

        Raises:
            ValueError: 当结果中缺少 follow-up review 所需的最小字段时。
        """
        task = self.storage.load_task(task_id, self.registry)
        incoming_bundle = dict(peer_result.get("delivery_bundle") or {})
        implementation_summary = (
            incoming_bundle.get("implementation_summary")
            or peer_result.get("implementation_summary")
            or peer_result.get("summary")
            or ""
        )
        diff = incoming_bundle.get("diff")
        if diff is None:
            diff = peer_result.get("diff", "")
        peer_target = (
            incoming_bundle.get("peer_target")
            or peer_result.get("peer_target")
            or peer_result.get("target")
            or task.context.inputs.get("peer_target")
            or ""
        )
        artifacts = incoming_bundle.get("artifacts") or peer_result.get("artifacts") or []

        if not implementation_summary:
            raise ValueError("peer delivery bundle requires implementation_summary")
        if diff is None:
            raise ValueError("peer delivery bundle requires diff")

        delivery_bundle = {
            "implementation_summary": implementation_summary,
            "diff": diff,
            "peer_target": peer_target,
            "artifacts": artifacts,
        }
        task.context.inputs["delivery_bundle"] = delivery_bundle
        task.context.inputs["latest_peer_result"] = dict(peer_result)
        self.storage.save_context(task.context)
        self.storage.append_event(
            Event(
                task_id=task.task_id,
                type="peer.delivery_bundle.recorded",
                status="succeeded",
                payload={
                    "peer_target": peer_target,
                    "artifact_count": len(artifacts) if isinstance(artifacts, list) else 0,
                    "has_diff": bool(diff),
                },
            )
        )
        return delivery_bundle

    def complete_peer_collaboration(self, task_id: str, peer_result: Dict[str, Any]) -> Task:
        """接收 AI 技术同事的执行结果并完成该协作任务。

        对于普通协作任务，该方法会把 result bundle 写回并将任务标记为 completed。
        对于 review loop 中的 repair task，该方法还会自动进入 follow-up review 闭环。

        Args:
            task_id: 接收协作结果的任务 ID。
            peer_result: AI 技术同事返回的结构化结果字典。

        Returns:
            Task: 普通任务返回更新后的任务；repair task 返回自动运行后的 follow-up review 任务。
        """
        task = self.storage.load_task(task_id, self.registry)
        delivery_bundle = self.record_peer_delivery_bundle(task_id, peer_result)
        task = self.storage.load_task(task_id, self.registry)
        task.status = TaskStatus.COMPLETED
        self.storage.save_task(task)
        self.storage.append_event(
            Event(
                task_id=task.task_id,
                type="peer.collaboration.completed",
                status=task.status.value,
                payload={
                    "peer_target": delivery_bundle.get("peer_target"),
                    "has_diff": bool(delivery_bundle.get("diff")),
                    "has_review_cycle": bool(task.context.inputs.get("review_cycle_id")),
                },
            )
        )

        if task.context.inputs.get("subagent_scope") == SubagentScope.FORMAL_SUBTASK.value:
            parent_task_id = task.context.inputs.get("parent_task_id")
            if parent_task_id:
                self.storage.append_event(
                    Event(
                        task_id=parent_task_id,
                        type="subagent.run.completed",
                        status=SubagentRunStatus.SUCCEEDED.value,
                        payload={
                            "scope": SubagentScope.FORMAL_SUBTASK.value,
                            "run_id": task.task_id,
                            "parent_task_id": parent_task_id,
                            "parent_session_id": "",
                            "root_task_id": task.context.inputs.get("root_task_id") or parent_task_id,
                            "depth": int(task.context.inputs.get("spawn_depth", 1)),
                            "execution_mode": "serial",
                            "budget": {},
                            "used_tools": [],
                            "degradation_reason": "",
                            "join_step_id": task.context.inputs.get("join_step_id"),
                            "subtask_type": task.context.inputs.get("subtask_type"),
                        },
                    )
                )
                join_result = self.join_formal_subtasks(parent_task_id)
                if join_result.get("ready"):
                    return self.handle_repair_completion(parent_task_id)
            return self.storage.load_task(task.task_id, self.registry)

        if (
            task.context.inputs.get("review_cycle_id")
            and task.context.inputs.get("machine_spec")
            and task.context.inputs.get("acceptance_protocol")
        ):
            return self.handle_repair_completion(task.task_id)
        return self.storage.load_task(task.task_id, self.registry)

    def start_peer_collaboration(self, task_id: str, peer_target: Optional[str] = None) -> Task:
        """根据任务中的 `peer_target` 与 agent package 真实派发协作 handler。

        该入口负责：
        1. 从任务上下文解析目标 AI 技术同事。
        2. 读取已写出的 `agent_package_codex.md` 产物文本。
        3. 调用已注册的 PeerAdapter handler。
        4. 将 handler 结果回收到 `delivery_bundle`，并沿用既有 review loop。

        Args:
            task_id: 待派发的任务 ID。
            peer_target: 可选的显式目标覆盖值。

        Returns:
            Task: 普通任务返回完成后的任务；repair task 返回后续 follow-up review 任务。

        Raises:
            ValueError: 当目标缺失、任务包缺失或目标 handler 未注册时抛出。
        """
        task = self.storage.load_task(task_id, self.registry)
        resolved_target = (
            peer_target
            or task.context.inputs.get("peer_target")
            or task.context.step_outputs.get("agent_package_generator", {}).get("structured", {}).get("peer_target")
            or task.context.step_outputs.get("agent_package_generator", {}).get("structured", {}).get("worker_target")
        )
        if not resolved_target:
            self.storage.append_event(
                Event(
                    task_id=task.task_id,
                    type="peer.collaboration.dispatch.failed",
                    status="failed",
                    payload={"reason": "missing_peer_target"},
                )
            )
            raise ValueError("peer collaboration requires peer_target")

        package_artifact = next((artifact for artifact in task.context.artifacts if artifact.name == "agent_package_codex.md"), None)
        if not package_artifact:
            self.storage.append_event(
                Event(
                    task_id=task.task_id,
                    type="peer.collaboration.dispatch.failed",
                    status="failed",
                    payload={"reason": "missing_agent_package", "peer_target": resolved_target},
                )
            )
            raise ValueError("peer collaboration requires agent_package_codex.md artifact")

        package_text = self.storage.read_artifact(package_artifact.artifact_id).content or ""
        self.storage.append_event(
            Event(
                task_id=task.task_id,
                type="peer.collaboration.dispatch.started",
                status="running",
                payload={
                    "peer_target": resolved_target,
                    "artifact_id": package_artifact.artifact_id,
                    "artifact_name": package_artifact.name,
                },
            )
        )
        try:
            peer_result = self.peer_adapter.dispatch(task, package_text, resolved_target)
        except Exception as exc:
            self.storage.append_event(
                Event(
                    task_id=task.task_id,
                    type="peer.collaboration.dispatch.failed",
                    status="failed",
                    payload={
                        "peer_target": resolved_target,
                        "error": str(exc),
                    },
                )
            )
            raise

        self.storage.append_event(
            Event(
                task_id=task.task_id,
                type="peer.collaboration.dispatch.completed",
                status="succeeded",
                payload={"peer_target": resolved_target},
            )
        )
        return self.complete_peer_collaboration(task.task_id, peer_result)

    @staticmethod
    def _repair_business_intent(parent: Task, fix_tasks: list[dict[str, Any]]) -> str:
        lines = [
            "Apply the following Acceptance Review fix tasks as a repair iteration.",
            "Preserve the existing machine_spec and acceptance_protocol as the source of truth.",
        ]
        for index, fix in enumerate(fix_tasks, start=1):
            title = fix.get("title", "Untitled fix task")
            priority = fix.get("priority", "high")
            source_ids = ", ".join(fix.get("source_issue_ids", []))
            lines.append(f"{index}. [{priority}] {title} (source issues: {source_ids})")
        if parent.context.inputs.get("machine_spec"):
            lines.append("\nMachine Spec Snapshot:\n" + str(parent.context.inputs.get("machine_spec"))[:2000])
        if parent.context.inputs.get("acceptance_protocol"):
            lines.append("\nAcceptance Protocol Snapshot:\n" + str(parent.context.inputs.get("acceptance_protocol"))[:2000])
        return "\n".join(lines)

    def _validate_required(self, definition: TaskDefinition, payload: Dict[str, Any]) -> None:
        """验证 payload 是否提供了该任务定义所必需的入参。

        Args:
            definition: 任务定义规格。
            payload: 输入参数载荷。

        Raises:
            ValueError: 当缺少任何必需的入参字段时。
        """
        missing = [field for field in definition.input_schema.get("required", []) if not payload.get(field)]
        if missing:
            public_task_type = definition.metadata.get("public_task_type", definition.type)
            raise ValueError(f"missing required fields for {public_task_type}: {', '.join(missing)}")

    @classmethod
    def _normalize_task_type(cls, task_type: str) -> str:
        """将任务类型别名标准化为系统内的规范键值。

        Args:
            task_type: 待标准化的原始任务类型名称。

        Returns:
            str: 标准化后的规范任务类型。
        """
        return cls.COMPATIBILITY_TYPE_ALIASES.get(task_type, task_type)

    def get_work_item(self, task_id: str) -> WorkItem:
        """将任务转换为 EvoCanvas WorkItem 状态实体。

        Args:
            task_id: 任务的唯一标识符。

        Returns:
            WorkItem: EvoCanvas 工作项，包含状态映射与 Playbook 信息。
        """
        task = self.storage.load_task(task_id, self.registry)
        # 将 Task 状态映射到 WorkStatus
        status_map = {
            TaskStatus.CREATED: WorkStatus.CREATED,
            TaskStatus.RUNNING: WorkStatus.RUNNING,
            TaskStatus.WAITING_FOR_USER: WorkStatus.WAITING_FOR_DECISION,
            TaskStatus.COMPLETED: WorkStatus.COMPLETED,
            TaskStatus.FAILED: WorkStatus.FAILED,
            TaskStatus.CANCELLED: WorkStatus.CANCELLED,
            TaskStatus.BLOCKED: WorkStatus.BLOCKED,
        }
        work_status = status_map.get(task.status, WorkStatus.CREATED)
        
        # 将入口任务类型转换为 WorkType
        if task.definition.type == "prd":
            work_type = WorkType.PRD
        elif task.definition.type == "manual":
            work_type = WorkType.MANUAL
        else:
            try:
                work_type = WorkType(task.definition.type)
            except ValueError:
                work_type = WorkType.PRD

        return WorkItem(
            work_id=task.task_id,
            work_type=work_type,
            playbook_id=task.definition.workflow.name,
            title=task.context.title,
            objective=task.context.goal,
            workspace_id=task.task_id,
            product_context_ref=f"ctx_{task.task_id}",
            artifact_graph_ref=f"graph_{task.task_id}",
            status=work_status,
            current_decision_gate_id=task.waiting_step_id,
            iteration=int(task.context.inputs.get("iteration", 0)),
            parent_work_id=task.context.inputs.get("parent_work_id"),
            review_cycle_id=task.context.inputs.get("review_cycle_id"),
            max_review_iterations=int(task.context.inputs.get("max_review_iterations", 2)),
            metadata={
                "compatibility_task_id": task.task_id,
                "compatibility_bridge": True,
                "subagent_scope": task.context.inputs.get("subagent_scope"),
                "parent_task_id": task.context.inputs.get("parent_task_id"),
                "root_task_id": task.context.inputs.get("root_task_id"),
                "subtask_type": task.context.inputs.get("subtask_type"),
            }
        )

    def _list_formal_subtasks(self, parent_task_id: str) -> list[Task]:
        tasks = self.storage.list_tasks(self.registry)
        return [
            task
            for task in tasks
            if task.context.inputs.get("subagent_scope") == SubagentScope.FORMAL_SUBTASK.value
            and task.context.inputs.get("parent_task_id") == parent_task_id
        ]

    @staticmethod
    def _default_formal_subtask_budget(fanout: int) -> Any:
        from app.core.subagent import SubagentBudget

        return SubagentBudget(
            max_iterations=4,
            max_input_tokens=800,
            max_output_tokens=240,
            max_tool_calls=2,
            spawn_fanout_remaining=max(0, 3 - fanout),
        )

    @staticmethod
    def _should_fanout_fix_tasks(review_result: Dict[str, Any]) -> bool:
        fix_tasks = list(review_result.get("fix_tasks") or [])
        if len(fix_tasks) < 2 or len(fix_tasks) > 3:
            return False
        source_ids = []
        for fix_task in fix_tasks:
            task_source_ids = list(fix_task.get("source_issue_ids", []))
            if not task_source_ids:
                return False
            source_ids.extend(task_source_ids)
        return len(source_ids) == len(set(source_ids))

    def get_product_context(self, task_id: str) -> ProductContext:
        """将任务上下文及其关联信息整理为 EvoCanvas ProductContext。

        提取源材料、核心需求陈述、用户约束条件、已被裁决的 DecisionGate 列表等。

        Args:
            task_id: 任务的唯一标识符。

        Returns:
            ProductContext: EvoCanvas 产品上下文。
        """
        task = self.storage.load_task(task_id, self.registry)
        ctx = task.context
        
        # 转换输入材料 (SourceInput)
        source_inputs = []
        for i, mat in enumerate(ctx.source_materials):
            source_inputs.append(SourceInput(
                input_id=mat.get("material_id", f"mat_{i}"),
                kind="material",
                summary=f"Material input: {mat.get('material_id')}"
            ))
        source_inputs.append(SourceInput(
            input_id="payload_inputs",
            kind="inputs_payload",
            summary="Original task inputs payload",
            metadata=ctx.inputs
        ))
        
        # 转换业务需求 (Requirement)
        requirements = []
        primary_feature = (
            ctx.inputs.get("feature")
            or ctx.inputs.get("module_name")
            or ctx.inputs.get("business_intent")
        )
        if primary_feature:
            requirements.append(
                Requirement(
                    requirement_id="req_primary",
                    statement=str(primary_feature),
                    priority="must",
                    rationale=ctx.goal
                )
            )
        
        # 转换用户约束 (ProductConstraint)
        constraints = [
            ProductConstraint(
                constraint_id=f"const_{i}",
                statement=c,
                category="user"
            ) for i, c in enumerate(ctx.user_constraints)
        ]
        
        # 将已完成的决策（user_decisions）整理为 DecisionGate 结构
        user_decisions = []
        for i, dec in enumerate(ctx.user_decisions):
            gate_id = f"gate_{i}"
            options = []
            if dec.selected_option:
                options.append(DecisionOption(
                    option_id=dec.selected_option,
                    label=f"Option {dec.selected_option}",
                    summary=dec.decision
                ))
            
            resolution = None
            if dec.selected_option:
                resolution = GateResolution(
                    selected_option_id=dec.selected_option,
                    rationale=dec.decision,
                    decided_by=ctx.username,
                )
            
            user_decisions.append(DecisionGate(
                gate_id=gate_id,
                work_id=task.task_id,
                question=dec.decision,
                options=options,
                impact_summary="Compatibility task user decision",
                blocking=True,
                status=DecisionGateStatus.RESOLVED if dec.selected_option else DecisionGateStatus.OPEN,
                resolution=resolution,
                metadata={
                    "quoted_selections": dec.quoted_selections,
                    "applies_to_step_id": dec.applies_to_step_id,
                    "resume_step_id": dec.resume_step_id,
                }
            ))
            
        # 转换引用到的知识项（KnowledgeRef）
        knowledge_refs = []
        k_state = ctx.degradation_state.get("knowledge", {})
        if k_state and "preview" in k_state:
            for idx, item in enumerate(k_state.get("preview", [])):
                knowledge_refs.append(KnowledgeRef(
                    knowledge_id=f"kb_{idx}",
                    kind="retrieved_doc",
                    summary=item.get("summary", ""),
                    locator=item.get("title", "")
                ))
                
        return ProductContext(
            objective=ctx.goal,
            source_inputs=source_inputs,
            requirements=requirements,
            constraints=constraints,
            assumptions=[],
            user_decisions=user_decisions,
            knowledge_refs=knowledge_refs,
            worker_feedback=[],
            metadata={
                "username": ctx.username,
                "degradation_state": ctx.degradation_state,
                "inputs": ctx.inputs,
            }
        )

    def get_artifact_graph(self, task_id: str) -> ArtifactGraph:
        """根据任务产物集合与决策状态构建 ArtifactGraph。

        Args:
            task_id: 任务的唯一标识符。

        Returns:
            ArtifactGraph: EvoCanvas 产物依赖关系图。
        """
        task = self.storage.load_task(task_id, self.registry)
        ctx = task.context
        
        nodes = []
        edges = []

        # 映射文件名称与 EvoCanvas 产物类型的关系
        native_type_map = {
            "machine_spec.yaml": ArtifactNodeType.MACHINE_SPEC,
            "human_brief.md": ArtifactNodeType.HUMAN_BRIEF,
            "agent_package_codex.md": ArtifactNodeType.AGENT_PACKAGE,
            "acceptance.md": ArtifactNodeType.ACCEPTANCE_PROTOCOL,
            "review_checklist.md": ArtifactNodeType.REVIEW_CHECKLIST,
            "traceability.json": ArtifactNodeType.TRACEABILITY_MAP,
            "review_result.md": ArtifactNodeType.REVIEW_RESULT,
            "PRD.md": ArtifactNodeType.OPTIONAL_PRD,
            "模块概览.md": ArtifactNodeType.OPTIONAL_MANUAL,
        }
        edge_type_map = {
            ArtifactNodeType.ACCEPTANCE_PROTOCOL: ArtifactEdgeType.VALIDATES,
            ArtifactNodeType.REVIEW_RESULT: ArtifactEdgeType.REVIEWS,
        }

        # 提取或初始化 MACHINE_SPEC (机器规格) 节点作为根/底座
        spec_node_id = None
        spec_artifact = next((art for art in ctx.artifacts if native_type_map.get(art.name) == ArtifactNodeType.MACHINE_SPEC), None)
        if spec_artifact:
            spec_node_id = f"node_art_{spec_artifact.artifact_id}"
            nodes.append(ArtifactNode(
                node_id=spec_node_id,
                type=ArtifactNodeType.MACHINE_SPEC,
                artifact_ref=ArtifactRef(
                    name=spec_artifact.name,
                    version=spec_artifact.version,
                    storage_uri=f"file://artifacts/{spec_artifact.artifact_id}",
                    checksum=getattr(spec_artifact, "checksum", None),
                ),
                summary="Native machine spec artifact",
                created_by=spec_artifact.created_by or "system",
            ))
        else:
            spec_node_id = f"node_spec_{task.task_id}"
            nodes.append(ArtifactNode(
                node_id=spec_node_id,
                type=ArtifactNodeType.MACHINE_SPEC,
                artifact_ref=ArtifactRef(
                    name="machine_spec",
                    storage_uri=f"memory://tasks/{task.task_id}/inputs"
                ),
                summary="Original task inputs and specifications",
                created_by="system"
            ))

        # 构建其他产物节点，并关联依赖（DERIVES_FROM 等边）
        for art in ctx.artifacts:
            if spec_artifact and art.artifact_id == spec_artifact.artifact_id:
                continue
            art_node_id = f"node_art_{art.artifact_id}"
            node_type = native_type_map.get(art.name)
            if node_type is None:
                projection_type_str = task.definition.metadata.get("compatibility_projection") or task.definition.metadata.get("legacy_projection")
                node_type = ArtifactNodeType.OPTIONAL_PRD
                if projection_type_str == "optional_manual":
                    node_type = ArtifactNodeType.OPTIONAL_MANUAL
            nodes.append(ArtifactNode(
                node_id=art_node_id,
                type=node_type,
                artifact_ref=ArtifactRef(
                    name=art.name,
                    version=art.version,
                    storage_uri=f"file://artifacts/{art.artifact_id}",
                    checksum=getattr(art, "checksum", None)
                ),
                summary=f"Artifact: {art.name}",
                created_by=art.created_by or "system"
            ))
            
            edges.append(ArtifactEdge(
                edge_id=f"edge_derive_{art.artifact_id}",
                from_node_id=art_node_id,
                to_node_id=spec_node_id,
                type=edge_type_map.get(node_type, ArtifactEdgeType.DERIVES_FROM),
                summary=f"{art.name} is linked to machine spec"
            ))
            
        # 构建决策节点，将用户决策映射进产物图
        for idx, dec in enumerate(ctx.user_decisions):
            dec_node_id = f"node_dec_{idx}_{task.task_id}"
            nodes.append(ArtifactNode(
                node_id=dec_node_id,
                type=ArtifactNodeType.DECISION,
                artifact_ref=ArtifactRef(
                    name=f"decision_{idx}",
                    storage_uri=f"memory://tasks/{task.task_id}/decision_{idx}"
                ),
                summary=f"User decision: {dec.decision}",
                created_by=ctx.username
            ))
            
            edges.append(ArtifactEdge(
                edge_id=f"edge_dec_{idx}",
                from_node_id=spec_node_id,
                to_node_id=dec_node_id,
                type=ArtifactEdgeType.RESOLVES_DECISION,
                summary="Machine spec resolves user decision"
            ))
            
        graph = ArtifactGraph(
            work_id=task.task_id,
            nodes=nodes,
            edges=edges
        )
        graph.validate()
        return graph

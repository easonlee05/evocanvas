"""工作流步骤执行器注册表模块。

该模块用于将工作流引擎的步骤调度逻辑与具体步骤的执行细节解耦。通过引入 `StepExecutor` 协议与 
`StepExecutionRegistry` 注册表，系统能根据步骤类型（type）或步骤 ID（id）动态匹配并调用相应的执行器。
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional, Protocol

from app.core.errors import DomainError
from app.core.events import Event
from app.core.task import StepResult, StepStatus, Task, WorkflowStep
from app.core.tools import ToolCall
from app.workflows.context_compiler import ContextCompilerService


class StepExecutor(Protocol):
    """具体的具体工作流步骤执行器必须实现的协议接口。"""

    step_type: str
    step_id: Optional[str] = None

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        """执行工作流步骤。

        Args:
            task (Task): 包含当前执行上下文的任务实例。
            step (WorkflowStep): 正在执行的工作流步骤。
            run_id (Optional[str], optional): 当前运行周期 ID。默认为 None。
            is_parallel (bool, optional): 是否以并行方式执行该步骤。默认为 False。

        Returns:
            StepResult: 步骤执行完成后的结果对象。
        """
        ...


@dataclass
class StepExecutionRegistry:
    """工作流步骤执行器的分发与注册中心。

    根据 `WorkflowStep.type` 或 `WorkflowStep.id` 将执行请求分发到匹配的 `StepExecutor`。
    """

    executors: Iterable[StepExecutor] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._executors: Dict[str, StepExecutor] = {}
        self._id_executors: Dict[str, StepExecutor] = {}
        for executor in self.executors:
            self.register(executor)

    def register(self, executor: StepExecutor) -> None:
        """向注册表中添加一个新的步骤执行器。

        如果执行器声明了 `step_id`，则优先按步骤 ID 注册（精确匹配）；
        否则，按步骤类型 `step_type` 注册（类型匹配）。

        Args:
            executor (StepExecutor): 步骤执行器实例。

        Raises:
            DomainError: 当执行器既未声明 step_id 也没声明非空的 step_type 时。
        """
        step_id = getattr(executor, "step_id", None)
        if step_id:
            self._id_executors[step_id] = executor
            return

        step_type = getattr(executor, "step_type", "")
        if not step_type:
            raise DomainError("workflow.executor_missing_type", "Step executor must declare a non-empty step_type or step_id.")
        self._executors[step_type] = executor

    def get(self, step_type: str, step_id: Optional[str] = None) -> Optional[StepExecutor]:
        """根据步骤的类型和可选的 ID 检索匹配的执行器。

        优先通过 ID 精确寻找，无果则回退到按类型寻找。

        Args:
            step_type (str): 步骤的类型名称。
            step_id (Optional[str], optional): 步骤的唯一标识。默认为 None。

        Returns:
            Optional[StepExecutor]: 找到的执行器实例；若无则返回 None。
        """
        if step_id and step_id in self._id_executors:
            return self._id_executors[step_id]
        return self._executors.get(step_type)

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        """分发并运行指定的步骤。

        Args:
            task (Task): 任务实例。
            step (WorkflowStep): 工作流步骤。
            run_id (Optional[str], optional): 当前运行周期 ID。默认为 None。
            is_parallel (bool, optional): 是否并行。默认为 False。

        Returns:
            StepResult: 步骤执行结果。
        """
        executor = self.get(step.type, step.id)
        if executor is None:
            # 未配置执行器时返回失败状态
            return StepResult(
                step.id,
                StepStatus.FAILED,
                error=DomainError("workflow.unknown_step_type", f"Unknown step type: {step.type} (id: {step.id})"),
            )
        return executor.run(task, step, run_id=run_id, is_parallel=is_parallel)


@dataclass
class ContextStepExecutor:
    """专注于上下文加载/处理的步骤执行器。

    支持对 `retrieve_knowledge` (检索知识)、`ingest_materials` (导入输入材料) 等特定步骤进行编排，
    无需在引擎控制面写死这些分支。
    """

    tool_service: Any = None
    storage: Any = None
    custom_handlers: Dict[str, Any] = field(default_factory=dict)
    step_type: str = "context"

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        custom_handler = self.custom_handlers.get(step.id)
        if callable(custom_handler):
            return custom_handler(task, step)
            
        # 针对知识检索步骤的分支处理
        if step.id == "retrieve_knowledge" and self.tool_service is not None:
            # 组合知识查询词，充分融入标题、目标、任务类型及功能特征
            query_parts = [
                task.context.title,
                task.context.goal,
                task.definition.type,
                task.context.inputs.get("feature"),
                task.context.inputs.get("business_goal"),
            ]
            query = " ".join(part.strip() for part in query_parts if isinstance(part, str) and part.strip())
            call = ToolCall(task.task_id, step.id, "SYSTEM", "knowledge.retrieve", {"query": query})
            result = self.tool_service.invoke(task.definition, task.context, call)
            
            # 若检索失败，任务处于受阻（BLOCKED）状态
            if result.status != "succeeded":
                return StepResult(step.id, StepStatus.BLOCKED, error=result.error)
                
            # 加载知识上下文并记录降级诊断状态
            task.context.knowledge_context = result.data
            preview = self._knowledge_preview(result.data)
            task.context.degradation_state["knowledge"] = {
                "degraded": bool(result.data.get("degraded")),
                "error": result.data.get("error"),
                "items": len(result.data.get("items", [])),
                "preview": preview,
            }
            return StepResult(step.id, StepStatus.SUCCEEDED, "knowledge context loaded", outputs={"knowledge_context": result.data}, tool_calls=[call])
            
        # 针对材料导入步骤的分支处理
        if step.id == "ingest_materials" and self.tool_service is not None:
            call = ToolCall(task.task_id, step.id, "SYSTEM", "material.parse", {})
            result = self.tool_service.invoke(task.definition, task.context, call)
            return StepResult(step.id, StepStatus.SUCCEEDED, "materials ingested", outputs=result.data, tool_calls=[call])
            
        # 如果存在存储组件，则保存 context.loaded 事件
        if self.storage is not None:
            self.storage.append_event(
                Event(
                    task_id=task.task_id,
                    type="context.loaded",
                    status="loaded",
                    payload={
                        "degraded": bool(task.context.degradation_state),
                        "title": task.context.title,
                        "degradation_state": task.context.degradation_state,
                    },
                )
            )
        return StepResult(step.id, StepStatus.SUCCEEDED, "context ready", outputs={"goal": task.context.goal})

    @staticmethod
    def _knowledge_preview(data: Dict[str, Any]) -> list[dict[str, str]]:
        """为加载的知识提取前 3 条概要预览。

        Args:
            data (Dict[str, Any]): 知识检索返回的字典数据。

        Returns:
            list[dict[str, str]]: 包含预览标题和摘要的字典列表。
        """
        preview: list[dict[str, str]] = []
        for item in data.get("items", [])[:3]:
            if isinstance(item, dict):
                preview.append({"title": item.get("title", "未命名知识"), "summary": item.get("summary", "")})
        return preview


@dataclass
class DiffStepExecutor:
    """代码/配置差异（Diff）分析与规则提取步骤执行器。"""

    step_type: str = "diff"

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        # 当前为轻量占位，后续可接入 diff 工具进行差异规则发现
        return StepResult(step.id, StepStatus.SUCCEEDED, "diff candidates prepared", outputs={"candidates": []})


@dataclass
class CheckpointStepExecutor:
    """显式检查点保存步骤执行器。"""

    step_type: str = "checkpoint"

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        return StepResult(step.id, StepStatus.SUCCEEDED, "checkpoint saved", outputs={"checkpoint": step.id})


@dataclass
class ArtifactStepExecutor:
    """生成并写入交付产物（Artifact）的步骤执行器。

    使用 `ContextCompilerService` 编译上下文模板生成产物，并调用 `artifact.write` 工具落盘。
    """

    tool_service: Any
    context_compiler: ContextCompilerService
    storage: Any = None
    step_type: str = "artifact"

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        try:
            # 编译出产物的名称和具体内容
            name, content = self.context_compiler.artifact_payload(task, step)
        except DomainError as error:
            return StepResult(step.id, StepStatus.FAILED, error=error)
            
        # 申请受控工具 artifact.write 进行文件落盘
        call = ToolCall(task.task_id, step.id, step.role, "artifact.write", {"name": name, "content": content})
        result = self.tool_service.invoke(task.definition, task.context, call)
        
        # 处理可能的权限拒绝或写入失败
        if result.status != "succeeded":
            status = StepStatus.BLOCKED if result.status == "denied" else StepStatus.FAILED
            return StepResult(step.id, status, error=result.error)
            
        # 记录生成的产物元数据至任务上下文中，并触发事件通知
        for artifact in result.artifacts:
            if not any(existing.artifact_id == artifact.artifact_id for existing in task.context.artifacts):
                task.context.artifacts.append(artifact)
            if self.storage is not None:
                self.storage.append_event(
                    Event(
                        task_id=task.task_id,
                        type="artifact.created",
                        role=step.role,
                        status="created",
                        payload={"artifact_id": artifact.artifact_id, "name": artifact.name, "version": artifact.version},
                    )
                )
        return StepResult(step.id, StepStatus.SUCCEEDED, "artifact written", outputs={"artifacts": [artifact.to_dict() for artifact in result.artifacts]}, tool_calls=[call])


@dataclass
class DelegatingStepExecutor:
    """委托模式步骤执行器。

    作为一个适配器，将步骤执行的具体行为委托给引擎自身的方法或自定义回调，
    常用于衔接引擎内部仍需兼容的复杂行为（如既有 agent、gate 等）。
    """

    step_type: str
    callback: Any
    custom_handlers: Dict[str, Any] = field(default_factory=dict)

    def run(self, task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
        custom_handler = self.custom_handlers.get(step.id)
        # 优先使用在自定义处理器表中注册的针对该步骤 ID 的回调
        if callable(custom_handler):
            signature = inspect.signature(custom_handler)
            kwargs: Dict[str, Any] = {}
            if "run_id" in signature.parameters:
                kwargs["run_id"] = run_id
            if "is_parallel" in signature.parameters:
                kwargs["is_parallel"] = is_parallel
            if "llm" in signature.parameters and hasattr(self.callback, "__self__"):
                kwargs["llm"] = getattr(self.callback.__self__, "llm", None)
            if "tool_service" in signature.parameters and hasattr(self.callback, "__self__"):
                kwargs["tool_service"] = getattr(self.callback.__self__, "tool_service", None)
            return custom_handler(task, step, **kwargs)
            
        # 否则，退回到调用默认的委托回调，并利用内省适配其所需的函数签名参数
        signature = inspect.signature(self.callback)
        kwargs: Dict[str, Any] = {}
        if "run_id" in signature.parameters:
            kwargs["run_id"] = run_id
        if "is_parallel" in signature.parameters:
            kwargs["is_parallel"] = is_parallel
        return self.callback(task, step, **kwargs)


@dataclass
class DefaultStepExecutorRegistryFactory:
    """为工作流引擎实例构建核心步骤执行器注册表的工厂类。

    该工厂除了注入常用的基础设施服务外，还负责按需加载 spec_to_agent 和 acceptance_review 两类工作流的具体业务步骤执行器。
    """

    tool_service: Any
    llm: Any
    storage: Any
    context_compiler: ContextCompilerService
    agent_callback: Any = None
    gate_callback: Any = None
    arbitration_callback: Any = None
    context_handlers: Dict[str, Any] = field(default_factory=dict)
    agent_handlers: Dict[str, Any] = field(default_factory=dict)
    gate_handlers: Dict[str, Any] = field(default_factory=dict)
    arbitration_handlers: Dict[str, Any] = field(default_factory=dict)

    def build(self) -> StepExecutionRegistry:
        """组装并返回统一的 `StepExecutionRegistry` 实例。

        Returns:
            StepExecutionRegistry: 包含了所有预配置执行器的步骤注册表。
        """
        executors: list[StepExecutor] = [
            # 基础通用执行器
            ContextStepExecutor(
                tool_service=self.tool_service,
                storage=self.storage,
                custom_handlers=self.context_handlers,
            ),
            ArtifactStepExecutor(tool_service=self.tool_service, context_compiler=self.context_compiler, storage=self.storage),
            DiffStepExecutor(),
            CheckpointStepExecutor(),
        ]

        executors.extend(self._load_spec_to_agent_executors())
        executors.extend(self._load_acceptance_review_executors())
        
        # 追加代理模式执行器以衔接兼容引擎的复杂事件分支
        executors.append(
            DelegatingStepExecutor(
                "agent",
                self.agent_callback or self._missing_delegate("agent"),
                custom_handlers=self.agent_handlers,
            )
        )
        executors.append(
            DelegatingStepExecutor(
                "gate",
                self.gate_callback or self._missing_delegate("gate"),
                custom_handlers=self.gate_handlers,
            )
        )
        executors.append(
            DelegatingStepExecutor(
                "arbitration",
                self.arbitration_callback or self._missing_delegate("arbitration"),
                custom_handlers=self.arbitration_handlers,
            )
        )
        return StepExecutionRegistry(executors)

    def _load_spec_to_agent_executors(self) -> list[StepExecutor]:
        try:
            from app.workflows.spec_to_agent import (
                AcceptanceProtocolGeneratorExecutor,
                AgentPackageGeneratorExecutor,
                ContextNormalizerExecutor,
                HumanDecisionGateExecutor,
                MachineSpecCompilerExecutor,
                OpenQuestionIdentifierExecutor,
            )
        except ModuleNotFoundError:
            return []

        return [
            ContextNormalizerExecutor(),
            OpenQuestionIdentifierExecutor(llm=self.llm, tool_service=self.tool_service),
            HumanDecisionGateExecutor(),
            MachineSpecCompilerExecutor(llm=self.llm, tool_service=self.tool_service),
            AgentPackageGeneratorExecutor(llm=self.llm, tool_service=self.tool_service),
            AcceptanceProtocolGeneratorExecutor(llm=self.llm, tool_service=self.tool_service),
        ]

    def _load_acceptance_review_executors(self) -> list[StepExecutor]:
        try:
            from app.workflows.acceptance_review import (
                DiffImpactAnalyzerExecutor,
                IngestAcceptanceContextExecutor,
                RequirementCoverageExecutor,
                ReviewGateExecutor,
                ReviewResultCompilerExecutor,
            )
        except ModuleNotFoundError:
            return []

        return [
            IngestAcceptanceContextExecutor(),
            RequirementCoverageExecutor(llm=self.llm, tool_service=self.tool_service),
            DiffImpactAnalyzerExecutor(llm=self.llm, tool_service=self.tool_service),
            ReviewResultCompilerExecutor(llm=self.llm),
            ReviewGateExecutor(),
        ]

    @staticmethod
    def _missing_delegate(step_type: str):
        """当引擎未绑定必要的委托回调时返回一个失败占位函数。"""
        def run(task: Task, step: WorkflowStep, *, run_id: Optional[str] = None, is_parallel: bool = False) -> StepResult:
            return StepResult(step.id, StepStatus.FAILED, error=DomainError("workflow.executor_not_bound", f"No delegate bound for {step_type} step."))
        return run

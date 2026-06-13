"""任务定义工作流的 DAG 就绪运行时规划原语模块。

该模块提供了解析、验证工作流规范（WorkflowSpec）的核心规划结构，
支持将线性的步骤列表在逻辑上组织成可执行的批次（WorkflowExecutionBatch），
并能够支持并行的分组以及步骤间的路由选择逻辑。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.core.errors import DomainError
from app.core.task import StepResult, WorkflowSpec, WorkflowStep


@dataclass(frozen=True)
class WorkflowExecutionBatch:
    """可执行步骤批次数据类。

    包含单步骤批次（沿用传统线性行为）或多步骤并行批次（对应同一个 `parallel_group`）。
    这为未来平滑演进到更复杂的 DAG 并行调度提供了底层模型支持。
    """

    steps: List[WorkflowStep]
    parallel_group: Optional[str] = None

    @property
    def is_parallel(self) -> bool:
        """判断当前执行批次是否为并行批次。

        Returns:
            bool: 如果包含的步骤数大于 1，则为 True，否则为 False。
        """
        return len(self.steps) > 1


@dataclass(frozen=True)
class WorkflowRuntimePlan:
    """基于 `WorkflowSpec` 导出并经过静态验证的运行时执行计划。"""

    workflow: WorkflowSpec
    step_by_id: Dict[str, WorkflowStep]
    order: List[str]

    @classmethod
    def from_workflow(cls, workflow: WorkflowSpec) -> "WorkflowRuntimePlan":
        """从工作流规范构建运行时执行计划，并执行标识符唯一性校验。

        Args:
            workflow (WorkflowSpec): 输入的工作流规范定义。

        Returns:
            WorkflowRuntimePlan: 构建好并验证通过的运行计划。

        Raises:
            DomainError: 如果发现重复的步骤 ID。
        """
        step_by_id: Dict[str, WorkflowStep] = {}
        order: List[str] = []
        for step in workflow.steps:
            if step.id in step_by_id:
                raise DomainError(
                    "workflow.duplicate_step_id",
                    f"Workflow step id '{step.id}' appears more than once.",
                )
            step_by_id[step.id] = step
            order.append(step.id)

        plan = cls(workflow=workflow, step_by_id=step_by_id, order=order)
        # 静态验证所有步骤配置的路由是否指向已知的合法步骤
        plan._validate_routes()
        return plan

    def _validate_routes(self) -> None:
        """静态校验所有步骤的 on_success 和 on_failure 路由目标是否存在。

        Raises:
            DomainError: 如果某个路由目标指向了不存在的步骤 ID。
        """
        for step in self.workflow.steps:
            for route_name, target in (("on_success", step.on_success), ("on_failure", step.on_failure)):
                if target and target not in self.step_by_id:
                    raise DomainError(
                        "workflow.dangling_route",
                        f"Step '{step.id}' has {route_name} route to unknown step '{target}'.",
                        details={"step_id": step.id, "route": route_name, "target": target},
                    )

    def step_index(self, step_id: str) -> int:
        """获取指定步骤在顺序执行列表中的索引位置。

        Args:
            step_id (str): 步骤 ID。

        Returns:
            int: 步骤在 order 列表中的索引位置。

        Raises:
            KeyError: 当步骤 ID 未知时。
        """
        if step_id not in self.step_by_id:
            raise KeyError(f"unknown workflow step: {step_id}")
        return self.order.index(step_id)

    def next_step_id(self, step_id: str) -> Optional[str]:
        """获取线性执行顺序下的下一个默认步骤 ID。

        Args:
            step_id (str): 步骤 ID。

        Returns:
            Optional[str]: 下一个步骤 ID；若是最后一个步骤则返回 None。
        """
        index = self.step_index(step_id)
        if index + 1 >= len(self.order):
            return None
        return self.order[index + 1]

    def batches_from(self, start_step_id: Optional[str] = None) -> List[WorkflowExecutionBatch]:
        """从指定步骤开始，将剩余步骤组合划分成一组可按批次执行的结构。

        同属于一个并行组（parallel_group）的连续步骤会被合并入同一个并行批次。

        Args:
            start_step_id (Optional[str], optional): 开始解析批次的步骤 ID，默认为 None 表示从头开始。

        Returns:
            List[WorkflowExecutionBatch]: 拆分出来的执行批次列表。
        """
        start_index = self.step_index(start_step_id) if start_step_id else 0
        groups: List[WorkflowExecutionBatch] = []
        current: List[WorkflowStep] = []
        current_group: Optional[str] = None

        for step in self.workflow.steps[start_index:]:
            # 如果属于同一个并行组且前一步也在该组，则加入当前批次
            if current and step.parallel_group and step.parallel_group == current_group:
                current.append(step)
                continue
            # 否则，封存上一个批次，开始新的一批
            if current:
                groups.append(WorkflowExecutionBatch(steps=current, parallel_group=current_group))
            current = [step]
            current_group = step.parallel_group

        # 封存最后的未决批次
        if current:
            groups.append(WorkflowExecutionBatch(steps=current, parallel_group=current_group))
        return groups

    def resolve_success_route(self, step_id: str, result: StepResult) -> Optional[str]:
        """根据步骤执行成功的结果动态解析实际的下一个步骤 ID。

        Args:
            step_id (str): 当前执行完成的步骤 ID。
            result (StepResult): 执行结果对象。

        Returns:
            Optional[str]: 决定路由到的下一个步骤 ID；如果结束则返回 None。
        """
        step = self.step_by_id[step_id]
        # 优先级：步骤执行返回的显式路径 > 静态配置的 on_success 路由 > 默认的线性下一步
        return result.next_step_id or step.on_success or self.next_step_id(step_id)

    def resolve_failure_route(self, step_id: str, result: StepResult) -> Optional[str]:
        """根据步骤执行失败的结果动态解析实际的下一个错误处理步骤 ID。

        Args:
            step_id (str): 当前执行失败的步骤 ID。
            result (StepResult): 失败的执行结果对象。

        Returns:
            Optional[str]: 决定路由到的下一个步骤 ID；若无相应路由则返回 None。
        """
        step = self.step_by_id[step_id]
        # 优先级：步骤执行返回的显式错误处理路径 > 静态配置的 on_failure 错误路径
        return result.next_step_id or step.on_failure


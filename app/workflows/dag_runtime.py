"""原生 Evoloop 剧本的 DAG（有向无环图）运行时原语模块。

该模块独立于具体的 LLM/工具执行。它将已有的工作流规范（WorkflowSpec）契约转换成
带有依赖感知的节点（DAGRuntimeNode），使旧版引擎能够在无契约改动的情况下演进为支持真正拓扑调度的 DAG 运行时。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

from app.core.errors import DomainError
from app.core.task import WorkflowSpec, WorkflowStep


@dataclass(frozen=True)
class DAGRuntimeNode:
    """包装了工作流步骤及显式依赖与路由元数据的 DAG 运行时节点。"""

    step: WorkflowStep
    dependencies: List[str] = field(default_factory=list)

    @property
    def node_id(self) -> str:
        """获取节点的唯一 ID。

        Returns:
            str: 关联步骤的 ID。
        """
        return self.step.id

    @property
    def step_type(self) -> str:
        """获取步骤的类型。

        Returns:
            str: 关联步骤的类型。
        """
        return self.step.type


@dataclass
class PlaybookDAGRuntime:
    """用于驱动以 WorkflowSpec 为后台的剧本依赖前沿（frontier）调度器。

    支持对步骤节点的依赖图进行构建、依赖项分析、循环依赖验证、拓扑排序，以及实时决策下一个可运行的节点集。
    """

    nodes: Dict[str, DAGRuntimeNode]
    order: List[str]

    @classmethod
    def from_workflow(cls, workflow: WorkflowSpec) -> "PlaybookDAGRuntime":
        """从给定的工作流规范构建并初始化一个 `PlaybookDAGRuntime` 运行时对象。

        Args:
            workflow (WorkflowSpec): 输入的工作流规范定义。

        Returns:
            PlaybookDAGRuntime: 构建完成并经过合法性校验的 DAG 运行时调度器。

        Raises:
            DomainError: 当发现步骤 ID 重复时。
        """
        nodes: Dict[str, DAGRuntimeNode] = {}
        order: List[str] = []
        for index, step in enumerate(workflow.steps):
            if step.id in nodes:
                raise DomainError("workflow.duplicate_step_id", f"Workflow step id '{step.id}' appears more than once.")
            # 解析并确定当前步骤的直接依赖项
            dependencies = cls._dependencies_for_step(step, workflow.steps, index)
            nodes[step.id] = DAGRuntimeNode(step=step, dependencies=dependencies)
            order.append(step.id)
            
        runtime = cls(nodes=nodes, order=order)
        # 执行依赖链和路由校验
        runtime.validate()
        return runtime

    @staticmethod
    def _dependencies_for_step(step: WorkflowStep, steps: List[WorkflowStep], index: int) -> List[str]:
        """解析并计算当前步骤的入度依赖项。

        如果步骤中声明的输入键（input_keys）存在于已知的其他步骤 ID 中，则作为显式依赖；
        若无显式输入键，除首个步骤外，默认依赖于列表中前一个线性相邻步骤。

        Args:
            step (WorkflowStep): 待解析依赖的步骤。
            steps (List[WorkflowStep]): 整个工作流的步骤列表。
            index (int): 当前步骤在列表中的索引。

        Returns:
            List[str]: 解析出的前置依赖步骤 ID 列表。
        """
        explicit = [item for item in step.input_keys if item in {candidate.id for candidate in steps}]
        if explicit:
            return explicit
        if index == 0:
            return []
        return [steps[index - 1].id]

    def validate(self) -> None:
        """执行 DAG 图的完整性校验。

        校验包括：
        1. 检查是否存在悬空的依赖（指向未定义的步骤）；
        2. 检查 on_success/on_failure 路由目标是否存在；
        3. 检测图中是否存在循环依赖（通过拓扑排序）。

        Raises:
            DomainError: 当发现任何悬挂路径、无效步骤引用或检测到循环依赖时。
        """
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    raise DomainError(
                        "workflow.dag_dangling_dependency",
                        f"Node '{node.node_id}' depends on unknown node '{dep}'.",
                        details={"node_id": node.node_id, "dependency": dep},
                    )
            for route_name, target in (("on_success", node.step.on_success), ("on_failure", node.step.on_failure)):
                if target and target not in self.nodes:
                    raise DomainError(
                        "workflow.dag_dangling_route",
                        f"Node '{node.node_id}' has {route_name} route to unknown node '{target}'.",
                        details={"node_id": node.node_id, "route": route_name, "target": target},
                    )
        # 内部触发拓扑排序以校验并抛出潜在的循环依赖
        self.topological_order()

    def topological_order(self) -> List[str]:
        """通过深度优先搜索（DFS）计算当前 DAG 图的拓扑排序序列。

        Returns:
            List[str]: 满足拓扑依赖关系的节点 ID 序列。

        Raises:
            DomainError: 当检测到循环依赖时抛出。
        """
        visited: Dict[str, str] = {}
        ordered: List[str] = []

        def visit(node_id: str) -> None:
            state = visited.get(node_id)
            if state == "visiting":
                raise DomainError("workflow.dag_cycle", f"Cycle detected at workflow node '{node_id}'.")
            if state == "visited":
                return
            visited[node_id] = "visiting"
            for dep in self.nodes[node_id].dependencies:
                visit(dep)
            visited[node_id] = "visited"
            ordered.append(node_id)

        for node_id in self.order:
            visit(node_id)
        return ordered

    def ready_node_ids(self, *, completed: Set[str], running: Optional[Set[str]] = None, failed: Optional[Set[str]] = None) -> List[str]:
        """根据当前已完成、正在运行以及失败的节点状态，计算出依赖已满足且可执行的就绪节点 ID 列表。

        Args:
            completed (Set[str]): 已经成功完成的节点 ID 集合。
            running (Optional[Set[str]], optional): 正在运行的节点 ID 集合。默认为 None。
            failed (Optional[Set[str]], optional): 执行失败的节点 ID 集合。默认为 None。

        Returns:
            List[str]: 所有当前处于就绪状态、可以直接分发运行的节点 ID 列表。
        """
        running = running or set()
        failed = failed or set()
        ready: List[str] = []
        for node_id in self.topological_order():
            # 过滤掉已处于完成、运行或失败状态的节点
            if node_id in completed or node_id in running or node_id in failed:
                continue
            node = self.nodes[node_id]
            # 只有当所有前置依赖项都已成功完成，该节点才是 Ready 状态
            if all(dep in completed for dep in node.dependencies):
                ready.append(node_id)
        return ready

    def route_for(self, node_id: str, result: Dict[str, Any]) -> Optional[str]:
        """根据单个步骤节点的执行结果字典，动态计算其应当流转的下一个节点 ID。

        Args:
            node_id (str): 当前评估节点的 ID。
            result (Dict[str, Any]): 该步骤执行产生的返回结果字典。

        Returns:
            Optional[str]: 下一个目标节点 ID；若无显式或静态定义的目标则返回 None。
        """
        node = self.nodes[node_id]
        # 1. 优先采用步骤返回载荷中显式指定的下一个节点/步骤
        explicit_next = result.get("next_step_id") or result.get("next_node_id")
        if explicit_next:
            self.require_node(str(explicit_next))
            return str(explicit_next)
            
        # 2. 根据结果状态值，回退到匹配对应的 on_success 或 on_failure 静态静态配置
        status = str(result.get("status", "")).lower()
        if status in {"succeeded", "success", "pass", "passed"} and node.step.on_success:
            return node.step.on_success
        if status in {"failed", "failure", "blocked", "error"} and node.step.on_failure:
            return node.step.on_failure
        return None

    def downstream_node_ids(self, node_id: str) -> List[str]:
        """获取依赖于指定节点的所有下游直接子节点 ID 列表。

        Args:
            node_id (str): 目标节点 ID。

        Returns:
            List[str]: 下游直接子节点的 ID 列表。
        """
        self.require_node(node_id)
        return [candidate_id for candidate_id, node in self.nodes.items() if node_id in node.dependencies]

    def require_node(self, node_id: str) -> DAGRuntimeNode:
        """安全检索一个节点，若该节点在 DAG 图中不存在则抛出 DomainError。

        Args:
            node_id (str): 待查找的节点 ID。

        Returns:
            DAGRuntimeNode: 获取到的 DAG 节点对象。

        Raises:
            DomainError: 当节点不存在时抛出。
        """
        try:
            return self.nodes[node_id]
        except KeyError as exc:
            raise DomainError("workflow.dag_unknown_node", f"Unknown workflow DAG node '{node_id}'.") from exc


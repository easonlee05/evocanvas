"""EvoCanvas Playbook 的 DAG 任务图执行模型定义。

提供静态有向无环图（DAG）的节点定义（DAGNode）与执行流管理器（TaskDAG），
支持基于拓扑排序的节点排程、执行依赖验证、有向环路检测以及持久化读写。
"""
from __future__ import annotations

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from app.core.errors import DomainError
from app.core.persistence import FilePersistenceMixin


class NodeStatus(Enum):
    """DAG 节点的生命周期执行状态枚举。"""
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DAGNode:
    """DAG 图中的单个执行节点实体。

    Attributes:
        node_id: 节点的唯一 ID 标识。
        action_type: 节点所对应的动作或引擎类型（如 'agent', 'gate', 'artifact', 'system'）。
        status: 节点的当前执行状态。
        dependencies: 该节点直接前置依赖的节点 ID 列表。
        conditions: 该节点被激活触发的控制流条件约束字典。
        result: 节点执行完成后返回的任意结果产物。
    """
    node_id: str
    action_type: str  # e.g., 'agent', 'gate', 'artifact', 'system'
    status: NodeStatus = NodeStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None

    def is_ready(self, all_nodes: Dict[str, 'DAGNode']) -> bool:
        """Check if all dependencies are COMPLETED."""
        if self.status != NodeStatus.PENDING:
            return False
        for dep in self.dependencies:
            node = all_nodes.get(dep)
            if not node or node.status != NodeStatus.COMPLETED:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "action_type": self.action_type,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "conditions": self.conditions,
            "result": self.result
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DAGNode":
        return cls(
            node_id=data["node_id"],
            action_type=data["action_type"],
            status=NodeStatus(data.get("status", "pending")),
            dependencies=list(data.get("dependencies", [])),
            conditions=dict(data.get("conditions", {})),
            result=data.get("result")
        )



@dataclass
class TaskDAG(FilePersistenceMixin):
    """表示一个完整任务有向无环图的执行流管理器，支持对其依赖进行静态及动态拓扑排序与校验。

    Attributes:
        graph_id: 有向无环图的唯一 ID 标识。
        nodes: DAG 图中包含的所有节点，以键值对 node_id -> DAGNode 的形式进行映射存储。
    """
    graph_id: str
    nodes: Dict[str, DAGNode] = field(default_factory=dict)

    def add_node(self, node: DAGNode) -> None:
        self.nodes[node.node_id] = node

    def get_executable_nodes(self) -> List[DAGNode]:
        """Return nodes whose dependencies are met and are currently pending."""
        return [n for n in self.nodes.values() if n.is_ready(self.nodes)]

    def is_completed(self) -> bool:
        return all(n.status == NodeStatus.COMPLETED for n in self.nodes.values())

    def has_failed(self) -> bool:
        return any(n.status == NodeStatus.FAILED for n in self.nodes.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskDAG":
        nodes_data = data.get("nodes", {})
        nodes = {nid: DAGNode.from_dict(ndata) for nid, ndata in nodes_data.items()}
        return cls(
            graph_id=data["graph_id"],
            nodes=nodes
        )

    def validate_dag(self) -> None:
        """Validate DAG constraints including dangling dependencies and cycles."""
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    raise DomainError(
                        code="dag.dangling_dependency",
                        message=f"Node '{node.node_id}' has dangling dependency on '{dep}'"
                    )
        self.get_topological_sort()

    def get_topological_sort(self) -> List[str]:
        """Return the topological sort order of the node IDs.
        
        Raises DomainError if dangling dependencies or cyclic dependencies are detected.
        """
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    raise DomainError(
                        code="dag.dangling_dependency",
                        message=f"Node '{node.node_id}' has dangling dependency on '{dep}'"
                    )

        visited = {}  # node_id -> state (1: visiting, 2: visited)
        order = []

        def dfs(node_id: str):
            state = visited.get(node_id, 0)
            if state == 1:
                raise DomainError(
                    code="dag.cyclic_dependency",
                    message=f"Cyclic dependency detected at node '{node_id}'"
                )
            if state == 2:
                return

            visited[node_id] = 1
            node = self.nodes[node_id]
            for dep in node.dependencies:
                dfs(dep)
            visited[node_id] = 2
            order.append(node_id)

        for node_id in self.nodes:
            dfs(node_id)
        return order

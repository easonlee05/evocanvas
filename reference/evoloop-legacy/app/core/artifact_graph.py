"""Evoloop 3.0 交付资产关系图（ArtifactGraph）核心契约定义。

本模块构建了以机器规格书（machine_spec）为唯一真相源（Source of Truth），
管理需求、决策、验收协议、代码包、评审结论等交付资产及其派生/覆盖/评审依赖关系的有向图。
提供严格的结构合法性校验规则（如单 Truth 节点校验、不可逆向派生、有向环路检测等）。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from app.core.persistence import FilePersistenceMixin


SOURCE_OF_TRUTH_ARTIFACT = "machine_spec"
HUMAN_PROJECTION_ARTIFACTS = frozenset({"human_brief", "optional_prd", "optional_manual"})


class ArtifactGraphValidationError(ValueError):
    """交付资产关系图约束条件校验失败时抛出的异常。"""
    pass


class ArtifactNodeType(str, Enum):
    """交付资产图中节点的类型枚举。"""
    REQUIREMENT = "requirement"
    DECISION = "decision"
    HUMAN_BRIEF = "human_brief"
    MACHINE_SPEC = SOURCE_OF_TRUTH_ARTIFACT
    AGENT_PACKAGE = "agent_package"
    ACCEPTANCE_PROTOCOL = "acceptance_protocol"
    REVIEW_CHECKLIST = "review_checklist"
    REVIEW_RESULT = "review_result"
    TRACEABILITY_MAP = "traceability_map"
    DECISION_LOG = "decision_log"
    OPTIONAL_PRD = "optional_prd"
    OPTIONAL_MANUAL = "optional_manual"


class ArtifactEdgeType(str, Enum):
    """交付资产图中各节点之间依赖与指向关系的边类型枚举。"""
    DERIVES_FROM = "derives_from"
    ADDRESSES_REQUIREMENT = "addresses_requirement"
    RESOLVES_DECISION = "resolves_decision"
    VALIDATES = "validates"
    REVIEWS = "reviews"
    SUPERSEDES = "supersedes"


@dataclass
class ArtifactRef:
    """指向底层具体物理存储实体的引用信息描述类。

    Attributes:
        name: 资产引用名称（如 'app_core_task_py'）。
        version: 资产引用版本号。
        storage_uri: 该资产在持久化介质中的绝对/相对存储 URI（如 file:///...）。
        checksum: 校验和签名（MD5 或 SHA256），用于防篡改完整性校验。
        metadata: 其他扩展属性字典。
    """
    name: str
    version: Optional[str] = None
    storage_uri: Optional[str] = None
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 ArtifactRef 转换为字典。

        Returns:
            Dict[str, Any]: 转换后的字典。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactRef":
        """从字典反序列化生成 ArtifactRef 实例。

        Args:
            data: 包含引用信息的元数据字典。

        Returns:
            ArtifactRef: 还原后的引用实体。
        """
        return cls(
            name=data["name"],
            version=data.get("version"),
            storage_uri=data.get("storage_uri"),
            checksum=data.get("checksum"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ArtifactNode:
    """交付资产图中的单个资产节点包装实体。

    Attributes:
        node_id: 节点唯一 ID。
        type: 交付资产节点类型。
        artifact_ref: 指向物理存储或详细元数据的 ArtifactRef 引用。
        summary: 节点内容的简短中文说明。
        created_by: 创建本节点的角色或 worker_id，默认为 'system'。
        metadata: 其他元数据。
    """
    node_id: str
    type: ArtifactNodeType
    artifact_ref: ArtifactRef
    summary: str = ""
    created_by: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_source_of_truth(self) -> bool:
        """判断当前节点是否为全局真相源（machine_spec）节点。

        Returns:
            bool: 是则返回 True，否则返回 False。
        """
        return self.type == ArtifactNodeType.MACHINE_SPEC

    def to_dict(self) -> Dict[str, Any]:
        """将 ArtifactNode 序列化为字典。

        Returns:
            Dict[str, Any]: 序列化后的字典。
        """
        return {
            "node_id": self.node_id,
            "type": self.type.value,
            "artifact_ref": self.artifact_ref.to_dict(),
            "summary": self.summary,
            "created_by": self.created_by,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactNode":
        """从字典反序列化重构 ArtifactNode 实例。

        Args:
            data: 包含资产节点元数据的字典.

        Returns:
            ArtifactNode: 反序列化出的资产节点包装实体。
        """
        return cls(
            node_id=data["node_id"],
            type=ArtifactNodeType(data["type"]),
            artifact_ref=ArtifactRef.from_dict(data["artifact_ref"]),
            summary=data.get("summary", ""),
            created_by=data.get("created_by", "system"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ArtifactEdge:
    """表示交付资产图中，两个节点之间关系的边描述实体。

    Attributes:
        edge_id: 边的唯一 ID。
        from_node_id: 起始资产节点 ID。
        to_node_id: 目标指向资产节点 ID。
        type: 关系的具体边类型。
        summary: 关系的文字描述摘要。
        metadata: 额外附带的元数据。
    """
    edge_id: str
    from_node_id: str
    to_node_id: str
    type: ArtifactEdgeType
    summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 ArtifactEdge 序列化为字典。

        Returns:
            Dict[str, Any]: 序列化后的字典。
        """
        data = asdict(self)
        data["type"] = self.type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactEdge":
        """从字典反序列化重构 ArtifactEdge 实例。

        Args:
            data: 边元数据字典。

        Returns:
            ArtifactEdge: 重构出的边关系实体。
        """
        return cls(
            edge_id=data["edge_id"],
            from_node_id=data["from_node_id"],
            to_node_id=data["to_node_id"],
            type=ArtifactEdgeType(data["type"]),
            summary=data.get("summary", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ArtifactGraph(FilePersistenceMixin):
    """交付资产依赖及派生有向无环图管理器。

    Attributes:
        work_id: 关联的工作项 ID。
        nodes: 图中包含的所有资产节点列表。
        edges: 图中包含的所有关系边列表。
        graph_id: 图的唯一 ID，自动生成。
        metadata: 图维度的元数据扩展项。
    """
    work_id: str
    nodes: List[ArtifactNode] = field(default_factory=list)
    edges: List[ArtifactEdge] = field(default_factory=list)
    graph_id: str = field(default_factory=lambda: f"graph_{uuid4().hex[:12]}")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def source_of_truth_node(self) -> Optional[ArtifactNode]:
        """获取当前交付资产关系图中的唯一真相源（machine_spec）节点。

        Returns:
            Optional[ArtifactNode]: 真相源节点，若不存在返回 None。
        """
        for node in self.nodes:
            if node.is_source_of_truth:
                return node
        return None

    def validate(self) -> None:
        """执行资产依赖图核心规则边界拦截校验。

        校验规则如下：
        1. 悬挂边拦截：任何边的起始/目标节点必须在 nodes 列表中。
        2. 真相源机器规格唯一性：如果图包含派生/投影节点，必须有且仅有一个 machine_spec 真相源节点。
        3. 可追溯连通性：任何投影/派生节点必须与 machine_spec 节点在无向连通分量上可达（连通）。
        4. 严禁反向派生：真相源 machine_spec 绝对不允许通过 derives_from 指向任何派生/投影节点。
        5. 有向环路检测：交付资产依赖链路必须是有向无环图（DAG），严禁产生任何依赖闭环死循环。
        6. 边类型与节点类型校验矩阵：验证 edge.type 的使用与其源节点、目标节点类型是否完美符合语义规范。

        Raises:
            ArtifactGraphValidationError: 当以上任何规则校验失败时抛出。
        """
        nodes_by_id = {node.node_id: node for node in self.nodes}

        # 1. 悬挂边/未定义节点依赖拦截
        for edge in self.edges:
            if edge.from_node_id not in nodes_by_id or edge.to_node_id not in nodes_by_id:
                raise ArtifactGraphValidationError(
                    f"ArtifactGraph contains a dangling edge '{edge.edge_id}' referencing "
                    f"non-existent node: from_node_id='{edge.from_node_id}', to_node_id='{edge.to_node_id}'."
                )

        spec_nodes = [node for node in self.nodes if node.is_source_of_truth]
        
        project_or_derived_types = {
            ArtifactNodeType.HUMAN_BRIEF,
            ArtifactNodeType.OPTIONAL_PRD,
            ArtifactNodeType.OPTIONAL_MANUAL,
            ArtifactNodeType.AGENT_PACKAGE,
            ArtifactNodeType.ACCEPTANCE_PROTOCOL,
            ArtifactNodeType.REVIEW_RESULT,
            ArtifactNodeType.REVIEW_CHECKLIST,
            ArtifactNodeType.TRACEABILITY_MAP,
            ArtifactNodeType.MACHINE_SPEC
        }
        
        has_project_or_derived = any(node.type in project_or_derived_types for node in self.nodes)
        
        if has_project_or_derived:
            if len(spec_nodes) != 1:
                raise ArtifactGraphValidationError(
                    f"ArtifactGraph must contain exactly one machine_spec node when containing "
                    f"projections or derived artifacts, but found {len(spec_nodes)}."
                )
            
            spec_node = spec_nodes[0]
            spec_node_id = spec_node.node_id
            
            # Compute connectivity using undirected BFS
            from collections import defaultdict
            adj = defaultdict(list)
            for edge in self.edges:
                adj[edge.from_node_id].append(edge.to_node_id)
                adj[edge.to_node_id].append(edge.from_node_id)
                
            visited = {spec_node_id}
            queue = [spec_node_id]
            while queue:
                curr = queue.pop(0)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
                        
            # Ensure all projection or derived nodes are connected to the machine_spec
            target_types = project_or_derived_types - {ArtifactNodeType.MACHINE_SPEC}
            for node in self.nodes:
                if node.type in target_types and node.node_id not in visited:
                    raise ArtifactGraphValidationError(
                        f"Artifact node '{node.node_id}' of type '{node.type.value}' "
                        f"is disconnected from the machine_spec source of truth."
                    )
                    
            # Prevent reverse derives_from dependencies
            projection_node_ids = {node.node_id for node in self.nodes if node.type in target_types}
            for edge in self.edges:
                if edge.type == ArtifactEdgeType.DERIVES_FROM:
                    if edge.from_node_id == spec_node_id and edge.to_node_id in projection_node_ids:
                        to_node = nodes_by_id[edge.to_node_id]
                        raise ArtifactGraphValidationError(
                            f"Edge '{edge.edge_id}' is invalid because the source of truth "
                            f"cannot derive from projection/derived node '{to_node.node_id}' "
                            f"of type '{to_node.type.value}'."
                        )

        # 4. 有向图环路检测 (Cycle Detection)
        # 构建有向邻接表
        from collections import defaultdict
        digraph = defaultdict(list)
        for edge in self.edges:
            digraph[edge.from_node_id].append(edge.to_node_id)
            
        visited_states = {}  # node_id -> 0 (visiting), 1 (visited)
        
        def has_cycle(node_id: str) -> bool:
            visited_states[node_id] = 0  # 标记为访问中
            for neighbor in digraph[node_id]:
                state = visited_states.get(neighbor)
                if state == 0:
                    return True  # 发现返祖边，有环
                elif state is None:
                    if has_cycle(neighbor):
                        return True
            visited_states[node_id] = 1  # 标记为已访问
            return False

        for node in self.nodes:
            if node.node_id not in visited_states:
                if has_cycle(node.node_id):
                    raise ArtifactGraphValidationError(
                        f"ArtifactGraph contains a dependency loop/cycle involving node '{node.node_id}'."
                    )

        # 5. 边类型与节点类型强规则匹配矩阵校验
        for edge in self.edges:
            from_node = nodes_by_id[edge.from_node_id]
            to_node = nodes_by_id[edge.to_node_id]
                
            if edge.type == ArtifactEdgeType.REVIEWS:
                if from_node.type != ArtifactNodeType.REVIEW_RESULT:
                    raise ArtifactGraphValidationError(
                        f"Edge '{edge.edge_id}' type 'reviews' is incompatible: source must be review_result, got '{from_node.type.value}'."
                    )
            elif edge.type == ArtifactEdgeType.VALIDATES:
                if from_node.type not in {ArtifactNodeType.ACCEPTANCE_PROTOCOL, ArtifactNodeType.REVIEW_CHECKLIST}:
                    raise ArtifactGraphValidationError(
                        f"Edge '{edge.edge_id}' type 'validates' is incompatible: source must be acceptance_protocol or review_checklist, got '{from_node.type.value}'."
                    )
            elif edge.type == ArtifactEdgeType.ADDRESSES_REQUIREMENT:
                if to_node.type != ArtifactNodeType.REQUIREMENT:
                    raise ArtifactGraphValidationError(
                        f"Edge '{edge.edge_id}' type 'addresses_requirement' is incompatible: target must be requirement, got '{to_node.type.value}'."
                    )
            elif edge.type == ArtifactEdgeType.RESOLVES_DECISION:
                if to_node.type != ArtifactNodeType.DECISION:
                    raise ArtifactGraphValidationError(
                        f"Edge '{edge.edge_id}' type 'resolves_decision' is incompatible: target must be decision, got '{to_node.type.value}'."
                    )
            elif edge.type == ArtifactEdgeType.SUPERSEDES:
                if from_node.type != to_node.type:
                    raise ArtifactGraphValidationError(
                        f"Edge '{edge.edge_id}' type 'supersedes' is incompatible: source type '{from_node.type.value}' must equal target type '{to_node.type.value}'."
                    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "work_id": self.work_id,
            "nodes": [item.to_dict() for item in self.nodes],
            "edges": [item.to_dict() for item in self.edges],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactGraph":
        return cls(
            graph_id=data.get("graph_id", f"graph_{uuid4().hex[:12]}"),
            work_id=data["work_id"],
            nodes=[ArtifactNode.from_dict(item) for item in data.get("nodes", [])],
            edges=[ArtifactEdge.from_dict(item) for item in data.get("edges", [])],
            metadata=dict(data.get("metadata", {})),
        )


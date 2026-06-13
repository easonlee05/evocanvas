"""Evoloop 3.0 核心契约层交付产物域模型定义。

本模块定义了交付资产实体（Artifact）及其持久化元数据格式。
在 Evoloop 3.0 架构中，Artifact 作为 ArtifactGraph 的节点，用于支持产品迭代链和变更追踪。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class Artifact:
    """产品交付产物实体，代表工作流推进过程中产生或消费的数据/文档资产（如 prd、manual、spec 等）。

    Attributes:
        artifact_id: 交付产物的唯一标识符。
        task_id: 生成该产物关联的任务或工作项 ID。
        name: 交付产物名称（通常是它的逻辑名称，如 'machine_spec'）。
        version: 该资产的版本号，用于支持多版本迭代。
        content_type: 内容类型，默认为 "text/markdown"。
        created_by: 创建该产物的执行器或角色（如 'compiler'）。
        summary: 产物的摘要性描述。
        content: 产物的详细文本内容，可选。
    """
    artifact_id: str
    task_id: str
    name: str
    version: int
    content_type: str = "text/markdown"
    created_by: str = "system"
    summary: str = ""
    content: Optional[str] = None

    def to_dict(self, include_content: bool = False) -> Dict[str, Any]:
        """将交付产物实例转换为字典格式。

        Args:
            include_content: 是否包含详细内容文本。默认为 False，主要是为了防范在不需要时加载庞大的正文影响效率。

        Returns:
            Dict[str, Any]: 转换后的字典。
        """
        data = asdict(self)
        if not include_content:
            data.pop("content", None)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Artifact":
        """从字典反序列化生成交付产物实例。

        Args:
            data: 包含交付产物元数据的字典。

        Returns:
            Artifact: 反序列化出的交付产物实例。
        """
        return cls(
            artifact_id=data["artifact_id"],
            task_id=data["task_id"],
            name=data["name"],
            version=int(data.get("version", 1)),
            content_type=data.get("content_type", "text/markdown"),
            created_by=data.get("created_by", "system"),
            summary=data.get("summary", ""),
            content=data.get("content"),
        )

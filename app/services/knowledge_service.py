"""知识库检索的外观服务（Facade）。

本服务模块为系统提供统一的知识库检索接口，
可根据配置代理到不同的底层知识检索后端（如基于向量或命令行的 GBrain，或本地 Snapshots）。
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class KnowledgeService:
    """知识检索外观服务类。

    提供检索接口，供编排流、任务上下文或 Agent 调用，以获取辅助知识或经验法则。
    """

    def __init__(self, backend: Any):
        """初始化 KnowledgeService 实例。

        Args:
            backend: 底层提供 retrieve 检索接口的具体知识服务后端（如 GBrainKnowledge 实例）。
        """
        self.backend = backend

    def retrieve(self, query: str, scope: Optional[str] = None) -> Dict[str, Any]:
        """在配置的后端知识库中检索与关键词相符的记录。

        Args:
            query: 检索的关键词或查询语句。
            scope: 可选的作用域分区过滤。

        Returns:
            Dict[str, Any]: 结构化的知识检索结果字典。
        """
        return self.backend.retrieve(query=query, scope=scope)


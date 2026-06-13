"""Evoloop 3.0 核心契约层端口定义模块。

定义了用于隔离内核与外部大模型、知识检索及存储层提供商的依赖倒置端口（Port / Protocol）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol


@dataclass
class LLMResult:
    """大语言模型调用结果承载对象。

    Attributes:
        content: 模型返回的纯文本内容。
        structured: 模型返回的结构化数据（如 JSON 转换得到的字典）。
    """
    content: str
    structured: Dict[str, Any] = field(default_factory=dict)


class LLMPort(Protocol):
    """大语言模型通信端口协议，定义了内核与 LLM 交互的抽象接口。"""

    def invoke(self, role: str, prompt: str, context: Dict[str, Any]) -> LLMResult:
        """调用大语言模型。

        Args:
            role: 执行调用的角色定位（如 'compiler', 'reviewer'）。
            prompt: 具体的提示词。
            context: 调用的附加上下文。

        Returns:
            LLMResult: 模型调用的文本与结构化结果。
        """
        ...

    def invoke_with_tools(
        self,
        role: str,
        prompt: str,
        context: Dict[str, Any],
        tools: List[Dict[str, Any]],
        tool_messages: List[Dict[str, Any]] | None = None,
    ) -> LLMResult:
        """调用支持 provider-native tool calling 的大语言模型。

        该方法是 AgentSession 运行时的优先路径；不支持原生工具协议的实现可不提供，
        AgentRuntime 会自动退回到普通 invoke() + JSON tool_calls 兼容协议。
        """
        ...


class KnowledgePort(Protocol):
    """知识库/检索服务端口协议，定义了内核向外部知识底座查询信息的抽象接口。"""

    def retrieve(self, query: str, scope: str | None = None) -> Dict[str, Any]:
        """检索相关的背景知识或历史资产证据。

        Args:
            query: 检索关键词或问句。
            scope: 检索范围限定，可选。

        Returns:
            Dict[str, Any]: 包含检索结果列表及分数的字典。
        """
        ...


class StoragePort(Protocol):
    """持久化存储端口协议，抽象了文件、检查点、产品上下文以及资产图的存储读写操作。"""
    root: Any

    def append_event(self, event: Any) -> Any:
        """向审计存储追加一个事件。

        Args:
            event: 事件实体。

        Returns:
            Any: 存储追加结果。
        """
        ...

    def save_context(self, context: Any) -> None:
        """保存任务的运行上下文。

        Args:
            context: 运行上下文实例。
        """
        ...

    def save_product_context(self, work_id: str, context: Any) -> None:
        """保存指定工作项的产品上下文。

        Args:
            work_id: 工作项 ID。
            context: 产品上下文实例。
        """
        ...

    def load_product_context(self, work_id: str) -> Any | None:
        """加载指定工作项的产品上下文。

        Args:
            work_id: 工作项 ID。

        Returns:
            Any | None: 产品上下文实例，若不存在则返回 None。
        """
        ...

    def save_artifact_graph(self, work_id: str, graph: Any) -> None:
        """保存指定工作项的交付资产关系图。

        Args:
            work_id: 工作项 ID。
            graph: 资产图实例。
        """
        ...

    def load_artifact_graph(self, work_id: str) -> Any | None:
        """加载指定工作项的交付资产关系图。

        Args:
            work_id: 工作项 ID。

        Returns:
            Any | None: 交付资产图实例，若不存在则返回 None。
        """
        ...

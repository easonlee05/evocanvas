"""EvoCanvas 核心契约层域异常定义模块。

定义 EvoCanvas 后端内核共享的领域级异常与错误模型。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class DomainError(Exception):
    """领域错误模型实体，用于在核心内核中传播并持久化结构化错误信息。

    Attributes:
        code: 错误标识码，代表特定的业务/系统错误类型（例如 'persistence.save_failed'）。
        message: 针对错误的可读描述。
        details: 错误的额外上下文细节，例如校验失败的具体字段。
    """
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """初始化后的后置处理器，调用基类 Exception 初始化方法传递错误消息。"""
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """将领域错误转换成字典格式。

        Returns:
            Dict[str, Any]: 包含 code, message, details 的字典。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "DomainError | None":
        """从字典格式反序列化得到 DomainError 实例。

        Args:
            data: 包含错误字段的字典。

        Returns:
            DomainError | None: 反序列化出的领域错误实例，如果输入为 None 则返回 None。
        """
        if not data:
            return None
        return cls(
            code=data.get("code", "unknown"),
            message=data.get("message", ""),
            details=data.get("details"),
        )


class BackendDomainException(Exception):
    """后端领域异常包装器，主要用于将结构化的 DomainError 转化为标准的 Python 异常抛出。

    Attributes:
        error: 内部包装的结构化 DomainError 实例。
    """
    def __init__(self, error: DomainError):
        """初始化后端领域异常。

        Args:
            error: 需要包装的领域错误模型。
        """
        super().__init__(error.message)
        self.error = error

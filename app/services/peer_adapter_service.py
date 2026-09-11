"""PeerAdapter 协作适配服务。

该模块定义 EvoCanvas 面向 AI 技术同事的最小派发层：
- 控制面按 `peer_target` 选择已注册 handler
- handler 接收 agent package 文本并返回结构化 result bundle
- 本层只负责协作通道分发，不负责直接修改控制面状态
"""
from __future__ import annotations

from typing import Any, Dict, Protocol


class PeerHandler(Protocol):
    """AI 技术同事协作 handler 协议。"""

    def execute(self, task: Any, package_text: str) -> Dict[str, Any]:
        """执行指定任务包并返回结构化 result bundle。"""
        ...


class PeerAdapterService:
    """管理 AI 技术同事协作 handler 的注册与派发。"""

    def __init__(self):
        """初始化空的协作 handler 注册表。"""
        self.adapters: Dict[str, PeerHandler] = {}

    def register_adapter(self, target_type: str, handler: PeerHandler) -> None:
        """注册指定协作目标的 handler。"""
        self.adapters[target_type] = handler

    def dispatch(self, task: Any, package_text: str, target_type: str) -> Dict[str, Any]:
        """把 agent package 派发给指定 AI 技术同事 handler。

        Args:
            task: 当前任务对象。
            package_text: 已准备好的 agent package 文本。
            target_type: 目标协作通道，例如 `codex`、`claude`、`cursor`。

        Returns:
            Dict[str, Any]: handler 返回的结构化 result bundle。

        Raises:
            ValueError: 当目标没有已注册 handler 时抛出。
        """
        handler = self.adapters.get(target_type)
        if not handler:
            raise ValueError(f"no peer adapter registered for {target_type}")
        return handler.execute(task, package_text)

"""Legacy worker adapter compatibility layer.

该模块保留 3.0 时期的 `Worker*` 命名以兼容旧代码，
但语义上应理解为 AI 技术同事协作适配层，而不是“下游从属执行器”。
在 3.1 中，这一层的目标名称是 PeerAdapter / peer collaboration。
"""
from __future__ import annotations

from typing import Dict, Any, Protocol


class WorkerTargetType:
    """兼容旧命名的 AI 技术同事协作目标类型常量定义。"""
    CLI = "cli"
    MCP = "mcp"
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"


class WorkerHandler(Protocol):
    """兼容旧命名的协作适配器执行处理器协议。"""
    
    def execute(self, package_path: str) -> Dict[str, Any]:
        """执行指定路径下的智能体任务包。

        Args:
            package_path: 智能体任务包的磁盘绝对路径或相对路径。

        Returns:
            Dict[str, Any]: 执行结果字典，包含执行状态与产出信息。
        """
        ...


class WorkerAdapterService:
    """兼容旧命名的协作适配器分发服务类。

    抽象并隔离不同 AI 技术同事执行端的细节，通过注册适配器实现对各种协作通道的派发。
    """
    
    def __init__(self, sandbox_manager: Any = None):
        """初始化 WorkerAdapterService 实例。

        Args:
            sandbox_manager: 可选的沙箱管理器实例，若不指定则在内部延迟加载并初始化默认 SandboxManager。
        """
        self.adapters: Dict[str, WorkerHandler] = {}
        if not sandbox_manager:
            from app.services.sandbox.manager import SandboxManager
            sandbox_manager = SandboxManager()
        self.sandbox = sandbox_manager

    def register_adapter(self, target_type: str, handler: WorkerHandler) -> None:
        """注册对接特定类型下游执行端的处理器适配器。

        Args:
            target_type: 下游执行端类型标识（参见 WorkerTargetType）。
            handler: 实现了 WorkerHandler 协议的处理器适配器实例。
        """
        self.adapters[target_type] = handler

    def dispatch(self, package_path: str, target_type: str) -> Dict[str, Any]:
        """将打包的 Agent 任务包派发给指定的下游执行端并执行。

        Args:
            package_path: 智能体任务包的物理路径。
            target_type: 下游执行端的目标类型。

        Raises:
            ValueError: 当指定的目标类型没有注册对应的适配器时抛出。

        Returns:
            Dict[str, Any]: 执行结果。
        """
        handler = self.adapters.get(target_type)
        if not handler:
            raise ValueError(f"No adapter registered for {target_type}")
            
        print(f"[*] Dispatching {package_path} to worker type: {target_type}")
        return handler.execute(package_path)

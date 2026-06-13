"""沙箱隔离环境管理器（SandboxManager）。

本模块提供沙箱执行流程的总体调度，负责在运行时动态检测宿主机的 Docker 容器环境可用性；
并智能选择 Docker 强隔离适配器或轻量级子进程隔离适配器来执行下游代码。
"""
from __future__ import annotations

import logging
from typing import Optional

from app.services.sandbox.adapters.base import SandboxAdapter, ExecutionResult
from app.services.sandbox.adapters.subprocess_adapter import SubprocessSandboxAdapter
from app.services.sandbox.config import SandboxConfig

logger = logging.getLogger(__name__)


class SandboxManager:
    """沙箱执行适配调度管理器类。

    维护具体选用的沙箱适配器实例，并作为外部系统调用沙箱的统一入口。
    """

    def __init__(self, force_subprocess: bool = False):
        """初始化 SandboxManager 实例。

        Args:
            force_subprocess: 是否强制关闭 Docker 检测并锁定使用 Subprocess 适配器。
        """
        self.adapter: SandboxAdapter = self._resolve_adapter(force_subprocess)

    def _resolve_adapter(self, force_subprocess: bool) -> SandboxAdapter:
        """根据系统环境与调用参数，自适应解析并选择出最适合的沙箱执行适配器。

        Args:
            force_subprocess: 是否强制 Subprocess。

        Returns:
            SandboxAdapter: 选中的沙箱适配器实例。
        """
        if force_subprocess:
            logger.info("SandboxManager forced to use SubprocessSandboxAdapter")
            return SubprocessSandboxAdapter()
        
        try:
            # 动态尝试引入 Docker 适配器，防止非 Docker 容器化宿主环境在启动时由于缺失 docker-py 库而直接崩溃
            from app.services.sandbox.adapters.docker_adapter import DockerSandboxAdapter
            adapter = DockerSandboxAdapter()
            logger.info("SandboxManager initialized with DockerSandboxAdapter")
            return adapter
        except Exception as e:
            # 当 Docker 未安装、未启动或驱动缺失时，优雅地向下兼容，自动回退到 Subprocess 隔离
            logger.warning(f"Docker sandbox not available ({e}), falling back to SubprocessSandboxAdapter")
            return SubprocessSandboxAdapter()

    def execute(self, code: str, config: Optional[SandboxConfig] = None) -> ExecutionResult:
        """通过选定的适配器在沙箱环境中执行指定代码。

        Args:
            code: 待执行的代码内容字符串。
            config: 可选的沙箱行为控制与资源配额限制参数，如不指定则采用默认 SandboxConfig。

        Returns:
            ExecutionResult: 规范化的代码执行结果实体。
        """
        if not config:
            config = SandboxConfig()
        return self.adapter.execute(code, config)


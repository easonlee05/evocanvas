"""沙箱环境适配层基础抽象与数据结构定义。

本模块声明了沙箱内代码执行输出的标准数据模型 `ExecutionResult`，
以及沙箱适配器的抽象基类 `SandboxAdapter`，用于规范各种沙箱环境（进程、Docker 等）的接口定义。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional

from app.services.sandbox.config import SandboxConfig


@dataclass
class ExecutionResult:
    """沙箱代码执行结果数据类。

    标准地记录代码在沙箱内的执行退出状态、返回码、标准输出和错误输出，以及资源指标。
    """
    # 执行退出状态，取值通常为 "succeeded" 或 "failed"
    status: str
    # 进程执行退出返回码
    exit_code: int
    # 执行捕获的标准输出内容
    stdout: str
    # 执行捕获的标准错误输出内容
    stderr: str
    # 底层执行框架抛出的异常错误详情
    error: Optional[str] = None
    # 是否因超出内存限额而被宿主机 OOM 强杀进程
    oom_killed: bool = False
    # 是否因执行超时而被沙箱调度管理器主动中断
    timeout: bool = False
    # 可选的性能和资源监控指标（如 CPU、内存消耗等）
    metrics: Optional[Dict[str, float]] = None


class SandboxAdapter(ABC):
    """沙箱环境抽象基类。

    为所有的沙箱执行后端适配器（如进程适配器、容器适配器）定义统一的执行抽象接口。
    """

    @abstractmethod
    def execute(self, code: str, config: SandboxConfig) -> ExecutionResult:
        """在沙箱边界与约束中执行不可信的动态脚本代码。

        Args:
            code: 待执行的代码内容。
            config: 沙箱安全与资源控制配额参数。

        Returns:
            ExecutionResult: 代码执行的统一封装结果。
        """
        pass


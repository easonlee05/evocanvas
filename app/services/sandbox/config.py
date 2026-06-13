"""沙箱环境安全限制配置参数模型。

本模块提供了一个统一的 `SandboxConfig` 数据结构，
用于集中配置沙箱执行资源上限、超时期限、内存额度及网络接入策略等参数。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SandboxConfig:
    """沙箱运行配置数据类。

    用于定义对下游代码执行沙箱的精细化资源与行为限制。
    """
    # 沙箱执行超时时长限制（单位：秒），用于防止恶意的死循环卡死系统资源
    timeout_seconds: int = 30
    # 沙箱最大物理内存使用限额（单位：MB）
    memory_limit_mb: int = 128
    # 是否彻底断开网络，默认 True，防止不可信代码向外部上传数据泄密或拉取恶意依赖
    network_disabled: bool = True
    # 分配给沙箱容器的 CPU 权重占比（若使用 Docker 适配器时生效）
    cpu_shares: Optional[int] = None
    # 待运行的代码语言环境，默认 python
    language: str = "python"


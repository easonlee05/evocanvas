"""基于 Docker 容器技术的强隔离沙箱执行适配器。

本模块通过调用 Docker SDK，在完全隔离的容器环境（默认 `python:3.11-slim`）中执行不可信代码。
支持对容器实施内存限额（memory limit）、CPU 限制、禁用网络访问（network_mode='none'），
并对执行超时及 OOM（内存溢出强杀）进行监控与清理。
"""
from __future__ import annotations

import logging
import os
import tempfile
import time
from typing import Any, Dict

from app.services.sandbox.adapters.base import SandboxAdapter, ExecutionResult
from app.services.sandbox.config import SandboxConfig

logger = logging.getLogger(__name__)


class DockerSandboxAdapter(SandboxAdapter):
    """Docker 容器沙箱执行适配器类。

    封装与本地或远程 Docker 守护进程的通信，管理容器生命周期并安全捕获执行状态与系统度量。
    """

    def __init__(self):
        """初始化 DockerSandboxAdapter 实例。

        尝试加载 `docker` SDK 并连接本地守护进程环境。

        Raises:
            ImportError: 当缺少 `docker` 依赖包时抛出。
            RuntimeError: 当无法与 Docker 守护进程建立通信时抛出。
        """
        try:
            import docker
            self.client = docker.from_env()
        except ImportError:
            raise ImportError("docker library is not installed. Install it via `pip install docker`")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Docker daemon: {e}")

    def execute(self, code: str, config: SandboxConfig) -> ExecutionResult:
        """在只读挂载的隔离 Docker 容器内执行动态 Python 代码。

        核心隔离防护措施：
        1. 只读卷挂载（Read-Only volume bind）：限制不可信代码仅能读取而不能破坏宿主机临时代码目录。
        2. 内存限制（mem_limit）：在容器级别实施严格物理内存上限设定。
        3. 网络禁用（network_mode="none"）：彻底切断外部网络，阻断数据外泄。
        4. OOM 事件监测：读取容器 inspect data 获取其是否因 OOM 崩溃。
        5. 超时强杀（Timeout kill）：限制最大执行周期，超时自动终止并强制移除残留容器。

        Args:
            code: 待执行的脚本代码。
            config: 沙箱安全与资源控制配额参数。

        Returns:
            ExecutionResult: 代码执行的统一封装结果。
        """
        if config.language != "python":
            return ExecutionResult(
                status="failed", exit_code=-1, stdout="", stderr="",
                error=f"Unsupported language {config.language} in DockerAdapter"
            )

        import docker
        from docker.errors import APIError, ContainerError, ImageNotFound
        
        image_name = "python:3.11-slim"
        try:
            self.client.images.get(image_name)
        except ImageNotFound:
            logger.info(f"Pulling image {image_name}...")
            self.client.images.pull(image_name)

        start_time = time.monotonic()
        
        # 准备隔离的临时目录以存放执行脚本
        with tempfile.TemporaryDirectory(prefix="docker_sandbox_") as temp_dir:
            script_path = os.path.join(temp_dir, "script.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            mem_limit_str = f"{config.memory_limit_mb}m" if config.memory_limit_mb else None
            
            try:
                # 调起 Docker 容器以运行代码
                container = self.client.containers.run(
                    image=image_name,
                    command=["python3", "/sandbox/script.py"],
                    # 关键安全点：只读（ro）挂载，防止沙箱中运行的脚本篡改或删除挂载的文件系统
                    volumes={temp_dir: {'bind': '/sandbox', 'mode': 'ro'}},
                    working_dir="/sandbox",
                    mem_limit=mem_limit_str,
                    # 关键安全点：网络不可达设定，彻底隔绝泄密与外部拉取风险
                    network_mode="none" if config.network_disabled else "bridge",
                    cpu_shares=config.cpu_shares,
                    detach=True
                )
                
                try:
                    # 等待执行结束并设定最长超时
                    result = container.wait(timeout=config.timeout_seconds)
                    exit_code = result.get('StatusCode', -1)
                    
                    stdout = container.logs(stdout=True, stderr=False).decode("utf-8")
                    stderr = container.logs(stdout=False, stderr=True).decode("utf-8")
                    
                    # 审计容器 OOM (内存被强杀) 状态
                    inspect_data = self.client.api.inspect_container(container.id)
                    oom = inspect_data['State'].get('OOMKilled', False)
                    
                    duration = time.monotonic() - start_time
                    
                    return ExecutionResult(
                        status="succeeded" if exit_code == 0 else "failed",
                        exit_code=exit_code,
                        stdout=stdout,
                        stderr=stderr,
                        oom_killed=oom,
                        metrics={"duration_sec": duration}
                    )
                except Exception as wait_err:
                    import requests
                    # 捕获 requests 超时，代表容器在限制时间内没有跑完，需强制 Kill
                    if isinstance(wait_err, requests.exceptions.ReadTimeout):
                        container.kill()
                        return ExecutionResult(
                            status="failed", exit_code=-1, stdout="", stderr="",
                            error=f"Timeout after {config.timeout_seconds}s", timeout=True
                        )
                    raise
                finally:
                    # 必须保证容器无论执行成功与否、超时与否都被强行销毁，防止资源泄露
                    try:
                        container.remove(force=True)
                    except Exception:
                        pass
            
            except APIError as api_err:
                logger.error(f"Docker API Error: {api_err}")
                return ExecutionResult(
                    status="failed", exit_code=-1, stdout="", stderr="", error=str(api_err)
                )
            except Exception as e:
                logger.error(f"Docker Sandbox execution error: {e}")
                return ExecutionResult(
                    status="failed", exit_code=-1, stdout="", stderr="", error=str(e)
                )


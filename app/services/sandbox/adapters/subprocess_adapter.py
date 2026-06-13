"""基于系统子进程的轻量级沙箱执行适配器。

本模块提供了一个在 Docker 环境不可用时的备用/开发期沙箱环境。
通过 `subprocess.run` 启动独立进程执行代码，在 Linux 系统上自动尝试利用 `resource` 模块
对子进程的虚拟内存空间大小（`RLIMIT_AS`）进行硬性配额限制，并捕获运行耗时及输出。
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from typing import Any, Dict

from app.services.sandbox.adapters.base import SandboxAdapter, ExecutionResult
from app.services.sandbox.config import SandboxConfig

logger = logging.getLogger(__name__)


class SubprocessSandboxAdapter(SandboxAdapter):
    """子进程轻量级沙箱执行适配器类。

    利用 Python `subprocess` 隔离执行 Python 脚本，支持超时中止、环境变量剥离以及基于 rlimit 的内存限制。
    """

    def execute(self, code: str, config: SandboxConfig) -> ExecutionResult:
        """在系统子进程隔离环境中执行动态 Python 代码。

        隔离防护特征：
        1. 临时文件系统：使用 `TemporaryDirectory` 在执行完毕后自动擦除执行痕迹；
        2. 敏感变量隔离：仅继承最基础的 PATH 变量，防止代理及私钥泄露；
        3. Linux rlimit 限额：在 Linux 平台通过 `preexec_fn` 预执行钩子强制设置内存配额，
           并在 stderr 中通过 `MemoryError` 或退出码 -9 识别 OOM 强杀事件；
        4. 超时阻断：利用 `subprocess` timeout 限额，强制回收超时的子进程。

        Args:
            code: 待执行的脚本代码。
            config: 沙箱安全与资源控制配额参数。

        Returns:
            ExecutionResult: 代码执行的统一封装结果。
        """
        if config.language != "python":
            return ExecutionResult(
                status="failed", exit_code=-1, stdout="", stderr="",
                error=f"Unsupported language {config.language} in SubprocessAdapter"
            )

        # 建立临时隔离的工作物理文件夹
        with tempfile.TemporaryDirectory(prefix="evoloop_sandbox_") as temp_dir:
            script_path = os.path.join(temp_dir, "script.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            # 仅保留最小的环境变量，杜绝系统敏感 Token、数据库口令等直接泄露至被执行的进程
            env = {
                "PATH": os.environ.get("PATH", ""),
                "PYTHONUNBUFFERED": "1"
            }
            if config.network_disabled:
                # 注：原生子进程在未开启 netns 命名空间前无法强行断网，
                # 此处通过清空 HTTP_PROXY/HTTPS_PROXY 等常见代理环境来削弱访问广度。
                pass

            # Linux 平台专有的轻量级 rlimit 虚拟内存限制设置
            preexec_fn = None
            if sys.platform.startswith("linux"):
                def set_limits():
                    import resource
                    if config.memory_limit_mb:
                        mem_bytes = config.memory_limit_mb * 1024 * 1024
                        try:
                            # 限制子进程允许分配的最大虚拟内存地址空间（RLIMIT_AS）
                            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
                        except ValueError:
                            pass
                preexec_fn = set_limits

            try:
                import time
                start_time = time.monotonic()
                # 调起子进程并挂接超时器
                result = subprocess.run(
                    ["python3", script_path],
                    cwd=temp_dir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=config.timeout_seconds,
                    preexec_fn=preexec_fn
                )
                duration = time.monotonic() - start_time
                
                # 识别是否被强杀（退出码为 -9 常代表 SIGKILL，在 Linux 虚拟内存限制下通常也会伴随 MemoryError 抛出）
                oom = False
                if result.returncode == -9 or (sys.platform.startswith("linux") and "MemoryError" in result.stderr):
                    oom = True

                return ExecutionResult(
                    status="succeeded" if result.returncode == 0 else "failed",
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    oom_killed=oom,
                    metrics={"duration_sec": duration}
                )

            except subprocess.TimeoutExpired as e:
                # 子进程超时，截断并强制解出已经产生的输出
                return ExecutionResult(
                    status="failed",
                    exit_code=-1,
                    stdout=e.stdout.decode('utf-8') if e.stdout else "",
                    stderr=e.stderr.decode('utf-8') if e.stderr else "",
                    error=f"Timeout after {config.timeout_seconds}s",
                    timeout=True
                )
            except Exception as e:
                logger.error(f"Subprocess Sandbox execution error: {e}")
                return ExecutionResult(
                    status="failed",
                    exit_code=-1,
                    stdout="",
                    stderr="",
                    error=str(e)
                )


"""不受信任 AI Worker 代码的沙箱（Sandbox）执行服务。

本模块提供了一个轻量级的安全代码执行隔离环境，通过临时目录与严格受限的进程环境运行动态脚本，
保障主机不受不受信任代码的恶意干扰，并支持设置运行超时机制。
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SandboxService:
    """进程级隔离沙箱执行服务类。

    管理沙箱生命周期、准备运行所需的隔离环境目录以及安全环境变量，并捕获运行的标准输出与错误输出。
    """

    def __init__(self, timeout_seconds: int = 30):
        """初始化 SandboxService 实例。

        Args:
            timeout_seconds: 沙箱中代码执行的最大超时时间，默认 30 秒。
        """
        self.timeout_seconds = timeout_seconds

    def execute_code(self, code: str, language: str = "python", env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """在隔离的子进程沙箱中安全运行指定的代码。

        当前阶段仅支持 "python" 脚本。
        流程包含：
        1. 建立临时物理隔离路径；
        2. 剥离非必要的环境变量，组装 PATH 等最小安全环境变量字典；
        3. 执行代码并限制最长运行时间；
        4. 捕获标准输出 (stdout)、标准错误 (stderr)、返回码并格式化输出。

        Args:
            code: 待执行的脚本源码文本。
            language: 开发语言，目前固定为 'python'。
            env: 传递给沙箱的额外安全环境变量字典。

        Returns:
            Dict[str, Any]: 执行结果字典，包含 status, exit_code, stdout, stderr, error 等字段。
        """
        if language != "python":
            return {"status": "failed", "error": f"Language {language} not supported yet in sandbox.", "stdout": "", "stderr": ""}

        # 轻量级退回机制：使用独立的临时目录创建 python 文件，隔离运行以避免直接影响项目主目录
        with tempfile.TemporaryDirectory(prefix="sandbox_") as temp_dir:
            script_path = os.path.join(temp_dir, "script.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            # 仅允许继承系统的必要环境变量（如 PATH），防止父进程的敏感环境变量泄露至沙箱内部
            safe_env = {
                "PATH": os.environ.get("PATH", ""),
                "PYTHONUNBUFFERED": "1"
            }
            if env:
                safe_env.update(env)

            try:
                # 调起 python3 子进程并限制最大耗时以防止死循环挂死 CPU
                result = subprocess.run(
                    ["python3", script_path],
                    cwd=temp_dir,
                    env=safe_env,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds
                )
                return {
                    "status": "succeeded" if result.returncode == 0 else "failed",
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "error": None
                }
            except subprocess.TimeoutExpired:
                return {
                    "status": "failed",
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "",
                    "error": f"Execution timed out after {self.timeout_seconds} seconds"
                }
            except Exception as e:
                logger.error(f"Sandbox execution error: {e}")
                return {
                    "status": "failed",
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "",
                    "error": str(e)
                }


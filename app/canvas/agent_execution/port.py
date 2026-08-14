"""产品内核使用的窄执行端口。"""

from __future__ import annotations

from typing import Protocol

from .contracts import (
    CancelRequest,
    CancelResult,
    ChatRunRequest,
    ChatRunResult,
    ConvergenceRunRequest,
    ConvergenceRunResult,
    JudgementRunRequest,
    JudgementRunResult,
)


class AgentExecutionPort(Protocol):
    """只表达三类 EvoCanvas 运行和取消，不暴露任意 Provider/工具调用。"""

    async def run_chat(self, request: ChatRunRequest) -> ChatRunResult:
        ...

    async def run_judgement(self, request: JudgementRunRequest) -> JudgementRunResult:
        ...

    async def run_convergence(self, request: ConvergenceRunRequest) -> ConvergenceRunResult:
        ...

    async def cancel(self, request: CancelRequest) -> CancelResult:
        ...

"""EvoCanvas Product Kernel 的最小职责编排边界。

此模块只负责把产品控制面与 ``AgentExecutionPort`` 接起来：

* Chat 终态完整且有 assistant message 时才交给消息存储；
* Judgement 是独立步骤，不在 Chat 内隐式触发；
* Convergence 只把 Pi 返回的完整 proposal 交给唯一的 governed commit port；
* Pi 运行结果本身不写 Package、Card、Ledger 或 Projection。

Canvas HTTP 已通过 ``CanvasService.run_pi_turn`` 装配到这条边界；辅助任务 API 独立存在，不得反向进入本主链。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from app.canvas.agent_execution.contracts import (
    AssistantMessage,
    ChatRunRequest,
    ChatRunResult,
    ConvergenceProposal,
    ConvergenceRunRequest,
    ConvergenceRunResult,
    JudgementRunRequest,
    JudgementRunResult,
    TraceContext,
)
from app.canvas.agent_execution.port import AgentExecutionPort


class AssistantMessageSink(Protocol):
    async def append_assistant_message(
        self,
        *,
        workspace_id: str,
        conversation_id: str,
        run_id: str,
        message: AssistantMessage,
    ) -> str:
        """持久化一条完整 assistant 主消息并返回 message_id。"""


class GovernedCommitPort(Protocol):
    async def submit_convergence_proposal(
        self,
        *,
        proposal: ConvergenceProposal,
        trace_context: TraceContext,
    ) -> Mapping[str, Any]:
        """执行 Verification → Governance → 唯一 Governed State Commit。"""


@dataclass(frozen=True)
class ChatKernelOutcome:
    result: ChatRunResult
    assistant_message_id: str | None


@dataclass(frozen=True)
class JudgementKernelOutcome:
    result: JudgementRunResult


@dataclass(frozen=True)
class ConvergenceKernelOutcome:
    result: ConvergenceRunResult
    commit_result: Mapping[str, Any] | None


class ProductKernel:
    """把产品编排步骤串成窄边界，不把业务事实交给 Pi。"""

    def __init__(
        self,
        *,
        execution: AgentExecutionPort,
        assistant_messages: AssistantMessageSink,
        governed_commit: GovernedCommitPort,
    ) -> None:
        self.execution = execution
        self.assistant_messages = assistant_messages
        self.governed_commit = governed_commit

    async def run_chat(self, request: ChatRunRequest) -> ChatKernelOutcome:
        result = await self.execution.run_chat(request)
        # 取消、超时、错误或半条流式片段均不能伪造正式 assistant 消息。
        if result.finish_reason != "completed" or result.assistant_message is None:
            return ChatKernelOutcome(result=result, assistant_message_id=None)
        message_id = await self.assistant_messages.append_assistant_message(
            workspace_id=request.workspace_id,
            conversation_id=request.conversation_id,
            run_id=request.run_id,
            message=result.assistant_message,
        )
        return ChatKernelOutcome(result=result, assistant_message_id=message_id)

    async def run_judgement(self, request: JudgementRunRequest) -> JudgementKernelOutcome:
        # Scheduler 是否推进 Convergence 由上层显式决定；Judgement 失败不能默认 trigger。
        return JudgementKernelOutcome(result=await self.execution.run_judgement(request))

    async def run_convergence(self, request: ConvergenceRunRequest) -> ConvergenceKernelOutcome:
        result = await self.execution.run_convergence(request)
        if result.finish_reason != "completed" or result.proposal is None:
            return ConvergenceKernelOutcome(result=result, commit_result=None)
        commit_result = await self.governed_commit.submit_convergence_proposal(
            proposal=result.proposal,
            trace_context=request.trace_context,
        )
        return ConvergenceKernelOutcome(result=result, commit_result=commit_result)

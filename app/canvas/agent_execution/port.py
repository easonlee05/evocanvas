"""产品内核使用的窄执行端口。"""

from __future__ import annotations

from typing import Any, Protocol

from .contracts import (
    CancelRequest,
    CancelResult,
    ChatRunRequest,
    ChatRunResult,
    ConvergenceRunRequest,
    ConvergenceRunResult,
    JudgementRunRequest,
    JudgementRunResult,
    SessionLifecycleCommand,
    SessionLifecycleResult,
    UserSubmissionRequest,
    UserSubmissionReceipt,
    WorkspaceCommitRequest,
    WorkspaceCommitResult,
    WorkspaceSessionBinding,
)


class AgentExecutionPort(Protocol):
    """只表达 EvoCanvas 运行、提交与会话治理，不暴露任意 Provider/底层实现。"""

    async def run_chat(self, request: ChatRunRequest) -> ChatRunResult:
        ...

    async def run_judgement(self, request: JudgementRunRequest) -> JudgementRunResult:
        ...

    async def run_convergence(self, request: ConvergenceRunRequest) -> ConvergenceRunResult:
        ...

    async def cancel(self, request: CancelRequest) -> CancelResult:
        ...

    async def submit_user_message(self, request: UserSubmissionRequest) -> UserSubmissionReceipt:
        ...

    async def run_workspace(self, workspace_id: str, submission_id: str, *, selected_card_ids=None, materials=None, model=None) -> dict[str, Any]:
        ...

    async def get_messages(self, workspace_id: str) -> dict[str, Any]:
        ...

    async def commit_workspace(self, request: WorkspaceCommitRequest) -> WorkspaceCommitResult:
        ...

    async def get_binding(self, workspace_id: str) -> WorkspaceSessionBinding | None:
        ...

    async def session_lifecycle(self, command: SessionLifecycleCommand) -> SessionLifecycleResult:
        ...

    async def get_projection(self, workspace_id: str) -> dict[str, Any]:
        ...

    async def get_revision(self, workspace_id: str, revision_id: str) -> dict[str, Any]:
        ...

    async def edit_workspace(self, workspace_id: str, **payload) -> dict[str, Any]:
        ...

    async def get_handoff(self, workspace_id: str) -> dict[str, Any]:
        ...

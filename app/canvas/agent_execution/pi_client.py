"""Pi Runtime 私有 HTTP 客户端。

客户端负责跨语言传输、NDJSON 合同解析和稳定错误映射；它不做产品提交、治理
或重试。断流后终态查询失败会抛出 ``PiRuntimeUnknownError``，调用方必须沿用
同一个 ``run_id`` 查询，不得重新生成运行或使用半条提案。
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from .contracts import (
    CancelRequest,
    CancelResult,
    ChatRunRequest,
    ChatRunResult,
    ConvergenceRunRequest,
    ConvergenceRunResult,
    EventEnvelope,
    JudgementRunRequest,
    JudgementRunResult,
    RunKind,
    RunSnapshot,
    SessionLifecycleCommand,
    SessionLifecycleResult,
    UserSubmissionRequest,
    UserSubmissionReceipt,
    WorkspaceCommitRequest,
    WorkspaceCommitResult,
    WorkspaceSessionBinding,
    chat_result_from_payload,
    convergence_result_from_payload,
    judgement_result_from_payload,
)
from .port import AgentExecutionPort


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    headers: Mapping[str, str]


class HttpTransport(Protocol):
    def __call__(
        self,
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse:
        ...


def _urlopen_transport(
    method: str,
    url: str,
    body: bytes | None,
    headers: Mapping[str, str],
    timeout: float,
) -> HttpResponse:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            return HttpResponse(response.status, response.read(), response_headers)
    except urllib.error.HTTPError as error:
        return HttpResponse(
            error.code,
            error.read(),
            {key.lower(): value for key, value in error.headers.items()},
        )


class PiRuntimeError(RuntimeError):
    """Pi 返回稳定错误封套后的领域边界异常。"""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        category: str = "temporary_error",
        retryable: bool = False,
        http_status: int | None = None,
        run_id: str | None = None,
        trace_id: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.category = category
        self.retryable = retryable
        self.http_status = http_status
        self.run_id = run_id
        self.trace_id = trace_id
        self.details = dict(details or {})

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any], http_status: int | None = None) -> "PiRuntimeError":
        return cls(
            str(payload.get("error_code", "runtime_internal_error")),
            str(payload.get("message", "Pi Runtime request failed")),
            category=str(payload.get("category", "temporary_error")),
            retryable=bool(payload.get("retryable", False)),
            http_status=http_status,
            run_id=payload.get("run_id"),
            trace_id=payload.get("trace_id"),
            details=payload.get("details") if isinstance(payload.get("details"), Mapping) else {},
        )


class PiRuntimeUnknownError(PiRuntimeError):
    """请求已可能在 Pi 执行，但 Python 无法确认终态。"""

    def __init__(self, message: str, *, run_id: str, details: Mapping[str, Any] | None = None) -> None:
        merged = {"retry_same_run_id": True, **dict(details or {})}
        super().__init__(
            "run_terminal_unknown",
            message,
            category="temporary_error",
            retryable=True,
            run_id=run_id,
            details=merged,
        )


EventHandler = Callable[[EventEnvelope], None]


class PiRuntimeClient(AgentExecutionPort):
    """唯一的 Python → Pi Runtime 生产客户端。"""

    _ENDPOINTS: Mapping[RunKind, str] = {
        "chat": "/v1/chat-runs",
        "judgement": "/v1/judgement-runs",
        "convergence": "/v1/convergence-runs",
    }

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8790",
        *,
        internal_secret: str | None = None,
        timeout_seconds: float = 30.0,
        transport: HttpTransport | None = None,
        event_handler: EventHandler | None = None,
        workspace_namespace: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.workspace_namespace = workspace_namespace
        self.internal_secret = internal_secret
        self.timeout_seconds = timeout_seconds
        self._transport = transport or _urlopen_transport
        self._event_handler = event_handler

    async def run_chat(self, request: ChatRunRequest) -> ChatRunResult:
        return await self._run(request, "chat", chat_result_from_payload)

    async def run_judgement(self, request: JudgementRunRequest) -> JudgementRunResult:
        return await self._run(request, "judgement", judgement_result_from_payload)

    async def run_convergence(self, request: ConvergenceRunRequest) -> ConvergenceRunResult:
        return await self._run(request, "convergence", convergence_result_from_payload)

    async def cancel(self, request: CancelRequest) -> CancelResult:
        response = await self._request(
            "POST",
            f"/v1/runs/{urllib.parse.quote(request.run_id, safe='')}/cancel",
            request.to_payload(),
            timeout_seconds=self.timeout_seconds,
        )
        payload = self._decode_json_response(response)
        if response.status >= 400:
            raise PiRuntimeError.from_payload(payload, response.status)
        return CancelResult(
            run_id=str(payload["run_id"]),
            status=str(payload["status"]),
            event_sequence=int(payload["event_sequence"]),
        )

    async def get_run(self, run_id: str, *, after_sequence: int = 0) -> RunSnapshot:
        if not run_id.strip():
            raise ValueError("run_id must be a non-empty string")
        if after_sequence < 0:
            raise ValueError("after_sequence must be >= 0")
        path = f"/v1/runs/{urllib.parse.quote(run_id, safe='')}?after_sequence={after_sequence}"
        response = await self._request("GET", path, None, timeout_seconds=self.timeout_seconds)
        payload = self._decode_json_response(response)
        if response.status >= 400:
            raise PiRuntimeError.from_payload(payload, response.status)
        try:
            events = tuple(EventEnvelope.from_payload(item) for item in payload.get("events", []))
            return RunSnapshot(
                run_id=str(payload["run_id"]),
                run_kind=payload["run_kind"],
                status=str(payload["status"]),
                event_sequence=int(payload["event_sequence"]),
                result=payload.get("result"),
                error=payload.get("error"),
                events=events,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PiRuntimeError("protocol_error", "Pi Runtime returned an invalid run summary", details={"error": str(error)}) from error

    async def _run(self, request: Any, run_kind: RunKind, result_parser: Callable[[Mapping[str, Any]], Any]) -> Any:
        events = await self._post_events(request, run_kind)
        try:
            snapshot = await self.get_run(request.run_id)
        except PiRuntimeError as error:
            raise PiRuntimeUnknownError(
                "Pi Runtime stream ended before Python could confirm the terminal state",
                run_id=request.run_id,
                details={"terminal_query_error_code": error.error_code},
            ) from error
        if snapshot.status not in {"completed", "failed", "cancelled"}:
            raise PiRuntimeUnknownError(
                f"Pi Runtime run {request.run_id} has non-terminal status {snapshot.status}",
                run_id=request.run_id,
            )
        if snapshot.event_sequence < (events[-1].sequence if events else 0):
            raise PiRuntimeError("protocol_error", "terminal summary regressed event sequence", run_id=request.run_id)
        if snapshot.error is not None:
            raise PiRuntimeError.from_payload(snapshot.error)
        if snapshot.result is None:
            raise PiRuntimeError("protocol_error", "completed Pi Runtime run has no result", run_id=request.run_id)
        try:
            result = result_parser(snapshot.result)
        except (KeyError, TypeError, ValueError) as error:
            raise PiRuntimeError("protocol_error", "Pi Runtime returned an invalid result", run_id=request.run_id, details={"error": str(error)}) from error
        if result.run_id != request.run_id:
            raise PiRuntimeError("protocol_error", "result run_id does not match request", run_id=request.run_id)
        return result

    async def _post_events(self, request: Any, run_kind: RunKind) -> tuple[EventEnvelope, ...]:
        timeout = min(self.timeout_seconds, max(0.001, request.deadline_ms / 1000))
        try:
            response = await self._request("POST", self._ENDPOINTS[run_kind], request.to_payload(), timeout_seconds=timeout)
        except (OSError, TimeoutError, urllib.error.URLError) as error:
            raise PiRuntimeUnknownError("Pi Runtime request transport failed", run_id=request.run_id, details={"error": str(error)}) from error
        if response.status >= 400:
            payload = self._decode_json_response(response)
            raise PiRuntimeError.from_payload(payload, response.status)
        events: list[EventEnvelope] = []
        previous_sequence = 0
        for line in response.body.splitlines():
            if not line.strip():
                continue
            try:
                event = EventEnvelope.from_payload(json.loads(line))
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                raise PiRuntimeError("protocol_error", "Pi Runtime returned invalid NDJSON", run_id=request.run_id, details={"error": str(error)}) from error
            if event.run_id != request.run_id or event.sequence <= previous_sequence:
                raise PiRuntimeError("protocol_error", "Pi Runtime event sequence is invalid", run_id=request.run_id)
            previous_sequence = event.sequence
            events.append(event)
            if self._event_handler is not None:
                self._event_handler(event)
        if not events:
            raise PiRuntimeUnknownError("Pi Runtime returned an empty event stream", run_id=request.run_id)
        return tuple(events)

    async def _request(self, method: str, path: str, payload: Mapping[str, Any] | None, *, timeout_seconds: float) -> HttpResponse:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8") if payload is not None else None
        headers = {
            "Accept": "application/x-ndjson, application/json",
            "Content-Type": "application/json",
        }
        if self.internal_secret:
            headers["Authorization"] = f"Bearer {self.internal_secret}"
        return await asyncio.to_thread(self._transport, method, f"{self.base_url}{path}", body, headers, timeout_seconds)

    @staticmethod
    def _decode_json_response(response: HttpResponse) -> Mapping[str, Any]:
        try:
            payload = json.loads(response.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PiRuntimeError("protocol_error", "Pi Runtime returned invalid JSON", http_status=response.status, details={"error": str(error)}) from error
        if not isinstance(payload, Mapping):
            raise PiRuntimeError("protocol_error", "Pi Runtime JSON response must be an object", http_status=response.status)
        return payload

    async def _workspace_request(self, method: str, workspace_id: str, suffix: str, payload=None):
        import hashlib
        runtime_workspace_id = workspace_id
        if self.workspace_namespace is not None:
            namespace = hashlib.sha256(self.workspace_namespace.encode()).hexdigest()
            runtime_workspace_id = f"tenant:{namespace}:{workspace_id}"
        if payload is not None:
            payload = dict(payload)
            if "workspace_id" in payload:
                payload["workspace_id"] = runtime_workspace_id
            if "tool_context" in payload:
                payload["tool_context"] = {**payload["tool_context"], "workspace_id": runtime_workspace_id}
        path = f"/v1/workspaces/{urllib.parse.quote(runtime_workspace_id, safe='')}/{suffix}"
        try:
            response = await self._request(method, path, payload, timeout_seconds=max(self.timeout_seconds, 125.0) if suffix == "turns" else self.timeout_seconds)
        except (OSError, TimeoutError, urllib.error.URLError) as error:
            raise PiRuntimeError("runtime.transport_unknown", "Pi Runtime 连接失败，结果未确认", details={"workspace_id": workspace_id, "operation": suffix}) from error
        data = self._decode_json_response(response)
        if response.status >= 400:
            raise PiRuntimeError.from_payload(data, response.status)
        if "workspace_id" in data:
            data = {**data, "workspace_id": workspace_id}
        return data

    async def get_binding(self, workspace_id: str) -> WorkspaceSessionBinding | None:
        try:
            return WorkspaceSessionBinding.from_payload(await self._workspace_request("GET", workspace_id, "binding"))
        except PiRuntimeError as error:
            if error.http_status == 404:
                return None
            raise

    async def submit_user_message(self, request: UserSubmissionRequest) -> UserSubmissionReceipt:
        return UserSubmissionReceipt.from_payload(await self._workspace_request("POST", request.workspace_id, "submissions", request.to_payload()))

    async def run_workspace(self, workspace_id: str, submission_id: str, *, selected_card_ids=None, materials=None, model=None, model_config=None) -> dict[str, Any]:
        return dict(await self._workspace_request("POST", workspace_id, "turns", {"workspace_id": workspace_id, "submission_id": submission_id, "selected_card_ids": selected_card_ids or [], "materials": materials or [], "model": model, "model_config": model_config}))

    async def commit_workspace(self, request: WorkspaceCommitRequest) -> WorkspaceCommitResult:
        return WorkspaceCommitResult.from_payload(await self._workspace_request("POST", str(request.tool_context["workspace_id"]), "commit", request.to_payload()))

    async def session_lifecycle(self, command: SessionLifecycleCommand) -> SessionLifecycleResult:
        return SessionLifecycleResult.from_payload(await self._workspace_request("POST", command.workspace_id, "lifecycle", command.to_payload()))

    async def get_projection(self, workspace_id: str) -> dict[str, Any]:
        return dict(await self._workspace_request("GET", workspace_id, "projection"))

    async def get_revision(self, workspace_id: str, revision_id: str) -> dict[str, Any]:
        return dict(await self._workspace_request("GET", workspace_id, f"revisions/{urllib.parse.quote(revision_id, safe='')}"))

    async def get_messages(self, workspace_id: str) -> dict[str, Any]:
        return dict(await self._workspace_request("GET", workspace_id, "messages"))

    async def edit_workspace(self, workspace_id: str, **payload) -> dict[str, Any]:
        return dict(await self._workspace_request("POST", workspace_id, "edits", {"workspace_id": workspace_id, **payload}))

    async def get_handoff(self, workspace_id: str) -> dict[str, Any]:
        return dict(await self._workspace_request("GET", workspace_id, "handoff"))

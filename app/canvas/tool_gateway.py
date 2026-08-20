"""EvoCanvas 内部只读 Tool Gateway 与 Run-scoped Token。

Gateway 是 Pi 与 Python 之间的权限边界。它不暴露 Repository，也不接受任何
内部写入或外部副作用工具；结构化提案捕获仍留在 Pi Runtime 内存中。
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import inspect
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Mapping
from uuid import uuid4


# 这里使用 Callable[Any] 保持 Python 3.9 的运行时导入兼容；具体处理器可以同步或异步返回。
ToolCallHandler = Callable[["ToolCallContext"], Any]


class ToolGatewayError(ValueError):
    """工具调用被拒绝或不符合内部合同。"""

    def __init__(self, code: str, message: str, *, category: str = "input_error") -> None:
        super().__init__(message)
        self.code = code
        self.category = category


@dataclass(frozen=True)
class RunScope:
    run_id: str
    run_kind: str
    workspace_id: str
    conversation_id: str
    package_id: str | None
    tenant_id: str | None
    allowed_tools: tuple[str, ...]
    expires_at: int
    max_calls: int
    max_result_bytes: int
    token_id: str
    from_message_seq: int | None = None
    through_message_seq: int | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "evocanvas.run-scoped-token.v1",
            "run_id": self.run_id,
            "run_kind": self.run_kind,
            "workspace_id": self.workspace_id,
            "conversation_id": self.conversation_id,
            "package_id": self.package_id,
            "tenant_id": self.tenant_id,
            "allowed_tools": list(self.allowed_tools),
            "expires_at": self.expires_at,
            "max_calls": self.max_calls,
            "max_result_bytes": self.max_result_bytes,
            "token_id": self.token_id,
            "message_range": (
                {"from_seq": self.from_message_seq, "through_seq": self.through_message_seq}
                if self.from_message_seq is not None and self.through_message_seq is not None
                else None
            ),
        }


class RunScopedTokenCodec:
    """使用 HMAC 签发和验证短期运行令牌。"""

    def __init__(self, secret: str | bytes) -> None:
        secret_bytes = secret.encode("utf-8") if isinstance(secret, str) else secret
        if not secret_bytes:
            raise ValueError("Run-scoped token secret must be configured")
        self._secret = secret_bytes

    def issue(
        self,
        *,
        run_id: str,
        run_kind: str,
        workspace_id: str,
        conversation_id: str,
        package_id: str | None,
        tenant_id: str | None = None,
        allowed_tools: tuple[str, ...],
        ttl_seconds: int = 60,
        max_calls: int = 8,
        max_result_bytes: int = 131072,
        message_range: tuple[int, int] | None = None,
    ) -> str:
        if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or ttl_seconds < 1:
            raise ValueError("token ttl_seconds must be an integer >= 1")
        if not isinstance(max_calls, int) or isinstance(max_calls, bool) or max_calls < 0:
            raise ValueError("token max_calls must be an integer >= 0")
        if not isinstance(max_result_bytes, int) or isinstance(max_result_bytes, bool) or max_result_bytes < 1024:
            raise ValueError("token max_result_bytes must be an integer >= 1024")
        for field_name, value in (
            ("run_id", run_id),
            ("run_kind", run_kind),
            ("workspace_id", workspace_id),
            ("conversation_id", conversation_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"token {field_name} must be a non-empty string")
        if any(not isinstance(item, str) or not item.strip() for item in allowed_tools):
            raise ValueError("token allowed_tools must contain non-empty strings")
        from_message_seq: int | None = None
        through_message_seq: int | None = None
        if message_range is not None:
            if (
                len(message_range) != 2
                or any(not isinstance(item, int) or isinstance(item, bool) for item in message_range)
                or message_range[0] < 0
                or message_range[1] < message_range[0]
            ):
                raise ValueError("token message_range must be an ordered non-negative integer pair")
            from_message_seq, through_message_seq = message_range
        scope = RunScope(
            run_id=run_id,
            run_kind=run_kind,
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            package_id=package_id,
            tenant_id=tenant_id,
            allowed_tools=tuple(dict.fromkeys(str(item) for item in allowed_tools)),
            expires_at=int(time.time()) + ttl_seconds,
            max_calls=max_calls,
            max_result_bytes=max_result_bytes,
            token_id=f"token_{uuid4().hex[:16]}",
            from_message_seq=from_message_seq,
            through_message_seq=through_message_seq,
        )
        encoded_payload = self._encode(scope.to_payload())
        signature = self._sign(encoded_payload)
        return f"v1.{encoded_payload}.{signature}"

    def verify(self, token: str) -> RunScope:
        parts = str(token).split(".")
        if len(parts) != 3 or parts[0] != "v1":
            raise ToolGatewayError("permission_denied", "invalid run-scoped token", category="permission_denied")
        payload_part, signature = parts[1], parts[2]
        expected = self._sign(payload_part)
        if not hmac.compare_digest(signature, expected):
            raise ToolGatewayError("permission_denied", "invalid run-scoped token signature", category="permission_denied")
        try:
            payload = json.loads(self._decode(payload_part))
            if not isinstance(payload, Mapping):
                raise ValueError("token payload must be an object")
            if payload.get("schema_version") != "evocanvas.run-scoped-token.v1":
                raise ValueError("token schema version is invalid")
            allowed_tools = payload["allowed_tools"]
            if not isinstance(allowed_tools, list):
                raise ValueError("token allowed_tools must be an array")
            scope = RunScope(
                run_id=str(payload["run_id"]),
                run_kind=str(payload["run_kind"]),
                workspace_id=str(payload["workspace_id"]),
                conversation_id=str(payload["conversation_id"]),
                package_id=str(payload["package_id"]) if payload.get("package_id") is not None else None,
                tenant_id=str(payload["tenant_id"]) if payload.get("tenant_id") is not None else None,
                allowed_tools=tuple(str(item) for item in allowed_tools),
                expires_at=int(payload["expires_at"]),
                max_calls=int(payload["max_calls"]),
                max_result_bytes=int(payload["max_result_bytes"]),
                token_id=str(payload["token_id"]),
                from_message_seq=(
                    int(payload["message_range"]["from_seq"])
                    if isinstance(payload.get("message_range"), Mapping)
                    and payload["message_range"].get("from_seq") is not None
                    else None
                ),
                through_message_seq=(
                    int(payload["message_range"]["through_seq"])
                    if isinstance(payload.get("message_range"), Mapping)
                    and payload["message_range"].get("through_seq") is not None
                    else None
                ),
            )
            if any(not item.strip() for item in scope.allowed_tools):
                raise ValueError("token allowed_tools contains an empty name")
            if scope.max_calls < 0 or scope.max_result_bytes < 1024:
                raise ValueError("token limits are invalid")
            if (scope.from_message_seq is None) != (scope.through_message_seq is None):
                raise ValueError("token message_range is incomplete")
            if (
                scope.from_message_seq is not None
                and scope.through_message_seq is not None
                and scope.through_message_seq < scope.from_message_seq
            ):
                raise ValueError("token message_range is reversed")
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError) as error:
            raise ToolGatewayError("permission_denied", "malformed run-scoped token", category="permission_denied") from error
        if scope.expires_at <= int(time.time()):
            raise ToolGatewayError("permission_denied", "run-scoped token expired", category="permission_denied")
        if not scope.run_id or not scope.workspace_id or not scope.conversation_id:
            raise ToolGatewayError("permission_denied", "run-scoped token scope is incomplete", category="permission_denied")
        return scope

    def fingerprint(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _sign(self, encoded_payload: str) -> str:
        return base64.urlsafe_b64encode(
            hmac.new(self._secret, encoded_payload.encode("ascii"), hashlib.sha256).digest()
        ).decode("ascii").rstrip("=")

    @staticmethod
    def _encode(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _decode(value: str) -> str:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(f"{value}{padding}").decode("utf-8")


@dataclass(frozen=True)
class ToolCallContext:
    scope: RunScope
    tool_call_id: str
    tool_name: str
    tool_version: str
    arguments: Mapping[str, Any]
    attempt: int
    message_range: Mapping[str, int]
    trace_context: Mapping[str, Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    version: str
    allowed_run_kinds: tuple[str, ...]
    side_effect: str
    timeout_seconds: float
    handler: ToolCallHandler


@dataclass(frozen=True)
class ToolCallResult:
    tool_call_id: str
    status: str
    summary: str
    data: Any = None
    data_ref: str | None = None
    source_refs: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    error: Mapping[str, Any] | None = None
    completed_at: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "pi-runtime.tool-result.v1",
            "tool_call_id": self.tool_call_id,
            "status": self.status,
            "summary": self.summary[:20000],
            "data": self.data,
            "data_ref": self.data_ref,
            "source_refs": list(self.source_refs),
            "artifacts": list(self.artifacts),
            "error": dict(self.error) if self.error is not None else None,
            "completed_at": self.completed_at or _now_iso(),
        }


class ToolGateway:
    """只读工具注册与运行级权限执行器。"""

    def __init__(self, token_codec: RunScopedTokenCodec) -> None:
        self.token_codec = token_codec
        self._specs: dict[str, ToolSpec] = {}
        self._calls: dict[str, int] = {}
        self.audit_events: list[dict[str, Any]] = []

    def register(
        self,
        *,
        name: str,
        version: str,
        allowed_run_kinds: tuple[str, ...],
        side_effect: str,
        timeout_seconds: float,
        handler: ToolCallHandler,
    ) -> None:
        if side_effect not in {"none", "read"}:
            raise ValueError("Pi Tool Gateway only accepts none/read handlers")
        if name == "submit_convergence_proposal":
            raise ValueError("proposal capture must remain inside Pi Runtime")
        if timeout_seconds <= 0:
            raise ValueError("tool timeout must be positive")
        self._specs[name] = ToolSpec(
            name=name,
            version=version,
            allowed_run_kinds=tuple(allowed_run_kinds),
            side_effect=side_effect,
            timeout_seconds=timeout_seconds,
            handler=handler,
        )

    def issue_run_token(
        self,
        *,
        run_id: str,
        run_kind: str,
        workspace_id: str,
        conversation_id: str,
        package_id: str | None,
        tenant_id: str | None = None,
        allowed_tools: tuple[str, ...],
        ttl_seconds: int = 60,
        max_calls: int = 8,
        max_result_bytes: int = 131072,
        message_range: tuple[int, int] | None = None,
    ) -> str:
        unknown = [tool for tool in allowed_tools if tool not in self._specs]
        if unknown:
            raise ToolGatewayError("invalid_request", f"unknown tools cannot enter a token: {unknown}")
        return self.token_codec.issue(
            run_id=run_id,
            run_kind=run_kind,
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            package_id=package_id,
            tenant_id=tenant_id,
            allowed_tools=allowed_tools,
            ttl_seconds=ttl_seconds,
            max_calls=max_calls,
            max_result_bytes=max_result_bytes,
            message_range=message_range,
        )

    async def invoke(self, token: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        scope = self.token_codec.verify(token)
        request = self._validate_request(payload, scope)
        token_key = self.token_codec.fingerprint(token)
        call_count = self._calls.get(token_key, 0)
        if call_count >= scope.max_calls:
            return self._denied(request["tool_call_id"], "tool call budget exhausted", "permission_denied")
        tool_name = request["tool_name"]
        if tool_name not in scope.allowed_tools:
            return self._denied(request["tool_call_id"], f"tool {tool_name} is not allowed for this run", "permission_denied")
        spec = self._specs.get(tool_name)
        if spec is None:
            return self._denied(request["tool_call_id"], f"tool {tool_name} is not registered", "tool_unavailable")
        if request["tool_version"] != spec.version:
            self._audit("tool.call.denied", request, status="denied", error_code="invalid_request")
            return self._failed(
                request["tool_call_id"],
                "invalid_request",
                f"tool {tool_name} version {request['tool_version']} is not supported",
                "denied",
                category="input_error",
            )
        if scope.run_kind not in spec.allowed_run_kinds or spec.side_effect not in {"none", "read"}:
            return self._denied(request["tool_call_id"], f"tool {tool_name} is not allowed for {scope.run_kind}", "permission_denied")
        self._calls[token_key] = call_count + 1
        self._audit("tool.call.started", request, status="running")
        context = ToolCallContext(
            scope=scope,
            tool_call_id=request["tool_call_id"],
            tool_name=tool_name,
            tool_version=request["tool_version"],
            arguments=request["arguments"],
            attempt=request["attempt"],
            message_range=request["message_range"],
            trace_context=request["trace_context"],
        )
        try:
            result = spec.handler(context)
            if inspect.isawaitable(result):
                import asyncio

                result = await asyncio.wait_for(result, timeout=spec.timeout_seconds)
            normalized = self._normalize_handler_result(request["tool_call_id"], result)
            self._assert_result_size(normalized, scope)
            if normalized.status == "succeeded":
                self._audit("tool.call.succeeded", request, status="succeeded", source_refs=normalized.source_refs)
            else:
                self._audit("tool.call.failed", request, status=normalized.status, source_refs=normalized.source_refs)
            return normalized.to_payload()
        except TimeoutError:
            self._audit("tool.call.failed", request, status="timed_out", error_code="tool_timeout")
            return self._failed(request["tool_call_id"], "tool_timeout", "tool execution timed out", "timed_out")
        except ToolGatewayError as error:
            self._audit("tool.call.failed", request, status="failed", error_code=error.code)
            return self._failed(
                request["tool_call_id"],
                error.code,
                str(error),
                "failed",
                category=error.category,
            )
        except Exception as error:
            self._audit("tool.call.failed", request, status="failed", error_code="tool_failed")
            return self._failed(request["tool_call_id"], "tool_failed", str(error), "failed")

    def _validate_request(self, payload: Mapping[str, Any], scope: RunScope) -> dict[str, Any]:
        required = ("schema_version", "tool_call_id", "tool_name", "tool_version", "run_id", "run_kind", "workspace_id", "conversation_id", "arguments", "attempt", "trace_context")
        missing = [field for field in required if field not in payload]
        if missing:
            raise ToolGatewayError("invalid_request", f"tool call missing fields: {', '.join(missing)}")
        if payload["schema_version"] != "pi-runtime.tool-call.v1":
            raise ToolGatewayError("schema_invalid", "tool call schema version is invalid")
        for field_name in ("tool_call_id", "tool_name", "tool_version", "run_id", "run_kind", "workspace_id", "conversation_id"):
            if not isinstance(payload[field_name], str) or not payload[field_name].strip():
                raise ToolGatewayError("invalid_request", f"tool call {field_name} must be a non-empty string")
        if str(payload["run_id"]) != scope.run_id or str(payload["run_kind"]) != scope.run_kind:
            raise ToolGatewayError("permission_denied", "tool call run scope does not match token", category="permission_denied")
        if str(payload["workspace_id"]) != scope.workspace_id or str(payload["conversation_id"]) != scope.conversation_id:
            raise ToolGatewayError("permission_denied", "tool call workspace scope does not match token", category="permission_denied")
        tenant_id = payload.get("tenant_id")
        if tenant_id is not None and (not isinstance(tenant_id, str) or not tenant_id.strip()):
            raise ToolGatewayError("invalid_request", "tool call tenant_id must be a non-empty string")
        if tenant_id != scope.tenant_id:
            raise ToolGatewayError("permission_denied", "tool call tenant scope does not match token", category="permission_denied")
        package_id = payload.get("package_id")
        if package_id != scope.package_id:
            raise ToolGatewayError("permission_denied", "tool call package scope does not match token", category="permission_denied")
        if not isinstance(payload["arguments"], Mapping):
            raise ToolGatewayError("invalid_request", "tool call arguments must be an object")
        if not isinstance(payload["trace_context"], Mapping):
            raise ToolGatewayError("invalid_request", "tool call trace_context must be an object")
        if not isinstance(payload["attempt"], int) or isinstance(payload["attempt"], bool) or payload["attempt"] < 1:
            raise ToolGatewayError("invalid_request", "tool call attempt must be an integer >= 1")
        message_range = payload.get("message_range") or {
            "from_seq": 0,
            "through_seq": 0,
        }
        if not isinstance(message_range, Mapping):
            raise ToolGatewayError("invalid_request", "tool call message_range must be an object")
        try:
            from_seq = int(message_range.get("from_seq", 0))
            through_seq = int(message_range.get("through_seq", 0))
        except (TypeError, ValueError) as error:
            raise ToolGatewayError("invalid_request", "tool call message_range values must be integers") from error
        if from_seq < 0 or through_seq < from_seq:
            raise ToolGatewayError("invalid_request", "tool call message_range must be a non-negative ordered range")
        if (
            scope.from_message_seq is not None
            and scope.through_message_seq is not None
            and (from_seq != scope.from_message_seq or through_seq != scope.through_message_seq)
        ):
            raise ToolGatewayError(
                "permission_denied",
                "tool call message_range does not match the run scope",
                category="permission_denied",
            )
        return {
            **dict(payload),
            "tool_call_id": str(payload["tool_call_id"]),
            "tool_name": str(payload["tool_name"]),
            "tool_version": str(payload["tool_version"]),
            "run_id": str(payload["run_id"]),
            "run_kind": str(payload["run_kind"]),
            "workspace_id": str(payload["workspace_id"]),
            "conversation_id": str(payload["conversation_id"]),
            "message_range": {
                "from_seq": from_seq,
                "through_seq": through_seq,
            },
        }

    @staticmethod
    def _normalize_handler_result(tool_call_id: str, result: Any) -> ToolCallResult:
        if isinstance(result, ToolCallResult):
            return result
        if not isinstance(result, Mapping):
            return ToolCallResult(tool_call_id, "succeeded", str(result), data=result)
        return ToolCallResult(
            tool_call_id=tool_call_id,
            status=str(result.get("status", "succeeded")),
            summary=str(result.get("summary", "tool completed")),
            data=result.get("data"),
            data_ref=result.get("data_ref"),
            source_refs=tuple(str(item) for item in result.get("source_refs", [])),
            artifacts=tuple(str(item) for item in result.get("artifacts", [])),
            error=result.get("error"),
            completed_at=str(result.get("completed_at", "")),
        )

    @staticmethod
    def _assert_result_size(result: ToolCallResult, scope: RunScope) -> None:
        try:
            encoded = json.dumps(result.to_payload(), ensure_ascii=False, sort_keys=True).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise ToolGatewayError("invalid_request", "tool result is not JSON serializable") from error
        if len(encoded) > scope.max_result_bytes:
            raise ToolGatewayError("invalid_request", "tool result exceeds the gateway hard limit")

    def _denied(self, tool_call_id: str, message: str, code: str) -> dict[str, Any]:
        result = self._failed(tool_call_id, code, message, "denied")
        self._audit("tool.call.denied", {"tool_call_id": tool_call_id, "tool_name": "unknown"}, status="denied")
        return result

    @staticmethod
    def _failed(
        tool_call_id: str,
        code: str,
        message: str,
        status: str,
        *,
        category: str | None = None,
        retryable: bool | None = None,
    ) -> dict[str, Any]:
        resolved_category = category or ("permission_denied" if status == "denied" else "temporary_error")
        return ToolCallResult(
            tool_call_id=tool_call_id,
            status=status,
            summary=message,
            error={
                "schema_version": "pi-runtime.error.v1",
                "error_code": code,
                "category": resolved_category,
                "message": message,
                "retryable": status == "timed_out" if retryable is None else retryable,
                "details": {},
            },
        ).to_payload()

    def _audit(self, event_type: str, request: Mapping[str, Any], **extra: Any) -> None:
        self.audit_events.append(
            {
                "type": event_type,
                "tool_call_id": request.get("tool_call_id"),
                "tool_name": request.get("tool_name"),
                "run_id": request.get("run_id"),
                "workspace_id": request.get("workspace_id"),
                **extra,
                "created_at": _now_iso(),
            }
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

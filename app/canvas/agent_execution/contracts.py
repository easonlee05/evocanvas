"""Pi Runtime v1 的 Python 侧强类型合同。

这里的类型只描述 EvoCanvas 产品需要的字段；不暴露 Pi 内部消息类、Provider
对象或供应商原生请求。序列化结果与
``docs/technical-specs/schemas/pi-runtime/v1-contracts.json`` 对齐。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, TypeVar

RunKind = Literal["chat", "judgement", "convergence"]
FinishReason = Literal["completed", "length", "tool_failed", "cancelled", "error"]


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_seq(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{field_name} must be an integer >= 1")
    return value


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    request_id: str
    parent_run_id: str | None = None
    operation_id: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.trace_id, "trace_id")
        _require_text(self.request_id, "request_id")

    def to_payload(self) -> dict[str, Any]:
        payload = dict(self.extra)
        payload.update({"trace_id": self.trace_id, "request_id": self.request_id})
        if self.parent_run_id is not None:
            payload["parent_run_id"] = self.parent_run_id
        if self.operation_id is not None:
            payload["operation_id"] = self.operation_id
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "TraceContext":
        known = {"trace_id", "request_id", "parent_run_id", "operation_id"}
        return cls(
            trace_id=str(payload["trace_id"]),
            request_id=str(payload["request_id"]),
            parent_run_id=payload.get("parent_run_id"),
            operation_id=payload.get("operation_id"),
            extra={key: value for key, value in payload.items() if key not in known},
        )


@dataclass(frozen=True)
class PackageRef:
    package_id: str
    package_version: int
    state_version: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "package_version": self.package_version,
            "state_version": self.state_version,
        }


@dataclass(frozen=True)
class StructuredPackageInputRef:
    id: str
    content_hash: str

    def to_payload(self) -> dict[str, str]:
        return {"id": self.id, "content_hash": self.content_hash}


@dataclass(frozen=True)
class MessageScope:
    from_seq: int
    through_seq: int
    history_compaction_ref: str | None = None
    raw_user_message_ref: str | None = None

    def __post_init__(self) -> None:
        _require_seq(self.from_seq, "message_scope.from_seq")
        _require_seq(self.through_seq, "message_scope.through_seq")
        if self.through_seq < self.from_seq:
            raise ValueError("message_scope.through_seq must be >= from_seq")

    def to_payload(self) -> dict[str, Any]:
        return {
            "from_seq": self.from_seq,
            "through_seq": self.through_seq,
            "history_compaction_ref": self.history_compaction_ref,
            "raw_user_message_ref": self.raw_user_message_ref,
        }


@dataclass(frozen=True)
class ContextManifest:
    context_manifest_id: str
    request_kind: RunKind
    package_ref: PackageRef
    structured_package_input_ref: StructuredPackageInputRef
    message_scope: MessageScope
    instruction_and_schema_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    included_sections: tuple[str, ...]
    omissions: tuple[Mapping[str, Any], ...]
    assembly_policy_version: str
    budget_ref: str
    degradation_flags: tuple[str, ...]
    content_hashes: Mapping[str, str]
    transport_ref: Mapping[str, Any]

    def __post_init__(self) -> None:
        _require_text(self.context_manifest_id, "context_manifest_id")
        _require_text(self.assembly_policy_version, "assembly_policy_version")
        _require_text(self.budget_ref, "budget_ref")

    def to_payload(self) -> dict[str, Any]:
        return {
            "context_manifest_id": self.context_manifest_id,
            "request_kind": self.request_kind,
            "package_ref": self.package_ref.to_payload(),
            "structured_package_input_ref": self.structured_package_input_ref.to_payload(),
            "message_scope": self.message_scope.to_payload(),
            "instruction_and_schema_refs": list(self.instruction_and_schema_refs),
            "source_refs": list(self.source_refs),
            "included_sections": list(self.included_sections),
            "omissions": [dict(item) for item in self.omissions],
            "assembly_policy_version": self.assembly_policy_version,
            "budget_ref": self.budget_ref,
            "degradation_flags": list(self.degradation_flags),
            "content_hashes": dict(self.content_hashes),
            "transport_ref": dict(self.transport_ref),
        }


@dataclass(frozen=True)
class ModelPolicy:
    quality_tier: str
    latency_tier: str
    structured_output_required: bool
    tool_calling_required: bool
    max_cost: float | None = None
    provider_allowlist: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "quality_tier": self.quality_tier,
            "latency_tier": self.latency_tier,
            "structured_output_required": self.structured_output_required,
            "tool_calling_required": self.tool_calling_required,
            "max_cost": self.max_cost,
            "provider_allowlist": list(self.provider_allowlist),
        }


@dataclass(frozen=True)
class RuntimeInputSnapshot:
    """本次模型调用的临时输入快照；不写入运行记录或产品事实。"""

    structured_package_input: Mapping[str, Any]
    conversation_messages: tuple[Mapping[str, Any], ...] = ()
    raw_user_message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.structured_package_input, Mapping):
            raise ValueError("runtime_inputs.structured_package_input must be an object")
        if any(not isinstance(item, Mapping) for item in self.conversation_messages):
            raise ValueError("runtime_inputs.conversation_messages must contain objects")
        if self.raw_user_message is not None and not isinstance(self.raw_user_message, str):
            raise ValueError("runtime_inputs.raw_user_message must be a string or null")

    def to_payload(self) -> dict[str, Any]:
        return {
            "structured_package_input": dict(self.structured_package_input),
            "conversation_messages": [dict(item) for item in self.conversation_messages],
            "raw_user_message": self.raw_user_message,
        }


@dataclass(frozen=True)
class ToolProfile:
    run_kind: RunKind
    allowed_tools: tuple[str, ...]
    max_calls: int
    max_result_bytes: int
    gateway_url: str | None = None
    run_scoped_token: str | None = None
    tenant_id: str | None = None

    def __post_init__(self) -> None:
        if self.run_kind not in {"chat", "judgement", "convergence"}:
            raise ValueError("tool_profile.run_kind is invalid")
        if any(not isinstance(tool, str) or not tool.strip() for tool in self.allowed_tools):
            raise ValueError("tool_profile.allowed_tools must contain non-empty strings")
        if not isinstance(self.max_calls, int) or isinstance(self.max_calls, bool) or self.max_calls < 0:
            raise ValueError("tool_profile.max_calls must be an integer >= 0")
        if not isinstance(self.max_result_bytes, int) or isinstance(self.max_result_bytes, bool) or self.max_result_bytes < 1024:
            raise ValueError("tool_profile.max_result_bytes must be an integer >= 1024")
        if "submit_convergence_proposal" in self.allowed_tools and self.run_kind != "convergence":
            raise ValueError("submit_convergence_proposal is only valid for convergence runs")
        if (self.gateway_url is None) != (self.run_scoped_token is None):
            raise ValueError("tool_profile.gateway_url and run_scoped_token must be provided together")

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_kind": self.run_kind,
            "allowed_tools": list(self.allowed_tools),
            "max_calls": self.max_calls,
            "max_result_bytes": self.max_result_bytes,
        }
        if self.gateway_url:
            payload["gateway_url"] = self.gateway_url
        if self.run_scoped_token:
            payload["run_scoped_token"] = self.run_scoped_token
        if self.tenant_id:
            payload["tenant_id"] = self.tenant_id
        return payload


@dataclass(frozen=True)
class BaseRunRequest:
    run_id: str
    run_kind: RunKind
    workspace_id: str
    conversation_id: str
    from_message_seq: int
    through_message_seq: int
    context_manifest: ContextManifest
    instructions_ref: str
    model_policy: ModelPolicy
    tool_profile: ToolProfile
    deadline_ms: int
    trace_context: TraceContext
    idempotency_key: str
    schema_version: str = "pi-runtime.request.v1"
    runtime_inputs: RuntimeInputSnapshot | None = None

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        _require_text(self.workspace_id, "workspace_id")
        _require_text(self.conversation_id, "conversation_id")
        _require_text(self.instructions_ref, "instructions_ref")
        _require_text(self.idempotency_key, "idempotency_key")
        _require_seq(self.from_message_seq, "from_message_seq")
        _require_seq(self.through_message_seq, "through_message_seq")
        if self.through_message_seq < self.from_message_seq:
            raise ValueError("through_message_seq must be >= from_message_seq")
        if not isinstance(self.deadline_ms, int) or self.deadline_ms < 1:
            raise ValueError("deadline_ms must be an integer >= 1")
        if self.context_manifest.request_kind != self.run_kind:
            raise ValueError("context_manifest.request_kind must match run_kind")
        if self.tool_profile.run_kind != self.run_kind:
            raise ValueError("tool_profile.run_kind must match run_kind")

    def _base_payload(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "run_kind": self.run_kind,
            "workspace_id": self.workspace_id,
            "conversation_id": self.conversation_id,
            "from_message_seq": self.from_message_seq,
            "through_message_seq": self.through_message_seq,
            "context_manifest": self.context_manifest.to_payload(),
            "instructions_ref": self.instructions_ref,
            "model_policy": self.model_policy.to_payload(),
            "tool_profile": self.tool_profile.to_payload(),
            "deadline_ms": self.deadline_ms,
            "trace_context": self.trace_context.to_payload(),
            "idempotency_key": self.idempotency_key,
        }
        if self.runtime_inputs is not None:
            payload["runtime_inputs"] = self.runtime_inputs.to_payload()
        return payload

    def to_payload(self) -> dict[str, Any]:
        return self._base_payload()


@dataclass(frozen=True)
class ChatRunRequest(BaseRunRequest):
    package_id: str = ""
    raw_user_message_ref: str = ""
    assistant_reply_schema_ref: str = ""
    conversation_order_key: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        for field_name in ("package_id", "raw_user_message_ref", "assistant_reply_schema_ref", "conversation_order_key"):
            _require_text(getattr(self, field_name), field_name)

    def to_payload(self) -> dict[str, Any]:
        payload = self._base_payload()
        payload.update(
            {
                "package_id": self.package_id,
                "raw_user_message_ref": self.raw_user_message_ref,
                "assistant_reply_schema_ref": self.assistant_reply_schema_ref,
                "conversation_order_key": self.conversation_order_key,
            }
        )
        return payload


@dataclass(frozen=True)
class JudgementRunRequest(BaseRunRequest):
    chat_turn_id: str = ""
    base_state_version: int = 0
    base_package_version: int = 0
    signal_summary_ref: str = ""
    package_id: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text(self.chat_turn_id, "chat_turn_id")
        _require_text(self.signal_summary_ref, "signal_summary_ref")
        if self.base_state_version < 0 or self.base_package_version < 0:
            raise ValueError("base versions must be >= 0")

    def to_payload(self) -> dict[str, Any]:
        payload = self._base_payload()
        payload.update(
            {
                "chat_turn_id": self.chat_turn_id,
                "base_state_version": self.base_state_version,
                "base_package_version": self.base_package_version,
                "signal_summary_ref": self.signal_summary_ref,
            }
        )
        if self.package_id is not None:
            payload["package_id"] = self.package_id
        return payload


@dataclass(frozen=True)
class ConvergenceRunRequest(BaseRunRequest):
    package_id: str = ""
    convergence_run_id: str = ""
    base_state_version: int = 0
    base_package_version: int = 0
    proposal_schema_ref: str = ""
    proposal_capture_tool_ref: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        for field_name in ("package_id", "convergence_run_id", "proposal_schema_ref", "proposal_capture_tool_ref"):
            _require_text(getattr(self, field_name), field_name)
        if self.base_state_version < 0 or self.base_package_version < 0:
            raise ValueError("base versions must be >= 0")

    def to_payload(self) -> dict[str, Any]:
        payload = self._base_payload()
        payload.update(
            {
                "package_id": self.package_id,
                "convergence_run_id": self.convergence_run_id,
                "base_state_version": self.base_state_version,
                "base_package_version": self.base_package_version,
                "proposal_schema_ref": self.proposal_schema_ref,
                "proposal_capture_tool_ref": self.proposal_capture_tool_ref,
            }
        )
        return payload


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    provider_usage_ref: str | None


@dataclass(frozen=True)
class ModelIdentity:
    provider_id: str
    model_id: str
    adapter_version: str
    protocol_version: str


@dataclass(frozen=True)
class AssistantMessage:
    content_blocks: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class ChatRunResult:
    run_id: str
    assistant_message: AssistantMessage | None
    finish_reason: FinishReason
    events_summary: Mapping[str, Any]
    usage: Usage
    model_identity: ModelIdentity
    context_manifest_id: str


@dataclass(frozen=True)
class JudgementRunResult:
    run_id: str
    decision: Literal["skip", "defer", "trigger"]
    reason_codes: tuple[str, ...]
    through_message_seq: int
    confidence: float | None
    usage: Usage
    model_identity: ModelIdentity
    context_manifest_id: str


@dataclass(frozen=True)
class ProposalOperation:
    operation_id: str
    operation_type: str
    target_object_id: str | None
    temporary_target_ref: str | None
    before_ref: str | None
    payload: Mapping[str, Any]
    source_refs: tuple[str, ...]
    confirmation_refs: tuple[str, ...]
    unresolved_refs: tuple[str, ...]
    risk_level: Literal["low", "medium", "high"]
    reason_codes: tuple[str, ...]
    atomic_group_id: str | None


@dataclass(frozen=True)
class ConvergenceProposal:
    proposal_schema_version: str
    proposal_id: str
    run_id: str
    package_id: str
    from_message_seq: int
    through_message_seq: int
    base_state_version: int
    base_package_version: int
    operations: tuple[ProposalOperation, ...]


@dataclass(frozen=True)
class ConvergenceRunResult:
    run_id: str
    proposal: ConvergenceProposal | None
    finish_reason: Literal["completed", "not_ready", "tool_failed", "cancelled", "error"]
    tool_trace: tuple[str, ...]
    usage: Usage
    model_identity: ModelIdentity
    context_manifest_id: str


@dataclass(frozen=True)
class EventEnvelope:
    schema_version: str
    event_id: str
    run_id: str
    sequence: int
    timestamp: str
    type: str
    trace_context: TraceContext
    payload: Mapping[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "EventEnvelope":
        required = ("schema_version", "event_id", "run_id", "sequence", "timestamp", "type", "trace_context", "payload")
        missing = [field_name for field_name in required if field_name not in payload]
        if missing:
            raise ValueError(f"event missing required fields: {', '.join(missing)}")
        if not isinstance(payload["sequence"], int) or payload["sequence"] < 1:
            raise ValueError("event sequence must be an integer >= 1")
        if not isinstance(payload["payload"], Mapping):
            raise ValueError("event payload must be an object")
        return cls(
            schema_version=str(payload["schema_version"]),
            event_id=str(payload["event_id"]),
            run_id=str(payload["run_id"]),
            sequence=payload["sequence"],
            timestamp=str(payload["timestamp"]),
            type=str(payload["type"]),
            trace_context=TraceContext.from_payload(payload["trace_context"]),
            payload=payload["payload"],
        )


@dataclass(frozen=True)
class CancelRequest:
    run_id: str
    reason_code: str
    requested_by: str
    trace_context: TraceContext
    schema_version: str = "pi-runtime.cancel.v1"

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "reason_code": self.reason_code,
            "requested_by": self.requested_by,
            "trace_context": self.trace_context.to_payload(),
        }


@dataclass(frozen=True)
class CancelResult:
    run_id: str
    status: str
    event_sequence: int


@dataclass(frozen=True)
class RunSnapshot:
    run_id: str
    run_kind: RunKind
    status: str
    event_sequence: int
    result: Mapping[str, Any] | None
    error: Mapping[str, Any] | None
    events: tuple[EventEnvelope, ...]


_ResultT = TypeVar("_ResultT")


def usage_from_payload(payload: Mapping[str, Any]) -> Usage:
    return Usage(
        input_tokens=payload.get("input_tokens"),
        output_tokens=payload.get("output_tokens"),
        total_tokens=payload.get("total_tokens"),
        provider_usage_ref=payload.get("provider_usage_ref"),
    )


def model_identity_from_payload(payload: Mapping[str, Any]) -> ModelIdentity:
    return ModelIdentity(
        provider_id=str(payload["provider_id"]),
        model_id=str(payload["model_id"]),
        adapter_version=str(payload["adapter_version"]),
        protocol_version=str(payload["protocol_version"]),
    )


def assistant_message_from_payload(payload: Mapping[str, Any] | None) -> AssistantMessage | None:
    if payload is None:
        return None
    blocks = payload.get("content_blocks")
    if not isinstance(blocks, list):
        raise ValueError("assistant_message.content_blocks must be an array")
    return AssistantMessage(content_blocks=tuple(item for item in blocks if isinstance(item, Mapping)))


def chat_result_from_payload(payload: Mapping[str, Any]) -> ChatRunResult:
    return ChatRunResult(
        run_id=str(payload["run_id"]),
        assistant_message=assistant_message_from_payload(payload.get("assistant_message")),
        finish_reason=payload["finish_reason"],
        events_summary=payload.get("events_summary", {}),
        usage=usage_from_payload(payload["usage"]),
        model_identity=model_identity_from_payload(payload["model_identity"]),
        context_manifest_id=str(payload["context_manifest_id"]),
    )


def judgement_result_from_payload(payload: Mapping[str, Any]) -> JudgementRunResult:
    return JudgementRunResult(
        run_id=str(payload["run_id"]),
        decision=payload["decision"],
        reason_codes=tuple(str(item) for item in payload.get("reason_codes", [])),
        through_message_seq=int(payload["through_message_seq"]),
        confidence=payload.get("confidence"),
        usage=usage_from_payload(payload["usage"]),
        model_identity=model_identity_from_payload(payload["model_identity"]),
        context_manifest_id=str(payload["context_manifest_id"]),
    )


def proposal_from_payload(payload: Mapping[str, Any]) -> ConvergenceProposal:
    operations = []
    for operation in payload.get("operations", []):
        operations.append(
            ProposalOperation(
                operation_id=str(operation["operation_id"]),
                operation_type=str(operation["operation_type"]),
                target_object_id=operation.get("target_object_id"),
                temporary_target_ref=operation.get("temporary_target_ref"),
                before_ref=operation.get("before_ref"),
                payload=operation.get("payload", {}),
                source_refs=tuple(str(item) for item in operation.get("source_refs", [])),
                confirmation_refs=tuple(str(item) for item in operation.get("confirmation_refs", [])),
                unresolved_refs=tuple(str(item) for item in operation.get("unresolved_refs", [])),
                risk_level=operation["risk_level"],
                reason_codes=tuple(str(item) for item in operation.get("reason_codes", [])),
                atomic_group_id=operation.get("atomic_group_id"),
            )
        )
    return ConvergenceProposal(
        proposal_schema_version=str(payload["proposal_schema_version"]),
        proposal_id=str(payload["proposal_id"]),
        run_id=str(payload["run_id"]),
        package_id=str(payload["package_id"]),
        from_message_seq=int(payload["from_message_seq"]),
        through_message_seq=int(payload["through_message_seq"]),
        base_state_version=int(payload["base_state_version"]),
        base_package_version=int(payload["base_package_version"]),
        operations=tuple(operations),
    )


def convergence_result_from_payload(payload: Mapping[str, Any]) -> ConvergenceRunResult:
    proposal_payload = payload.get("proposal")
    return ConvergenceRunResult(
        run_id=str(payload["run_id"]),
        proposal=proposal_from_payload(proposal_payload) if isinstance(proposal_payload, Mapping) else None,
        finish_reason=payload["finish_reason"],
        tool_trace=tuple(str(item) for item in payload.get("tool_trace", [])),
        usage=usage_from_payload(payload["usage"]),
        model_identity=model_identity_from_payload(payload["model_identity"]),
        context_manifest_id=str(payload["context_manifest_id"]),
    )

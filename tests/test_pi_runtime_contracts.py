"""Pi Runtime v1 合同的跨语言 fixture 测试。

阶段 0 尚未有 Pi Runtime 生产实现，因此这里直接对机器可读合同做验证。
测试故意只依赖 Python 标准库：开发环境若装有 ``jsonschema``，可以替换为
完整实现；默认的轻量校验器覆盖本合同实际使用到的 JSON Schema 关键字，保证
仓库的最小测试环境也能执行这些合同测试。
"""

from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs/technical-specs/schemas/pi-runtime/v1-contracts.json"
)
RUNTIME_INPUTS_FIXTURE_PATH = SCHEMA_PATH.parent / "fixtures/runtime-inputs-chat-request.json"


class _SchemaValidationError(AssertionError):
    """轻量 JSON Schema 校验器的可读错误。"""


class _ContractSchemaValidator:
    """验证 Pi v1 合同使用到的 JSON Schema 2020-12 子集。

    Schema 明确允许未知字段，以便前向兼容；因此校验器只检查类型、必填字段、
    常量、枚举、范围和格式，不把未知字段当作错误。
    """

    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document
        self.defs = document["$defs"]

    def validate(self, value: Any, definition: str) -> None:
        self._validate(value, {"$ref": f"#/$defs/{definition}"}, "$" )

    def _validate(self, value: Any, schema: dict[str, Any], path: str) -> None:
        if "$ref" in schema:
            ref = schema["$ref"]
            if not ref.startswith("#/$defs/"):
                raise _SchemaValidationError(f"{path}: unsupported ref {ref!r}")
            schema = self.defs[ref.removeprefix("#/$defs/")]

        if "allOf" in schema:
            for index, branch in enumerate(schema["allOf"]):
                self._validate(value, branch, f"{path}.allOf[{index}]")

        if "anyOf" in schema:
            errors: list[str] = []
            for branch in schema["anyOf"]:
                try:
                    self._validate(value, branch, path)
                    break
                except _SchemaValidationError as exc:
                    errors.append(str(exc))
            else:
                detail = "; ".join(errors[:3])
                raise _SchemaValidationError(f"{path}: no anyOf branch matched ({detail})")

        if "const" in schema and value != schema["const"]:
            raise _SchemaValidationError(
                f"{path}: expected const {schema['const']!r}, got {value!r}"
            )

        if "enum" in schema and value not in schema["enum"]:
            raise _SchemaValidationError(
                f"{path}: expected one of {schema['enum']!r}, got {value!r}"
            )

        if "type" in schema and not self._matches_type(value, schema["type"]):
            raise _SchemaValidationError(
                f"{path}: expected type {schema['type']!r}, got {type(value).__name__}"
            )

        if isinstance(value, dict):
            for required in schema.get("required", []):
                if required not in value:
                    raise _SchemaValidationError(f"{path}: missing required field {required!r}")
            for key, child_schema in schema.get("properties", {}).items():
                if key in value:
                    self._validate(value[key], child_schema, f"{path}.{key}")

        if isinstance(value, list):
            if len(value) < schema.get("minItems", 0):
                raise _SchemaValidationError(f"{path}: fewer than minItems")
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                raise _SchemaValidationError(f"{path}: more than maxItems")
            if schema.get("uniqueItems") and len({self._freeze(item) for item in value}) != len(value):
                raise _SchemaValidationError(f"{path}: uniqueItems violated")
            if "items" in schema:
                for index, item in enumerate(value):
                    self._validate(item, schema["items"], f"{path}[{index}]")

        if isinstance(value, str):
            if len(value) < schema.get("minLength", 0):
                raise _SchemaValidationError(f"{path}: shorter than minLength")
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                raise _SchemaValidationError(f"{path}: longer than maxLength")
            if schema.get("format") == "date-time":
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise _SchemaValidationError(f"{path}: invalid date-time") from exc

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                raise _SchemaValidationError(f"{path}: below minimum")
            if "maximum" in schema and value > schema["maximum"]:
                raise _SchemaValidationError(f"{path}: above maximum")

    @staticmethod
    def _matches_type(value: Any, expected: str | list[str]) -> bool:
        expected_types = [expected] if isinstance(expected, str) else expected
        for expected_type in expected_types:
            if expected_type == "null" and value is None:
                return True
            if expected_type == "object" and isinstance(value, dict):
                return True
            if expected_type == "array" and isinstance(value, list):
                return True
            if expected_type == "string" and isinstance(value, str):
                return True
            if expected_type == "boolean" and isinstance(value, bool):
                return True
            if expected_type == "integer" and isinstance(value, int) and not isinstance(value, bool):
                return True
            if expected_type == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
                return True
        return False

    @staticmethod
    def _freeze(value: Any) -> Any:
        if isinstance(value, dict):
            return tuple(sorted((key, _ContractSchemaValidator._freeze(item)) for key, item in value.items()))
        if isinstance(value, list):
            return tuple(_ContractSchemaValidator._freeze(item) for item in value)
        return value


def _base_request(run_kind: str) -> dict[str, Any]:
    manifest = {
        "context_manifest_id": "manifest-1",
        "request_kind": run_kind,
        "package_ref": {"package_id": "pkg-1", "package_version": 3, "state_version": 8},
        "structured_package_input_ref": {"id": "spi-1", "content_hash": "sha256:abc"},
        "message_scope": {"from_seq": 1, "through_seq": 4, "history_compaction_ref": None, "raw_user_message_ref": "msg-4"},
        "instruction_and_schema_refs": ["instructions:v1", "schema:reply:v1"],
        "source_refs": ["source:meeting-1"],
        "included_sections": ["evidence", "open_questions"],
        "omissions": [],
        "assembly_policy_version": "assembly:v1",
        "budget_ref": "budget:default",
        "degradation_flags": [],
        "content_hashes": {"package": "sha256:pkg"},
        "transport_ref": {
            "provider_id": "fake-provider",
            "adapter_version": "fake-adapter:v1",
            "protocol_version": "pi-runtime.protocol.v1",
            "capability_profile_version": "fake-capabilities:v1",
        },
    }
    request: dict[str, Any] = {
        "schema_version": "pi-runtime.request.v1",
        "run_id": "run-1",
        "run_kind": run_kind,
        "workspace_id": "ws-1",
        "conversation_id": "conv-1",
        "package_id": "pkg-1",
        "from_message_seq": 1,
        "through_message_seq": 4,
        "context_manifest": manifest,
        "instructions_ref": "instructions:v1",
        "model_policy": {
            "quality_tier": "balanced",
            "latency_tier": "standard",
            "structured_output_required": run_kind != "chat",
            "tool_calling_required": run_kind == "convergence",
            "max_cost": 1.0,
            "provider_allowlist": ["fake-provider"],
        },
        "tool_profile": {
            "run_kind": run_kind,
            "allowed_tools": ["source.resolve"] if run_kind != "judgement" else [],
            "max_calls": 4,
            "max_result_bytes": 65536,
        },
        "deadline_ms": 10000,
        "trace_context": {"trace_id": "trace-1", "request_id": "request-1"},
        "idempotency_key": "run-1",
    }
    if run_kind == "chat":
        request.update(
            raw_user_message_ref="msg-4",
            assistant_reply_schema_ref="schema:assistant:v1",
            conversation_order_key="conv-1:4",
        )
    elif run_kind == "judgement":
        request.update(
            chat_turn_id="turn-1",
            base_state_version=8,
            base_package_version=3,
            signal_summary_ref="signal:turn-1",
        )
        request.pop("package_id")
    else:
        request.update(
            convergence_run_id="convergence-1",
            base_state_version=8,
            base_package_version=3,
            proposal_schema_ref="schema:proposal:v1",
            proposal_capture_tool_ref="tool:submit_convergence_proposal:v1",
        )
    return request


def _proposal() -> dict[str, Any]:
    return {
        "proposal_schema_version": "evocanvas.convergence-proposal.v1",
        "proposal_id": "proposal-1",
        "run_id": "run-1",
        "package_id": "pkg-1",
        "from_message_seq": 1,
        "through_message_seq": 4,
        "base_state_version": 8,
        "base_package_version": 3,
        "operations": [
            {
                "operation_id": "operation-1",
                "operation_type": "clarification.open",
                "target_object_id": None,
                "temporary_target_ref": "tmp:clarification:1",
                "before_ref": None,
                "payload": {"title": "确认目标用户"},
                "source_refs": ["source:meeting-1"],
                "confirmation_refs": [],
                "unresolved_refs": ["gap:target-user"],
                "risk_level": "low",
                "reason_codes": ["missing_scope"],
                "atomic_group_id": "atomic-1",
            }
        ],
    }


class PiRuntimeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.validator = _ContractSchemaValidator(cls.schema)

    def assert_valid(self, value: Any, definition: str) -> None:
        try:
            self.validator.validate(value, definition)
        except _SchemaValidationError as exc:
            self.fail(f"{definition} fixture should validate: {exc}")

    def assert_invalid(self, value: Any, definition: str) -> None:
        with self.assertRaises(_SchemaValidationError):
            self.validator.validate(value, definition)

    def test_v1_schema_is_parseable_and_has_contract_definitions(self) -> None:
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(
            self.schema["properties"]["contract_version"]["const"],
            "pi-runtime.contracts.v1",
        )
        for definition in (
            "ChatRunRequest",
            "JudgementRunRequest",
            "ConvergenceRunRequest",
            "EventEnvelope",
            "ConvergenceProposal",
            "ToolCallRequest",
            "ToolCallResult",
            "ErrorEnvelope",
        ):
            self.assertIn(definition, self.schema["$defs"])

    def test_chat_judgement_and_convergence_requests_validate(self) -> None:
        for kind in ("chat", "judgement", "convergence"):
            with self.subTest(run_kind=kind):
                self.assert_valid(_base_request(kind), f"{kind.title()}RunRequest")

    def test_runtime_inputs_fixture_validates_as_a_chat_request(self) -> None:
        fixture = json.loads(RUNTIME_INPUTS_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assert_valid(fixture, "ChatRunRequest")
        runtime_inputs = fixture["runtime_inputs"]
        self.assertEqual(runtime_inputs["structured_package_input"]["intent"], "reduce requirement distortion")
        self.assertEqual(runtime_inputs["conversation_messages"][-1]["message_id"], "msg-4")
        self.assertEqual(runtime_inputs["raw_user_message"], runtime_inputs["conversation_messages"][-1]["content"])

    def test_result_fixtures_validate(self) -> None:
        model_identity = {
            "provider_id": "fake-provider",
            "model_id": "fake-model",
            "adapter_version": "fake-adapter:v1",
            "protocol_version": "pi-runtime.protocol.v1",
        }
        usage = {"input_tokens": 10, "output_tokens": 12, "total_tokens": 22, "provider_usage_ref": None}
        self.assert_valid(
            {
                "run_id": "run-1",
                "assistant_message": {"content_blocks": [{"type": "text", "text": "收到，我先整理待澄清项。"}]},
                "finish_reason": "completed",
                "events_summary": {"event_count": 2},
                "usage": usage,
                "model_identity": model_identity,
                "context_manifest_id": "manifest-1",
            },
            "ChatRunResult",
        )
        self.assert_valid(
            {
                "run_id": "run-1",
                "decision": "trigger",
                "reason_codes": ["new_evidence"],
                "through_message_seq": 4,
                "confidence": 0.91,
                "usage": usage,
                "model_identity": model_identity,
                "context_manifest_id": "manifest-1",
            },
            "JudgementRunResult",
        )
        self.assert_valid(
            {
                "run_id": "run-1",
                "proposal": _proposal(),
                "finish_reason": "completed",
                "tool_trace": ["tool-call-1"],
                "usage": usage,
                "model_identity": model_identity,
                "context_manifest_id": "manifest-1",
            },
            "ConvergenceRunResult",
        )

    def test_event_proposal_tool_and_error_fixtures_validate(self) -> None:
        event = {
            "schema_version": "pi-runtime.event.v1",
            "event_id": "event-1",
            "run_id": "run-1",
            "sequence": 1,
            "timestamp": "2026-08-14T12:00:00Z",
            "type": "run.completed",
            "trace_context": {"trace_id": "trace-1", "request_id": "request-1"},
            "payload": {"finish_reason": "completed"},
        }
        self.assert_valid(event, "EventEnvelope")
        self.assert_valid(_proposal(), "ConvergenceProposal")
        self.assert_valid(
            {
                "schema_version": "pi-runtime.tool-call.v1",
                "tool_call_id": "tool-call-1",
                "tool_name": "source.resolve",
                "tool_version": "source.resolve:v1",
                "run_id": "run-1",
                "run_kind": "convergence",
                "workspace_id": "ws-1",
                "conversation_id": "conv-1",
                "package_id": "pkg-1",
                "message_range": {"from_seq": 1, "through_seq": 4},
                "arguments": {"source_ref": "source:meeting-1"},
                "attempt": 1,
                "trace_context": {"trace_id": "trace-1", "request_id": "request-1"},
            },
            "ToolCallRequest",
        )
        self.assert_valid(
            {
                "schema_version": "pi-runtime.tool-result.v1",
                "tool_call_id": "tool-call-1",
                "status": "succeeded",
                "summary": "已读取来源指针",
                "data": {"content_hash": "sha256:abc"},
                "data_ref": None,
                "source_refs": ["source:meeting-1"],
                "artifacts": [],
                "error": None,
                "completed_at": "2026-08-14T12:00:01Z",
            },
            "ToolCallResult",
        )
        self.assert_valid(
            {
                "schema_version": "pi-runtime.error.v1",
                "error_code": "run_id_conflict",
                "category": "input_error",
                "message": "run_id 已存在且幂等键不一致",
                "retryable": False,
                "run_id": "run-1",
                "trace_id": "trace-1",
                "details": {"idempotency_key": "other-key"},
            },
            "ErrorEnvelope",
        )

    def test_invalid_run_id_and_missing_required_fields_fail(self) -> None:
        empty_run_id = _base_request("chat")
        empty_run_id["run_id"] = ""
        self.assert_invalid(empty_run_id, "ChatRunRequest")

        missing_idempotency_key = _base_request("chat")
        del missing_idempotency_key["idempotency_key"]
        self.assert_invalid(missing_idempotency_key, "ChatRunRequest")

        invalid_conflict_error_code = {
            "schema_version": "pi-runtime.error.v1",
            "error_code": "run_id_conflicted",
            "category": "input_error",
            "message": "invalid code",
            "retryable": False,
            "details": {},
        }
        self.assert_invalid(invalid_conflict_error_code, "ErrorEnvelope")

    def test_invalid_event_envelope_fails(self) -> None:
        event = {
            "schema_version": "pi-runtime.event.v1",
            "event_id": "event-1",
            "run_id": "run-1",
            "sequence": 1,
            "timestamp": "2026-08-14T12:00:00Z",
            "type": "run.completed",
            "trace_context": {"trace_id": "trace-1", "request_id": "request-1"},
            "payload": {},
        }

        missing_trace = copy.deepcopy(event)
        del missing_trace["trace_context"]
        self.assert_invalid(missing_trace, "EventEnvelope")

        zero_sequence = copy.deepcopy(event)
        zero_sequence["sequence"] = 0
        self.assert_invalid(zero_sequence, "EventEnvelope")

        malformed_timestamp = copy.deepcopy(event)
        malformed_timestamp["timestamp"] = "not-a-date"
        self.assert_invalid(malformed_timestamp, "EventEnvelope")


if __name__ == "__main__":
    unittest.main()

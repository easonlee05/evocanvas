"""Pi Runtime v1 合同的跨语言 fixture 测试。

直接对机器可读合同 docs/technical-specs/schemas/pi-runtime/v1-contracts.json
和 fixtures 进行验证。
测试只依赖 Python 标准库。
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import Any


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs/technical-specs/schemas/pi-runtime/v1-contracts.json"
)
FIXTURES_DIR = SCHEMA_PATH.parent / "fixtures"


class _SchemaValidationError(AssertionError):
    """轻量 JSON Schema 校验器的可读错误。"""


class _ContractSchemaValidator:
    """验证 Pi v1 合同使用到的 JSON Schema 2020-12 子集。"""

    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document
        self.defs = document["$defs"]

    def validate(self, value: Any, definition: str) -> None:
        self._validate(value, {"$ref": f"#/$defs/{definition}"}, "$")

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

        if "oneOf" in schema:
            matched = 0
            for branch in schema["oneOf"]:
                try:
                    self._validate(value, branch, path)
                    matched += 1
                except _SchemaValidationError:
                    pass
            if matched != 1:
                raise _SchemaValidationError(f"{path}: expected exactly one oneOf branch match, got {matched}")

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

        if isinstance(value, str):
            if "minLength" in schema and len(value) < schema["minLength"]:
                raise _SchemaValidationError(f"{path}: shorter than minLength {schema['minLength']}")
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                raise _SchemaValidationError(f"{path}: longer than maxLength {schema['maxLength']}")
            if "pattern" in schema and not re.search(schema["pattern"], value):
                raise _SchemaValidationError(f"{path}: value {value!r} does not match pattern {schema['pattern']!r}")

        if isinstance(value, dict):
            for required in schema.get("required", []):
                if required not in value:
                    raise _SchemaValidationError(f"{path}: missing required field {required!r}")
            if schema.get("additionalProperties") is False:
                properties = schema.get("properties", {})
                for key in value:
                    if key not in properties:
                        raise _SchemaValidationError(f"{path}: unexpected additional property {key!r}")
            for key, child_schema in schema.get("properties", {}).items():
                if key in value:
                    self._validate(value[key], child_schema, f"{path}.{key}")

        if isinstance(value, list):
            if len(value) < schema.get("minItems", 0):
                raise _SchemaValidationError(f"{path}: fewer than minItems")
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                raise _SchemaValidationError(f"{path}: more than maxItems")
            if "items" in schema:
                for index, item in enumerate(value):
                    self._validate(item, schema["items"], f"{path}[{index}]")

    @staticmethod
    def _matches_type(value: Any, expected_type: str) -> bool:
        if expected_type == "object":
            return isinstance(value, dict)
        if expected_type == "array":
            return isinstance(value, list)
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "null":
            return value is None
        return True


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
        self.assertIn("EvoCanvas Pi Session Integration Contracts v1", self.schema["title"])
        for definition in (
            "WorkspaceSessionBinding",
            "UserSubmissionRequest",
            "UserSubmissionReceipt",
            "WorkspaceCommitRequest",
            "ToolExecutionRecord",
            "SessionLifecycleCommand",
            "SessionLifecycleResult",
        ):
            self.assertIn(definition, self.schema["$defs"])

    def test_user_submission_request_fixture_validates(self) -> None:
        fixture_path = FIXTURES_DIR / "user-submission-request.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assert_valid(fixture, "UserSubmissionRequest")
        self.assertEqual(fixture["contract_type"], "user_submission_request")
        self.assertEqual(fixture["schema_version"], "evocanvas.pi-runtime.v1")
        self.assertEqual(fixture["workspace_id"], "workspace-01")

    def test_workspace_commit_request_fixture_validates(self) -> None:
        fixture_path = FIXTURES_DIR / "workspace-commit-request.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assert_valid(fixture, "WorkspaceCommitRequest")
        self.assertEqual(fixture["contract_type"], "workspace_commit_request")
        self.assertEqual(fixture["tool_context"]["capabilities"], ["workspace:commit"])

    def test_session_lifecycle_result_fixture_validates(self) -> None:
        fixture_path = FIXTURES_DIR / "session-delete-result.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assert_valid(fixture, "SessionLifecycleResult")
        self.assertEqual(fixture["contract_type"], "session_lifecycle_result")
        self.assertEqual(fixture["action"], "delete")
        self.assertEqual(fixture["outcome"], "partial")

    def test_workspace_session_binding_validates(self) -> None:
        valid_binding = {
            "contract_type": "workspace_session_binding",
            "schema_version": "evocanvas.pi-runtime.v1",
            "workspace_id": "ws-01",
            "primary_session_id": "sess-01",
            "main_lane": "main",
            "status": "ready",
            "pi_session_format_version": "1.0",
            "session_file_ref": "sess-01.sqlite",
            "created_at": "2026-09-08T10:00:00Z",
            "last_opened_at": "2026-09-08T10:00:00Z",
        }
        self.assert_valid(valid_binding, "WorkspaceSessionBinding")

        # invalid status
        invalid_binding = dict(valid_binding, status="invalid_status")
        self.assert_invalid(invalid_binding, "WorkspaceSessionBinding")

        # missing required field
        invalid_binding2 = dict(valid_binding)
        del invalid_binding2["primary_session_id"]
        self.assert_invalid(invalid_binding2, "WorkspaceSessionBinding")

    def test_user_submission_receipt_validates(self) -> None:
        valid_receipt = {
            "contract_type": "user_submission_receipt",
            "schema_version": "evocanvas.pi-runtime.v1",
            "status": "accepted",
            "submission_id": "sub-01",
            "content_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "session_id": "sess-01",
            "entry_id": "entry-01",
            "binding_status": "ready",
        }
        self.assert_valid(valid_receipt, "UserSubmissionReceipt")

        # invalid status
        self.assert_invalid(dict(valid_receipt, status="unknown"), "UserSubmissionReceipt")

    def test_tool_execution_record_validates(self) -> None:
        valid_record = {
            "contract_type": "tool_execution_record",
            "schema_version": "evocanvas.pi-runtime.v1",
            "tool_name": "workspace.commit",
            "tool_version": "1.0",
            "tool_context": {
                "workspace_id": "ws-01",
                "session_id": "sess-01",
                "turn_id": "turn-01",
                "entry_id": "entry-01",
                "invocation_id": "inv-01",
                "tool_call_id": "call-01",
                "actor_id": "user-01",
                "capabilities": ["workspace:commit"],
                "current_revision_id": "rev-01",
                "instruction_bundle_version": "ib-01",
                "active_skill_versions": [],
            },
            "side_effect_class": "workspace",
            "replay": "safe",
            "result_status": "success",
            "request_hash": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "started_at": "2026-09-08T10:00:00Z",
            "finished_at": "2026-09-08T10:00:01Z",
        }
        self.assert_valid(valid_record, "ToolExecutionRecord")

        # invalid replay
        self.assert_invalid(dict(valid_record, replay="retry_always"), "ToolExecutionRecord")

    def test_session_lifecycle_command_validates(self) -> None:
        valid_cmd = {
            "contract_type": "session_lifecycle_command",
            "schema_version": "evocanvas.pi-runtime.v1",
            "lifecycle_operation_id": "life-01",
            "workspace_id": "ws-01",
            "action": "archive",
            "idempotency_key": "idem-01",
        }
        self.assert_valid(valid_cmd, "SessionLifecycleCommand")

        # invalid action
        self.assert_invalid(dict(valid_cmd, action="destroy"), "SessionLifecycleCommand")

    def test_content_hash_pattern_enforced(self) -> None:
        valid_req = {
            "contract_type": "user_submission_request",
            "schema_version": "evocanvas.pi-runtime.v1",
            "submission_id": "sub-01",
            "content_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "workspace_id": "ws-01",
            "actor_id": "user-01",
            "pi_user_message": {"role": "user", "content": "hi"},
        }
        self.assert_valid(valid_req, "UserSubmissionRequest")

        # invalid hash pattern
        self.assert_invalid(dict(valid_req, content_hash="not-a-sha256"), "UserSubmissionRequest")
        self.assert_invalid(dict(valid_req, content_hash="sha256:short"), "UserSubmissionRequest")


if __name__ == "__main__":
    unittest.main()

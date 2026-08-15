"""Pi 迁移所需的四类 Python 运行记录与包级租约。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, ClassVar, Mapping


class RuntimeRecordValidationError(ValueError):
    """运行记录缺少 L3 必需字段。"""


def _text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeRecordValidationError(f"{field_name} must be a non-empty string")
    return value


def _non_negative(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RuntimeRecordValidationError(f"{field_name} must be an integer >= 0")
    return value


@dataclass(frozen=True)
class ChatTurnRecord:
    chat_turn_id: str
    workspace_id: str
    conversation_id: str
    package_id: str | None
    message_seq: int
    status: str
    created_at: str
    updated_at: str
    assistant_message_id: str | None = None
    failure_code: str | None = None
    record_type: ClassVar[str] = "chat_turn"

    def __post_init__(self) -> None:
        _text(self.chat_turn_id, "chat_turn_id")
        _text(self.workspace_id, "workspace_id")
        _text(self.conversation_id, "conversation_id")
        _non_negative(self.message_seq, "message_seq")
        _text(self.status, "status")
        _text(self.created_at, "created_at")
        _text(self.updated_at, "updated_at")

    def to_dict(self) -> dict[str, Any]:
        return {"record_type": self.record_type, **asdict(self)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ChatTurnRecord":
        values = dict(payload)
        values.pop("record_type", None)
        return cls(**values)


@dataclass(frozen=True)
class ConvergenceJudgementRecord:
    judgement_id: str
    chat_turn_id: str
    workspace_id: str
    package_id: str | None
    through_message_seq: int
    status: str
    decision: str | None
    reason_codes: tuple[str, ...]
    created_at: str
    updated_at: str
    failure_code: str | None = None
    record_type: ClassVar[str] = "convergence_judgement"

    def __post_init__(self) -> None:
        _text(self.judgement_id, "judgement_id")
        _text(self.chat_turn_id, "chat_turn_id")
        _text(self.workspace_id, "workspace_id")
        _non_negative(self.through_message_seq, "through_message_seq")
        _text(self.status, "status")
        _text(self.created_at, "created_at")
        _text(self.updated_at, "updated_at")

    def to_dict(self) -> dict[str, Any]:
        payload = {"record_type": self.record_type, **asdict(self)}
        payload["reason_codes"] = list(self.reason_codes)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ConvergenceJudgementRecord":
        values = dict(payload)
        values.pop("record_type", None)
        values["reason_codes"] = tuple(values.get("reason_codes", []))
        return cls(**values)


@dataclass(frozen=True)
class ConvergenceRunRecord:
    convergence_run_id: str
    workspace_id: str
    package_id: str
    from_message_seq: int
    through_message_seq: int
    base_state_version: int
    base_package_version: int
    status: str
    business_result: str | None
    created_at: str
    updated_at: str
    proposal_id: str | None = None
    failure_code: str | None = None
    record_type: ClassVar[str] = "convergence_run"

    def __post_init__(self) -> None:
        _text(self.convergence_run_id, "convergence_run_id")
        _text(self.workspace_id, "workspace_id")
        _text(self.package_id, "package_id")
        _non_negative(self.from_message_seq, "from_message_seq")
        _non_negative(self.through_message_seq, "through_message_seq")
        if self.through_message_seq < self.from_message_seq:
            raise RuntimeRecordValidationError("through_message_seq must be >= from_message_seq")
        _non_negative(self.base_state_version, "base_state_version")
        _non_negative(self.base_package_version, "base_package_version")
        _text(self.status, "status")
        _text(self.created_at, "created_at")
        _text(self.updated_at, "updated_at")

    def to_dict(self) -> dict[str, Any]:
        return {"record_type": self.record_type, **asdict(self)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ConvergenceRunRecord":
        values = dict(payload)
        values.pop("record_type", None)
        return cls(**values)


@dataclass(frozen=True)
class CommitAttemptRecord:
    commit_attempt_id: str
    operation_id: str
    workspace_id: str
    package_id: str
    base_state_version: int
    base_package_version: int
    status: str
    created_at: str
    updated_at: str
    result_code: str | None = None
    error_code: str | None = None
    record_type: ClassVar[str] = "commit_attempt"

    def __post_init__(self) -> None:
        _text(self.commit_attempt_id, "commit_attempt_id")
        _text(self.operation_id, "operation_id")
        _text(self.workspace_id, "workspace_id")
        _text(self.package_id, "package_id")
        _non_negative(self.base_state_version, "base_state_version")
        _non_negative(self.base_package_version, "base_package_version")
        _text(self.status, "status")
        _text(self.created_at, "created_at")
        _text(self.updated_at, "updated_at")

    def to_dict(self) -> dict[str, Any]:
        return {"record_type": self.record_type, **asdict(self)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CommitAttemptRecord":
        values = dict(payload)
        values.pop("record_type", None)
        return cls(**values)


@dataclass(frozen=True)
class PackageLease:
    workspace_id: str
    package_id: str
    lease_id: str
    holder_run_id: str
    acquired_at: str
    expires_at: str

    def __post_init__(self) -> None:
        for field_name in ("workspace_id", "package_id", "lease_id", "holder_run_id", "acquired_at", "expires_at"):
            _text(getattr(self, field_name), field_name)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PackageLease":
        return cls(
            workspace_id=str(payload["workspace_id"]),
            package_id=str(payload["package_id"]),
            lease_id=str(payload["lease_id"]),
            holder_run_id=str(payload["holder_run_id"]),
            acquired_at=str(payload["acquired_at"]),
            expires_at=str(payload["expires_at"]),
        )

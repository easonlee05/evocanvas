"""EvoCanvas 确认记录（ConfirmationRecord）。

L3 规格要求：确认记录本身不可改写；撤回通过追加 confirmation_withdrawn
事件与新确认记录表达，不修改旧记录。确认记录必须能回指 Chat 中的
Assistant 提议消息与 User 确认消息，并显式记录适用范围与仍未解决的引用。

参见 docs/harness/02-memory-state/02 State Ledger（状态账本）.md
与 docs/harness/05-safety-governance/07 Authority and Guardrails（权限与护栏）.md。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List


class ConfirmationKind(str, Enum):
    """确认范围匹配结果。

    规格要求至少区分：明确确认、部分确认、试探表达（不放行）、明确否定、
    带修正确认、确认后撤回/推翻、泛化点击（不放行）。
    """

    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    REJECTED = "rejected"
    CORRECTED = "corrected"
    WITHDRAWN = "withdrawn"


class ConfirmationPath(str, Enum):
    """确认来源路径。

    L3 规格要求确认记录显式区分两条路径：
    - Assistant 提议后用户明确确认或修正；
    - 用户直接给出清晰、完整且带范围的产品判断（不要求 Assistant 先复述）。

    参见 docs/harness/02-memory-state/02 State Ledger（状态账本）.md
    与 docs/harness/05-safety-governance/07 Authority and Guardrails（权限与护栏）.md。
    """

    ASSISTANT_PROPOSAL_THEN_USER_RESPONSE = "assistant_proposal_then_user_response"
    DIRECT_USER_STATEMENT = "direct_user_statement"


@dataclass
class ConfirmedClaim:
    """单条已确认判断或动作，含适用对象范围。"""

    claim: str
    scope_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将已确认判断序列化为字典。"""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfirmedClaim":
        """从字典恢复已确认判断。"""

        return cls(
            claim=data.get("claim", ""),
            scope_refs=list(data.get("scope_refs", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ConfirmationRecord:
    """不可改写的确认记录。

    撤回通过追加 confirmation_withdrawn 账本事件与新确认记录表达，
    不修改本记录任何字段。confirmed_claims 必须显式记录确认的判断、
    动作及其适用对象范围；remaining_unresolved_refs 记录确认后仍未解决的引用。

    confirmation_path 区分两条合法确认路径：
    - assistant_proposal_then_user_response：Assistant 提议后用户确认或修正；
    - direct_user_statement：用户直接给出清晰、完整且带范围的产品判断。

    直接陈述路径下 proposal_message_refs 可为空；assistant 提议路径下必填。
    """

    confirmation_id: str
    workspace_id: str
    package_id: str
    user_message_refs: List[str]
    confirmed_claims: List[ConfirmedClaim]
    scope_refs: List[str]
    confirmation_kind: ConfirmationKind
    remaining_unresolved_refs: List[str]
    recorded_at: str
    confirmation_path: ConfirmationPath = ConfirmationPath.ASSISTANT_PROPOSAL_THEN_USER_RESPONSE
    proposal_message_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将确认记录序列化为字典。"""

        data = asdict(self)
        data["confirmation_kind"] = self.confirmation_kind.value
        data["confirmation_path"] = self.confirmation_path.value
        data["confirmed_claims"] = [claim.to_dict() for claim in self.confirmed_claims]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfirmationRecord":
        """从字典恢复确认记录实例。

        兼容历史持久化数据：缺失 confirmation_path 时按 assistant 提议路径恢复，
        因为历史记录均走该路径。
        """

        kind_raw = data.get("confirmation_kind", ConfirmationKind.CONFIRMED.value)
        path_raw = data.get(
            "confirmation_path",
            ConfirmationPath.ASSISTANT_PROPOSAL_THEN_USER_RESPONSE.value,
        )
        return cls(
            confirmation_id=data["confirmation_id"],
            workspace_id=data.get("workspace_id", ""),
            package_id=data.get("package_id", ""),
            proposal_message_refs=list(data.get("proposal_message_refs", [])),
            user_message_refs=list(data.get("user_message_refs", [])),
            confirmed_claims=[
                ConfirmedClaim.from_dict(item) for item in data.get("confirmed_claims", [])
            ],
            scope_refs=list(data.get("scope_refs", [])),
            confirmation_kind=ConfirmationKind(kind_raw),
            remaining_unresolved_refs=list(data.get("remaining_unresolved_refs", [])),
            recorded_at=data.get("recorded_at", ""),
            confirmation_path=ConfirmationPath(path_raw),
            metadata=dict(data.get("metadata", {})),
        )

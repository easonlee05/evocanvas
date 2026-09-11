"""EvoCanvas 运行时状态辅助。

L3 规格已废弃未类型化语义：stage_node / checkpoint / pending_gate_ids /
transition_history / next_progression_hint 不再迁入对象状态，也不作为
主题阶段机。当前工作区运行时状态只保留与 active_turn 相关的最小占位
（属于 Runtime/Tools 模块范围，后续替换为包级租约）。

本模块现在提供：
- 基于类型化状态的未决对象提取（替代未类型化 unresolved_issue_ids_from_cards）。
- 账本事件构造辅助，供 service 层在同提交升级中追加事件。
- 交接物元数据与视图的派生（不再写聊天总结，不再维护主题阶段）。

参见 docs/harness/02-memory-state/02 State Ledger（状态账本）.md
与 docs/harness/04-orchestration-lifecycle/02 Lifecycle（生命周期）.md。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.canvas.domain.cards import CanvasCard, CanvasCardKind
from app.canvas.domain.handoff import StructuredHandoff
from app.canvas.domain.ledger import LedgerActorType, LedgerEvent, LedgerEventType
from app.canvas.domain.mutations import CanvasMutationProposal
from app.canvas.domain.object_status import (
    GovernanceClass,
    ValidationState,
    derive_governance_class,
    is_unresolved_status,
)
from app.canvas.domain.workspace import CanvasWorkspace


def unresolved_issue_ids_from_cards(cards: Iterable[CanvasCard]) -> list[str]:
    """根据当前卡片集合提取仍影响推进的未决对象 ID。

    基于类型化状态派生治理地位，不再依赖自由字符串状态比对，
    也不再读取 metadata.governance_state（已废弃双写）。
    """

    unresolved: list[str] = []
    for card in cards:
        kind_value = card.kind.value if hasattr(card.kind, "value") else str(card.kind)
        if is_unresolved_status(kind_value, card.status):
            unresolved.append(card.card_id)
    return unresolved


def ensure_workspace_runtime_defaults(workspace: CanvasWorkspace) -> CanvasWorkspace:
    """补齐工作区最小运行时元数据。

    L3 规格已废弃 lifecycle / verification_summary / state_ledger 等
    覆盖式摘要字段。本函数仅保留 active_turn 相关占位。历史
    handoff_metadata 不会在此补默认值或作为当前状态更新，避免形成包版本
    之外的第二份交接状态。
    """

    metadata = dict(workspace.metadata or {})
    # 不再写入 lifecycle / verification_summary / state_ledger。
    # 历史持久化数据中残留的这些字段保留为只读，不参与运行时决策。
    workspace.metadata = metadata

    return workspace


def build_handoff_metadata(
    cards: Iterable[CanvasCard],
    *,
    confirmation_state: str,
    source_snapshot_id: str,
    refreshed_by: str,
    refreshed_at: str,
) -> Dict[str, Any]:
    """生成结构化交接物的最小可追溯元数据。

    基于类型化状态派生未决与高置信未确认计数，不再依赖未类型化 stage_node。
    """

    card_list = list(cards)
    unresolved_count = 0
    high_confidence_unconfirmed_count = 0
    generated_from_card_ids: list[str] = []
    for card in card_list:
        generated_from_card_ids.append(card.card_id)
        kind_value = card.kind.value if hasattr(card.kind, "value") else str(card.kind)
        governance_class = derive_governance_class(kind_value, card.status)
        if governance_class == GovernanceClass.UNRESOLVED:
            unresolved_count += 1
        if governance_class == GovernanceClass.UNRESOLVED and card.validation_state in {
            ValidationState.VALID.value,
            ValidationState.WARNING.value,
        }:
            high_confidence_unconfirmed_count += 1

    return {
        "confirmation_state": confirmation_state,
        "source_snapshot_id": source_snapshot_id,
        "generated_from_card_ids": generated_from_card_ids,
        "generated_from_card_count": len(generated_from_card_ids),
        "unresolved_count": unresolved_count,
        "high_confidence_unconfirmed_count": high_confidence_unconfirmed_count,
        "refreshed_by": refreshed_by,
        "refreshed_at": refreshed_at,
    }


def build_handoff_state(
    workspace: CanvasWorkspace,
    handoff: Optional[StructuredHandoff],
    handoff_status: Optional[str] = None,
) -> Dict[str, Any]:
    """从工作区与交接物构造前端可直接消费的交接状态。

    L3 规格要求交接有效性只读取包版本 initial_governance_status 及账本叠加。
    因此只消费调用方传入的包版本投影状态和交接模块元数据；不读取工作区
    的历史 handoff_status / handoff_metadata 字段。
    """

    del workspace
    metadata = dict(handoff.metadata or {}) if handoff is not None else {}
    effective_status = handoff_status or "not_ready"
    confirmation_state = metadata.get("confirmation_state") or effective_status
    return {
        "status": effective_status,
        "confirmation_state": confirmation_state,
        "source_snapshot_id": metadata.get("source_snapshot_id", ""),
        "generated_from_card_count": metadata.get("generated_from_card_count", 0),
        "unresolved_count": metadata.get("unresolved_count", 0),
        "high_confidence_unconfirmed_count": metadata.get("high_confidence_unconfirmed_count", 0),
    }


def apply_turn_runtime_state(
    workspace: CanvasWorkspace,
    *,
    intent: str,
    proposal: CanvasMutationProposal,
    result_action: str,
    cards: Iterable[CanvasCard] | None = None,
    pending_gate_ids: Optional[list[str]] = None,
    unresolved_issue_ids: Optional[list[str]] = None,
) -> CanvasWorkspace:
    """将单轮处理结果回写到工作区运行时元数据。

    L3 规格已废弃 stage_node / checkpoint / transition_history 主题阶段机语义。
    本函数不再写入 lifecycle / verification_summary / state_ledger 覆盖式摘要，
    仅保留工作区元数据的轻量更新，供当前 UI 运行态使用。

    真正的状态变化应通过 append_ledger_event 追加账本事件记录，由 service 层
    在原子提交时调用。本函数仅为兼容现有 service 调用签名而保留。
    """

    ensure_workspace_runtime_defaults(workspace)
    # 不再写入 stage_node / checkpoint / transition_history / state_ledger。
    # 提案的验证回执与门禁原因保留在 proposal.metadata 中，由 service 层决定
    # 是否追加为账本事件，而不是覆盖式写入 workspace.metadata。
    return workspace


def build_canvas_view_meta(
    workspace: CanvasWorkspace,
    *,
    pending_confirmation_ids: list[str],
    handoff: Optional[StructuredHandoff],
    is_snapshot: bool,
    handoff_status: Optional[str] = None,
) -> Dict[str, Any]:
    """构建画布主视图的运行时元信息。

    L3 规格已废弃 lifecycle / verification_summary / state_ledger 覆盖式摘要。
    本函数只输出由调用方传入的包版本投影交接状态与待确认列表。
    """

    ensure_workspace_runtime_defaults(workspace)
    return {
        "handoff_status": handoff_status or "not_ready",
        "is_snapshot": is_snapshot,
        "pending_confirmation_ids": list(pending_confirmation_ids),
        "handoff_state": build_handoff_state(workspace, handoff, handoff_status),
    }


# ----------------------------------------------------------------------
# 账本事件构造辅助
# ----------------------------------------------------------------------


def make_object_created_event(
    *,
    ledger_event_id: str,
    workspace_id: str,
    package_id: str,
    object_id: str,
    object_type: str,
    operation_id: str,
    occurred_at: str,
    state_version_before: int = 0,
    state_version_after: int = 0,
    chat_turn_id: str = "",
    convergence_run_id: str = "",
    message_refs: Optional[list[str]] = None,
    source_refs: Optional[list[str]] = None,
    reason_codes: Optional[list[str]] = None,
    actor_type: LedgerActorType = LedgerActorType.SYSTEM,
    actor_id: str = "canvas_agent",
) -> LedgerEvent:
    """构造 object_created 账本事件。"""

    return LedgerEvent(
        ledger_event_id=ledger_event_id,
        workspace_id=workspace_id,
        package_id=package_id,
        event_type=LedgerEventType.OBJECT_CREATED,
        entity_type=object_type,
        entity_id=object_id,
        actor_type=actor_type,
        actor_id=actor_id,
        occurred_at=occurred_at,
        state_version_before=state_version_before,
        state_version_after=state_version_after,
        operation_id=operation_id,
        convergence_run_id=convergence_run_id,
        chat_turn_id=chat_turn_id,
        message_refs=list(message_refs or []),
        source_refs=list(source_refs or []),
        reason_codes=list(reason_codes or []),
    )


def make_object_status_changed_event(
    *,
    ledger_event_id: str,
    workspace_id: str,
    package_id: str,
    object_id: str,
    object_type: str,
    before_status: str,
    after_status: str,
    operation_id: str,
    occurred_at: str,
    state_version_before: int = 0,
    state_version_after: int = 0,
    chat_turn_id: str = "",
    convergence_run_id: str = "",
    confirmation_id: Optional[str] = None,
    message_refs: Optional[list[str]] = None,
    reason_codes: Optional[list[str]] = None,
    actor_type: LedgerActorType = LedgerActorType.SYSTEM,
    actor_id: str = "canvas_agent",
) -> LedgerEvent:
    """构造 object_status_changed 账本事件。"""

    return LedgerEvent(
        ledger_event_id=ledger_event_id,
        workspace_id=workspace_id,
        package_id=package_id,
        event_type=LedgerEventType.OBJECT_STATUS_CHANGED,
        entity_type=object_type,
        entity_id=object_id,
        actor_type=actor_type,
        actor_id=actor_id,
        occurred_at=occurred_at,
        state_version_before=state_version_before,
        state_version_after=state_version_after,
        before_ref=before_status,
        after_ref=after_status,
        operation_id=operation_id,
        convergence_run_id=convergence_run_id,
        chat_turn_id=chat_turn_id,
        confirmation_id=confirmation_id,
        message_refs=list(message_refs or []),
        reason_codes=list(reason_codes or []),
    )


def make_package_version_created_event(
    *,
    ledger_event_id: str,
    workspace_id: str,
    package_id: str,
    package_version: int,
    state_version_before: int,
    state_version_after: int,
    operation_id: str,
    occurred_at: str,
    convergence_run_id: str = "",
    reason_codes: Optional[list[str]] = None,
) -> LedgerEvent:
    """构造 package_version_created 账本事件。"""

    return LedgerEvent(
        ledger_event_id=ledger_event_id,
        workspace_id=workspace_id,
        package_id=package_id,
        event_type=LedgerEventType.PACKAGE_VERSION_CREATED,
        entity_type="package_version",
        entity_id=f"{package_id}@v{package_version}",
        actor_type=LedgerActorType.SYSTEM,
        actor_id="canvas_agent",
        occurred_at=occurred_at,
        package_version=package_version,
        state_version_before=state_version_before,
        state_version_after=state_version_after,
        operation_id=operation_id,
        convergence_run_id=convergence_run_id,
        reason_codes=list(reason_codes or []),
    )


def make_confirmation_recorded_event(
    *,
    ledger_event_id: str,
    workspace_id: str,
    package_id: str,
    confirmation_id: str,
    operation_id: str,
    occurred_at: str,
    message_refs: Optional[list[str]] = None,
    reason_codes: Optional[list[str]] = None,
) -> LedgerEvent:
    """构造 confirmation_recorded 账本事件。"""

    return LedgerEvent(
        ledger_event_id=ledger_event_id,
        workspace_id=workspace_id,
        package_id=package_id,
        event_type=LedgerEventType.CONFIRMATION_RECORDED,
        entity_type="confirmation",
        entity_id=confirmation_id,
        actor_type=LedgerActorType.USER,
        actor_id="user",
        occurred_at=occurred_at,
        operation_id=operation_id,
        confirmation_id=confirmation_id,
        message_refs=list(message_refs or []),
        reason_codes=list(reason_codes or []),
    )

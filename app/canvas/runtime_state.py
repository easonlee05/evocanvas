"""EvoCanvas 运行时状态辅助。

把 L 层生命周期状态、G 层门禁状态和交接物状态的最小运行时口径
集中在一个地方，避免这些结构散落在 service 里各自拼装。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from app.canvas.domain.cards import CanvasCard, CanvasCardKind
from app.canvas.domain.handoff import StructuredHandoff
from app.canvas.domain.mutations import CanvasMutationProposal
from app.canvas.domain.workspace import CanvasWorkspace


def default_lifecycle_state() -> Dict[str, Any]:
    """返回工作区默认生命周期状态。"""

    return {
        "stage_node": "compilation",
        "checkpoint": "idle",
        "pending_gate_ids": [],
        "unresolved_issue_ids": [],
    }


def default_verification_summary() -> Dict[str, Any]:
    """返回默认验证摘要。"""

    return {
        "result": "not_run",
        "checks": {},
        "gate_reason": "",
        "proposal_id": "",
    }


def ensure_workspace_runtime_defaults(workspace: CanvasWorkspace) -> CanvasWorkspace:
    """补齐工作区最小运行时元数据。"""

    metadata = dict(workspace.metadata or {})
    lifecycle = {**default_lifecycle_state(), **dict(metadata.get("lifecycle", {}))}
    verification_summary = {
        **default_verification_summary(),
        **dict(metadata.get("verification_summary", {})),
    }
    metadata["lifecycle"] = lifecycle
    metadata["verification_summary"] = verification_summary
    workspace.metadata = metadata

    handoff_metadata = dict(workspace.handoff_metadata or {})
    handoff_metadata.setdefault("source_snapshot_id", "")
    handoff_metadata.setdefault("generated_from_card_ids", [])
    handoff_metadata.setdefault("generated_from_card_count", 0)
    handoff_metadata.setdefault("unresolved_count", 0)
    handoff_metadata.setdefault("high_confidence_unconfirmed_count", 0)
    default_confirmation_state = (
        "not_ready"
        if not handoff_metadata.get("source_snapshot_id") and handoff_metadata.get("generated_from_card_count", 0) == 0
        else (workspace.handoff_status or "draft")
    )
    handoff_metadata.setdefault("confirmation_state", default_confirmation_state)
    workspace.handoff_metadata = handoff_metadata
    return workspace


def stage_node_for_intent(intent: str) -> str:
    """将 supervisor intent 映射为 L 层主链阶段节点。"""

    intent_set = {part.strip() for part in str(intent).split("+") if part.strip()}
    if "handoff" in intent_set:
        return "handoff"
    if {"constraint", "decision", "option"} & intent_set:
        return "convergence"
    if "clarification" in intent_set:
        return "clarification"
    return "compilation"


def unresolved_issue_ids_from_cards(cards: Iterable[CanvasCard]) -> list[str]:
    """根据当前卡片集合提取关键未决对象。"""

    unresolved: list[str] = []
    for card in cards:
        if card.kind in {CanvasCardKind.CLARIFICATION, CanvasCardKind.DECISION} and card.status in {
            "open",
            "draft",
            "pending",
        }:
            unresolved.append(card.card_id)
    return unresolved


def build_handoff_metadata(
    cards: Iterable[CanvasCard],
    *,
    confirmation_state: str,
    source_snapshot_id: str,
    refreshed_by: str,
    refreshed_at: str,
) -> Dict[str, Any]:
    """生成结构化交接物的最小可追溯元数据。"""

    card_list = list(cards)
    unresolved_count = 0
    generated_from_card_ids: list[str] = []
    for card in card_list:
        if card.kind == CanvasCardKind.HANDOFF:
            continue
        generated_from_card_ids.append(card.card_id)
        if card.kind in {CanvasCardKind.CLARIFICATION, CanvasCardKind.DECISION} and card.status in {
            "open",
            "draft",
            "pending",
        }:
            unresolved_count += 1

    return {
        "confirmation_state": confirmation_state,
        "source_snapshot_id": source_snapshot_id,
        "generated_from_card_ids": generated_from_card_ids,
        "generated_from_card_count": len(generated_from_card_ids),
        "unresolved_count": unresolved_count,
        "high_confidence_unconfirmed_count": 0,
        "refreshed_by": refreshed_by,
        "refreshed_at": refreshed_at,
    }


def build_handoff_state(
    workspace: CanvasWorkspace,
    handoff: Optional[StructuredHandoff],
) -> Dict[str, Any]:
    """从工作区与交接物构造前端可直接消费的交接状态。"""

    metadata = dict(workspace.handoff_metadata or {})
    if handoff is not None:
        metadata = {**metadata, **dict(handoff.metadata or {})}
    confirmation_state = metadata.get("confirmation_state") or workspace.handoff_status or "not_ready"
    return {
        "status": workspace.handoff_status or "not_ready",
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
    pending_gate_ids: Optional[list[str]] = None,
    unresolved_issue_ids: Optional[list[str]] = None,
) -> CanvasWorkspace:
    """将单轮处理结果回写到工作区运行时元数据。"""

    ensure_workspace_runtime_defaults(workspace)
    metadata = dict(workspace.metadata or {})
    receipt = dict(proposal.metadata.get("verification_receipt", {}))
    gate_reason = str(proposal.metadata.get("gate_reason", ""))
    metadata["verification_summary"] = {
        "result": receipt.get("result", "not_run"),
        "checks": dict(receipt.get("checks", {})),
        "gate_reason": gate_reason,
        "proposal_id": proposal.proposal_id,
    }
    metadata["lifecycle"] = {
        "stage_node": stage_node_for_intent(intent),
        "checkpoint": "awaiting_confirmation" if result_action == "pending_confirmation" else "applied",
        "pending_gate_ids": list(pending_gate_ids or []),
        "unresolved_issue_ids": list(unresolved_issue_ids or []),
    }
    workspace.metadata = metadata
    return workspace


def build_canvas_view_meta(
    workspace: CanvasWorkspace,
    *,
    pending_confirmation_ids: list[str],
    handoff: Optional[StructuredHandoff],
    is_snapshot: bool,
) -> Dict[str, Any]:
    """构建画布主视图的运行时元信息。"""

    ensure_workspace_runtime_defaults(workspace)
    return {
        "handoff_status": workspace.handoff_status,
        "is_snapshot": is_snapshot,
        "lifecycle": dict(workspace.metadata.get("lifecycle", default_lifecycle_state())),
        "verification_summary": dict(
            workspace.metadata.get("verification_summary", default_verification_summary())
        ),
        "pending_confirmation_ids": list(pending_confirmation_ids),
        "handoff_state": build_handoff_state(workspace, handoff),
    }

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
        "transition_history": [],
    }


def default_verification_summary() -> Dict[str, Any]:
    """返回默认验证摘要。"""

    return {
        "result": "not_run",
        "checks": {},
        "gate_reason": "",
        "proposal_id": "",
    }


def build_state_ledger(
    workspace: CanvasWorkspace,
    cards: Iterable[CanvasCard],
    proposal: CanvasMutationProposal,
    result_action: str,
) -> Dict[str, Any]:
    """生成工作区的最小状态账本。"""

    card_list = list(cards)
    blocked_by_card_ids: list[str] = []
    non_blocking_reminders: list[dict[str, Any]] = []

    # 1. 计算关键未决卡片 (blocked_by_card_ids) 和非阻塞提醒
    for card in card_list:
        if card.kind in {CanvasCardKind.CLARIFICATION, CanvasCardKind.DECISION} and card.status in {
            "open",
            "draft",
            "pending",
        }:
            blocked_by_card_ids.append(card.card_id)
        elif card.status == "superseded" or card.metadata.get("governance_state") == "under_review":
            non_blocking_reminders.append({
                "card_id": card.card_id,
                "title": card.title,
                "type": card.kind.value if hasattr(card.kind, "value") else str(card.kind),
                "reason": "已失效被替代" if card.status == "superseded" else "处于复核状态",
            })

    # 2. 计算阶段结论 stage_conclusion (主判断)
    stage_conclusion: dict[str, Any] = {}
    leading_card = None

    # 优先选取已确认的约束或决策卡片
    for card in card_list:
        if card.kind in {CanvasCardKind.CONSTRAINT, CanvasCardKind.DECISION} and card.status in {
            "confirmed",
            "effective",
        }:
            leading_card = card
            break

    # 若无，寻找未确认的候选约束或决策
    if leading_card is None:
        for card in card_list:
            if card.kind in {CanvasCardKind.CONSTRAINT, CanvasCardKind.DECISION} and card.status not in {
                "superseded",
            }:
                leading_card = card
                break

    if leading_card is not None:
        stage_conclusion = {
            "card_id": leading_card.card_id,
            "title": leading_card.title,
            "content_summary": leading_card.summary[:100] if leading_card.summary else "",
            "is_confirmed": leading_card.status in {"confirmed", "effective"},
            "lead_reason": "上位事实边界" if leading_card.kind == CanvasCardKind.CONSTRAINT else "已拍板决策",
        }
    else:
        stage_conclusion = {
            "card_id": None,
            "title": workspace.title or "待收敛结论",
            "content_summary": workspace.objective or "",
            "is_confirmed": False,
            "lead_reason": "初始目标",
        }

    # 3. 确定当前阶段和下一步推进 hint
    current_stage = workspace.metadata.get("lifecycle", {}).get("stage_node", "compilation")
    progression_map = {
        "compilation": "clarification",
        "clarification": "convergence",
        "convergence": "handoff",
        "handoff": "handoff",
    }
    next_hint = progression_map.get(current_stage, "handoff")

    gate_reason = str(proposal.metadata.get("gate_reason", ""))
    receipt = dict(proposal.metadata.get("verification_receipt", {}))
    if receipt.get("result") == "failed":
        gate_reason = "verification_failed"

    return {
        "stage_node": current_stage,
        "checkpoint": workspace.metadata.get("lifecycle", {}).get("checkpoint", "idle"),
        "next_progression_hint": next_hint,
        "gate_reason": gate_reason,
        "blocked_by_card_ids": blocked_by_card_ids,
        "non_blocking_reminders": non_blocking_reminders,
        "stage_conclusion": stage_conclusion,
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
    high_confidence_unconfirmed_count = 0
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
        if card.kind in {CanvasCardKind.CONSTRAINT, CanvasCardKind.DECISION} and card.status not in {
            "confirmed",
            "resolved",
            "superseded",
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
    cards: Iterable[CanvasCard] | None = None,
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

    # 确定初始阶段节点
    stage_node = stage_node_for_intent(intent)
    rollback_hint = proposal.metadata.get("rollback_hint")
    if rollback_hint:
        stage_node = rollback_hint

    # 提取原阶段状态与跃迁历史
    old_lifecycle = dict(metadata.get("lifecycle", default_lifecycle_state()))
    from_stage = old_lifecycle.get("stage_node", "compilation")

    # 相邻阶段回流校验保护算法
    stages_order = ["compilation", "clarification", "convergence", "handoff"]
    try:
        from_idx = stages_order.index(from_stage)
        to_idx = stages_order.index(stage_node)
        # 如果试图向前回滚且步长超过相邻段（即回滚2段或以上）
        if to_idx < from_idx - 1:
            # 强行修正为相邻的前序阶段，防止跨级大回退
            stage_node = stages_order[from_idx - 1]
    except ValueError:
        pass

    # 映射处理结果到运行时的 checkpoint
    checkpoint_map = {
        "pending_confirmation": "awaiting_confirmation",
        "downgrade_to_proposal": "fallback_to_proposal",
        "awaiting_clarification": "awaiting_clarification",
        "auto_apply": "applied",
        "approved": "applied",
    }
    checkpoint = checkpoint_map.get(result_action, "applied")

    # 记录跃迁历史
    history = list(old_lifecycle.get("transition_history", []))
    try:
        f_idx = stages_order.index(from_stage)
        t_idx = stages_order.index(stage_node)
        if t_idx > f_idx:
            action_type = "advance"
        elif t_idx < f_idx:
            action_type = "rollback"
        else:
            action_type = "stay"
    except ValueError:
        action_type = "stay"

    reason_category = "auto_apply"
    if result_action in {"downgrade_to_proposal", "awaiting_clarification"}:
        reason_category = "verification_failed"
    elif result_action == "pending_confirmation":
        reason_category = "gate_intercept"

    history.append({
        "turn_id": proposal.turn_id,
        "from_stage": from_stage,
        "to_stage": stage_node,
        "action_type": action_type,
        "reason_category": reason_category,
        "reason_details": f"意图: {intent}, 回合应用动作: {result_action}",
    })
    # 限制历史条数，防止元数据体积无限膨胀
    if len(history) > 30:
        history = history[-30:]

    metadata["lifecycle"] = {
        "stage_node": stage_node,
        "checkpoint": checkpoint,
        "pending_gate_ids": list(pending_gate_ids or []),
        "unresolved_issue_ids": list(unresolved_issue_ids or []),
        "transition_history": history,
    }
    workspace.metadata = metadata

    # 4. 生成状态账本并写入 metadata
    actual_cards = cards if cards is not None else []
    metadata["state_ledger"] = build_state_ledger(
        workspace, actual_cards, proposal, result_action
    )
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
        "state_ledger": dict(workspace.metadata.get("state_ledger", {})),
        "pending_confirmation_ids": list(pending_confirmation_ids),
        "handoff_state": build_handoff_state(workspace, handoff),
    }

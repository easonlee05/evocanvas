"""EvoCanvas 提案预验证。

当前只实现 V 层最小运行时基线：
- 结构验证
- 来源验证
- 策略验证

它不直接做放行裁决，只生成验证回执，供治理层和生命周期层继续处理。
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from app.canvas.domain.mutations import CanvasMutationProposal, CanvasMutationTarget
from app.canvas.domain.cards import CanvasCard
from app.canvas.domain.object_status import is_stable_status


@dataclass
class CanvasVerificationReceipt:
    """结构化验证回执。"""

    result: str  # passed, failed, warned, not_run
    checks: Dict[str, str]  # 各项检查项的结果 (passed/failed)
    notes: List[str]  # 检查错误/警告信息说明
    source_summary: str  # 依据来源摘要
    recommendation: str  # 建议分流去向

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def verify_mutation_proposal(
    proposal: CanvasMutationProposal,
    *,
    intent: str,
    existing_cards: list[CanvasCard] | None = None,
) -> Dict[str, Any]:
    """对提案执行最小 V 层检查并返回验证回执。"""

    from app.canvas.domain.cards import CanvasCardKind

    checks = {
        "structure": "passed",
        "source": "passed",
        "policy": "passed",
        "conflict": "passed",
        "evaluation": "passed",
    }
    notes: list[str] = []

    if not proposal.mutations:
        checks["structure"] = "failed"
        notes.append("提案中没有可执行的 mutation。")

    for mutation in proposal.mutations:
        # 1. 结构检查
        if mutation.target == CanvasMutationTarget.CARD:
            card_payload = mutation.payload.get("card")
            if card_payload is not None:
                if not str(card_payload.get("title", "")).strip():
                    checks["structure"] = "failed"
                    notes.append("卡片提案缺少标题。")
                if not str(card_payload.get("kind", "")).strip():
                    checks["structure"] = "failed"
                    notes.append("卡片提案缺少类型。")
            elif mutation.action.value == "update" and not mutation.target_id:
                checks["structure"] = "failed"
                notes.append("卡片更新提案缺少目标 ID。")

        if mutation.target == CanvasMutationTarget.HANDOFF:
            handoff_payload = mutation.payload.get("handoff", {})
            if not str(handoff_payload.get("handoff_id", "")).strip():
                checks["structure"] = "failed"
                notes.append("交接物提案缺少 handoff_id。")

        # 2. 依据来源检查：非 EVIDENCE 类型的卡片创建必须有关联的证据来源引用
        if mutation.target == CanvasMutationTarget.CARD and mutation.action.value == "add":
            card_payload = mutation.payload.get("card")
            if card_payload is not None:
                status = card_payload.get("status")
                kind = card_payload.get("kind")
                # L3 规格已将 evidence_refs 统一为 source_refs；兼容历史持久化回看。
                source_refs = card_payload.get("source_refs") or card_payload.get("evidence_refs", [])
                if kind and kind != CanvasCardKind.EVIDENCE.value and status in {"effective", "decided", "clarified"}:
                    if not source_refs:
                        checks["source"] = "failed"
                        notes.append(f"稳定事实卡片 [{kind}] 缺少关联依据引用，无法确认生效。")

        # 3. 策略与越级检查：不能将新建的非稳定卡片直接越级标记为已确认或生效状态
        if mutation.target == CanvasMutationTarget.CARD and mutation.action.value == "add":
            card_payload = mutation.payload.get("card")
            if card_payload is not None:
                status = card_payload.get("status")
                if status in {"effective", "decided", "clarified", "formal"}:
                    mutation_type = mutation.metadata.get("mutation_type", "")
                    allowed_types = {
                        "confirm_constraint",
                        "resolve_clarification",
                        "resolve_critical_clarification",
                        "promote_formal_handoff",
                        "refresh_handoff_card",
                        "refresh_handoff_draft",
                    }
                    if mutation_type not in allowed_types:
                        checks["policy"] = "failed"
                        notes.append("不可直接将卡片设为已确认或生效状态，需经过必要的前置提案或澄清动作。")

        # 4. 冲突检查：如果试图修改已处于稳定治理地位的卡片核心内容，标记冲突
        if existing_cards and mutation.target == CanvasMutationTarget.CARD and mutation.action.value == "update":
            card_map = {c.card_id: c for c in existing_cards}
            orig_card = card_map.get(mutation.target_id)
            if orig_card and is_stable_status(orig_card.kind.value, orig_card.status):
                new_title = mutation.payload.get("title")
                new_summary = mutation.payload.get("summary")
                title_changed = new_title is not None and new_title.strip() != orig_card.title.strip()
                summary_changed = new_summary is not None and new_summary.strip() != orig_card.summary.strip()
                if title_changed or summary_changed:
                    checks["conflict"] = "failed"
                    notes.append(f"正在更新已确认的稳定事实卡片 [{orig_card.card_id}]，存在边界冲突，需进入待复核路径。")

    # 5. 角色权限越权检测
    roles = set(proposal.metadata.get("roles", []))
    # L3 规格已下线 OptionBuilder 角色；此处只保留收敛者职责边界判定。
    divergent_roles = {"InputCompiler", "Clarifier"}
    convergent_roles = {"ConstraintSteward", "DecisionSteward"}
    
    if roles:
        # 发散者权限越界检测
        if roles.issubset(divergent_roles):
            for mutation in proposal.mutations:
                mutation_type = mutation.metadata.get("mutation_type", "")
                status = mutation.payload.get("status")
                if mutation.payload.get("card") is not None:
                    status = status or mutation.payload["card"].get("status")
                
                is_resolve = mutation_type in {"resolve_clarification", "resolve_critical_clarification"} or status in {"clarified", "decided", "effective", "formal"}
                is_handoff_publish = mutation.target == CanvasMutationTarget.HANDOFF or mutation_type == "promote_formal_handoff"
                
                if is_resolve or is_handoff_publish:
                    checks["policy"] = "failed"
                    notes.append(f"角色权限越界：发散者角色 {list(roles)} 无权确认生效或发布交接物。")
                    break
        
        # 收敛者权限越界检测
        elif roles.issubset(convergent_roles):
            for mutation in proposal.mutations:
                status = mutation.payload.get("status")
                if mutation.payload.get("card") is not None:
                    status = status or mutation.payload["card"].get("status")
                mutation_type = mutation.metadata.get("mutation_type", "")
                
                if status in {"clarified", "decided", "effective"}:
                    if mutation_type not in {"confirm_constraint", "resolve_clarification"}:
                        checks["policy"] = "failed"
                        notes.append(f"角色权限越界：收敛者角色 {list(roles)} 无法直接让提案生效，需经必要确认。")
                        break

    # 6. 正式交接物发布占比与污染门禁
    is_formal_handoff = False
    for mutation in proposal.mutations:
        mutation_type = mutation.metadata.get("mutation_type", "")
        status = mutation.payload.get("status")
        if mutation.payload.get("handoff") is not None:
            status = status or mutation.payload["handoff"].get("status")
        if mutation_type == "promote_formal_handoff" or (mutation.target == CanvasMutationTarget.HANDOFF and status in {"formal", "confirmed"}):
            is_formal_handoff = True
            break

    if is_formal_handoff and existing_cards:
        main_kinds = {CanvasCardKind.CONSTRAINT, CanvasCardKind.DECISION, CanvasCardKind.CLARIFICATION}
        main_cards = [c for c in existing_cards if c.kind in main_kinds]
        unconfirmed_cards = [
            c
            for c in main_cards
            if not is_stable_status(c.kind.value, c.status) and c.status != "superseded"
        ]
        
        if main_cards:
            ratio = len(unconfirmed_cards) / len(main_cards)
            if ratio > (1.0 / 3.0):
                checks["policy"] = "failed"
                notes.append(f"交接物门禁拦截：高置信未确认内容占比 ({ratio:.1%}) 超过三分之一限制，无法发布正式交接物。")

    if "handoff" in str(intent) and not any(
        mutation.target == CanvasMutationTarget.HANDOFF for mutation in proposal.mutations
    ):
        checks["policy"] = "failed"
        notes.append("交接意图缺少交接物 mutation。")

    # 7. 独立评估 (Independent Evaluation)
    if is_formal_handoff and existing_cards:
        # 检查是否有关联卡片处于“复核状态”
        under_review_cards = [
            c for c in existing_cards if c.validation_state in {"warning", "invalid"}
        ]
        if under_review_cards:
            checks["evaluation"] = "failed"
            notes.append(
                f"独立评估拦截：存在高概率失真或待复核的卡片依赖 {[c.card_id for c in under_review_cards]}，无法通过独立评估。"
            )

    # 8. 依据来源摘要 (source_summary) 生成
    mut_targets = [
        f"{m.target.value if hasattr(m.target, 'value') else str(m.target)}:{m.target_id or 'new'}"
        for m in proposal.mutations
    ]
    source_summary = (
        f"验证依据：提案 [{proposal.proposal_id}] 对 "
        + ", ".join(mut_targets)
        + f" 进行了 {len(proposal.mutations)} 项变更。"
    )

    # 9. 动态推导建议分流去向 (recommendation)
    result = "passed" if all(value == "passed" for value in checks.values()) else "failed"
    if result == "failed":
        if checks["structure"] == "failed" or checks["source"] == "failed":
            recommendation = "downgrade_to_proposal"
        else:
            recommendation = "awaiting_clarification"
    else:
        # 通过验证时，根据风险度决定
        is_high_risk = is_formal_handoff or "snapshot" in str(intent)
        for m in proposal.mutations:
            if m.metadata.get("mutation_type") in {
                "confirm_constraint",
                "resolve_clarification",
                "promote_formal_handoff",
            }:
                is_high_risk = True
        recommendation = "awaiting_chat_confirmation" if is_high_risk else "auto_apply"

    receipt_obj = CanvasVerificationReceipt(
        result=result,
        checks=checks,
        notes=notes,
        source_summary=source_summary[:200],
        recommendation=recommendation,
    )
    return receipt_obj.to_dict()

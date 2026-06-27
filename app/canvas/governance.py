"""EvoCanvas 画布变更治理。

该模块负责把 mutation proposal 分类为自动应用或待确认，
以满足 1.0 的“低风险自动写入，高影响动作必须确认”规则。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.canvas.domain.cards import CanvasCard
from app.canvas.domain.mutations import CanvasMutationProposal, CanvasMutationStatus, CanvasMutationTarget, MutationRiskLevel


@dataclass(frozen=True)
class GovernanceOutcome:
    """描述提案经过治理后的处理结果。"""

    action: str
    risk_level: MutationRiskLevel


class MutationGovernance:
    """根据 EvoCanvas 1.0 治理规则对提案进行分类。"""

    HIGH_RISK_MUTATION_TYPES = {
        "confirm_constraint",
        "resolve_clarification",
        "create_decision_request",
        "create_snapshot",
        "promote_formal_handoff",
    }
    HIGH_RISK_STATUSES = {"effective", "confirmed", "resolved", "formal"}
    HIGH_RISK_TARGETS = {CanvasMutationTarget.SNAPSHOT}

    def __init__(self, repository=None) -> None:
        self.repository = repository

    MEDIUM_RISK_MUTATION_TYPES = {
        "create_constraint_candidate",
        "create_decision_candidate",
        "merge_problems",
        "refresh_handoff_draft",
        "refresh_handoff_card",
    }

    def classify(
        self,
        proposal: CanvasMutationProposal,
        existing_cards: list[CanvasCard] | None = None,
    ) -> GovernanceOutcome:
        """返回提案处理方式，并同步标记提案风险等级。"""

        from app.canvas.domain.cards import CanvasCardKind

        # 1. 结合验证回执处理验证失败情况
        receipt = proposal.metadata.get("verification_receipt", {})
        if receipt.get("result") == "failed":
            action = receipt.get("recommendation") or "downgrade_to_proposal"
            rollback_hint = "compilation" if action == "downgrade_to_proposal" else "clarification"
            proposal.status = CanvasMutationStatus.PROPOSED
            proposal.risk_level = MutationRiskLevel.HIGH
            proposal.metadata["rollback_hint"] = rollback_hint
            return GovernanceOutcome(action=action, risk_level=MutationRiskLevel.HIGH)

        # 2. 精细化计算提案风险等级
        max_risk = MutationRiskLevel.LOW
        for mutation in proposal.mutations:
            risk = self._evaluate_mutation_risk(mutation, existing_cards)
            if risk == MutationRiskLevel.HIGH:
                max_risk = MutationRiskLevel.HIGH
                break
            elif risk == MutationRiskLevel.MEDIUM:
                max_risk = MutationRiskLevel.MEDIUM

        proposal.risk_level = max_risk

        # 3. 针对验证通过的分类动作决定
        if max_risk == MutationRiskLevel.HIGH:
            proposal.status = CanvasMutationStatus.PENDING_CONFIRMATION
            proposal.metadata["gate_reason"] = self._gate_reason_for(proposal)
            self._enqueue_confirmation(proposal)
            return GovernanceOutcome(action="pending_confirmation", risk_level=MutationRiskLevel.HIGH)

        proposal.status = CanvasMutationStatus.APPLIED
        proposal.metadata["gate_reason"] = ""
        return GovernanceOutcome(action="auto_apply", risk_level=max_risk)

    def _evaluate_mutation_risk(
        self,
        mutation,
        existing_cards: list[CanvasCard] | None = None,
    ) -> MutationRiskLevel:
        """评估单条变更的风险级别。"""

        from app.canvas.domain.cards import CanvasCardKind

        # 检查高风险
        mutation_type = str(mutation.metadata.get("mutation_type", ""))
        status = str(mutation.payload.get("status", ""))
        card_payload = mutation.payload.get("card")
        if card_payload is not None:
            status = status or str(card_payload.get("status", ""))

        is_high = bool(
            mutation.requires_confirmation
            or mutation.target in self.HIGH_RISK_TARGETS
            or mutation_type in self.HIGH_RISK_MUTATION_TYPES
            or status in self.HIGH_RISK_STATUSES
        )

        # 检查是否修改了已确认卡片核心字段（高风险冲突）
        if not is_high and existing_cards and mutation.target == CanvasMutationTarget.CARD and mutation.action.value == "update":
            card_map = {c.card_id: c for c in existing_cards}
            orig_card = card_map.get(mutation.target_id)
            if orig_card and orig_card.status in {"confirmed", "effective", "resolved"}:
                new_title = mutation.payload.get("title")
                new_summary = mutation.payload.get("summary")
                if (new_title is not None and new_title.strip() != orig_card.title.strip()) or \
                   (new_summary is not None and new_summary.strip() != orig_card.summary.strip()):
                    is_high = True

        if is_high:
            return MutationRiskLevel.HIGH

        # 检查中风险
        kind = None
        if card_payload is not None:
            kind = card_payload.get("kind")

        is_medium = bool(
            mutation_type in self.MEDIUM_RISK_MUTATION_TYPES
            or (mutation.target == CanvasMutationTarget.CARD and mutation.action.value == "add" and kind in {CanvasCardKind.CONSTRAINT.value, CanvasCardKind.DECISION.value})
            or (mutation.target == CanvasMutationTarget.CARD and mutation.action.value == "update" and mutation_type in {"update_constraint", "update_decision"})
        )
        if is_medium:
            return MutationRiskLevel.MEDIUM

        return MutationRiskLevel.LOW

    def _enqueue_confirmation(self, proposal: CanvasMutationProposal) -> None:
        if self.repository is None:
            return
        queue = self.repository.load_confirmation_queue(proposal.workspace_id)
        if not any(item.proposal_id == proposal.proposal_id for item in queue):
            queue.append(proposal)
        self.repository.save_confirmation_queue(proposal.workspace_id, queue)

    @staticmethod
    def _gate_reason_for(proposal: CanvasMutationProposal) -> str:
        for mutation in proposal.mutations:
            mutation_type = str(mutation.metadata.get("mutation_type", ""))
            if mutation_type == "promote_formal_handoff":
                return "handoff_publish"
            if mutation.target == CanvasMutationTarget.SNAPSHOT or mutation_type == "create_snapshot":
                return "snapshot_publish"
        return "fact_boundary_change"

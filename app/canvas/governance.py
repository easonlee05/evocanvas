"""EvoCanvas 画布变更治理。

该模块负责把 mutation proposal 分类为自动应用或待确认，
以满足 1.0 的“低风险自动写入，高影响动作必须确认”规则。
"""

from __future__ import annotations

from dataclasses import dataclass

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

    def classify(self, proposal: CanvasMutationProposal) -> GovernanceOutcome:
        """返回提案处理方式，并同步标记提案风险等级。"""

        if any(self._is_high_risk_mutation(mutation) for mutation in proposal.mutations):
            proposal.risk_level = MutationRiskLevel.HIGH
            proposal.status = CanvasMutationStatus.PENDING_CONFIRMATION
            proposal.metadata["gate_reason"] = self._gate_reason_for(proposal)
            self._enqueue_confirmation(proposal)
            return GovernanceOutcome(action="pending_confirmation", risk_level=MutationRiskLevel.HIGH)

        proposal.risk_level = MutationRiskLevel.LOW
        proposal.status = CanvasMutationStatus.APPLIED
        proposal.metadata["gate_reason"] = ""
        return GovernanceOutcome(action="auto_apply", risk_level=MutationRiskLevel.LOW)

    def _is_high_risk_mutation(self, mutation) -> bool:
        mutation_type = str(mutation.metadata.get("mutation_type", ""))
        status = str(mutation.payload.get("status", ""))
        return bool(
            mutation.requires_confirmation
            or mutation.target in self.HIGH_RISK_TARGETS
            or mutation_type in self.HIGH_RISK_MUTATION_TYPES
            or status in self.HIGH_RISK_STATUSES
        )

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

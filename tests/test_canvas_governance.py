import json
import tempfile
import unittest
from pathlib import Path

from app.canvas.domain.cards import CanvasCard, CanvasCardKind
from app.canvas.domain.mutations import (
    CanvasMutation,
    CanvasMutationAction,
    CanvasMutationProposal,
    CanvasMutationStatus,
    CanvasMutationTarget,
    MutationRiskLevel,
)
from app.canvas.governance import MutationGovernance
from app.canvas.repository import CanvasRepository
from app.services.fakes import FakeStorage


class CanvasGovernanceTests(unittest.TestCase):
    def test_marks_confirmation_for_high_impact_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = CanvasRepository(FakeStorage(Path(tmpdir)))
            governance = MutationGovernance(repository=repository)
            proposal = CanvasMutationProposal(
                proposal_id="proposal_001",
                workspace_id="ws_demo",
                turn_id="turn_001",
                mutations=[
                    CanvasMutation(
                        mutation_id="mutation_001",
                        action=CanvasMutationAction.UPDATE,
                        target=CanvasMutationTarget.CARD,
                        target_id="card_001",
                        payload={"status": "effective"},
                        metadata={"mutation_type": "confirm_constraint"},
                    )
                ],
            )

            outcome = governance.classify(proposal)

            self.assertEqual(outcome.action, "pending_confirmation")
            self.assertEqual(outcome.risk_level, MutationRiskLevel.HIGH)
            self.assertEqual(proposal.risk_level, MutationRiskLevel.HIGH)
            self.assertEqual(proposal.status, CanvasMutationStatus.PENDING_CONFIRMATION)
            self.assertEqual(proposal.metadata["gate_reason"], "fact_boundary_change")
            self.assertEqual(
                [item.proposal_id for item in repository.load_confirmation_queue("ws_demo")],
                ["proposal_001"],
            )

    def test_auto_applies_low_risk_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = CanvasRepository(FakeStorage(Path(tmpdir)))
            governance = MutationGovernance(repository=repository)
            proposal = CanvasMutationProposal(
                proposal_id="proposal_002",
                workspace_id="ws_demo",
                turn_id="turn_002",
                mutations=[
                    CanvasMutation(
                        mutation_id="mutation_002",
                        action=CanvasMutationAction.ADD,
                        target=CanvasMutationTarget.CARD,
                        target_id="card_002",
                        payload={"title": "新增待澄清"},
                        metadata={"mutation_type": "add_card"},
                    )
                ],
            )

            outcome = governance.classify(proposal)

            self.assertEqual(outcome.action, "auto_apply")
            self.assertEqual(outcome.risk_level, MutationRiskLevel.LOW)
            self.assertEqual(proposal.risk_level, MutationRiskLevel.LOW)
            self.assertEqual(proposal.status, CanvasMutationStatus.APPLIED)
            self.assertEqual(repository.load_confirmation_queue("ws_demo"), [])

    def test_repository_persists_confirmation_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = CanvasRepository(FakeStorage(Path(tmpdir)))
            proposals = [
                CanvasMutationProposal(
                    proposal_id="proposal_003",
                    workspace_id="ws_demo",
                    turn_id="turn_003",
                )
            ]

            repository.save_confirmation_queue("ws_demo", proposals)

            queue_file = repository._workspace_dir("ws_demo") / "confirmation_queue.json"
            self.assertTrue(queue_file.exists())
            self.assertEqual(
                json.loads(queue_file.read_text(encoding="utf-8"))["items"][0]["proposal_id"],
                "proposal_003",
            )
            loaded = repository.load_confirmation_queue("ws_demo")
            self.assertEqual([proposal.proposal_id for proposal in loaded], ["proposal_003"])

    def test_governance_detects_medium_risk_mutation(self) -> None:
        governance = MutationGovernance()
        proposal = CanvasMutationProposal(
            proposal_id="proposal_m",
            workspace_id="ws_demo",
            turn_id="turn_m",
            mutations=[
                CanvasMutation(
                    mutation_id="mutation_m",
                    action=CanvasMutationAction.ADD,
                    target=CanvasMutationTarget.CARD,
                    target_id="card_m",
                    payload={"card": {"kind": "constraint", "status": "draft", "title": "约束候选"}},
                    metadata={"mutation_type": "create_constraint_candidate"},
                )
            ],
        )
        outcome = governance.classify(proposal)
        self.assertEqual(outcome.action, "auto_apply")
        self.assertEqual(outcome.risk_level, MutationRiskLevel.MEDIUM)

    def test_governance_detects_conflict_with_confirmed_card(self) -> None:
        governance = MutationGovernance()
        existing = [
            CanvasCard(
                card_id="card_001",
                kind=CanvasCardKind.CONSTRAINT,
                title="原有已确认约束",
                status="confirmed",
            )
        ]
        proposal = CanvasMutationProposal(
            proposal_id="proposal_c",
            workspace_id="ws_demo",
            turn_id="turn_c",
            mutations=[
                CanvasMutation(
                    mutation_id="mutation_c",
                    action=CanvasMutationAction.UPDATE,
                    target=CanvasMutationTarget.CARD,
                    target_id="card_001",
                    payload={"title": "修改后的约束"},
                )
            ],
        )
        outcome = governance.classify(proposal, existing_cards=existing)
        self.assertEqual(outcome.action, "pending_confirmation")
        self.assertEqual(outcome.risk_level, MutationRiskLevel.HIGH)

    def test_apply_proposal_handles_supersede_and_retention(self) -> None:
        from app.canvas.service import CanvasService
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = CanvasRepository(FakeStorage(Path(tmpdir)))
            service = CanvasService(storage=FakeStorage(Path(tmpdir)))
            service.repository = repository  # 覆盖为相同 repository 实例
            
            workspace = service.get_workspace("ws_demo")
            card = CanvasCard(
                card_id="card_orig",
                kind=CanvasCardKind.CONSTRAINT,
                title="原确认约束",
                status="confirmed",
            )
            repository.save_cards("ws_demo", [card])
            
            proposal = CanvasMutationProposal(
                proposal_id="prop_s",
                workspace_id="ws_demo",
                turn_id="turn_s",
                mutations=[
                    CanvasMutation(
                        mutation_id="mut_s",
                        action=CanvasMutationAction.UPDATE,
                        target=CanvasMutationTarget.CARD,
                        target_id="card_orig",
                        payload={"title": "更新后的约束内容"},
                    )
                ]
            )
            
            service._apply_proposal(workspace, proposal)
            
            updated_cards = repository.load_cards("ws_demo")
            self.assertEqual(len(updated_cards), 2)
            
            orig_card = next(c for c in updated_cards if c.card_id == "card_orig")
            new_card = next(c for c in updated_cards if c.card_id != "card_orig")
            
            self.assertEqual(orig_card.status, "superseded")
            self.assertEqual(orig_card.metadata["superseded_by"], new_card.card_id)
            self.assertEqual(new_card.status, "confirmed")
            self.assertEqual(new_card.title, "更新后的约束内容")
            self.assertEqual(new_card.metadata["supersedes"], "card_orig")
            
            relations = repository.load_relations("ws_demo")
            self.assertEqual(len(relations), 1)
            self.assertEqual(relations[0].kind.value, "derived_from")
            self.assertEqual(relations[0].from_card_id, "card_orig")
            self.assertEqual(relations[0].to_card_id, new_card.card_id)

    def test_divergent_role_blocked_from_publishing_handoff(self) -> None:
        from app.canvas.verification import verify_mutation_proposal
        proposal = CanvasMutationProposal(
            proposal_id="proposal_v",
            workspace_id="ws_demo",
            turn_id="turn_v",
            mutations=[
                CanvasMutation(
                    mutation_id="mutation_v",
                    action=CanvasMutationAction.UPDATE,
                    target=CanvasMutationTarget.HANDOFF,
                    target_id="handoff_01",
                    payload={"handoff": {"handoff_id": "handoff_01", "status": "formal"}},
                    metadata={"mutation_type": "promote_formal_handoff"},
                )
            ],
            metadata={"roles": ["Clarifier"]}  # 发散者角色
        )
        receipt = verify_mutation_proposal(proposal, intent="handoff")
        self.assertEqual(receipt["result"], "failed")
        self.assertEqual(receipt["checks"]["policy"], "failed")
        
        proposal.metadata["verification_receipt"] = receipt
        governance = MutationGovernance()
        outcome = governance.classify(proposal)
        self.assertEqual(outcome.action, "awaiting_clarification")

    def test_formal_handoff_blocked_due_to_high_unconfirmed_ratio(self) -> None:
        from app.canvas.verification import verify_mutation_proposal
        existing = [
            CanvasCard(card_id="card_c1", kind=CanvasCardKind.CONSTRAINT, title="约束1", status="draft"),
            CanvasCard(card_id="card_c2", kind=CanvasCardKind.CONSTRAINT, title="约束2", status="draft"),
            CanvasCard(card_id="card_d1", kind=CanvasCardKind.DECISION, title="决策1", status="confirmed"),
        ]
        
        proposal = CanvasMutationProposal(
            proposal_id="proposal_h",
            workspace_id="ws_demo",
            turn_id="turn_h",
            mutations=[
                CanvasMutation(
                    mutation_id="mutation_h",
                    action=CanvasMutationAction.UPDATE,
                    target=CanvasMutationTarget.HANDOFF,
                    target_id="handoff_01",
                    payload={"handoff": {"handoff_id": "handoff_01", "status": "formal"}},
                    metadata={"mutation_type": "promote_formal_handoff"},
                )
            ],
            metadata={"roles": ["HandoffBuilder"]}
        )
        
        receipt = verify_mutation_proposal(proposal, intent="handoff", existing_cards=existing)
        self.assertEqual(receipt["result"], "failed")
        self.assertEqual(receipt["checks"]["policy"], "failed")
        self.assertTrue(any("交接物门禁拦截" in note for note in receipt["notes"]))
        
        proposal.metadata["verification_receipt"] = receipt
        governance = MutationGovernance()
        outcome = governance.classify(proposal, existing_cards=existing)
        self.assertEqual(outcome.action, "awaiting_clarification")


if __name__ == "__main__":
    unittest.main()

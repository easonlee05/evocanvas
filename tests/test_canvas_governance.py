import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()

import unittest
from app.canvas.domain.cards import CanvasCard, CanvasCardKind
from app.canvas.domain.mutations import (
    CanvasMutation,
    CanvasMutationAction,
    CanvasMutationProposal,
    CanvasMutationStatus,
    CanvasMutationTarget,
)
from app.canvas.verification import verify_mutation_proposal
from app.canvas.governance import MutationGovernance


class CanvasVerificationTests(unittest.TestCase):
    def test_structured_verification_receipt_generation(self) -> None:
        """验证 verify_mutation_proposal 正确返回结构化验证回执。"""

        proposal = CanvasMutationProposal(
            proposal_id="proposal_v",
            workspace_id="ws_demo",
            turn_id="turn_v",
            mutations=[
                CanvasMutation(
                    mutation_id="mut_1",
                    action=CanvasMutationAction.ADD,
                    target=CanvasMutationTarget.CARD,
                    target_id="card_new",
                    payload={"card": {"card_id": "card_new", "kind": "constraint", "title": "新约束", "summary": "依据充分", "status": "draft"}},
                )
            ]
        )

        receipt = verify_mutation_proposal(proposal, intent="constraint")

        # 校验回执字段
        self.assertEqual(receipt["result"], "passed")
        self.assertEqual(receipt["checks"]["evaluation"], "passed")
        self.assertIn("验证依据：提案 [proposal_v]", receipt["source_summary"])
        # 没有确认操作，属于中低风险，建议去向为 auto_apply
        self.assertEqual(receipt["recommendation"], "auto_apply")

    def test_independent_evaluation_intercepts_on_under_review_cards(self) -> None:
        """验证独立评估 (Independent Evaluation) 拦截：当发布正式交接物时，若其依赖有 under_review (复核中) 卡片，则评估失败。"""

        # 存在一个复核中的卡片
        existing = [
            CanvasCard(
                card_id="card_c1",
                kind=CanvasCardKind.CONSTRAINT,
                title="复核中的约束",
                status="effective",
                validation_state="warning",
            )
        ]

        # 发布正式交接物提案
        proposal = proposal = CanvasMutationProposal(
            proposal_id="proposal_e",
            workspace_id="ws_demo",
            turn_id="turn_e",
            mutations=[
                CanvasMutation(
                    mutation_id="mut_e",
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
        self.assertEqual(receipt["checks"]["evaluation"], "failed")
        self.assertTrue(any("独立评估拦截" in note for note in receipt["notes"]))
        self.assertEqual(receipt["recommendation"], "awaiting_clarification")

    def test_governance_consumes_recommendation_and_sets_rollback(self) -> None:
        """验证 G层与V层契约解耦：治理分类直接使用回执中的 recommendation 并推导 rollback_hint。"""

        governance = MutationGovernance()

        # 模拟结构验证失败回执 (推荐 downgrade_to_proposal)
        proposal_a = CanvasMutationProposal(
            proposal_id="proposal_a",
            workspace_id="ws_demo",
            turn_id="turn_a",
            mutations=[]
        )
        proposal_a.metadata["verification_receipt"] = {
            "result": "failed",
            "recommendation": "downgrade_to_proposal"
        }

        outcome_a = governance.classify(proposal_a)
        self.assertEqual(outcome_a.action, "downgrade_to_proposal")
        self.assertEqual(proposal_a.metadata["rollback_hint"], "compilation")

        # 模拟策略验证失败回执 (推荐 awaiting_clarification)
        proposal_b = CanvasMutationProposal(
            proposal_id="proposal_b",
            workspace_id="ws_demo",
            turn_id="turn_b",
            mutations=[]
        )
        proposal_b.metadata["verification_receipt"] = {
            "result": "failed",
            "recommendation": "awaiting_clarification"
        }

        outcome_b = governance.classify(proposal_b)
        self.assertEqual(outcome_b.action, "awaiting_clarification")
        self.assertEqual(proposal_b.metadata["rollback_hint"], "clarification")


if __name__ == "__main__":
    unittest.main()

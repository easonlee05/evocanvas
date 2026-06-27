import unittest
from app.canvas.domain.cards import CanvasCard, CanvasCardKind
from app.canvas.domain.mutations import (
    CanvasMutation,
    CanvasMutationAction,
    CanvasMutationProposal,
    CanvasMutationStatus,
    CanvasMutationTarget,
)
from app.canvas.domain.workspace import CanvasWorkspace
from app.canvas.runtime_state import apply_turn_runtime_state, build_state_ledger


class CanvasLifecycleTests(unittest.TestCase):
    def test_enforces_adjacent_stage_rollback_limit(self) -> None:
        """验证相邻阶段回流校验保护算法：不允许跨两级及以上的非法回滚，强行修正为相邻前序段。"""

        # 初始在 handoff 阶段
        workspace = CanvasWorkspace(
            workspace_id="ws_test",
            title="测试项目",
        )
        workspace.metadata = {
            "lifecycle": {
                "stage_node": "handoff",
                "checkpoint": "applied",
                "pending_gate_ids": [],
                "unresolved_issue_ids": [],
                "transition_history": [],
            }
        }

        # 试图直接回滚到 compilation 阶段 (跨越了 convergence 和 clarification)
        proposal = CanvasMutationProposal(
            proposal_id="proposal_rollback",
            workspace_id="ws_test",
            turn_id="turn_rb",
        )
        proposal.metadata["rollback_hint"] = "compilation"

        # 回写状态，result_action 为验证失败
        updated_ws = apply_turn_runtime_state(
            workspace,
            intent="compilation",
            proposal=proposal,
            result_action="downgrade_to_proposal",
        )

        lifecycle = updated_ws.metadata["lifecycle"]
        # 应该被拦截并限制在相邻的前序阶段 (即 convergence)
        self.assertEqual(lifecycle["stage_node"], "convergence")
        self.assertEqual(lifecycle["checkpoint"], "fallback_to_proposal")

        # 历史记录检查
        history = lifecycle["transition_history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["from_stage"], "handoff")
        self.assertEqual(history[0]["to_stage"], "convergence")
        self.assertEqual(history[0]["action_type"], "rollback")
        self.assertEqual(history[0]["reason_category"], "verification_failed")

    def test_state_ledger_blocked_and_non_blocking_classification(self) -> None:
        """验证状态账本的阻塞卡片、非阻塞提醒和下一步 hint。"""

        workspace = CanvasWorkspace(
            workspace_id="ws_test",
            title="测试项目",
        )
        workspace.metadata = {
            "lifecycle": {
                "stage_node": "convergence",
                "checkpoint": "applied",
            }
        }

        # 1. 存在 open 的决策，作为阻塞卡片
        # 2. 存在 superseded 的约束卡片，作为非阻塞提醒
        cards = [
            CanvasCard(
                card_id="card_dec",
                kind=CanvasCardKind.DECISION,
                title="待决策",
                status="pending",
            ),
            CanvasCard(
                card_id="card_old",
                kind=CanvasCardKind.CONSTRAINT,
                title="老约束",
                status="superseded",
            ),
        ]

        proposal = CanvasMutationProposal(
            proposal_id="prop_01",
            workspace_id="ws_test",
            turn_id="turn_01",
        )

        ledger = build_state_ledger(workspace, cards, proposal, "auto_apply")

        self.assertEqual(ledger["stage_node"], "convergence")
        self.assertEqual(ledger["next_progression_hint"], "handoff")
        self.assertEqual(ledger["blocked_by_card_ids"], ["card_dec"])
        self.assertEqual(len(ledger["non_blocking_reminders"]), 1)
        self.assertEqual(ledger["non_blocking_reminders"][0]["card_id"], "card_old")
        self.assertEqual(ledger["non_blocking_reminders"][0]["reason"], "已失效被替代")

    def test_stage_conclusion_leading_card_extraction(self) -> None:
        """验证阶段结论（主判断）根据卡片稳定程度动态挑选。"""

        workspace = CanvasWorkspace(
            workspace_id="ws_test",
            title="测试项目",
        )
        workspace.metadata = {
            "lifecycle": {
                "stage_node": "convergence",
            }
        }

        # 场景 A：只有未确认的约束卡片
        cards_unconfirmed = [
            CanvasCard(
                card_id="card_c1",
                kind=CanvasCardKind.CONSTRAINT,
                title="约束草稿",
                summary="内容1",
                status="draft",
            )
        ]
        proposal = CanvasMutationProposal(
            proposal_id="prop_01", workspace_id="ws_test", turn_id="turn_01"
        )
        ledger_a = build_state_ledger(workspace, cards_unconfirmed, proposal, "auto_apply")
        conclusion_a = ledger_a["stage_conclusion"]
        self.assertEqual(conclusion_a["card_id"], "card_c1")
        self.assertEqual(conclusion_a["is_confirmed"], False)

        # 场景 B：存在已确认的约束卡片，优先提取
        cards_confirmed = [
            CanvasCard(
                card_id="card_c1",
                kind=CanvasCardKind.CONSTRAINT,
                title="约束草稿",
                summary="内容1",
                status="draft",
            ),
            CanvasCard(
                card_id="card_c2",
                kind=CanvasCardKind.CONSTRAINT,
                title="已拍板约束",
                summary="确认内容",
                status="confirmed",
            ),
        ]
        ledger_b = build_state_ledger(workspace, cards_confirmed, proposal, "auto_apply")
        conclusion_b = ledger_b["stage_conclusion"]
        self.assertEqual(conclusion_b["card_id"], "card_c2")
        self.assertEqual(conclusion_b["is_confirmed"], True)
        self.assertEqual(conclusion_b["lead_reason"], "上位事实边界")


if __name__ == "__main__":
    unittest.main()

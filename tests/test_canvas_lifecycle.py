"""L3 规格下的运行时状态与账本事件辅助测试。

旧版基于 stage_node / checkpoint / transition_history / build_state_ledger
的测试已整体废弃：L3 规格下线主题阶段机后，运行时状态只保留与 active_turn
相关的最小占位，真正的事实变化通过 append_ledger_event 追加账本事件记录。

参见 docs/harness/02-memory-state/02 State Ledger（状态账本）.md
与 docs/harness/04-orchestration-lifecycle/02 Lifecycle（生命周期）.md。
"""

import unittest

from app.canvas.domain.cards import CanvasCard, CanvasCardKind
from app.canvas.domain.object_status import (
    GovernanceClass,
    ValidationState,
    derive_governance_class,
    is_unresolved_status,
)
from app.canvas.runtime_state import (
    build_handoff_metadata,
    make_object_created_event,
    make_object_status_changed_event,
    unresolved_issue_ids_from_cards,
)


class CanvasLifecycleTests(unittest.TestCase):
    def test_unresolved_issue_ids_derived_from_typed_status(self) -> None:
        """验证未决对象 ID 从类型化状态派生，不再依赖旧 stage_node。"""

        cards = [
            CanvasCard(
                card_id="card_dec_pending",
                kind=CanvasCardKind.DECISION,
                title="待决策",
                status="pending_decision",
            ),
            CanvasCard(
                card_id="card_dec_decided",
                kind=CanvasCardKind.DECISION,
                title="已拍板决策",
                status="decided",
            ),
            CanvasCard(
                card_id="card_clarify_open",
                kind=CanvasCardKind.CLARIFICATION,
                title="开放澄清",
                status="open",
            ),
            CanvasCard(
                card_id="card_clarify_closed",
                kind=CanvasCardKind.CLARIFICATION,
                title="已关闭澄清",
                status="closed",
            ),
        ]

        unresolved = unresolved_issue_ids_from_cards(cards)

        # pending_decision / open 视为未决；decided / closed 不计入。
        self.assertIn("card_dec_pending", unresolved)
        self.assertIn("card_clarify_open", unresolved)
        self.assertNotIn("card_dec_decided", unresolved)
        self.assertNotIn("card_clarify_closed", unresolved)

    def test_governance_class_derived_from_kind_and_status(self) -> None:
        """验证通用治理地位由 (kind, status) 派生，不依赖独立写入。"""

        # 源（source）：evidence 默认 collected/cited/archived
        self.assertEqual(
            derive_governance_class("evidence", "collected"),
            GovernanceClass.SOURCE,
        )
        # 未决（unresolved）：clarification 的 open/blocked
        self.assertEqual(
            derive_governance_class("clarification", "open"),
            GovernanceClass.UNRESOLVED,
        )
        # 稳定（stable）：constraint 的 effective
        self.assertEqual(
            derive_governance_class("constraint", "effective"),
            GovernanceClass.STABLE,
        )
        # 历史（historical）：constraint 的 archived
        self.assertEqual(
            derive_governance_class("constraint", "archived"),
            GovernanceClass.HISTORICAL,
        )

    def test_handoff_metadata_counts_unresolved_and_high_confidence(self) -> None:
        """验证交接物元数据派生未决计数与高置信未确认计数。"""

        cards = [
            CanvasCard(
                card_id="card_clarify_open_valid",
                kind=CanvasCardKind.CLARIFICATION,
                title="开放且已验证",
                status="open",
                validation_state=ValidationState.VALID.value,
            ),
            CanvasCard(
                card_id="card_clarify_open_warning",
                kind=CanvasCardKind.CLARIFICATION,
                title="开放但有警告",
                status="open",
                validation_state=ValidationState.WARNING.value,
            ),
            CanvasCard(
                card_id="card_decided",
                kind=CanvasCardKind.DECISION,
                title="已拍板",
                status="decided",
                validation_state=ValidationState.VALID.value,
            ),
        ]

        metadata = build_handoff_metadata(
            cards,
            confirmation_state="draft",
            source_snapshot_id="snapshot-1",
            refreshed_by="user",
            refreshed_at="2026-07-14T10:00:00Z",
        )

        # 两个未决（open + open），其中两个都是 valid/warning → 高置信未确认 = 2
        self.assertEqual(metadata["unresolved_count"], 2)
        self.assertEqual(metadata["high_confidence_unconfirmed_count"], 2)
        self.assertEqual(metadata["generated_from_card_count"], 3)
        self.assertEqual(metadata["confirmation_state"], "draft")

    def test_make_object_created_event_carries_required_fields(self) -> None:
        """验证账本事件构造辅助产出符合 L3 规格的事件结构。"""

        event = make_object_created_event(
            ledger_event_id="evt-1",
            workspace_id="ws-1",
            package_id="pkg-1",
            object_id="card-1",
            object_type="clarification",
            operation_id="op-1",
            occurred_at="2026-07-14T10:00:00Z",
            state_version_before=0,
            state_version_after=1,
            chat_turn_id="turn-1",
            source_refs=["input:meeting-1"],
        )

        self.assertEqual(event.event_type.value, "object_created")
        self.assertEqual(event.entity_id, "card-1")
        self.assertEqual(event.entity_type, "clarification")
        self.assertEqual(event.operation_id, "op-1")
        self.assertEqual(event.state_version_before, 0)
        self.assertEqual(event.state_version_after, 1)
        self.assertEqual(event.source_refs, ["input:meeting-1"])
        self.assertEqual(event.chat_turn_id, "turn-1")

    def test_make_object_status_changed_event_carries_confirmation_id(self) -> None:
        """验证状态变更事件可携带 confirmation_id，支撑确认留痕。"""

        event = make_object_status_changed_event(
            ledger_event_id="evt-2",
            workspace_id="ws-1",
            package_id="pkg-1",
            object_id="card-dec-1",
            object_type="decision",
            before_status="pending_decision",
            after_status="decided",
            operation_id="op-2",
            occurred_at="2026-07-14T10:05:00Z",
            confirmation_id="conf-1",
        )

        self.assertEqual(event.event_type.value, "object_status_changed")
        self.assertEqual(event.confirmation_id, "conf-1")
        self.assertEqual(event.entity_id, "card-dec-1")

    def test_is_unresolved_status_handles_compatibility_values(self) -> None:
        """验证 is_unresolved_status 对兼容状态值的判断。"""

        # 新类型化状态
        self.assertTrue(is_unresolved_status("clarification", "open"))
        self.assertTrue(is_unresolved_status("clarification", "blocked"))
        self.assertFalse(is_unresolved_status("clarification", "closed"))
        self.assertTrue(is_unresolved_status("decision", "pending_decision"))
        self.assertFalse(is_unresolved_status("decision", "decided"))
        # 历史状态值在映射表里缺失，回退到 WORKING，不计入未决。
        self.assertFalse(is_unresolved_status("clarification", "compatibility_unknown"))


if __name__ == "__main__":
    unittest.main()

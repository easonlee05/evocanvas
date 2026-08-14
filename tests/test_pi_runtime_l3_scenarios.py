"""Pi Runtime 阶段 0 的 L3 失败恢复与幂等语义 fixture。

阶段 1 的运行器尚未落地，本文件先把 L3 的不可越过边界冻结为只读 fixture：
fixture 表示 Product Kernel 在收到 Pi/提交器结果后应保留的事实与下一动作，
测试只断言禁止伪造回复、部分写入、盲目重试和权限升级。
"""

from __future__ import annotations

import unittest
from typing import Any


def _chat_failed_fixture() -> dict[str, Any]:
    return {
        "chat_turn": {
            "chat_turn_id": "turn-1",
            "status": "failed",
            "user_message_persisted": True,
            "assistant_message": None,
            "stream_fragments": ["我先帮你", "我先帮你梳理"],
            "stream_promoted_to_message": False,
            "convergence_judgement_created": False,
            "convergence_lease_held": False,
        },
        "retry": {
            "same_chat_turn_id": "turn-1",
            "parent_turn_id": None,
            "competing_assistant_messages": 0,
        },
    }


def _judgement_failed_fixture() -> dict[str, Any]:
    return {
        "judgement": {
            "judgement_id": "judgement-1",
            "status": "failed",
            "decision": None,
            "message_range": {"from_seq": 1, "through_seq": 4},
            "pending_rejudgement_through_seq": 4,
        },
        "convergence": {
            "scheduled": False,
            "default_decision_used": None,
            "run_id": None,
        },
    }


def _convergence_stale_fixture() -> dict[str, Any]:
    return {
        "convergence_run": {
            "convergence_run_id": "convergence-1",
            "technical_status": "stale",
            "business_result": None,
            "stale_reason": "base_version_changed",
            "proposal": {
                "proposal_id": "proposal-1",
                "base_state_version": 8,
                "base_package_version": 3,
                "operations": [{"operation_id": "operation-1"}],
            },
        },
        "commit": {
            "started": False,
            "operations_written": [],
            "package_version_before": 3,
            "package_version_after": 3,
        },
        "recovery": {
            "old_run_replayed": False,
            "latest_watermark_rejudgement": True,
        },
    }


def _unknown_commit_fixture() -> dict[str, Any]:
    return {
        "commit_attempt": {
            "operation_id": "operation-1",
            "status": "unknown",
            "attempt_count": 1,
        },
        "recovery": {
            "next_action": "query",
            "query_by": "operation_id",
            "query_operation_id": "operation-1",
            "queried": False,
            "replay_allowed_before_query": False,
            "new_operation_id": None,
        },
    }


def _not_ready_fixture() -> dict[str, Any]:
    return {
        "convergence_run": {
            "convergence_run_id": "convergence-2",
            "technical_status": "completed",
            "business_result": "not_ready",
            "reason_codes": ["insufficient_confirmation_scope"],
            "proposal": None,
            "technical_retry_count": 0,
        },
        "chat": {
            "assistant_messages_sent": 1,
            "second_assistant_message_sent": False,
            "followup_is_normal_user_chat": True,
        },
    }


def _tool_denied_fixture() -> dict[str, Any]:
    return {
        "tool_call": {
            "tool_call_id": "tool-call-1",
            "tool_name": "source.resolve",
            "status": "denied",
            "error_code": "tool_denied",
            "error_category": "permission_denied",
            "retryable": False,
            "attempt": 1,
        },
        "recovery": {
            "retry_count": 0,
            "permission_escalation_requested": False,
            "substituted_tool": None,
            "tool_scope_before": ["source.resolve"],
            "tool_scope_after": ["source.resolve"],
            "source_gap_recorded": True,
        },
    }


def _duplicate_operation_fixture() -> dict[str, Any]:
    return {
        "first_commit": {
            "operation_id": "operation-1",
            "status": "applied",
            "result_ref": "commit-result-1",
            "package_version_created": 4,
        },
        "retry_commit": {
            "operation_id": "operation-1",
            "status": "duplicate",
            "result_ref": "commit-result-1",
            "package_version_created": None,
            "returned_original_result": True,
        },
        "store": {"package_versions_created_for_operation": 1},
    }


class PiRuntimeL3ScenarioTests(unittest.TestCase):
    """把 Failure and Recovery L3 的硬门保持为可审查的最小场景。"""

    def test_chat_failure_does_not_fabricate_assistant_reply(self) -> None:
        fixture = _chat_failed_fixture()
        turn = fixture["chat_turn"]
        retry = fixture["retry"]

        self.assertEqual(turn["status"], "failed")
        self.assertTrue(turn["user_message_persisted"])
        self.assertIsNone(turn["assistant_message"])
        self.assertFalse(turn["stream_promoted_to_message"])
        self.assertFalse(turn["convergence_judgement_created"])
        self.assertFalse(turn["convergence_lease_held"])
        # 重试复用回合 ID，或至少明确父回合；这里选择复用，不能制造竞争回复。
        self.assertEqual(retry["same_chat_turn_id"], turn["chat_turn_id"])
        self.assertEqual(retry["competing_assistant_messages"], 0)

    def test_judgement_failure_does_not_default_to_trigger(self) -> None:
        fixture = _judgement_failed_fixture()
        judgement = fixture["judgement"]
        convergence = fixture["convergence"]

        self.assertEqual(judgement["status"], "failed")
        self.assertIsNone(judgement["decision"])
        self.assertEqual(judgement["pending_rejudgement_through_seq"], 4)
        self.assertFalse(convergence["scheduled"])
        self.assertIsNone(convergence["default_decision_used"])
        self.assertIsNone(convergence["run_id"])

    def test_stale_convergence_is_not_submitted_or_replayed(self) -> None:
        fixture = _convergence_stale_fixture()
        run = fixture["convergence_run"]
        commit = fixture["commit"]
        recovery = fixture["recovery"]

        self.assertEqual(run["technical_status"], "stale")
        self.assertEqual(run["stale_reason"], "base_version_changed")
        self.assertIsNone(run["business_result"])
        self.assertFalse(commit["started"])
        self.assertEqual(commit["operations_written"], [])
        self.assertEqual(commit["package_version_after"], commit["package_version_before"])
        self.assertFalse(recovery["old_run_replayed"])
        self.assertTrue(recovery["latest_watermark_rejudgement"])

    def test_unknown_commit_queries_by_operation_id_before_replay(self) -> None:
        fixture = _unknown_commit_fixture()
        attempt = fixture["commit_attempt"]
        recovery = fixture["recovery"]

        self.assertEqual(attempt["status"], "unknown")
        self.assertEqual(recovery["next_action"], "query")
        self.assertEqual(recovery["query_by"], "operation_id")
        self.assertEqual(recovery["query_operation_id"], attempt["operation_id"])
        self.assertFalse(recovery["queried"])
        self.assertFalse(recovery["replay_allowed_before_query"])
        self.assertIsNone(recovery["new_operation_id"])

    def test_not_ready_does_not_retry_or_send_second_assistant_message(self) -> None:
        fixture = _not_ready_fixture()
        run = fixture["convergence_run"]
        chat = fixture["chat"]

        self.assertEqual(run["technical_status"], "completed")
        self.assertEqual(run["business_result"], "not_ready")
        self.assertEqual(run["reason_codes"], ["insufficient_confirmation_scope"])
        self.assertIsNone(run["proposal"])
        self.assertEqual(run["technical_retry_count"], 0)
        self.assertEqual(chat["assistant_messages_sent"], 1)
        self.assertFalse(chat["second_assistant_message_sent"])
        self.assertTrue(chat["followup_is_normal_user_chat"])

    def test_tool_denied_does_not_escalate_permission_or_switch_tool(self) -> None:
        fixture = _tool_denied_fixture()
        call = fixture["tool_call"]
        recovery = fixture["recovery"]

        self.assertEqual(call["status"], "denied")
        self.assertEqual(call["error_code"], "tool_denied")
        self.assertEqual(call["error_category"], "permission_denied")
        self.assertFalse(call["retryable"])
        self.assertEqual(call["attempt"], 1)
        self.assertEqual(recovery["retry_count"], 0)
        self.assertFalse(recovery["permission_escalation_requested"])
        self.assertIsNone(recovery["substituted_tool"])
        self.assertEqual(recovery["tool_scope_before"], recovery["tool_scope_after"])
        self.assertTrue(recovery["source_gap_recorded"])

    def test_duplicate_operation_id_returns_original_result_without_new_version(self) -> None:
        fixture = _duplicate_operation_fixture()
        first = fixture["first_commit"]
        retry = fixture["retry_commit"]

        self.assertEqual(first["operation_id"], retry["operation_id"])
        self.assertEqual(first["status"], "applied")
        self.assertEqual(retry["status"], "duplicate")
        self.assertEqual(retry["result_ref"], first["result_ref"])
        self.assertTrue(retry["returned_original_result"])
        self.assertIsNone(retry["package_version_created"])
        self.assertEqual(fixture["store"]["package_versions_created_for_operation"], 1)


if __name__ == "__main__":
    unittest.main()

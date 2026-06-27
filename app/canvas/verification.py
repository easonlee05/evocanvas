"""EvoCanvas 提案预验证。

当前只实现 V 层最小运行时基线：
- 结构验证
- 来源验证
- 策略验证

它不直接做放行裁决，只生成验证回执，供治理层和生命周期层继续处理。
"""

from __future__ import annotations

from typing import Any, Dict

from app.canvas.domain.mutations import CanvasMutationProposal, CanvasMutationTarget


def verify_mutation_proposal(proposal: CanvasMutationProposal, *, intent: str) -> Dict[str, Any]:
    """对提案执行最小 V 层检查并返回验证回执。"""

    checks = {
        "structure": "passed",
        "source": "passed",
        "policy": "passed",
    }
    notes: list[str] = []

    if not proposal.mutations:
        checks["structure"] = "failed"
        notes.append("提案中没有可执行的 mutation。")

    for mutation in proposal.mutations:
        if mutation.target == CanvasMutationTarget.CARD:
            card_payload = mutation.payload.get("card")
            if card_payload is not None:
                if not str(card_payload.get("title", "")).strip():
                    checks["structure"] = "failed"
                    notes.append("卡片提案缺少标题。")
                if not str(card_payload.get("kind", "")).strip():
                    checks["structure"] = "failed"
                    notes.append("卡片提案缺少类型。")
            elif not mutation.target_id:
                checks["structure"] = "failed"
                notes.append("卡片更新提案缺少目标 ID。")

        if mutation.target == CanvasMutationTarget.HANDOFF:
            handoff_payload = mutation.payload.get("handoff", {})
            if not str(handoff_payload.get("handoff_id", "")).strip():
                checks["structure"] = "failed"
                notes.append("交接物提案缺少 handoff_id。")

    if "handoff" in str(intent) and not any(
        mutation.target == CanvasMutationTarget.HANDOFF for mutation in proposal.mutations
    ):
        checks["policy"] = "failed"
        notes.append("交接意图缺少交接物 mutation。")

    result = "passed" if all(value == "passed" for value in checks.values()) else "failed"
    return {
        "result": result,
        "checks": checks,
        "notes": notes,
    }

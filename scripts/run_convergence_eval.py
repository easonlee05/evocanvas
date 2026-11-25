#!/usr/bin/env python3
"""EvoCanvas 1.0 离线收敛评估基准（Harness Evaluation 最小闭环）。

验证四项核心反失真不变量：
1. 冲突来源显性化；
2. 未确认高风险写入/交接门禁拦截；
3. 稳定对象来源可追溯；
4. 交接物状态与过时边界一致性。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.canvas.domain import (
    CanvasMutation,
    CanvasMutationAction,
    CanvasMutationProposal,
    CanvasMutationTarget,
)
from app.canvas.repository import CanvasRepository
from app.canvas.service import CanvasService
from app.canvas.verification import verify_mutation_proposal
from app.services.fakes import FakeLLM, FakeStorage


def _make_service(tmp_dir: Path) -> CanvasService:
    storage = FakeStorage(tmp_dir)
    return CanvasService(storage=storage, llm=FakeLLM())


def _extract_card_id(result: Dict[str, object]) -> str:
    if isinstance(result.get("card"), dict):
        return str(result["card"].get("card_id") or "")
    return str(result.get("card_id") or result.get("id") or "")


def run_eval_case(case_id: str) -> Tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="evocanvas_eval_") as tmp:
        service = _make_service(Path(tmp))
        ws_id = f"ws_{case_id}"
        service.get_workspace(ws_id)

        if case_id == "eval_01_conflict_exposure":
            c1 = service.create_card(
                ws_id,
                kind="evidence",
                title="运营诉求：优惠券默认自动勾选",
                summary="提升转化率",
            )
            c1_id = _extract_card_id(c1)
            c2 = service.create_card(
                ws_id,
                kind="clarification",
                title="客服反馈误触率高与运营默认勾选冲突",
                summary="待明确默认态策略与防误触阈值",
                source_refs=[c1_id],
            )
            c2_id = _extract_card_id(c2)
            canvas = service.get_canvas_view(ws_id)
            kinds = {item["kind"] for item in canvas["cards"]}
            card_ids = {item["card_id"] for item in canvas["cards"]}
            ok = "evidence" in kinds and "clarification" in kinds and c2_id in card_ids
            return ok, f"cards={len(canvas['cards'])}, kinds={sorted(kinds)}"

        if case_id == "eval_02_confirmation_gate":
            proposal = CanvasMutationProposal(
                proposal_id="prop_eval_handoff",
                workspace_id=ws_id,
                turn_id="turn_eval_1",
                mutations=[
                    CanvasMutation(
                        mutation_id="mut_eval_handoff",
                        action=CanvasMutationAction.UPDATE,
                        target=CanvasMutationTarget.HANDOFF,
                        target_id="handoff_eval",
                        payload={"mutation_type": "promote_formal_handoff"},
                        rationale="尝试在无来源与未确认状态下晋升正式交接",
                        requires_confirmation=True,
                    )
                ],
            )
            receipt = verify_mutation_proposal(proposal, intent="promote_formal_handoff", existing_cards=[])
            verdict = str(receipt.get("result", ""))
            recommendation = str(receipt.get("recommendation", ""))
            notes = receipt.get("notes", [])
            return verdict != "passed", f"result={verdict}, recommendation={recommendation}, notes={notes}"

        if case_id == "eval_03_source_traceability":
            ev = service.create_card(
                ws_id,
                kind="evidence",
                title="技术评审纪要",
                summary="618 期间禁止修改结算核心接口",
            )
            ev_id = _extract_card_id(ev)
            con = service.create_card(
                ws_id,
                kind="constraint",
                title="结算核心接口零侵入",
                summary="所有改造限制在前端交互与外围配置层",
                source_refs=[ev_id],
            )
            con_id = _extract_card_id(con)
            cards = service.repository.load_cards(ws_id)
            target = next((c for c in cards if c.card_id == con_id), None)
            has_source = bool(target and ev_id in target.source_refs)
            return has_source, f"source_refs={target.source_refs if target else []}"

        if case_id == "eval_04_handoff_staleness":
            service.create_card(
                ws_id,
                kind="problem",
                title="活动页误触率偏高",
                summary="需要降低高价值券误领",
            )
            handoff = service.refresh_handoff(ws_id)
            status = str(handoff.get("status", ""))
            has_handoff = handoff.get("handoff") is not None
            return bool(status) and has_handoff, f"handoff_status={status}"

        return False, f"unknown case_id={case_id}"


def main() -> int:
    cases_path = Path(__file__).with_name("eval_cases.json")
    cases: List[Dict[str, object]] = json.loads(cases_path.read_text(encoding="utf-8"))
    passed_count = 0

    print("=== EvoCanvas 1.0 Convergence Evaluation ===")
    for case in cases:
        case_id = str(case["id"])
        ok, detail = run_eval_case(case_id)
        if ok:
            passed_count += 1
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {case_id} ({case['name']}) -> {detail}")

    total = len(cases)
    rate = (passed_count / total * 100.0) if total else 0.0
    print(f"=== Result: {passed_count}/{total} passed ({rate:.1f}%) ===")
    return 0 if passed_count == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

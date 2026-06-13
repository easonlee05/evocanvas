import unittest

from app.canvas.domain.cards import CanvasCard, CanvasCardKind
from app.canvas.domain.handoff import StructuredHandoff, TodoProjection
from app.canvas.domain.mutations import (
    CanvasMutationAction,
    CanvasMutationProposal,
    CanvasMutationTarget,
)
from app.canvas.domain.relations import CanvasRelation, CanvasRelationKind
from app.canvas.domain.snapshots import CanvasSnapshot
from app.canvas.domain.workspace import CanvasWorkspace


class CanvasDomainRoundtripTests(unittest.TestCase):
    def test_canvas_card_roundtrip(self) -> None:
        card = CanvasCard(
            card_id="card-1",
            kind=CanvasCardKind.CLARIFICATION,
            title="确认核心用户是谁",
            summary="现有输入同时提到产品经理和业务负责人，需要继续澄清主使用者。",
            stage="definition",
            status="open",
            tags=["user", "ambiguity"],
            evidence_refs=["input:meeting-1", "input:chat-2"],
            metadata={"priority": "high"},
        )

        data = card.to_dict()

        self.assertEqual(CanvasCard.from_dict(data), card)

    def test_canvas_relation_roundtrip(self) -> None:
        relation = CanvasRelation(
            relation_id="rel-1",
            kind=CanvasRelationKind.CLARIFIES,
            from_card_id="card-1",
            to_card_id="card-2",
            note="这条待澄清卡用于解释问题定义中的指代歧义。",
            metadata={"source": "assistant"},
        )

        data = relation.to_dict()

        self.assertEqual(CanvasRelation.from_dict(data), relation)

    def test_todo_projection_roundtrip(self) -> None:
        todo = TodoProjection(
            todo_id="todo-1",
            source_card_id="card-1",
            title="补充目标用户范围",
            status="open",
            reason="关键范围仍不稳定，无法进入结构化交接物。",
            assignee="pm",
            metadata={"lane": "active"},
        )

        data = todo.to_dict()

        self.assertEqual(TodoProjection.from_dict(data), todo)

    def test_canvas_mutation_roundtrip(self) -> None:
        mutation = CanvasMutationProposal(
            proposal_id="proposal-1",
            action=CanvasMutationAction.ADD,
            target=CanvasMutationTarget.CARD,
            target_id="card-3",
            payload={
                "kind": "constraint",
                "title": "首版不做多人实时协作",
            },
            rationale="根据首版范围冻结结果，需要把明确约束显性化到画布。",
            requires_confirmation=True,
            metadata={"origin": "assistant"},
        )

        data = mutation.to_dict()

        self.assertEqual(CanvasMutationProposal.from_dict(data), mutation)

    def test_canvas_snapshot_roundtrip(self) -> None:
        snapshot = CanvasSnapshot(
            snapshot_id="snapshot-1",
            workspace_id="workspace-1",
            title="首次输入编译后",
            summary="完成输入编译并显影第一批缺口。",
            created_at="2026-06-14T10:00:00+00:00",
            cards=[
                CanvasCard(
                    card_id="card-1",
                    kind=CanvasCardKind.EVIDENCE,
                    title="会议纪要摘录",
                    summary="老板希望先验证多源输入收敛能力。",
                    stage="discovery",
                )
            ],
            relations=[
                CanvasRelation(
                    relation_id="rel-1",
                    kind=CanvasRelationKind.SUPPORTS,
                    from_card_id="card-1",
                    to_card_id="card-2",
                )
            ],
            active_todos=[
                TodoProjection(
                    todo_id="todo-1",
                    source_card_id="card-2",
                    title="确认 1.0 是否需要方案卡",
                    reason="当前范围描述强调先聚焦待澄清与约束。",
                )
            ],
            handoff=StructuredHandoff(
                handoff_id="handoff-1",
                summary="当前已收束出首版闭环与关键缺口。",
                constraints=["首版不做多人实时协作"],
                open_questions=["方案层对象是否进入 1.0"],
                decisions=["先聚焦输入编译到结构化交接物"],
                metadata={"version": "1.0"},
            ),
            metadata={"trigger": "manual"},
        )

        data = snapshot.to_dict()

        self.assertEqual(CanvasSnapshot.from_dict(data), snapshot)

    def test_canvas_workspace_roundtrip(self) -> None:
        workspace = CanvasWorkspace(
            workspace_id="workspace-1",
            title="EvoCanvas 1.0",
            goal="把多源输入收束为待澄清问题、约束、待决策和结构化交接物。",
            stage="definition",
            cards=[
                CanvasCard(
                    card_id="card-1",
                    kind=CanvasCardKind.QUESTION,
                    title="为什么不是 PRD 生成器",
                    summary="需要持续强调产品目标是想明白，而不是直接产文档。",
                    stage="definition",
                )
            ],
            relations=[
                CanvasRelation(
                    relation_id="rel-1",
                    kind=CanvasRelationKind.CONFLICTS_WITH,
                    from_card_id="card-1",
                    to_card_id="card-2",
                )
            ],
            snapshots=[
                CanvasSnapshot(
                    snapshot_id="snapshot-1",
                    workspace_id="workspace-1",
                    title="范围冻结",
                    summary="当前完成首版范围确认。",
                    created_at="2026-06-14T11:00:00+00:00",
                )
            ],
            metadata={"owner_role": "pm"},
        )

        data = workspace.to_dict()

        self.assertEqual(CanvasWorkspace.from_dict(data), workspace)


if __name__ == "__main__":
    unittest.main()

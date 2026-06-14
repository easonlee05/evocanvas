import unittest

from app.canvas.domain.cards import CanvasCard, CanvasCardKind
from app.canvas.domain.handoff import StructuredHandoff, TodoItem, TodoProjection
from app.canvas.domain.mutations import (
    CanvasMutation,
    CanvasMutationAction,
    CanvasMutationProposal,
    CanvasMutationStatus,
    CanvasMutationTarget,
    MutationRiskLevel,
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

        self.assertEqual(data["kind"], "clarification")
        self.assertEqual(CanvasCard.from_dict(data), card)

    def test_canvas_card_problem_kind_serializes_to_problem(self) -> None:
        card = CanvasCard(card_id="card-problem", kind=CanvasCardKind.PROBLEM, title="核心问题")

        data = card.to_dict()

        self.assertEqual(data["kind"], "problem")
        self.assertEqual(data["stage"], "discovery")
        self.assertEqual(data["status"], "open")

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

        self.assertEqual(data["kind"], "clarifies")
        self.assertEqual(CanvasRelation.from_dict(data), relation)

    def test_todo_projection_roundtrip(self) -> None:
        todo = TodoProjection(
            projection_id="todo-projection-1",
            workspace_id="workspace-1",
            items=[
                TodoItem(
                    todo_id="todo-1",
                    source_card_id="card-1",
                    title="补充目标用户范围",
                    status="open",
                    reason="关键范围仍不稳定，无法进入结构化交接物。",
                    assignee="pm",
                    metadata={"lane": "active"},
                )
            ],
            metadata={"lane": "active"},
        )

        data = todo.to_dict()

        self.assertEqual(data["items"][0]["source_card_id"], "card-1")
        self.assertEqual(TodoProjection.from_dict(data), todo)

    def test_todo_projection_defaults_to_empty_items(self) -> None:
        projection = TodoProjection(projection_id="todo-projection-2", workspace_id="workspace-1")

        data = projection.to_dict()

        self.assertEqual(data["items"], [])
        self.assertEqual(data["metadata"], {})

    def test_canvas_mutation_roundtrip(self) -> None:
        proposal = CanvasMutationProposal(
            proposal_id="proposal-1",
            workspace_id="workspace-1",
            turn_id="turn-12",
            mutations=[
                CanvasMutation(
                    mutation_id="mutation-1",
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
            ],
            risk_level=MutationRiskLevel.HIGH,
            status=CanvasMutationStatus.PROPOSED,
            metadata={"origin": "assistant"},
        )

        data = proposal.to_dict()

        self.assertEqual(data["risk_level"], "high")
        self.assertEqual(data["status"], "proposed")
        self.assertEqual(data["mutations"][0]["action"], "add")
        self.assertEqual(CanvasMutationProposal.from_dict(data), proposal)

    def test_canvas_snapshot_roundtrip(self) -> None:
        snapshot = CanvasSnapshot(
            snapshot_id="snapshot-1",
            workspace_id="workspace-1",
            title="首次输入编译后",
            summary="完成输入编译并显影第一批缺口。",
            created_at="2026-06-14T10:00:00+00:00",
            active_card_ids=["card-1", "card-2"],
            active_relation_ids=["rel-1"],
            cards=[CanvasCard(card_id="card-1", kind=CanvasCardKind.CLARIFICATION, title="确认 1.0 是否需要方案卡")],
            relations=[
                CanvasRelation(
                    relation_id="rel-1",
                    kind=CanvasRelationKind.SUPPORTS,
                    from_card_id="card-1",
                    to_card_id="card-2",
                )
            ],
            todo_projection=TodoProjection(
                projection_id="todo-projection-1",
                workspace_id="workspace-1",
                items=[
                    TodoItem(
                        todo_id="todo-1",
                        source_card_id="card-2",
                        title="确认 1.0 是否需要方案卡",
                        reason="当前范围描述强调先聚焦待澄清与约束。",
                    )
                ],
            ),
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

        self.assertEqual(data["active_card_ids"], ["card-1", "card-2"])
        self.assertEqual(data["cards"][0]["title"], "确认 1.0 是否需要方案卡")
        self.assertEqual(data["relations"][0]["kind"], "supports")
        self.assertEqual(CanvasSnapshot.from_dict(data), snapshot)

    def test_canvas_workspace_roundtrip(self) -> None:
        workspace = CanvasWorkspace(
            workspace_id="workspace-1",
            title="EvoCanvas 1.0",
            objective="把多源输入收束为待澄清问题、约束、待决策和结构化交接物。",
            active_snapshot_id="snapshot-1",
            active_turn_id="turn-1",
            active_turn_status="running",
            active_turn_started_at="2026-06-14T10:00:00Z",
            handoff_status="in_progress",
            metadata={"owner_role": "pm"},
            handoff_metadata={"last_handoff_id": "handoff-1"},
        )

        data = workspace.to_dict()

        self.assertEqual(data["objective"], "把多源输入收束为待澄清问题、约束、待决策和结构化交接物。")
        self.assertEqual(data["active_snapshot_id"], "snapshot-1")
        self.assertEqual(data["active_turn_id"], "turn-1")
        self.assertEqual(data["active_turn_status"], "running")
        self.assertNotIn("cards", data)
        self.assertEqual(CanvasWorkspace.from_dict(data), workspace)


if __name__ == "__main__":
    unittest.main()

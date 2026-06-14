"""EvoCanvas 工作区应用服务。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.canvas.agent.supervisor import CanvasSupervisor
from app.canvas.domain.cards import CanvasCard, CanvasCardKind
from app.canvas.domain.handoff import StructuredHandoff, TodoItem, TodoProjection
from app.canvas.domain.mutations import (
    CanvasMutation,
    CanvasMutationAction,
    CanvasMutationProposal,
    CanvasMutationStatus,
    CanvasMutationTarget,
)
from app.canvas.domain.relations import CanvasRelation, CanvasRelationKind
from app.canvas.domain.snapshots import CanvasSnapshot
from app.canvas.domain.workspace import CanvasWorkspace
from app.canvas.governance import MutationGovernance
from app.canvas.repository import CanvasRepository
from app.core.events import Event, utc_now_iso
from app.services.fakes import FakeLLM


class CanvasTurnInProgressError(RuntimeError):
    """表示当前工作区已有回合执行中，新的输入需要等待。"""

    def __init__(self, workspace_id: str, active_turn: Dict[str, Any]):
        super().__init__(f"workspace {workspace_id} already has an active turn")
        self.workspace_id = workspace_id
        self.active_turn = active_turn


class CanvasCardNotFoundError(KeyError):
    """表示请求修订的画布卡片不存在。"""


class CanvasRelationValidationError(ValueError):
    """表示画布关系请求引用了不存在的卡片或非法关系类型。"""


class CanvasCardMoveValidationError(ValueError):
    """表示卡片迁移目标不合法，不能静默破坏 EvoCanvas 的阶段语义。"""


class CanvasSnapshotNotFoundError(KeyError):
    """表示请求读取的画布快照不存在。"""


class CanvasMessageValidationError(ValueError):
    """表示画布消息引用了不存在的上下文对象。"""


class CanvasService:
    """封装 EvoCanvas 工作区的读取、回合推进与确认流。"""

    def __init__(self, storage: Any, llm: Any = None):
        self.storage = storage
        self.repository = CanvasRepository(storage)
        self.supervisor = CanvasSupervisor(llm=llm or FakeLLM())
        self.governance = MutationGovernance(repository=self.repository)

    def get_workspace(self, workspace_id: str) -> CanvasWorkspace:
        workspace = self.repository.load_workspace(workspace_id)
        if workspace is not None:
            return workspace

        workspace = CanvasWorkspace(
            workspace_id=workspace_id,
            title=f"EvoCanvas Workspace {workspace_id}",
            objective="从多源输入中收敛待澄清、约束、待决策与结构化交接物。",
            handoff_status="draft",
        )
        self.repository.save_workspace(workspace)
        return workspace

    def get_canvas_view(self, workspace_id: str, snapshot_id: Optional[str] = None) -> Dict[str, Any]:
        workspace, cards, relations, snapshot = self._load_canvas_state(workspace_id, snapshot_id=snapshot_id)
        todo_projection = self._build_todo_projection(workspace_id, cards)
        pending_confirmations = self.repository.load_confirmation_queue(workspace_id)

        return {
            "workspace_id": workspace.workspace_id,
            "snapshot_id": snapshot.snapshot_id if snapshot else workspace.active_snapshot_id or None,
            "active_turn": self._serialize_active_turn(workspace),
            "cards": [card.to_dict() for card in cards],
            "relations": [relation.to_dict() for relation in relations],
            "todo_projection": todo_projection.to_dict(),
            "pending_confirmations_count": len(pending_confirmations),
            "view_meta": {
                "handoff_status": workspace.handoff_status,
                "is_snapshot": snapshot is not None,
            },
        }

    def start_turn(
        self,
        workspace_id: str,
        message: str,
        selected_card_ids: List[str],
        material_ids: List[str],
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        del mode

        turn_id = f"turn_{uuid4().hex[:12]}"
        workspace = self._begin_turn(workspace_id, turn_id)
        try:
            self._publish_event(
                workspace_id,
                "canvas.turn.started",
                {
                    "workspace_id": workspace_id,
                    "turn_id": turn_id,
                    "proposal_id": None,
                    "active_turn": self._serialize_active_turn(workspace),
                },
                status="running",
            )
            existing_cards = self.repository.load_cards(workspace_id)
            self._validate_selected_cards(selected_card_ids, existing_cards)
            plan = self.supervisor.recognize_and_plan(
                workspace_context={
                    "workspace_id": workspace_id,
                    "selected_card_ids": list(selected_card_ids),
                    "material_ids": list(material_ids),
                },
                message=message,
            )
            proposal = self._build_mutation_proposal(
                workspace,
                turn_id,
                message,
                plan,
                existing_cards=existing_cards,
                selected_card_ids=selected_card_ids,
                material_ids=material_ids,
            )
            self.repository.append_proposal_history(workspace_id, proposal)
            self._publish_event(
                workspace_id,
                "canvas.mutation.proposed",
                self._proposal_event_payload(
                    workspace_id=workspace_id,
                    turn_id=turn_id,
                    proposal=proposal,
                    intent=plan.intent,
                    roles=list(plan.roles),
                    result_action="proposed",
                    active_turn=self._serialize_active_turn(workspace),
                ),
                status="proposed",
            )
            outcome = self.governance.classify(proposal)

            if outcome.action == "auto_apply":
                self._apply_proposal(workspace, proposal)
            else:
                self._mark_turn_awaiting_confirmation(workspace_id, turn_id)

            self._publish_event(
                workspace_id,
                "canvas.confirmation.requested" if outcome.action == "pending_confirmation" else "canvas.mutation.applied",
                self._proposal_event_payload(
                    workspace_id=workspace_id,
                    turn_id=turn_id,
                    proposal=proposal,
                    intent=plan.intent,
                    roles=list(plan.roles),
                    result_action=outcome.action,
                    active_turn=self._serialize_active_turn(self.get_workspace(workspace_id)),
                ),
                status=proposal.status.value,
            )
            if outcome.action == "auto_apply":
                self._finish_turn(workspace_id, turn_id)
                self._publish_event(
                    workspace_id,
                    "canvas.turn.completed",
                    {
                        "workspace_id": workspace_id,
                        "turn_id": turn_id,
                        "proposal_id": proposal.proposal_id,
                        "result_action": outcome.action,
                        "active_turn": None,
                    },
                    status="completed",
                )
            return {
                "turn_id": turn_id,
                "workspace_id": workspace_id,
                "proposal_id": proposal.proposal_id,
                "action": outcome.action,
                "risk_level": outcome.risk_level.value,
                "intent": plan.intent,
                "roles": list(plan.roles),
            }
        except Exception as exc:
            self._finish_turn(workspace_id, turn_id)
            self._publish_event(
                workspace_id,
                "canvas.turn.failed",
                {
                    "workspace_id": workspace_id,
                    "turn_id": turn_id,
                    "proposal_id": None,
                    "result_action": "failed",
                    "active_turn": None,
                    "error": str(exc),
                },
                status="failed",
            )
            raise

    def list_confirmations(self, workspace_id: str) -> Dict[str, Any]:
        items = self.repository.load_confirmation_queue(workspace_id)
        return {"items": [item.to_dict() for item in items]}

    def approve_confirmation(self, workspace_id: str, proposal_id: str) -> Dict[str, Any]:
        queue = self.repository.load_confirmation_queue(workspace_id)
        approved = None
        remaining = []
        for proposal in queue:
            if proposal.proposal_id == proposal_id:
                approved = proposal
            else:
                remaining.append(proposal)
        if approved is None:
            return {"workspace_id": workspace_id, "proposal_id": proposal_id, "status": "not_found"}

        self._materialize_confirmation_approval(approved)
        approved.status = CanvasMutationStatus.APPLIED
        self.repository.append_proposal_history(workspace_id, approved)
        self._apply_proposal(self.get_workspace(workspace_id), approved)
        if any(
            mutation.metadata.get("mutation_type") == "promote_formal_handoff"
            for mutation in approved.mutations
        ):
            workspace = self.get_workspace(workspace_id)
            workspace.handoff_status = "confirmed"
            workspace.handoff_metadata = {
                **dict(workspace.handoff_metadata),
                "confirmed_by": "user",
                "confirmation_proposal_id": approved.proposal_id,
            }
            self.repository.save_workspace(workspace)
        self.repository.save_confirmation_queue(workspace_id, remaining)
        self._publish_event(
            workspace_id,
            "canvas.confirmation.approved",
            self._proposal_event_payload(
                workspace_id=workspace_id,
                turn_id=approved.turn_id,
                proposal=approved,
                result_action="approved",
                active_turn=self._serialize_active_turn(self.get_workspace(workspace_id)),
            ),
            status="approved",
        )
        self._publish_event(
            workspace_id,
            "canvas.mutation.applied",
            self._proposal_event_payload(
                workspace_id=workspace_id,
                turn_id=approved.turn_id,
                proposal=approved,
                result_action="approved",
                active_turn=self._serialize_active_turn(self.get_workspace(workspace_id)),
            ),
            status=approved.status.value,
        )
        self._finish_turn(workspace_id, approved.turn_id)
        self._publish_event(
            workspace_id,
            "canvas.turn.completed",
            {
                "workspace_id": workspace_id,
                "turn_id": approved.turn_id,
                "proposal_id": approved.proposal_id,
                "result_action": "approved",
                "active_turn": None,
            },
            status="completed",
        )
        return {"workspace_id": workspace_id, "proposal_id": proposal_id, "status": "applied"}

    def reject_confirmation(self, workspace_id: str, proposal_id: str) -> Dict[str, Any]:
        queue = self.repository.load_confirmation_queue(workspace_id)
        rejected_turn_id = ""
        remaining = []
        found = False
        for proposal in queue:
            if proposal.proposal_id == proposal_id:
                found = True
                rejected_turn_id = proposal.turn_id
            else:
                remaining.append(proposal)
        if not found:
            return {"workspace_id": workspace_id, "proposal_id": proposal_id, "status": "not_found"}
        if rejected_turn_id:
            rejected = next((proposal for proposal in queue if proposal.proposal_id == proposal_id), None)
            if rejected is not None:
                rejected.status = CanvasMutationStatus.REJECTED
                self.repository.append_proposal_history(workspace_id, rejected)
        self.repository.save_confirmation_queue(workspace_id, remaining)
        if rejected_turn_id:
            self._publish_event(
                workspace_id,
                "canvas.confirmation.rejected",
                {
                    "workspace_id": workspace_id,
                    "turn_id": rejected_turn_id,
                    "proposal_id": proposal_id,
                    "result_action": "rejected",
                    "active_turn": self._serialize_active_turn(self.get_workspace(workspace_id)),
                    "affected_card_ids": [],
                    "affected_relation_ids": [],
                    "affected_snapshot_ids": [],
                },
                status="rejected",
            )
            self._finish_turn(workspace_id, rejected_turn_id)
            self._publish_event(
                workspace_id,
                "canvas.turn.completed",
                {
                    "workspace_id": workspace_id,
                    "turn_id": rejected_turn_id,
                    "proposal_id": proposal_id,
                    "result_action": "rejected",
                    "active_turn": None,
                },
                status="completed",
            )
        return {"workspace_id": workspace_id, "proposal_id": proposal_id, "status": "rejected"}

    def list_snapshots(self, workspace_id: str) -> Dict[str, Any]:
        snapshots = self.repository.list_snapshots(workspace_id)
        return {"items": [snapshot.to_dict() for snapshot in snapshots]}

    def create_snapshot(self, workspace_id: str, title: str, summary: str = "") -> Dict[str, Any]:
        """手动保存当前画布状态，供产品经理回看某次认知收敛结果。"""

        workspace = self.get_workspace(workspace_id)
        cards = self.repository.load_cards(workspace_id)
        relations = self.repository.load_relations(workspace_id)
        handoff = self.repository.load_handoff(workspace_id)
        snapshot = CanvasSnapshot(
            snapshot_id=f"snapshot_{uuid4().hex[:10]}",
            workspace_id=workspace_id,
            title=title.strip() or "未命名快照",
            summary=summary.strip(),
            created_at=utc_now_iso(),
            active_card_ids=[card.card_id for card in cards],
            active_relation_ids=[relation.relation_id for relation in relations],
            cards=list(cards),
            relations=list(relations),
            todo_projection=self._build_todo_projection(workspace_id, cards),
            handoff=handoff,
            metadata={"created_by": "user"},
        )
        self.repository.save_snapshot(workspace_id, snapshot)
        workspace.active_snapshot_id = snapshot.snapshot_id
        self.repository.save_workspace(workspace)
        self._publish_event(
            workspace_id,
            "canvas.snapshot.created",
            {
                "workspace_id": workspace_id,
                "snapshot_id": snapshot.snapshot_id,
                "snapshot": snapshot.to_dict(),
            },
            status="created",
        )
        return {"workspace_id": workspace_id, "snapshot": snapshot.to_dict()}

    def get_handoff(self, workspace_id: str) -> Dict[str, Any]:
        workspace = self.get_workspace(workspace_id)
        handoff = self.repository.load_handoff(workspace_id)
        if handoff is None:
            handoff = StructuredHandoff(handoff_id=f"handoff_{workspace_id}", summary="")
        return {
            "workspace_id": workspace_id,
            "status": workspace.handoff_status or "draft",
            "content": handoff.summary,
            "handoff": handoff.to_dict(),
        }

    def refresh_handoff(self, workspace_id: str) -> Dict[str, Any]:
        """基于当前画布状态重新收束结构化交接物草稿，并落一份新快照。"""

        workspace = self.get_workspace(workspace_id)
        active_turn = self._serialize_active_turn(workspace)
        if active_turn is not None:
            raise CanvasTurnInProgressError(workspace_id, active_turn)

        cards = self.repository.load_cards(workspace_id)
        relations = self.repository.load_relations(workspace_id)
        refreshed_at = utc_now_iso()
        handoff = StructuredHandoff(
            handoff_id=f"handoff_{workspace_id}",
            summary=self._build_refresh_handoff_summary(cards),
            constraints=self._handoff_items(cards, CanvasCardKind.CONSTRAINT),
            open_questions=self._handoff_items(cards, CanvasCardKind.CLARIFICATION),
            decisions=self._handoff_items(cards, CanvasCardKind.DECISION),
            metadata={"refreshed_by": "user", "refreshed_at": refreshed_at},
        )
        handoff_card = self._upsert_handoff_card(cards, handoff, refreshed_at=refreshed_at)
        todo_projection = self._build_todo_projection(workspace_id, cards)
        snapshot = CanvasSnapshot(
            snapshot_id=f"snapshot_{uuid4().hex[:10]}",
            workspace_id=workspace_id,
            title="结构化交接物草稿已刷新",
            summary=handoff.summary,
            created_at=refreshed_at,
            active_card_ids=[card.card_id for card in cards],
            active_relation_ids=[relation.relation_id for relation in relations],
            cards=list(cards),
            relations=list(relations),
            todo_projection=todo_projection,
            handoff=handoff,
            metadata={"created_by": "user", "source": "handoff_refresh"},
        )

        self.repository.save_handoff(workspace_id, handoff)
        self.repository.save_cards(workspace_id, cards)
        self.repository.save_snapshot(workspace_id, snapshot)
        workspace.handoff_status = "draft"
        workspace.handoff_metadata = {
            **dict(workspace.handoff_metadata),
            "last_refreshed_at": refreshed_at,
            "last_refreshed_by": "user",
            "source_snapshot_id": snapshot.snapshot_id,
        }
        workspace.active_snapshot_id = snapshot.snapshot_id
        self.repository.save_workspace(workspace)
        self._publish_event(
            workspace_id,
            "canvas.handoff.refreshed",
            {
                "workspace_id": workspace_id,
                "snapshot_id": snapshot.snapshot_id,
                "handoff": handoff.to_dict(),
                "card_id": handoff_card.card_id,
            },
            status="refreshed",
        )
        return {
            "workspace_id": workspace_id,
            "status": workspace.handoff_status,
            "content": handoff.summary,
            "handoff": handoff.to_dict(),
            "card": handoff_card.to_dict(),
            "snapshot": snapshot.to_dict(),
            "todo_projection": todo_projection.to_dict(),
        }

    def get_todos(self, workspace_id: str, snapshot_id: Optional[str] = None) -> Dict[str, Any]:
        """返回当前画布时态下的活跃缺口投影。"""

        _, cards, _, _ = self._load_canvas_state(workspace_id, snapshot_id=snapshot_id)
        return self._build_todo_projection(workspace_id, cards).to_dict()

    def patch_card(self, workspace_id: str, card_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        """原地修订卡片展示字段，保留卡片类型、来源与关系边界不变。"""

        workspace = self.get_workspace(workspace_id)
        cards = self.repository.load_cards(workspace_id)
        updated_card = None
        for card in cards:
            if card.card_id != card_id:
                continue
            if "title" in patch and patch["title"] is not None:
                card.title = str(patch["title"]).strip()
            if "summary" in patch and patch["summary"] is not None:
                card.summary = str(patch["summary"]).strip()
            if "status" in patch and patch["status"] is not None:
                card.status = str(patch["status"]).strip()
            if "tags" in patch and patch["tags"] is not None:
                card.tags = [str(tag).strip() for tag in patch["tags"] if str(tag).strip()]
            card.metadata["last_edited_by"] = "user"
            card.metadata["last_edited_at"] = utc_now_iso()
            updated_card = card
            break

        if updated_card is None:
            raise CanvasCardNotFoundError(card_id)

        self.repository.save_cards(workspace_id, cards)
        todo_projection = self._build_todo_projection(workspace_id, cards)
        self.repository.save_workspace(workspace)
        self._publish_event(
            workspace_id,
            "canvas.card.updated",
            {
                "workspace_id": workspace_id,
                "card_id": card_id,
                "card": updated_card.to_dict(),
            },
            status="updated",
        )
        return {
            "workspace_id": workspace_id,
            "card": updated_card.to_dict(),
            "todo_projection": todo_projection.to_dict(),
        }

    def create_relation(
        self,
        workspace_id: str,
        kind: str,
        from_card_id: str,
        to_card_id: str,
        note: str = "",
    ) -> Dict[str, Any]:
        """创建两张已有卡片之间的语义关系，帮助画布显性化证据链与冲突链。"""

        self.get_workspace(workspace_id)
        cards = self.repository.load_cards(workspace_id)
        card_ids = {card.card_id for card in cards}
        if from_card_id not in card_ids or to_card_id not in card_ids:
            raise CanvasRelationValidationError("relation endpoints must reference existing cards")
        try:
            relation_kind = CanvasRelationKind(kind)
        except ValueError as exc:
            raise CanvasRelationValidationError(f"unsupported relation kind: {kind}") from exc

        relations = self.repository.load_relations(workspace_id)
        relation = CanvasRelation(
            relation_id=f"rel_{uuid4().hex[:10]}",
            kind=relation_kind,
            from_card_id=from_card_id,
            to_card_id=to_card_id,
            note=note.strip(),
            metadata={"created_by": "user", "created_at": utc_now_iso()},
        )
        relations.append(relation)
        self.repository.save_relations(workspace_id, relations)
        self._publish_event(
            workspace_id,
            "canvas.relation.created",
            {
                "workspace_id": workspace_id,
                "relation_id": relation.relation_id,
                "relation": relation.to_dict(),
            },
            status="created",
        )
        return {"workspace_id": workspace_id, "relation": relation.to_dict()}

    def move_card(self, workspace_id: str, card_id: str, stage: str, reason: str = "") -> Dict[str, Any]:
        """在合法阶段带之间迁移卡片，避免把主画布退化为自由白板。"""

        workspace = self.get_workspace(workspace_id)
        cards = self.repository.load_cards(workspace_id)
        normalized_stage = self._normalize_stage(stage)
        updated_card = None
        previous_stage = ""
        for card in cards:
            if card.card_id != card_id:
                continue
            self._validate_stage_move(card, normalized_stage)
            previous_stage = card.stage
            card.stage = normalized_stage
            card.metadata["last_moved_by"] = "user"
            card.metadata["last_moved_at"] = utc_now_iso()
            card.metadata["previous_stage"] = previous_stage
            if reason.strip():
                card.metadata["move_reason"] = reason.strip()
            updated_card = card
            break

        if updated_card is None:
            raise CanvasCardNotFoundError(card_id)

        self.repository.save_cards(workspace_id, cards)
        todo_projection = self._build_todo_projection(workspace_id, cards)
        self.repository.save_workspace(workspace)
        self._publish_event(
            workspace_id,
            "canvas.card.moved",
            {
                "workspace_id": workspace_id,
                "card_id": card_id,
                "from_stage": previous_stage,
                "to_stage": normalized_stage,
                "card": updated_card.to_dict(),
            },
            status="moved",
        )
        return {
            "workspace_id": workspace_id,
            "action": "applied",
            "card": updated_card.to_dict(),
            "move": {
                "from_stage": previous_stage,
                "to_stage": normalized_stage,
                "reason": reason.strip(),
                "semantic_change": previous_stage != normalized_stage,
            },
            "todo_projection": todo_projection.to_dict(),
        }

    @staticmethod
    def event_stream_id(workspace_id: str) -> str:
        return f"canvas:{workspace_id}"

    def _build_mutation_proposal(
        self,
        workspace: CanvasWorkspace,
        turn_id: str,
        message: str,
        plan,
        existing_cards: List[CanvasCard],
        selected_card_ids: List[str],
        material_ids: List[str],
    ) -> CanvasMutationProposal:
        mutations: list[CanvasMutation] = []
        selected_cards = [card for card in existing_cards if card.card_id in set(selected_card_ids)]
        contextual_summary = self._build_contextual_summary(message, selected_cards)

        for role_name in plan.roles:
            if role_name == "Clarifier":
                mutations.append(
                    self._card_mutation(
                        mutation_type="add_card",
                        kind=CanvasCardKind.CLARIFICATION,
                        title=self._truncate_title(message, "待澄清"),
                        summary=contextual_summary,
                        evidence_refs=material_ids,
                        selected_card_ids=selected_card_ids,
                    )
                )
            elif role_name == "ConstraintSteward":
                mutations.append(
                    self._card_mutation(
                        mutation_type="promote_to_constraint_draft",
                        kind=CanvasCardKind.CONSTRAINT,
                        title=self._truncate_title(message, "约束草稿"),
                        summary=contextual_summary,
                        status="draft",
                        evidence_refs=material_ids,
                        selected_card_ids=selected_card_ids,
                    )
                )
            elif role_name == "DecisionSteward":
                mutations.append(
                    self._card_mutation(
                        mutation_type="create_decision_request",
                        kind=CanvasCardKind.DECISION,
                        title=self._truncate_title(message, "待决策"),
                        summary=contextual_summary,
                        status="pending",
                        evidence_refs=material_ids,
                        selected_card_ids=selected_card_ids,
                    )
                )
            elif role_name == "HandoffBuilder":
                handoff_card = CanvasCard(
                    card_id=f"card_{uuid4().hex[:10]}",
                    kind=CanvasCardKind.HANDOFF,
                    title=self._truncate_title(message, "结构化交接物草稿"),
                    summary=self._build_handoff_summary(message, existing_cards),
                    stage="handoff",
                    status="draft",
                    evidence_refs=list(material_ids),
                    metadata={
                        "created_by": "canvas_agent",
                        "source_turn_id": turn_id,
                        "selected_card_ids": list(selected_card_ids),
                    },
                )
                mutations.append(
                    CanvasMutation(
                        mutation_id=f"mutation_{uuid4().hex[:10]}",
                        action=CanvasMutationAction.ADD,
                        target=CanvasMutationTarget.CARD,
                        target_id=handoff_card.card_id,
                        payload={"card": handoff_card.to_dict()},
                        metadata={
                            "mutation_type": "refresh_handoff_card",
                            "selected_card_ids": list(selected_card_ids),
                            "material_ids": list(material_ids),
                        },
                    )
                )
                mutations.append(
                    CanvasMutation(
                        mutation_id=f"mutation_{uuid4().hex[:10]}",
                        action=CanvasMutationAction.UPDATE,
                        target=CanvasMutationTarget.HANDOFF,
                        target_id="handoff_draft",
                        payload={
                            "handoff": {
                                "handoff_id": f"handoff_{workspace.workspace_id}",
                                "summary": self._build_handoff_summary(message, existing_cards),
                                "constraints": self._handoff_items(existing_cards, CanvasCardKind.CONSTRAINT),
                                "open_questions": self._handoff_items(existing_cards, CanvasCardKind.CLARIFICATION),
                                "decisions": self._handoff_items(existing_cards, CanvasCardKind.DECISION),
                                "metadata": {
                                    "source_turn_id": turn_id,
                                    "material_ids": list(material_ids),
                                    "selected_card_ids": list(selected_card_ids),
                                },
                            }
                        },
                        metadata={"mutation_type": "refresh_handoff_draft"},
                    )
                )
            else:
                mutations.append(
                    self._card_mutation(
                        mutation_type="add_card",
                        kind=CanvasCardKind.EVIDENCE,
                        title=self._truncate_title(message, "输入摘要"),
                        summary=contextual_summary,
                        evidence_refs=material_ids,
                        selected_card_ids=selected_card_ids,
                    )
                )
                mutations.append(
                    self._card_mutation(
                        mutation_type="add_card",
                        kind=CanvasCardKind.PROBLEM,
                        title=self._truncate_title(message, "问题定义草稿"),
                        summary=f"从输入中抽取的待定义问题：{contextual_summary}",
                        evidence_refs=material_ids,
                        selected_card_ids=selected_card_ids,
                    )
                )
                mutations.append(
                    self._card_mutation(
                        mutation_type="add_card",
                        kind=CanvasCardKind.CLARIFICATION,
                        title=self._truncate_title(message, "待澄清缺口"),
                        summary=f"需要继续澄清的关键信息：{contextual_summary}",
                        evidence_refs=material_ids,
                        selected_card_ids=selected_card_ids,
                    )
                )

        return CanvasMutationProposal(
            proposal_id=f"proposal_{uuid4().hex[:12]}",
            workspace_id=workspace.workspace_id,
            turn_id=turn_id,
            mutations=mutations,
            metadata={
                "selected_card_ids": list(selected_card_ids),
                "material_ids": list(material_ids),
            },
        )

    def _apply_proposal(self, workspace: CanvasWorkspace, proposal: CanvasMutationProposal) -> None:
        cards = self.repository.load_cards(workspace.workspace_id)
        relations = self.repository.load_relations(workspace.workspace_id)
        handoff = self.repository.load_handoff(workspace.workspace_id)

        card_index = {card.card_id: card for card in cards}
        relation_index = {relation.relation_id: relation for relation in relations}
        latest_card_id = None
        for mutation in proposal.mutations:
            mutation_type = str(mutation.metadata.get("mutation_type", ""))
            if mutation.target == CanvasMutationTarget.CARD and mutation_type in {
                "add_card",
                "promote_to_constraint_draft",
                "create_decision_request",
                "refresh_handoff_card",
            }:
                card = CanvasCard.from_dict(mutation.payload["card"])
                card_index[card.card_id] = card
                latest_card_id = card.card_id
            elif mutation.target == CanvasMutationTarget.CARD and mutation.action == CanvasMutationAction.UPDATE:
                card = card_index.get(mutation.target_id)
                if card is None:
                    continue
                if "title" in mutation.payload:
                    card.title = str(mutation.payload["title"])
                if "summary" in mutation.payload:
                    card.summary = str(mutation.payload["summary"])
                if "stage" in mutation.payload:
                    card.stage = str(mutation.payload["stage"])
                if "status" in mutation.payload:
                    card.status = str(mutation.payload["status"])
                if "tags" in mutation.payload:
                    card.tags = [str(tag) for tag in mutation.payload["tags"]]
                if "metadata" in mutation.payload:
                    card.metadata = {**card.metadata, **dict(mutation.payload["metadata"])}
                card_index[card.card_id] = card
                latest_card_id = card.card_id
            elif mutation.target == CanvasMutationTarget.HANDOFF and mutation_type == "refresh_handoff_draft":
                handoff = StructuredHandoff.from_dict(mutation.payload["handoff"])
            elif mutation.target == CanvasMutationTarget.SNAPSHOT and mutation_type == "create_snapshot":
                snapshot_id = mutation.target_id or f"snapshot_{uuid4().hex[:10]}"
                handoff_for_snapshot = handoff if handoff is not None else self.repository.load_handoff(workspace.workspace_id)
                snapshot = CanvasSnapshot(
                    snapshot_id=snapshot_id,
                    workspace_id=workspace.workspace_id,
                    title=str(mutation.payload.get("title", "")).strip() or "AI 建议保存快照",
                    summary=str(mutation.payload.get("summary", "")).strip(),
                    created_at=utc_now_iso(),
                    active_card_ids=[card.card_id for card in cards],
                    active_relation_ids=[relation.relation_id for relation in relations],
                    cards=list(cards),
                    relations=list(relations),
                    todo_projection=self._build_todo_projection(workspace.workspace_id, cards),
                    handoff=handoff_for_snapshot,
                    metadata={
                        "created_by": "canvas_agent",
                        **dict(mutation.payload.get("metadata", {})),
                    },
                )
                self.repository.save_snapshot(workspace.workspace_id, snapshot)
                workspace.active_snapshot_id = snapshot.snapshot_id

        cards = list(card_index.values())
        if latest_card_id is not None:
            for selected_card_id in proposal.metadata.get("selected_card_ids", []):
                relation = CanvasRelation(
                    relation_id=f"rel_{uuid4().hex[:10]}",
                    kind=CanvasRelationKind.DERIVED_FROM,
                    from_card_id=selected_card_id,
                    to_card_id=latest_card_id,
                    metadata={"source_proposal_id": proposal.proposal_id},
                )
                relation_index[relation.relation_id] = relation

        relations = list(relation_index.values())
        self.repository.save_cards(workspace.workspace_id, cards)
        self.repository.save_relations(workspace.workspace_id, relations)
        if handoff is not None:
            self.repository.save_handoff(workspace.workspace_id, handoff)
            workspace.handoff_status = "draft"
            snapshot = CanvasSnapshot(
                snapshot_id=f"snapshot_{uuid4().hex[:10]}",
                workspace_id=workspace.workspace_id,
                title="结构化交接物草稿已刷新",
                summary=handoff.summary,
                created_at=utc_now_iso(),
                active_card_ids=[card.card_id for card in cards],
                active_relation_ids=[relation.relation_id for relation in relations],
                cards=list(cards),
                relations=list(relations),
                todo_projection=self._build_todo_projection(workspace.workspace_id, cards),
                handoff=handoff,
                metadata={"source_proposal_id": proposal.proposal_id},
            )
            self.repository.save_snapshot(workspace.workspace_id, snapshot)
            workspace.active_snapshot_id = snapshot.snapshot_id
        self.repository.save_workspace(workspace)

    def _card_mutation(
        self,
        mutation_type: str,
        kind: CanvasCardKind,
        title: str,
        summary: str,
        status: str = "open",
        evidence_refs: Optional[List[str]] = None,
        selected_card_ids: Optional[List[str]] = None,
    ) -> CanvasMutation:
        card = CanvasCard(
            card_id=f"card_{uuid4().hex[:10]}",
            kind=kind,
            title=title,
            summary=summary,
            stage="define" if kind != CanvasCardKind.EVIDENCE else "discovery",
            status=status,
            evidence_refs=list(evidence_refs or []),
            metadata={
                "created_by": "canvas_agent",
                "selected_card_ids": list(selected_card_ids or []),
            },
        )
        return CanvasMutation(
            mutation_id=f"mutation_{uuid4().hex[:10]}",
            action=CanvasMutationAction.ADD,
            target=CanvasMutationTarget.CARD,
            target_id=card.card_id,
            payload={"card": card.to_dict()},
            metadata={
                "mutation_type": mutation_type,
                "selected_card_ids": list(selected_card_ids or []),
                "material_ids": list(evidence_refs or []),
            },
        )

    def _build_todo_projection(self, workspace_id: str, cards: List[CanvasCard]) -> TodoProjection:
        items: list[TodoItem] = []
        for card in cards:
            if card.status in {"open", "draft", "pending"} and card.kind in {
                CanvasCardKind.CLARIFICATION,
                CanvasCardKind.CONSTRAINT,
                CanvasCardKind.DECISION,
            }:
                items.append(
                    TodoItem(
                        todo_id=f"todo_{card.card_id}",
                        source_card_id=card.card_id,
                        title=card.title,
                        reason=card.kind.value,
                    )
                )
        return TodoProjection(
            projection_id=f"todo_{workspace_id}",
            workspace_id=workspace_id,
            items=items,
        )

    def _publish_event(self, workspace_id: str, event_type: str, payload: Dict[str, Any], status: str) -> None:
        if not hasattr(self.storage, "event_bus") or self.storage.event_bus is None:
            return
        self.storage.event_bus.publish(
            Event(
                task_id=self.event_stream_id(workspace_id),
                type=event_type,
                payload=payload,
                role="CanvasSupervisor",
                status=status,
            )
        )

    @staticmethod
    def _proposal_event_payload(
        workspace_id: str,
        turn_id: str,
        proposal: CanvasMutationProposal,
        intent: str = "",
        roles: Optional[List[str]] = None,
        result_action: str = "",
        active_turn: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        affected_card_ids = []
        affected_relation_ids = []
        affected_snapshot_ids = []
        for mutation in proposal.mutations:
            if mutation.target == CanvasMutationTarget.CARD:
                affected_card_ids.append(mutation.target_id)
            elif mutation.target == CanvasMutationTarget.RELATION:
                affected_relation_ids.append(mutation.target_id)
            elif mutation.target == CanvasMutationTarget.SNAPSHOT:
                affected_snapshot_ids.append(mutation.target_id)
        return {
            "workspace_id": workspace_id,
            "turn_id": turn_id,
            "proposal_id": proposal.proposal_id,
            "intent": intent or str(proposal.metadata.get("intent", "")),
            "roles": list(roles or proposal.metadata.get("roles", [])),
            "risk_level": proposal.risk_level.value,
            "result_action": result_action,
            "active_turn": active_turn,
            "mutation_count": len(proposal.mutations),
            "affected_card_ids": affected_card_ids,
            "affected_relation_ids": affected_relation_ids,
            "affected_snapshot_ids": affected_snapshot_ids,
        }

    def _begin_turn(self, workspace_id: str, turn_id: str) -> CanvasWorkspace:
        workspace = self.get_workspace(workspace_id)
        claimed = self.repository.claim_active_turn(workspace_id, turn_id, utc_now_iso())
        if claimed is None:
            raise CanvasTurnInProgressError(
                workspace_id,
                self._serialize_active_turn(self.get_workspace(workspace_id)) or self._serialize_active_turn(workspace),
            )
        return claimed

    def _finish_turn(self, workspace_id: str, turn_id: str) -> None:
        self.repository.release_active_turn(workspace_id, turn_id)

    def _mark_turn_awaiting_confirmation(self, workspace_id: str, turn_id: str) -> None:
        self.repository.mark_turn_awaiting_confirmation(workspace_id, turn_id)

    @staticmethod
    def _serialize_active_turn(workspace: CanvasWorkspace) -> Optional[Dict[str, Any]]:
        if not workspace.active_turn_id:
            return None
        return {
            "turn_id": workspace.active_turn_id,
            "status": workspace.active_turn_status,
            "started_at": workspace.active_turn_started_at or None,
        }

    @staticmethod
    def _truncate_title(message: str, fallback: str) -> str:
        stripped = " ".join(message.split())
        return stripped[:32] if stripped else fallback

    @staticmethod
    def _build_contextual_summary(message: str, selected_cards: List[CanvasCard]) -> str:
        if not selected_cards:
            return message
        selected_titles = "；".join(card.title for card in selected_cards)
        return f"{message}\n关联上下文：{selected_titles}"

    def _load_canvas_state(
        self,
        workspace_id: str,
        snapshot_id: Optional[str] = None,
    ) -> tuple[CanvasWorkspace, List[CanvasCard], List[CanvasRelation], Optional[CanvasSnapshot]]:
        workspace = self.get_workspace(workspace_id)
        cards = self.repository.load_cards(workspace_id)
        relations = self.repository.load_relations(workspace_id)
        snapshot = self.repository.load_snapshot(workspace_id, snapshot_id) if snapshot_id else None
        if snapshot is not None:
            if snapshot.cards:
                cards = list(snapshot.cards)
            else:
                active_card_ids = set(snapshot.active_card_ids)
                cards = [card for card in cards if card.card_id in active_card_ids]
            if snapshot.relations:
                relations = list(snapshot.relations)
            else:
                active_relation_ids = set(snapshot.active_relation_ids)
                relations = [relation for relation in relations if relation.relation_id in active_relation_ids]
        elif snapshot_id:
            raise CanvasSnapshotNotFoundError(snapshot_id)
        return workspace, cards, relations, snapshot

    @staticmethod
    def _validate_selected_cards(selected_card_ids: List[str], cards: List[CanvasCard]) -> None:
        if not selected_card_ids:
            return
        existing_ids = {card.card_id for card in cards}
        missing_ids = [card_id for card_id in selected_card_ids if card_id not in existing_ids]
        if missing_ids:
            raise CanvasMessageValidationError(f"selected cards not found: {', '.join(missing_ids)}")

    @staticmethod
    def _normalize_stage(stage: str) -> str:
        stage_key = str(stage).strip().lower()
        return {"definition": "define"}.get(stage_key, stage_key)

    def _validate_stage_move(self, card: CanvasCard, target_stage: str) -> None:
        allowed_stages = {"discovery", "define", "handoff"}
        if target_stage not in allowed_stages:
            raise CanvasCardMoveValidationError(f"unsupported stage: {target_stage}")
        if card.kind == CanvasCardKind.HANDOFF and target_stage != "handoff":
            raise CanvasCardMoveValidationError("handoff card must stay in handoff stage")
        if target_stage == card.stage:
            return
        allowed_transitions = {
            "discovery": {"define"},
            "define": {"handoff"},
            "handoff": {"define"},
        }
        if target_stage not in allowed_transitions.get(card.stage, set()):
            raise CanvasCardMoveValidationError(f"illegal stage transition: {card.stage} -> {target_stage}")

    def _upsert_handoff_card(self, cards: List[CanvasCard], handoff: StructuredHandoff, refreshed_at: str) -> CanvasCard:
        for card in cards:
            if card.kind != CanvasCardKind.HANDOFF:
                continue
            card.title = card.title or "结构化交接物草稿"
            card.summary = handoff.summary
            card.stage = "handoff"
            card.status = "draft"
            card.metadata["last_edited_by"] = "user"
            card.metadata["last_edited_at"] = refreshed_at
            card.metadata["refresh_source"] = "current_canvas"
            return card

        handoff_card = CanvasCard(
            card_id=f"card_{uuid4().hex[:10]}",
            kind=CanvasCardKind.HANDOFF,
            title="结构化交接物草稿",
            summary=handoff.summary,
            stage="handoff",
            status="draft",
            metadata={
                "created_by": "user",
                "created_at": refreshed_at,
                "refresh_source": "current_canvas",
            },
        )
        cards.append(handoff_card)
        return handoff_card

    @staticmethod
    def _handoff_items(cards: List[CanvasCard], kind: CanvasCardKind) -> List[str]:
        return [card.title for card in cards if card.kind == kind and card.status in {"open", "draft", "pending"}]

    def _build_handoff_summary(self, message: str, cards: List[CanvasCard]) -> str:
        clarifications = self._handoff_items(cards, CanvasCardKind.CLARIFICATION)
        constraints = self._handoff_items(cards, CanvasCardKind.CONSTRAINT)
        return (
            f"基于当前回合收束的结构化交接物草稿：{message}"
            f"；待澄清 {len(clarifications)} 项，约束 {len(constraints)} 项。"
        )

    def _build_refresh_handoff_summary(self, cards: List[CanvasCard]) -> str:
        clarifications = self._handoff_items(cards, CanvasCardKind.CLARIFICATION)
        constraints = self._handoff_items(cards, CanvasCardKind.CONSTRAINT)
        decisions = self._handoff_items(cards, CanvasCardKind.DECISION)
        return (
            "基于当前画布收束的结构化交接物草稿："
            f"待澄清 {len(clarifications)} 项，约束 {len(constraints)} 项，待决策 {len(decisions)} 项。"
        )

    @staticmethod
    def _materialize_confirmation_approval(proposal: CanvasMutationProposal) -> None:
        """将待确认提案转换为已确认后的最终落盘状态。"""

        confirmed_at = utc_now_iso()
        for mutation in proposal.mutations:
            mutation_type = str(mutation.metadata.get("mutation_type", ""))
            if mutation.target == CanvasMutationTarget.CARD and mutation_type == "create_decision_request":
                card_payload = mutation.payload.get("card", {})
                card_payload["status"] = "confirmed"
                mutation.payload["card"] = card_payload
            elif mutation.target == CanvasMutationTarget.SNAPSHOT and mutation_type == "create_snapshot":
                mutation.action = CanvasMutationAction.ADD
                mutation.payload = {
                    **mutation.payload,
                    "metadata": {
                        **dict(mutation.payload.get("metadata", {})),
                        "confirmed_by": "user",
                        "confirmed_at": confirmed_at,
                        "confirmation_proposal_id": proposal.proposal_id,
                        "source_turn_id": proposal.turn_id,
                    },
                }
            elif mutation.target == CanvasMutationTarget.CARD and mutation_type == "confirm_constraint":
                mutation.action = CanvasMutationAction.UPDATE
                mutation.payload = {
                    **mutation.payload,
                    "status": "effective",
                    "metadata": {
                        **dict(mutation.payload.get("metadata", {})),
                        "confirmed_by": "user",
                        "confirmed_at": confirmed_at,
                        "confirmation_proposal_id": proposal.proposal_id,
                        "source_turn_id": proposal.turn_id,
                    },
                }
            elif mutation.target == CanvasMutationTarget.CARD and mutation_type == "resolve_clarification":
                mutation.action = CanvasMutationAction.UPDATE
                resolution = str(mutation.payload.get("resolution", "")).strip()
                mutation.payload = {
                    **mutation.payload,
                    "status": "resolved",
                    "metadata": {
                        **dict(mutation.payload.get("metadata", {})),
                        "resolved_by": "user",
                        "resolved_at": confirmed_at,
                        "resolution": resolution,
                        "confirmation_proposal_id": proposal.proposal_id,
                        "source_turn_id": proposal.turn_id,
                    },
                }
            elif mutation.target == CanvasMutationTarget.CARD and mutation_type == "promote_formal_handoff":
                mutation.action = CanvasMutationAction.UPDATE
                mutation.payload = {
                    **mutation.payload,
                    "status": "confirmed",
                    "metadata": {
                        **dict(mutation.payload.get("metadata", {})),
                        "confirmed_by": "user",
                        "confirmed_at": confirmed_at,
                        "confirmation_proposal_id": proposal.proposal_id,
                        "source_turn_id": proposal.turn_id,
                    },
                }

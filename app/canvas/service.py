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
from app.canvas.runtime_state import (
    apply_turn_runtime_state,
    build_canvas_view_meta,
    build_handoff_metadata,
    ensure_workspace_runtime_defaults,
    unresolved_issue_ids_from_cards,
)
from app.canvas.verification import verify_mutation_proposal
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


class CanvasRelationNotFoundError(KeyError):
    """表示请求删除的画布关系不存在。"""


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
        self.llm = llm
        self.repository = CanvasRepository(storage)
        self.supervisor = CanvasSupervisor(llm=llm or FakeLLM())
        self.governance = MutationGovernance(repository=self.repository)

    def get_workspace(self, workspace_id: str) -> CanvasWorkspace:
        workspace = self.repository.load_workspace(workspace_id)
        if workspace is not None:
            ensure_workspace_runtime_defaults(workspace)
            if not workspace.created_at or not workspace.updated_at:
                self._touch_workspace(workspace, initialize_missing_only=True)
            else:
                self.repository.save_workspace(workspace)
            return workspace

        now = utc_now_iso()
        workspace = CanvasWorkspace(
            workspace_id=workspace_id,
            title=f"EvoCanvas Workspace {workspace_id}",
            objective="从多源输入中收敛待澄清、约束、待决策与结构化交接物。",
            handoff_status="draft",
            created_at=now,
            updated_at=now,
        )
        ensure_workspace_runtime_defaults(workspace)
        self.repository.save_workspace(workspace)
        return workspace

    def list_recent_workspaces(self, limit: int = 24) -> Dict[str, Any]:
        """列出最近编辑过的 EvoCanvas 工作区，供最近项目视图恢复入口使用。"""

        items = []
        for workspace in self.repository.list_workspaces()[:limit]:
            handoff = self.repository.load_handoff(workspace.workspace_id)
            summary = ""
            if handoff is not None:
                summary = (handoff.summary or "").strip()
            if not summary:
                summary = (workspace.objective or "").strip()
            if not summary:
                summary = "继续补充这张产品工作画布。"
            items.append(
                {
                    "workspace_id": workspace.workspace_id,
                    "title": workspace.title or "未命名项目",
                    "created_at": workspace.created_at,
                    "updated_at": workspace.updated_at or workspace.created_at,
                    "handoff_status": workspace.handoff_status or "not_ready",
                    "summary_preview": summary[:140],
                    "cover_mode": "placeholder",
                    "cards": [
                        {
                            "kind": card.kind,
                            "stage": card.stage,
                        }
                        for card in self.repository.load_cards(workspace.workspace_id)
                    ],
                }
            )
        return {"items": items}

    def get_canvas_view(self, workspace_id: str, snapshot_id: Optional[str] = None) -> Dict[str, Any]:
        workspace, cards, relations, snapshot = self._load_canvas_state(workspace_id, snapshot_id=snapshot_id)
        todo_projection = self._build_todo_projection(workspace_id, cards)
        pending_confirmations = self.repository.load_confirmation_queue(workspace_id)
        handoff = snapshot.handoff if snapshot is not None else self.repository.load_handoff(workspace_id)

        return {
            "workspace_id": workspace.workspace_id,
            "snapshot_id": snapshot.snapshot_id if snapshot else workspace.active_snapshot_id or None,
            "active_turn": self._serialize_active_turn(workspace),
            "cards": [card.to_dict() for card in cards],
            "relations": [relation.to_dict() for relation in relations],
            "todo_projection": todo_projection.to_dict(),
            "pending_confirmations_count": len(pending_confirmations),
            "view_meta": build_canvas_view_meta(
                workspace,
                pending_confirmation_ids=[proposal.proposal_id for proposal in pending_confirmations],
                handoff=handoff,
                is_snapshot=snapshot is not None,
            ),
        }

    def start_turn(
        self,
        workspace_id: str,
        message: str,
        selected_card_ids: List[str],
        material_ids: List[str],
        source_ref_ids: Optional[List[str]] = None,
        mode: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        del mode
        source_ref_ids = list(source_ref_ids or [])

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

            selected_cards_info = []
            card_map = {c.card_id: c for c in existing_cards}
            for cid in selected_card_ids:
                if cid in card_map:
                    card = card_map[cid]
                    selected_cards_info.append({
                        "card_id": card.card_id,
                        "kind": card.kind.value if hasattr(card.kind, "value") else str(card.kind),
                        "status": card.status,
                    })

            # 映射前端发送的模型标识符至后端实际的 API model 名称
            resolved_model = None
            if model:
                model_lower = model.lower()
                if "deepseek" in model_lower:
                    resolved_model = "deepseek-chat"
                elif "gemini" in model_lower:
                    resolved_model = "gemini-1.5-flash"

            plan = self.supervisor.recognize_and_plan(
                workspace_context={
                    "workspace_id": workspace_id,
                    "selected_card_ids": list(selected_card_ids),
                    "selected_cards": selected_cards_info,
                    "material_ids": list(material_ids),
                    "source_ref_ids": list(source_ref_ids),
                    "model": resolved_model,
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
                source_ref_ids=source_ref_ids,
                model=resolved_model,
            )
            proposal.metadata["intent"] = plan.intent
            proposal.metadata["roles"] = list(plan.roles)
            proposal.metadata["verification_receipt"] = verify_mutation_proposal(
                proposal, intent=plan.intent, existing_cards=existing_cards
            )
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
            outcome = self.governance.classify(proposal, existing_cards=existing_cards)
            apply_turn_runtime_state(
                workspace,
                intent=plan.intent,
                proposal=proposal,
                result_action=outcome.action,
                cards=existing_cards,
                pending_gate_ids=[proposal.proposal_id] if outcome.action == "pending_confirmation" else [],
                unresolved_issue_ids=unresolved_issue_ids_from_cards(existing_cards),
            )
            self.repository.save_workspace(workspace)
            self.repository.append_proposal_history(workspace_id, proposal)

            if outcome.action == "auto_apply":
                self._apply_proposal(workspace, proposal)
                # 应用提案后，重新加载最新的卡片并再次更新运行时元数据以同步状态账本
                updated_cards = self.repository.load_cards(workspace_id)
                apply_turn_runtime_state(
                    workspace,
                    intent=plan.intent,
                    proposal=proposal,
                    result_action=outcome.action,
                    cards=updated_cards,
                    pending_gate_ids=[],
                    unresolved_issue_ids=unresolved_issue_ids_from_cards(updated_cards),
                )
                self.repository.save_workspace(workspace)
            elif outcome.action == "pending_confirmation":
                self._mark_turn_awaiting_confirmation(workspace_id, turn_id)
            else:
                # 验证失败情况 (downgrade_to_proposal 或 awaiting_clarification)
                # 不应用提案，也不用挂起，回合由于错误直接结束
                pass

            event_type = "canvas.mutation.applied"
            if outcome.action == "pending_confirmation":
                event_type = "canvas.confirmation.requested"
            elif outcome.action in {"downgrade_to_proposal", "awaiting_clarification"}:
                event_type = "canvas.mutation.failed"

            self._publish_event(
                workspace_id,
                event_type,
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
            if outcome.action != "pending_confirmation":
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
        workspace = self.get_workspace(workspace_id)
        self._apply_proposal(workspace, approved)
        if any(
            mutation.metadata.get("mutation_type") == "promote_formal_handoff"
            for mutation in approved.mutations
        ):
            workspace.handoff_status = "confirmed"
            workspace.handoff_metadata = {
                **dict(workspace.handoff_metadata),
                "confirmed_by": "user",
                "confirmation_proposal_id": approved.proposal_id,
                "confirmation_state": "confirmed",
            }
            self._touch_workspace(workspace)
        updated_cards = self.repository.load_cards(workspace_id)
        apply_turn_runtime_state(
            workspace,
            intent=str(approved.metadata.get("intent", "")),
            proposal=approved,
            result_action="approved",
            cards=updated_cards,
            pending_gate_ids=[],
            unresolved_issue_ids=unresolved_issue_ids_from_cards(updated_cards),
        )
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
        rejected = None
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
            workspace = self.get_workspace(workspace_id)
            apply_turn_runtime_state(
                workspace,
                intent=str(rejected.metadata.get("intent", "")) if rejected is not None else "",
                proposal=rejected
                or CanvasMutationProposal(
                    proposal_id=proposal_id,
                    workspace_id=workspace_id,
                    turn_id=rejected_turn_id,
                ),
                result_action="rejected",
                pending_gate_ids=[],
                unresolved_issue_ids=unresolved_issue_ids_from_cards(self.repository.load_cards(workspace_id)),
            )
            self.repository.save_workspace(workspace)
            self._publish_event(
                workspace_id,
                "canvas.confirmation.rejected",
                {
                    "workspace_id": workspace_id,
                    "turn_id": rejected_turn_id,
                    "proposal_id": proposal_id,
                    "result_action": "rejected",
                    "active_turn": self._serialize_active_turn(workspace),
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
        self._touch_workspace(workspace)
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
            handoff = StructuredHandoff(
                handoff_id=f"handoff_{workspace_id}",
                summary="",
                metadata=dict(workspace.handoff_metadata),
            )
        return {
            "workspace_id": workspace_id,
            "status": workspace.handoff_status or "not_ready",
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
            metadata={},
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

        handoff.metadata = build_handoff_metadata(
            cards,
            confirmation_state="draft",
            source_snapshot_id=snapshot.snapshot_id,
            refreshed_by="user",
            refreshed_at=refreshed_at,
        )
        self.repository.save_handoff(workspace_id, handoff)
        self.repository.save_cards(workspace_id, cards)
        self.repository.save_snapshot(workspace_id, snapshot)
        workspace.handoff_status = "draft"
        workspace.handoff_metadata = {**dict(workspace.handoff_metadata), **dict(handoff.metadata)}
        workspace.active_snapshot_id = snapshot.snapshot_id
        self._touch_workspace(workspace)
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
        self._touch_workspace(workspace)
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

    def patch_workspace(self, workspace_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        """原地修订工作区本身的基础属性，例如 title。"""
        workspace = self.get_workspace(workspace_id)
        if "title" in patch and patch["title"] is not None:
            workspace.title = str(patch["title"]).strip()
        
        workspace.updated_at = utc_now_iso()
        self.repository.save_workspace(workspace)
        return {
            "workspace_id": workspace.workspace_id,
            "title": workspace.title,
            "updated_at": workspace.updated_at,
        }

    def create_relation(
        self,
        workspace_id: str,
        kind: str,
        from_card_id: str,
        to_card_id: str,
        note: str = "",
        metadata: Optional[Dict[str, Any]] = None,
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
            metadata={
                "created_by": "user",
                "created_at": utc_now_iso(),
                **dict(metadata or {}),
            },
        )
        relations.append(relation)
        self.repository.save_relations(workspace_id, relations)
        self._touch_workspace(self.get_workspace(workspace_id))
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

    def delete_relation(self, workspace_id: str, relation_id: str) -> Dict[str, Any]:
        """删除一条已有卡片关系，允许用户修正错误连接并重新收敛证据链。"""

        self.get_workspace(workspace_id)
        relations = self.repository.load_relations(workspace_id)
        remaining_relations = [relation for relation in relations if relation.relation_id != relation_id]
        if len(remaining_relations) == len(relations):
            raise CanvasRelationNotFoundError(relation_id)

        self.repository.save_relations(workspace_id, remaining_relations)
        self._touch_workspace(self.get_workspace(workspace_id))
        self._publish_event(
            workspace_id,
            "canvas.relation.deleted",
            {
                "workspace_id": workspace_id,
                "relation_id": relation_id,
            },
            status="deleted",
        )
        return {
            "workspace_id": workspace_id,
            "relation_id": relation_id,
            "deleted": True,
        }

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
        self._touch_workspace(workspace)
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
        source_ref_ids: List[str],
        model: Optional[str] = None,
    ) -> CanvasMutationProposal:
        # 1. 检查是否为真实大模型运行环境 (非 FakeLLM，且 API 秘钥有效)
        from app.services.fakes import FakeLLM
        is_fake = (
            self.llm is None
            or isinstance(self.llm, FakeLLM)
            or getattr(self.llm, "api_key", "") == ""
        )

        if not is_fake:
            # 真实大模型调用，获取语义匹配的提案建议
            proposal = self._build_mutation_proposal_with_llm(
                workspace, turn_id, message, plan, existing_cards, selected_card_ids, material_ids, source_ref_ids, model=model
            )
            if proposal is not None:
                return proposal

        # 2. 本地回退规则分支
        mutations: list[CanvasMutation] = []
        selected_cards = [card for card in existing_cards if card.card_id in set(selected_card_ids)]
        evidence_refs = list(material_ids) + list(source_ref_ids)
        contextual_summary = self._build_contextual_summary(message, selected_cards)
        role_set = set(plan.roles)

        for role_name in plan.roles:
            if role_name == "InputCompiler":
                mutations.append(
                    self._card_mutation(
                        mutation_type="add_card",
                        kind=CanvasCardKind.EVIDENCE,
                        title=self._truncate_title(message, "输入摘要"),
                        summary=contextual_summary,
                        evidence_refs=evidence_refs,
                        material_ids=material_ids,
                        source_ref_ids=source_ref_ids,
                        selected_card_ids=selected_card_ids,
                    )
                )
                mutations.append(
                    self._card_mutation(
                        mutation_type="add_card",
                        kind=CanvasCardKind.PROBLEM,
                        title=self._truncate_title(message, "问题定义草稿"),
                        summary=f"从输入中抽取的待定义问题：{contextual_summary}",
                        evidence_refs=evidence_refs,
                        material_ids=material_ids,
                        source_ref_ids=source_ref_ids,
                        selected_card_ids=selected_card_ids,
                    )
                )
            elif role_name == "Clarifier":
                raw_title = self._truncate_title(message, "待澄清")
                title = raw_title.replace("先把", "").replace("把", "").replace("列出来", "").replace("的待澄清问题", "").replace("待澄清问题", "").strip()
                if not title.startswith("待澄清：") and not title.startswith("澄清："):
                    title = f"澄清：{title}"
                mutations.append(
                    self._card_mutation(
                        mutation_type="add_card",
                        kind=CanvasCardKind.CLARIFICATION,
                        title=title,
                        summary=contextual_summary,
                        evidence_refs=evidence_refs,
                        material_ids=material_ids,
                        source_ref_ids=source_ref_ids,
                        selected_card_ids=selected_card_ids,
                    )
                )
            elif role_name == "ConstraintSteward":
                raw_title = self._truncate_title(message, "约束草稿")
                title = raw_title.replace("先把", "").replace("把", "").replace("约束", "").replace("补齐", "").strip()
                if not title.startswith("约束："):
                    title = f"约束：{title}"
                mutations.append(
                    self._card_mutation(
                        mutation_type="promote_to_constraint_draft",
                        kind=CanvasCardKind.CONSTRAINT,
                        title=title,
                        summary=f"拟定规则：{contextual_summary}",
                        status="draft",
                        evidence_refs=evidence_refs,
                        material_ids=material_ids,
                        source_ref_ids=source_ref_ids,
                        selected_card_ids=selected_card_ids,
                    )
                )
            elif role_name == "DecisionSteward":
                raw_title = self._truncate_title(message, "待决策")
                title = raw_title.replace("把", "").replace("整理成需要拍板的", "").replace("待决策", "").replace("决策", "").strip()
                if not title.startswith("决策："):
                    title = f"决策：{title}"
                mutations.append(
                    self._card_mutation(
                        mutation_type="create_decision_request",
                        kind=CanvasCardKind.DECISION,
                        title=title,
                        summary=f"【决策点：为什么需要拍板此项？】\n{contextual_summary}",
                        status="pending",
                        evidence_refs=evidence_refs,
                        material_ids=material_ids,
                        source_ref_ids=source_ref_ids,
                        selected_card_ids=selected_card_ids,
                    )
                )
            elif role_name == "OptionBuilder":
                mutations.append(
                    self._card_mutation(
                        mutation_type="add_card",
                        kind=CanvasCardKind.OPTION,
                        title=f"方案：{self._truncate_title(message, '方案候选')}",
                        summary=contextual_summary,
                        status="draft",
                        evidence_refs=evidence_refs,
                        material_ids=material_ids,
                        source_ref_ids=source_ref_ids,
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
                    evidence_refs=evidence_refs,
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
                            "source_ref_ids": list(source_ref_ids),
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
                                    "source_ref_ids": list(source_ref_ids),
                                    "selected_card_ids": list(selected_card_ids),
                                },
                            }
                        },
                        metadata={"mutation_type": "refresh_handoff_draft"},
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
                "source_ref_ids": list(source_ref_ids),
            },
        )

    def _build_mutation_proposal_with_llm(
        self,
        workspace: CanvasWorkspace,
        turn_id: str,
        message: str,
        plan,
        existing_cards: List[CanvasCard],
        selected_card_ids: List[str],
        material_ids: List[str],
        source_ref_ids: List[str],
        model: Optional[str] = None,
    ) -> CanvasMutationProposal | None:
        import json
        import re
        from app.canvas.domain.cards import CanvasCardKind, CanvasCard
        from app.canvas.domain.mutations import CanvasMutation, CanvasMutationAction, CanvasMutationTarget

        mutations: list[CanvasMutation] = []
        selected_cards = [card for card in existing_cards if card.card_id in set(selected_card_ids)]
        evidence_refs = list(material_ids) + list(source_ref_ids)

        selected_cards_json = json.dumps([c.to_dict() for c in selected_cards], ensure_ascii=False)
        
        # 从全局内存缓存中水合材料具体内容，供协作角色直接读取文件文本
        materials_content_list = []
        try:
            from app.api.server import global_materials_cache, global_source_refs_cache
            for mid in material_ids:
                if mid in global_materials_cache:
                    mat = global_materials_cache[mid]
                    materials_content_list.append(
                        f"--- 材料文件名: {mat['filename']} (ID: {mid}) ---\n{mat['content']}\n"
                    )
            for source_ref_id in source_ref_ids:
                if source_ref_id in global_source_refs_cache:
                    source_ref = global_source_refs_cache[source_ref_id]
                    snapshot = source_ref.get("snapshot", {})
                    materials_content_list.append(
                        f"--- 数据引用: {source_ref.get('display_name', source_ref_id)} (ID: {source_ref_id}) ---\n"
                        f"{snapshot.get('summary', '该数据引用暂无快照摘要。')}\n"
                    )
        except Exception:
            pass
        materials_str = "\n".join(materials_content_list) if materials_content_list else "（无新引入材料内容）"

        for role_name in plan.roles:
            role_instruction = ""
            expected_kind = ""
            expected_mutation_type = ""

            if role_name == "Clarifier":
                expected_kind = "clarification"
                expected_mutation_type = "add_card"
                role_instruction = "你负责发现歧义、缺失信息与冲突，并提出待澄清缺口。请深入提取出至少一个当前最需要向相关方澄清的问题（即不确定性）。"
            elif role_name == "ConstraintSteward":
                expected_kind = "constraint"
                expected_mutation_type = "promote_to_constraint_draft"
                role_instruction = "你负责沉淀业务边界、状态、口径、权限和计费等限制。请深度分析提取出目前应该沉淀的规则约束草稿。"
            elif role_name == "DecisionSteward":
                expected_kind = "decision"
                expected_mutation_type = "create_decision_request"
                role_instruction = "你负责识别必须由 PM 拍板的待决策项，而非单纯的信息缺失。请深度分析并生成待拍板决策卡（要给出备选方案和影响面）。"
            elif role_name == "HandoffBuilder":
                expected_kind = "handoff"
                expected_mutation_type = "refresh_handoff_card"
                role_instruction = "你负责收束结构化交接物草稿。请依据用户的意图和已有的卡片结构，撰写一份结构化交接物的草稿建议。"
            else:
                expected_kind = "evidence"
                expected_mutation_type = "add_card"
                role_instruction = "你负责接收新输入，编译多源材料，提取核心证据。"

            prompt = f"""你是一个需求分析协作 Agent，目前分配给你的角色是: "{role_name}"。
你的职责和指导方针如下:
{role_instruction}

上下文信息:
- 用户输入/对话消息: "{message}"
- 关联被选中卡片: {selected_cards_json}
- 新引入参考材料具体内容如下:
{materials_str}

请基于上述上下文信息进行语义分析与智能归纳，并生成拟建议的画布卡片修改提案（必须是 JSON 格式的 mutations 列表）。
注意：请使用以下拟建议的字段属性：
- 卡片的 kind 必须是: "{expected_kind}"
- mutations 的 mutation_type 必须是: "{expected_mutation_type}"

你必须输出符合以下 JSON 格式的回复，不需要任何 Markdown 包裹或说明：
{{
  "title": "拟建议的卡片标题（15字内，要求精炼）",
  "summary": "提炼出的详细内容摘要（包含核心事实、冲突点、约束规则陈述或待拍板抉择的具体背景）"
}}
"""
            try:
                result = self.llm.invoke(
                    role=role_name,
                    prompt=prompt,
                    context={
                        "title": f"Agent {role_name}",
                        "goal": "Generate canvas mutation proposal",
                        "model": model,
                    }
                )
                raw_content = result.content.strip()
                match = re.search(r"\{.*\}", raw_content, re.DOTALL)
                if match:
                    raw_content = match.group(0)

                card_data = json.loads(raw_content)
                title = card_data["title"]
                summary = card_data["summary"]

                # 构造真正的 CanvasMutation
                if role_name == "HandoffBuilder":
                    handoff_card = CanvasCard(
                        card_id=f"card_{uuid4().hex[:10]}",
                        kind=CanvasCardKind.HANDOFF,
                        title=title,
                        summary=summary,
                        stage="handoff",
                        status="draft",
                        evidence_refs=evidence_refs,
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
                                "source_ref_ids": list(source_ref_ids),
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
                                    "summary": summary,
                                    "constraints": self._handoff_items(existing_cards, CanvasCardKind.CONSTRAINT),
                                    "open_questions": self._handoff_items(existing_cards, CanvasCardKind.CLARIFICATION),
                                    "decisions": self._handoff_items(existing_cards, CanvasCardKind.DECISION),
                                    "metadata": {
                                        "source_turn_id": turn_id,
                                        "material_ids": list(material_ids),
                                        "source_ref_ids": list(source_ref_ids),
                                        "selected_card_ids": list(selected_card_ids),
                                    },
                                }
                            },
                            metadata={"mutation_type": "refresh_handoff_draft"},
                        )
                    )
                else:
                    kind_enum = CanvasCardKind(expected_kind)
                    card_status = "open" if kind_enum in (CanvasCardKind.CLARIFICATION, CanvasCardKind.EVIDENCE, CanvasCardKind.PROBLEM) else "draft"
                    if kind_enum == CanvasCardKind.DECISION:
                        card_status = "pending"

                    mutations.append(
                        self._card_mutation(
                            mutation_type=expected_mutation_type,
                            kind=kind_enum,
                            title=title,
                            summary=summary,
                            status=card_status,
                            evidence_refs=evidence_refs,
                            material_ids=material_ids,
                            source_ref_ids=source_ref_ids,
                            selected_card_ids=selected_card_ids,
                        )
                    )
            except Exception:
                return None

        if not mutations:
            return None

        return CanvasMutationProposal(
            proposal_id=f"proposal_{uuid4().hex[:12]}",
            workspace_id=workspace.workspace_id,
            turn_id=turn_id,
            mutations=mutations,
            metadata={
                "selected_card_ids": list(selected_card_ids),
                "material_ids": list(material_ids),
                "source_ref_ids": list(source_ref_ids),
            },
        )

    def _apply_proposal(self, workspace: CanvasWorkspace, proposal: CanvasMutationProposal) -> None:
        from app.canvas.domain.relations import CanvasRelation, CanvasRelationKind
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
                from app.canvas.domain.cards import CanvasCardKind
                card = CanvasCard.from_dict(mutation.payload["card"])
                
                # 水合 G层 最小治理与验证基线字段
                receipt = dict(proposal.metadata.get("verification_receipt", {}))
                card.metadata["governance_state"] = "proposal"
                card.metadata["verification_state"] = receipt.get("result", "passed")
                card.metadata["source_summary"] = card.summary[:100] if card.summary else ""
                
                if card.kind == CanvasCardKind.CONSTRAINT:
                    card.metadata.setdefault("stability_source", "raw_compiler")
                    card.metadata.setdefault("impact_scope", "general")
                    card.metadata.setdefault("review_risk", False)
                elif card.kind == CanvasCardKind.DECISION:
                    card.metadata.setdefault("confirmation_source", "")
                    card.metadata.setdefault("current_stable_status", "proposal")

                card_index[card.card_id] = card
                latest_card_id = card.card_id
            elif mutation.target == CanvasMutationTarget.CARD and mutation.action == CanvasMutationAction.UPDATE:
                card = card_index.get(mutation.target_id)
                if card is None:
                    continue

                # 检查是否修改了已确认的稳定事实卡片核心字段（冲突替代留痕）
                title_changed = "title" in mutation.payload and mutation.payload["title"] is not None and str(mutation.payload["title"]).strip() != card.title.strip()
                summary_changed = "summary" in mutation.payload and mutation.payload["summary"] is not None and str(mutation.payload["summary"]).strip() != card.summary.strip()
                is_stable = card.status in {"confirmed", "effective", "resolved"}

                if is_stable and (title_changed or summary_changed):
                    import copy
                    new_card_id = f"card_{uuid4().hex[:10]}"
                    new_card = copy.deepcopy(card)
                    new_card.card_id = new_card_id
                    
                    if "title" in mutation.payload:
                        new_card.title = str(mutation.payload["title"])
                    if "summary" in mutation.payload:
                        new_card.summary = str(mutation.payload["summary"])
                    if "stage" in mutation.payload:
                        new_card.stage = str(mutation.payload["stage"])
                    if "status" in mutation.payload:
                        new_card.status = str(mutation.payload["status"])
                    else:
                        new_card.status = "confirmed"
                    if "tags" in mutation.payload:
                        new_card.tags = [str(tag) for tag in mutation.payload["tags"]]
                    if "metadata" in mutation.payload:
                        new_card.metadata = {**new_card.metadata, **dict(mutation.payload["metadata"])}
                    
                    # 记录相互替代关系与治理水合
                    new_card.metadata["supersedes"] = card.card_id
                    new_card.metadata["governance_state"] = "confirmed"
                    new_card.metadata["verification_state"] = "passed"
                    new_card.metadata["source_summary"] = new_card.summary[:100] if new_card.summary else ""
                    
                    card.status = "superseded"
                    card.metadata["governance_state"] = "superseded"
                    card.metadata["superseded_by"] = new_card_id

                    card_index[card.card_id] = card
                    card_index[new_card_id] = new_card
                    latest_card_id = new_card_id

                    # 建立 DERIVED_FROM 替代追溯关系
                    supersede_relation = CanvasRelation(
                        relation_id=f"rel_{uuid4().hex[:10]}",
                        kind=CanvasRelationKind.DERIVED_FROM,
                        from_card_id=card.card_id,
                        to_card_id=new_card_id,
                        metadata={"source_proposal_id": proposal.proposal_id, "relation_type": "supersede_tracking"}
                    )
                    relation_index[supersede_relation.relation_id] = supersede_relation
                else:
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
                    
                    # 水合治理状态
                    if card.status in {"confirmed", "effective", "resolved"}:
                        card.metadata["governance_state"] = "confirmed"
                        card.metadata["verification_state"] = "passed"
                    else:
                        card.metadata["governance_state"] = "proposal"
                    card.metadata["source_summary"] = card.summary[:100] if card.summary else ""

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
            latest_card = card_index.get(latest_card_id)
            for selected_card_id in proposal.metadata.get("selected_card_ids", []):
                selected_card = card_index.get(selected_card_id)
                rel_kind = CanvasRelationKind.DERIVED_FROM
                if selected_card and latest_card:
                    selected_kind_str = selected_card.kind.value if hasattr(selected_card.kind, "value") else str(selected_card.kind)
                    latest_kind_str = latest_card.kind.value if hasattr(latest_card.kind, "value") else str(latest_card.kind)
                    if selected_kind_str in ("option", "decision") and latest_kind_str in ("problem", "clarification"):
                        rel_kind = CanvasRelationKind.REOPENS
                relation = CanvasRelation(
                    relation_id=f"rel_{uuid4().hex[:10]}",
                    kind=rel_kind,
                    from_card_id=selected_card_id,
                    to_card_id=latest_card_id,
                    metadata={"source_proposal_id": proposal.proposal_id},
                )
                relation_index[relation.relation_id] = relation

        relations = list(relation_index.values())
        self.repository.save_cards(workspace.workspace_id, cards)
        self.repository.save_relations(workspace.workspace_id, relations)
        if handoff is not None:
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
            handoff.metadata = {
                **dict(handoff.metadata or {}),
                **build_handoff_metadata(
                    cards,
                    confirmation_state="draft",
                    source_snapshot_id=snapshot.snapshot_id,
                    refreshed_by="canvas_agent",
                    refreshed_at=snapshot.created_at,
                ),
            }
            self.repository.save_handoff(workspace.workspace_id, handoff)
            self.repository.save_snapshot(workspace.workspace_id, snapshot)
            workspace.handoff_status = "draft"
            workspace.handoff_metadata = {
                **dict(workspace.handoff_metadata),
                **dict(handoff.metadata),
            }
            workspace.active_snapshot_id = snapshot.snapshot_id
        self._touch_workspace(workspace)

    def _card_mutation(
        self,
        mutation_type: str,
        kind: CanvasCardKind,
        title: str,
        summary: str,
        status: str = "open",
        evidence_refs: Optional[List[str]] = None,
        material_ids: Optional[List[str]] = None,
        source_ref_ids: Optional[List[str]] = None,
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
                "material_ids": list(material_ids or []),
                "source_ref_ids": list(source_ref_ids or []),
            },
        )

    def _build_todo_projection(self, workspace_id: str, cards: List[CanvasCard]) -> TodoProjection:
        items: list[TodoItem] = []
        for card in cards:
            is_todo = False
            if card.status in {"open", "draft", "pending"} and card.kind in {
                CanvasCardKind.CLARIFICATION,
                CanvasCardKind.CONSTRAINT,
                CanvasCardKind.DECISION,
            }:
                is_todo = True
            elif card.kind == CanvasCardKind.OPTION and card.status in {"blocked", "pending"}:
                is_todo = True
            elif card.status == "blocked":
                is_todo = True
                
            if is_todo:
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

    def _touch_workspace(
        self,
        workspace: CanvasWorkspace,
        initialize_missing_only: bool = False,
    ) -> CanvasWorkspace:
        """刷新工作区时间戳，确保最近项目列表可以稳定反映最近编辑状态。"""

        now = utc_now_iso()
        if not workspace.created_at:
            workspace.created_at = now
        if initialize_missing_only:
            if not workspace.updated_at:
                workspace.updated_at = workspace.created_at or now
        else:
            workspace.updated_at = now
        ensure_workspace_runtime_defaults(workspace)
        self.repository.save_workspace(workspace)
        return workspace

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
        visible_statuses = {
            CanvasCardKind.CLARIFICATION: {"open", "draft", "pending"},
            CanvasCardKind.CONSTRAINT: {"draft", "effective", "confirmed"},
            CanvasCardKind.DECISION: {"pending", "confirmed"},
            CanvasCardKind.HANDOFF: {"draft", "confirmed"},
            CanvasCardKind.EVIDENCE: {"open", "draft", "confirmed"},
            CanvasCardKind.PROBLEM: {"open", "draft", "confirmed"},
            CanvasCardKind.OPTION: {"open", "draft", "confirmed"},
        }
        allowed = visible_statuses.get(kind, {"open", "draft", "pending"})
        return [card.title for card in cards if card.kind == kind and card.status in allowed]

    def _build_handoff_summary(self, message: str, cards: List[CanvasCard]) -> str:
        clarifications = self._handoff_items(cards, CanvasCardKind.CLARIFICATION)
        constraints = self._handoff_items(cards, CanvasCardKind.CONSTRAINT)
        return (
            f"基于当前回合收束的结构化交接物草稿：{message}"
            f"；待澄清 {len(clarifications)} 项，约束 {len(constraints)} 项。"
        )

    def _build_refresh_handoff_summary(self, cards: List[CanvasCard]) -> str:
        problems = [card.title for card in cards if card.kind == CanvasCardKind.PROBLEM]
        clarifications = self._handoff_items(cards, CanvasCardKind.CLARIFICATION)
        constraints = self._handoff_items(cards, CanvasCardKind.CONSTRAINT)
        decisions = self._handoff_items(cards, CanvasCardKind.DECISION)
        options = [card.title for card in cards if card.kind == CanvasCardKind.OPTION]
        
        problem_str = f"主问题：{problems[0]}" if problems else "暂无主问题"
        option_str = f"方案候选：{', '.join(options)}" if options else "暂无方案候选"
        
        return (
            "基于当前画布收束的结构化交接物草稿：\n" +
            f"【{problem_str}】\n" +
            f"待澄清 {len(clarifications)} 项，约束 {len(constraints)} 项，待决策 {len(decisions)} 项。\n" +
            f"【{option_str}】"
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

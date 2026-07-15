"""EvoCanvas 工作区应用服务。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.canvas.agent.supervisor import CanvasSupervisor
from app.canvas.domain.cards import CanvasCard, CanvasCardKind
from app.canvas.domain.confirmation import (
    ConfirmationKind,
    ConfirmationPath,
    ConfirmationRecord,
    ConfirmedClaim,
)
from app.canvas.domain.handoff import StructuredHandoff, TodoItem, TodoProjection
from app.canvas.domain.ledger import LedgerActorType, LedgerEvent, LedgerEventType
from app.canvas.domain.object_status import (
    InitialGovernanceStatus,
    ValidationState,
    default_status_for_kind,
    is_stable_status,
    is_unresolved_status,
)
from app.canvas.domain.package import Package, PackageVersion
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


class CanvasCardConfirmationRequiredError(ValueError):
    """表示稳定态卡片的语义修订必须回到普通 Chat 确认。"""


class CanvasRelationValidationError(ValueError):
    """表示画布关系请求引用了不存在的卡片或非法关系类型。"""


class CanvasRelationNotFoundError(KeyError):
    """表示请求删除的画布关系不存在。"""


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
        # L3 规格：新工作区尚未形成包版本时交接状态为 not_ready；
        # 后续状态由当前 PackageVersion.initial_governance_status 派生。
        workspace = CanvasWorkspace(
            workspace_id=workspace_id,
            title=f"EvoCanvas Workspace {workspace_id}",
            objective="从多源输入中收敛待澄清、约束、待决策与结构化交接物。",
            handoff_status="not_ready",
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
            # L3 规格已下线 StructuredHandoff.summary；优先用 metadata.legacy.summary 兼容旧持久化，
            # 缺失时回退到 workspace.objective，避免最近项目视图出现空白摘要。
            summary = ""
            if handoff is not None:
                legacy = dict(handoff.metadata or {}).get("legacy", {})
                summary = str(legacy.get("summary", "")).strip()
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
                    "handoff_status": self._handoff_status(workspace.workspace_id),
                    "summary_preview": summary[:140],
                    "cover_mode": "placeholder",
                    # L3 规格已废弃 stage 字段；改暴露 kind 与派生治理地位，供视图分组。
                    "cards": [
                        {
                            "kind": card.kind.value if hasattr(card.kind, "value") else str(card.kind),
                            "governance_class": card.governance_class,
                        }
                        for card in self.repository.load_cards(workspace.workspace_id)
                    ],
                }
            )
        return {"items": items}

    def get_canvas_view(self, workspace_id: str, snapshot_id: Optional[str] = None) -> Dict[str, Any]:
        workspace, cards, relations, snapshot = self._load_canvas_state(workspace_id, snapshot_id=snapshot_id)
        todo_projection = self._build_todo_projection(workspace_id, cards)
        handoff = snapshot.handoff if snapshot is not None else self.repository.load_handoff(workspace_id)
        handoff_status = self._handoff_status(workspace_id, handoff=handoff)

        return {
            "workspace_id": workspace.workspace_id,
            "snapshot_id": snapshot.snapshot_id if snapshot else workspace.active_snapshot_id or None,
            "active_turn": self._serialize_active_turn(workspace),
            "cards": [card.to_dict() for card in cards],
            "relations": [relation.to_dict() for relation in relations],
            "todo_projection": todo_projection.to_dict(),
            "pending_confirmations_count": 0,
            "view_meta": build_canvas_view_meta(
                workspace,
                pending_confirmation_ids=[],
                handoff=handoff,
                is_snapshot=snapshot is not None,
                handoff_status=handoff_status,
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
            user_message = self.repository.append_chat_message(
                workspace_id,
                {
                    "message_id": f"msg_{uuid4().hex[:12]}",
                    "role": "user",
                    "content": message,
                    "turn_id": turn_id,
                    "created_at": utc_now_iso(),
                },
            )
            pending_proposal = self._latest_chat_confirmation_proposal(workspace_id)
            if pending_proposal is not None and self._is_explicit_confirmation(message):
                return self._apply_chat_confirmation(
                    workspace,
                    turn_id,
                    pending_proposal,
                    user_message_ref=str(user_message["message_id"]),
                )
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
            assistant_message = self.repository.append_chat_message(
                workspace_id,
                {
                    "message_id": f"msg_{uuid4().hex[:12]}",
                    "role": "assistant",
                    "content": self._proposal_message_content(proposal),
                    "turn_id": turn_id,
                    "created_at": utc_now_iso(),
                },
            )
            proposal.metadata["assistant_message_ref"] = assistant_message["message_id"]
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
                pending_gate_ids=[],
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
            elif outcome.action == "awaiting_chat_confirmation":
                # 提议已记录为普通 Chat 消息，下一条用户消息可确认、否定或修正。
                pass
            else:
                # 验证失败情况 (downgrade_to_proposal 或 awaiting_clarification)
                # 不应用提案，也不用挂起，回合由于错误直接结束
                pass

            event_type = "canvas.mutation.applied"
            if outcome.action == "awaiting_chat_confirmation":
                event_type = "canvas.chat_confirmation.requested"
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
        self.get_workspace(workspace_id)
        handoff = self.repository.load_handoff(workspace_id)
        if handoff is None:
            handoff = StructuredHandoff(
                handoff_id=f"handoff_{workspace_id}",
            )
        # L3 规格要求交接模块不复制对象正文；此处 content 仅作过渡期前端兼容回显，
        # 真正内容应通过 handoff.*_refs 回指源对象渲染。
        legacy_summary = str(dict(handoff.metadata or {}).get("legacy", {}).get("summary", ""))
        return {
            "workspace_id": workspace_id,
            "status": self._handoff_status(workspace_id, handoff=handoff),
            "content": legacy_summary,
            "handoff": handoff.to_dict(),
        }

    def _handoff_status(
        self,
        workspace_id: str,
        *,
        handoff: Optional[StructuredHandoff] = None,
    ) -> str:
        """从当前包版本派生交接状态，不再读取工作区覆盖式状态字段。"""

        version = self.repository.load_active_package_version(workspace_id)
        effective_handoff = handoff if handoff is not None else self.repository.load_handoff(workspace_id)
        if version is None or effective_handoff is None:
            return "not_ready"
        return version.initial_governance_status.value

    def refresh_handoff(self, workspace_id: str) -> Dict[str, Any]:
        """基于当前画布状态重新收束结构化交接物草稿，并落一份新快照。"""

        workspace = self.get_workspace(workspace_id)
        active_turn = self._serialize_active_turn(workspace)
        if active_turn is not None:
            raise CanvasTurnInProgressError(workspace_id, active_turn)

        cards = self.repository.load_cards(workspace_id)
        relations = self.repository.load_relations(workspace_id)
        refreshed_at = utc_now_iso()
        # L3 规格要求交接模块只持有对象引用，不复制对象正文。
        # 此处依据当前画布卡片类型化状态派生引用集合，正文由源对象维护。
        handoff = StructuredHandoff(
            handoff_id=f"handoff_{workspace_id}",
            confirmed_constraint_refs=[
                card.card_id
                for card in cards
                if card.kind == CanvasCardKind.CONSTRAINT
                and card.status == "effective"
            ],
            completed_decision_refs=[
                card.card_id
                for card in cards
                if card.kind == CanvasCardKind.DECISION and card.status == "decided"
            ],
            unresolved_refs=unresolved_issue_ids_from_cards(cards),
            pending_decision_refs=[
                card.card_id
                for card in cards
                if card.kind == CanvasCardKind.DECISION
                and card.status in {"pending_decision", "pending_confirmation"}
            ],
            key_source_refs=[
                ref
                for card in cards
                if card.kind == CanvasCardKind.EVIDENCE
                for ref in list(card.source_refs)
            ],
            metadata={
                "legacy": {
                    "summary": self._build_refresh_handoff_summary(cards),
                }
            },
        )
        todo_projection = self._build_todo_projection(workspace_id, cards)
        snapshot = CanvasSnapshot(
            snapshot_id=f"snapshot_{uuid4().hex[:10]}",
            workspace_id=workspace_id,
            title="结构化交接物草稿已刷新",
            summary=dict(handoff.metadata or {}).get("legacy", {}).get("summary", ""),
            created_at=refreshed_at,
            active_card_ids=[card.card_id for card in cards],
            active_relation_ids=[relation.relation_id for relation in relations],
            cards=list(cards),
            relations=list(relations),
            todo_projection=todo_projection,
            handoff=handoff,
            metadata={"created_by": "user", "source": "handoff_refresh"},
        )

        handoff.metadata = {
            **dict(handoff.metadata or {}),
            **build_handoff_metadata(
                cards,
                confirmation_state="draft",
                source_snapshot_id=snapshot.snapshot_id,
                refreshed_by="user",
                refreshed_at=refreshed_at,
            ),
        }
        self.repository.save_snapshot(workspace_id, snapshot)
        workspace.active_snapshot_id = snapshot.snapshot_id
        proposal = CanvasMutationProposal(
            proposal_id=f"proposal_{uuid4().hex[:12]}",
            workspace_id=workspace_id,
            turn_id=f"turn_handoff_refresh_{uuid4().hex[:8]}",
            mutations=[
                CanvasMutation(
                    mutation_id=f"mutation_{uuid4().hex[:10]}",
                    action=CanvasMutationAction.UPDATE,
                    target=CanvasMutationTarget.HANDOFF,
                    target_id=handoff.handoff_id,
                    payload={"handoff": handoff.to_dict()},
                    metadata={"mutation_type": "refresh_handoff_draft"},
                )
            ],
            status=CanvasMutationStatus.APPLIED,
            metadata={"user_edit": True},
        )
        self._commit_canvas_state(workspace, cards, relations, handoff, proposal, None)
        self.repository.append_proposal_history(workspace_id, proposal)
        self._touch_workspace(workspace)
        self._publish_event(
            workspace_id,
            "canvas.handoff.refreshed",
            {
                "workspace_id": workspace_id,
                "snapshot_id": snapshot.snapshot_id,
                "handoff": handoff.to_dict(),
                "card_id": None,
            },
            status="refreshed",
        )
        return {
            "workspace_id": workspace_id,
            "status": "draft",
            "content": dict(handoff.metadata or {}).get("legacy", {}).get("summary", ""),
            "handoff": handoff.to_dict(),
            "card": None,
            "snapshot": snapshot.to_dict(),
            "todo_projection": todo_projection.to_dict(),
        }

    def get_todos(self, workspace_id: str, snapshot_id: Optional[str] = None) -> Dict[str, Any]:
        """返回当前画布时态下的活跃缺口投影。"""

        _, cards, _, _ = self._load_canvas_state(workspace_id, snapshot_id=snapshot_id)
        return self._build_todo_projection(workspace_id, cards).to_dict()

    def patch_card(self, workspace_id: str, card_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        """提交展示字段修订；业务状态只能经受控提案和确认记录升级。"""

        workspace = self.get_workspace(workspace_id)
        cards = self.repository.load_cards(workspace_id)
        if "status" in patch:
            raise ValueError("canvas card status is not directly writable")
        # L3 规格要求对象类型不可通过 patch 修改：待澄清卡不得通过改类型变成约束卡
        # 或待决策卡，澄清结果应创建或更新关联的结果对象并保留原对象身份。
        if "kind" in patch:
            raise ValueError("canvas card kind is not directly writable")
        updated_card = None
        for card in cards:
            if card.card_id != card_id:
                continue
            title_changed = (
                "title" in patch
                and patch["title"] is not None
                and str(patch["title"]).strip() != card.title.strip()
            )
            summary_changed = (
                "summary" in patch
                and patch["summary"] is not None
                and str(patch["summary"]).strip() != card.summary.strip()
            )
            kind_value = card.kind.value if hasattr(card.kind, "value") else str(card.kind)
            if is_stable_status(kind_value, card.status) and (title_changed or summary_changed):
                raise CanvasCardConfirmationRequiredError(
                    "稳定态卡片的标题或摘要修改需要在普通 Chat 中明确确认。"
                )
            if "title" in patch and patch["title"] is not None:
                card.title = str(patch["title"]).strip()
            if "summary" in patch and patch["summary"] is not None:
                card.summary = str(patch["summary"]).strip()
            if "tags" in patch and patch["tags"] is not None:
                card.tags = [str(tag).strip() for tag in patch["tags"] if str(tag).strip()]
            card.metadata["last_edited_by"] = "user"
            card.metadata["last_edited_at"] = utc_now_iso()
            updated_card = card
            break

        if updated_card is None:
            raise CanvasCardNotFoundError(card_id)

        proposal = CanvasMutationProposal(
            proposal_id=f"proposal_{uuid4().hex[:12]}",
            workspace_id=workspace_id,
            turn_id=f"turn_user_edit_{uuid4().hex[:8]}",
            mutations=[
                CanvasMutation(
                    mutation_id=f"mutation_{uuid4().hex[:10]}",
                    action=CanvasMutationAction.UPDATE,
                    target=CanvasMutationTarget.CARD,
                    target_id=card_id,
                    payload={
                        "title": updated_card.title,
                        "summary": updated_card.summary,
                        "tags": list(updated_card.tags),
                    },
                    metadata={"mutation_type": "user_display_edit"},
                )
            ],
            status=CanvasMutationStatus.APPLIED,
            metadata={"user_edit": True},
        )
        self._commit_canvas_state(
            workspace,
            cards,
            self.repository.load_relations(workspace_id),
            self.repository.load_handoff(workspace_id),
            proposal,
            None,
        )
        self.repository.append_proposal_history(workspace_id, proposal)
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

    def create_card(
        self,
        workspace_id: str,
        kind: str,
        title: str,
        summary: str = "",
        tags: Optional[List[str]] = None,
        source_refs: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """用户在画布上直接新增卡片。

        L3 规格：对象类型不可绕过校验，kind 必须是五类合法枚举之一；
        status 取该类型的默认初始状态，不允许调用方传入。
        本方法只承载展示字段，不涉及业务状态升级，故无需 Chat 确认。
        metadata 仅承载展示辅助信息（如 section_hint），不写入业务状态。
        """

        workspace = self.get_workspace(workspace_id)
        # 拒绝旧 handoff/option 等已下线类型，强制走 L3 五类合法枚举
        try:
            card_kind = CanvasCardKind(kind)
        except ValueError as exc:
            raise ValueError(f"unsupported canvas card kind: {kind}") from exc
        card_metadata = {"created_by": "user", "source": "manual_create"}
        if metadata:
            card_metadata.update(metadata)
        card = CanvasCard(
            card_id=f"card_{uuid4().hex[:10]}",
            kind=card_kind,
            title=str(title).strip(),
            summary=str(summary or "").strip(),
            tags=[str(tag).strip() for tag in (tags or []) if str(tag).strip()],
            source_refs=list(source_refs or []),
            metadata=card_metadata,
        )
        cards = self.repository.load_cards(workspace_id)
        cards.append(card)
        proposal = CanvasMutationProposal(
            proposal_id=f"proposal_{uuid4().hex[:12]}",
            workspace_id=workspace_id,
            turn_id=f"turn_user_create_{uuid4().hex[:8]}",
            mutations=[
                CanvasMutation(
                    mutation_id=f"mutation_{uuid4().hex[:10]}",
                    action=CanvasMutationAction.ADD,
                    target=CanvasMutationTarget.CARD,
                    target_id=card.card_id,
                    payload={"card": card.to_dict()},
                    metadata={"mutation_type": "user_manual_create"},
                )
            ],
            status=CanvasMutationStatus.APPLIED,
            metadata={"user_edit": True},
        )
        self._commit_canvas_state(
            workspace,
            cards,
            self.repository.load_relations(workspace_id),
            self.repository.load_handoff(workspace_id),
            proposal,
            None,
        )
        self.repository.append_proposal_history(workspace_id, proposal)
        todo_projection = self._build_todo_projection(workspace_id, cards)
        self._touch_workspace(workspace)
        self._publish_event(
            workspace_id,
            "canvas.card.created",
            {
                "workspace_id": workspace_id,
                "card_id": card.card_id,
                "card": card.to_dict(),
            },
            status="created",
        )
        return {
            "workspace_id": workspace_id,
            "card": card.to_dict(),
            "todo_projection": todo_projection.to_dict(),
        }

    def delete_card(self, workspace_id: str, card_id: str) -> Dict[str, Any]:
        """用户在画布上直接删除卡片。

        L3 规格：对象不物理删除，按 kind 派生 archive/superseded 终态；
        稳定态卡片删除视为治理动作，仍走终态归档以保留可追溯性。
        关联关系在归档后由调用方或后续回合清理，本方法只负责对象状态。
        """

        workspace = self.get_workspace(workspace_id)
        cards = self.repository.load_cards(workspace_id)
        target_card: Optional[CanvasCard] = None
        for card in cards:
            if card.card_id == card_id:
                target_card = card
                break
        if target_card is None:
            raise CanvasCardNotFoundError(card_id)
        kind_value = (
            target_card.kind.value if hasattr(target_card.kind, "value") else str(target_card.kind)
        )
        # 约束卡归档走 superseded，其余走 archived，与稳定态替代规则一致
        if kind_value == "constraint":
            target_card.status = "superseded"
        else:
            target_card.status = "archived"
        target_card.metadata = {
            **dict(target_card.metadata or {}),
            "archived_by": "user",
            "archived_at": utc_now_iso(),
        }
        proposal = CanvasMutationProposal(
            proposal_id=f"proposal_{uuid4().hex[:12]}",
            workspace_id=workspace_id,
            turn_id=f"turn_user_delete_{uuid4().hex[:8]}",
            mutations=[
                CanvasMutation(
                    mutation_id=f"mutation_{uuid4().hex[:10]}",
                    action=CanvasMutationAction.UPDATE,
                    target=CanvasMutationTarget.CARD,
                    target_id=card_id,
                    payload={"status": target_card.status, "metadata": dict(target_card.metadata)},
                    metadata={"mutation_type": "user_manual_delete"},
                )
            ],
            status=CanvasMutationStatus.APPLIED,
            metadata={"user_edit": True},
        )
        self._commit_canvas_state(
            workspace,
            cards,
            self.repository.load_relations(workspace_id),
            self.repository.load_handoff(workspace_id),
            proposal,
            None,
        )
        self.repository.append_proposal_history(workspace_id, proposal)
        todo_projection = self._build_todo_projection(workspace_id, cards)
        self._touch_workspace(workspace)
        self._publish_event(
            workspace_id,
            "canvas.card.deleted",
            {
                "workspace_id": workspace_id,
                "card_id": card_id,
                "card": target_card.to_dict(),
            },
            status="deleted",
        )
        return {
            "workspace_id": workspace_id,
            "card_id": card_id,
            "card": target_card.to_dict(),
            "todo_projection": todo_projection.to_dict(),
        }

    def list_chat_confirmation_proposals(
        self, workspace_id: str
    ) -> Dict[str, Any]:
        """返回当前所有尚待普通 Chat 明确确认的高影响提议投影。

        仅作只读投影，不产生新的确认路径；确认仍由普通 Chat 消息触发。
        """

        self.get_workspace(workspace_id)
        items: List[Dict[str, Any]] = []
        for proposal in self.repository.load_proposal_history(workspace_id):
            if (
                proposal.status == CanvasMutationStatus.PENDING_CONFIRMATION
                and proposal.metadata.get("awaiting_chat_confirmation")
            ):
                items.append(
                    {
                        "proposal_id": proposal.proposal_id,
                        "turn_id": proposal.turn_id,
                        "risk_level": proposal.risk_level.value,
                        "mutations": [mutation.to_dict() for mutation in proposal.mutations],
                        "metadata": dict(proposal.metadata),
                    }
                )
        return {"workspace_id": workspace_id, "items": items}

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

        workspace = self.get_workspace(workspace_id)
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
        proposal = CanvasMutationProposal(
            proposal_id=f"proposal_{uuid4().hex[:12]}",
            workspace_id=workspace_id,
            turn_id=f"turn_user_relation_{uuid4().hex[:8]}",
            mutations=[
                CanvasMutation(
                    mutation_id=f"mutation_{uuid4().hex[:10]}",
                    action=CanvasMutationAction.ADD,
                    target=CanvasMutationTarget.RELATION,
                    target_id=relation.relation_id,
                    payload={"relation": relation.to_dict()},
                    metadata={"mutation_type": "user_create_relation"},
                )
            ],
            status=CanvasMutationStatus.APPLIED,
            metadata={"user_edit": True},
        )
        self._commit_canvas_state(
            workspace,
            cards,
            relations,
            self.repository.load_handoff(workspace_id),
            proposal,
            None,
        )
        self.repository.append_proposal_history(workspace_id, proposal)
        self._touch_workspace(workspace)
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

        workspace = self.get_workspace(workspace_id)
        cards = self.repository.load_cards(workspace_id)
        relations = self.repository.load_relations(workspace_id)
        remaining_relations = [relation for relation in relations if relation.relation_id != relation_id]
        if len(remaining_relations) == len(relations):
            raise CanvasRelationNotFoundError(relation_id)

        proposal = CanvasMutationProposal(
            proposal_id=f"proposal_{uuid4().hex[:12]}",
            workspace_id=workspace_id,
            turn_id=f"turn_user_relation_{uuid4().hex[:8]}",
            mutations=[
                CanvasMutation(
                    mutation_id=f"mutation_{uuid4().hex[:10]}",
                    action=CanvasMutationAction.REMOVE,
                    target=CanvasMutationTarget.RELATION,
                    target_id=relation_id,
                    metadata={"mutation_type": "user_delete_relation"},
                )
            ],
            status=CanvasMutationStatus.APPLIED,
            metadata={"user_edit": True},
        )
        self._commit_canvas_state(
            workspace,
            cards,
            remaining_relations,
            self.repository.load_handoff(workspace_id),
            proposal,
            None,
        )
        self.repository.append_proposal_history(workspace_id, proposal)
        self._touch_workspace(workspace)
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
        """已废弃：L3 规格下线 stage_node 主题阶段机后，卡片不再有 stage 字段。

        为避免破坏迁移期调用方，本方法保留 API 签名但不再持久化 stage 请求，
        也不触发事件或版本提交。调用方应迁移到受治理的 Chat 提案与确认流程。
        """

        workspace = self.get_workspace(workspace_id)
        cards = self.repository.load_cards(workspace_id)
        card = next((item for item in cards if item.card_id == card_id), None)
        if card is None:
            raise CanvasCardNotFoundError(card_id)

        todo_projection = self._build_todo_projection(workspace_id, cards)
        return {
            "workspace_id": workspace_id,
            "action": "deprecated_noop",
            "card": card.to_dict(),
            "move": {
                "from_stage": "",
                "to_stage": stage,
                "reason": reason.strip(),
                "semantic_change": False,
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
        # L3 规格已将 evidence_refs 统一为 source_refs；保留局部变量名以便回看。
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
                        source_refs=evidence_refs,
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
                        source_refs=evidence_refs,
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
                        source_refs=evidence_refs,
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
                        source_refs=evidence_refs,
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
                        status="pending_decision",
                        source_refs=evidence_refs,
                        material_ids=material_ids,
                        source_ref_ids=source_ref_ids,
                        selected_card_ids=selected_card_ids,
                    )
                )
            # L3 规格已下线 OptionBuilder 角色（option 不纳入 1.0 对象类型），
            # 也不再为 HandoffBuilder 创建 HANDOFF 卡片：交接模块只通过引用组织对象。
            elif role_name == "HandoffBuilder":
                # 只生成 refresh_handoff_draft 变更，正文由源对象维护；
                # legacy 摘要写入 metadata.legacy.summary 仅供过渡期前端回看。
                mutations.append(
                    CanvasMutation(
                        mutation_id=f"mutation_{uuid4().hex[:10]}",
                        action=CanvasMutationAction.UPDATE,
                        target=CanvasMutationTarget.HANDOFF,
                        target_id="handoff_draft",
                        payload={
                            "handoff": {
                                "handoff_id": f"handoff_{workspace.workspace_id}",
                                "confirmed_constraint_refs": [
                                    card.card_id
                                    for card in existing_cards
                                    if card.kind == CanvasCardKind.CONSTRAINT
                                    and card.status == "effective"
                                ],
                                "completed_decision_refs": [
                                    card.card_id
                                    for card in existing_cards
                                    if card.kind == CanvasCardKind.DECISION and card.status == "decided"
                                ],
                                "unresolved_refs": unresolved_issue_ids_from_cards(existing_cards),
                                "pending_decision_refs": [
                                    card.card_id
                                    for card in existing_cards
                                    if card.kind == CanvasCardKind.DECISION
                                    and card.status in {"pending_decision", "pending_confirmation"}
                                ],
                                "metadata": {
                                    "legacy": {
                                        "summary": self._build_handoff_summary(message, existing_cards),
                                    },
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
                # L3 规格已下线 HANDOFF 卡片；交接模块只生成 refresh_handoff_draft 变更。
                expected_kind = ""
                expected_mutation_type = "refresh_handoff_draft"
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
                    # L3 规格已下线 HANDOFF 卡片；只生成 refresh_handoff_draft 变更，
                    # 正文由源对象维护，legacy 摘要写入 metadata.legacy.summary 供过渡期回看。
                    mutations.append(
                        CanvasMutation(
                            mutation_id=f"mutation_{uuid4().hex[:10]}",
                            action=CanvasMutationAction.UPDATE,
                            target=CanvasMutationTarget.HANDOFF,
                            target_id="handoff_draft",
                            payload={
                                "handoff": {
                                    "handoff_id": f"handoff_{workspace.workspace_id}",
                                    "confirmed_constraint_refs": [
                                        card.card_id
                                        for card in existing_cards
                                        if card.kind == CanvasCardKind.CONSTRAINT
                                        and card.status == "effective"
                                    ],
                                    "completed_decision_refs": [
                                        card.card_id
                                        for card in existing_cards
                                        if card.kind == CanvasCardKind.DECISION and card.status == "decided"
                                    ],
                                    "unresolved_refs": unresolved_issue_ids_from_cards(existing_cards),
                                    "pending_decision_refs": [
                                        card.card_id
                                        for card in existing_cards
                                        if card.kind == CanvasCardKind.DECISION
                                        and card.status in {"pending_decision", "pending_confirmation"}
                                    ],
                                    "metadata": {
                                        "legacy": {
                                            "summary": summary,
                                        },
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
                        card_status = "pending_decision"

                    mutations.append(
                        self._card_mutation(
                            mutation_type=expected_mutation_type,
                            kind=kind_enum,
                            title=title,
                            summary=summary,
                            status=card_status,
                            source_refs=evidence_refs,
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

    def _apply_proposal(
        self,
        workspace: CanvasWorkspace,
        proposal: CanvasMutationProposal,
        confirmation: Optional[ConfirmationRecord] = None,
    ) -> None:
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
                
                # 验证结果独立写入 validation_state；禁止在 metadata 维护第二套治理状态。
                receipt = dict(proposal.metadata.get("verification_receipt", {}))
                card.validation_state = (
                    ValidationState.VALID.value
                    if receipt.get("result", "passed") == "passed"
                    else ValidationState.WARNING.value
                )
                
                if card.kind == CanvasCardKind.CONSTRAINT:
                    card.metadata.setdefault("stability_source", "raw_compiler")
                    card.metadata.setdefault("impact_scope", "general")
                    card.metadata.setdefault("review_risk", False)
                elif card.kind == CanvasCardKind.DECISION:
                    card.metadata.setdefault("confirmation_source", "")

                card_index[card.card_id] = card
                latest_card_id = card.card_id
            elif mutation.target == CanvasMutationTarget.CARD and mutation.action == CanvasMutationAction.UPDATE:
                card = card_index.get(mutation.target_id)
                if card is None:
                    continue

                # 检查是否修改了已确认的稳定事实卡片核心字段（冲突替代留痕）
                title_changed = "title" in mutation.payload and mutation.payload["title"] is not None and str(mutation.payload["title"]).strip() != card.title.strip()
                summary_changed = "summary" in mutation.payload and mutation.payload["summary"] is not None and str(mutation.payload["summary"]).strip() != card.summary.strip()
                # L3 规格下稳定态由 (kind, status) 派生，替代旧自由字符串集合。
                kind_value = card.kind.value if hasattr(card.kind, "value") else str(card.kind)
                is_stable = is_stable_status(kind_value, card.status)

                if is_stable and (title_changed or summary_changed):
                    import copy
                    new_card_id = f"card_{uuid4().hex[:10]}"
                    new_card = copy.deepcopy(card)
                    new_card.card_id = new_card_id

                    if "title" in mutation.payload:
                        new_card.title = str(mutation.payload["title"])
                    if "summary" in mutation.payload:
                        new_card.summary = str(mutation.payload["summary"])
                    # L3 规格已下线 stage 字段；忽略 mutation.payload["stage"]，
                    # 不再写入卡片业务状态。
                    if "status" in mutation.payload:
                        new_card.status = str(mutation.payload["status"])
                    else:
                        new_card.status = card.status
                    if "tags" in mutation.payload:
                        new_card.tags = [str(tag) for tag in mutation.payload["tags"]]
                    if "metadata" in mutation.payload:
                        new_card.metadata = {**new_card.metadata, **dict(mutation.payload["metadata"])}
                    
                    # 记录相互替代关系；通用治理地位始终由 (kind, status) 派生。
                    new_card.metadata["supersedes"] = card.card_id
                    new_card.validation_state = ValidationState.VALID.value

                    # L3 规格要求过时状态必须是对应对象类型的合法类型化状态：
                    # constraint -> superseded；其余类型 -> archived。
                    # 直接赋值不会触发 __post_init__ 校验，但序列化后 from_dict 会校验，
                    # 因此必须写入合法类型化状态，否则重载后状态丢失、治理地位错误降级。
                    legacy_kind = card.kind.value if hasattr(card.kind, "value") else str(card.kind)
                    if legacy_kind == "constraint":
                        card.status = "superseded"
                    else:
                        card.status = "archived"
                    card.metadata["superseded_by"] = new_card_id

                    card_index[card.card_id] = card
                    card_index[new_card_id] = new_card
                    latest_card_id = new_card_id

                    # 建立 REPLACES 替代追溯关系。
                    supersede_relation = CanvasRelation(
                        relation_id=f"rel_{uuid4().hex[:10]}",
                        kind=CanvasRelationKind.REPLACES,
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
                    # L3 规格已下线 stage 字段；忽略 mutation.payload["stage"]。
                    if "status" in mutation.payload:
                        card.status = str(mutation.payload["status"])
                    if "tags" in mutation.payload:
                        card.tags = [str(tag) for tag in mutation.payload["tags"]]
                    if "metadata" in mutation.payload:
                        card.metadata = {**card.metadata, **dict(mutation.payload["metadata"])}
                    
                    card.validation_state = ValidationState.VALID.value

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
                    # L3 规格已下线 REOPENS 关系；改用 REPLACES 表达决策重开/约束替代等过时关系。
                    if selected_kind_str in ("option", "decision") and latest_kind_str in ("problem", "clarification"):
                        rel_kind = CanvasRelationKind.REPLACES
                relation = CanvasRelation(
                    relation_id=f"rel_{uuid4().hex[:10]}",
                    kind=rel_kind,
                    from_card_id=selected_card_id,
                    to_card_id=latest_card_id,
                    metadata={"source_proposal_id": proposal.proposal_id},
                )
                relation_index[relation.relation_id] = relation

        relations = list(relation_index.values())
        if handoff is not None:
            # L3 规格已下线 StructuredHandoff.summary；快照 summary 改读 metadata.legacy.summary。
            legacy_summary = str(dict(handoff.metadata or {}).get("legacy", {}).get("summary", ""))
            snapshot = CanvasSnapshot(
                snapshot_id=f"snapshot_{uuid4().hex[:10]}",
                workspace_id=workspace.workspace_id,
                title="结构化交接物草稿已刷新",
                summary=legacy_summary,
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
            self.repository.save_snapshot(workspace.workspace_id, snapshot)
            workspace.active_snapshot_id = snapshot.snapshot_id
        self._commit_canvas_state(workspace, cards, relations, handoff, proposal, confirmation)
        self._touch_workspace(workspace)

    def _card_mutation(
        self,
        mutation_type: str,
        kind: CanvasCardKind,
        title: str,
        summary: str,
        status: Optional[str] = None,
        source_refs: Optional[List[str]] = None,
        material_ids: Optional[List[str]] = None,
        source_ref_ids: Optional[List[str]] = None,
        selected_card_ids: Optional[List[str]] = None,
    ) -> CanvasMutation:
        # L3 规格已下线 stage 字段；CanvasCard 不再接受 stage kwarg。
        # evidence_refs 已统一为 source_refs，由本方法消费方传入。
        card = CanvasCard(
            card_id=f"card_{uuid4().hex[:10]}",
            kind=kind,
            title=title,
            summary=summary,
            status=status or default_status_for_kind(kind.value),
            source_refs=list(source_refs or []),
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

    def _commit_canvas_state(
        self,
        workspace: CanvasWorkspace,
        cards: List[CanvasCard],
        relations: List[CanvasRelation],
        handoff: Optional[StructuredHandoff],
        proposal: CanvasMutationProposal,
        confirmation: Optional[ConfirmationRecord],
    ) -> Package:
        """把本轮结构化结果提交为新的不可变包版本和追加式账本事件。

        `cards.json`、`relations.json` 与 `handoff.json` 仅在首次读取旧工作区时使用。
        所有新的画布事实都通过该入口提交，包根指针由仓储在同一工作区锁下推进。
        """

        previous_package = self.repository.load_active_package(workspace.workspace_id)
        previous_version = self.repository.load_active_package_version(workspace.workspace_id)
        now = utc_now_iso()
        package = previous_package or Package(
            package_id=f"pkg_{workspace.workspace_id}",
            workspace_id=workspace.workspace_id,
            scope={"workspace_id": workspace.workspace_id},
            created_at=now,
        )
        package.updated_at = now
        next_version = package.current_version + 1
        next_state_version = package.state_version + 1
        message_refs = [
            str(ref)
            for ref in (
                proposal.metadata.get("assistant_message_ref"),
                proposal.metadata.get("user_message_ref"),
            )
            if ref
        ]
        source_refs = sorted(
            {
                source_ref
                for card in cards
                for source_ref in card.source_refs
            }
        )
        version = PackageVersion(
            package_id=package.package_id,
            package_version=next_version,
            parent_version=previous_version.package_version if previous_version else None,
            state_version=next_state_version,
            created_by_run_id=proposal.turn_id,
            operation_id=f"operation_{proposal.proposal_id}",
            initial_governance_status=(
                InitialGovernanceStatus.CONFIRMED
                if confirmation is not None
                else InitialGovernanceStatus.DRAFT
            ),
            created_at=now,
            scope={
                **dict(package.scope),
                "workspace_title": workspace.title,
                "objective": workspace.objective,
            },
            background={"workspace_objective": workspace.objective},
            objects=[card.to_dict() for card in cards],
            relations=[relation.to_dict() for relation in relations],
            handoff=handoff.to_dict() if handoff is not None else None,
            source_refs=[{"ref": source_ref} for source_ref in source_refs],
        )
        events = self._build_package_ledger_events(
            workspace=workspace,
            package=package,
            version=version,
            previous_version=previous_version,
            cards=cards,
            relations=relations,
            proposal=proposal,
            confirmation=confirmation,
            message_refs=message_refs,
            occurred_at=now,
        )
        committed = self.repository.commit_package_version(
            workspace.workspace_id,
            package,
            version,
            events,
            confirmation=confirmation,
        )
        workspace.metadata = {
            **dict(workspace.metadata),
            "active_package_id": committed.package_id,
        }
        return committed

    def _latest_chat_confirmation_proposal(
        self,
        workspace_id: str,
    ) -> Optional[CanvasMutationProposal]:
        """返回尚待普通 Chat 明确确认的最新高影响提议。

        L3 规格允许两条确认路径：Assistant 提议后用户确认，以及用户直接陈述。
        因此 proposal 可以没有 assistant_message_ref（直接陈述路径），
        只要有 awaiting_chat_confirmation 标记即视为待确认。
        """

        for proposal in reversed(self.repository.load_proposal_history(workspace_id)):
            if (
                proposal.status == CanvasMutationStatus.PENDING_CONFIRMATION
                and proposal.metadata.get("awaiting_chat_confirmation")
            ):
                return proposal
        return None

    @staticmethod
    def _is_explicit_confirmation(message: str) -> bool:
        """识别当前回合是否给出明确同意，而非把模糊表达误判为确认。"""

        normalized = "".join(message.strip().lower().split())
        if any(token in normalized for token in ("不确认", "不同意", "拒绝", "再看看", "先不要")):
            return False
        return any(token in normalized for token in ("确认", "同意", "按这个执行", "就这么定", "可以生效"))

    @staticmethod
    def _proposal_message_content(proposal: CanvasMutationProposal) -> str:
        """为可追溯确认保存助手实际提出的结构化变更摘要。"""

        items = []
        for mutation in proposal.mutations:
            card = dict(mutation.payload.get("card", {}))
            title = str(card.get("title", mutation.target_id)).strip()
            mutation_type = str(mutation.metadata.get("mutation_type", mutation.action.value))
            items.append(f"{mutation_type}: {title}")
        return "；".join(items) or "本轮没有可应用的结构化变更。"

    def _apply_chat_confirmation(
        self,
        workspace: CanvasWorkspace,
        turn_id: str,
        proposal: CanvasMutationProposal,
        *,
        user_message_ref: str,
    ) -> Dict[str, Any]:
        """把用户在普通 Chat 中的明确确认写为记录并提交对应包版本。"""

        package = self.repository.load_active_package(workspace.workspace_id)
        package_id = package.package_id if package is not None else f"pkg_{workspace.workspace_id}"
        proposal.metadata = {
            **dict(proposal.metadata),
            "user_message_ref": user_message_ref,
            "confirmed_turn_id": turn_id,
        }
        self._materialize_confirmation_approval(proposal)
        scope_refs = [mutation.target_id for mutation in proposal.mutations if mutation.target_id]
        # L3 规格要求确认记录显式区分两条路径：
        # - Assistant 提议后用户确认：proposal_message_refs 必填；
        # - 用户直接给出清晰、完整且带范围的产品判断：proposal_message_refs 可空。
        assistant_message_ref = proposal.metadata.get("assistant_message_ref")
        if assistant_message_ref:
            confirmation_path = ConfirmationPath.ASSISTANT_PROPOSAL_THEN_USER_RESPONSE
            proposal_message_refs = [str(assistant_message_ref)]
        else:
            confirmation_path = ConfirmationPath.DIRECT_USER_STATEMENT
            proposal_message_refs = []
        confirmation = ConfirmationRecord(
            confirmation_id=f"confirmation_{uuid4().hex[:12]}",
            workspace_id=workspace.workspace_id,
            package_id=package_id,
            confirmation_path=confirmation_path,
            proposal_message_refs=proposal_message_refs,
            user_message_refs=[user_message_ref],
            confirmed_claims=[
                ConfirmedClaim(
                    claim=(
                        mutation.rationale.strip()
                        or str(mutation.metadata.get("mutation_type", mutation.action.value))
                    ),
                    scope_refs=[mutation.target_id] if mutation.target_id else [],
                )
                for mutation in proposal.mutations
            ],
            scope_refs=scope_refs,
            confirmation_kind=ConfirmationKind.CONFIRMED,
            remaining_unresolved_refs=self._projected_unresolved_refs(
                workspace.workspace_id, proposal
            ),
            recorded_at=utc_now_iso(),
        )
        proposal.status = CanvasMutationStatus.APPLIED
        self._apply_proposal(workspace, proposal, confirmation=confirmation)
        self.repository.append_proposal_history(workspace.workspace_id, proposal)
        self._publish_event(
            workspace.workspace_id,
            "canvas.chat_confirmation.recorded",
            self._proposal_event_payload(
                workspace_id=workspace.workspace_id,
                turn_id=turn_id,
                proposal=proposal,
                result_action="applied_confirmation",
                active_turn=self._serialize_active_turn(workspace),
            ),
            status="confirmed",
        )
        self._publish_event(
            workspace.workspace_id,
            "canvas.mutation.applied",
            self._proposal_event_payload(
                workspace_id=workspace.workspace_id,
                turn_id=turn_id,
                proposal=proposal,
                result_action="applied_confirmation",
                active_turn=self._serialize_active_turn(workspace),
            ),
            status=proposal.status.value,
        )
        self._finish_turn(workspace.workspace_id, turn_id)
        self._publish_event(
            workspace.workspace_id,
            "canvas.turn.completed",
            {
                "workspace_id": workspace.workspace_id,
                "turn_id": turn_id,
                "proposal_id": proposal.proposal_id,
                "result_action": "applied_confirmation",
                "active_turn": None,
            },
            status="completed",
        )
        return {
            "turn_id": turn_id,
            "workspace_id": workspace.workspace_id,
            "proposal_id": proposal.proposal_id,
            "action": "applied_confirmation",
            "risk_level": proposal.risk_level.value,
        }

    def _projected_unresolved_refs(
        self,
        workspace_id: str,
        proposal: CanvasMutationProposal,
    ) -> List[str]:
        """按待确认提案的最终状态投影确认记录中的未决引用。

        确认记录随包版本一起提交，不能先写入“确认前”的未决集合再回写。
        这里只计算状态投影，不触碰存储，也不生成第二条状态写路径。
        """

        card_index = {
            card.card_id: CanvasCard.from_dict(card.to_dict())
            for card in self.repository.load_cards(workspace_id)
        }
        for mutation in proposal.mutations:
            if mutation.target != CanvasMutationTarget.CARD:
                continue
            if mutation.action == CanvasMutationAction.ADD and mutation.payload.get("card"):
                card = CanvasCard.from_dict(mutation.payload["card"])
                card_index[card.card_id] = card
                continue
            if mutation.action != CanvasMutationAction.UPDATE:
                continue
            card = card_index.get(mutation.target_id)
            if card is not None and "status" in mutation.payload:
                card.status = str(mutation.payload["status"])
        return unresolved_issue_ids_from_cards(card_index.values())

    def _build_package_ledger_events(
        self,
        *,
        workspace: CanvasWorkspace,
        package: Package,
        version: PackageVersion,
        previous_version: Optional[PackageVersion],
        cards: List[CanvasCard],
        relations: List[CanvasRelation],
        proposal: CanvasMutationProposal,
        confirmation: Optional[ConfirmationRecord],
        message_refs: List[str],
        occurred_at: str,
    ) -> List[LedgerEvent]:
        """从两个包版本的投影差异生成不含对象正文的账本事件。"""

        before_state_version = previous_version.state_version if previous_version else 0
        before_cards = {
            str(item.get("card_id")): item
            for item in (previous_version.objects if previous_version else [])
        }
        before_relations = {
            str(item.get("relation_id")): item
            for item in (previous_version.relations if previous_version else [])
        }
        actor_type = LedgerActorType.USER if confirmation is not None else LedgerActorType.SYSTEM
        actor_id = "workspace_user" if confirmation is not None else "canvas_service"
        operation_id = version.operation_id

        def make_event(
            event_type: LedgerEventType,
            entity_type: str,
            entity_id: str,
            *,
            before_ref: Optional[str] = None,
            after_ref: Optional[str] = None,
            source_refs: Optional[List[str]] = None,
            confirmation_id: Optional[str] = None,
        ) -> LedgerEvent:
            return LedgerEvent(
                ledger_event_id=f"ledger_{uuid4().hex[:12]}",
                workspace_id=workspace.workspace_id,
                package_id=package.package_id,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                actor_type=actor_type,
                actor_id=actor_id,
                occurred_at=occurred_at,
                package_version=version.package_version,
                state_version_before=before_state_version,
                state_version_after=version.state_version,
                before_ref=before_ref,
                after_ref=after_ref,
                operation_id=operation_id,
                convergence_run_id=proposal.turn_id,
                chat_turn_id=proposal.turn_id,
                message_refs=list(message_refs),
                source_refs=list(source_refs or []),
                confirmation_id=confirmation_id,
            )

        events: List[LedgerEvent] = []
        if previous_version is None:
            events.append(
                make_event(
                    LedgerEventType.PACKAGE_CREATED,
                    "package",
                    package.package_id,
                    after_ref=f"package:{package.package_id}",
                )
            )
        events.append(
            make_event(
                LedgerEventType.PACKAGE_VERSION_CREATED,
                "package_version",
                f"{package.package_id}:v{version.package_version}",
                before_ref=(
                    f"package:{package.package_id}:v{previous_version.package_version}"
                    if previous_version
                    else None
                ),
                after_ref=f"package:{package.package_id}:v{version.package_version}",
            )
        )
        events.append(
            make_event(
                LedgerEventType.CURRENT_VERSION_MOVED,
                "package",
                package.package_id,
                before_ref=(
                    f"package:{package.package_id}:v{previous_version.package_version}"
                    if previous_version
                    else None
                ),
                after_ref=f"package:{package.package_id}:v{version.package_version}",
            )
        )

        for card in cards:
            previous = before_cards.get(card.card_id)
            after_ref = f"package:{package.package_id}:v{version.package_version}:object:{card.card_id}"
            if previous is None:
                events.append(
                    make_event(
                        LedgerEventType.OBJECT_CREATED,
                        card.kind.value,
                        card.card_id,
                        after_ref=after_ref,
                        source_refs=card.source_refs,
                    )
                )
            elif str(previous.get("status")) != card.status:
                events.append(
                    make_event(
                        LedgerEventType.OBJECT_STATUS_CHANGED,
                        card.kind.value,
                        card.card_id,
                        before_ref=f"package:{package.package_id}:v{previous_version.package_version}:object:{card.card_id}",
                        after_ref=after_ref,
                        source_refs=card.source_refs,
                        confirmation_id=confirmation.confirmation_id if confirmation else None,
                    )
                )
            elif previous != card.to_dict():
                events.append(
                    make_event(
                        LedgerEventType.OBJECT_CONTENT_UPDATED,
                        card.kind.value,
                        card.card_id,
                        before_ref=f"package:{package.package_id}:v{previous_version.package_version}:object:{card.card_id}",
                        after_ref=after_ref,
                        source_refs=card.source_refs,
                    )
                )

        for relation in relations:
            if relation.relation_id not in before_relations:
                events.append(
                    make_event(
                        LedgerEventType.RELATION_CREATED,
                        "relation",
                        relation.relation_id,
                        after_ref=f"package:{package.package_id}:v{version.package_version}:relation:{relation.relation_id}",
                        source_refs=relation.source_refs,
                    )
                )
        for relation_id in before_relations.keys() - {relation.relation_id for relation in relations}:
            events.append(
                make_event(
                    LedgerEventType.RELATION_REMOVED,
                    "relation",
                    relation_id,
                    before_ref=f"package:{package.package_id}:v{previous_version.package_version}:relation:{relation_id}",
                )
            )
        if confirmation is not None:
            events.append(
                make_event(
                    LedgerEventType.CONFIRMATION_RECORDED,
                    "confirmation",
                    confirmation.confirmation_id,
                    after_ref=f"confirmation:{confirmation.confirmation_id}",
                    confirmation_id=confirmation.confirmation_id,
                )
            )
            events.append(
                make_event(
                    LedgerEventType.LATEST_CONFIRMED_VERSION_MOVED,
                    "package",
                    package.package_id,
                    after_ref=f"package:{package.package_id}:v{version.package_version}",
                    confirmation_id=confirmation.confirmation_id,
                )
            )
        return events

    def _build_todo_projection(self, workspace_id: str, cards: List[CanvasCard]) -> TodoProjection:
        # L3 规格已下线 OPTION 卡片；待澄清/约束/待决策的未决状态由类型化 status 派生。
        items: list[TodoItem] = []
        for card in cards:
            if is_unresolved_status(card.kind.value, card.status):
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

    # L3 规格已下线 stage_node 主题阶段机；_normalize_stage / _validate_stage_move
    # 与 _upsert_handoff_card（依赖已删除的 CanvasCardKind.HANDOFF）一并移除。
    # move_card 在过渡期保留为 deprecated_noop，不再依赖上述辅助。

    @staticmethod
    def _handoff_items(cards: List[CanvasCard], kind: CanvasCardKind) -> List[str]:
        # L3 规格已下线 OPTION / HANDOFF 卡片类型；状态集合对齐类型化状态枚举。
        visible_statuses = {
            CanvasCardKind.CLARIFICATION: {"open", "pending_confirmation", "blocked"},
            CanvasCardKind.CONSTRAINT: {"draft", "pending_confirmation", "effective"},
            CanvasCardKind.DECISION: {"pending_decision", "pending_confirmation", "decided"},
            CanvasCardKind.EVIDENCE: {"collected", "cited"},
            CanvasCardKind.PROBLEM: {"initial", "converging", "converged"},
        }
        allowed = visible_statuses.get(kind, set())
        return [card.title for card in cards if card.kind == kind and card.status in allowed]

    def _build_handoff_summary(self, message: str, cards: List[CanvasCard]) -> str:
        # L3 规格要求交接模块不复制对象正文；本方法仅生成过渡期 metadata.legacy.summary
        # 供前端兼容回看，真正内容仍由源对象维护。
        clarifications = self._handoff_items(cards, CanvasCardKind.CLARIFICATION)
        constraints = self._handoff_items(cards, CanvasCardKind.CONSTRAINT)
        return (
            f"基于当前回合收束的结构化交接物草稿：{message}"
            f"；待澄清 {len(clarifications)} 项，约束 {len(constraints)} 项。"
        )

    def _build_refresh_handoff_summary(self, cards: List[CanvasCard]) -> str:
        # L3 规格已下线 OPTION 卡片；本方法只输出过渡期 legacy 摘要。
        problems = [card.title for card in cards if card.kind == CanvasCardKind.PROBLEM]
        clarifications = self._handoff_items(cards, CanvasCardKind.CLARIFICATION)
        constraints = self._handoff_items(cards, CanvasCardKind.CONSTRAINT)
        decisions = self._handoff_items(cards, CanvasCardKind.DECISION)

        problem_str = f"主问题：{problems[0]}" if problems else "暂无主问题"

        return (
            "基于当前画布收束的结构化交接物草稿：\n"
            + f"【{problem_str}】\n"
            + f"待澄清 {len(clarifications)} 项，约束 {len(constraints)} 项，待决策 {len(decisions)} 项。"
        )

    @staticmethod
    def _materialize_confirmation_approval(proposal: CanvasMutationProposal) -> None:
        """将待确认提案转换为已确认后的最终落盘状态。"""

        confirmed_at = utc_now_iso()
        for mutation in proposal.mutations:
            mutation_type = str(mutation.metadata.get("mutation_type", ""))
            if mutation.target == CanvasMutationTarget.CARD and mutation_type == "create_decision_request":
                # L3 规格：decision 类型化状态为 pending_decision/pending_confirmation/decided/archived；
                # 旧自由字符串 "confirmed" 已下线，统一改为 "decided"。
                card_payload = mutation.payload.get("card", {})
                card_payload["status"] = "decided"
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
                # L3 规格：clarification 类型化状态为 open/pending_confirmation/clarified/blocked/closed；
                # 旧自由字符串 "resolved" 已下线，统一改为 "clarified"。
                mutation.action = CanvasMutationAction.UPDATE
                resolution = str(mutation.payload.get("resolution", "")).strip()
                mutation.payload = {
                    **mutation.payload,
                    "status": "clarified",
                    "metadata": {
                        **dict(mutation.payload.get("metadata", {})),
                        "resolved_by": "user",
                        "resolved_at": confirmed_at,
                        "resolution": resolution,
                        "confirmation_proposal_id": proposal.proposal_id,
                        "source_turn_id": proposal.turn_id,
                    },
                }

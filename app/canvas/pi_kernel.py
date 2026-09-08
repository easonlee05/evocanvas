"""Pi 驱动的 EvoCanvas 产品内核适配层。

生产回合由 Primary Pi Session 和受治理的 workspace.commit 驱动。Python
只维护 UI 活跃回合和可重建投影；旧合同方法保留为迁移兼容入口。
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Mapping
from uuid import uuid4

from app.canvas.agent_execution.contracts import (
    ChatRunRequest,
    ContextManifest,
    ConvergenceProposal,
    ConvergenceRunRequest,
    JudgementRunRequest,
    MessageScope,
    ModelPolicy,
    PackageRef,
    RuntimeInputSnapshot,
    StructuredPackageInputRef,
    ToolProfile,
    TraceContext,
    UserSubmissionRequest,
    WorkspaceCommitRequest,
)
from app.canvas.agent_execution.port import AgentExecutionPort
from app.canvas.domain.cards import CanvasCard, CanvasCardKind
from app.canvas.domain.mutations import (
    CanvasMutation,
    CanvasMutationAction,
    CanvasMutationProposal,
    CanvasMutationStatus,
    CanvasMutationTarget,
)
from app.canvas.domain.runtime_records import (
    ChatTurnRecord,
    CommitAttemptRecord,
    ConvergenceJudgementRecord,
    ConvergenceRunRecord,
)
from app.canvas.product_kernel import ProductKernel
from app.canvas.repository import PackageVersionStaleError
from app.canvas.runtime_state import apply_turn_runtime_state, unresolved_issue_ids_from_cards
from app.canvas.verification import verify_mutation_proposal
from app.core.events import utc_now_iso


class PiCanvasKernel:
    """把一个 CanvasService 接到唯一的 PiRuntimeClient。"""

    def __init__(self, service: Any, execution: AgentExecutionPort) -> None:
        self.service = service
        self.execution = execution
        self.product_kernel = ProductKernel(
            execution=execution,
            assistant_messages=self,
            governed_commit=self,
        )

    async def append_assistant_message(
        self,
        *,
        workspace_id: str,
        conversation_id: str,
        run_id: str,
        message: Any,
    ) -> str:
        """只在 Pi 返回完整终态后保存正式 Assistant 主消息。"""

        del conversation_id
        content_parts: list[str] = []
        for block in message.content_blocks:
            if not isinstance(block, Mapping):
                continue
            if block.get("type") == "text" and str(block.get("text", "")).strip():
                content_parts.append(str(block["text"]).strip())
        content = "\n".join(content_parts).strip()
        if not content:
            content = json.dumps(
                [dict(block) for block in message.content_blocks if isinstance(block, Mapping)],
                ensure_ascii=False,
                sort_keys=True,
            )
        record = self.service.repository.append_chat_message(
            workspace_id,
            {
                "message_id": f"msg_{uuid4().hex[:12]}",
                "role": "assistant",
                "content": content,
                "turn_id": run_id,
                "created_at": utc_now_iso(),
                "metadata": {"source": "pi_runtime", "run_id": run_id},
            },
        )
        return str(record["message_id"])

    async def edit_canvas(self, workspace_id: str, actor_id: str, operations: list[dict], summary: str) -> dict[str, Any]:
        """用户明确编辑通过统一提交器生效，成功后才刷新兼容投影。"""
        projection = await self.refresh_projection(workspace_id)
        result = await self.execution.edit_workspace(workspace_id, actor_id=actor_id,
            submission_id=f"edit_{uuid4().hex}", base_revision_id=projection["projected_revision_id"],
            operations=operations, change_summary=summary)
        await self.refresh_projection(workspace_id)
        self.service._publish_event(workspace_id, "canvas.mutation.applied", {"workspace_id": workspace_id, "result_action": "applied", "new_revision_id": result["new_revision_id"]}, status="applied")
        return result

    async def refresh_projection(self, workspace_id: str) -> dict[str, Any]:
        """从稳定 Revision 重建兼容画布缓存；缓存不参与治理或提交。"""
        from app.canvas.domain.relations import CanvasRelation
        from app.canvas.agent_execution.pi_client import PiRuntimeError
        projection = await self.execution.get_projection(workspace_id)
        revision_id = projection["projected_revision_id"]
        revision = await self.execution.get_revision(workspace_id, revision_id)
        if revision_id == "rev_0" and self.service.repository.load_cards(workspace_id):
            raise PiRuntimeError("workspace.migration_required", "该工作区仍有旧版卡片，需完成稳定版本迁移；原数据已保留")
        cards = []
        for obj in revision["objects"].values():
            if obj["object_type"] == "handoff" or obj["type_status"] in {"archived", "superseded"}:
                continue
            data = dict(obj.get("data") or {})
            cards.append(CanvasCard.from_dict({
                **data, "card_id": obj["id"], "kind": obj["object_type"],
                "title": obj["title"], "summary": obj.get("summary", ""),
                "status": obj["type_status"], "confirmation_refs": obj.get("confirmation_refs", []),
                "created_at": obj["created_at"], "updated_at": obj["updated_at"],
                "metadata": {**data.get("metadata", {}), "projected_revision_id": revision_id},
            }))
        card_ids = {card.card_id for card in cards}
        relations = [CanvasRelation.from_dict({
            "relation_id": rel["relation_id"], "kind": rel["relation_type"],
            "from_card_id": rel["source_id"], "to_card_id": rel["target_id"],
        }) for rel in revision["relations"] if rel["source_id"] in card_ids and rel["target_id"] in card_ids]
        self.service.repository.save_cards(workspace_id, cards)
        self.service.repository.save_relations(workspace_id, relations)
        return projection

    async def refresh_messages(self, workspace_id: str) -> None:
        """从真实 Session Entry 重建可读消息缓存，不创建伪造 Entry。"""
        from datetime import datetime, timezone
        records = await self.execution.get_messages(workspace_id)
        existing = {m["message_id"] for m in self.service.repository.load_chat_messages(workspace_id)}
        for entry in records["messages"]:
            message = entry["message"]
            if entry["id"] in existing or message["role"] not in {"user", "assistant"}:
                continue
            if message["role"] == "assistant" and (message.get("stopReason") != "stop" or message.get("evocanvas_terminal") == "failed"):
                continue
            content = message.get("content", "")
            if isinstance(content, list):
                content = "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
            if not content.strip():
                continue
            try:
                self.service.repository.append_chat_message(workspace_id, {
                    "message_id": entry["id"], "role": message["role"], "content": content,
                    "created_at": datetime.fromtimestamp(entry["timestamp"] / 1000, timezone.utc).isoformat(),
                    "metadata": {"session_id": records["session_id"], "entry_id": entry["id"], "source": "pi_session_projection"},
                })
            except FileExistsError:
                # 并发读取可能已由另一个投影刷新写入同一 Entry。
                continue

    async def run_turn(
        self, *, workspace_id: str, message: str, selected_card_ids: list[str],
        material_ids: list[str], source_ref_ids: list[str], model: str | None = None,
        submission_id: str | None = None, actor_id: str = "user",
    ) -> dict[str, Any]:
        """唯一生产主链：真实 Session → Pi 工具循环 → Revision → 画布缓存。"""
        from app.canvas.agent_execution.pi_client import PiRuntimeError
        service = self.service
        submission_id = submission_id or f"sub_{uuid4().hex}"
        turn_id = submission_id
        workspace = service._begin_turn(workspace_id, turn_id)
        try:
            service._publish_event(workspace_id, "canvas.turn.started", {
                "workspace_id": workspace_id, "turn_id": turn_id, "active_turn": service._serialize_active_turn(workspace),
            }, status="running")
            await self.refresh_projection(workspace_id)
            service._validate_selected_cards(selected_card_ids, service.repository.load_cards(workspace_id))
            materials = []
            if material_ids or source_ref_ids:
                from app.api.server import global_materials_cache, global_source_refs_cache
                for source_id in material_ids + source_ref_ids:
                    source = global_materials_cache.get(source_id) or global_source_refs_cache.get(source_id)
                    if source is None:
                        raise PiRuntimeError("workspace.source_missing", f"来源 {source_id} 不存在，无法恢复内容")
                    materials.append({"id": source_id, "content": str(source.get("content") or source.get("excerpt") or json.dumps(source.get("snapshot", {}), ensure_ascii=False))})
            pi_message = {"role": "user", "content": message}
            normalized = json.dumps(pi_message, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            receipt = await self.execution.submit_user_message(UserSubmissionRequest(
                submission_id=submission_id, content_hash="sha256:" + hashlib.sha256(normalized.encode()).hexdigest(),
                workspace_id=workspace_id, actor_id=actor_id, pi_user_message=pi_message,
            ))
            result = await self.execution.run_workspace(workspace_id, receipt.submission_id, selected_card_ids=selected_card_ids, materials=materials, model=model)
            if not result.get("assistant_entry_id"):
                raise PiRuntimeError("protocol_error", "Runtime 没有返回真实 Assistant Entry")
            await self.refresh_projection(workspace_id)
            await self.refresh_messages(workspace_id)
            service._finish_turn(workspace_id, turn_id)
            service._publish_event(workspace_id, "canvas.turn.completed", {
                "workspace_id": workspace_id, "turn_id": turn_id, "result_action": result["action"], "active_turn": None,
            }, status="completed")
            return {**result, "turn_id": turn_id, "assistant_message_id": result["assistant_entry_id"], "proposal_id": None, "roles": [], "intent": "pi_workspace"}
        except Exception as exc:
            service._finish_turn(workspace_id, turn_id)
            service._publish_event(workspace_id, "canvas.turn.failed", {
                "workspace_id": workspace_id, "turn_id": turn_id, "result_action": "failed",
                "error": getattr(exc, "error_code", str(exc)), "active_turn": None,
                "submission_id": submission_id,
            }, status="failed")
            raise

    async def submit_convergence_proposal(
        self,
        *,
        proposal: ConvergenceProposal,
        trace_context: TraceContext,
    ) -> Mapping[str, Any]:
        """重新验证 Pi 提案，并交给现有唯一 Canvas 提交入口。"""

        workspace_id = str(trace_context.extra.get("workspace_id", "")).strip()
        if not workspace_id:
            raise ValueError("convergence trace context must include workspace_id")
        service = self.service
        package_id, actual_package_version, actual_state_version = self._package_base(workspace_id)
        if proposal.package_id != package_id:
            raise ValueError("convergence proposal package_id does not match active package")
        if (
            proposal.base_package_version != actual_package_version
            or proposal.base_state_version != actual_state_version
        ):
            raise PackageVersionStaleError(
                package_id,
                proposal.base_package_version,
                actual_package_version,
                proposal.base_state_version,
                actual_state_version,
            )

        mutation_proposal = self._to_canvas_proposal(proposal, workspace_id)
        existing_cards = service.repository.load_cards(workspace_id)
        receipt = verify_mutation_proposal(
            mutation_proposal,
            intent="pi_convergence",
            existing_cards=existing_cards,
        )
        mutation_proposal.metadata["verification_receipt"] = receipt
        outcome = service.governance.classify(mutation_proposal, existing_cards=existing_cards)
        if outcome.action != "auto_apply":
            mutation_proposal.status = CanvasMutationStatus.PENDING_CONFIRMATION
            service.repository.append_proposal_history(workspace_id, mutation_proposal)
            return {
                "result": "not_ready",
                "proposal_id": proposal.proposal_id,
                "governance_action": outcome.action,
            }

        operation_id = f"operation_{proposal.proposal_id}"
        commit_id = f"commit_{uuid4().hex[:12]}"
        now = utc_now_iso()
        service.repository.save_commit_attempt(
            CommitAttemptRecord(
                commit_attempt_id=commit_id,
                operation_id=operation_id,
                workspace_id=workspace_id,
                package_id=package_id,
                base_state_version=proposal.base_state_version,
                base_package_version=proposal.base_package_version,
                status="started",
                created_at=now,
                updated_at=now,
            )
        )
        try:
            workspace = service.get_workspace(workspace_id)
            service._apply_proposal(workspace, mutation_proposal)
            service.repository.append_proposal_history(workspace_id, mutation_proposal)
            service.repository.save_commit_attempt(
                CommitAttemptRecord(
                    commit_attempt_id=commit_id,
                    operation_id=operation_id,
                    workspace_id=workspace_id,
                    package_id=package_id,
                    base_state_version=proposal.base_state_version,
                    base_package_version=proposal.base_package_version,
                    status="applied",
                    result_code="applied",
                    created_at=now,
                    updated_at=utc_now_iso(),
                )
            )
            return {
                "result": "applied",
                "proposal_id": proposal.proposal_id,
                "operation_id": operation_id,
            }
        except PackageVersionStaleError:
            service.repository.save_commit_attempt(
                CommitAttemptRecord(
                    commit_attempt_id=commit_id,
                    operation_id=operation_id,
                    workspace_id=workspace_id,
                    package_id=package_id,
                    base_state_version=proposal.base_state_version,
                    base_package_version=proposal.base_package_version,
                    status="stale",
                    error_code=PackageVersionStaleError.code,
                    created_at=now,
                    updated_at=utc_now_iso(),
                )
            )
            raise
        except Exception as error:
            service.repository.save_commit_attempt(
                CommitAttemptRecord(
                    commit_attempt_id=commit_id,
                    operation_id=operation_id,
                    workspace_id=workspace_id,
                    package_id=package_id,
                    base_state_version=proposal.base_state_version,
                    base_package_version=proposal.base_package_version,
                    status="failed",
                    error_code=self._failure_code(error),
                    created_at=now,
                    updated_at=utc_now_iso(),
                )
            )
            raise

    def _to_canvas_proposal(self, proposal: ConvergenceProposal, workspace_id: str) -> CanvasMutationProposal:
        mutations: list[CanvasMutation] = []
        for operation in proposal.operations:
            payload = dict(operation.payload)
            target = self._operation_target(operation.operation_type, payload)
            action = self._operation_action(operation.operation_type, payload)
            target_id = operation.target_object_id or operation.temporary_target_ref or f"object_{uuid4().hex[:10]}"
            mutation_type = operation.operation_type
            if target == CanvasMutationTarget.CARD and action == CanvasMutationAction.ADD:
                mutation_type = "add_card"
            elif target == CanvasMutationTarget.HANDOFF and action == CanvasMutationAction.UPDATE:
                mutation_type = "refresh_handoff_draft"
            mutation_metadata = {
                "mutation_type": mutation_type,
                "source_refs": list(operation.source_refs),
                "confirmation_refs": list(operation.confirmation_refs),
                "unresolved_refs": list(operation.unresolved_refs),
                "temporary_target_ref": operation.temporary_target_ref,
            }
            if target == CanvasMutationTarget.CARD and action == CanvasMutationAction.ADD:
                card_payload = dict(payload.get("card", payload))
                kind = self._card_kind(operation.operation_type, card_payload)
                card_payload["card_id"] = target_id
                card_payload["kind"] = kind.value
                card_payload["title"] = str(card_payload.get("title", "")).strip() or "待补充结构对象"
                card_payload["summary"] = str(card_payload.get("summary", "")).strip()
                card_payload["status"] = str(card_payload.get("status", "")) or self._default_status(kind)
                card_payload["source_refs"] = self._merge_refs(
                    operation.source_refs,
                    card_payload.get("source_refs", []),
                )
                card_payload["confirmation_refs"] = self._merge_refs(
                    operation.confirmation_refs,
                    card_payload.get("confirmation_refs", []),
                )
                card_payload["unresolved_refs"] = self._merge_refs(
                    operation.unresolved_refs,
                    card_payload.get("unresolved_refs", []),
                )
                card_payload.setdefault("created_at", utc_now_iso())
                card_payload.setdefault("updated_at", card_payload["created_at"])
                CanvasCard.from_dict(card_payload)
                payload = {"card": card_payload}
            elif target == CanvasMutationTarget.HANDOFF:
                payload = {"handoff": dict(payload.get("handoff", payload))}
            mutations.append(
                CanvasMutation(
                    mutation_id=operation.operation_id or f"mutation_{uuid4().hex[:10]}",
                    action=action,
                    target=target,
                    target_id=target_id,
                    payload=payload,
                    rationale="；".join(operation.reason_codes),
                    requires_confirmation=operation.risk_level == "high",
                    metadata=mutation_metadata,
                )
            )
        return CanvasMutationProposal(
            proposal_id=proposal.proposal_id,
            workspace_id=workspace_id,
            turn_id=proposal.run_id,
            mutations=mutations,
            metadata={
                "source": "pi_runtime",
                "pi_proposal_id": proposal.proposal_id,
                "from_message_seq": proposal.from_message_seq,
                "through_message_seq": proposal.through_message_seq,
            },
        )

    def _chat_request(self, **kwargs: Any) -> ChatRunRequest:
        return ChatRunRequest(
            run_id=kwargs["run_id"],
            run_kind="chat",
            workspace_id=kwargs["workspace_id"],
            conversation_id=kwargs["conversation_id"],
            from_message_seq=kwargs["from_message_seq"],
            through_message_seq=kwargs["through_message_seq"],
            context_manifest=self._manifest("chat", **kwargs),
            instructions_ref="evocanvas.chat.instructions.v1",
            model_policy=ModelPolicy("balanced", "interactive", False, False),
            tool_profile=self._tool_profile("chat", kwargs),
            deadline_ms=self._deadline_ms(),
            trace_context=self._trace(kwargs["run_id"], kwargs["workspace_id"], kwargs["conversation_id"]),
            idempotency_key=kwargs["run_id"],
            runtime_inputs=self._runtime_inputs(**kwargs),
            package_id=kwargs["package_id"],
            raw_user_message_ref=kwargs["raw_user_message_ref"],
            assistant_reply_schema_ref="evocanvas.assistant-message.v1",
            conversation_order_key=f"{kwargs['conversation_id']}:{kwargs['through_message_seq']}",
        )

    def _judgement_request(self, **kwargs: Any) -> JudgementRunRequest:
        return JudgementRunRequest(
            run_id=kwargs["run_id"],
            run_kind="judgement",
            workspace_id=kwargs["workspace_id"],
            conversation_id=kwargs["conversation_id"],
            from_message_seq=kwargs["from_message_seq"],
            through_message_seq=kwargs["through_message_seq"],
            context_manifest=self._manifest("judgement", **kwargs),
            instructions_ref="evocanvas.judgement.instructions.v1",
            model_policy=ModelPolicy("balanced", "background", True, False),
            tool_profile=self._tool_profile("judgement", kwargs),
            deadline_ms=self._deadline_ms(),
            trace_context=self._trace(
                kwargs["run_id"],
                kwargs["workspace_id"],
                kwargs["conversation_id"],
                parent_run_id=kwargs.get("parent_run_id"),
            ),
            idempotency_key=kwargs["run_id"],
            runtime_inputs=self._runtime_inputs(**kwargs),
            chat_turn_id=kwargs["chat_turn_id"],
            base_state_version=kwargs["state_version"],
            base_package_version=kwargs["package_version"],
            signal_summary_ref=f"chat-signal:{kwargs['chat_turn_id']}:{kwargs['through_message_seq']}",
            package_id=kwargs["package_id"],
        )

    def _convergence_request(self, **kwargs: Any) -> ConvergenceRunRequest:
        return ConvergenceRunRequest(
            run_id=kwargs["run_id"],
            run_kind="convergence",
            workspace_id=kwargs["workspace_id"],
            conversation_id=kwargs["conversation_id"],
            from_message_seq=kwargs["from_message_seq"],
            through_message_seq=kwargs["through_message_seq"],
            context_manifest=self._manifest("convergence", **kwargs),
            instructions_ref="evocanvas.convergence.instructions.v1",
            model_policy=ModelPolicy("quality", "background", True, True),
            tool_profile=self._tool_profile("convergence", kwargs),
            deadline_ms=self._deadline_ms(),
            trace_context=self._trace(
                kwargs["run_id"],
                kwargs["workspace_id"],
                kwargs["conversation_id"],
                parent_run_id=kwargs.get("parent_run_id"),
            ),
            idempotency_key=kwargs["run_id"],
            runtime_inputs=self._runtime_inputs(**kwargs),
            package_id=kwargs["package_id"],
            convergence_run_id=kwargs["run_id"],
            base_state_version=kwargs["state_version"],
            base_package_version=kwargs["package_version"],
            proposal_schema_ref="evocanvas.convergence-proposal.v1",
            proposal_capture_tool_ref="submit_convergence_proposal:v1",
        )

    def _tool_profile(self, run_kind: str, kwargs: Mapping[str, Any]) -> ToolProfile:
        """为单次运行签发最小工具权限；提案捕获不经过 Python Gateway。"""

        read_tools: tuple[str, ...] = ()
        if self.service.canvas_tool_gateway is not None and run_kind in {"chat", "convergence"}:
            read_tools = (
                "source.resolve",
                "material.read",
                "knowledge.retrieve",
                "structure.validate",
            ) if run_kind == "convergence" else (
                "source.resolve",
                "material.read",
                "knowledge.retrieve",
            )
        allowed_tools = list(read_tools)
        if run_kind == "convergence":
            allowed_tools.append("submit_convergence_proposal")
        gateway_url = None
        token = None
        tenant_id = getattr(self.service, "tenant_id", "default")
        max_calls = 0
        if self.service.canvas_tool_gateway is not None and read_tools:
            import os

            gateway_url = os.getenv(
                "PI_TOOL_GATEWAY_URL",
                "http://127.0.0.1:8000/internal/v1/tool-calls",
            )
            token = self.service.canvas_tool_gateway.issue_run_token(
                run_id=str(kwargs["run_id"]),
                run_kind=run_kind,
                workspace_id=str(kwargs["workspace_id"]),
                conversation_id=str(kwargs["conversation_id"]),
                package_id=str(kwargs["package_id"]) if kwargs.get("package_id") is not None else None,
                tenant_id=tenant_id,
                allowed_tools=read_tools,
                ttl_seconds=max(1, int(self._deadline_ms() / 1000) + 5),
                max_calls=8,
                max_result_bytes=131072,
                message_range=(int(kwargs["from_message_seq"]), int(kwargs["through_message_seq"])),
            )
            max_calls = 8
        elif run_kind == "convergence":
            max_calls = 1
        return ToolProfile(
            run_kind=run_kind,  # type: ignore[arg-type]
            allowed_tools=tuple(allowed_tools),
            max_calls=max_calls,
            max_result_bytes=131072,
            gateway_url=gateway_url,
            run_scoped_token=token,
            tenant_id=tenant_id,
        )

    def _manifest(self, request_kind: str, **kwargs: Any) -> ContextManifest:
        workspace_id = kwargs["workspace_id"]
        package_id = kwargs["package_id"]
        package_version = kwargs["package_version"]
        state_version = kwargs["state_version"]
        messages = self.service.repository.load_chat_messages(workspace_id)
        cards = self.service.repository.load_cards(workspace_id)
        package = self.service.repository.load_package(workspace_id, package_id)
        content = {
            "package": package.to_dict() if package is not None else {},
            "package_version": package_version,
            "state_version": state_version,
            "cards": [card.to_dict() for card in cards],
            "messages": [item for item in messages if kwargs["from_message_seq"] <= int(item.get("message_seq", 0)) <= kwargs["through_message_seq"]],
        }
        content_hash = hashlib.sha256(
            json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        source_refs = self._merge_refs(
            kwargs.get("material_ids", []),
            kwargs.get("source_ref_ids", []),
            [ref for card in cards for ref in card.source_refs],
        )
        degradation_flags: list[str] = []
        if package_version == 0:
            degradation_flags.append("package_uninitialized")
        if not source_refs:
            degradation_flags.append("no_external_source_refs")
        return ContextManifest(
            context_manifest_id=f"manifest_{uuid4().hex[:16]}",
            request_kind=request_kind,
            package_ref=PackageRef(package_id, package_version, state_version),
            structured_package_input_ref=StructuredPackageInputRef(
                id=f"package-input:{package_id}:v{package_version}:s{state_version}",
                content_hash=f"sha256:{content_hash}",
            ),
            message_scope=MessageScope(
                from_seq=kwargs["from_message_seq"],
                through_seq=kwargs["through_message_seq"],
                raw_user_message_ref=kwargs.get("raw_user_message_ref"),
            ),
            instruction_and_schema_refs=(
                f"evocanvas.{request_kind}.instructions.v1",
                "evocanvas.convergence-proposal.v1" if request_kind == "convergence" else "evocanvas.assistant-message.v1",
            ),
            source_refs=tuple(source_refs),
            included_sections=("structured_package", "messages", "cards", "source_refs"),
            omissions=({"section": "provider_prompt", "reason": "assembled_inside_pi_runtime"},),
            assembly_policy_version="evocanvas.context-assembly.v1",
            budget_ref=f"budget:{request_kind}:v1",
            degradation_flags=tuple(degradation_flags),
            content_hashes={"structured_context": f"sha256:{content_hash}"},
            transport_ref={
                "provider_id": os.getenv("PI_PROVIDER") or "deepseek",
                "model_id": os.getenv("PI_MODEL") or "deepseek-v4-flash",
                "adapter_version": os.getenv("PI_ADAPTER_VERSION") or "pi-runtime.pi-agent-core.v1",
                "protocol_version": os.getenv("PI_PROTOCOL_VERSION") or "pi-runtime.protocol.v1",
                "capability_profile_version": os.getenv("PI_CAPABILITY_PROFILE_VERSION", "unknown"),
            },
        )

    def _runtime_inputs(self, **kwargs: Any) -> RuntimeInputSnapshot:
        """把 Python 已选定的输入面以临时快照交给 Pi，不改变 Manifest 事实边界。"""

        workspace_id = str(kwargs["workspace_id"])
        package_id = str(kwargs["package_id"])
        package = self.service.repository.load_package(workspace_id, package_id)
        messages = self.service.repository.load_chat_messages(workspace_id)
        from_seq = int(kwargs["from_message_seq"])
        through_seq = int(kwargs["through_message_seq"])
        scoped_messages: list[Mapping[str, Any]] = []
        raw_user_message: str | None = None
        raw_user_message_ref = kwargs.get("raw_user_message_ref")
        for item in messages:
            sequence = int(item.get("message_seq", 0))
            if not from_seq <= sequence <= through_seq:
                continue
            scoped_messages.append(
                {
                    "message_id": str(item.get("message_id", "")),
                    "message_seq": sequence,
                    "role": str(item.get("role", "")),
                    "content": str(item.get("content", "")),
                    "created_at": str(item.get("created_at", "")),
                    "metadata": dict(item.get("metadata", {})),
                }
            )
            if raw_user_message_ref and item.get("message_id") == raw_user_message_ref:
                raw_user_message = str(item.get("content", ""))
        package_input: dict[str, Any] = {
            "package_id": package_id,
            "package_version": int(kwargs["package_version"]),
            "state_version": int(kwargs["state_version"]),
            "scope": dict(package.scope) if package is not None else {},
            "selected_card_ids": [str(item) for item in kwargs.get("selected_card_ids", [])],
            "source_refs": list(self._merge_refs(kwargs.get("material_ids", []), kwargs.get("source_ref_ids", []))),
        }
        return RuntimeInputSnapshot(
            structured_package_input=package_input,
            conversation_messages=tuple(scoped_messages),
            raw_user_message=raw_user_message,
        )

    @staticmethod
    def _trace(run_id: str, workspace_id: str, conversation_id: str, parent_run_id: str | None = None) -> TraceContext:
        return TraceContext(
            trace_id=f"trace_{uuid4().hex[:16]}",
            request_id=run_id,
            parent_run_id=parent_run_id,
            extra={"workspace_id": workspace_id, "conversation_id": conversation_id},
        )

    def _package_base(self, workspace_id: str) -> tuple[str, int, int]:
        package = self.service.repository.load_active_package(workspace_id)
        if package is None:
            return f"pkg_{workspace_id}", 0, 0
        version = self.service.repository.load_active_package_version(workspace_id)
        return package.package_id, package.current_version, version.state_version if version is not None else package.state_version

    def _save_chat_failure(
        self,
        chat_turn_id: str,
        workspace_id: str,
        conversation_id: str,
        package_id: str,
        message_seq: int,
        error: Exception,
    ) -> None:
        now = utc_now_iso()
        self.service.repository.save_chat_turn(
            ChatTurnRecord(
                chat_turn_id=chat_turn_id,
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                package_id=package_id,
                message_seq=message_seq,
                status="failed",
                created_at=now,
                updated_at=now,
                failure_code=self._failure_code(error),
            )
        )

    def _publish_failure(self, workspace_id: str, turn_id: str, error_code: str) -> None:
        self.service._publish_event(
            workspace_id,
            "canvas.turn.failed",
            {
                "workspace_id": workspace_id,
                "turn_id": turn_id,
                "result_action": "failed",
                "error": error_code,
                "active_turn": None,
            },
            status="failed",
        )

    @staticmethod
    def _failure_code(error: Exception) -> str:
        return str(getattr(error, "error_code", None) or getattr(error, "code", None) or error.__class__.__name__)

    @staticmethod
    def _deadline_ms() -> int:
        try:
            return max(1, int(os.getenv("PI_RUNTIME_TIMEOUT_MS", "30000")))
        except ValueError:
            return 30000

    @staticmethod
    def _lease_ttl_seconds() -> int:
        try:
            return max(1, int(os.getenv("PI_PACKAGE_LEASE_TTL_SECONDS", "30")))
        except ValueError:
            return 30

    @staticmethod
    def _merge_refs(*groups: Any) -> list[str]:
        refs: list[str] = []
        for group in groups:
            if isinstance(group, str):
                group = [group]
            if not group:
                continue
            for ref in group:
                value = str(ref).strip()
                if value and value not in refs:
                    refs.append(value)
        return refs

    @staticmethod
    def _operation_target(operation_type: str, payload: Mapping[str, Any]) -> CanvasMutationTarget:
        raw = str(payload.get("target_type", payload.get("target", ""))).strip()
        if not raw:
            lower = operation_type.lower()
            raw = "handoff" if "handoff" in lower else "relation" if "relation" in lower else "card"
        try:
            return CanvasMutationTarget(raw)
        except ValueError as error:
            raise ValueError(f"unsupported Pi proposal target: {raw}") from error

    @staticmethod
    def _operation_action(operation_type: str, payload: Mapping[str, Any]) -> CanvasMutationAction:
        raw = str(payload.get("action", "")).strip()
        if raw:
            try:
                return CanvasMutationAction(raw)
            except ValueError as error:
                raise ValueError(f"unsupported Pi proposal action: {raw}") from error
        lower = operation_type.lower()
        if any(token in lower for token in ("remove", "delete", "archive")):
            return CanvasMutationAction.REMOVE
        if any(token in lower for token in ("update", "replace", "refresh", "resolve", "confirm", "promote")):
            return CanvasMutationAction.UPDATE
        return CanvasMutationAction.ADD

    @staticmethod
    def _card_kind(operation_type: str, payload: Mapping[str, Any]) -> CanvasCardKind:
        raw = str(payload.get("kind", "")).strip()
        if not raw:
            lower = operation_type.lower()
            raw = next(
                (kind.value for kind in CanvasCardKind if kind.value in lower),
                CanvasCardKind.EVIDENCE.value,
            )
        try:
            return CanvasCardKind(raw)
        except ValueError as error:
            raise ValueError(f"unsupported Pi proposal card kind: {raw}") from error

    @staticmethod
    def _default_status(kind: CanvasCardKind) -> str:
        return {
            CanvasCardKind.EVIDENCE: "collected",
            CanvasCardKind.PROBLEM: "initial",
            CanvasCardKind.CLARIFICATION: "open",
            CanvasCardKind.CONSTRAINT: "draft",
            CanvasCardKind.DECISION: "pending_decision",
        }[kind]

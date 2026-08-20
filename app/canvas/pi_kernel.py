"""Pi 驱动的 EvoCanvas 产品内核适配层。

该模块把 Pi Runtime 的三类运行结果接入现有 Canvas 领域服务。Pi 只返回
候选回复、判断和提案；消息记录、运行账本、租约、验证、治理与包提交仍由
Python 持有。
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

    async def run_turn(
        self,
        *,
        workspace_id: str,
        message: str,
        selected_card_ids: list[str],
        material_ids: list[str],
        source_ref_ids: list[str],
        model: str | None = None,
    ) -> dict[str, Any]:
        """执行一轮 Pi Chat，并按判断结果决定是否进入 Convergence。"""

        del model
        service = self.service
        service.get_workspace(workspace_id)
        existing_cards = service.repository.load_cards(workspace_id)
        service._validate_selected_cards(selected_card_ids, existing_cards)

        conversation_id = f"conversation_{workspace_id}"
        chat_turn_id = f"chat_{uuid4().hex[:12]}"
        package_id, base_package_version, base_state_version = self._package_base(workspace_id)
        user_message = service.repository.append_chat_message(
            workspace_id,
            {
                "message_id": f"msg_{uuid4().hex[:12]}",
                "role": "user",
                "content": message,
                "turn_id": chat_turn_id,
                "created_at": utc_now_iso(),
                "metadata": {
                    "selected_card_ids": list(selected_card_ids),
                    "material_ids": list(material_ids),
                    "source_ref_ids": list(source_ref_ids),
                },
            },
        )
        user_message_id = str(user_message["message_id"])
        user_message_seq = int(user_message["message_seq"])
        service._publish_event(
            workspace_id,
            "canvas.turn.started",
            {
                "workspace_id": workspace_id,
                "turn_id": chat_turn_id,
                "execution_path": "pi_runtime",
                "message_seq": user_message_seq,
                "active_turn": None,
            },
            status="running",
        )
        now = utc_now_iso()
        service.repository.save_chat_turn(
            ChatTurnRecord(
                chat_turn_id=chat_turn_id,
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                package_id=package_id,
                message_seq=user_message_seq,
                status="queued",
                created_at=now,
                updated_at=now,
            )
        )
        chat_request = self._chat_request(
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            run_id=chat_turn_id,
            package_id=package_id,
            package_version=base_package_version,
            state_version=base_state_version,
            from_message_seq=user_message_seq,
            through_message_seq=user_message_seq,
            raw_user_message_ref=user_message_id,
            material_ids=material_ids,
            source_ref_ids=source_ref_ids,
            selected_card_ids=selected_card_ids,
        )
        service.repository.save_chat_turn(
            ChatTurnRecord(
                chat_turn_id=chat_turn_id,
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                package_id=package_id,
                message_seq=user_message_seq,
                status="running",
                created_at=now,
                updated_at=utc_now_iso(),
            )
        )

        try:
            chat_outcome = await self.product_kernel.run_chat(chat_request)
        except Exception as error:
            self._save_chat_failure(chat_turn_id, workspace_id, conversation_id, package_id, user_message_seq, error)
            self._publish_failure(workspace_id, chat_turn_id, self._failure_code(error))
            raise

        if chat_outcome.result.finish_reason != "completed":
            failure_code = chat_outcome.result.finish_reason
            service.repository.save_chat_turn(
                ChatTurnRecord(
                    chat_turn_id=chat_turn_id,
                    workspace_id=workspace_id,
                    conversation_id=conversation_id,
                    package_id=package_id,
                    message_seq=user_message_seq,
                    status="cancelled" if failure_code == "cancelled" else "failed",
                    created_at=now,
                    updated_at=utc_now_iso(),
                    failure_code=failure_code,
                )
            )
            self._publish_failure(workspace_id, chat_turn_id, failure_code)
            return {
                "turn_id": chat_turn_id,
                "workspace_id": workspace_id,
                "action": "chat_failed",
                "failure_code": failure_code,
                "assistant_message_id": None,
            }

        service.repository.save_chat_turn(
            ChatTurnRecord(
                chat_turn_id=chat_turn_id,
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                package_id=package_id,
                message_seq=user_message_seq,
                status="completed",
                created_at=now,
                updated_at=utc_now_iso(),
                assistant_message_id=chat_outcome.assistant_message_id,
            )
        )
        service._publish_event(
            workspace_id,
            "canvas.chat.completed",
            {
                "workspace_id": workspace_id,
                "turn_id": chat_turn_id,
                "assistant_message_id": chat_outcome.assistant_message_id,
                "message_seq": service.repository.last_message_seq(workspace_id),
            },
            status="completed",
        )

        through_message_seq = service.repository.last_message_seq(workspace_id)
        judgement_id = f"judgement_{uuid4().hex[:12]}"
        judgement_created_at = utc_now_iso()
        service.repository.save_convergence_judgement(
            ConvergenceJudgementRecord(
                judgement_id=judgement_id,
                chat_turn_id=chat_turn_id,
                workspace_id=workspace_id,
                package_id=package_id,
                through_message_seq=through_message_seq,
                status="queued",
                decision=None,
                reason_codes=(),
                created_at=judgement_created_at,
                updated_at=judgement_created_at,
            )
        )
        judgement_request = self._judgement_request(
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            run_id=judgement_id,
            parent_run_id=chat_turn_id,
            chat_turn_id=chat_turn_id,
            package_id=package_id,
            package_version=base_package_version,
            state_version=base_state_version,
            from_message_seq=user_message_seq,
            through_message_seq=through_message_seq,
            raw_user_message_ref=user_message_id,
            material_ids=material_ids,
            source_ref_ids=source_ref_ids,
            selected_card_ids=selected_card_ids,
        )
        service.repository.save_convergence_judgement(
            ConvergenceJudgementRecord(
                judgement_id=judgement_id,
                chat_turn_id=chat_turn_id,
                workspace_id=workspace_id,
                package_id=package_id,
                through_message_seq=through_message_seq,
                status="running",
                decision=None,
                reason_codes=(),
                created_at=judgement_created_at,
                updated_at=utc_now_iso(),
            )
        )
        try:
            judgement_outcome = await self.product_kernel.run_judgement(judgement_request)
        except Exception as error:
            service.repository.save_convergence_judgement(
                ConvergenceJudgementRecord(
                    judgement_id=judgement_id,
                    chat_turn_id=chat_turn_id,
                    workspace_id=workspace_id,
                    package_id=package_id,
                    through_message_seq=through_message_seq,
                    status="failed",
                    decision=None,
                    reason_codes=(),
                    created_at=judgement_created_at,
                    updated_at=utc_now_iso(),
                    failure_code=self._failure_code(error),
                )
            )
            self._publish_failure(workspace_id, chat_turn_id, self._failure_code(error))
            raise

        service.repository.save_convergence_judgement(
            ConvergenceJudgementRecord(
                judgement_id=judgement_id,
                chat_turn_id=chat_turn_id,
                workspace_id=workspace_id,
                package_id=package_id,
                through_message_seq=judgement_outcome.result.through_message_seq,
                status="completed",
                decision=judgement_outcome.result.decision,
                reason_codes=judgement_outcome.result.reason_codes,
                created_at=judgement_created_at,
                updated_at=utc_now_iso(),
            )
        )
        service.repository.advance_judgement_watermark(
            workspace_id,
            conversation_id,
            package_id,
            judgement_outcome.result.through_message_seq,
        )

        response: dict[str, Any] = {
            "turn_id": chat_turn_id,
            "workspace_id": workspace_id,
            "assistant_message_id": chat_outcome.assistant_message_id,
            "judgement_id": judgement_id,
            "judgement": {
                "decision": judgement_outcome.result.decision,
                "reason_codes": list(judgement_outcome.result.reason_codes),
                "through_message_seq": judgement_outcome.result.through_message_seq,
            },
        }
        if judgement_outcome.result.decision != "trigger":
            response["action"] = "deferred"
            service._publish_event(
                workspace_id,
                "canvas.turn.completed",
                {
                    "workspace_id": workspace_id,
                    "turn_id": chat_turn_id,
                    "result_action": "deferred",
                    "judgement_id": judgement_id,
                    "active_turn": None,
                },
                status="completed",
            )
            return response

        lease = service.repository.acquire_package_lease(
            workspace_id,
            package_id,
            chat_turn_id,
            ttl_seconds=self._lease_ttl_seconds(),
        )
        if lease is None:
            response["action"] = "convergence_busy"
            response["failure_code"] = "package_lease_conflict"
            service._publish_event(
                workspace_id,
                "canvas.turn.completed",
                {
                    "workspace_id": workspace_id,
                    "turn_id": chat_turn_id,
                    "result_action": "convergence_busy",
                    "judgement_id": judgement_id,
                    "active_turn": None,
                },
                status="completed",
            )
            return response

        convergence_id = f"convergence_{uuid4().hex[:12]}"
        convergence_created_at = utc_now_iso()
        convergence_record = ConvergenceRunRecord(
            convergence_run_id=convergence_id,
            workspace_id=workspace_id,
            package_id=package_id,
            from_message_seq=user_message_seq,
            through_message_seq=through_message_seq,
            base_state_version=base_state_version,
            base_package_version=base_package_version,
            status="queued",
            business_result=None,
            created_at=convergence_created_at,
            updated_at=convergence_created_at,
        )
        service.repository.save_convergence_run(convergence_record)
        convergence_request = self._convergence_request(
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            run_id=convergence_id,
            parent_run_id=judgement_id,
            package_id=package_id,
            package_version=base_package_version,
            state_version=base_state_version,
            from_message_seq=user_message_seq,
            through_message_seq=through_message_seq,
            raw_user_message_ref=user_message_id,
            material_ids=material_ids,
            source_ref_ids=source_ref_ids,
            selected_card_ids=selected_card_ids,
        )
        service.repository.save_convergence_run(
            ConvergenceRunRecord(
                **{
                    **convergence_record.__dict__,
                    "status": "running",
                    "updated_at": utc_now_iso(),
                }
            )
        )
        try:
            convergence_outcome = await self.product_kernel.run_convergence(convergence_request)
            result = convergence_outcome.commit_result or {}
            business_result = str(result.get("result", "not_ready"))
            final_status = "completed" if convergence_outcome.result.finish_reason == "completed" else "failed"
            service.repository.save_convergence_run(
                ConvergenceRunRecord(
                    **{
                        **convergence_record.__dict__,
                        "status": final_status,
                        "business_result": business_result,
                        "proposal_id": convergence_outcome.result.proposal.proposal_id
                        if convergence_outcome.result.proposal is not None
                        else None,
                        "failure_code": None
                        if final_status == "completed"
                        else convergence_outcome.result.finish_reason,
                        "updated_at": utc_now_iso(),
                    }
                )
            )
            response.update(
                {
                    "convergence_run_id": convergence_id,
                    "proposal_id": convergence_outcome.result.proposal.proposal_id
                    if convergence_outcome.result.proposal is not None
                    else None,
                    "action": business_result,
                }
            )
            if business_result == "applied":
                service._publish_event(
                    workspace_id,
                    "canvas.mutation.applied",
                    {
                        "workspace_id": workspace_id,
                        "turn_id": chat_turn_id,
                        "proposal_id": response["proposal_id"],
                        "result_action": business_result,
                        "execution_path": "pi_runtime",
                    },
                    status="applied",
                )
            else:
                service._publish_event(
                    workspace_id,
                    "canvas.mutation.proposed",
                    {
                        "workspace_id": workspace_id,
                        "turn_id": chat_turn_id,
                        "proposal_id": response["proposal_id"],
                        "result_action": business_result,
                        "execution_path": "pi_runtime",
                    },
                    status=business_result,
                )
            service._publish_event(
                workspace_id,
                "canvas.turn.completed",
                {
                    "workspace_id": workspace_id,
                    "turn_id": chat_turn_id,
                    "proposal_id": response["proposal_id"],
                    "result_action": business_result,
                    "active_turn": None,
                },
                status="completed",
            )
            return response
        except PackageVersionStaleError:
            service.repository.save_convergence_run(
                ConvergenceRunRecord(
                    **{
                        **convergence_record.__dict__,
                        "status": "stale",
                        "failure_code": PackageVersionStaleError.code,
                        "updated_at": utc_now_iso(),
                    }
                )
            )
            self._publish_failure(workspace_id, chat_turn_id, PackageVersionStaleError.code)
            raise
        except Exception as error:
            service.repository.save_convergence_run(
                ConvergenceRunRecord(
                    **{
                        **convergence_record.__dict__,
                        "status": "failed",
                        "failure_code": self._failure_code(error),
                        "updated_at": utc_now_iso(),
                    }
                )
            )
            service._publish_event(
                workspace_id,
                "canvas.turn.failed",
                {
                    "workspace_id": workspace_id,
                    "turn_id": chat_turn_id,
                    "result_action": "failed",
                    "error": self._failure_code(error),
                    "active_turn": None,
                },
                status="failed",
            )
            raise
        finally:
            service.repository.release_package_lease(
                workspace_id,
                package_id,
                lease.lease_id,
                chat_turn_id,
            )

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

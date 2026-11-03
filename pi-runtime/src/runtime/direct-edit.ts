/** 用户在画布上的明确编辑，与 Pi 工具共用同一提交器。 */
import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";
import { WorkspaceSessionStore } from "./session-store.js";
import { WorkspaceRevisionStore, semanticHash, validateOperations, type SemanticOperation, type WorkspaceCommitRequest, CommitError } from "./workspace-revision-store.js";
export async function directEdit(sessions: WorkspaceSessionStore, revisions: WorkspaceRevisionStore, request: {
  workspace_id: string; actor_id: string; submission_id: string; base_revision_id: string; operations: SemanticOperation[]; change_summary: string;
}) {
  validateOperations(request.operations);
  if (!request.actor_id || !request.submission_id || !request.base_revision_id) throw new CommitError("auth.invalid_identity", "用户编辑身份不完整");
  const base = revisions.getRevision(request.workspace_id,request.base_revision_id);
  if (!base) throw new CommitError("workspace.revision_not_found","基础版本不存在");
  // 手工编辑不能成为新的状态升级或交接确认入口。
  for (const op of request.operations) {
    const obj=base.objects[op.payload.id];
    if (!["create_object","update_object","change_status","create_relation","remove_relation"].includes(op.operation_type)) throw new CommitError("workspace.confirmation_required","该操作须通过对话确认");
    if (op.operation_type === "change_status" && op.payload.type_status !== "archived") throw new CommitError("workspace.confirmation_required","状态升级须通过对话确认");
    if (op.operation_type === "update_object" && obj && ["converged","clarified","effective","decided"].includes(obj.type_status)) throw new CommitError("workspace.confirmation_required","稳定卡片修订须通过对话确认");
    if (op.operation_type === "create_object" && ["converged","clarified","effective","decided","confirmed"].includes(op.payload.type_status)) throw new CommitError("workspace.confirmation_required","新对象不能直接进入稳定态");
  }
  // 画布编辑是 UI 上的用户动作，不是发给 Agent 的对话消息。
  // 记录 custom Entry 作为可追溯授权，消息投影只读取 message Entry，因此不会出现在右侧聊天里。
  const audit=await sessions.appendCustomEntry({
    workspaceId:request.workspace_id,
    customType:"workspace.direct-edit.authorization",
    data:{
      submission_id:request.submission_id,
      actor_id:request.actor_id,
      base_revision_id:request.base_revision_id,
      change_summary:request.change_summary,
      operations:request.operations,
      authorized_at:new Date().toISOString(),
    },
  });
  try {
    const commit: WorkspaceCommitRequest={contract_type:"workspace_commit_request",schema_version:"evocanvas.pi-runtime.v1",
      tool_context:{workspace_id:request.workspace_id,actor_id:request.actor_id,session_id:audit.sessionId,entry_id:audit.entryId,turn_id:request.submission_id,invocation_id:request.submission_id,tool_call_id:request.submission_id,current_revision_id:request.base_revision_id,capabilities:["workspace:commit"],instruction_bundle_version:"evocanvas.direct-edit.v1",active_skill_versions:[]},
      base_revision_id:request.base_revision_id,idempotency_key:request.submission_id,request_hash:semanticHash(request.operations),operations:request.operations,confirmation_refs:[audit.entryId],change_summary:request.change_summary};
    const result=await revisions.commit(commit,{confirmation_id:audit.entryId,entry_id:audit.entryId,target_object_ids:request.operations.map(op=>op.payload.id).filter(Boolean),actor_id:request.actor_id,confirmed_at:new Date().toISOString(),scope_hash:semanticHash({base_revision_id:request.base_revision_id,operations:request.operations})});
    const branch=await audit.session.branch("main",BACKGROUND_CONTEXT);
    await branch!.appendCustomEntry("workspace.direct-edit.receipt",{submission_id:request.submission_id,...result},BACKGROUND_CONTEXT);
    return result;
  }finally{audit.releaseLock();}
}

import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createModels, fauxProvider, fauxAssistantMessage, fauxToolCall } from "@earendil-works/pi-ai";
import { PiProviderRunExecutor } from "./executor.js";
import { WorkspaceSessionStore, computeContentHash } from "./session-store.js";
import { WorkspaceRevisionStore, semanticHash } from "./workspace-revision-store.js";
import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";

export function fixtureExecutor() {
  const faux = fauxProvider({ provider: "test-workspace", models: [{ id: "test-model" }] });
  const models = createModels(); models.setProvider(faux.provider);
  return { faux, executor: new PiProviderRunExecutor({ providerId: "test-workspace", modelId: "test-model", models }) };
}

test("真实 Pi Agent 在同一 Session 完成候选、确认、第二次修改及重启恢复", async () => {
  const dir = await mkdtemp(join(tmpdir(), "workspace-turn-"));
  let sessions = new WorkspaceSessionStore({ storageDir: join(dir,"sessions") });
  let revisions = new WorkspaceRevisionStore({ storageDir: join(dir,"revisions") });
  await sessions.init(); await revisions.init();
  const { faux, executor } = fixtureExecutor();
  const ops = [{ operation_id: "create", operation_type: "create_object", payload: { id: "c1", object_type: "constraint", title: "单机使用", type_status: "effective" } }];
  const edit = [{ operation_id: "edit", operation_type: "update_object", payload: { id: "c1", title: "单机离线使用" } }];
  faux.setResponses([
    fauxAssistantMessage(fauxToolCall("workspace_propose", { operations: ops, change_summary: "确认单机约束" })), fauxAssistantMessage("建议约束：单机使用。请确认。"),
    fauxAssistantMessage(fauxToolCall("workspace_commit", {})), fauxAssistantMessage("已应用单机约束。"),
    fauxAssistantMessage(fauxToolCall("workspace_propose", { operations: edit, change_summary: "改为离线" })), fauxAssistantMessage("建议改为单机离线使用，请确认。"),
    fauxAssistantMessage(fauxToolCall("workspace_commit", {})), fauxAssistantMessage("已应用离线约束。"),
  ]);
  const turn = async (id: string, text: string) => {
    const message = { role: "user" as const, content: text };
    const submission = await sessions.submitUserMessage({ workspaceId:"w", actorId:"u", submissionId:id, contentHash:computeContentHash(message), piUserMessage:message as any }); submission.releaseLock();
    return executor.executeWorkspace({ workspace_id:"w", submission_id:id }, { sessions, revisions }, new AbortController().signal);
  };
  try {
    assert.equal((await turn("s1","希望只在单机使用")).action,"awaiting_chat_confirmation");
    assert.equal(revisions.getPointers("w").current_revision_id,"rev_0");
    const applied = await turn("s2","确认");
    assert.equal(applied.action,"applied_confirmation");
    const first = revisions.getPointers("w").current_revision_id;
    assert.equal(revisions.getRevision("w",first)?.objects.c1.title,"单机使用");
    await sessions.close(); revisions.close();
    sessions = new WorkspaceSessionStore({ storageDir:join(dir,"sessions") }); await sessions.init();
    revisions = new WorkspaceRevisionStore({ storageDir:join(dir,"revisions") }); await revisions.init();
    // 重放入口回执，不能再次调用模型或提交。
    assert.deepEqual(await executor.executeWorkspace({ workspace_id:"w", submission_id:"s2" }, {sessions,revisions},new AbortController().signal),applied);
    await turn("s3","还需要离线");
    await turn("s4","确认");
    const second = revisions.getPointers("w").current_revision_id;
    assert.notEqual(first,second);
    const revision = revisions.getRevision("w",second)!;
    assert.equal(revision.objects.c1.title,"单机离线使用");
    assert.equal(revision.relations.length,0);
    assert.equal(revision.confirmations.length,2);
    const binding = await sessions.getBinding("w");
    const session = await sessions.getOrOpenSession(binding!);
    const entries = await (await session.branch("main",BACKGROUND_CONTEXT))!.findEntries(undefined,BACKGROUND_CONTEXT);
    assert.ok(entries.some(e => e.type === "message" && e.message.role === "toolResult"));
    assert.ok(entries.some(e => e.id === applied.assistant_entry_id));
  } finally { await sessions.close(); revisions.close(); await rm(dir,{recursive:true,force:true}); }
});

test("模型调用提交工具也不能把未确认回复当作授权", async () => {
  const dir=await mkdtemp(join(tmpdir(),"workspace-denied-"));
  const sessions=new WorkspaceSessionStore({storageDir:join(dir,"s")});await sessions.init();
  const revisions=new WorkspaceRevisionStore({storageDir:join(dir,"r")});await revisions.init();
  const {faux,executor}=fixtureExecutor();
  faux.setResponses([
    fauxAssistantMessage(fauxToolCall("workspace_propose",{operations:[{operation_id:"c",operation_type:"create_object",payload:{id:"c",object_type:"constraint",title:"离线使用"}}],change_summary:"离线约束"})),fauxAssistantMessage("建议离线使用。"),
    fauxAssistantMessage(fauxToolCall("workspace_commit",{})),fauxAssistantMessage("不应展示的成功回复"),
  ]);
  const turn=async(id:string,text:string)=>{
    const message={role:"user" as const,content:text};const submission=await sessions.submitUserMessage({workspaceId:"w",actorId:"u",submissionId:id,contentHash:computeContentHash(message),piUserMessage:message as any});submission.releaseLock();
    return executor.executeWorkspace({workspace_id:"w",submission_id:id},{sessions,revisions},new AbortController().signal);
  };
  try{
    await turn("s1","考虑离线使用");
    await assert.rejects(turn("s2","继续讨论，暂不确认"),{code:"workspace.confirmation_required"});
    assert.equal(revisions.getPointers("w").current_revision_id,"rev_0");
    assert.equal(sessions.lockManager.isLocked("w"),false);
  }finally{await sessions.close();revisions.close();await rm(dir,{recursive:true,force:true});}
});

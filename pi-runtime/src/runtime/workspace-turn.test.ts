import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createModels, fauxProvider, fauxAssistantMessage, fauxToolCall } from "@earendil-works/pi-ai";
import { FakeRunExecutor, PiProviderRunExecutor } from "./executor.js";
import { WorkspaceSessionStore, computeContentHash } from "./session-store.js";
import { WorkspaceRevisionStore, semanticHash, validateOperations } from "./workspace-revision-store.js";
import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";
import { explicitlyRequestsDecisionChallenge, loadProductMethods, productMethodPath } from "./product-methods.js";
import { verifySessionConfirmation } from "./workspace-turn.js";
import type { WorkspaceCommitRequest } from "./workspace-revision-store.js";

export function fixtureExecutor() {
  const faux = fauxProvider({ provider: "test-workspace", models: [{ id: "test-model" }] });
  const models = createModels(); models.setProvider(faux.provider);
  return { faux, executor: new PiProviderRunExecutor({ providerId: "test-workspace", modelId: "test-model", models }) };
}

test("不要提出候选或修改画布不会触发内部补提案，模型误调用也不能生成候选", async () => {
  for (const miscall of [false, true]) {
    const dir = await mkdtemp(join(tmpdir(), "workspace-no-candidate-"));
    const sessions = new WorkspaceSessionStore({ storageDir: join(dir, "sessions") });
    const revisions = new WorkspaceRevisionStore({ storageDir: join(dir, "revisions") });
    await sessions.init(); await revisions.init();
    const { faux, executor } = fixtureExecutor();
    faux.setResponses(miscall ? [fauxAssistantMessage(fauxToolCall("workspace_propose", { operations: [{ operation_id: "p", operation_type: "create_object", payload: { id: "p", object_type: "problem", title: "重复候选", type_status: "initial" } }], change_summary: "重复" })), fauxAssistantMessage("只复述范围与未决。")] : [fauxAssistantMessage("只复述范围与未决。")]);
    try {
      const message = { role: "user" as const, content: "只用两句话复述已经确认的改动范围和仍未验证的指标。不要提出候选或修改画布。" };
      const submission = await sessions.submitUserMessage({ workspaceId: "no-candidate", actorId: "u", submissionId: "s", contentHash: computeContentHash(message), piUserMessage: message as any });
      submission.releaseLock();
      const result = await executor.executeWorkspace({ workspace_id: "no-candidate", submission_id: "s" }, { sessions, revisions }, new AbortController().signal);
      assert.equal(result.action, "chat_only");
      assert.equal(revisions.getPointers("no-candidate").current_revision_id, "rev_0");
    } finally { await sessions.close(); revisions.close(); await rm(dir, { recursive: true, force: true }); }
  }
});

test("交接候选与确认回复不承诺未进入稳定结构的指标", async () => {
  const dir = await mkdtemp(join(tmpdir(), "workspace-handoff-disclosure-"));
  const sessions = new WorkspaceSessionStore({ storageDir: join(dir, "sessions") });
  const revisions = new WorkspaceRevisionStore({ storageDir: join(dir, "revisions") });
  await sessions.init(); await revisions.init();
  const { faux, executor } = fixtureExecutor();
  faux.setResponses([
    fauxAssistantMessage(fauxToolCall("workspace_propose", {
      operations: [{ operation_id: "p", operation_type: "create_object", payload: { id: "p", object_type: "problem", title: "申请退回补信息", type_status: "initial" } }], change_summary: "问题候选",
    })), fauxAssistantMessage("请确认问题候选。待确认内容：模型复制的历史候选"),
    fauxAssistantMessage(fauxToolCall("workspace_commit", {})), fauxAssistantMessage("问题已确认。"),
    fauxAssistantMessage(fauxToolCall("workspace_propose", {
      operations: [{ operation_id: "h", operation_type: "confirm_handoff", payload: {} }], change_summary: "交接候选",
    })), fauxAssistantMessage("已纳入退回率和成功率尚无数据。"),
    fauxAssistantMessage(fauxToolCall("workspace_commit", {})), fauxAssistantMessage("交接已确认，退回率和成功率均已保存。"),
  ]);
  const turn = async (id: string, content: string) => {
    const message = { role: "user" as const, content };
    const submission = await sessions.submitUserMessage({ workspaceId: "disclosure", actorId: "u", submissionId: id, contentHash: computeContentHash(message), piUserMessage: message as any });
    submission.releaseLock();
    return executor.executeWorkspace({ workspace_id: "disclosure", submission_id: id }, { sessions, revisions }, new AbortController().signal);
  };
  try {
    await turn("p", "请整理问题候选");
    await turn("pc", "确认");
    await turn("h", "生成交接候选");
    await turn("hc", "确认交接");
    const binding = await sessions.getBinding("disclosure");
    const session = await sessions.getOrOpenSession(binding!);
    const entries = await (await session.branch("main", BACKGROUND_CONTEXT))!.findEntries(undefined, BACKGROUND_CONTEXT);
    const assistants = entries.sort((a, b) => a.seq - b.seq).filter(e => e.type === "message" && e.message.role === "assistant" && e.message.stopReason === "stop");
    const visible = JSON.stringify(assistants.slice(-2));
    const allVisible = JSON.stringify(assistants);
    assert.equal(allVisible.includes("模型复制的历史候选"), false);
    assert.equal(visible.includes("退回率和成功率"), false);
    assert.ok(visible.includes("申请退回补信息"));
    assert.ok(visible.includes("实际保存的交接内容"), visible);
  } finally { await sessions.close(); revisions.close(); await rm(dir, { recursive: true, force: true }); }
});

test("产品方法实际读取才进入 Session Trace，确认后沿用候选的方法版本", async () => {
  const dir = await mkdtemp(join(tmpdir(), "workspace-method-trace-"));
  const sessions = new WorkspaceSessionStore({ storageDir: join(dir, "sessions") });
  const revisions = new WorkspaceRevisionStore({ storageDir: join(dir, "revisions") });
  await sessions.init(); await revisions.init();
  const { faux, executor } = fixtureExecutor();
  faux.setResponses([
    fauxAssistantMessage(fauxToolCall("read", { path: productMethodPath("scenario-shaping") })),
    fauxAssistantMessage(fauxToolCall("workspace_propose", {
      operations: [{ operation_id: "problem-1", operation_type: "create_object", payload: { id: "problem-1", object_type: "problem", title: "公共支出漏记", summary: "室友经常忘记登记公共支出", type_status: "initial" } }],
      change_summary: "形成问题候选",
    })),
    fauxAssistantMessage("当前场景中的问题是公共支出漏记。请确认候选。"),
    fauxAssistantMessage(fauxToolCall("workspace_commit", {})),
    fauxAssistantMessage("问题已确认。"),
  ]);
  const turn = async (id: string, content: string) => {
    const message = { role: "user" as const, content };
    const submission = await sessions.submitUserMessage({ workspaceId: "method-ws", actorId: "u", submissionId: id, contentHash: computeContentHash(message), piUserMessage: message as any });
    submission.releaseLock();
    return executor.executeWorkspace({ workspace_id: "method-ws", submission_id: id }, { sessions, revisions }, new AbortController().signal);
  };
  try {
    const proposed = await turn("method-1", "请根据室友经常漏记公共支出的场景，整理一个问题卡候选");
    const method = (await loadProductMethods()).get("scenario-shaping")!;
    assert.equal(proposed.action, "awaiting_chat_confirmation");
    assert.deepEqual(proposed.active_skill_versions, [method.ref]);
    assert.equal(revisions.getPointers("method-ws").current_revision_id, "rev_0");

    const applied = await turn("method-2", "确认");
    assert.equal(applied.action, "applied_confirmation");
    assert.deepEqual(applied.active_skill_versions, []);
    const revision = revisions.getRevision("method-ws", revisions.getPointers("method-ws").current_revision_id)!;
    assert.equal(revision.instruction_bundle_version, "evocanvas.workspace.v3");
    assert.deepEqual(revision.active_skill_versions, [method.ref]);
    assert.equal(revision.objects["problem-1"].confirmation_refs?.length, 1);

    const binding = await sessions.getBinding("method-ws");
    const session = await sessions.getOrOpenSession(binding!);
    const entries = await (await session.branch("main", BACKGROUND_CONTEXT))!.findEntries(undefined, BACKGROUND_CONTEXT);
    assert.ok(entries.some(entry => entry.type === "custom" && entry.customType === "workspace.method.used"
      && (entry.data as any).submission_id === "method-1" && (entry.data as any).content_hash === method.content_hash));
    const confirmedUser = entries.find(entry => entry.type === "message" && entry.message.role === "user"
      && entry.id !== entries.find(item => item.type === "message" && item.message.role === "user")?.id) as Extract<typeof entries[number], { type: "message" }>;
    const candidate = entries.find(entry => entry.type === "message" && entry.message.role === "toolResult"
      && entry.message.toolName === "workspace_propose") as Extract<typeof entries[number], { type: "message" }>;
    const candidateData = (candidate.message as any).details;
    const forged: WorkspaceCommitRequest = {
      contract_type: "workspace_commit_request", schema_version: "evocanvas.pi-runtime.v1",
      tool_context: { workspace_id: "method-ws", session_id: binding!.primary_session_id, turn_id: "method-2", entry_id: confirmedUser.id,
        invocation_id: "forged", tool_call_id: "forged", actor_id: "u", capabilities: ["workspace:commit"], current_revision_id: "rev_0",
        instruction_bundle_version: "evocanvas.workspace.v3", active_skill_versions: ["unread-method@1.0.0#sha256:fake"] },
      base_revision_id: candidateData.base_revision_id, idempotency_key: "forged", request_hash: "forged", operations: candidateData.operations,
      confirmation_refs: [confirmedUser.id], change_summary: candidateData.change_summary,
    };
    await assert.rejects(verifySessionConfirmation(sessions, forged), { code: "workspace.source_missing" });
  } finally { await sessions.close(); revisions.close(); await rm(dir, { recursive: true, force: true }); }
});

test("决策挑战仅在用户明确请求时可读取，挑战回复不改变 Revision", async () => {
  assert.equal(explicitlyRequestsDecisionChallenge("不要每轮挑战，但现在请红队一下这个方案"), true);
  assert.equal(explicitlyRequestsDecisionChallenge("请不要红队一下这个方案"), false);
  assert.equal(explicitlyRequestsDecisionChallenge("普通讨论，不用挑战"), false);
  const dir = await mkdtemp(join(tmpdir(), "workspace-explicit-challenge-"));
  const sessions = new WorkspaceSessionStore({ storageDir: join(dir, "sessions") });
  const revisions = new WorkspaceRevisionStore({ storageDir: join(dir, "revisions") });
  await sessions.init(); await revisions.init();
  const { faux, executor } = fixtureExecutor();
  let denied = false;
  let challengeLoaded = false;
  faux.setResponses([
    fauxAssistantMessage(fauxToolCall("read", { path: productMethodPath("decision-challenge") })),
    context => {
      denied = JSON.stringify(context.messages).includes("当前路径不是本轮可用的完整 Pi Skill");
      return fauxAssistantMessage("先说说你希望达到的结果。不能替你判断风险。 ");
    },
    fauxAssistantMessage(fauxToolCall("read", { path: productMethodPath("decision-challenge") })),
    context => {
      challengeLoaded = JSON.stringify(context.messages).includes("失败机制");
      return fauxAssistantMessage("当前方向有依据，但还需要验证使用场景；最小验证是观察实际登记流程。 ");
    },
    fauxAssistantMessage(fauxToolCall("read", { path: productMethodPath("decision-challenge") })),
    fauxAssistantMessage("下一轮只讨论补记动力：是否有真实记录说明室友会持续使用？"),
  ]);
  const turn = async (id: string, content: string) => {
    const message = { role: "user" as const, content };
    const submission = await sessions.submitUserMessage({ workspaceId: "challenge-ws", actorId: "u", submissionId: id, contentHash: computeContentHash(message), piUserMessage: message as any });
    submission.releaseLock();
    return executor.executeWorkspace({ workspace_id: "challenge-ws", submission_id: id }, { sessions, revisions }, new AbortController().signal);
  };
  try {
    const ordinary = await turn("challenge-1", "我想讨论公共支出漏记的问题");
    assert.equal(ordinary.action, "chat_only");
    assert.deepEqual(ordinary.active_skill_versions, []);
    assert.equal(denied, true);
    const challenged = await turn("challenge-2", "请红队一下这个公共支出登记方案，找找问题");
    assert.equal(challenged.action, "chat_only");
    assert.deepEqual(challenged.active_skill_versions, [(await loadProductMethods()).get("decision-challenge")!.ref]);
    assert.equal(challengeLoaded, true);
    const continued = await turn("challenge-3", "继续下一轮");
    assert.equal(continued.action, "chat_only");
    assert.deepEqual(continued.active_skill_versions, [(await loadProductMethods()).get("decision-challenge")!.ref]);
    assert.equal(revisions.getPointers("challenge-ws").current_revision_id, "rev_0");
  } finally { await sessions.close(); revisions.close(); await rm(dir, { recursive: true, force: true }); }
});

test("真实 Pi Agent 在同一 Session 完成候选、确认、第二次修改及重启恢复", async () => {
  const dir = await mkdtemp(join(tmpdir(), "workspace-turn-"));
  let sessions = new WorkspaceSessionStore({ storageDir: join(dir,"sessions") });
  let revisions = new WorkspaceRevisionStore({ storageDir: join(dir,"revisions") });
  await sessions.init(); await revisions.init();
  const { faux, executor } = fixtureExecutor();
  const ops = [{ operation_id: "create", operation_type: "create_object", payload: { id: "c1", object_type: "constraint", title: "单机使用", type_status: "effective" } }];
  const edit = [{ operation_id: "edit", operation_type: "update_object", payload: { id: "c1", title: "单机离线使用", data: { source_refs: [] } } }];
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
    assert.equal((await turn("s1","请提出“只在单机使用”的约束候选")).action,"awaiting_chat_confirmation");
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
    const firstSources = revisions.getRevision("w",first)!.objects.c1.data?.source_refs;
    assert.equal(firstSources.length, 1);
    assert.equal(revision.objects.c1.data?.source_refs.length, 2);
    assert.ok(revision.objects.c1.data?.source_refs.includes(firstSources[0]));
    assert.equal(revision.relations.length,0);
    assert.equal(revision.confirmations.length,2);
    const binding = await sessions.getBinding("w");
    const session = await sessions.getOrOpenSession(binding!);
    const entries = await (await session.branch("main",BACKGROUND_CONTEXT))!.findEntries(undefined,BACKGROUND_CONTEXT);
    assert.ok(entries.some(e => e.type === "message" && e.message.role === "toolResult"));
    assert.ok(entries.some(e => e.id === applied.assistant_entry_id));
  } finally { await sessions.close(); revisions.close(); await rm(dir,{recursive:true,force:true}); }
});

test("首轮开放输入即使误调用候选工具也只保留为普通对话", async () => {
  const dir = await mkdtemp(join(tmpdir(), "workspace-turn-initial-open-"));
  const sessions = new WorkspaceSessionStore({ storageDir: join(dir, "sessions") });
  const revisions = new WorkspaceRevisionStore({ storageDir: join(dir, "revisions") });
  await sessions.init(); await revisions.init();
  const { faux, executor } = fixtureExecutor();
  faux.setResponses([
    fauxAssistantMessage(fauxToolCall("workspace_propose", {
      operations: [{ operation_id: "p1", operation_type: "create_object", payload: { id: "p1", object_type: "problem", title: "模型擅自扩写", type_status: "initial" } }],
      change_summary: "不应在首轮直接收敛",
    })),
    fauxAssistantMessage("我先复述你的想法，并确认一个关键问题。"),
  ]);
  try {
    const message = { role: "user" as const, content: "我想做一个宿舍费用记录工具，室友常忘记登记公共支出。" };
    const submission = await sessions.submitUserMessage({
      workspaceId: "initial-open",
      actorId: "u",
      submissionId: "initial-s1",
      contentHash: computeContentHash(message),
      piUserMessage: message as any,
    });
    submission.releaseLock();
    const result = await executor.executeWorkspace(
      { workspace_id: "initial-open", submission_id: "initial-s1" },
      { sessions, revisions },
      new AbortController().signal,
    );
    assert.equal(result.action, "chat_only");
    assert.equal(revisions.getPointers("initial-open").current_revision_id, "rev_0");
  } finally {
    await sessions.close();
    revisions.close();
    await rm(dir, { recursive: true, force: true });
  }
});

test("明确候选请求在模型漏调工具时自动补齐受治理提案", async () => {
  const dir = await mkdtemp(join(tmpdir(), "workspace-turn-candidate-retry-"));
  const sessions = new WorkspaceSessionStore({ storageDir: join(dir, "sessions") });
  const revisions = new WorkspaceRevisionStore({ storageDir: join(dir, "revisions") });
  await sessions.init(); await revisions.init();
  const { faux, executor } = fixtureExecutor();
  faux.setResponses([
    fauxAssistantMessage("我先确认一下方向，再整理候选。"),
    fauxAssistantMessage(fauxToolCall("workspace_propose", {
      operations: [{ operation_id: "p1", operation_type: "create_object", payload: { id: "p1", object_type: "problem", title: "宿舍支出登记遗漏", type_status: "initial" } }],
      change_summary: "整理最小问题卡候选",
    })),
    fauxAssistantMessage("问题卡候选已整理，等待你的确认。"),
  ]);
  try {
    const message = { role: "user" as const, content: "请整理一个问题卡候选，不要直接写入画布。" };
    const submission = await sessions.submitUserMessage({
      workspaceId: "candidate-retry",
      actorId: "u",
      submissionId: "candidate-s1",
      contentHash: computeContentHash(message),
      piUserMessage: message as any,
    });
    submission.releaseLock();
    const result = await executor.executeWorkspace(
      { workspace_id: "candidate-retry", submission_id: "candidate-s1" },
      { sessions, revisions },
      new AbortController().signal,
    );
    assert.equal(result.action, "awaiting_chat_confirmation");
    assert.equal(revisions.getPointers("candidate-retry").current_revision_id, "rev_0");
  } finally {
    await sessions.close();
    revisions.close();
    await rm(dir, { recursive: true, force: true });
  }
});

test("用户明确写画布时自动提交卡片并补齐问题与澄清项关系", async () => {
  const dir = await mkdtemp(join(tmpdir(), "workspace-turn-auto-canvas-"));
  const sessions = new WorkspaceSessionStore({ storageDir: join(dir, "sessions") });
  const revisions = new WorkspaceRevisionStore({ storageDir: join(dir, "revisions") });
  await sessions.init();
  await revisions.init();
  const { faux, executor } = fixtureExecutor();
  faux.setResponses([
    fauxAssistantMessage(fauxToolCall("workspace_propose", {
      operations: [
        { operation_id: "p1", operation_type: "create_object", payload: { id: "p1", object_type: "problem", title: "宿舍公共支出记录", summary: "解决公共支出经常漏记。", type_status: "initial" } },
        { operation_id: "c1", operation_type: "create_object", payload: { id: "c1", object_type: "clarification", title: "补记动力", summary: "需要明确如何让室友愿意补记。", type_status: "open" } },
      ],
      change_summary: "把当前结论写入画布",
    })),
    fauxAssistantMessage("已自动写入画布，问题和待澄清项已经建立关系。"),
  ]);

  try {
    const message = { role: "user" as const, content: "请直接写入画布：把当前问题和待澄清项自动建卡并连线，不要让我再次手动确认" };
    const submission = await sessions.submitUserMessage({
      workspaceId: "auto-canvas",
      actorId: "u",
      submissionId: "auto-s1",
      contentHash: computeContentHash(message),
      piUserMessage: message as any,
    });
    submission.releaseLock();
    const result = await executor.executeWorkspace(
      { workspace_id: "auto-canvas", submission_id: "auto-s1" },
      { sessions, revisions },
      new AbortController().signal,
    );

    assert.equal(result.action, "auto_applied");
    const revisionId = revisions.getPointers("auto-canvas").current_revision_id;
    assert.notEqual(revisionId, "rev_0");
    const revision = revisions.getRevision("auto-canvas", revisionId)!;
    assert.equal(Object.keys(revision.objects).length, 2);
    assert.equal(revision.relations.length, 1);
    assert.deepEqual(revision.relations[0], {
      relation_id: revision.relations[0].relation_id,
      source_id: "c1",
      target_id: "p1",
      relation_type: "clarifies",
    });
    assert.equal(revision.confirmations.length, 1);

    const binding = await sessions.getBinding("auto-canvas");
    const session = await sessions.getOrOpenSession(binding!);
    const entries = await (await session.branch("main", BACKGROUND_CONTEXT))!.findEntries(undefined, BACKGROUND_CONTEXT);
    const assistantMessages = entries.filter((entry): entry is Extract<typeof entry, { type: "message" }> =>
      entry.type === "message" && entry.message.role === "assistant");
    assert.ok(assistantMessages.some((entry) => JSON.stringify(entry.message).includes("已自动写入")));
    assert.equal(assistantMessages.some((entry) => JSON.stringify(entry.message).includes("回复“确认”后生效")), false);
  } finally {
    await sessions.close();
    revisions.close();
    await rm(dir, { recursive: true, force: true });
  }
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

test("模型连接失败保留 Provider 错误原因，不再伪装成空回复", async () => {
  const dir = await mkdtemp(join(tmpdir(), "workspace-turn-error-"));
  const sessions = new WorkspaceSessionStore({ storageDir: join(dir, "s") });
  await sessions.init();
  const revisions = new WorkspaceRevisionStore({ storageDir: join(dir, "r") });
  await revisions.init();
  const { faux, executor } = fixtureExecutor();
  faux.setResponses([
    fauxAssistantMessage("", { stopReason: "error", errorMessage: "self-signed certificate in certificate chain" }),
  ]);
  const message = { role: "user" as const, content: "测试模型连接" };
  const submission = await sessions.submitUserMessage({
    workspaceId: "w",
    actorId: "u",
    submissionId: "error-1",
    contentHash: computeContentHash(message),
    piUserMessage: message as any,
  });
  submission.releaseLock();
  try {
    await assert.rejects(
      executor.executeWorkspace({ workspace_id: "w", submission_id: "error-1" }, { sessions, revisions }, new AbortController().signal),
      (error: any) => error?.code === "runtime.model_failed" && error.message.includes("self-signed certificate in certificate chain"),
    );
  } finally {
    await sessions.close();
    revisions.close();
    await rm(dir, { recursive: true, force: true });
  }
});

test("模型错误不会把 Provider 回显的 Key 片段带回 Session", async () => {
  const dir = await mkdtemp(join(tmpdir(), "workspace-turn-secret-"));
  const sessions = new WorkspaceSessionStore({ storageDir: join(dir, "s") });
  await sessions.init();
  const revisions = new WorkspaceRevisionStore({ storageDir: join(dir, "r") });
  await revisions.init();
  const { faux, executor } = fixtureExecutor();
  faux.setResponses([
    fauxAssistantMessage("", { stopReason: "error", errorMessage: "Authentication Fails, Your api key: ****alid is invalid" }),
  ]);
  const message = { role: "user" as const, content: "测试凭证错误脱敏" };
  const submission = await sessions.submitUserMessage({
    workspaceId: "w",
    actorId: "u",
    submissionId: "secret-1",
    contentHash: computeContentHash(message),
    piUserMessage: message as any,
  });
  submission.releaseLock();
  try {
    await assert.rejects(
      executor.executeWorkspace({ workspace_id: "w", submission_id: "secret-1" }, { sessions, revisions }, new AbortController().signal),
      (error: any) => error?.code === "runtime.model_failed"
        && error.message.includes("api key: [已隐藏]")
        && !error.message.includes("****alid"),
    );
    const binding = await sessions.getBinding("w");
    const session = await sessions.getOrOpenSession(binding!);
    const entries = await (await session.branch("main", BACKGROUND_CONTEXT))!.findEntries(undefined, BACKGROUND_CONTEXT);
    const assistant = entries.find((entry) => entry.type === "message" && entry.message.role === "assistant");
    assert.equal((assistant as any)?.message?.errorMessage?.includes("****alid"), false);
    assert.equal((assistant as any)?.message?.errorMessage?.includes("api key: [已隐藏]"), true);
  } finally {
    await sessions.close();
    revisions.close();
    await rm(dir, { recursive: true, force: true });
  }
});

test("受控 Fake Provider 也能执行 Primary Session 的候选与确认", async () => {
  const dir = await mkdtemp(join(tmpdir(), "workspace-turn-fake-provider-"));
  const sessions = new WorkspaceSessionStore({ storageDir: join(dir, "sessions") });
  const revisions = new WorkspaceRevisionStore({ storageDir: join(dir, "revisions") });
  await sessions.init();
  await revisions.init();
  const executor = new FakeRunExecutor();
  const turn = async (submissionId: string, content: string) => {
    const message = { role: "user" as const, content };
    const submission = await sessions.submitUserMessage({
      workspaceId: "fake-workspace",
      actorId: "u",
      submissionId,
      contentHash: computeContentHash(message),
      piUserMessage: message as any,
    });
    submission.releaseLock();
    return executor.executeWorkspace(
      { workspace_id: "fake-workspace", submission_id: submissionId },
      { sessions, revisions },
      new AbortController().signal,
    );
  };

  try {
    const initial = await turn("fake-s0", "我想做一个学生宿舍费用记录工具，室友经常忘记登记公共支出。");
    assert.equal(initial.action, "chat_only");
    assert.equal(revisions.getPointers("fake-workspace").current_revision_id, "rev_0");

    const proposed = await turn("fake-s1", "我想做一个学生宿舍费用记录工具，请先整理问题卡候选");
    assert.equal(proposed.action, "awaiting_chat_confirmation");
    assert.equal(revisions.getPointers("fake-workspace").current_revision_id, "rev_0");

    const applied = await turn("fake-s2", "确认");
    assert.equal(applied.action, "applied_confirmation");
    const revisionId = revisions.getPointers("fake-workspace").current_revision_id;
    const revision = revisions.getRevision("fake-workspace", revisionId)!;
    assert.ok(Object.values(revision.objects).some((object) => object.object_type === "problem" && object.title === "学生记账容易遗漏"));

    const chatOnly = await turn("fake-s3", "你好");
    assert.equal(chatOnly.action, "chat_only");
    assert.equal(revisions.getPointers("fake-workspace").current_revision_id, revisionId);
  } finally {
    await sessions.close();
    revisions.close();
    await rm(dir, { recursive: true, force: true });
  }
});

test("validateOperations 与 commit 容错规范化自然语言关系与无ID对象", async () => {
  const dir = await mkdtemp(join(tmpdir(), "workspace-norm-"));
  const sessions = new WorkspaceSessionStore({ storageDir: join(dir, "sessions") });
  const revisions = new WorkspaceRevisionStore({ storageDir: join(dir, "revisions") });
  await sessions.init();
  await revisions.init();

  try {
    const message = { role: "user" as const, content: "确认" };
    const sub = await sessions.submitUserMessage({
      workspaceId: "norm-ws",
      actorId: "u1",
      submissionId: "sub-norm-1",
      contentHash: computeContentHash(message),
      piUserMessage: message as any,
    });
    sub.releaseLock();
    const binding = (await sessions.getBinding("norm-ws"))!;

    // 模拟真实模型输出：create_relation 在前、使用 from/to、使用自然语义关系 constrains、缺少 relation_id
    const rawOperations: any[] = [
      {
        operation_id: "op_r1",
        operation_type: "create_relation",
        payload: {
          from: "p1",
          to: "c1",
          relation_type: "constrains",
        },
      },
      {
        operation_id: "op_1",
        operation_type: "create_object",
        payload: {
          id: "p1",
          object_type: "problem",
          title: "核心痛点",
          summary: "问题摘要",
        },
      },
      {
        operation_id: "op_2",
        operation_type: "create_object",
        payload: {
          id: "c1",
          object_type: "constraint",
          title: "防刷约束",
          summary: "必须防止刷单",
        },
      },
    ];

    validateOperations(rawOperations);
    assert.equal(rawOperations[0].payload.source_id, "p1");
    assert.equal(rawOperations[0].payload.target_id, "c1");
    assert.equal(rawOperations[0].payload.relation_type, "supports");
    assert.ok(rawOperations[0].payload.relation_id);

    // 排序后提交
    const hash = semanticHash({ base_revision_id: "rev_0", operations: rawOperations });
    const verified = {
      confirmation_id: sub.receipt.entry_id,
      entry_id: sub.receipt.entry_id,
      target_object_ids: ["p1", "c1"],
      confirmed_at: new Date().toISOString(),
      actor_id: "u1",
      scope_hash: hash,
    };

    const commitResult = await revisions.commit({
      contract_type: "workspace_commit_request",
      schema_version: "evocanvas.pi-runtime.v1",
      tool_context: {
        workspace_id: "norm-ws",
        session_id: binding.primary_session_id,
        turn_id: "sub-norm-1",
        entry_id: sub.receipt.entry_id,
        invocation_id: "call_norm",
        tool_call_id: "call_norm",
        actor_id: "u1",
        capabilities: ["workspace:commit"],
        current_revision_id: "rev_0",
        instruction_bundle_version: "v1",
        active_skill_versions: [],
      },
      base_revision_id: "rev_0",
      operations: rawOperations,
      confirmation_refs: [sub.receipt.entry_id],
      change_summary: "规范化测试",
      idempotency_key: "k1",
      request_hash: hash,
    }, verified);

    assert.equal(commitResult.operations_applied, 3);
    const rev = revisions.getRevision("norm-ws", commitResult.new_revision_id)!;
    assert.equal(Object.keys(rev.objects).length, 2);
    assert.equal(rev.relations.length, 1);
    assert.equal(rev.relations[0].source_id, "p1");
    assert.equal(rev.relations[0].target_id, "c1");
    assert.equal(rev.relations[0].relation_type, "supports");
  } finally {
    await sessions.close();
    revisions.close();
    await rm(dir, { recursive: true, force: true });
  }
});

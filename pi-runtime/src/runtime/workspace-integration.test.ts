import { strict as assert } from "node:assert";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
  WorkspaceRevisionStore,
  type WorkspaceCommitRequest,
  type ToolContext,
  CommitError,
  semanticHash,
} from "./workspace-revision-store.js";
import { createWorkspaceTransformContext } from "./context-projector.js";
import {
  ToolRecoveryManager,
  ToolRecoveryError,
  type ToolDefinition,
  type ToolExecutionRecord,
} from "./tool-recovery.js";

function dummyToolContext(workspaceId: string, revId: string): ToolContext {
  return {
    workspace_id: workspaceId,
    session_id: "sess-1",
    turn_id: "turn-1",
    entry_id: "entry-1",
    invocation_id: "inv-1",
    tool_call_id: "tc-1",
    actor_id: "user-1",
    capabilities: ["workspace:commit"],
    current_revision_id: revId,
    instruction_bundle_version: "v1",
    active_skill_versions: ["vibe@1"],
  };
}

function verified(request: WorkspaceCommitRequest) {
  return { confirmation_id: request.confirmation_refs[0], entry_id: "verified-user-entry", actor_id: request.tool_context.actor_id, target_object_ids: [], confirmed_at: new Date().toISOString(), scope_hash: semanticHash({base_revision_id: request.base_revision_id, operations: request.operations}) };
}

test("WorkspaceRevisionStore & workspace.commit 9-step check and immutable revisions", async () => {
  const dir = await mkdtemp(join(tmpdir(), "rev-store-test-"));
  try {
    const store = new WorkspaceRevisionStore({ storageDir: dir });
    await store.init();

    const pointers0 = await store.getPointers("ws-test");
    assert.equal(pointers0.current_revision_id, "rev_0");
    assert.equal(pointers0.latest_confirmed_handoff_revision_id, null);

    // 1. 未确认的 decision/constraint 会被拒绝 (workspace.confirmation_required)
    const unconfirmedRequest: WorkspaceCommitRequest = {
      contract_type: "workspace_commit_request",
      schema_version: "evocanvas.pi-runtime.v1",
      tool_context: dummyToolContext("ws-test", "rev_0"),
      base_revision_id: "rev_0",
      idempotency_key: "commit-1",
      request_hash: "sha256:1111",
      operations: [
        {
          operation_id: "op-1",
          operation_type: "create_object",
          payload: {
            object_type: "constraint",
            title: "首版必须支持单机 SQLite",
          },
        },
      ],
      confirmation_refs: [], // 缺少确认！
      change_summary: "试图直接创建约束",
    };

    await assert.rejects(
      async () => store.commit(unconfirmedRequest),
      (err: any) => err instanceof CommitError && err.code === "workspace.confirmation_required",
    );

    // 确认 revision 没变
    const pointersAfterFail = await store.getPointers("ws-test");
    assert.equal(pointersAfterFail.current_revision_id, "rev_0");

    // 2. 提供 confirmation_refs，成功提交创建约束卡
    const confirmedRequest: WorkspaceCommitRequest = {
      ...unconfirmedRequest,
      confirmation_refs: ["entry-user-confirmed-1"],
    };
    const result1 = await store.commit(confirmedRequest, verified(confirmedRequest));
    assert.equal(result1.operations_applied, 1);
    assert.ok(result1.new_revision_id);
    assert.notEqual(result1.new_revision_id, "rev_0");

    const pointers1 = await store.getPointers("ws-test");
    assert.equal(pointers1.current_revision_id, result1.new_revision_id);

    const rev1 = await store.getRevision("ws-test", result1.new_revision_id);
    assert.ok(rev1);
    const objects = Object.values(rev1.objects);
    assert.equal(objects.length, 1);
    assert.equal(objects[0].object_type, "constraint");
    assert.equal(objects[0].title, "首版必须支持单机 SQLite");

    // 3. 幂等重试返回相同 CommitResult
    const retryResult = await store.commit(confirmedRequest, verified(confirmedRequest));
    assert.equal(retryResult.new_revision_id, result1.new_revision_id);
    assert.equal(retryResult.commit_id, result1.commit_id);

    // 4. 过期 base_revision 被拒绝 (workspace.stale_revision)
    const staleRequest: WorkspaceCommitRequest = {
      contract_type: "workspace_commit_request",
      schema_version: "evocanvas.pi-runtime.v1",
      tool_context: dummyToolContext("ws-test", "rev_0"),
      base_revision_id: "rev_0", // 已经过时！当前是 result1.new_revision_id
      idempotency_key: "commit-stale",
      request_hash: "sha256:2222",
      operations: [
        {
          operation_id: "op-2",
          operation_type: "create_object",
          payload: {
            object_type: "problem",
            title: "多宿主并发写入冲突",
          },
        },
      ],
      confirmation_refs: [],
      change_summary: "stale commit",
    };

    await assert.rejects(
      async () => store.commit(staleRequest),
      (err: any) => err instanceof CommitError && err.code === "workspace.stale_revision",
    );

    // 5. 提交确认交接 (confirm_handoff)：独立推进 latest_confirmed_handoff_revision_id
    const handoffCommitRequest: WorkspaceCommitRequest = {
      contract_type: "workspace_commit_request",
      schema_version: "evocanvas.pi-runtime.v1",
      tool_context: dummyToolContext("ws-test", result1.new_revision_id),
      base_revision_id: result1.new_revision_id,
      idempotency_key: "commit-handoff",
      request_hash: "sha256:3333",
      operations: [
        {
          operation_id: "op-handoff",
          operation_type: "confirm_handoff",
          payload: { target_revision_id: result1.new_revision_id, scope_object_ids: Object.keys(rev1.objects).sort(), disclosed_summary: "约束：首版必须支持单机 SQLite" },
        },
      ],
      confirmation_refs: ["entry-handoff-confirmed"],
      change_summary: "确认首版交接",
    };
    const handoffResult = await store.commit(handoffCommitRequest, verified(handoffCommitRequest));
    assert.equal(handoffResult.handoff_impact, "confirmed");

    const pointers2 = await store.getPointers("ws-test");
    assert.equal(pointers2.current_revision_id, handoffResult.new_revision_id);
    assert.equal(pointers2.latest_confirmed_handoff_revision_id, handoffResult.new_revision_id);

    // 6. 后续普通更新只推进 current_revision_id，latest_confirmed_handoff_revision_id 保持不变
    const followupRequest: WorkspaceCommitRequest = {
      contract_type: "workspace_commit_request",
      schema_version: "evocanvas.pi-runtime.v1",
      tool_context: dummyToolContext("ws-test", pointers2.current_revision_id),
      base_revision_id: pointers2.current_revision_id,
      idempotency_key: "commit-followup",
      request_hash: "sha256:4444",
      operations: [
        {
          operation_id: "op-problem",
          operation_type: "create_object",
          payload: {
            object_type: "problem",
            title: "后续新问题",
            type_status: "initial",
          },
        },
      ],
      confirmation_refs: ["followup-confirmation"],
      change_summary: "新增后续问题",
    };
    const followupResult = await store.commit(followupRequest, verified(followupRequest));
    const pointers3 = await store.getPointers("ws-test");
    assert.equal(pointers3.current_revision_id, followupResult.new_revision_id);
    // 关键断言：handoff 指针与 current 指针独立推进！
    assert.equal(pointers3.latest_confirmed_handoff_revision_id, handoffResult.new_revision_id);
    assert.notEqual(pointers3.latest_confirmed_handoff_revision_id, pointers3.current_revision_id);

    // 7. transformContext 测试：每次读取正确 current Revision
    const transformContext = createWorkspaceTransformContext("ws-test", store);
    const messages = [{ role: "user" as const, content: "你好", timestamp: Date.now() }];
    const transformed = await transformContext(messages);
    assert.equal(transformed.length, 2);
    assert.equal(transformed[0].role, "user");
    const firstContent = (transformed[0] as any).content;
    assert.ok(typeof firstContent === "string" && firstContent.includes(pointers3.current_revision_id));
    assert.ok(typeof firstContent === "string" && firstContent.includes("后续新问题"));
    // 原始用户消息保持不变
    assert.equal((transformed[1] as any).content, "你好");
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("ToolRecoveryManager enforces replay policies and unknown status rules", () => {
  const manager = new ToolRecoveryManager();

  const safeReadTool: ToolDefinition = {
    name: "workspace.read",
    version: "v1",
    sideEffectClass: "none",
    replay: "safe",
  };

  const irreversibleTool: ToolDefinition = {
    name: "external.post",
    version: "v1",
    sideEffectClass: "external",
    replay: "never",
    requiresExternalAuth: true,
  };

  // 1. 外部副作用需要独立动作级授权
  assert.throws(
    () => manager.evaluateReplay(irreversibleTool, "idem-ext-1", "hash-1", false),
    (err: any) => err instanceof ToolRecoveryError && err.code === "external.action_unauthorized",
  );

  // 授权后允许初次执行
  const eval1 = manager.evaluateReplay(irreversibleTool, "idem-ext-1", "hash-1", true);
  assert.equal(eval1.allowExecution, true);

  // 2. 模拟工具结果为 unknown
  const recordUnknown: ToolExecutionRecord = {
    contract_type: "tool_execution_record",
    schema_version: "evocanvas.pi-runtime.v1",
    tool_name: "external.post",
    tool_version: "v1",
    tool_context: dummyToolContext("ws-1", "rev_0"),
    side_effect_class: "external",
    replay: "never",
    result_status: "unknown",
    request_hash: "hash-1",
    idempotency_key: "idem-ext-1",
    started_at: new Date().toISOString(),
    finished_at: new Date().toISOString(),
  };
  manager.recordExecution(recordUnknown);

  // 3. replay=never 且结果未知时禁止自动重放 (tool.replay_forbidden)
  assert.throws(
    () => manager.evaluateReplay(irreversibleTool, "idem-ext-1", "hash-1", true),
    (err: any) => err instanceof ToolRecoveryError && err.code === "tool.replay_forbidden",
  );

  // 4. safe 工具初次执行与已成功缓存
  const recordSuccess: ToolExecutionRecord = {
    contract_type: "tool_execution_record",
    schema_version: "evocanvas.pi-runtime.v1",
    tool_name: "workspace.read",
    tool_version: "v1",
    tool_context: dummyToolContext("ws-1", "rev_0"),
    side_effect_class: "none",
    replay: "safe",
    result_status: "success",
    request_hash: "hash-read-1",
    idempotency_key: "idem-read-1",
    started_at: new Date().toISOString(),
    finished_at: new Date().toISOString(),
  };
  manager.recordExecution(recordSuccess);

  const evalSafe = manager.evaluateReplay(safeReadTool, "idem-read-1", "hash-read-1");
  assert.equal(evalSafe.allowExecution, false);
  assert.equal(evalSafe.reason, "already_succeeded");

  // 5. 相同幂等键使用不同 request_hash 被拒绝
  assert.throws(
    () => manager.evaluateReplay(safeReadTool, "idem-read-1", "different-hash"),
    (err: any) => err instanceof ToolRecoveryError && err.code === "tool.request_hash_mismatch",
  );
});

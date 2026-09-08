import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { createPiRuntimeServer } from "../server.js";
import { computeContentHash, WorkspaceSessionStore } from "./session-store.js";
import { WorkspaceRevisionStore } from "./workspace-revision-store.js";

function sha256(text: string): string {
  return `sha256:${createHash("sha256").update(text).digest("hex")}`;
}

test("PiRuntimeServer exposes v1 workspace endpoints (binding, submission, commit, projection, revision, lifecycle)", async () => {
  const tempDir = await mkdtemp(join(tmpdir(), "pi-server-v1-test-"));
  const sessionStore = new WorkspaceSessionStore({ storageDir: join(tempDir, "sessions") });
  const revisionStore = new WorkspaceRevisionStore({ storageDir: join(tempDir, "revisions") });

  const runtime = createPiRuntimeServer({
    host: "127.0.0.1",
    port: 0,
    sessionStore,
    revisionStore,
  });

  await runtime.listen();
  const address = runtime.server.address();
  const port = typeof address === "object" && address ? address.port : 8790;
  const baseUrl = `http://127.0.0.1:${port}`;

  const wsId = "ws_test_http_1";

  try {
    // 1. Initial binding should return 404 (empty workspace does not create session)
    const bindingRes1 = await fetch(`${baseUrl}/v1/workspaces/${wsId}/binding`);
    assert.equal(bindingRes1.status, 404);

    // 2. Initial projection should return 200 with empty cards (initialized rev_0)
    const projRes1 = await fetch(`${baseUrl}/v1/workspaces/${wsId}/projection`);
    assert.equal(projRes1.status, 200);
    const proj1 = await projRes1.json() as any;
    assert.equal(proj1.projected_revision_id, "rev_0");
    assert.equal(proj1.cards.length, 0);

    // 3. User Submission
    const rawText = "我需要一个针对学生群体的记账工具";
    const subHash = sha256(rawText);
    const subPayload = {
      contract_type: "user_submission_request",
      schema_version: "evocanvas.pi-runtime.v1",
      submission_id: "sub_http_001",
      content_hash: subHash,
      workspace_id: wsId,
      actor_id: "user_1",
      pi_user_message: {
        role: "user",
        content: [{ type: "text", text: rawText }],
      },
    };

    subPayload.content_hash = computeContentHash(subPayload.pi_user_message);
    const subRes = await fetch(`${baseUrl}/v1/workspaces/${wsId}/submissions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(subPayload),
    });
    assert.equal(subRes.status, 200);
    const subReceipt = await subRes.json() as any;
    assert.equal(subReceipt.contract_type, "user_submission_receipt");
    assert.equal(subReceipt.submission_id, "sub_http_001");
    assert.equal(subReceipt.status, "accepted");

    // Duplicate submission idempotency
    const subDupRes = await fetch(`${baseUrl}/v1/workspaces/${wsId}/submissions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(subPayload),
    });
    assert.equal(subDupRes.status, 200);
    const subDupReceipt = await subDupRes.json() as any;
    assert.equal(subDupReceipt.status, "duplicate");
    assert.equal(subDupReceipt.entry_id, subReceipt.entry_id);

    // 4. Binding should now be ready
    const bindingRes2 = await fetch(`${baseUrl}/v1/workspaces/${wsId}/binding`);
    assert.equal(bindingRes2.status, 200);
    const binding2 = await bindingRes2.json() as any;
    assert.equal(binding2.status, "ready");
    assert.equal(binding2.primary_session_id, subReceipt.session_id);

    // 5. Workspace Commit (create problem card)
    const commitPayload = {
      contract_type: "workspace_commit_request",
      schema_version: "evocanvas.pi-runtime.v1",
      tool_context: {
        workspace_id: wsId,
        session_id: binding2.primary_session_id,
        turn_id: "turn_1",
        entry_id: subReceipt.entry_id,
        invocation_id: "inv_1",
        tool_call_id: "call_1",
        actor_id: "user_1",
        capabilities: ["workspace:commit"],
        current_revision_id: "rev_0",
        instruction_bundle_version: "1.0",
        active_skill_versions: [],
      },
      base_revision_id: "rev_0",
      idempotency_key: "idem_http_commit_1",
      request_hash: "hash_c1",
      operations: [
        {
          operation_id: "op_c1",
          operation_type: "create_object",
          payload: {
            id: "prob_1",
            object_type: "evidence",
            title: "记账繁琐容易遗漏",
            type_status: "collected",
            summary: rawText,
          },
        },
      ],
      confirmation_refs: [],
      change_summary: "创建记账繁琐问题卡",
    };

    const commitRes = await fetch(`${baseUrl}/v1/workspaces/${wsId}/commit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(commitPayload),
    });
    assert.equal(commitRes.status, 200);
    const commitResult = await commitRes.json() as any;
    assert.equal(commitResult.contract_type, "workspace_commit_result");
    assert.equal(commitResult.operations_applied, 1);
    const newRevId = commitResult.new_revision_id;
    assert.notEqual(newRevId, "rev_0");

    // 6. Query revision by ID
    const revRes = await fetch(`${baseUrl}/v1/workspaces/${wsId}/revisions/${newRevId}`);
    assert.equal(revRes.status, 200);
    const revData = await revRes.json() as any;
    assert.equal(revData.revision_id, newRevId);
    assert.equal(revData.objects.prob_1.title, "记账繁琐容易遗漏");

    // 7. Check projection updated
    const projRes2 = await fetch(`${baseUrl}/v1/workspaces/${wsId}/projection`);
    assert.equal(projRes2.status, 200);
    const proj2 = await projRes2.json() as any;
    assert.equal(proj2.projected_revision_id, newRevId);
    assert.equal(proj2.cards.length, 1);
    assert.equal(proj2.cards[0].card_id, "prob_1");
    assert.equal(proj2.cards[0].card_type, "evidence");
    assert.equal(proj2.cards[0].stage, "discovery");

    // 8. Session Lifecycle (archive)
    const lifecyclePayload = {
      contract_type: "session_lifecycle_command",
      schema_version: "evocanvas.pi-runtime.v1",
      lifecycle_operation_id: "life_op_1",
      workspace_id: wsId,
      action: "archive",
      idempotency_key: "idem_life_1",
    };
    const lifeRes = await fetch(`${baseUrl}/v1/workspaces/${wsId}/lifecycle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(lifecyclePayload),
    });
    assert.equal(lifeRes.status, 200);
    const lifeResult = await lifeRes.json() as any;
    assert.equal(lifeResult.outcome, "archived");

    // Check binding is now archived
    const bindingRes3 = await fetch(`${baseUrl}/v1/workspaces/${wsId}/binding`);
    assert.equal(bindingRes3.status, 200);
    const binding3 = await bindingRes3.json() as any;
    assert.equal(binding3.status, "archived");
  } finally {
    await runtime.close();
    await rm(tempDir, { recursive: true, force: true });
  }
});

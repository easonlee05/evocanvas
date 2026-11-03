import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";
import { WorkspaceSessionStore } from "./session-store.js";
import { directEdit } from "./direct-edit.js";
import { WorkspaceRevisionStore } from "./workspace-revision-store.js";

test("画布直接编辑写入审计 custom Entry，不进入 Agent 对话消息", async () => {
  const dir = await mkdtemp(join(tmpdir(), "workspace-direct-edit-"));
  const sessions = new WorkspaceSessionStore({ storageDir: join(dir, "sessions") });
  const revisions = new WorkspaceRevisionStore({ storageDir: join(dir, "revisions") });
  await sessions.init();
  await revisions.init();

  try {
    const result = await directEdit(sessions, revisions, {
      workspace_id: "direct-edit",
      actor_id: "u",
      submission_id: "edit-1",
      base_revision_id: "rev_0",
      operations: [{
        operation_id: "evidence-1",
        operation_type: "create_object",
        payload: { id: "evidence-1", object_type: "evidence", title: "用户原话", summary: "用户原话" },
      }],
      change_summary: "新增证据卡",
    });

    assert.notEqual(result.new_revision_id, "rev_0");
    const binding = await sessions.getBinding("direct-edit");
    assert.ok(binding);
    const session = await sessions.getOrOpenSession(binding!);
    const branch = await session.branch("main", BACKGROUND_CONTEXT);
    const entries = await branch!.findEntries(undefined, BACKGROUND_CONTEXT);
    assert.equal(entries.filter((entry) => entry.type === "message").length, 0);
    assert.deepEqual(
      new Set(entries.filter((entry) => entry.type === "custom").map((entry) => entry.customType)),
      new Set(["workspace.direct-edit.authorization", "workspace.direct-edit.receipt"]),
    );
  } finally {
    await sessions.close();
    revisions.close();
    await rm(dir, { recursive: true, force: true });
  }
});

import { strict as assert } from "node:assert";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
  computeContentHash,
  HostSessionLockManager,
  SessionLockedError,
  SubmissionConflictError,
  WorkspaceSessionStore,
} from "./session-store.js";
import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";

test("HostSessionLockManager enforces exclusive lock per workspace", () => {
  const manager = new HostSessionLockManager();
  const release = manager.acquire("ws-1");
  assert.equal(manager.isLocked("ws-1"), true);
  assert.equal(manager.isLocked("ws-2"), false);

  assert.throws(() => manager.acquire("ws-1"), SessionLockedError);

  release();
  assert.equal(manager.isLocked("ws-1"), false);
  const releaseAgain = manager.acquire("ws-1");
  releaseAgain();
});

test("WorkspaceSessionStore: empty workspace does not create session", async () => {
  const dir = await mkdtemp(join(tmpdir(), "pi-store-test-"));
  try {
    const store = new WorkspaceSessionStore({ storageDir: dir });
    await store.init();

    const binding = await store.getBinding("empty-ws");
    assert.equal(binding, null);
    await store.close();
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("WorkspaceSessionStore: first message creates Primary Session, idempotency, restart recovery", async () => {
  const dir = await mkdtemp(join(tmpdir(), "pi-store-test-"));
  try {
    const store1 = new WorkspaceSessionStore({ storageDir: dir });
    await store1.init();

    const userMessage = { role: "user" as const, content: "把这个问题固定为正式待澄清项", timestamp: Date.now() };
    const hash = computeContentHash(userMessage);

    // 1. 第一条真实用户消息创建 Primary Session
    const firstResult = await store1.submitUserMessage({
      submissionId: "sub-1",
      contentHash: hash,
      workspaceId: "ws-1",
      actorId: "user-1",
      piUserMessage: userMessage,
    });
    firstResult.releaseLock();

    assert.equal(firstResult.receipt.status, "accepted");
    assert.equal(firstResult.receipt.binding_status, "ready");
    assert.ok(firstResult.receipt.session_id);
    assert.ok(firstResult.receipt.entry_id);

    const binding = await store1.getBinding("ws-1");
    assert.ok(binding);
    assert.equal(binding.status, "ready");
    assert.equal(binding.primary_session_id, firstResult.receipt.session_id);

    // 2. 相同 submission_id + content_hash 重试返回 duplicate，同一个 entry_id
    const duplicateResult = await store1.submitUserMessage({
      submissionId: "sub-1",
      contentHash: hash,
      workspaceId: "ws-1",
      actorId: "user-1",
      piUserMessage: userMessage,
    });
    duplicateResult.releaseLock();

    assert.equal(duplicateResult.receipt.status, "duplicate");
    assert.equal(duplicateResult.receipt.entry_id, firstResult.receipt.entry_id);
    assert.equal(duplicateResult.receipt.session_id, firstResult.receipt.session_id);

    // 3. 相同 submission_id 携带不同 hash 被拒绝 (submission_conflict)
    await assert.rejects(
      async () => {
        await store1.submitUserMessage({
          submissionId: "sub-1",
          contentHash: "sha256:differenthash111111111111111111111111111111111111111111111111111111",
          workspaceId: "ws-1",
          actorId: "user-1",
          piUserMessage: { role: "user", content: "不一样的消息", timestamp: Date.now() },
        });
      },
      SubmissionConflictError,
    );

    // 4. 第二条真实消息进入同一个 Primary Session
    const userMessage2 = { role: "user" as const, content: "第二条消息", timestamp: Date.now() };
    const hash2 = computeContentHash(userMessage2);
    const secondResult = await store1.submitUserMessage({
      submissionId: "sub-2",
      contentHash: hash2,
      workspaceId: "ws-1",
      actorId: "user-1",
      piUserMessage: userMessage2,
    });
    secondResult.releaseLock();
    assert.equal(secondResult.receipt.session_id, firstResult.receipt.session_id);
    assert.notEqual(secondResult.receipt.entry_id, firstResult.receipt.entry_id);

    await store1.close();

    // 5. 进程重启恢复同一个 Primary Session 和历史 Entry
    const store2 = new WorkspaceSessionStore({ storageDir: dir });
    await store2.init();

    const restoredBinding = await store2.getBinding("ws-1");
    assert.ok(restoredBinding);
    assert.equal(restoredBinding.primary_session_id, firstResult.receipt.session_id);

    const session = await store2.getOrOpenSession(restoredBinding);
    const branch = await session.branch("main", BACKGROUND_CONTEXT);
    assert.ok(branch);
    const entries = await branch.findEntries({ order: "oldestFirst" }, BACKGROUND_CONTEXT);
    assert.equal(entries.length, 2);
    assert.equal(entries[0].id, firstResult.receipt.entry_id);
    assert.equal(entries[1].id, secondResult.receipt.entry_id);

    // 6. 归档测试
    await store2.archiveWorkspace("ws-1");
    const archivedBinding = await store2.getBinding("ws-1");
    assert.equal(archivedBinding?.status, "archived");

    // 7. 换代 replace 测试
    const replacementId = "replacement-sess-1";
    const replaced = await store2.replaceSession("ws-1", replacementId);
    assert.equal(replaced.primary_session_id, replacementId);
    assert.equal(replaced.predecessor_session_id, firstResult.receipt.session_id);

    // 8. retention_held 测试
    const held = await store2.deleteWorkspace("ws-1", { retainReason: "legal_hold" });
    assert.equal(held.outcome, "retention_held");

    // 9. 真正删除测试
    const deleted = await store2.deleteWorkspace("ws-1");
    assert.equal(deleted.outcome, "deleted");

    await store2.close();
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

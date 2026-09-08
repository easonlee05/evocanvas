import { semanticHash } from "./workspace-revision-store.js";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, writeFile, unlink, rename } from "node:fs/promises";
import { join } from "node:path";
import { BACKGROUND_CONTEXT } from "@earendil-works/chord/context";
import {
  createNodeSqliteFactory,
  SqliteSessionRepo,
} from "@earendil-works/pi-session-backend-sqlite-node";
import type { AgentMessage } from "@earendil-works/pi-agent-core";
import type { V1SessionLifecycleCommand, V1SessionLifecycleResult } from "../contracts.js";

export type SqliteOpenSession = Awaited<ReturnType<SqliteSessionRepo["create"]>>;
export type SqliteSessionMetadata = Parameters<SqliteSessionRepo["open"]>[0];

export type BindingStatus = "binding" | "ready" | "unavailable" | "archived";

export interface WorkspaceSessionBinding {
  contract_type: "workspace_session_binding";
  schema_version: "evocanvas.pi-runtime.v1";
  workspace_id: string;
  primary_session_id: string;
  main_lane: "main";
  status: BindingStatus;
  pi_session_format_version: string;
  session_file_ref: string;
  created_at: string;
  last_opened_at: string;
  predecessor_session_id?: string;
  unavailable_reason?: string;
}

export interface UserSubmissionReceipt {
  contract_type: "user_submission_receipt";
  schema_version: "evocanvas.pi-runtime.v1";
  status: "accepted" | "duplicate";
  submission_id: string;
  content_hash: string;
  session_id: string;
  entry_id: string;
  binding_status: "ready";
}

export class SessionLockedError extends Error {
  readonly code = "runtime.session_locked";
  constructor(readonly workspaceId: string) {
    super(`Session for workspace ${workspaceId} is locked by another writer`);
    this.name = "SessionLockedError";
  }
}

export class SubmissionConflictError extends Error {
  readonly code = "runtime.submission_conflict";
  constructor(readonly submissionId: string) {
    super(`Submission ${submissionId} was already submitted with a different content hash`);
    this.name = "SubmissionConflictError";
  }
}

export class SessionUnavailableError extends Error {
  readonly code = "runtime.session_unavailable";
  constructor(readonly workspaceId: string, readonly reason?: string) {
    super(`Session for workspace ${workspaceId} is unavailable: ${reason ?? "unknown"}`);
    this.name = "SessionUnavailableError";
  }
}

/**
 * 宿主级独占写锁 (Host-level Exclusive Write Lock)
 * 防止同一 Workspace 发生并发写入或打开第二个可写 Session。
 */
export class HostSessionLockManager {
  private readonly heldLocks = new Set<string>();

  acquire(workspaceId: string): () => void {
    if (this.heldLocks.has(workspaceId)) {
      throw new SessionLockedError(workspaceId);
    }
    this.heldLocks.add(workspaceId);
    let released = false;
    return () => {
      if (!released) {
        released = true;
        this.heldLocks.delete(workspaceId);
      }
    };
  }

  isLocked(workspaceId: string): boolean {
    return this.heldLocks.has(workspaceId);
  }
}

/**
 * 计算规范化 content_hash
 */
export function computeContentHash(message: unknown): string {
  return semanticHash(message);
}

export interface SessionStoreOptions {
  storageDir: string;
}

/**
 * Workspace Primary Session 存储与绑定管理器
 */
export class WorkspaceSessionStore {
  readonly lockManager = new HostSessionLockManager();
  private readonly storageDir: string;
  private readonly sessionsDir: string;
  private readonly bindingsDir: string;
  private readonly submissionsDir: string;
  private readonly repo: SqliteSessionRepo;
  private readonly openSessions = new Map<string, SqliteOpenSession>();

  constructor(options: SessionStoreOptions) {
    this.storageDir = options.storageDir;
    this.sessionsDir = join(this.storageDir, "sessions");
    this.bindingsDir = join(this.storageDir, "bindings");
    this.submissionsDir = join(this.storageDir, "submissions");

    const factory = createNodeSqliteFactory();
    this.repo = new SqliteSessionRepo({
      directory: this.sessionsDir,
      databaseFactory: factory,
    });
  }

  async init(): Promise<void> {
    await mkdir(this.sessionsDir, { recursive: true });
    await mkdir(this.bindingsDir, { recursive: true });
    await mkdir(this.submissionsDir, { recursive: true });
  }

  private bindingPath(workspaceId: string): string {
    return join(this.bindingsDir, `${encodeURIComponent(workspaceId)}.json`);
  }

  private submissionPath(workspaceId: string, submissionId: string): string {
    return join(this.submissionsDir, `${encodeURIComponent(workspaceId)}_${encodeURIComponent(submissionId)}.json`);
  }

  /**
   * 读取 Binding，空 Workspace 返回 null
   */
  async getBinding(workspaceId: string): Promise<WorkspaceSessionBinding | null> {
    try {
      const data = await readFile(this.bindingPath(workspaceId), "utf8");
      return JSON.parse(data) as WorkspaceSessionBinding;
    } catch (error: any) {
      if (error.code === "ENOENT") return null;
      throw error;
    }
  }

  async saveBinding(binding: WorkspaceSessionBinding): Promise<void> {
    await this.atomicJson(this.bindingPath(binding.workspace_id), binding);
  }

  async getSubmissionReceipt(workspaceId: string, submissionId: string): Promise<UserSubmissionReceipt | null> {
    try {
      const data = await readFile(this.submissionPath(workspaceId, submissionId), "utf8");
      return JSON.parse(data) as UserSubmissionReceipt;
    } catch (error: any) {
      if (error.code === "ENOENT") return null;
      throw error;
    }
  }

  async saveSubmissionReceipt(workspaceId: string, receipt: UserSubmissionReceipt): Promise<void> {
    await this.atomicJson(this.submissionPath(workspaceId, receipt.submission_id), receipt);
  }

  private async atomicJson(path: string, value: unknown): Promise<void> {
    const temporary = `${path}.${randomUUID()}.tmp`;
    await writeFile(temporary, JSON.stringify(value), "utf8");
    await rename(temporary, path);
  }

  /**
   * 打开或创建 Primary Session
   * 遵循：空 Workspace 不建 Session，第一条真实用户消息才创建并绑定。
   */
  async submitUserMessage(params: {
    submissionId: string;
    contentHash: string;
    workspaceId: string;
    actorId: string;
    piUserMessage: AgentMessage;
  }): Promise<{ receipt: UserSubmissionReceipt; session: SqliteOpenSession; releaseLock: () => void }> {
    const { submissionId, contentHash, workspaceId, piUserMessage } = params;

    if (computeContentHash(piUserMessage) !== contentHash || piUserMessage.role !== "user") throw new SubmissionConflictError(submissionId);

    // 1. 入口幂等核对
    const existingReceipt = await this.getSubmissionReceipt(workspaceId, submissionId);
    if (existingReceipt) {
      if (existingReceipt.content_hash !== contentHash) {
        throw new SubmissionConflictError(submissionId);
      }
      // 重试取得已有 Session
      const binding = await this.getBinding(workspaceId);
      if (!binding || binding.status !== "ready") {
        throw new SessionUnavailableError(workspaceId, "Binding not ready for duplicated submission");
      }
      const session = await this.getOrOpenSession(binding);
      const original = await session.getEntry(existingReceipt.entry_id, BACKGROUND_CONTEXT);
      if (original?.type !== "message" || (original.message as any).actor_id !== params.actorId) throw new SubmissionConflictError(submissionId);
      const duplicateReceipt: UserSubmissionReceipt = {
        ...existingReceipt,
        status: "duplicate",
      };
      return { receipt: duplicateReceipt, session, releaseLock: () => {} };
    }

    // 2. 宿主级独占锁
    const releaseLock = this.lockManager.acquire(workspaceId);

    try {
      let binding = await this.getBinding(workspaceId);

      if (binding && binding.status === "archived") {
        throw new SessionUnavailableError(workspaceId, "Workspace is archived");
      }
      if (binding && binding.status === "unavailable") {
        throw new SessionUnavailableError(workspaceId, binding.unavailable_reason);
      }

      let session: SqliteOpenSession;
      let entryId: string;
      const nowIso = new Date().toISOString();

      if (!binding) {
        // 第一条真实用户消息到达，创建 Primary Session Binding
        const reservedSessionId = randomUUID();
        binding = {
          contract_type: "workspace_session_binding",
          schema_version: "evocanvas.pi-runtime.v1",
          workspace_id: workspaceId,
          primary_session_id: reservedSessionId,
          main_lane: "main",
          status: "binding",
          pi_session_format_version: "pi-session.v1",
          session_file_ref: `${reservedSessionId}.sqlite`,
          created_at: nowIso,
          last_opened_at: nowIso,
        };
        await this.saveBinding(binding);

        try {
          // 创建单 Session SQLite 文件
          session = await this.repo.create({ id: reservedSessionId }, BACKGROUND_CONTEXT);
          this.openSessions.set(reservedSessionId, session);

          // 创建 main 分支
          const branch = await session.createBranch("main", null, BACKGROUND_CONTEXT);
          // 持久化首条 User Entry
          entryId = await branch.appendMessage({ ...piUserMessage, timestamp: (piUserMessage as any).timestamp ?? Date.now(), actor_id: params.actorId } as AgentMessage, BACKGROUND_CONTEXT);

          // 标记 ready
          binding.status = "ready";
          binding.last_opened_at = new Date().toISOString();
          await this.saveBinding(binding);
        } catch (createError) {
          binding.status = "unavailable";
          binding.unavailable_reason = createError instanceof Error ? createError.message : "create_failed";
          await this.saveBinding(binding);
          throw createError;
        }
      } else {
        // 已有 ready Binding，打开并写入
        session = await this.getOrOpenSession(binding);
        let branch = await session.branch("main", BACKGROUND_CONTEXT);
        if (!branch) {
          branch = await session.createBranch("main", null, BACKGROUND_CONTEXT);
        }
        entryId = await branch.appendMessage({ ...piUserMessage, timestamp: (piUserMessage as any).timestamp ?? Date.now(), actor_id: params.actorId } as AgentMessage, BACKGROUND_CONTEXT);
        binding.last_opened_at = nowIso;
        await this.saveBinding(binding);
      }

      const receipt: UserSubmissionReceipt = {
        contract_type: "user_submission_receipt",
        schema_version: "evocanvas.pi-runtime.v1",
        status: "accepted",
        submission_id: submissionId,
        content_hash: contentHash,
        session_id: binding.primary_session_id,
        entry_id: entryId,
        binding_status: "ready",
      };
      await this.saveSubmissionReceipt(workspaceId, receipt);

      return { receipt, session, releaseLock };
    } catch (error) {
      releaseLock();
      throw error;
    }
  }

  async getOrOpenSession(binding: WorkspaceSessionBinding): Promise<SqliteOpenSession> {
    const existing = this.openSessions.get(binding.primary_session_id);
    if (existing) return existing;

    const metadata: SqliteSessionMetadata = {
      id: binding.primary_session_id,
      path: join(this.sessionsDir, binding.session_file_ref),
      createdAt: Date.parse(binding.created_at),
      storageVersion: 1,
      parentSessionId: binding.predecessor_session_id,
    };
    const session = await this.repo.open(metadata, BACKGROUND_CONTEXT);
    this.openSessions.set(binding.primary_session_id, session);
    return session;
  }

  async closeSession(workspaceId: string): Promise<void> {
    const binding = await this.getBinding(workspaceId);
    if (!binding) return;
    const session = this.openSessions.get(binding.primary_session_id);
    if (session) {
      this.openSessions.delete(binding.primary_session_id);
      await session.close(BACKGROUND_CONTEXT);
    }
  }

  async archiveWorkspace(workspaceId: string): Promise<WorkspaceSessionBinding> {
    const binding = await this.getBinding(workspaceId);
    if (!binding) {
      throw new SessionUnavailableError(workspaceId, "Workspace has no binding to archive");
    }
    await this.closeSession(workspaceId);
    binding.status = "archived";
    await this.saveBinding(binding);
    return binding;
  }

  async replaceSession(workspaceId: string, replacementSessionId?: string): Promise<WorkspaceSessionBinding> {
    const binding = await this.getBinding(workspaceId);
    if (!binding) {
      throw new SessionUnavailableError(workspaceId, "Workspace has no binding to replace");
    }
    await this.closeSession(workspaceId);

    const oldSessionId = binding.primary_session_id;
    const newSessionId = replacementSessionId || randomUUID();
    const nowIso = new Date().toISOString();

    const newSession = await this.repo.create({ id: newSessionId }, BACKGROUND_CONTEXT);
    await newSession.createBranch("main", null, BACKGROUND_CONTEXT);
    this.openSessions.set(newSessionId, newSession);

    const updatedBinding: WorkspaceSessionBinding = {
      ...binding,
      primary_session_id: newSessionId,
      status: "ready",
      session_file_ref: `${newSessionId}.sqlite`,
      predecessor_session_id: oldSessionId,
      created_at: nowIso,
      last_opened_at: nowIso,
    };
    await this.saveBinding(updatedBinding);
    return updatedBinding;
  }

  async deleteWorkspace(workspaceId: string, options?: { retainReason?: string }): Promise<{
    outcome: "deleted" | "partial" | "retention_held";
    residualTargets: string[];
    retentionReason?: string;
  }> {
    if (options?.retainReason) {
      return {
        outcome: "retention_held",
        residualTargets: [workspaceId],
        retentionReason: options.retainReason,
      };
    }

    const residualTargets: string[] = [];
    await this.closeSession(workspaceId);

    const binding = await this.getBinding(workspaceId);
    if (binding) {
      const sessionFile = join(this.sessionsDir, binding.session_file_ref);
      try {
        await unlink(sessionFile);
      } catch (err: any) {
        if (err.code !== "ENOENT") {
          residualTargets.push(`session_file:${sessionFile}`);
        }
      }
      try {
        await unlink(this.bindingPath(workspaceId));
      } catch (err: any) {
        if (err.code !== "ENOENT") {
          residualTargets.push(`binding:${workspaceId}`);
        }
      }
    }

    if (residualTargets.length > 0) {
      return { outcome: "partial", residualTargets };
    }
    return { outcome: "deleted", residualTargets: [] };
  }

  async executeLifecycle(command: V1SessionLifecycleCommand): Promise<V1SessionLifecycleResult> {
    const { workspace_id, action, lifecycle_operation_id } = command;
    if (action === "close") {
      await this.closeSession(workspace_id);
      return {
        contract_type: "session_lifecycle_result",
        schema_version: "evocanvas.pi-runtime.v1",
        lifecycle_operation_id,
        workspace_id,
        action: "close",
        outcome: "closed",
        residual_targets: [],
      };
    }
    if (action === "archive") {
      await this.archiveWorkspace(workspace_id);
      return {
        contract_type: "session_lifecycle_result",
        schema_version: "evocanvas.pi-runtime.v1",
        lifecycle_operation_id,
        workspace_id,
        action: "archive",
        outcome: "archived",
        residual_targets: [],
      };
    }
    if (action === "replace") {
      const binding = await this.replaceSession(workspace_id, command.replacement_session_id);
      return {
        contract_type: "session_lifecycle_result",
        schema_version: "evocanvas.pi-runtime.v1",
        lifecycle_operation_id,
        workspace_id,
        action: "replace",
        outcome: "replaced",
        residual_targets: [],
        replacement_session_id: binding.primary_session_id,
      };
    }
    if (action === "delete") {
      const res = await this.deleteWorkspace(workspace_id);
      return {
        contract_type: "session_lifecycle_result",
        schema_version: "evocanvas.pi-runtime.v1",
        lifecycle_operation_id,
        workspace_id,
        action: "delete",
        outcome: res.outcome,
        residual_targets: res.residualTargets,
        retention_reason: res.retentionReason,
      };
    }
    throw new Error(`Unsupported lifecycle action: ${action}`);
  }

  async close(): Promise<void> {
    for (const session of this.openSessions.values()) {
      try {
        await session.close(BACKGROUND_CONTEXT);
      } catch {
        // ignore
      }
    }
    this.openSessions.clear();
    await this.repo.close(BACKGROUND_CONTEXT);
  }
}

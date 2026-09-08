import { createHash, randomUUID } from "node:crypto";
import { mkdir, readFile, readdir } from "node:fs/promises";
import { DatabaseSync } from "node:sqlite";
import { join } from "node:path";

export interface ToolContext {
  workspace_id: string;
  session_id: string;
  turn_id: string;
  entry_id: string;
  invocation_id: string;
  tool_call_id: string;
  actor_id: string;
  capabilities: string[];
  current_revision_id: string;
  instruction_bundle_version: string;
  active_skill_versions: string[];
}

export interface SemanticOperation {
  operation_id: string;
  operation_type:
    | "create_object"
    | "update_object"
    | "change_status"
    | "supersede_object"
    | "create_relation"
    | "remove_relation"
    | "record_confirmation"
    | "confirm_handoff"
    | "suspend_handoff"
    | "invalidate_handoff";
  payload: Record<string, any>;
}

export interface WorkspaceCommitRequest {
  contract_type: "workspace_commit_request";
  schema_version: "evocanvas.pi-runtime.v1";
  tool_context: ToolContext;
  base_revision_id: string;
  idempotency_key: string;
  request_hash: string;
  operations: SemanticOperation[];
  confirmation_refs: string[];
  change_summary: string;
}

export interface WorkspaceObject {
  id: string;
  object_type: "evidence" | "problem" | "clarification" | "constraint" | "decision" | "handoff";
  title: string;
  type_status: string;
  summary?: string;
  data?: Record<string, any>;
  confirmation_refs?: string[];
  created_at: string;
  updated_at: string;
}

export interface Relation {
  relation_id: string;
  source_id: string;
  target_id: string;
  relation_type: string;
}

export interface ConfirmationRecord {
  confirmation_id: string;
  entry_id: string;
  target_object_ids: string[];
  confirmed_at: string;
  actor_id: string;
  scope_hash?: string;
}

export interface HandoffState {
  status: "draft" | "ready" | "confirmed" | "suspended" | "invalidated" | "superseded";
  confirmed_revision_id?: string;
  updated_at: string;
}

export interface ImmutableRevision {
  revision_id: string;
  workspace_id: string;
  parent_revision_id: string | null;
  commit_id: string;
  created_at: string;
  change_summary: string;
  actor_id: string;
  objects: Record<string, WorkspaceObject>;
  relations: Relation[];
  confirmations: ConfirmationRecord[];
  handoff: HandoffState;
}

export interface CommitResult {
  contract_type: "workspace_commit_result";
  schema_version: "evocanvas.pi-runtime.v1";
  commit_id: string;
  base_revision_id: string;
  new_revision_id: string;
  operations_applied: number;
  dependency_impact: string[];
  handoff_impact: "none" | "draft" | "candidate" | "confirmed" | "suspended" | "invalidated";
  projection_enqueued: boolean;
  request_hash: string;
}

export class CommitError extends Error {
  constructor(readonly code: string, message: string) {
    super(message);
    this.name = "CommitError";
  }
}

export interface WorkspacePointers {
  workspace_id: string;
  current_revision_id: string;
  latest_confirmed_handoff_revision_id: string | null;
  updated_at: string;
}

export class WorkspaceRevisionStore {
  private readonly dir: string;
  private db!: DatabaseSync;

  constructor(options: { storageDir: string }) { this.dir = options.storageDir; }

  async init(): Promise<void> {
    await mkdir(this.dir, { recursive: true });
    this.db = new DatabaseSync(join(this.dir, "workspace.sqlite"));
    this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;
      CREATE TABLE IF NOT EXISTS revisions (workspace TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(workspace,id));
      CREATE TABLE IF NOT EXISTS pointers (workspace TEXT PRIMARY KEY, body TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS commits (workspace TEXT, key TEXT, hash TEXT, body TEXT NOT NULL, PRIMARY KEY(workspace,key));`);
    // 兼容迁移已有 JSON Revision；保留源文件，不覆盖已经迁入的工作区。
    let files: string[];
    try { files = await readdir(join(this.dir, "pointers")); }
    catch (error: any) { if (error.code === "ENOENT") return; throw error; }
    for (const file of files.filter(name => name.endsWith(".json"))) {
      const pointers = JSON.parse(await readFile(join(this.dir, "pointers", file), "utf8")) as WorkspacePointers;
      if (this.db.prepare("SELECT 1 FROM pointers WHERE workspace=?").get(pointers.workspace_id)) continue;
      const revisions: ImmutableRevision[] = [];
      let id: string | null = pointers.current_revision_id;
      while (id) {
        const revision = JSON.parse(await readFile(join(this.dir, "revisions", `${encodeURIComponent(pointers.workspace_id)}_${encodeURIComponent(id)}.json`), "utf8")) as ImmutableRevision;
        revisions.push(revision); id = revision.parent_revision_id;
      }
      this.db.exec("BEGIN IMMEDIATE");
      try {
        for (const revision of revisions) this.saveRevision(revision);
        this.savePointers(pointers);
        this.db.exec("COMMIT");
      } catch (error) { this.db.exec("ROLLBACK"); throw error; }
    }
  }

  close(): void { this.db?.close(); }

  getPointers(workspaceId: string): WorkspacePointers {
    const row = this.db.prepare("SELECT body FROM pointers WHERE workspace=?").get(workspaceId);
    if (row) return JSON.parse(String(row.body));
    // 空工作区读取没有写副作用；首个 commit 在事务内写入 rev_0。
    return { workspace_id: workspaceId, current_revision_id: "rev_0", latest_confirmed_handoff_revision_id: null, updated_at: "1970-01-01T00:00:00.000Z" };
  }

  private savePointers(pointers: WorkspacePointers): void {
    this.db.prepare("INSERT OR REPLACE INTO pointers VALUES (?,?)").run(pointers.workspace_id, JSON.stringify(pointers));
  }

  private createInitialRevision(workspaceId: string): ImmutableRevision {
    const revId = "rev_0";
    return {
      revision_id: revId,
      workspace_id: workspaceId,
      parent_revision_id: null,
      commit_id: "commit_init",
      created_at: new Date().toISOString(),
      change_summary: "Initial workspace revision",
      actor_id: "system",
      objects: {},
      relations: [],
      confirmations: [],
      handoff: {
        status: "draft",
        updated_at: new Date().toISOString(),
      },
    };
  }

  getRevision(workspaceId: string, revisionId: string): ImmutableRevision | null {
    const row = this.db.prepare("SELECT body FROM revisions WHERE workspace=? AND id=?").get(workspaceId, revisionId);
    if (row) return JSON.parse(String(row.body));
    return revisionId === "rev_0" ? this.createInitialRevision(workspaceId) : null;
  }

  private saveRevision(revision: ImmutableRevision): void {
    this.db.prepare("INSERT INTO revisions VALUES (?,?,?)").run(revision.workspace_id, revision.revision_id, JSON.stringify(revision));
  }

  async commit(request: WorkspaceCommitRequest, verifiedConfirmation?: ConfirmationRecord): Promise<CommitResult> {
    // 同步事务覆盖版本核对、不可变 Revision、指针和幂等回执，避免丢失更新。
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const result = this.commitTransaction(request, verifiedConfirmation);
      this.db.exec("COMMIT");
      return result;
    } catch (error) { this.db.exec("ROLLBACK"); throw error; }
  }

  /**
   * 唯一稳定写入提交器 workspace.commit
   * 严格执行 9 步门禁检查：
   * 1. 身份
   * 2. capability
   * 3. Schema
   * 4. base Revision
   * 5. 来源引用
   * 6. 用户确认内容与范围
   * 7. 对象类型化状态转换
   * 8. 依赖传播
   * 9. 幂等键与 request hash
   */
  private commitTransaction(request: WorkspaceCommitRequest, verifiedConfirmation?: ConfirmationRecord): CommitResult {
    const { tool_context, base_revision_id, idempotency_key, request_hash, operations, confirmation_refs, change_summary } = request;
    const workspaceId = tool_context?.workspace_id;

    if (!tool_context?.actor_id || !workspaceId || !Array.isArray(tool_context.capabilities)) {
      throw new CommitError("auth.invalid_identity", "缺少身份或能力上下文");
    }
    if (!tool_context.capabilities.includes("workspace:commit")) {
      throw new CommitError("auth.permission_denied", "缺少 workspace:commit 能力");
    }
    const actualHash = semanticHash({ base_revision_id, operations, confirmation_refs, change_summary, actor_id: tool_context.actor_id });
    const saved = this.db.prepare("SELECT hash,body FROM commits WHERE workspace=? AND key=?").get(workspaceId, idempotency_key);
    if (saved) {
      if (saved.hash !== actualHash) throw new CommitError("workspace.idempotency_conflict", "同一幂等键的内容发生变化");
      return JSON.parse(String(saved.body));
    }

    // 3. Schema 检查
    if (!Array.isArray(operations) || operations.length === 0) {
      throw new CommitError("schema.invalid_operations", "operations must be a non-empty array");
    }
    for (const op of operations) {
      if (!op || !op.operation_id || !op.operation_type || typeof op.payload !== "object") {
        throw new CommitError("schema.invalid_operation", `Invalid operation schema in op ${op?.operation_id}`);
      }
    }

    // 4. Base Revision 检查
    const pointers = this.getPointers(workspaceId);
    if (base_revision_id !== pointers.current_revision_id) {
      throw new CommitError("workspace.stale_revision", `Base revision ${base_revision_id} does not match current ${pointers.current_revision_id}`);
    }

    const baseRevision = this.getRevision(workspaceId, base_revision_id);
    if (!baseRevision) {
      throw new CommitError("workspace.revision_not_found", `Base revision ${base_revision_id} not found`);
    }

    validateOperations(operations);
    // 非来源事实变更必须绑定宿主核验的用户 Entry、当前版本和完整操作内容。
    const needsConfirmation = operations.some(op => op.operation_type !== "create_object" || op.payload.object_type !== "evidence");
    if (needsConfirmation && (!verifiedConfirmation || !confirmation_refs.includes(verifiedConfirmation.confirmation_id)
        || verifiedConfirmation.actor_id !== tool_context.actor_id
        || verifiedConfirmation.scope_hash !== semanticHash({ base_revision_id, operations }))) {
      throw new CommitError("workspace.confirmation_required", "缺少匹配当前版本、内容和范围的用户确认");
    }

    // 7. 对象类型化状态转换 & 8. 依赖传播
    const nextObjects: Record<string, WorkspaceObject> = JSON.parse(JSON.stringify(baseRevision.objects));
    const nextRelations: Relation[] = JSON.parse(JSON.stringify(baseRevision.relations));
    const nextConfirmations: ConfirmationRecord[] = JSON.parse(JSON.stringify(baseRevision.confirmations));
    if (verifiedConfirmation) nextConfirmations.push(verifiedConfirmation);
    let nextHandoff: HandoffState = JSON.parse(JSON.stringify(baseRevision.handoff));

    const dependencyImpact: string[] = [];
    let handoffImpact: "none" | "draft" | "candidate" | "confirmed" | "suspended" | "invalidated" = "none";
    const nowIso = new Date().toISOString();

    for (const op of operations) {
      switch (op.operation_type) {
        case "create_object": {
          const id = op.payload.id || `obj_${randomUUID().slice(0, 8)}`;
          if (nextObjects[id]) throw new CommitError("workspace.object_exists", `对象 ${id} 已存在`);
          nextObjects[id] = {
            id,
            object_type: op.payload.object_type,
            title: op.payload.title,
            type_status: op.payload.type_status || OBJECT_STATUSES[op.payload.object_type][0],
            summary: op.payload.summary,
            data: op.payload.data || {},
            confirmation_refs: [...confirmation_refs],
            created_at: nowIso,
            updated_at: nowIso,
          };
          dependencyImpact.push(id);
          break;
        }
        case "update_object": {
          const id = op.payload.id;
          if (!nextObjects[id]) {
            throw new CommitError("workspace.object_not_found", `Object ${id} not found`);
          }
          if (op.payload.title !== undefined) nextObjects[id].title = op.payload.title;
          if (op.payload.summary !== undefined) nextObjects[id].summary = op.payload.summary;
          if (op.payload.data !== undefined) nextObjects[id].data = { ...nextObjects[id].data, ...op.payload.data };
          nextObjects[id].confirmation_refs = [...confirmation_refs];
          nextObjects[id].updated_at = nowIso;
          dependencyImpact.push(id);
          break;
        }
        case "change_status": {
          const id = op.payload.id;
          if (!nextObjects[id]) {
            throw new CommitError("workspace.object_not_found", `Object ${id} not found`);
          }
          if (!OBJECT_STATUSES[nextObjects[id].object_type]?.includes(op.payload.type_status)) throw new CommitError("schema.invalid_status", "非法类型化状态");
          nextObjects[id].type_status = op.payload.type_status;
          nextObjects[id].confirmation_refs = [...confirmation_refs];
          nextObjects[id].updated_at = nowIso;
          dependencyImpact.push(id);
          break;
        }
        case "supersede_object": {
          const id = op.payload.id;
          if (!nextObjects[id] || !OBJECT_STATUSES[nextObjects[id].object_type].includes("superseded")) throw new CommitError("schema.invalid_status", "该对象不支持替代状态");
          if (nextObjects[id]) {
            nextObjects[id].type_status = "superseded";
            nextObjects[id].updated_at = nowIso;
            dependencyImpact.push(id);
          }
          break;
        }
        case "create_relation": {
          if (!nextObjects[op.payload.source_id] || !nextObjects[op.payload.target_id]) throw new CommitError("workspace.object_not_found", "关系端点不存在");
          const relId = op.payload.relation_id || `rel_${randomUUID().slice(0, 8)}`;
          if (nextRelations.some(rel => rel.relation_id === relId)) throw new CommitError("workspace.relation_exists", "关系 ID 已存在");
          nextRelations.push({
            relation_id: relId,
            source_id: op.payload.source_id,
            target_id: op.payload.target_id,
            relation_type: op.payload.relation_type,
          });
          break;
        }
        case "remove_relation": {
          const relId = op.payload.relation_id;
          const idx = nextRelations.findIndex((r) => r.relation_id === relId);
          if (idx === -1) throw new CommitError("workspace.relation_not_found", "关系不存在");
          nextRelations.splice(idx, 1);
          break;
        }
        case "confirm_handoff": {
          if (op.payload.target_revision_id !== base_revision_id || semanticHash(op.payload.scope_object_ids) !== semanticHash(Object.keys(baseRevision.objects).sort()) || typeof op.payload.disclosed_summary !== "string") throw new CommitError("handoff.scope_incomplete", "交接未完整展示当前范围");
          nextHandoff = {
            status: "confirmed",
            confirmed_revision_id: "", // 将在原子创建后回填新 revision id
            updated_at: nowIso,
          };
          handoffImpact = "confirmed";
          break;
        }
        case "suspend_handoff": {
          nextHandoff = {
            status: "suspended",
            updated_at: nowIso,
          };
          handoffImpact = "suspended";
          break;
        }
        case "invalidate_handoff": {
          nextHandoff = {
            status: "invalidated",
            updated_at: nowIso,
          };
          handoffImpact = "invalidated";
          break;
        }
        default: throw new CommitError("schema.invalid_operation", "不支持的操作");
      }
    }

    if (baseRevision.handoff.status === "confirmed" && handoffImpact === "none" && dependencyImpact.length) {
      const changedStable = dependencyImpact.some(id => baseRevision.objects[id] && ["constraint", "decision", "evidence"].includes(baseRevision.objects[id].object_type));
      handoffImpact = changedStable ? "invalidated" : "suspended";
      nextHandoff = { status: handoffImpact, updated_at: nowIso };
    }

    // 原子生成新 Revision
    const newRevId = `rev_${Date.now()}_${randomUUID().slice(0, 6)}`;
    const commitId = `commit_${randomUUID().slice(0, 8)}`;

    if (handoffImpact === "confirmed") {
      nextHandoff.confirmed_revision_id = newRevId;
    }

    const newRevision: ImmutableRevision = {
      revision_id: newRevId,
      workspace_id: workspaceId,
      parent_revision_id: base_revision_id,
      commit_id: commitId,
      created_at: nowIso,
      change_summary,
      actor_id: tool_context.actor_id,
      objects: nextObjects,
      relations: nextRelations,
      confirmations: nextConfirmations,
      handoff: nextHandoff,
    };

    if (base_revision_id === "rev_0" && !this.db.prepare("SELECT 1 FROM revisions WHERE workspace=? AND id='rev_0'").get(workspaceId)) this.saveRevision(baseRevision);
    this.saveRevision(newRevision);

    // 事务内推进版本指针
    pointers.current_revision_id = newRevId;
    pointers.updated_at = nowIso;
    if (handoffImpact === "confirmed") {
      pointers.latest_confirmed_handoff_revision_id = newRevId;
    }
    this.savePointers(pointers);

    const result: CommitResult = {
      contract_type: "workspace_commit_result",
      schema_version: "evocanvas.pi-runtime.v1",
      commit_id: commitId,
      base_revision_id,
      new_revision_id: newRevId,
      operations_applied: operations.length,
      dependency_impact: dependencyImpact,
      handoff_impact: handoffImpact,
      projection_enqueued: true,
      request_hash,
    };

    this.db.prepare("INSERT INTO commits VALUES (?,?,?,?)").run(workspaceId, idempotency_key, actualHash, JSON.stringify(result));
    return result;
  }
}

/** 哈希覆盖实际语义内容，不信任调用方自行声明的 hash。 */
export function semanticHash(value: unknown): string {
  const normalize = (item: any): any => Array.isArray(item) ? item.map(normalize)
    : item && typeof item === "object" ? Object.fromEntries(Object.keys(item).sort().map(key => [key, normalize(item[key])])) : item;
  return `sha256:${createHash("sha256").update(JSON.stringify(normalize(value))).digest("hex")}`;
}

export const OBJECT_STATUSES: Record<string, string[]> = {
  evidence: ["collected", "cited", "archived"],
  problem: ["initial", "converging", "converged", "archived"],
  clarification: ["open", "pending_confirmation", "clarified", "blocked", "closed"],
  constraint: ["draft", "pending_confirmation", "effective", "superseded", "archived"],
  decision: ["pending_decision", "pending_confirmation", "decided", "archived"],
  handoff: ["draft", "ready", "confirmed", "suspended", "invalidated", "superseded"],
};

export function validateOperations(operations: SemanticOperation[]): void {
  if (!Array.isArray(operations) || !operations.length) throw new CommitError("schema.invalid_operations", "操作不能为空");
  const ids = new Set<string>();
  for (const op of operations) {
    if (!op || typeof op.operation_id !== "string" || ids.has(op.operation_id) || !op.payload || typeof op.payload !== "object" || Array.isArray(op.payload)) throw new CommitError("schema.invalid_operation", "非法或重复的操作");
    ids.add(op.operation_id);
    const p = op.payload;
    if (p.id !== undefined && (typeof p.id !== "string" || !p.id || ["__proto__","constructor","prototype"].includes(p.id))) throw new CommitError("schema.invalid_object", "非法对象 ID");
    if (p.summary !== undefined && typeof p.summary !== "string") throw new CommitError("schema.invalid_object", "摘要必须是文本");
    if (p.title !== undefined && (typeof p.title !== "string" || !p.title.trim())) throw new CommitError("schema.invalid_object", "标题必须是非空文本");
    if (p.data !== undefined && (!p.data || typeof p.data !== "object" || Array.isArray(p.data))) throw new CommitError("schema.invalid_object", "data 必须是对象");
    if (p.data?.source_refs !== undefined && (!Array.isArray(p.data.source_refs) || p.data.source_refs.some((ref: unknown) => typeof ref !== "string"))) throw new CommitError("schema.invalid_object", "来源引用必须是字符串数组");
    if (op.operation_type === "create_object") {
      if (!OBJECT_STATUSES[p.object_type] || p.object_type === "handoff" || typeof p.title !== "string" || !p.title.trim()) throw new CommitError("schema.invalid_object", "对象类型或标题无效");
      if (p.type_status && !OBJECT_STATUSES[p.object_type].includes(p.type_status)) throw new CommitError("schema.invalid_status", "非法类型化状态");
    } else if (["update_object", "change_status", "supersede_object"].includes(op.operation_type)) {
      if (typeof p.id !== "string" || !p.id) throw new CommitError("schema.invalid_object", "缺少目标对象");
    } else if (op.operation_type === "create_relation") {
      if (!["derived_from","clarifies","supports","blocks","conflicts_with","produces","replaces"].includes(p.relation_type) || ![p.source_id,p.target_id,p.relation_type].every(value => typeof value === "string" && value)) throw new CommitError("schema.invalid_relation", "关系引用不完整");
    } else if (op.operation_type === "remove_relation") {
      if (typeof p.relation_id !== "string" || !p.relation_id) throw new CommitError("schema.invalid_relation", "缺少关系 ID");
    } else if (![ "confirm_handoff", "suspend_handoff", "invalidate_handoff"].includes(op.operation_type)) {
      throw new CommitError("schema.invalid_operation", "不支持的语义操作");
    }
  }
}

import type { AgentMessage } from "@earendil-works/pi-agent-core";
import type { WorkspaceRevisionStore, ImmutableRevision } from "./workspace-revision-store.js";

export interface WorkspaceContextSnapshot {
  workspace_id: string;
  current_revision_id: string;
  write_capability: boolean;
  problems_summary: string[];
  clarifications_summary: string[];
  constraints_summary: string[];
  decisions_summary: string[];
  handoff_status: string;
  active_todos: string[];
}

export function buildContextSnapshot(
  workspaceId: string,
  revision: ImmutableRevision | null,
  writeCapability = true,
): WorkspaceContextSnapshot {
  if (!revision) {
    return {
      workspace_id: workspaceId,
      current_revision_id: "none",
      write_capability: false,
      problems_summary: [],
      clarifications_summary: [],
      constraints_summary: [],
      decisions_summary: [],
      handoff_status: "unavailable",
      active_todos: [],
    };
  }

  const problems: string[] = [];
  const clarifications: string[] = [];
  const constraints: string[] = [];
  const decisions: string[] = [];
  const activeTodos: string[] = [];

  for (const obj of Object.values(revision.objects)) {
    if (obj.object_type === "problem") {
      problems.push(`[${obj.id}] ${obj.title} (${obj.type_status})`);
      if (obj.type_status !== "resolved") activeTodos.push(`解决焦点问题: ${obj.title}`);
    } else if (obj.object_type === "clarification") {
      clarifications.push(`[${obj.id}] ${obj.title} (${obj.type_status})`);
      if (obj.type_status !== "answered") activeTodos.push(`澄清事项: ${obj.title}`);
    } else if (obj.object_type === "constraint") {
      constraints.push(`[${obj.id}] ${obj.title} (${obj.type_status})`);
    } else if (obj.object_type === "decision") {
      decisions.push(`[${obj.id}] ${obj.title} (${obj.type_status})`);
      if (obj.type_status === "pending") activeTodos.push(`待决策事项: ${obj.title}`);
    }
  }

  return {
    workspace_id: workspaceId,
    current_revision_id: revision.revision_id,
    write_capability: writeCapability,
    problems_summary: problems,
    clarifications_summary: clarifications,
    constraints_summary: constraints,
    decisions_summary: decisions,
    handoff_status: revision.handoff.status,
    active_todos: activeTodos,
  };
}

/**
 * Pi 原生 transformContext 工厂：
 * 1. 每次模型调用前读取 current Revision
 * 2. 临时生成 Workspace Context Snapshot 并在运行时注入系统提示/模型上下文
 * 3. 原始 Pi messages 保持完整不被修改
 * 4. 快照不写回 Session SQLite
 * 5. 不复制完整来源正文
 * 6. 不建立独立 Context ID
 * 7. 若 Revision 不可用，保留消息但关闭稳定写入权限 (write_capability = false)
 */
export function createWorkspaceTransformContext(
  workspaceId: string,
  revisionStore: WorkspaceRevisionStore,
) {
  return async function transformContext(
    messages: AgentMessage[],
    _signal?: AbortSignal,
  ): Promise<AgentMessage[]> {
    let revision: ImmutableRevision | null = null;
    let writeCapability = true;

    try {
      const pointers = await revisionStore.getPointers(workspaceId);
      revision = await revisionStore.getRevision(workspaceId, pointers.current_revision_id);
    } catch {
      writeCapability = false;
    }

    const snapshot = buildContextSnapshot(workspaceId, revision, writeCapability);

    const snapshotContextBlock = [
      "--- [EvoCanvas Workspace Context Snapshot] ---",
      `Workspace: ${snapshot.workspace_id}`,
      `Current Revision: ${snapshot.current_revision_id}`,
      `Write Capability: ${snapshot.write_capability ? "enabled" : "DISABLED (read-only mode)"}`,
      `Handoff Status: ${snapshot.handoff_status}`,
      `Problems: ${snapshot.problems_summary.join("; ") || "none"}`,
      `Clarifications: ${snapshot.clarifications_summary.join("; ") || "none"}`,
      `Constraints: ${snapshot.constraints_summary.join("; ") || "none"}`,
      `Decisions: ${snapshot.decisions_summary.join("; ") || "none"}`,
      `Active Todos: ${snapshot.active_todos.join("; ") || "none"}`,
      "----------------------------------------------",
    ].join("\n");

    // 不修改原始 messages，仅在最前方附加临时上下文系统提示消息（包装为 user 上下文块）
    const contextMessage: AgentMessage = {
      role: "user",
      content: snapshotContextBlock,
      timestamp: Date.now(),
    };

    return [contextMessage, ...messages];
  };
}

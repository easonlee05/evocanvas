import { createHash } from "node:crypto";
import type { ToolContext } from "./workspace-revision-store.js";

export type SideEffectClass = "none" | "workspace" | "external";
export type ReplayPolicy = "safe" | "never";
export type ToolResultStatus = "success" | "failed" | "unknown";

export interface ToolDefinition {
  name: string;
  version: string;
  sideEffectClass: SideEffectClass;
  replay: ReplayPolicy;
  requiresExternalAuth?: boolean;
}

export interface ToolExecutionRecord {
  contract_type: "tool_execution_record";
  schema_version: "evocanvas.pi-runtime.v1";
  tool_name: string;
  tool_version: string;
  tool_context: ToolContext;
  side_effect_class: SideEffectClass;
  replay: ReplayPolicy;
  result_status: ToolResultStatus;
  request_hash: string;
  idempotency_key?: string;
  effect_id?: string;
  error_code?: string;
  started_at: string;
  finished_at: string;
}

export class ToolRecoveryError extends Error {
  constructor(readonly code: string, message: string) {
    super(message);
    this.name = "ToolRecoveryError";
  }
}

/**
 * 工具恢复决策器
 */
export class ToolRecoveryManager {
  private readonly executionRecords = new Map<string, ToolExecutionRecord>();

  recordExecution(record: ToolExecutionRecord): void {
    if (record.idempotency_key) {
      this.executionRecords.set(record.idempotency_key, record);
    }
  }

  getExecution(idempotencyKey: string): ToolExecutionRecord | undefined {
    return this.executionRecords.get(idempotencyKey);
  }

  /**
   * 恢复前评估是否允许执行或重试：
   * 1. 结果 unknown 不能自动授予重试许可
   * 2. replay=never 且结果未知时禁止自动重放
   * 3. replay=safe 工具恢复前必须查询原结果和 request hash
   * 4. 外部副作用必须有独立动作级授权
   */
  evaluateReplay(
    tool: ToolDefinition,
    idempotencyKey: string | undefined,
    requestHash: string,
    hasExternalActionAuth = false,
  ): { allowExecution: boolean; cachedRecord?: ToolExecutionRecord; reason?: string } {
    if (tool.sideEffectClass === "external" && tool.requiresExternalAuth && !hasExternalActionAuth) {
      throw new ToolRecoveryError(
        "external.action_unauthorized",
        `Tool ${tool.name} requires explicit action-level authorization; workspace/handoff confirmation is insufficient`,
      );
    }

    if (!idempotencyKey) {
      if (tool.replay === "never") {
        return { allowExecution: true };
      }
      return { allowExecution: true };
    }

    const previous = this.getExecution(idempotencyKey);
    if (!previous) {
      return { allowExecution: true };
    }

    // 核对 request_hash
    if (previous.request_hash !== requestHash) {
      throw new ToolRecoveryError(
        "tool.request_hash_mismatch",
        `Idempotency key ${idempotencyKey} was already executed with a different request hash`,
      );
    }

    // 结果已经成功
    if (previous.result_status === "success") {
      return { allowExecution: false, cachedRecord: previous, reason: "already_succeeded" };
    }

    // 结果未知 (unknown)
    if (previous.result_status === "unknown") {
      if (tool.replay === "never") {
        throw new ToolRecoveryError(
          "tool.replay_forbidden",
          `Tool ${tool.name} has replay=never and result_status=unknown; automatic replay is strictly forbidden`,
        );
      }
      // replay=safe 也不能无脑自动重试，必须显式检查
      throw new ToolRecoveryError(
        "tool.unknown_result_verification_required",
        `Tool ${tool.name} has result_status=unknown; query original effect before retrying`,
      );
    }

    // 结果失败 (failed)
    if (tool.replay === "never") {
      throw new ToolRecoveryError(
        "tool.replay_never",
        `Tool ${tool.name} has replay=never; failed execution cannot be replayed automatically`,
      );
    }

    return { allowExecution: true, reason: "safe_retry_allowed" };
  }
}

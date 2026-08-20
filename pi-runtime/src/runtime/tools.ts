import { randomUUID } from "node:crypto";
import type {
  ConvergenceProposal,
  EventEnvelope,
  RunKind,
  RunRequest,
  RuntimeErrorEnvelope,
  ToolCallRequest,
  ToolCallResult,
} from "../contracts.js";

export interface RunEventSink {
  (type: EventEnvelope["type"], payload: Record<string, unknown>): Promise<void> | void;
}

export interface ToolHandlerContext {
  request: ToolCallRequest;
  signal: AbortSignal;
}

export interface ToolHandlerResult {
  summary: string;
  data?: unknown;
  data_ref?: string | null;
  source_refs?: string[];
  artifacts?: string[];
}

export interface ToolHandler {
  name: string;
  version: string;
  allowed_run_kinds: RunKind[];
  side_effect: "none" | "read";
  timeout_ms: number;
  invoke(context: ToolHandlerContext): Promise<ToolHandlerResult>;
}

export class ToolPolicyError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly category?: RuntimeErrorEnvelope["category"],
    readonly retryable?: boolean,
  ) {
    super(message);
    this.name = "ToolPolicyError";
  }
}

function now(): string {
  return new Date().toISOString();
}

function safeSummary(value: unknown): string {
  if (typeof value === "string") return value.slice(0, 20000);
  try {
    return (JSON.stringify(value) ?? String(value)).slice(0, 20000);
  } catch {
    return "[unserializable]";
  }
}

function errorEnvelope(error: unknown, runId: string): RuntimeErrorEnvelope {
  if (error instanceof ToolPolicyError) {
    const category = error.category ?? (
      error.code === "permission_denied"
        ? "permission_denied"
        : error.code === "invalid_request" || error.code === "schema_invalid" ? "input_error" : "temporary_error"
    );
    return {
      schema_version: "pi-runtime.error.v1",
      error_code: error.code,
      category,
      message: error.message,
      retryable: error.retryable ?? (error.code === "tool_timeout" || error.code === "tool_unavailable"),
      run_id: runId,
      trace_id: null,
      details: {},
    };
  }
  return {
    schema_version: "pi-runtime.error.v1",
    error_code: "tool_failed",
    category: "temporary_error",
    message: error instanceof Error ? error.message : "tool failed",
    retryable: false,
    run_id: runId,
    trace_id: null,
    details: {},
  };
}

function validateProposal(value: unknown, request: ToolCallRequest): ConvergenceProposal {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new ToolPolicyError("invalid_request", "proposal must be an object");
  }
  const proposal = value as Partial<ConvergenceProposal>;
  if (proposal.proposal_schema_version !== "evocanvas.convergence-proposal.v1") {
    throw new ToolPolicyError("invalid_request", "proposal schema version is invalid");
  }
  if (proposal.run_id !== request.run_id) {
    throw new ToolPolicyError("invalid_request", "proposal run_id does not match the active run");
  }
  if (proposal.package_id !== (request.package_id ?? null)) {
    throw new ToolPolicyError("invalid_request", "proposal package_id does not match the active run");
  }
  if (!Number.isInteger(proposal.from_message_seq) || !Number.isInteger(proposal.through_message_seq)) {
    throw new ToolPolicyError("invalid_request", "proposal message range must be integer values");
  }
  if ((proposal.through_message_seq as number) < (proposal.from_message_seq as number)) {
    throw new ToolPolicyError("invalid_request", "proposal message range is reversed");
  }
  const range = request.message_range;
  if (range && (
    proposal.from_message_seq !== range.from_seq
    || proposal.through_message_seq !== range.through_seq
  )) {
    throw new ToolPolicyError("invalid_request", "proposal message range does not match the active run");
  }
  if (!Number.isInteger(proposal.base_state_version) || (proposal.base_state_version as number) < 0) {
    throw new ToolPolicyError("invalid_request", "proposal base_state_version is invalid");
  }
  if (!Number.isInteger(proposal.base_package_version) || (proposal.base_package_version as number) < 0) {
    throw new ToolPolicyError("invalid_request", "proposal base_package_version is invalid");
  }
  if (!Array.isArray(proposal.operations) || proposal.operations.length > 128) {
    throw new ToolPolicyError("invalid_request", "proposal operations must be an array of at most 128 items");
  }
  const operationIds = new Set<string>();
  for (const operation of proposal.operations) {
    if (!operation || typeof operation !== "object") {
      throw new ToolPolicyError("invalid_request", "proposal operation must be an object");
    }
    const item = operation as unknown as Record<string, unknown>;
    for (const field of ["operation_id", "operation_type", "risk_level"]) {
      if (typeof item[field] !== "string" || !String(item[field]).trim()) {
        throw new ToolPolicyError("invalid_request", `proposal operation ${field} is required`);
      }
    }
    if (operationIds.has(String(item.operation_id))) {
      throw new ToolPolicyError("invalid_request", "proposal operation_id values must be unique");
    }
    operationIds.add(String(item.operation_id));
    if (!item.payload || typeof item.payload !== "object" || Array.isArray(item.payload)) {
      throw new ToolPolicyError("invalid_request", "proposal operation payload must be an object");
    }
    if (!Array.isArray(item.source_refs) || !Array.isArray(item.confirmation_refs) || !Array.isArray(item.unresolved_refs)) {
      throw new ToolPolicyError("invalid_request", "proposal operation references must be arrays");
    }
    if (!["low", "medium", "high"].includes(String(item.risk_level))) {
      throw new ToolPolicyError("invalid_request", "proposal operation risk_level is invalid");
    }
  }
  return proposal as ConvergenceProposal;
}

class ProposalCaptureHandler implements ToolHandler {
  readonly name = "submit_convergence_proposal";
  readonly version = "v1";
  readonly allowed_run_kinds: RunKind[] = ["convergence"];
  readonly side_effect = "none" as const;
  readonly timeout_ms = 1000;
  private captured: ConvergenceProposal | null = null;

  async invoke(context: ToolHandlerContext): Promise<ToolHandlerResult> {
    if (this.captured !== null) {
      throw new ToolPolicyError("invalid_request", "only one convergence proposal may be captured per run");
    }
    const proposal = validateProposal(context.request.arguments.proposal, context.request);
    this.captured = proposal;
    return {
      summary: `captured convergence proposal ${proposal.proposal_id}`,
      data: proposal,
      source_refs: proposal.operations.flatMap((operation) => operation.source_refs),
    };
  }

  getProposal(): ConvergenceProposal | null {
    return this.captured;
  }
}

class PythonToolGatewayHandler implements ToolHandler {
  readonly side_effect = "read" as const;
  readonly allowed_run_kinds: RunKind[] = ["chat", "convergence"];
  readonly timeout_ms = 15000;

  constructor(
    readonly name: string,
    readonly version: string,
    private readonly gatewayUrl: string,
    private readonly token: string,
  ) {}

  async invoke(context: ToolHandlerContext): Promise<ToolHandlerResult> {
    const controller = new AbortController();
    const abort = () => controller.abort(context.signal.reason);
    context.signal.addEventListener("abort", abort, { once: true });
    try {
      const timeout = setTimeout(() => controller.abort(new Error("tool timeout")), this.timeout_ms);
      const response = await fetch(this.gatewayUrl, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "accept": "application/json",
          "authorization": `Run ${this.token}`,
          ...(context.request.tenant_id ? { "x-tenant-id": context.request.tenant_id } : {}),
        },
        body: JSON.stringify(context.request),
        signal: controller.signal,
      }).finally(() => clearTimeout(timeout));
      const payload = await response.json() as Partial<ToolCallResult>;
      if (payload.tool_call_id !== undefined && payload.tool_call_id !== context.request.tool_call_id) {
        throw new ToolPolicyError("invalid_request", "Tool Gateway returned a different tool_call_id");
      }
      if (!response.ok || payload.status !== "succeeded") {
        const errorPayload = payload.error && typeof payload.error === "object"
          ? payload.error as unknown as Record<string, unknown>
          : {};
        const errorCode = String(errorPayload.error_code ?? "");
        const policyCode = response.status === 401 || response.status === 403
          ? "permission_denied"
          : errorCode || "tool_unavailable";
        const category = errorPayload.category;
        const policyCategory = response.status === 401 || response.status === 403
          ? "permission_denied"
          : category === "temporary_error"
            || category === "input_error"
            || category === "permission_denied"
            || category === "not_ready"
            || category === "stale"
            || category === "governance_rejected"
            || category === "commit_unknown"
            || category === "projection_failed"
            || category === "engine_unavailable"
            ? category
            : undefined;
        throw new ToolPolicyError(
          policyCode,
          String(errorPayload.message ?? `Tool Gateway returned HTTP ${response.status}`),
          policyCategory,
          typeof errorPayload.retryable === "boolean" ? errorPayload.retryable : undefined,
        );
      }
      return {
        summary: String(payload.summary ?? "tool completed"),
        data: payload.data,
        data_ref: payload.data_ref,
        source_refs: Array.isArray(payload.source_refs) ? payload.source_refs.map(String) : [],
        artifacts: Array.isArray(payload.artifacts) ? payload.artifacts.map(String) : [],
      };
    } catch (error) {
      if (controller.signal.aborted && !context.signal.aborted) {
        throw new ToolPolicyError("tool_timeout", `tool ${this.name} timed out`);
      }
      throw error;
    } finally {
      context.signal.removeEventListener("abort", abort);
    }
  }
}

export interface RunToolRuntimeOptions {
  handlers?: ToolHandler[];
}

export class RunToolRuntime {
  readonly proposalCapture: ProposalCaptureHandler | null;
  private readonly handlers: Map<string, ToolHandler>;
  private calls = 0;

  constructor(readonly request: RunRequest, options: RunToolRuntimeOptions = {}) {
    this.proposalCapture = request.run_kind === "convergence" ? new ProposalCaptureHandler() : null;
    this.handlers = new Map((options.handlers ?? []).map((handler) => [handler.name, handler]));
    if (this.proposalCapture) this.handlers.set(this.proposalCapture.name, this.proposalCapture);
  }

  async call(
    toolName: string,
    argumentsValue: Record<string, unknown>,
    emit: RunEventSink,
    signal: AbortSignal,
  ): Promise<ToolCallResult> {
    const toolCallId = `tool_${randomUUID()}`;
    const handler = this.handlers.get(toolName);
    const completedAt = () => now();
    const baseRequest: ToolCallRequest = {
      schema_version: "pi-runtime.tool-call.v1",
      tool_call_id: toolCallId,
      tool_name: toolName,
      tool_version: handler?.version ?? "unknown",
      run_id: this.request.run_id,
      run_kind: this.request.run_kind,
      workspace_id: this.request.workspace_id,
      conversation_id: this.request.conversation_id,
      package_id: this.request.package_id ?? null,
      tenant_id: this.request.tool_profile.tenant_id,
      message_range: {
        from_seq: this.request.from_message_seq,
        through_seq: this.request.through_message_seq,
      },
      arguments: argumentsValue,
      attempt: 1,
      trace_context: this.request.trace_context,
    };
    const deny = async (error: ToolPolicyError): Promise<ToolCallResult> => {
      const errorData = errorEnvelope(error, this.request.run_id);
      await emit("tool.requested", {
        tool_call_id: toolCallId,
        tool_name: toolName,
        tool_version: baseRequest.tool_version,
        status: "denied",
      });
      await emit("tool.completed", {
        tool_call_id: toolCallId,
        tool_name: toolName,
        status: "denied",
        error_code: errorData.error_code,
      });
      return {
        schema_version: "pi-runtime.tool-result.v1",
        tool_call_id: toolCallId,
        status: "denied",
        summary: error.message,
        source_refs: [],
        artifacts: [],
        error: errorData,
        completed_at: completedAt(),
      };
    };

    if (!this.request.tool_profile.allowed_tools.includes(toolName)) {
      return deny(new ToolPolicyError("permission_denied", `tool ${toolName} is not allowed for this run`));
    }
    if (!handler) {
      return deny(new ToolPolicyError("tool_unavailable", `tool ${toolName} is not registered`));
    }
    if (!handler.allowed_run_kinds.includes(this.request.run_kind)) {
      return deny(new ToolPolicyError("permission_denied", `tool ${toolName} is not allowed for ${this.request.run_kind}`));
    }
    if (handler.side_effect !== "none" && handler.side_effect !== "read") {
      return deny(new ToolPolicyError("permission_denied", `tool ${toolName} has a forbidden side effect`));
    }
    if (this.calls >= this.request.tool_profile.max_calls) {
      return deny(new ToolPolicyError("permission_denied", "tool call budget exhausted"));
    }
    if (signal.aborted) {
      return deny(new ToolPolicyError("permission_denied", "run is cancelled"));
    }
    this.calls += 1;
    await emit("tool.requested", {
      tool_call_id: toolCallId,
      tool_name: toolName,
      tool_version: handler.version,
      attempt: 1,
      arguments_summary: safeSummary(argumentsValue),
    });
    try {
      const handlerController = new AbortController();
      const abortHandler = () => handlerController.abort(signal.reason);
      signal.addEventListener("abort", abortHandler, { once: true });
      let timeout: ReturnType<typeof setTimeout> | undefined;
      let result: ToolHandlerResult;
      try {
        result = await Promise.race([
          handler.invoke({ request: baseRequest, signal: handlerController.signal }),
          new Promise<never>((_, reject) => {
            timeout = setTimeout(() => {
              handlerController.abort(new Error(`tool ${handler.name} timed out`));
              reject(new ToolPolicyError("tool_timeout", `tool ${handler.name} timed out`));
            }, handler.timeout_ms);
          }),
        ]);
      } finally {
        if (timeout !== undefined) clearTimeout(timeout);
        signal.removeEventListener("abort", abortHandler);
      }
      const resultPayload = {
        summary: result.summary,
        data: result.data,
        data_ref: result.data_ref ?? null,
        source_refs: result.source_refs ?? [],
        artifacts: result.artifacts ?? [],
      };
      let encoded: string;
      try {
        encoded = JSON.stringify(resultPayload);
      } catch {
        throw new ToolPolicyError("invalid_request", "tool result is not JSON serializable");
      }
      if (Buffer.byteLength(encoded, "utf8") > this.request.tool_profile.max_result_bytes) {
        throw new ToolPolicyError("invalid_request", "tool result exceeds the run result size limit");
      }
      await emit("tool.completed", {
        tool_call_id: toolCallId,
        tool_name: toolName,
        status: "succeeded",
        source_refs: result.source_refs ?? [],
        summary: safeSummary(result.summary),
      });
      return {
        schema_version: "pi-runtime.tool-result.v1",
        tool_call_id: toolCallId,
        status: "succeeded",
        summary: result.summary,
        data: result.data,
        data_ref: result.data_ref ?? null,
        source_refs: result.source_refs ?? [],
        artifacts: result.artifacts ?? [],
        error: null,
        completed_at: completedAt(),
      };
    } catch (error) {
      const wrapped = error instanceof ToolPolicyError ? error : new ToolPolicyError("tool_unavailable", error instanceof Error ? error.message : "tool failed");
      const errorData = errorEnvelope(wrapped, this.request.run_id);
      await emit("tool.completed", {
        tool_call_id: toolCallId,
        tool_name: toolName,
        status: wrapped.code === "tool_timeout" ? "timed_out" : "failed",
        error_code: errorData.error_code,
      });
      return {
        schema_version: "pi-runtime.tool-result.v1",
        tool_call_id: toolCallId,
        status: wrapped.code === "tool_timeout" ? "timed_out" : "failed",
        summary: wrapped.message,
        source_refs: [],
        artifacts: [],
        error: errorData,
        completed_at: completedAt(),
      };
    }
  }
}

export function createRunToolRuntime(request: RunRequest): RunToolRuntime {
  const handlers: ToolHandler[] = [];
  const gatewayUrl = request.tool_profile.gateway_url;
  const token = request.tool_profile.run_scoped_token;
  if (gatewayUrl && token) {
    for (const name of request.tool_profile.allowed_tools) {
      if (name === "submit_convergence_proposal") continue;
      handlers.push(new PythonToolGatewayHandler(name, "v1", gatewayUrl, token));
    }
  }
  return new RunToolRuntime(request, { handlers });
}

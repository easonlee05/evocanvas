import type { RunKind, RunRequest, RuntimeErrorEnvelope } from "./contracts.js";

export class RuntimeContractError extends Error {
  readonly envelope: RuntimeErrorEnvelope;
  readonly httpStatus: number;

  constructor(
    errorCode: string,
    message: string,
    httpStatus = 400,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "RuntimeContractError";
    this.httpStatus = httpStatus;
    this.envelope = {
      schema_version: "pi-runtime.error.v1",
      error_code: errorCode,
      category: httpStatus === 401 || httpStatus === 403 ? "permission_denied" : "input_error",
      message,
      retryable: false,
      details,
    };
  }
}

const RUN_KINDS = new Set<RunKind>(["chat", "judgement", "convergence"]);

function asRecord(value: unknown, field: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new RuntimeContractError("invalid_request", `${field} must be an object`);
  }
  return value as Record<string, unknown>;
}

function requireString(record: Record<string, unknown>, field: string): string {
  const value = record[field];
  if (typeof value !== "string" || value.trim() === "") {
    throw new RuntimeContractError("invalid_request", `${field} must be a non-empty string`);
  }
  return value;
}

function requireInteger(record: Record<string, unknown>, field: string, minimum = 0): number {
  const value = record[field];
  if (!Number.isInteger(value) || (value as number) < minimum) {
    throw new RuntimeContractError("invalid_request", `${field} must be an integer >= ${minimum}`);
  }
  return value as number;
}

function requireObject(record: Record<string, unknown>, field: string): Record<string, unknown> {
  return asRecord(record[field], field);
}

function validateManifest(manifest: Record<string, unknown>): void {
  requireString(manifest, "context_manifest_id");
  requireString(manifest, "request_kind");
  requireObject(manifest, "package_ref");
  requireObject(manifest, "structured_package_input_ref");
  requireObject(manifest, "message_scope");
  requireString(manifest, "assembly_policy_version");
  requireString(manifest, "budget_ref");
  requireObject(manifest, "transport_ref");
}

export function validateRunRequest(input: unknown, expectedKind: RunKind): RunRequest {
  const record = asRecord(input, "request");
  if (record.schema_version !== "pi-runtime.request.v1") {
    throw new RuntimeContractError("schema_invalid", "schema_version must be pi-runtime.request.v1");
  }
  const runKind = requireString(record, "run_kind") as RunKind;
  if (!RUN_KINDS.has(runKind) || runKind !== expectedKind) {
    throw new RuntimeContractError("invalid_request", `run_kind must be ${expectedKind}`);
  }

  const runId = requireString(record, "run_id");
  const idempotencyKey = requireString(record, "idempotency_key");
  if (runId.length > 256 || idempotencyKey.length > 256) {
    throw new RuntimeContractError("invalid_request", "run_id and idempotency_key are too long");
  }
  requireString(record, "workspace_id");
  requireString(record, "conversation_id");
  const fromSeq = requireInteger(record, "from_message_seq", 1);
  const throughSeq = requireInteger(record, "through_message_seq", 1);
  if (throughSeq < fromSeq) {
    throw new RuntimeContractError("invalid_request", "through_message_seq must be >= from_message_seq");
  }
  validateManifest(requireObject(record, "context_manifest"));
  requireString(record, "instructions_ref");
  requireObject(record, "model_policy");
  requireObject(record, "tool_profile");
  requireInteger(record, "deadline_ms", 1);
  requireObject(record, "trace_context");

  if (runKind === "chat") {
    requireString(record, "package_id");
    requireString(record, "raw_user_message_ref");
    requireString(record, "assistant_reply_schema_ref");
    requireString(record, "conversation_order_key");
  } else if (runKind === "judgement") {
    requireString(record, "chat_turn_id");
    requireInteger(record, "base_state_version", 0);
    requireInteger(record, "base_package_version", 0);
    requireString(record, "signal_summary_ref");
  } else {
    requireString(record, "package_id");
    requireString(record, "convergence_run_id");
    requireInteger(record, "base_state_version", 0);
    requireInteger(record, "base_package_version", 0);
    requireString(record, "proposal_schema_ref");
    requireString(record, "proposal_capture_tool_ref");
  }

  return record as unknown as RunRequest;
}

export function validateCancelRequest(input: unknown, runId: string): void {
  const record = asRecord(input, "request");
  if (record.schema_version !== "pi-runtime.cancel.v1") {
    throw new RuntimeContractError("schema_invalid", "schema_version must be pi-runtime.cancel.v1");
  }
  if (record.run_id !== runId) {
    throw new RuntimeContractError("invalid_request", "cancel run_id does not match route run_id");
  }
  requireString(record, "reason_code");
  requireString(record, "requested_by");
  requireObject(record, "trace_context");
}

export function parseAfterSequence(url: URL): number {
  const raw = url.searchParams.get("after_sequence");
  if (raw === null || raw === "") return 0;
  const sequence = Number(raw);
  if (!Number.isInteger(sequence) || sequence < 0) {
    throw new RuntimeContractError("invalid_request", "after_sequence must be an integer >= 0");
  }
  return sequence;
}

export function toErrorEnvelope(error: unknown, runId?: string, traceId?: string): RuntimeErrorEnvelope {
  if (error instanceof RuntimeContractError) {
    return {
      ...error.envelope,
      run_id: runId,
      trace_id: traceId,
    };
  }
  return {
    schema_version: "pi-runtime.error.v1",
    error_code: "runtime_internal_error",
    category: "engine_unavailable",
    message: "Pi Runtime failed to execute the run",
    retryable: true,
    run_id: runId,
    trace_id: traceId,
    details: {},
  };
}

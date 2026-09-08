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

export class RuntimeDeadlineError extends Error {
  constructor(readonly runId: string, readonly deadlineMs: number) {
    super(`run ${runId} exceeded its ${deadlineMs}ms deadline`);
    this.name = "RuntimeDeadlineError";
  }
}

export class RuntimeProviderNotReadyError extends Error {
  constructor(
    readonly providerId: string,
    readonly modelId: string | undefined,
    readonly reason: string,
  ) {
    super(reason);
    this.name = "RuntimeProviderNotReadyError";
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

function validateToolProfile(profile: Record<string, unknown>, runKind: RunKind): void {
  if (requireString(profile, "run_kind") !== runKind) {
    throw new RuntimeContractError("invalid_request", "tool_profile.run_kind must match run_kind");
  }
  const allowedTools = profile.allowed_tools;
  if (!Array.isArray(allowedTools) || allowedTools.some((tool) => typeof tool !== "string" || tool.trim() === "")) {
    throw new RuntimeContractError("invalid_request", "tool_profile.allowed_tools must be an array of non-empty strings");
  }
  requireInteger(profile, "max_calls", 0);
  requireInteger(profile, "max_result_bytes", 1024);
  for (const field of ["gateway_url", "run_scoped_token", "tenant_id"]) {
    if (profile[field] !== undefined) requireString(profile, field);
  }
  if ((profile.gateway_url === undefined) !== (profile.run_scoped_token === undefined)) {
    throw new RuntimeContractError("invalid_request", "tool_profile.gateway_url and run_scoped_token must be provided together");
  }
  if (allowedTools.includes("submit_convergence_proposal") && runKind !== "convergence") {
    throw new RuntimeContractError("invalid_request", "submit_convergence_proposal is only valid for convergence runs");
  }
}

function validateRuntimeInputs(inputs: Record<string, unknown>): void {
  asRecord(inputs.structured_package_input, "runtime_inputs.structured_package_input");
  const messages = inputs.conversation_messages;
  if (!Array.isArray(messages) || messages.some((message) => !message || typeof message !== "object" || Array.isArray(message))) {
    throw new RuntimeContractError("invalid_request", "runtime_inputs.conversation_messages must be an array of objects");
  }
  if (inputs.raw_user_message !== undefined && inputs.raw_user_message !== null && typeof inputs.raw_user_message !== "string") {
    throw new RuntimeContractError("invalid_request", "runtime_inputs.raw_user_message must be a string or null");
  }
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
  validateToolProfile(requireObject(record, "tool_profile"), runKind);
  if (record.runtime_inputs !== undefined) validateRuntimeInputs(requireObject(record, "runtime_inputs"));
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
  if (error instanceof RuntimeDeadlineError) {
    return {
      schema_version: "pi-runtime.error.v1",
      error_code: "run_timeout",
      category: "temporary_error",
      message: error.message,
      retryable: true,
      run_id: runId ?? error.runId,
      trace_id: traceId,
      details: { deadline_ms: error.deadlineMs },
    };
  }
  if (error instanceof RuntimeProviderNotReadyError) {
    return {
      schema_version: "pi-runtime.error.v1",
      error_code: "runtime_not_ready",
      category: "not_ready",
      message: "Pi Runtime provider is not ready",
      retryable: false,
      run_id: runId,
      trace_id: traceId,
      details: {
        provider_id: error.providerId,
        model_id: error.modelId ?? null,
        reason: error.reason,
      },
    };
  }
  if (typeof error === "object" && error !== null && "code" in error && typeof (error as any).code === "string") {
    const code = (error as any).code;
    let category: RuntimeErrorEnvelope["category"] = "temporary_error";
    if (code === "runtime.submission_conflict" || code.startsWith("schema.")) category = "input_error";
    else if (code.startsWith("auth.")) category = "permission_denied";
    else if (code === "workspace.stale_revision") category = "stale";
    else if (code.startsWith("workspace.confirmation_")) category = "governance_rejected";
    return {
      schema_version: "pi-runtime.error.v1",
      error_code: code,
      category,
      message: error instanceof Error ? error.message : String((error as any).message ?? error),
      retryable: false,
      run_id: runId,
      trace_id: traceId,
      details: {},
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

// --- v1 Contract Validators ---

export function validateUserSubmissionRequest(value: unknown): import("./contracts.js").V1UserSubmissionRequest {
  const record = asRecord(value, "UserSubmissionRequest");
  if (record.contract_type !== "user_submission_request") {
    throw new RuntimeContractError("schema_invalid", "contract_type must be user_submission_request");
  }
  if (record.schema_version !== "evocanvas.pi-runtime.v1") {
    throw new RuntimeContractError("schema_invalid", "schema_version must be evocanvas.pi-runtime.v1");
  }
  const submissionId = requireString(record, "submission_id");
  const contentHash = requireString(record, "content_hash");
  if (!/^sha256:[a-fA-F0-9]{64}$/.test(contentHash)) {
    throw new RuntimeContractError("schema_invalid", "content_hash must match sha256 pattern");
  }
  const workspaceId = requireString(record, "workspace_id");
  const actorId = requireString(record, "actor_id");
  const piUserMessage = requireObject(record, "pi_user_message");

  return {
    contract_type: "user_submission_request",
    schema_version: "evocanvas.pi-runtime.v1",
    submission_id: submissionId,
    content_hash: contentHash,
    workspace_id: workspaceId,
    actor_id: actorId,
    pi_user_message: piUserMessage,
  };
}

export function validateWorkspaceCommitRequest(value: unknown): import("./contracts.js").V1WorkspaceCommitRequest {
  const record = asRecord(value, "WorkspaceCommitRequest");
  if (record.contract_type !== "workspace_commit_request") {
    throw new RuntimeContractError("schema_invalid", "contract_type must be workspace_commit_request");
  }
  if (record.schema_version !== "evocanvas.pi-runtime.v1") {
    throw new RuntimeContractError("schema_invalid", "schema_version must be evocanvas.pi-runtime.v1");
  }
  const toolContext = requireObject(record, "tool_context") as any;
  for (const key of ["workspace_id", "session_id", "entry_id", "actor_id"]) requireString(toolContext, key);
  if (!Array.isArray(toolContext.capabilities) || toolContext.capabilities.some((item: unknown) => typeof item !== "string")) throw new RuntimeContractError("schema_invalid", "capabilities must be a string array");
  const baseRevisionId = requireString(record, "base_revision_id");
  const idempotencyKey = requireString(record, "idempotency_key");
  const requestHash = requireString(record, "request_hash");
  if (!Array.isArray(record.operations)) {
    throw new RuntimeContractError("schema_invalid", "operations must be an array");
  }
  const confirmationRefs = Array.isArray(record.confirmation_refs) ? (record.confirmation_refs as string[]) : [];
  const changeSummary = requireString(record, "change_summary");

  return {
    contract_type: "workspace_commit_request",
    schema_version: "evocanvas.pi-runtime.v1",
    tool_context: toolContext,
    base_revision_id: baseRevisionId,
    idempotency_key: idempotencyKey,
    request_hash: requestHash,
    operations: record.operations as any,
    confirmation_refs: confirmationRefs,
    change_summary: changeSummary,
  };
}

export function validateSessionLifecycleCommand(value: unknown): import("./contracts.js").V1SessionLifecycleCommand {
  const record = asRecord(value, "SessionLifecycleCommand");
  if (record.contract_type !== "session_lifecycle_command") {
    throw new RuntimeContractError("schema_invalid", "contract_type must be session_lifecycle_command");
  }
  if (record.schema_version !== "evocanvas.pi-runtime.v1") {
    throw new RuntimeContractError("schema_invalid", "schema_version must be evocanvas.pi-runtime.v1");
  }
  const lifecycleOperationId = requireString(record, "lifecycle_operation_id");
  const workspaceId = requireString(record, "workspace_id");
  const action = requireString(record, "action");
  if (!["close", "archive", "replace", "delete"].includes(action)) {
    throw new RuntimeContractError("schema_invalid", `Invalid lifecycle action: ${action}`);
  }
  const idempotencyKey = requireString(record, "idempotency_key");

  return {
    contract_type: "session_lifecycle_command",
    schema_version: "evocanvas.pi-runtime.v1",
    lifecycle_operation_id: lifecycleOperationId,
    workspace_id: workspaceId,
    action: action as any,
    idempotency_key: idempotencyKey,
    replacement_session_id: typeof record.replacement_session_id === "string" ? record.replacement_session_id : undefined,
  };
}

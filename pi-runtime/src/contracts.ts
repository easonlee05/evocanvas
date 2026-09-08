export type RunKind = "chat" | "judgement" | "convergence";

export type RuntimeRunStatus =
  | "created"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type EventType =
  | "run.started"
  | "assistant.delta"
  | "assistant.completed"
  | "tool.requested"
  | "tool.completed"
  | "proposal.captured"
  | "usage.updated"
  | "run.completed"
  | "run.cancelled"
  | "run.failed"
  | string;

export interface TraceContext {
  trace_id: string;
  request_id: string;
  parent_run_id?: string;
  operation_id?: string;
  [key: string]: unknown;
}

export interface ContextManifest {
  context_manifest_id: string;
  request_kind: RunKind;
  package_ref: {
    package_id: string;
    package_version: number;
    state_version: number;
  };
  structured_package_input_ref: {
    id: string;
    content_hash: string;
  };
  message_scope: {
    from_seq: number;
    through_seq: number;
    history_compaction_ref?: string | null;
    raw_user_message_ref?: string | null;
  };
  instruction_and_schema_refs: string[];
  source_refs: string[];
  included_sections: string[];
  omissions: Array<Record<string, unknown>>;
  assembly_policy_version: string;
  budget_ref: string;
  degradation_flags: string[];
  content_hashes: Record<string, string>;
  transport_ref: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ModelPolicy {
  quality_tier: string;
  latency_tier: string;
  structured_output_required: boolean;
  tool_calling_required: boolean;
  max_cost?: number | null;
  provider_allowlist?: string[];
  [key: string]: unknown;
}

export interface ToolProfile {
  run_kind: RunKind;
  allowed_tools: string[];
  max_calls: number;
  max_result_bytes: number;
  gateway_url?: string;
  run_scoped_token?: string;
  tenant_id?: string;
  [key: string]: unknown;
}

/** Python 装配、单次调用消费、不进入运行记录或产品事实的临时输入快照。 */
export interface RuntimeInputSnapshot {
  structured_package_input: Record<string, unknown>;
  conversation_messages: Array<Record<string, unknown>>;
  raw_user_message?: string | null;
}

export interface ToolCallRequest {
  schema_version: "pi-runtime.tool-call.v1";
  tool_call_id: string;
  tool_name: string;
  tool_version: string;
  run_id: string;
  run_kind: RunKind;
  workspace_id: string;
  conversation_id: string;
  package_id?: string | null;
  tenant_id?: string;
  message_range?: { from_seq: number; through_seq: number };
  arguments: Record<string, unknown>;
  attempt: number;
  trace_context: TraceContext;
}

export type ToolCallStatus = "succeeded" | "failed" | "denied" | "timed_out" | "cancelled";

export interface ToolCallResult {
  schema_version: "pi-runtime.tool-result.v1";
  tool_call_id: string;
  status: ToolCallStatus;
  summary: string;
  data?: unknown;
  data_ref?: string | null;
  source_refs: string[];
  artifacts: string[];
  error: RuntimeErrorEnvelope | null;
  completed_at: string;
}

export interface BaseRunRequest {
  schema_version: "pi-runtime.request.v1";
  run_id: string;
  run_kind: RunKind;
  workspace_id: string;
  conversation_id: string;
  package_id?: string;
  from_message_seq: number;
  through_message_seq: number;
  context_manifest: ContextManifest;
  instructions_ref: string;
  model_policy: ModelPolicy;
  tool_profile: ToolProfile;
  deadline_ms: number;
  trace_context: TraceContext;
  idempotency_key: string;
  runtime_inputs?: RuntimeInputSnapshot;
  [key: string]: unknown;
}

export interface ChatRunRequest extends BaseRunRequest {
  run_kind: "chat";
  package_id: string;
  raw_user_message_ref: string;
  assistant_reply_schema_ref: string;
  conversation_order_key: string;
}

export interface JudgementRunRequest extends BaseRunRequest {
  run_kind: "judgement";
  chat_turn_id: string;
  base_state_version: number;
  base_package_version: number;
  signal_summary_ref: string;
}

export interface ConvergenceRunRequest extends BaseRunRequest {
  run_kind: "convergence";
  package_id: string;
  convergence_run_id: string;
  base_state_version: number;
  base_package_version: number;
  proposal_schema_ref: string;
  proposal_capture_tool_ref: string;
}

export type RunRequest = ChatRunRequest | JudgementRunRequest | ConvergenceRunRequest;

export interface Usage {
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  provider_usage_ref: string | null;
}

export interface ModelIdentity {
  provider_id: string;
  model_id: string;
  adapter_version: string;
  protocol_version: string;
}

export interface AssistantMessage {
  content_blocks: Array<{ type: "text"; text: string }>;
}

export interface ProposalOperation {
  operation_id: string;
  operation_type: string;
  target_object_id: string | null;
  temporary_target_ref: string | null;
  before_ref: string | null;
  payload: Record<string, unknown>;
  source_refs: string[];
  confirmation_refs: string[];
  unresolved_refs: string[];
  risk_level: "low" | "medium" | "high";
  reason_codes: string[];
  atomic_group_id: string | null;
}

export interface ConvergenceProposal {
  proposal_schema_version: "evocanvas.convergence-proposal.v1";
  proposal_id: string;
  run_id: string;
  package_id: string;
  from_message_seq: number;
  through_message_seq: number;
  base_state_version: number;
  base_package_version: number;
  operations: ProposalOperation[];
}

export interface ChatRunResult {
  run_id: string;
  assistant_message: AssistantMessage | null;
  finish_reason: "completed" | "length" | "tool_failed" | "cancelled" | "error";
  events_summary: Record<string, unknown>;
  usage: Usage;
  model_identity: ModelIdentity;
  context_manifest_id: string;
}

export interface JudgementRunResult {
  run_id: string;
  decision: "skip" | "defer" | "trigger";
  reason_codes: string[];
  through_message_seq: number;
  confidence: number | null;
  usage: Usage;
  model_identity: ModelIdentity;
  context_manifest_id: string;
}

export interface ConvergenceRunResult {
  run_id: string;
  proposal: ConvergenceProposal | null;
  finish_reason: "completed" | "not_ready" | "tool_failed" | "cancelled" | "error";
  tool_trace: string[];
  usage: Usage;
  model_identity: ModelIdentity;
  context_manifest_id: string;
}

export type RunResult = ChatRunResult | JudgementRunResult | ConvergenceRunResult;

export interface EventEnvelope {
  schema_version: "pi-runtime.event.v1";
  event_id: string;
  run_id: string;
  sequence: number;
  timestamp: string;
  type: EventType;
  trace_context: TraceContext;
  payload: Record<string, unknown>;
}

export interface RuntimeErrorEnvelope {
  schema_version: "pi-runtime.error.v1";
  error_code: string;
  category:
    | "temporary_error"
    | "input_error"
    | "permission_denied"
    | "not_ready"
    | "stale"
    | "governance_rejected"
    | "commit_unknown"
    | "projection_failed"
    | "engine_unavailable";
  message: string;
  retryable: boolean;
  run_id?: string | null;
  trace_id?: string | null;
  details: Record<string, unknown>;
}

export interface CancelRequest {
  schema_version: "pi-runtime.cancel.v1";
  run_id: string;
  reason_code: string;
  requested_by: string;
  trace_context: TraceContext;
}

export interface Capabilities {
  schema_version: "pi-runtime.capabilities.v1";
  runtime_version: string;
  pi_agent_core_version: string;
  pi_ai_version: string;
  node_version: string;
  provider_id: string;
  adapter_version: string;
  protocol_version: string;
  capability_profile_version: string;
  supported_run_kinds: RunKind[];
  structured_output: boolean;
  tool_calling: boolean;
  streaming: boolean;
  cancellation: boolean;
  usage_reporting: boolean;
}

// --- Pi Runtime v1 Target Integration Contracts ---

export type V1SchemaVersion = "evocanvas.pi-runtime.v1";

export interface V1WorkspaceSessionBinding {
  contract_type: "workspace_session_binding";
  schema_version: V1SchemaVersion;
  workspace_id: string;
  primary_session_id: string;
  main_lane: "main";
  status: "binding" | "ready" | "unavailable" | "archived";
  pi_session_format_version: string;
  session_file_ref: string;
  created_at: string;
  last_opened_at: string;
  predecessor_session_id?: string;
  unavailable_reason?: string;
}

export interface V1UserSubmissionRequest {
  contract_type: "user_submission_request";
  schema_version: V1SchemaVersion;
  submission_id: string;
  content_hash: string;
  workspace_id: string;
  actor_id: string;
  pi_user_message: Record<string, unknown>;
}

export interface V1UserSubmissionReceipt {
  contract_type: "user_submission_receipt";
  schema_version: V1SchemaVersion;
  status: "accepted" | "duplicate";
  submission_id: string;
  content_hash: string;
  session_id: string;
  entry_id: string;
  binding_status: "ready";
}

export interface V1ToolContext {
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

export interface V1SemanticOperation {
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
  payload: Record<string, unknown>;
}

export interface V1WorkspaceCommitRequest {
  contract_type: "workspace_commit_request";
  schema_version: V1SchemaVersion;
  tool_context: V1ToolContext;
  base_revision_id: string;
  idempotency_key: string;
  request_hash: string;
  operations: V1SemanticOperation[];
  confirmation_refs: string[];
  change_summary: string;
}

export interface V1ToolExecutionRecord {
  contract_type: "tool_execution_record";
  schema_version: V1SchemaVersion;
  tool_name: string;
  tool_version: string;
  tool_context: V1ToolContext;
  side_effect_class: "none" | "workspace" | "external";
  replay: "safe" | "never";
  result_status: "success" | "failed" | "unknown";
  request_hash: string;
  idempotency_key?: string;
  effect_id?: string;
  error_code?: string;
  started_at: string;
  finished_at: string;
}

export interface V1SessionLifecycleCommand {
  contract_type: "session_lifecycle_command";
  schema_version: V1SchemaVersion;
  lifecycle_operation_id: string;
  workspace_id: string;
  action: "close" | "archive" | "replace" | "delete";
  idempotency_key: string;
  replacement_session_id?: string;
}

export interface V1SessionLifecycleResult {
  contract_type: "session_lifecycle_result";
  schema_version: V1SchemaVersion;
  lifecycle_operation_id: string;
  workspace_id: string;
  action: "close" | "archive" | "replace" | "delete";
  outcome: "closed" | "archived" | "replaced" | "deleted" | "partial" | "retention_held";
  residual_targets: string[];
  retention_reason?: string;
  replacement_session_id?: string;
}

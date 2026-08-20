import { strict as assert } from "node:assert";
import { test } from "node:test";
import type { ChatRunRequest, ConvergenceRunRequest } from "../contracts.js";
import { createRunToolRuntime, RunToolRuntime, type ToolHandler } from "./tools.js";

function manifest(requestKind: "chat" | "convergence") {
  return {
    context_manifest_id: `manifest-${requestKind}`,
    request_kind: requestKind,
    package_ref: { package_id: "package-test", package_version: 1, state_version: 1 },
    structured_package_input_ref: { id: "spi-test", content_hash: "sha256:test" },
    message_scope: { from_seq: 1, through_seq: 2 },
    instruction_and_schema_refs: ["instructions:v1"],
    source_refs: [],
    included_sections: [],
    omissions: [],
    assembly_policy_version: "assembly:v1",
    budget_ref: "budget:test",
    degradation_flags: [],
    content_hashes: {},
    transport_ref: { provider_id: "test-provider" },
  };
}

function chatRequest(overrides: Partial<ChatRunRequest> = {}): ChatRunRequest {
  return {
    schema_version: "pi-runtime.request.v1",
    run_id: "run-tools-chat",
    run_kind: "chat",
    workspace_id: "workspace-test",
    conversation_id: "conversation-test",
    package_id: "package-test",
    from_message_seq: 1,
    through_message_seq: 2,
    context_manifest: manifest("chat"),
    instructions_ref: "instructions:v1",
    model_policy: {
      quality_tier: "balanced",
      latency_tier: "standard",
      structured_output_required: false,
      tool_calling_required: true,
    },
    tool_profile: {
      run_kind: "chat",
      allowed_tools: ["source.resolve"],
      max_calls: 2,
      max_result_bytes: 4096,
    },
    deadline_ms: 1000,
    trace_context: { trace_id: "trace-test", request_id: "request-test" },
    idempotency_key: "run-tools-chat",
    raw_user_message_ref: "message-test",
    assistant_reply_schema_ref: "schema:assistant:v1",
    conversation_order_key: "conversation-test:2",
    ...overrides,
  };
}

function convergenceRequest(overrides: Partial<ConvergenceRunRequest> = {}): ConvergenceRunRequest {
  return {
    schema_version: "pi-runtime.request.v1",
    run_id: "run-tools-convergence",
    run_kind: "convergence",
    workspace_id: "workspace-test",
    conversation_id: "conversation-test",
    package_id: "package-test",
    from_message_seq: 1,
    through_message_seq: 2,
    context_manifest: manifest("convergence"),
    instructions_ref: "instructions:convergence:v1",
    model_policy: {
      quality_tier: "quality",
      latency_tier: "background",
      structured_output_required: true,
      tool_calling_required: true,
    },
    tool_profile: {
      run_kind: "convergence",
      allowed_tools: ["submit_convergence_proposal"],
      max_calls: 2,
      max_result_bytes: 4096,
    },
    deadline_ms: 1000,
    trace_context: { trace_id: "trace-test", request_id: "request-test" },
    idempotency_key: "run-tools-convergence",
    convergence_run_id: "run-tools-convergence",
    base_state_version: 1,
    base_package_version: 1,
    proposal_schema_ref: "schema:proposal:v1",
    proposal_capture_tool_ref: "submit_convergence_proposal:v1",
    ...overrides,
  };
}

function events() {
  const values: Array<{ type: string; payload: Record<string, unknown> }> = [];
  return {
    values,
    emit: async (type: string, payload: Record<string, unknown>) => {
      values.push({ type, payload });
    },
  };
}

const readHandler: ToolHandler = {
  name: "source.resolve",
  version: "v1",
  allowed_run_kinds: ["chat"],
  side_effect: "read",
  timeout_ms: 100,
  async invoke({ request }) {
    return {
      summary: "source resolved",
      data: { source_ref_id: request.arguments.source_ref_id, verified: true },
      source_refs: [String(request.arguments.source_ref_id)],
    };
  },
};

test("RunToolRuntime executes an allowed read tool and emits a bounded trace", async () => {
  const runtime = new RunToolRuntime(chatRequest(), { handlers: [readHandler] });
  const trace = events();
  const result = await runtime.call(
    "source.resolve",
    { source_ref_id: "source-1" },
    trace.emit,
    new AbortController().signal,
  );

  assert.equal(result.status, "succeeded");
  assert.deepEqual(result.source_refs, ["source-1"]);
  assert.deepEqual(trace.values.map((event) => event.type), ["tool.requested", "tool.completed"]);
});

test("RunToolRuntime rejects unlisted tools and enforces the call budget", async () => {
  const request = chatRequest({
    tool_profile: { ...chatRequest().tool_profile, max_calls: 1 },
  });
  const runtime = new RunToolRuntime(request, { handlers: [readHandler] });
  const trace = events();
  const denied = await runtime.call("artifact.write", {}, trace.emit, new AbortController().signal);
  assert.equal(denied.status, "denied");
  assert.equal(denied.error?.error_code, "permission_denied");

  const first = await runtime.call("source.resolve", { source_ref_id: "source-1" }, trace.emit, new AbortController().signal);
  const second = await runtime.call("source.resolve", { source_ref_id: "source-2" }, trace.emit, new AbortController().signal);
  assert.equal(first.status, "succeeded");
  assert.equal(second.status, "denied");
  assert.equal(second.error?.error_code, "permission_denied");
});

test("RunToolRuntime reports input errors for oversized results", async () => {
  const oversized: ToolHandler = {
    ...readHandler,
    async invoke() {
      return { summary: "oversized", data: "x".repeat(5000) };
    },
  };
  const request = chatRequest({
    tool_profile: { ...chatRequest().tool_profile, max_result_bytes: 1024 },
  });
  const runtime = new RunToolRuntime(request, { handlers: [oversized] });
  const result = await runtime.call("source.resolve", {}, events().emit, new AbortController().signal);

  assert.equal(result.status, "failed");
  assert.equal(result.error?.error_code, "invalid_request");
  assert.equal(result.error?.category, "input_error");
});

test("RunToolRuntime applies handler timeouts", async () => {
  const slow: ToolHandler = {
    ...readHandler,
    timeout_ms: 5,
    async invoke() {
      await new Promise((resolve) => setTimeout(resolve, 50));
      return { summary: "too late" };
    },
  };
  const runtime = new RunToolRuntime(chatRequest(), { handlers: [slow] });
  const result = await runtime.call("source.resolve", {}, events().emit, new AbortController().signal);

  assert.equal(result.status, "timed_out");
  assert.equal(result.error?.error_code, "tool_timeout");
});

test("RunToolRuntime preserves stable error codes returned by the Python Gateway", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async () => new Response(JSON.stringify({
    status: "failed",
    summary: "source missing",
    error: {
      error_code: "source_not_found",
      category: "input_error",
      message: "source was not found",
      retryable: false,
    },
  }), {
    status: 200,
    headers: { "content-type": "application/json" },
  })) as typeof fetch;
  try {
    const request = chatRequest({
      tool_profile: {
        ...chatRequest().tool_profile,
        allowed_tools: ["source.resolve"],
        gateway_url: "http://gateway.test/internal/v1/tool-calls",
        run_scoped_token: "run-token",
      },
    });
    const runtime = createRunToolRuntime(request);
    const result = await runtime.call(
      "source.resolve",
      { source_ref_id: "missing" },
      events().emit,
      new AbortController().signal,
    );

    assert.equal(result.status, "failed");
    assert.equal(result.error?.error_code, "source_not_found");
    assert.equal(result.error?.category, "input_error");
    assert.equal(result.error?.retryable, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("RunToolRuntime captures one validated convergence proposal in memory", async () => {
  const runtime = new RunToolRuntime(convergenceRequest());
  const trace = events();
  const proposal = {
    proposal_schema_version: "evocanvas.convergence-proposal.v1",
    proposal_id: "proposal-1",
    run_id: "run-tools-convergence",
    package_id: "package-test",
    from_message_seq: 1,
    through_message_seq: 2,
    base_state_version: 1,
    base_package_version: 1,
    operations: [],
  } as const;
  const result = await runtime.call(
    "submit_convergence_proposal",
    { proposal },
    trace.emit,
    new AbortController().signal,
  );

  assert.equal(result.status, "succeeded");
  assert.equal(runtime.proposalCapture?.getProposal()?.proposal_id, "proposal-1");
  assert.equal(trace.values.at(-1)?.type, "tool.completed");
});

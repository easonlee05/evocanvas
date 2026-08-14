import { strict as assert } from "node:assert";
import type { AddressInfo } from "node:net";
import { test } from "node:test";
import { createPiRuntimeServer } from "../server.js";
import type { ChatRunRequest, EventEnvelope } from "../contracts.js";
import { FakeRunExecutor } from "./executor.js";
import { RunIdConflictError, RunRegistry } from "./run-registry.js";

function chatRequest(runId = "run-test-1"): ChatRunRequest {
  return {
    schema_version: "pi-runtime.request.v1",
    run_id: runId,
    run_kind: "chat",
    workspace_id: "workspace-test",
    conversation_id: "conversation-test",
    package_id: "package-test",
    from_message_seq: 1,
    through_message_seq: 1,
    context_manifest: {
      context_manifest_id: "manifest-test",
      request_kind: "chat",
      package_ref: { package_id: "package-test", package_version: 1, state_version: 1 },
      structured_package_input_ref: { id: "spi-test", content_hash: "sha256:test" },
      message_scope: { from_seq: 1, through_seq: 1, raw_user_message_ref: "message-test" },
      instruction_and_schema_refs: ["instructions:v1"],
      source_refs: [],
      included_sections: [],
      omissions: [],
      assembly_policy_version: "assembly:v1",
      budget_ref: "budget:test",
      degradation_flags: [],
      content_hashes: {},
      transport_ref: { provider_id: "fake-provider" },
    },
    instructions_ref: "instructions:v1",
    model_policy: {
      quality_tier: "balanced",
      latency_tier: "standard",
      structured_output_required: false,
      tool_calling_required: false,
    },
    tool_profile: { run_kind: "chat", allowed_tools: [], max_calls: 0, max_result_bytes: 1024 },
    deadline_ms: 1000,
    trace_context: { trace_id: "trace-test", request_id: "request-test" },
    idempotency_key: runId,
    raw_user_message_ref: "message-test",
    assistant_reply_schema_ref: "schema:assistant:v1",
    conversation_order_key: "conversation-test:1",
  };
}

test("RunRegistry keeps per-run sequence and rejects different duplicate payloads", () => {
  const registry = new RunRegistry();
  const first = registry.create(chatRequest());
  assert.equal(first.existing, false);
  const duplicate = registry.create(chatRequest());
  assert.equal(duplicate.existing, true);
  assert.throws(() => registry.create({
    ...chatRequest("run-test-1"),
    through_message_seq: 2,
  }), RunIdConflictError);
  registry.start(first.record);
  const firstEvent = first.record.events[0];
  assert.equal(firstEvent.sequence, 1);
  const secondEvent = registry.appendEvent(first.record, "usage.updated", {});
  assert.equal(secondEvent.sequence, 2);
});

test("Pi Runtime HTTP completes a fake Chat run and exposes terminal query", async () => {
  const runtime = createPiRuntimeServer({ host: "127.0.0.1", port: 0, executor: new FakeRunExecutor() });
  await runtime.listen();
  const address = runtime.server.address() as AddressInfo;
  const baseUrl = `http://127.0.0.1:${address.port}`;
  try {
    const response = await fetch(`${baseUrl}/v1/chat-runs`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(chatRequest()),
    });
    assert.equal(response.status, 200);
    const lines = (await response.text()).trim().split("\n").map((line) => JSON.parse(line) as EventEnvelope);
    assert.deepEqual(lines.map((event) => event.sequence), [1, 2, 3, 4, 5]);
    assert.deepEqual(
      lines.map((event) => event.type),
      ["run.started", "usage.updated", "assistant.delta", "assistant.completed", "run.completed"],
    );

    const terminal = await fetch(`${baseUrl}/v1/runs/run-test-1`);
    assert.equal(terminal.status, 200);
    const summary = await terminal.json() as { status: string; result: { run_id: string } };
    assert.equal(summary.status, "completed");
    assert.equal(summary.result.run_id, "run-test-1");
  } finally {
    await runtime.close();
  }
});

test("Pi Runtime readiness and capabilities expose package probe without provider credentials", async () => {
  const runtime = createPiRuntimeServer({ host: "127.0.0.1", port: 0 });
  await runtime.listen();
  const address = runtime.server.address() as AddressInfo;
  const baseUrl = `http://127.0.0.1:${address.port}`;
  try {
    const ready = await fetch(`${baseUrl}/readyz`);
    assert.equal(ready.status, 200);
    const readyPayload = await ready.json() as { status: string; probe: { agent_export_available: boolean } };
    assert.equal(readyPayload.status, "ready");
    assert.equal(readyPayload.probe.agent_export_available, true);

    const capabilities = await fetch(`${baseUrl}/v1/capabilities`);
    assert.equal(capabilities.status, 200);
    const payload = await capabilities.json() as { pi_agent_core_version: string; supported_run_kinds: string[] };
    assert.equal(payload.pi_agent_core_version, "0.84.1");
    assert.deepEqual(payload.supported_run_kinds, ["chat", "judgement", "convergence"]);
  } finally {
    await runtime.close();
  }
});

import { strict as assert } from "node:assert";
import { test } from "node:test";
import { createModels, fauxAssistantMessage, fauxProvider, fauxToolCall } from "@earendil-works/pi-ai";
import type { Context } from "@earendil-works/pi-ai";
import type {
  ChatRunRequest,
  ChatRunResult,
  ConvergenceRunRequest,
  ConvergenceRunResult,
  JudgementRunRequest,
  JudgementRunResult,
} from "../contracts.js";
import { createConfiguredRunExecutor, PiProviderRunExecutor } from "./executor.js";
import { RuntimeProviderNotReadyError } from "../validation.js";

function manifest(requestKind: "chat" | "judgement" | "convergence") {
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
    transport_ref: { provider_id: "faux-provider" },
  };
}

function baseRequest(runKind: "chat" | "judgement" | "convergence") {
  return {
    schema_version: "pi-runtime.request.v1" as const,
    run_id: `run-faux-${runKind}`,
    run_kind: runKind,
    workspace_id: "workspace-test",
    conversation_id: "conversation-test",
    from_message_seq: 1,
    through_message_seq: 2,
    context_manifest: manifest(runKind),
    instructions_ref: "instructions:v1",
    model_policy: {
      quality_tier: "balanced",
      latency_tier: "standard",
      structured_output_required: true,
      tool_calling_required: true,
    },
    tool_profile: {
      run_kind: runKind,
      allowed_tools: runKind === "convergence" ? ["submit_convergence_proposal"] : [],
      max_calls: 2,
      max_result_bytes: 4096,
    },
    deadline_ms: 1000,
    trace_context: { trace_id: "trace-test", request_id: "request-test" },
    idempotency_key: `run-faux-${runKind}`,
  };
}

function chatRequest(): ChatRunRequest {
  return {
    ...baseRequest("chat"),
    run_kind: "chat",
    package_id: "package-test",
    raw_user_message_ref: "message-test",
    assistant_reply_schema_ref: "schema:assistant:v1",
    conversation_order_key: "conversation-test:2",
  };
}

function judgementRequest(): JudgementRunRequest {
  return {
    ...baseRequest("judgement"),
    run_kind: "judgement",
    chat_turn_id: "chat-test",
    package_id: "package-test",
    base_state_version: 1,
    base_package_version: 1,
    signal_summary_ref: "signal-test",
  };
}

function convergenceRequest(): ConvergenceRunRequest {
  return {
    ...baseRequest("convergence"),
    run_kind: "convergence",
    package_id: "package-test",
    convergence_run_id: "run-faux-convergence",
    base_state_version: 1,
    base_package_version: 1,
    proposal_schema_ref: "schema:proposal:v1",
    proposal_capture_tool_ref: "submit_convergence_proposal:v1",
  };
}

function setup(response: ReturnType<typeof fauxAssistantMessage>) {
  const faux = fauxProvider({
    provider: "faux-provider",
    models: [{ id: "faux-model" }],
  });
  faux.setResponses([response]);
  const models = createModels();
  models.setProvider(faux.provider);
  return new PiProviderRunExecutor({ providerId: "faux-provider", modelId: "faux-model", models });
}

async function run(executor: PiProviderRunExecutor, request: ChatRunRequest | JudgementRunRequest | ConvergenceRunRequest) {
  const emitted: string[] = [];
  const result = await executor.execute(
    request,
    async (type) => {
      emitted.push(type);
    },
    new AbortController().signal,
  );
  return { result, emitted };
}

test("PiProviderRunExecutor maps a real Agent text stream into the product Chat result", async () => {
  const executor = setup(fauxAssistantMessage("hello from provider"));
  const { result, emitted } = await run(executor, chatRequest());

  const chatResult = result as ChatRunResult;
  assert.equal(chatResult.run_id, "run-faux-chat");
  assert.equal(chatResult.finish_reason, "completed");
  assert.deepEqual(chatResult.assistant_message?.content_blocks, [{ type: "text", text: "hello from provider" }]);
  assert.ok(emitted.includes("assistant.delta"));
  assert.ok(emitted.includes("assistant.completed"));
});

test("PiProviderRunExecutor keeps structured input, history, and raw user text as separate messages", async () => {
  const seen: Context[] = [];
  const faux = fauxProvider({
    provider: "faux-context-provider",
    models: [{ id: "faux-context-model" }],
  });
  faux.setResponses([(context: Context) => {
    seen.push(context);
    return fauxAssistantMessage("context preserved");
  }]);
  const models = createModels();
  models.setProvider(faux.provider);
  const executor = new PiProviderRunExecutor({
    providerId: "faux-context-provider",
    modelId: "faux-context-model",
    models,
  });
  const request: ChatRunRequest = {
    ...chatRequest(),
    runtime_inputs: {
      structured_package_input: { intent: "keep sources distinct" },
      conversation_messages: [
        { message_id: "history-user", role: "user", content: "历史消息" },
        { message_id: "history-assistant", role: "assistant", content: "历史回应" },
      ],
      raw_user_message: "这是本轮原话",
    },
  };

  await run(executor, request);

  assert.equal(seen.length, 1);
  const messages = seen[0].messages;
  assert.equal(messages[0].role, "user");
  assert.match(String(messages[0].content), /keep sources distinct/);
  assert.equal(messages[1].role, "user");
  assert.equal(messages[1].content, "历史消息");
  assert.equal(messages[2].role, "assistant");
  assert.deepEqual(messages[2].content, [{ type: "text", text: "历史回应" }]);
  assert.equal(messages.at(-1)?.role, "user");
  assert.deepEqual(messages.at(-1)?.content, [{ type: "text", text: "这是本轮原话" }]);
});

test("PiProviderRunExecutor requires and captures a structured judgement tool call", async () => {
  const executor = setup(fauxAssistantMessage(fauxToolCall("submit_judgement", {
    decision: "trigger",
    reason_codes: ["new_unresolved_signal"],
    confidence: 0.8,
  })));
  const { result } = await run(executor, judgementRequest());

  const judgementResult = result as JudgementRunResult;
  assert.equal(judgementResult.decision, "trigger");
  assert.deepEqual(judgementResult.reason_codes, ["new_unresolved_signal"]);
  assert.equal(judgementResult.confidence, 0.8);
});

test("PiProviderRunExecutor captures convergence proposals through the in-memory tool", async () => {
  const proposal = {
    proposal_schema_version: "evocanvas.convergence-proposal.v1" as const,
    proposal_id: "proposal-faux-1",
    run_id: "run-faux-convergence",
    package_id: "package-test",
    from_message_seq: 1,
    through_message_seq: 2,
    base_state_version: 1,
    base_package_version: 1,
    operations: [],
  };
  const executor = setup(fauxAssistantMessage(fauxToolCall("submit_convergence_proposal", { proposal })));
  const { result, emitted } = await run(executor, convergenceRequest());

  const convergenceResult = result as ConvergenceRunResult;
  assert.equal(convergenceResult.finish_reason, "completed");
  assert.equal(convergenceResult.proposal?.proposal_id, "proposal-faux-1");
  assert.ok(emitted.includes("tool.requested"));
  assert.ok(emitted.includes("proposal.captured"));
});

test("PiProviderRunExecutor reports a denied tool as tool_failed", async () => {
  const executor = setup(fauxAssistantMessage(fauxToolCall("source.resolve", { source_ref_id: "missing" })));
  const request: ChatRunRequest = {
    ...chatRequest(),
    tool_profile: {
      ...chatRequest().tool_profile,
      allowed_tools: ["source.resolve"],
      max_calls: 1,
    },
  };

  const { result } = await run(executor, request);
  const chatResult = result as ChatRunResult;
  assert.equal(chatResult.finish_reason, "tool_failed");
  assert.equal(chatResult.assistant_message, null);
});

test("configured Pi Runtime defaults to DeepSeek V4 Flash without faking readiness", async () => {
  const previousProvider = process.env.PI_PROVIDER;
  const previousModel = process.env.PI_MODEL;
  const previousApiKey = process.env.DEEPSEEK_API_KEY;
  delete process.env.PI_PROVIDER;
  delete process.env.PI_MODEL;
  delete process.env.DEEPSEEK_API_KEY;
  try {
    const executor = createConfiguredRunExecutor();
    assert.ok(executor instanceof PiProviderRunExecutor);
    const readiness = await executor.readiness();
    assert.equal(readiness.provider_id, "deepseek");
    assert.equal(readiness.model_id, "deepseek-v4-flash");
    assert.equal(readiness.ready, false);
  } finally {
    if (previousProvider === undefined) delete process.env.PI_PROVIDER;
    else process.env.PI_PROVIDER = previousProvider;
    if (previousModel === undefined) delete process.env.PI_MODEL;
    else process.env.PI_MODEL = previousModel;
    if (previousApiKey === undefined) delete process.env.DEEPSEEK_API_KEY;
    else process.env.DEEPSEEK_API_KEY = previousApiKey;
  }
});

test("configured Pi Runtime resolves GPT-5.6 models to the OpenAI provider", async () => {
  const previousProvider = process.env.PI_PROVIDER;
  const previousModel = process.env.PI_MODEL;
  const previousApiKey = process.env.OPENAI_API_KEY;
  delete process.env.PI_PROVIDER;
  process.env.PI_MODEL = "gpt-5.6-luna";
  delete process.env.OPENAI_API_KEY;
  try {
    const executor = createConfiguredRunExecutor();
    const readiness = await executor.readiness();
    assert.equal(readiness.provider_id, "openai");
    assert.equal(readiness.model_id, "gpt-5.6-luna");
    assert.equal(readiness.ready, false);
  } finally {
    if (previousProvider === undefined) delete process.env.PI_PROVIDER;
    else process.env.PI_PROVIDER = previousProvider;
    if (previousModel === undefined) delete process.env.PI_MODEL;
    else process.env.PI_MODEL = previousModel;
    if (previousApiKey === undefined) delete process.env.OPENAI_API_KEY;
    else process.env.OPENAI_API_KEY = previousApiKey;
  }
});

test("configured Pi Runtime fails explicitly when the default provider has no credentials", async () => {
  const previousProvider = process.env.PI_PROVIDER;
  const previousModel = process.env.PI_MODEL;
  const previousApiKey = process.env.DEEPSEEK_API_KEY;
  delete process.env.PI_PROVIDER;
  delete process.env.PI_MODEL;
  delete process.env.DEEPSEEK_API_KEY;
  try {
    const executor = createConfiguredRunExecutor();
    await assert.rejects(
      () => executor.execute(chatRequest(), async () => {}, new AbortController().signal),
      RuntimeProviderNotReadyError,
    );
  } finally {
    if (previousProvider === undefined) delete process.env.PI_PROVIDER;
    else process.env.PI_PROVIDER = previousProvider;
    if (previousModel === undefined) delete process.env.PI_MODEL;
    else process.env.PI_MODEL = previousModel;
    if (previousApiKey === undefined) delete process.env.DEEPSEEK_API_KEY;
    else process.env.DEEPSEEK_API_KEY = previousApiKey;
  }
});

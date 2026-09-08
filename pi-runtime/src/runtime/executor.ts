import { Agent, type AgentTool } from "@earendil-works/pi-agent-core";
import { createModels, Type, type Model, type MutableModels } from "@earendil-works/pi-ai";
import { builtinModels } from "@earendil-works/pi-ai/providers/all";
import type { AgentEvent } from "@earendil-works/pi-agent-core";
import type {
  AssistantMessage,
  ChatRunRequest,
  ConvergenceProposal,
  ConvergenceRunRequest,
  ConvergenceRunResult,
  EventEnvelope,
  JudgementRunRequest,
  JudgementRunResult,
  ModelIdentity,
  RunRequest,
  RunResult,
  Usage,
} from "../contracts.js";
import { createRunToolRuntime, type RunToolRuntime } from "./tools.js";
import { RuntimeProviderNotReadyError } from "../validation.js";

export interface RunEventSink {
  (type: EventEnvelope["type"], payload: Record<string, unknown>): Promise<void> | void;
}

export interface RunExecutor {
  execute(request: RunRequest, emit: RunEventSink, signal: AbortSignal, tools?: RunToolRuntime): Promise<RunResult>;
}

export interface RunReadiness {
  ready: boolean;
  provider_id: string;
  model_id?: string;
  reason?: string;
}

export interface ReadinessAwareRunExecutor extends RunExecutor {
  readiness(): Promise<RunReadiness>;
}

/** 未完成真实 Provider 适配时的显式失败执行器，禁止静默使用 Fake。 */
export class UnconfiguredRunExecutor implements RunExecutor {
  constructor(private readonly providerId: string) {}

  async execute(_request: RunRequest, _emit: RunEventSink, _signal: AbortSignal): Promise<RunResult> {
    throw new RuntimeProviderNotReadyError(
      this.providerId,
      undefined,
      `Pi Runtime provider ${this.providerId} is not configured; set PI_PROVIDER and install a real adapter`,
    );
  }

  async readiness(): Promise<RunReadiness> {
    return {
      ready: false,
      provider_id: this.providerId,
      reason: `Pi Runtime provider ${this.providerId} is not configured`,
    };
  }
}

const REAL_ADAPTER_VERSION = "pi-runtime.pi-agent-core.v1";
const REAL_PROTOCOL_VERSION = "pi-runtime.protocol.v1";
export const DEFAULT_PROVIDER_ID = "deepseek";
export const DEFAULT_MODEL_ID = "deepseek-v4-flash";

interface CapturedJudgement {
  decision: "skip" | "defer" | "trigger";
  reason_codes: string[];
  confidence: number | null;
}

function providerPrompt(request: RunRequest): string {
  const manifest = JSON.stringify(request.context_manifest);
  const common = [
    "你是 EvoCanvas 的 Pi Runtime 运行代理。Python Product Kernel 拥有产品事实、来源、版本、确认和提交权限。",
    "不得把信息不足伪装成结论，不得静默合并冲突，不得声称已写入产品状态。",
    `本次运行类型：${request.run_kind}；run_id：${request.run_id}。`,
    `Context Manifest（仅引用与范围，不是事实写入）：${manifest}`,
    `instructions_ref：${request.instructions_ref}`,
    "如果需要外部事实，只能使用请求中允许的只读工具，并保留来源引用。",
  ];
  if (request.run_kind === "chat") {
    common.push(
      `用户消息引用：${request.raw_user_message_ref}`,
      "先接住并命名用户尚未成形的感觉；只在上下文足够时给出结构化判断，不要编造消息正文。",
    );
  } else if (request.run_kind === "judgement") {
    common.push(
      `待判断聊天回合：${request.chat_turn_id}`,
      `信号摘要引用：${request.signal_summary_ref}`,
      "必须调用 submit_judgement 工具返回 decision、reason_codes 和可选 confidence；不要只在自然语言中给出判断。",
    );
  } else {
    common.push(
      `收敛运行：${request.convergence_run_id}`,
      "只有经过来源、范围、确认和版本约束检查后，才调用 submit_convergence_proposal；提案必须保留冲突、待澄清和未确认状态。",
    );
  }
  return common.join("\n");
}

function providerUserPrompt(request: RunRequest): string {
  if (request.run_kind === "chat") {
    return request.runtime_inputs?.raw_user_message ?? `请处理用户消息引用 ${request.raw_user_message_ref}，输出面向用户的阶段性回应。`;
  }
  if (request.run_kind === "judgement") {
    return `请根据聊天回合 ${request.chat_turn_id} 的信号摘要引用 ${request.signal_summary_ref} 完成判断。`;
  }
  return `请根据当前 Context Manifest 生成一次可验证的收敛提案，并通过 submit_convergence_proposal 提交候选。`;
}

function zeroProviderUsage() {
  return {
    input: 0,
    output: 0,
    cacheRead: 0,
    cacheWrite: 0,
    totalTokens: 0,
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
  };
}

function initialAgentMessages(
  request: RunRequest,
  model: Model<any>,
): import("@earendil-works/pi-ai").Message[] {
  const snapshot = request.runtime_inputs;
  if (!snapshot) return [];
  const messages: import("@earendil-works/pi-ai").Message[] = [
    {
      role: "user",
      content: `[Structured Package Input]\n${JSON.stringify(snapshot.structured_package_input)}`,
      timestamp: Date.now(),
    },
  ];
  for (const item of snapshot.conversation_messages) {
    const role = String(item.role ?? "user");
    const content = String(item.content ?? "");
    if (!content) continue;
    if (request.run_kind === "chat" && item.message_id === request.raw_user_message_ref) continue;
    const timestamp = Date.parse(String(item.created_at ?? "")) || Date.now();
    if (role === "assistant") {
      messages.push({
        role: "assistant",
        content: [{ type: "text", text: content }],
        api: model.api,
        provider: model.provider,
        model: model.id,
        usage: zeroProviderUsage(),
        stopReason: "stop",
        timestamp,
      });
    } else if (role === "toolResult") {
      messages.push({
        role: "toolResult",
        toolCallId: String(item.tool_call_id ?? "tool-history"),
        toolName: String(item.tool_name ?? "history"),
        content: [{ type: "text", text: content }],
        details: item.details,
        isError: Boolean(item.is_error),
        timestamp,
      });
    } else {
      messages.push({ role: "user", content, timestamp });
    }
  }
  return messages;
}

function toolSchema(name: string) {
  switch (name) {
    case "source.resolve":
      return Type.Object({ source_ref_id: Type.String() });
    case "material.read":
      return Type.Object({ material_id: Type.String() });
    case "knowledge.retrieve":
      return Type.Object({ query: Type.String(), scope: Type.Optional(Type.Any()) });
    case "structure.validate":
    case "submit_convergence_proposal":
      return Type.Object({ proposal: Type.Any() });
    default:
      return Type.Object({});
  }
}

function resultText(result: Record<string, unknown>): string {
  try {
    return JSON.stringify(result);
  } catch {
    return "工具返回了不可序列化的结果";
  }
}

function buildRuntimeTools(
  request: RunRequest,
  runtime: RunToolRuntime,
  emit: RunEventSink,
  toolTrace: string[],
  toolState: { failed: boolean },
  signal: AbortSignal,
): AgentTool[] {
  return request.tool_profile.allowed_tools.map((name) => ({
    name,
    label: name,
    description: `EvoCanvas 受控工具 ${name}；只返回本次运行允许的最小信息。`,
    parameters: toolSchema(name),
    executionMode: "sequential" as const,
    execute: async (toolCallId: string, params: unknown, toolSignal?: AbortSignal) => {
      toolTrace.push(toolCallId);
      const result = await runtime.call(
        name,
        (params && typeof params === "object" ? params : {}) as Record<string, unknown>,
        emit,
        toolSignal ?? signal,
      );
      if (result.status !== "succeeded") toolState.failed = true;
      return {
        content: [{ type: "text" as const, text: resultText(result as unknown as Record<string, unknown>) }],
        details: result,
        terminate: name === "submit_convergence_proposal" || result.status !== "succeeded",
      };
    },
  }));
}

function buildJudgementTool(capture: { value: CapturedJudgement | null }): AgentTool {
  return {
    name: "submit_judgement",
    label: "Submit Judgement",
    description: "提交本次聊天是否需要进入结构收敛的判断结果。",
    parameters: Type.Object({
      decision: Type.Union([Type.Literal("skip"), Type.Literal("defer"), Type.Literal("trigger")]),
      reason_codes: Type.Array(Type.String()),
      confidence: Type.Optional(Type.Number()),
    }),
    executionMode: "sequential",
    execute: async (_toolCallId: string, params: unknown) => {
      if (capture.value !== null) throw new Error("only one judgement may be captured per run");
      if (!params || typeof params !== "object") throw new Error("judgement must be an object");
      const value = params as Record<string, unknown>;
      const decision = value.decision;
      if (decision !== "skip" && decision !== "defer" && decision !== "trigger") {
        throw new Error("judgement decision is invalid");
      }
      const reasonCodes = value.reason_codes;
      if (!Array.isArray(reasonCodes) || reasonCodes.some((item) => typeof item !== "string" || !item.trim())) {
        throw new Error("judgement reason_codes must be a non-empty string array");
      }
      const confidence = value.confidence;
      if (confidence !== undefined && (typeof confidence !== "number" || confidence < 0 || confidence > 1)) {
        throw new Error("judgement confidence must be between 0 and 1");
      }
      capture.value = {
        decision,
        reason_codes: reasonCodes.map(String),
        confidence: confidence === undefined ? null : confidence,
      };
      return {
        content: [{ type: "text" as const, text: "judgement captured" }],
        details: capture.value,
        terminate: true,
      };
    },
  };
}

function usageFrom(message: import("@earendil-works/pi-ai").AssistantMessage): Usage {
  const input = Number.isFinite(message.usage.input) ? message.usage.input : null;
  const output = Number.isFinite(message.usage.output) ? message.usage.output : null;
  const total = Number.isFinite(message.usage.totalTokens)
    ? message.usage.totalTokens
    : input !== null && output !== null ? input + output : null;
  return {
    input_tokens: input,
    output_tokens: output,
    total_tokens: total,
    provider_usage_ref: message.responseId ? `provider-response:${message.responseId}` : null,
  };
}

function modelIdentity(message: import("@earendil-works/pi-ai").AssistantMessage): ModelIdentity {
  return {
    provider_id: message.provider,
    model_id: message.model,
    adapter_version: REAL_ADAPTER_VERSION,
    protocol_version: REAL_PROTOCOL_VERSION,
  };
}

function assistantBlocks(message: import("@earendil-works/pi-ai").AssistantMessage): Array<{ type: "text"; text: string }> {
  return message.content.flatMap((block) => block.type === "text" ? [{ type: "text" as const, text: block.text }] : []);
}

function chatFinishReason(
  message: import("@earendil-works/pi-ai").AssistantMessage,
  toolFailed: boolean,
): "completed" | "length" | "tool_failed" | "cancelled" | "error" {
  if (toolFailed) return "tool_failed";
  if (message.stopReason === "aborted") return "cancelled";
  if (message.stopReason === "error") return "error";
  if (message.stopReason === "length") return "length";
  return "completed";
}

/** 使用 Pi Agent Core + Pi AI 内置 Provider 的真实执行器。 */
export class PiProviderRunExecutor implements ReadinessAwareRunExecutor {
  private readonly models: MutableModels;
  private readonly providerId: string;
  private readonly modelId?: string;

  constructor(options: { providerId: string; modelId?: string; models?: MutableModels }) {
    this.providerId = options.providerId;
    this.modelId = options.modelId;
    this.models = options.models ?? builtinModels();
  }

  private resolveModel(): Model<any> {
    const models = this.models.getModels(this.providerId);
    if (models.length === 0) {
      throw new Error(`Pi Runtime provider ${this.providerId} has no available models`);
    }
    const selected = this.modelId ? models.find((model) => model.id === this.modelId) : models[0];
    if (!selected) {
      throw new Error(`Pi Runtime model ${this.providerId}/${this.modelId} was not found`);
    }
    return selected;
  }

  async readiness(): Promise<RunReadiness> {
    try {
      const model = this.resolveModel();
      const auth = await this.models.getAuth(model);
      if (!auth) {
        return {
          ready: false,
          provider_id: this.providerId,
          model_id: model.id,
          reason: `Pi Runtime provider ${this.providerId} has no resolved credentials`,
        };
      }
      return { ready: true, provider_id: this.providerId, model_id: model.id };
    } catch (error) {
      return {
        ready: false,
        provider_id: this.providerId,
        reason: error instanceof Error ? error.message : String(error),
      };
    }
  }

  async execute(request: RunRequest, emit: RunEventSink, signal: AbortSignal, tools?: RunToolRuntime): Promise<RunResult> {
    const model = this.resolveModel();
    const auth = await this.models.getAuth(model);
    if (!auth) {
      throw new RuntimeProviderNotReadyError(
        this.providerId,
        model.id,
        `Pi Runtime provider ${this.providerId} has no resolved credentials`,
      );
    }
    const runtime = tools ?? createRunToolRuntime(request);
    const toolTrace: string[] = [];
    const toolState = { failed: false };
    const judgementCapture: { value: CapturedJudgement | null } = { value: null };
    const agentTools = request.run_kind === "judgement"
      ? [buildJudgementTool(judgementCapture)]
      : buildRuntimeTools(request, runtime, emit, toolTrace, toolState, signal);
    const agent = new Agent({
      initialState: {
        systemPrompt: providerPrompt(request),
        model,
        tools: agentTools,
        messages: initialAgentMessages(request, model),
      },
      streamFn: this.models.streamSimple.bind(this.models),
      toolExecution: "sequential",
    });
    const abortAgent = () => agent.abort();
    signal.addEventListener("abort", abortAgent, { once: true });
    let lastAssistant: import("@earendil-works/pi-ai").AssistantMessage | null = null;
    try {
      agent.subscribe(async (event: AgentEvent) => {
        if (event.type === "message_update" && event.assistantMessageEvent.type === "text_delta") {
          await emit("assistant.delta", {
            content_delta: event.assistantMessageEvent.delta,
            delta_index: event.assistantMessageEvent.contentIndex,
          });
        }
        if (event.type === "message_end" && event.message.role === "assistant") {
          lastAssistant = event.message;
        }
      });
      await agent.prompt(providerUserPrompt(request));
      throwIfAborted(signal);
      lastAssistant ??= [...agent.state.messages].reverse().find((message) => message.role === "assistant") as import("@earendil-works/pi-ai").AssistantMessage | undefined ?? null;
      if (!lastAssistant) throw new Error("Pi Agent completed without an assistant message");

      const usage = usageFrom(lastAssistant);
      await emit("usage.updated", { ...usage });
      const identity = modelIdentity(lastAssistant);
      if (request.run_kind === "chat") {
        const finishReason = chatFinishReason(lastAssistant, toolState.failed);
        const assistantMessage = finishReason === "completed" || finishReason === "length"
          ? { content_blocks: assistantBlocks(lastAssistant) }
          : null;
        if (assistantMessage !== null) {
          await emit("assistant.completed", {
            assistant_message: assistantMessage,
            finish_reason: finishReason,
          });
        }
        return {
          run_id: request.run_id,
          assistant_message: assistantMessage,
          finish_reason: finishReason,
          events_summary: { provider: identity.provider_id, model: identity.model_id, tool_calls: toolTrace.length },
          usage,
          model_identity: identity,
          context_manifest_id: request.context_manifest.context_manifest_id,
        };
      }
      if (request.run_kind === "judgement") {
        if (!judgementCapture.value) throw new Error("Pi Agent did not capture a judgement");
        const judgement = judgementCapture.value;
        return {
          run_id: request.run_id,
          decision: judgement.decision,
          reason_codes: judgement.reason_codes,
          through_message_seq: request.through_message_seq,
          confidence: judgement.confidence,
          usage,
          model_identity: identity,
          context_manifest_id: request.context_manifest.context_manifest_id,
        };
      }
      const proposal = runtime.proposalCapture?.getProposal() ?? null;
      if (!proposal) {
        const finishReason = toolState.failed
          ? "tool_failed"
          : lastAssistant.stopReason === "aborted"
            ? "cancelled"
            : lastAssistant.stopReason === "error" ? "error" : "not_ready";
        return {
          run_id: request.run_id,
          proposal: null,
          finish_reason: finishReason,
          tool_trace: toolTrace,
          usage,
          model_identity: identity,
          context_manifest_id: request.context_manifest.context_manifest_id,
        };
      }
      await emit("proposal.captured", {
        proposal_id: proposal.proposal_id,
        proposal_schema_version: proposal.proposal_schema_version,
        operation_count: proposal.operations.length,
        tool_call_id: toolTrace.at(-1) ?? null,
      });
      return {
        run_id: request.run_id,
        proposal,
        finish_reason: "completed",
        tool_trace: toolTrace,
        usage,
        model_identity: identity,
        context_manifest_id: request.context_manifest.context_manifest_id,
      };
    } finally {
      signal.removeEventListener("abort", abortAgent);
    }
  }
}

export function createConfiguredRunExecutor(): ReadinessAwareRunExecutor {
  const providerId = process.env.PI_PROVIDER?.trim() || DEFAULT_PROVIDER_ID;
  if (providerId === "fake-provider") return new FakeRunExecutor();
  return new PiProviderRunExecutor({
    providerId,
    modelId: process.env.PI_MODEL?.trim() || DEFAULT_MODEL_ID,
  });
}

export interface PiPackageProbe {
  agent_export_available: boolean;
  models_export_available: boolean;
  models_instance_created: boolean;
}

export function probePiPackages(): PiPackageProbe {
  let modelsInstanceCreated = false;
  try {
    createModels();
    modelsInstanceCreated = true;
  } catch {
    modelsInstanceCreated = false;
  }
  return {
    agent_export_available: typeof Agent === "function",
    models_export_available: typeof createModels === "function",
    models_instance_created: modelsInstanceCreated,
  };
}

const FAKE_MODEL_IDENTITY: ModelIdentity = {
  provider_id: "fake-provider",
  model_id: "fake-model",
  adapter_version: "fake-adapter:v1",
  protocol_version: "pi-runtime.protocol.v1",
};

const EMPTY_USAGE: Usage = {
  input_tokens: 0,
  output_tokens: 0,
  total_tokens: 0,
  provider_usage_ref: null,
};

function throwIfAborted(signal: AbortSignal): void {
  if (signal.aborted) {
    if (signal.reason instanceof Error) throw signal.reason;
    throw new Error(String(signal.reason ?? "cancelled"));
  }
}

async function tick(signal: AbortSignal): Promise<void> {
  throwIfAborted(signal);
  await new Promise<void>((resolve) => setTimeout(resolve, 0));
  throwIfAborted(signal);
}

function chatResult(request: ChatRunRequest): {
  result: RunResult;
  assistantMessage: AssistantMessage;
} {
  const assistantMessage: AssistantMessage = {
    content_blocks: [
      {
        type: "text",
        text: `[fake-provider] 已接收 ${request.raw_user_message_ref}`,
      },
    ],
  };
  return {
    assistantMessage,
    result: {
      run_id: request.run_id,
      assistant_message: assistantMessage,
      finish_reason: "completed",
      events_summary: { provider: "fake-provider", tool_calls: 0 },
      usage: EMPTY_USAGE,
      model_identity: { ...FAKE_MODEL_IDENTITY, model_id: "fake-chat" },
      context_manifest_id: request.context_manifest.context_manifest_id,
    },
  };
}

function judgementResult(request: JudgementRunRequest): JudgementRunResult {
  return {
    run_id: request.run_id,
    decision: "defer",
    reason_codes: ["fake_provider_defer"],
    through_message_seq: request.through_message_seq,
    confidence: null,
    usage: EMPTY_USAGE,
    model_identity: { ...FAKE_MODEL_IDENTITY, model_id: "fake-judgement" },
    context_manifest_id: request.context_manifest.context_manifest_id,
  };
}

function convergenceResult(
  request: ConvergenceRunRequest,
  proposal: ConvergenceProposal | null,
  toolTrace: string[],
  finishReason: ConvergenceRunResult["finish_reason"] = "completed",
): ConvergenceRunResult {
  return {
    run_id: request.run_id,
    proposal,
    finish_reason: finishReason,
    tool_trace: toolTrace,
    usage: EMPTY_USAGE,
    model_identity: { ...FAKE_MODEL_IDENTITY, model_id: "fake-convergence" },
    context_manifest_id: request.context_manifest.context_manifest_id,
  };
}

/**
 * Deterministic provider used by phase-1 runtime tests. It exercises the same
 * request/result/event boundary without inventing a second real model engine.
 */
export class FakeRunExecutor implements RunExecutor {
  async readiness(): Promise<RunReadiness> {
    return { ready: true, provider_id: "fake-provider", model_id: "fake-model" };
  }

  async execute(request: RunRequest, emit: RunEventSink, signal: AbortSignal, tools?: RunToolRuntime): Promise<RunResult> {
    await tick(signal);
    await emit("usage.updated", { ...EMPTY_USAGE });

    if (request.run_kind === "chat") {
      const { result, assistantMessage } = chatResult(request);
      await emit("assistant.delta", { content_delta: assistantMessage.content_blocks[0].text, delta_index: 0 });
      await emit("assistant.completed", {
        assistant_message: assistantMessage,
        finish_reason: "completed",
      });
      return result;
    }

    if (request.run_kind === "judgement") {
      return judgementResult(request);
    }

    const proposal: ConvergenceProposal = {
      proposal_schema_version: "evocanvas.convergence-proposal.v1",
      proposal_id: `proposal_${request.run_id}`,
      run_id: request.run_id,
      package_id: request.package_id,
      from_message_seq: request.from_message_seq,
      through_message_seq: request.through_message_seq,
      base_state_version: request.base_state_version,
      base_package_version: request.base_package_version,
      operations: [],
    };
    if (!tools) throw new Error("convergence execution requires a RunToolRuntime");
    const capture = await tools.call(
      request.proposal_capture_tool_ref.split(":", 1)[0],
      { proposal },
      emit,
      signal,
    );
    if (capture.status !== "succeeded") {
      return convergenceResult(request, null, [capture.tool_call_id], "tool_failed");
    }
    const captured = tools.proposalCapture?.getProposal() ?? proposal;
    await emit("proposal.captured", {
      proposal_id: captured.proposal_id,
      proposal_schema_version: captured.proposal_schema_version,
      operation_count: captured.operations.length,
      tool_call_id: capture.tool_call_id,
    });
    return convergenceResult(request, captured, [capture.tool_call_id]);
  }
}

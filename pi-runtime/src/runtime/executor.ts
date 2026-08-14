import { Agent } from "@earendil-works/pi-agent-core";
import { createModels } from "@earendil-works/pi-ai";
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

export interface RunEventSink {
  (type: EventEnvelope["type"], payload: Record<string, unknown>): Promise<void> | void;
}

export interface RunExecutor {
  execute(request: RunRequest, emit: RunEventSink, signal: AbortSignal): Promise<RunResult>;
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
    const reason = signal.reason instanceof Error ? signal.reason.message : String(signal.reason ?? "cancelled");
    throw new Error(reason);
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

function convergenceResult(request: ConvergenceRunRequest): ConvergenceRunResult {
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
  return {
    run_id: request.run_id,
    proposal,
    finish_reason: "completed",
    tool_trace: [],
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
  async execute(request: RunRequest, emit: RunEventSink, signal: AbortSignal): Promise<RunResult> {
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

    const result = convergenceResult(request);
    await emit("proposal.captured", {
      proposal_id: result.proposal?.proposal_id,
      operation_count: result.proposal?.operations.length ?? 0,
    });
    return result;
  }
}

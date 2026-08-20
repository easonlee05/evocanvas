import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { URL } from "node:url";
import { RunIdConflictError, RunRegistry, type RunRecord } from "./runtime/run-registry.js";
import {
  createConfiguredRunExecutor,
  DEFAULT_MODEL_ID,
  DEFAULT_PROVIDER_ID,
  probePiPackages,
  type ReadinessAwareRunExecutor,
  type RunExecutor,
  type RunReadiness,
} from "./runtime/executor.js";
import { createRunToolRuntime } from "./runtime/tools.js";
import type { Capabilities, EventEnvelope, RunKind, RunRequest } from "./contracts.js";
import {
  RuntimeContractError,
  RuntimeDeadlineError,
  parseAfterSequence,
  toErrorEnvelope,
  validateCancelRequest,
  validateRunRequest,
} from "./validation.js";

const RUNTIME_VERSION = "0.1.0";
const PI_AGENT_CORE_VERSION = "0.84.1";
const PI_AI_VERSION = "0.84.1";
const PROTOCOL_VERSION = "pi-runtime.protocol.v1";
const ADAPTER_VERSION = process.env.PI_ADAPTER_VERSION ?? "pi-runtime.unconfigured.v1";

interface RuntimeOptions {
  host?: string;
  port?: number;
  internalSecret?: string;
  executor?: RunExecutor;
  registry?: RunRegistry;
}

function json(value: unknown): string {
  return JSON.stringify(value);
}

function sendJson(response: ServerResponse, status: number, value: unknown): void {
  if (response.writableEnded) return;
  response.statusCode = status;
  response.setHeader("Content-Type", "application/json; charset=utf-8");
  response.end(json(value));
}

function sendError(response: ServerResponse, status: number, error: unknown, runId?: string, traceId?: string): void {
  const envelope = toErrorEnvelope(error, runId, traceId);
  if (error instanceof RuntimeContractError) {
    response.statusCode = error.httpStatus;
  } else if (error instanceof RunIdConflictError) {
    response.statusCode = 409;
    envelope.error_code = "run_id_conflict";
    envelope.category = "input_error";
    envelope.message = error.message;
    envelope.retryable = false;
  } else {
    response.statusCode = status;
  }
  response.setHeader("Content-Type", "application/json; charset=utf-8");
  response.end(json(envelope));
}

async function readBody(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    size += buffer.length;
    if (size > 1024 * 1024) {
      throw new RuntimeContractError("invalid_request", "request body exceeds 1 MiB");
    }
    chunks.push(buffer);
  }
  if (chunks.length === 0) return {};
  const text = Buffer.concat(chunks).toString("utf8");
  try {
    return JSON.parse(text);
  } catch {
    throw new RuntimeContractError("schema_invalid", "request body must be valid JSON");
  }
}

function traceIdFrom(request: RunRequest): string | undefined {
  return request.trace_context.trace_id;
}

function capabilities(): Capabilities {
  const probe = probePiPackages();
  const providerId = process.env.PI_PROVIDER?.trim() || DEFAULT_PROVIDER_ID;
  const realProvider = providerId !== "unconfigured" && providerId !== "fake-provider";
  return {
    schema_version: "pi-runtime.capabilities.v1",
    runtime_version: RUNTIME_VERSION,
    pi_agent_core_version: PI_AGENT_CORE_VERSION,
    pi_ai_version: PI_AI_VERSION,
    node_version: process.version,
    provider_id: providerId,
    adapter_version: realProvider ? "pi-runtime.pi-agent-core.v1" : ADAPTER_VERSION,
    protocol_version: PROTOCOL_VERSION,
    capability_profile_version: `pi-runtime.capabilities:${probe.agent_export_available && probe.models_instance_created ? "ready" : "degraded"}`,
    supported_run_kinds: ["chat", "judgement", "convergence"],
    structured_output: true,
    tool_calling: realProvider || providerId === "fake-provider",
    streaming: true,
    cancellation: true,
    usage_reporting: true,
  };
}

function isAuthorized(request: IncomingMessage, internalSecret: string | undefined): boolean {
  if (!internalSecret) return true;
  const authorization = request.headers.authorization;
  const supplied = authorization?.startsWith("Bearer ")
    ? authorization.slice("Bearer ".length)
    : request.headers["x-pi-internal-secret"];
  return supplied === internalSecret;
}

function routeRunKind(pathname: string): RunKind | null {
  if (pathname === "/v1/chat-runs") return "chat";
  if (pathname === "/v1/judgement-runs") return "judgement";
  if (pathname === "/v1/convergence-runs") return "convergence";
  return null;
}

export class PiRuntimeServer {
  readonly registry: RunRegistry;
  readonly executor: RunExecutor;
  readonly internalSecret?: string;
  readonly server: Server;
  readonly host: string;
  readonly port: number;

  constructor(options: RuntimeOptions = {}) {
    this.registry = options.registry ?? new RunRegistry();
    this.executor = options.executor ?? createConfiguredRunExecutor();
    this.internalSecret = options.internalSecret ?? process.env.PI_RUNTIME_INTERNAL_SECRET;
    this.host = options.host ?? process.env.PI_RUNTIME_HOST ?? "127.0.0.1";
    this.port = options.port ?? Number(process.env.PI_RUNTIME_PORT ?? 8790);
    this.server = createServer((request, response) => {
      void this.handle(request, response);
    });
  }

  async listen(): Promise<void> {
    await new Promise<void>((resolve, reject) => {
      const onError = (error: Error) => {
        this.server.off("listening", onListening);
        reject(error);
      };
      const onListening = () => {
        this.server.off("error", onError);
        resolve();
      };
      this.server.once("error", onError);
      this.server.once("listening", onListening);
      this.server.listen(this.port, this.host);
    });
  }

  async close(): Promise<void> {
    if (!this.server.listening) return;
    await new Promise<void>((resolve, reject) => {
      this.server.close((error) => (error ? reject(error) : resolve()));
    });
  }

  private async handle(request: IncomingMessage, response: ServerResponse): Promise<void> {
    const method = request.method ?? "GET";
    const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "127.0.0.1"}`);
    const pathname = url.pathname;

    try {
      if (method === "GET" && pathname === "/healthz") {
        sendJson(response, 200, { status: "ok", service: "pi-runtime", version: RUNTIME_VERSION });
        return;
      }
      if (method === "GET" && pathname === "/readyz") {
        const probe = probePiPackages();
        const readiness = await this.readiness();
        const ready = probe.agent_export_available
          && probe.models_instance_created
          && readiness.ready;
        sendJson(response, ready ? 200 : 503, {
          status: ready ? "ready" : "not_ready",
          provider: readiness.provider_id,
          model: readiness.model_id,
          reason: readiness.reason,
          probe,
        });
        return;
      }
      if (method === "GET" && pathname === "/v1/capabilities") {
        this.requireAuthorization(request);
        sendJson(response, 200, capabilities());
        return;
      }

      const runKind = method === "POST" ? routeRunKind(pathname) : null;
      if (runKind) {
        this.requireAuthorization(request);
        await this.handleRun(request, response, runKind);
        return;
      }

      const runMatch = pathname.match(/^\/v1\/runs\/([^/]+)$/);
      if (runMatch && method === "GET") {
        this.requireAuthorization(request);
        await this.handleGetRun(response, url, runMatch[1]);
        return;
      }

      const cancelMatch = pathname.match(/^\/v1\/runs\/([^/]+)\/cancel$/);
      if (cancelMatch && method === "POST") {
        this.requireAuthorization(request);
        await this.handleCancel(request, response, cancelMatch[1]);
        return;
      }

      sendJson(response, 404, {
        schema_version: "pi-runtime.error.v1",
        error_code: "run_not_found",
        category: "input_error",
        message: "route not found",
        retryable: false,
        details: { pathname, method },
      });
    } catch (error) {
      sendError(response, 500, error);
    }
  }

  private requireAuthorization(request: IncomingMessage): void {
    if (isAuthorized(request, this.internalSecret)) return;
    throw new RuntimeContractError("permission_denied", "Pi Runtime internal authentication failed", 401);
  }

  private async readiness(): Promise<RunReadiness> {
    const executor = this.executor as Partial<ReadinessAwareRunExecutor>;
    if (typeof executor.readiness === "function") {
      return executor.readiness();
    }
    return {
      ready: false,
      provider_id: process.env.PI_PROVIDER?.trim() || DEFAULT_PROVIDER_ID,
      reason: "runtime executor does not expose a readiness probe",
    };
  }

  private async handleRun(request: IncomingMessage, response: ServerResponse, expectedKind: RunKind): Promise<void> {
    let payload: unknown;
    try {
      payload = await readBody(request);
    } catch (error) {
      sendError(response, 400, error);
      return;
    }

    let runRequest: RunRequest;
    try {
      runRequest = validateRunRequest(payload, expectedKind);
    } catch (error) {
      sendError(response, 400, error);
      return;
    }

    let created: { record: RunRecord; existing: boolean };
    try {
      created = this.registry.create(runRequest);
    } catch (error) {
      sendError(response, 409, error, runRequest.run_id, traceIdFrom(runRequest));
      return;
    }

    response.statusCode = 200;
    response.setHeader("Content-Type", "application/x-ndjson; charset=utf-8");
    response.setHeader("Cache-Control", "no-cache");
    response.setHeader("Connection", "keep-alive");

    let writtenSequence = 0;
    const writeEvent = (event: EventEnvelope): void => {
      if (event.sequence <= writtenSequence || response.writableEnded) return;
      response.write(`${json(event)}\n`);
      writtenSequence = event.sequence;
    };

    for (const event of this.registry.eventsAfter(created.record, 0)) writeEvent(event);
    if (created.existing) {
      response.end();
      return;
    }

    this.registry.start(created.record);
    writeEvent(created.record.events.at(-1)!);

    const deadlineTimer = setTimeout(() => {
      if (created.record.status === "running") {
        created.record.controller.abort(new RuntimeDeadlineError(runRequest.run_id, runRequest.deadline_ms));
      }
    }, runRequest.deadline_ms);
    try {
      const result = await this.executor.execute(
        runRequest,
        async (type, eventPayload) => {
          const event = this.registry.appendEvent(created.record, type, eventPayload);
          writeEvent(event);
        },
        created.record.controller.signal,
        createRunToolRuntime(runRequest),
      );
      if (created.record.status === "cancelled") {
        clearTimeout(deadlineTimer);
        for (const event of this.registry.eventsAfter(created.record, writtenSequence)) writeEvent(event);
        response.end();
        return;
      }
      if (created.record.controller.signal.aborted) {
        throw created.record.controller.signal.reason ?? new RuntimeDeadlineError(runRequest.run_id, runRequest.deadline_ms);
      }
      this.registry.complete(created.record, result);
      writeEvent(created.record.events.at(-1)!);
    } catch (error) {
      if (created.record.status !== "cancelled") {
        const envelope = toErrorEnvelope(error, runRequest.run_id, traceIdFrom(runRequest));
        this.registry.fail(created.record, envelope);
      }
      for (const event of this.registry.eventsAfter(created.record, writtenSequence)) writeEvent(event);
    }
    clearTimeout(deadlineTimer);
    response.end();
  }

  private async handleGetRun(response: ServerResponse, url: URL, runId: string): Promise<void> {
    const record = this.registry.get(runId);
    if (!record) {
      sendError(response, 404, new RuntimeContractError("run_not_found", `run ${runId} not found`, 404), runId);
      return;
    }
    const afterSequence = parseAfterSequence(url);
    sendJson(response, 200, {
      ...this.registry.summary(record),
      events: this.registry.eventsAfter(record, afterSequence),
    });
  }

  private async handleCancel(request: IncomingMessage, response: ServerResponse, runId: string): Promise<void> {
    let payload: unknown;
    try {
      payload = await readBody(request);
      validateCancelRequest(payload, runId);
    } catch (error) {
      sendError(response, 400, error, runId);
      return;
    }
    const record = this.registry.get(runId);
    if (!record) {
      sendError(response, 404, new RuntimeContractError("run_not_found", `run ${runId} not found`, 404), runId);
      return;
    }
    const reasonCode = String((payload as Record<string, unknown>).reason_code);
    this.registry.cancel(record, reasonCode);
    sendJson(response, 200, {
      schema_version: "pi-runtime.cancel-result.v1",
      run_id: runId,
      status: record.status,
      event_sequence: record.events.length,
    });
  }
}

export function createPiRuntimeServer(options: RuntimeOptions = {}): PiRuntimeServer {
  return new PiRuntimeServer(options);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const runtime = createPiRuntimeServer();
  runtime.listen().then(() => {
    process.stdout.write(`Pi Runtime listening on http://${runtime.host}:${runtime.port}\n`);
  }).catch((error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.stack ?? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}

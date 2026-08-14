import { randomUUID } from "node:crypto";
import type {
  EventEnvelope,
  RunRequest,
  RunResult,
  RuntimeErrorEnvelope,
  RuntimeRunStatus,
} from "../contracts.js";

export interface RunRecord {
  request: RunRequest;
  status: RuntimeRunStatus;
  events: EventEnvelope[];
  result: RunResult | null;
  error: RuntimeErrorEnvelope | null;
  controller: AbortController;
  fingerprint: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export class RunIdConflictError extends Error {
  constructor(readonly runId: string) {
    super(`run_id ${runId} already exists with different request payload`);
    this.name = "RunIdConflictError";
  }
}

function stableStringify(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(record[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function now(): string {
  return new Date().toISOString();
}

function isTerminal(status: RuntimeRunStatus): boolean {
  return status === "completed" || status === "failed" || status === "cancelled";
}

export class RunRegistry {
  private readonly runs = new Map<string, RunRecord>();

  constructor(private readonly ttlMs = 5 * 60 * 1000) {}

  create(request: RunRequest): { record: RunRecord; existing: boolean } {
    const fingerprint = stableStringify(request);
    const existing = this.runs.get(request.run_id);
    if (existing) {
      if (existing.fingerprint !== fingerprint) throw new RunIdConflictError(request.run_id);
      return { record: existing, existing: true };
    }

    const record: RunRecord = {
      request,
      status: "created",
      events: [],
      result: null,
      error: null,
      controller: new AbortController(),
      fingerprint,
      createdAt: now(),
      startedAt: null,
      finishedAt: null,
    };
    this.runs.set(request.run_id, record);
    return { record, existing: false };
  }

  get(runId: string): RunRecord | undefined {
    return this.runs.get(runId);
  }

  start(record: RunRecord): void {
    if (isTerminal(record.status)) return;
    record.status = "running";
    record.startedAt ??= now();
    this.appendEvent(record, "run.started", {
      run_kind: record.request.run_kind,
      context_manifest_id: record.request.context_manifest.context_manifest_id,
    });
  }

  appendEvent(record: RunRecord, type: EventEnvelope["type"], payload: Record<string, unknown>): EventEnvelope {
    const event: EventEnvelope = {
      schema_version: "pi-runtime.event.v1",
      event_id: `evt_${randomUUID()}`,
      run_id: record.request.run_id,
      sequence: record.events.length + 1,
      timestamp: now(),
      type,
      trace_context: record.request.trace_context,
      payload,
    };
    record.events.push(event);
    return event;
  }

  complete(record: RunRecord, result: RunResult): void {
    if (isTerminal(record.status)) return;
    record.result = result;
    record.status = "completed";
    record.finishedAt = now();
    this.appendEvent(record, "run.completed", {
      result_ref: `${record.request.run_id}:result`,
      finish_reason: "finish_reason" in result ? result.finish_reason : "completed",
    });
  }

  fail(record: RunRecord, error: RuntimeErrorEnvelope): void {
    if (isTerminal(record.status)) return;
    record.error = error;
    record.status = "failed";
    record.finishedAt = now();
    this.appendEvent(record, "run.failed", {
      error_code: error.error_code,
      retryable: error.retryable,
    });
  }

  cancel(record: RunRecord, reasonCode: string): void {
    if (isTerminal(record.status)) return;
    record.controller.abort(reasonCode);
    record.status = "cancelled";
    record.finishedAt = now();
    this.appendEvent(record, "run.cancelled", { reason_code: reasonCode });
  }

  eventsAfter(record: RunRecord, afterSequence: number): EventEnvelope[] {
    return record.events.filter((event) => event.sequence > afterSequence);
  }

  summary(record: RunRecord): Record<string, unknown> {
    return {
      schema_version: "pi-runtime.run-summary.v1",
      run_id: record.request.run_id,
      run_kind: record.request.run_kind,
      status: record.status,
      event_sequence: record.events.length,
      result: record.result,
      error: record.error,
      created_at: record.createdAt,
      started_at: record.startedAt,
      finished_at: record.finishedAt,
    };
  }

  prune(referenceTime = Date.now()): void {
    for (const [runId, record] of this.runs) {
      if (!record.finishedAt || !isTerminal(record.status)) continue;
      if (referenceTime - Date.parse(record.finishedAt) > this.ttlMs) this.runs.delete(runId);
    }
  }
}

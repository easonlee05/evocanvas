#!/usr/bin/env python3
"""为 Claude Code Harness 逆向分析生成可复核、脱敏的本地证据包。

脚本只读取明确列出的本机程序、固定公开源码快照、EvoCanvas 文件和
与本次研究直接相关的 rollout/session。它不会读取 settings、memory、
认证状态或密钥文件，也不会复制完整 Claude Code bundle 或完整私有会话。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = PACKAGE_ROOT / "evidence"
LOCAL_RUNTIME_DIR = EVIDENCE_ROOT / "local-runtime"
PUBLIC_SOURCE_DIR = EVIDENCE_ROOT / "public-source"
OFFICIAL_DOCS_DIR = EVIDENCE_ROOT / "official-docs"
SESSIONS_DIR = EVIDENCE_ROOT / "sessions"
WORKSPACE_DIR = EVIDENCE_ROOT / "workspace"

WORKSPACE_ROOT = Path("/Users/apple/Desktop/evocanvas")
CLAUDE_BIN = Path("/usr/local/bin/claude")
CLAUDE_PACKAGE_ROOT = Path("/usr/local/lib/node_modules/@anthropic-ai/claude-code")
CLAUDE_CLI = CLAUDE_PACKAGE_ROOT / "cli.js"
CLAUDE_PACKAGE_JSON = CLAUDE_PACKAGE_ROOT / "package.json"
CLAUDE_SDK_TYPES = CLAUDE_PACKAGE_ROOT / "sdk-tools.d.ts"
PUBLIC_SOURCE_ROOT = Path("/tmp/evocanvas-claude-code-2.1.88")
CLAUDE_PROJECT_DIR = Path("/Users/apple/.claude/projects/-Users-apple-Desktop-evocanvas")

CODEX_ROLLOUTS = {
    "codex-root-analysis": Path(
        "/Users/apple/.codex/sessions/2026/07/18/"
        "rollout-2026-07-18T16-15-21-019f744b-5314-7b72-b769-70a0c969636a.jsonl"
    ),
    "agent-local-forensics": Path(
        "/Users/apple/.codex/sessions/2026/07/18/"
        "rollout-2026-07-18T16-16-15-019f744c-2646-7f61-b6e2-5826279ba3d9.jsonl"
    ),
    "agent-official-research": Path(
        "/Users/apple/.codex/sessions/2026/07/18/"
        "rollout-2026-07-18T16-16-25-019f744c-4ece-7ef3-ab9b-3d07ca845279.jsonl"
    ),
    "agent-evocanvas-mapping": Path(
        "/Users/apple/.codex/sessions/2026/07/18/"
        "rollout-2026-07-18T16-16-34-019f744c-7256-70c0-afd1-e4ed5fb636a8.jsonl"
    ),
    "prior-context-convergence": Path(
        "/Users/apple/.codex/sessions/2026/07/16/"
        "rollout-2026-07-16T00-16-51-019f6691-132f-72f2-b8c5-d1b0723966cf.jsonl"
    ),
}

CLAUDE_SESSION_TO_EXTRACT = (
    CLAUDE_PROJECT_DIR / "0eef04e9-7dcc-46f3-8f0b-8833dca85fdd.jsonl"
)

OFFICIAL_URLS = [
    "https://code.claude.com/docs/en/how-claude-code-works",
    "https://code.claude.com/docs/en/agent-sdk/agent-loop",
    "https://code.claude.com/docs/en/memory",
    "https://code.claude.com/docs/en/permissions",
    "https://code.claude.com/docs/en/hooks",
    "https://code.claude.com/docs/en/sandboxing",
    "https://code.claude.com/docs/en/mcp",
    "https://code.claude.com/docs/en/sub-agents",
    "https://code.claude.com/docs/en/agent-teams",
    "https://code.claude.com/docs/en/sessions",
    "https://code.claude.com/docs/en/checkpointing",
    "https://code.claude.com/docs/en/monitoring-usage",
]

BUNDLE_SYMBOLS = [
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "PermissionRequest",
    "InstructionsLoaded",
    "PreCompact",
    "PostCompact",
    "compact_boundary",
    "autoCompact",
    "queryChainId",
    "fileCheckpointingEnabled",
    "ToolSearch",
    "SessionStart",
    "--bare",
]

PUBLIC_SOURCE_SYMBOLS = {
    "src/query.ts": ["async function* queryLoop", "autoCompactTracking"],
    "src/services/tools/toolOrchestration.ts": ["isConcurrencySafe", "partitionToolCalls"],
    "src/services/tools/toolExecution.ts": ["runPreToolUseHooks", "runPostToolUseFailureHooks"],
    "src/services/tools/toolHooks.ts": ["runPreToolUseHooks", "PermissionDecision"],
    "src/services/compact/autoCompact.ts": ["autoCompact"],
    "src/context.ts": ["getSystemContext", "getUserContext"],
}

WORKSPACE_EXCERPTS = [
    ("W-PRD-001", "docs/vision/EvoCanvas1.0-PRD.md", 16, 16, "产品定位"),
    ("W-PRD-002", "docs/vision/EvoCanvas1.0-PRD.md", 95, 107, "产品旅程与内层闭环"),
    ("W-PRD-003", "docs/vision/EvoCanvas1.0-PRD.md", 1242, 1268, "信任分级与约束候选"),
    ("W-PRD-004", "docs/vision/EvoCanvas1.0-PRD.md", 1838, 1897, "唯一状态与约束状态"),
    ("W-HARNESS-001", "docs/harness/README.md", 21, 40, "十二层 Harness 公式"),
    ("W-HARNESS-002", "docs/harness/README.md", 82, 115, "L2/L3 文档成熟度清单"),
    (
        "W-CONTEXT-001",
        "docs/harness/01-instructions-context/03 Context Assembly（上下文装配）.md",
        11,
        72,
        "四来源、预算裁剪与失败回退",
    ),
    (
        "W-TRACE-001",
        "docs/harness/06-observability/02 Trace Model（追踪模型）.md",
        11,
        83,
        "Chat 到 operation 的追踪链",
    ),
    (
        "W-STATE-001",
        "docs/harness/02-memory-state/02 State Ledger（状态账本）.md",
        69,
        116,
        "L3 对象状态与约束确认规则",
    ),
    (
        "W-GOV-001",
        "docs/harness/05-safety-governance/05 Object Governance（对象治理）.md",
        66,
        81,
        "L3 约束卡治理边界",
    ),
    ("W-CODE-001", "app/canvas/service.py", 1040, 1129, "当前 Prompt 拼接"),
    ("W-CODE-002", "app/canvas/agent/supervisor.py", 1, 5, "Supervisor 非真实 subagent 调度"),
    ("W-CODE-003", "app/canvas/agent/supervisor.py", 45, 136, "Supervisor 上下文拼接"),
    ("W-CODE-004", "app/core/tools.py", 16, 41, "ToolSpec 声明"),
    ("W-CODE-005", "app/core/tools.py", 99, 152, "ToolPolicy 与审批字段"),
    ("W-CODE-006", "app/services/tool_service.py", 194, 240, "当前工具执行链"),
    ("W-CODE-007", "app/services/agent_runtime/runtime.py", 48, 180, "有界 AgentRuntime"),
    ("W-CODE-008", "app/services/subagent_service.py", 33, 46, "Subagent 限额"),
    ("W-CODE-009", "app/services/subagent_service.py", 87, 199, "隔离运行与有界并发"),
    ("W-CODE-010", "app/canvas/repository.py", 267, 321, "包版本提交顺序"),
    ("W-CODE-011", "app/canvas/service.py", 178, 390, "当前同步 start_turn 主链"),
    ("W-CODE-012", "app/canvas/service.py", 1543, 1637, "当前确认识别与记录"),
    ("W-CODE-013", "app/workflows/canvas_session.py", 1, 89, "Canvas workflow 仍为 definition_only"),
    ("W-CODE-014", "app/canvas/domain/snapshots.py", 1, 62, "当前 CanvasSnapshot 副本结构"),
]

SECRET_KEY_RE = re.compile(
    r"(?i)(api[_-]?key|authorization|access[_-]?token|refresh[_-]?token|password|secret)"
)
SECRET_VALUE_PATTERNS = [
    re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(
        r"(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]\s*)"
        r"([^\s,;}\]]{8,})"
    ),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ensure_dirs() -> None:
    for path in (
        LOCAL_RUNTIME_DIR,
        PUBLIC_SOURCE_DIR,
        OFFICIAL_DOCS_DIR,
        SESSIONS_DIR,
        WORKSPACE_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(payload: str) -> str:
    return sha256_bytes(payload.encode("utf-8", errors="replace"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_command(args: list[str]) -> dict[str, Any]:
    env = dict(os.environ)
    env["NO_COLOR"] = "1"
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        return {
            "command": args,
            "exit_code": completed.returncode,
            "stdout": scrub_text(completed.stdout),
            "stderr": scrub_text(completed.stderr),
        }
    except Exception as exc:  # pragma: no cover - environment dependent
        return {"command": args, "error": str(exc)}


def scrub_text(text: str, max_chars: Optional[int] = None) -> str:
    value = text
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.groups >= 2:
            value = pattern.sub(r"\1[REDACTED]", value)
        else:
            value = pattern.sub("[REDACTED]", value)
    if max_chars is not None and len(value) > max_chars:
        digest = sha256_text(value)
        value = (
            value[:max_chars]
            + f"\n[TRUNCATED original_chars={len(value)} sha256={digest}]"
        )
    return value


def sanitize_value(value: Any, *, max_string: int = 12_000, key: str = "") -> Any:
    if SECRET_KEY_RE.search(key):
        return "[REDACTED]"
    if isinstance(value, str):
        return scrub_text(value, max_string)
    if isinstance(value, list):
        return [sanitize_value(item, max_string=max_string) for item in value]
    if isinstance(value, dict):
        return {
            str(item_key): sanitize_value(
                item_value,
                max_string=max_string,
                key=str(item_key),
            )
            for item_key, item_value in value.items()
        }
    return value


def file_fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "size_bytes": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).astimezone().isoformat(),
        "sha256": sha256_file(path),
    }


def capture_local_runtime() -> None:
    commands = {
        "claude-version.json": [str(CLAUDE_BIN), "--version"],
        "claude-help.json": [str(CLAUDE_BIN), "--help"],
        "claude-agents-help.json": [str(CLAUDE_BIN), "agents", "--help"],
        "claude-mcp-help.json": [str(CLAUDE_BIN), "mcp", "--help"],
        "claude-auto-mode-help.json": [str(CLAUDE_BIN), "auto-mode", "--help"],
    }
    for filename, args in commands.items():
        write_json(LOCAL_RUNTIME_DIR / filename, run_command(args))

    package_metadata: dict[str, Any] = {}
    if CLAUDE_PACKAGE_JSON.exists():
        raw = json.loads(CLAUDE_PACKAGE_JSON.read_text(encoding="utf-8"))
        for field in ("name", "version", "type", "bin", "engines", "files"):
            package_metadata[field] = raw.get(field)
    write_json(LOCAL_RUNTIME_DIR / "package-metadata.json", package_metadata)

    runtime_manifest: dict[str, Any] = {
        "captured_at": now_iso(),
        "entrypoint": str(CLAUDE_BIN),
        "entrypoint_symlink_target": os.readlink(CLAUDE_BIN) if CLAUDE_BIN.is_symlink() else None,
        "files": [],
        "scope_note": "Only fingerprints are stored; the full proprietary bundle is not copied.",
    }
    for path in (CLAUDE_CLI, CLAUDE_PACKAGE_JSON, CLAUDE_SDK_TYPES):
        if path.exists():
            runtime_manifest["files"].append(file_fingerprint(path))
    write_json(LOCAL_RUNTIME_DIR / "local-runtime-manifest.json", runtime_manifest)

    if CLAUDE_CLI.exists():
        bundle = CLAUDE_CLI.read_text(encoding="utf-8", errors="replace")
        symbol_evidence = {
            "source_path": str(CLAUDE_CLI),
            "source_sha256": sha256_file(CLAUDE_CLI),
            "note": "Counts only prove symbol presence in the checked bundle, not public API stability.",
            "symbols": {symbol: bundle.count(symbol) for symbol in BUNDLE_SYMBOLS},
        }
        write_json(LOCAL_RUNTIME_DIR / "bundle-symbol-evidence.json", symbol_evidence)


def git_output(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", "-C", str(PUBLIC_SOURCE_ROOT), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return completed.stdout.strip()


def capture_public_source() -> None:
    if not (PUBLIC_SOURCE_ROOT / ".git").exists():
        write_json(
            PUBLIC_SOURCE_DIR / "source-snapshot-manifest.json",
            {
                "captured_at": now_iso(),
                "available": False,
                "expected_path": str(PUBLIC_SOURCE_ROOT),
                "note": "Run the reproduction command in 02-reproduction.md, then rerun this collector.",
            },
        )
        return

    source_files = sorted(
        path for path in PUBLIC_SOURCE_ROOT.rglob("*") if path.is_file() and ".git" not in path.parts
    )
    manifest: dict[str, Any] = {
        "captured_at": now_iso(),
        "available": True,
        "local_path": str(PUBLIC_SOURCE_ROOT),
        "remote": git_output(["remote", "get-url", "origin"]),
        "commit": git_output(["rev-parse", "HEAD"]),
        "commit_date": git_output(["log", "-1", "--format=%cI"]),
        "commit_subject": git_output(["log", "-1", "--format=%s"]),
        "file_count": len(source_files),
        "classification": "unofficial_source_map_extraction",
        "trust_note": "Structural navigation only; not treated as current official source.",
        "selected_files": [],
    }
    for relative in PUBLIC_SOURCE_SYMBOLS:
        path = PUBLIC_SOURCE_ROOT / relative
        if path.exists():
            manifest["selected_files"].append(
                {
                    **file_fingerprint(path),
                    "relative_path": relative,
                    "line_count": sum(1 for _ in path.open(encoding="utf-8", errors="replace")),
                }
            )
    write_json(PUBLIC_SOURCE_DIR / "source-snapshot-manifest.json", manifest)

    symbol_index: list[dict[str, Any]] = []
    for relative, symbols in PUBLIC_SOURCE_SYMBOLS.items():
        path = PUBLIC_SOURCE_ROOT / relative
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for symbol in symbols:
            matches = [index for index, line in enumerate(lines, start=1) if symbol in line]
            symbol_index.append(
                {
                    "path": relative,
                    "symbol": symbol,
                    "line_numbers": matches[:50],
                    "match_count": len(matches),
                    "file_sha256": sha256_file(path),
                }
            )
    write_json(PUBLIC_SOURCE_DIR / "source-symbol-index.json", symbol_index)

    top_level = sorted(path.name for path in (PUBLIC_SOURCE_ROOT / "src").iterdir())
    write_text(PUBLIC_SOURCE_DIR / "source-tree.txt", "\n".join(top_level))


def capture_official_docs() -> None:
    records: list[dict[str, Any]] = []
    for url in OFFICIAL_URLS:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "EvoCanvas-Harness-Forensics/1.0"},
        )
        record: dict[str, Any] = {"url": url, "checked_at": now_iso()}
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                prefix = response.read(65_536)
                record.update(
                    {
                        "status": getattr(response, "status", None),
                        "final_url": response.geturl(),
                        "content_type": response.headers.get("Content-Type"),
                        "etag": response.headers.get("ETag"),
                        "last_modified": response.headers.get("Last-Modified"),
                        "content_length_header": response.headers.get("Content-Length"),
                        "first_65536_bytes_sha256": sha256_bytes(prefix),
                    }
                )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            record["error"] = str(exc)
        records.append(record)
    write_json(OFFICIAL_DOCS_DIR / "official-docs-manifest.json", records)


def sanitize_claude_block(block: Any) -> Any:
    if not isinstance(block, dict):
        return sanitize_value(block, max_string=4_000)
    block_type = str(block.get("type") or "unknown")
    if block_type in {"thinking", "redacted_thinking"}:
        raw = json.dumps(block, ensure_ascii=False, default=str)
        return {
            "type": block_type,
            "content": "[REDACTED_REASONING]",
            "original_sha256": sha256_text(raw),
        }
    if block_type in {"image", "document"}:
        raw = json.dumps(block, ensure_ascii=False, default=str)
        return {
            "type": block_type,
            "content": "[REDACTED_BINARY_OR_DOCUMENT]",
            "original_sha256": sha256_text(raw),
        }
    if block_type == "text":
        text = str(block.get("text") or "")
        if "<system-reminder>" in text or "<system-reminder" in text:
            return {
                "type": "text",
                "text": "[REDACTED_AMBIENT_SYSTEM_REMINDER]",
                "original_chars": len(text),
                "original_sha256": sha256_text(text),
            }
        return {"type": "text", "text": scrub_text(text, 8_000)}
    if block_type == "tool_result":
        content = block.get("content")
        raw = json.dumps(content, ensure_ascii=False, default=str)
        return {
            "type": "tool_result",
            "tool_use_id": block.get("tool_use_id"),
            "is_error": block.get("is_error", False),
            "content": sanitize_value(content, max_string=6_000),
            "original_content_sha256": sha256_text(raw),
        }
    return sanitize_value(block, max_string=8_000)


def sanitize_claude_message(message: Any) -> Any:
    if not isinstance(message, dict):
        return sanitize_value(message, max_string=8_000)
    result: dict[str, Any] = {}
    for key in ("role", "model", "id", "type", "stop_reason", "stop_sequence", "usage"):
        if key in message:
            result[key] = sanitize_value(message[key], max_string=2_000, key=key)
    content = message.get("content")
    if isinstance(content, str):
        result["content"] = scrub_text(content, 10_000)
    elif isinstance(content, list):
        result["content"] = [sanitize_claude_block(block) for block in content]
    elif content is not None:
        result["content"] = sanitize_value(content, max_string=8_000)
    return result


def sanitize_claude_session(source: Path, destination: Path) -> dict[str, Any]:
    type_counts: Counter[str] = Counter()
    written = 0
    with source.open(encoding="utf-8", errors="replace") as input_handle, destination.open(
        "w", encoding="utf-8"
    ) as output_handle:
        for line_number, line in enumerate(input_handle, start=1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            item_type = str(item.get("type") or "unknown")
            type_counts[item_type] += 1
            record: dict[str, Any] = {
                "_source_line": line_number,
                "type": item_type,
            }
            for key in (
                "uuid",
                "parentUuid",
                "sessionId",
                "isSidechain",
                "userType",
                "cwd",
                "version",
                "gitBranch",
                "timestamp",
                "subtype",
                "slug",
            ):
                if key in item:
                    record[key] = sanitize_value(item[key], max_string=1_000, key=key)

            if item_type in {"user", "assistant"}:
                record["message"] = sanitize_claude_message(item.get("message"))
            elif item_type == "summary":
                summary = str(item.get("summary") or "")
                record.update(
                    {
                        "summary": scrub_text(summary, 2_000),
                        "original_summary_chars": len(summary),
                        "original_summary_sha256": sha256_text(summary),
                    }
                )
            elif item_type == "system":
                for key in ("level", "durationMs", "compactMetadata", "toolUseID"):
                    if key in item:
                        record[key] = sanitize_value(item[key], max_string=2_000, key=key)
                if "content" in item:
                    content = str(item.get("content") or "")
                    record["content_sha256"] = sha256_text(content)
                    record["content_chars"] = len(content)
            elif item_type in {"file-history-snapshot", "queue-operation", "result"}:
                for key, value in item.items():
                    if key in record or key in {"message", "content"}:
                        continue
                    record[key] = sanitize_value(value, max_string=2_000, key=key)
            else:
                # Unknown/progress records retain only non-content metadata.
                for key in ("status", "name", "toolUseID", "parentToolUseID", "agentId"):
                    if key in item:
                        record[key] = sanitize_value(item[key], max_string=1_000, key=key)

            output_handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            written += 1
    return {
        "source": file_fingerprint(source),
        "output": file_fingerprint(destination),
        "records_written": written,
        "source_type_counts": dict(sorted(type_counts.items())),
        "sanitization": [
            "reasoning blocks replaced by hashes",
            "ambient system-reminder text removed",
            "binary/document blocks removed",
            "credential-looking values redacted",
            "long strings truncated with original hashes",
        ],
    }


def sanitize_codex_rollout(
    source: Path,
    destination: Path,
    *,
    max_source_line: Optional[int] = None,
) -> dict[str, Any]:
    type_counts: Counter[str] = Counter()
    written = 0
    skipped = 0
    with source.open(encoding="utf-8", errors="replace") as input_handle, destination.open(
        "w", encoding="utf-8"
    ) as output_handle:
        for line_number, line in enumerate(input_handle, start=1):
            if max_source_line is not None and line_number > max_source_line:
                break
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            item_type = str(item.get("type") or "unknown")
            type_counts[item_type] += 1
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            record: Optional[dict[str, Any]] = None

            if item_type == "session_meta":
                record = {
                    "_source_line": line_number,
                    "type": item_type,
                    "id": payload.get("id"),
                    "timestamp": payload.get("timestamp"),
                    "cwd": payload.get("cwd"),
                    "source": payload.get("source"),
                }
            elif item_type == "turn_context":
                record = {
                    "_source_line": line_number,
                    "type": item_type,
                    "turn_id": payload.get("turn_id"),
                    "cwd": payload.get("cwd"),
                }
            elif item_type == "response_item":
                response_type = str(payload.get("type") or "unknown")
                role = payload.get("role")
                if response_type == "reasoning" or role in {"developer", "system"}:
                    skipped += 1
                    continue
                record = {
                    "_source_line": line_number,
                    "type": item_type,
                    "response_type": response_type,
                    "role": role,
                    "name": payload.get("name"),
                    "call_id": payload.get("call_id"),
                }
                for key in ("content", "arguments", "input", "output"):
                    if key in payload:
                        raw = payload[key]
                        raw_text = json.dumps(raw, ensure_ascii=False, default=str)
                        if response_type == "custom_tool_call_output" and key == "output":
                            # Shell/web outputs can contain long source or webpage excerpts.
                            # Preserve provenance and a short orientation preview, not the body.
                            record["output_chars"] = len(raw_text)
                            record["output_preview"] = scrub_text(raw_text, 600)
                        else:
                            max_string = 4_000 if response_type == "custom_tool_call" else 16_000
                            record[key] = sanitize_value(raw, max_string=max_string, key=key)
                        record[f"{key}_sha256"] = sha256_text(raw_text)
            elif item_type == "event_msg":
                event_type = str(payload.get("type") or "unknown")
                if event_type not in {
                    "task_started",
                    "task_complete",
                    "user_message",
                    "agent_message",
                    "sub_agent_activity",
                    "web_search_end",
                }:
                    skipped += 1
                    continue
                record = {
                    "_source_line": line_number,
                    "type": item_type,
                    "event_type": event_type,
                }
            elif item_type == "compacted":
                raw = json.dumps(payload, ensure_ascii=False, default=str)
                record = {
                    "_source_line": line_number,
                    "type": item_type,
                    "payload_sha256": sha256_text(raw),
                    "payload_chars": len(raw),
                }
            else:
                skipped += 1
                continue

            output_handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            written += 1

    return {
        "source": file_fingerprint(source),
        "output": file_fingerprint(destination),
        "records_written": written,
        "records_skipped": skipped,
        "source_line_cutoff": max_source_line,
        "source_type_counts": dict(sorted(type_counts.items())),
        "sanitization": [
            "developer/system messages excluded",
            "reasoning and token accounting excluded",
            "credential-looking values redacted",
            "shell/web tool outputs reduced to short previews with original hashes",
            "other long structured results truncated with original hashes",
        ],
    }


def capture_sessions() -> None:
    inventory: list[dict[str, Any]] = []
    if CLAUDE_PROJECT_DIR.exists():
        for path in sorted(CLAUDE_PROJECT_DIR.glob("*.jsonl")):
            metadata: dict[str, Any] = {
                "session_id": None,
                "cwd": None,
                "version": None,
                "git_branch": None,
                "timestamp": None,
                "is_sidechain": None,
            }
            type_counts: Counter[str] = Counter()
            with path.open(encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    type_counts[str(item.get("type") or "unknown")] += 1
                    candidates = {
                        "session_id": item.get("sessionId"),
                        "cwd": item.get("cwd"),
                        "version": item.get("version"),
                        "git_branch": item.get("gitBranch"),
                        "timestamp": item.get("timestamp"),
                        "is_sidechain": item.get("isSidechain"),
                    }
                    for key, value in candidates.items():
                        if metadata.get(key) is None and value is not None:
                            metadata[key] = value
            inventory.append(
                {
                    **file_fingerprint(path),
                    "metadata": metadata,
                    "type_counts": dict(sorted(type_counts.items())),
                    "content_copied": path == CLAUDE_SESSION_TO_EXTRACT,
                }
            )
    write_json(SESSIONS_DIR / "claude-session-inventory.json", inventory)

    session_manifests: list[dict[str, Any]] = []
    if CLAUDE_SESSION_TO_EXTRACT.exists():
        output = SESSIONS_DIR / "claude-evocanvas-harness-session.sanitized.jsonl"
        session_manifests.append(sanitize_claude_session(CLAUDE_SESSION_TO_EXTRACT, output))

    for name, source in CODEX_ROLLOUTS.items():
        if not source.exists():
            session_manifests.append({"name": name, "missing_source": str(source)})
            continue
        output = SESSIONS_DIR / f"{name}.sanitized.jsonl"
        # 主 rollout 在第 408 行进入“生成证据包”的下一轮；本文件只保存
        # 前一轮 Claude Code Harness 分析本身，避免证据包递归收录自身。
        max_source_line = 407 if name == "codex-root-analysis" else None
        manifest = sanitize_codex_rollout(
            source,
            output,
            max_source_line=max_source_line,
        )
        manifest["name"] = name
        session_manifests.append(manifest)

    write_json(SESSIONS_DIR / "sanitized-session-manifest.json", session_manifests)


def numbered_excerpt(path: Path, start: int, end: int) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    selected = lines[start - 1 : end]
    width = len(str(end))
    return "\n".join(
        f"{line_number:>{width}} | {line}"
        for line_number, line in enumerate(selected, start=start)
    )


def capture_workspace() -> None:
    chunks = [
        "# EvoCanvas 工作区证据摘录",
        "",
        f"> 生成时间：{now_iso()}",
        "> 摘录保留原始行号；完整文件仍以仓库当前内容为准。",
        "",
    ]
    index: list[dict[str, Any]] = []
    for evidence_id, relative, start, end, claim in WORKSPACE_EXCERPTS:
        path = WORKSPACE_ROOT / relative
        if not path.exists():
            index.append({"id": evidence_id, "path": relative, "missing": True})
            continue
        chunks.extend(
            [
                f"## {evidence_id} — {claim}",
                "",
                f"来源：`{relative}:{start}-{end}`",
                "",
                "```text",
                numbered_excerpt(path, start, end),
                "```",
                "",
            ]
        )
        index.append(
            {
                "id": evidence_id,
                "claim": claim,
                "path": relative,
                "line_start": start,
                "line_end": end,
                "file_sha256": sha256_file(path),
            }
        )
    write_text(WORKSPACE_DIR / "workspace-excerpts.md", "\n".join(chunks))
    write_json(WORKSPACE_DIR / "workspace-evidence-index.json", index)

    maturity_lines: list[str] = []
    for directory in (
        "docs/harness/01-instructions-context",
        "docs/harness/05-safety-governance",
        "docs/harness/06-observability",
        "docs/harness/08-evaluation",
    ):
        for path in sorted((WORKSPACE_ROOT / directory).glob("*.md")):
            first_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[:6]
            maturity = next((line.strip() for line in first_lines if "当前成熟度层级" in line), "未标注")
            maturity_lines.append(f"{path.relative_to(WORKSPACE_ROOT)} | {maturity}")
    write_text(WORKSPACE_DIR / "harness-maturity-scan.txt", "\n".join(maturity_lines))


def finalize_manifest() -> None:
    excluded = {"MANIFEST.json", "SHA256SUMS"}
    entries: list[dict[str, Any]] = []
    for path in sorted(PACKAGE_ROOT.rglob("*")):
        if not path.is_file() or path.name in excluded:
            continue
        relative = path.relative_to(PACKAGE_ROOT).as_posix()
        entries.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    write_text(
        PACKAGE_ROOT / "SHA256SUMS",
        "\n".join(f"{entry['sha256']}  {entry['path']}" for entry in entries),
    )
    write_json(
        PACKAGE_ROOT / "MANIFEST.json",
        {
            "generated_at": now_iso(),
            "package": PACKAGE_ROOT.name,
            "workspace": str(WORKSPACE_ROOT),
            "privacy": {
                "raw_sessions_copied": False,
                "settings_or_credentials_read": False,
                "reasoning_copied": False,
                "sanitized_session_extracts": True,
            },
            "files": entries,
        },
    )


def main() -> None:
    ensure_dirs()
    capture_local_runtime()
    capture_public_source()
    capture_official_docs()
    capture_sessions()
    capture_workspace()
    finalize_manifest()


if __name__ == "__main__":
    main()

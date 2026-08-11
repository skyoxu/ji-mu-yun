#!/usr/bin/env python
"""Validate a model-visible tool round summary under Accepted ADR-0038."""

from __future__ import annotations

import argparse
import codecs
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from skill_input_consumption import (
    API_KEY_PATTERN,
    BEARER_PATTERN,
    COMMON_TOKEN_PATTERN,
    PRIVATE_KEY_PATTERN,
    SECRET_PATTERN,
    is_reparse_point,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "scripts" / "sc" / "schemas" / "model-visible-tool-round-summary.v1.schema.json"
PREFLIGHT_SCHEMA_PATH = ROOT / "scripts" / "sc" / "schemas" / "model-visible-tool-preflight.v1.schema.json"
MEASUREMENT_SCHEMA_PATH = ROOT / "scripts" / "sc" / "schemas" / "model-visible-tool-measurement.v1.schema.json"
MAX_BYTES = 12000
MAX_ESTIMATED_TOKENS = 3000
REGISTERED_OBSERVED_BOUNDARIES: frozenset[str] = frozenset()
# No workspace-authored sidecar is a trust root. A control-plane adapter must be
# explicitly registered here before repository-scope parallelization can be enabled.
REGISTERED_PREFLIGHT_ADAPTERS: frozenset[str] = frozenset()
REGISTERED_BACKGROUND_ADAPTERS: frozenset[str] = frozenset()

try:
    import jsonschema  # type: ignore
except ImportError:  # pragma: no cover
    jsonschema = None


class ToolRoundSummaryValidationError(ValueError):
    """Raised when a tool round summary is not safe to consume."""


def _reject_duplicate_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON members so consumers cannot disagree on last-wins data."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ToolRoundSummaryValidationError("duplicate JSON object member")
        result[key] = value
    return result


EXTENDED_TOKEN_PATTERNS = (
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\b(?:mongodb|postgres(?:ql)?|mysql)://[^\s\"']+:[^\s\"']+@[^\s\"']+"),
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
)
GENERIC_SECRET_PATTERN = re.compile(
    r"(?i)(token|secret|password|api[_-]?key|authorization)\s*[\"']?\s*[:=]\s*[\"']?(?!<redacted(?:-(?:private-key|api-key|token))?>)(?:\"[^\"\r\n]+\"|'[^'\r\n]+'|[^\s,;\"']+)"
)
SECRET_PATTERNS = (GENERIC_SECRET_PATTERN, BEARER_PATTERN, API_KEY_PATTERN, PRIVATE_KEY_PATTERN, COMMON_TOKEN_PATTERN) + EXTENDED_TOKEN_PATTERNS
ABSOLUTE_PATH_PATTERN = re.compile(r"(?i)(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|\\\\)[^\s\"']+")
POSIX_PATH_PATTERN = re.compile(r"(?<![A-Za-z0-9])/(?!/)[^\s\"']+")
REDACTED_VALUE_PATTERN = re.compile(r"(?i)<redacted(?:-(?:private-key|api-key|token))?>")
PRIVATE_KEY_HEADER_PATTERN = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")


def _reject_reparse_components(path: Path, *, stop: Path | None = None) -> None:
    """Reject links/reparse points before any path resolution follows them."""
    _reject_ads_components(path)
    current = path.absolute()
    boundary = stop.absolute() if stop is not None else None
    while True:
        if is_reparse_point(current):
            raise ToolRoundSummaryValidationError("workspace path may not contain a symlink or reparse point")
        if boundary is not None and current == boundary:
            return
        if current.parent == current:
            return
        current = current.parent


def _reject_ads_components(path: Path) -> None:
    """Reject Windows alternate-data-stream syntax from workspace members."""
    for part in path.parts:
        if ":" in part and not re.fullmatch(r"[A-Za-z]:[\\/]*", part):
            raise ToolRoundSummaryValidationError("workspace path may not contain an alternate data stream")


def _safe_workspace_root(root: Path) -> Path:
    candidate = root.absolute()
    if not candidate.exists() or not candidate.is_dir():
        raise ToolRoundSummaryValidationError("workspace root must be an existing directory")
    _reject_reparse_components(candidate)
    resolved = candidate.resolve()
    if is_reparse_point(resolved):
        raise ToolRoundSummaryValidationError("workspace root may not be a symlink or reparse point")
    return resolved


def _load_json(path: Path, *, label: str = "input") -> Any:
    """Load JSON without echoing a host path in an error message."""
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_json_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ToolRoundSummaryValidationError(f"invalid JSON {label} ({path.name}): {type(exc).__name__}") from exc


def _sha256_file(path: Path) -> str:
    """Hash a file incrementally so large evidence never enters memory at once."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _serialized_size(payload: dict[str, Any]) -> int:
    return len((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _walk_strings(value: Any, path: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, str):
        found.append((path, value))
    elif isinstance(value, dict):
        for key, item in value.items():
            found.extend(_walk_strings(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_walk_strings(item, f"{path}[{index}]"))
    return found


def _contains_secret(value: str) -> bool:
    # Redacted placeholders are intentionally safe and must not match the
    # shared key/value pattern again.
    candidate = REDACTED_VALUE_PATTERN.sub("", value)
    return bool(PRIVATE_KEY_HEADER_PATTERN.search(candidate)) or any(pattern.search(candidate) for pattern in SECRET_PATTERNS)


def _contains_absolute_path(value: str) -> bool:
    return bool(ABSOLUTE_PATH_PATTERN.search(value) or POSIX_PATH_PATTERN.search(value))


def _redact_diagnostic(value: str) -> str:
    """Keep validator diagnostics useful without returning host paths or credentials."""
    value = re.sub(r"(?i)[A-Za-z]:[\\/][^\n'\";]+", "<path>", value)
    value = re.sub(r"\\\\[^\n'\";]+", "<path>", value)
    value = PRIVATE_KEY_PATTERN.sub("<redacted-private-key>", value)
    value = BEARER_PATTERN.sub("Bearer <redacted>", value)
    value = API_KEY_PATTERN.sub("<redacted-api-key>", value)
    value = COMMON_TOKEN_PATTERN.sub("<redacted-token>", value)
    for pattern in EXTENDED_TOKEN_PATTERNS:
        value = pattern.sub("<redacted-token>", value)
    value = SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=<redacted>", value)
    return value


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _unsafe_relative_ref(value: str) -> bool:
    if "\\" in value:
        return True
    normalized = value.replace("\\", "/")
    return (
        not value
        or normalized.startswith("/")
        or bool(re.match(r"^[A-Za-z]:", normalized))
        or "://" in normalized
        or any(part == ".." for part in normalized.split("/"))
    )


def _unsafe_workspace_member_ref(value: str) -> bool:
    """Apply relative-reference rules plus a Windows ADS member check."""
    if _unsafe_relative_ref(value):
        return True
    return any(":" in part for part in value.replace("\\", "/").split("/"))


def _resolve_evidence_path(root: Path, relative_path: str) -> Path | None:
    if _unsafe_workspace_member_ref(relative_path):
        return None
    try:
        root_resolved = _safe_workspace_root(root)
        candidate = root_resolved.joinpath(*relative_path.replace("\\", "/").split("/"))
        _reject_reparse_components(candidate, stop=root_resolved)
        if is_reparse_point(candidate):
            return None
        candidate = candidate.resolve()
    except ToolRoundSummaryValidationError:
        return None
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None
    if is_reparse_point(candidate):
        return None
    return candidate


def _resolve_summary_input(root: Path, path: Path) -> Path:
    resolved_root = _safe_workspace_root(root)
    raw_candidate = path if path.is_absolute() else (resolved_root / path)
    _reject_reparse_components(raw_candidate, stop=resolved_root)
    if is_reparse_point(raw_candidate):
        raise ToolRoundSummaryValidationError("summary path may not be a symlink or reparse point")
    candidate = raw_candidate.resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ToolRoundSummaryValidationError("summary path must be inside the workspace root") from exc
    return candidate


def _schema_validation_errors(payload: Any, schema_path: Path) -> list[str]:
    if jsonschema is None:
        return []
    schema = _load_json(schema_path, label="schema")
    return [_redact_diagnostic(error.message) for error in sorted(jsonschema.Draft202012Validator(schema).iter_errors(payload), key=lambda item: list(item.path))]


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def retry_count(attempts: Any) -> int:
    """Return a non-negative retry count for both executed and blocked calls."""
    attempt_count = int(attempts)
    return max(attempt_count - 1, 0)


def operation_manifest_hash(operations: list[dict[str, Any]]) -> str:
    """Hash the preflight-relevant operation intent in a stable representation."""
    fields = (
        "operation_id", "tool_call_id", "parent_tool_call_id", "round_id", "scope",
        "tool_family", "access_mode", "execution_mode", "group_id",
    )
    manifest = [
        {field: operation.get(field) for field in fields}
        for operation in sorted(operations, key=lambda item: str(item.get("operation_id", "")))
    ]
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _file_safety_scan(path: Path, *, text_kind: bool) -> str | None:
    """Scan evidence incrementally; return a diagnostic code, or None when safe."""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="strict" if text_kind else "ignore")
    overlap = ""
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(64 * 1024), b""):
                try:
                    text = decoder.decode(chunk, final=False)
                except UnicodeDecodeError:
                    return "evidence is not valid UTF-8"
                sample = overlap + text
                if text_kind and any(ord(character) < 32 and character not in "\t\r\n" for character in sample):
                    return "evidence contains unsupported text control characters"
                if _contains_secret(sample):
                    return "evidence contains an unredacted credential"
                overlap = sample[-2048:]
            try:
                tail = decoder.decode(b"", final=True)
            except UnicodeDecodeError:
                return "evidence is not valid UTF-8"
            if text_kind and any(ord(character) < 32 and character not in "\t\r\n" for character in overlap + tail):
                return "evidence contains unsupported text control characters"
            if _contains_secret(overlap + tail):
                return "evidence contains an unredacted credential"
    except OSError:
        return "evidence file cannot be scanned"
    return None


def _manual_schema_errors(payload: dict[str, Any]) -> list[str]:
    """Small dependency-free structural gate used when jsonschema is unavailable."""
    errors: list[str] = []
    top_required = {
        "schema_version", "status", "run_id", "turn_id", "scope", "timing", "measurement", "metrics",
        "preflight", "round_events", "operations", "continuation", "evidence_refs", "external_boundaries", "errors",
    }
    top_allowed = top_required | {"parent_turn_id"}
    for name in sorted(top_required - payload.keys()):
        errors.append(f"$:{name} is required")
    for name in sorted(set(payload) - top_allowed):
        errors.append(f"$:{name} is not allowed")
    if payload.get("schema_version") != "model-visible-tool-round-summary.v1":
        errors.append("$.schema_version: invalid value")
    if payload.get("status") not in {"complete", "partial", "failed", "interrupted", "blocked"}:
        errors.append("$.status: invalid value")
    identifier = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
    for field in ("run_id", "turn_id"):
        if not isinstance(payload.get(field), str) or not identifier.fullmatch(payload[field]):
            errors.append(f"$.{field}: invalid identifier")
    if payload.get("parent_turn_id") is not None and (not isinstance(payload.get("parent_turn_id"), str) or not identifier.fullmatch(payload["parent_turn_id"])):
        errors.append("$.parent_turn_id: invalid identifier")

    scope = payload.get("scope")
    if not isinstance(scope, dict):
        errors.append("$.scope: expected an object")
    else:
        if set(scope) != {"scope_kind", "scope_ref"}:
            errors.append("$.scope: invalid fields")
        if scope.get("scope_kind") not in {"repository", "phase", "project", "workspace"}:
            errors.append("$.scope.scope_kind: invalid value")
        if not isinstance(scope.get("scope_ref"), str) or len(scope.get("scope_ref", "")) > 256 or "\r" in scope.get("scope_ref", "") or "\n" in scope.get("scope_ref", "") or _unsafe_relative_ref(scope.get("scope_ref", "")):
            errors.append("$.scope.scope_ref: invalid workspace-relative reference")

    timing = payload.get("timing")
    if not isinstance(timing, dict) or set(timing) != {"started_at", "finished_at"} or any(not isinstance(timing.get(key), str) or not timing.get(key) for key in ("started_at", "finished_at")):
        errors.append("$.timing: invalid fields")

    measurement = payload.get("measurement")
    if not isinstance(measurement, dict) or set(measurement) != {"rounds", "tokens", "rounds_evidence_ref", "tokens_evidence_ref"}:
        errors.append("$.measurement: invalid fields")
    else:
        if measurement.get("rounds") not in {"observed", "estimated", "unknown"}:
            errors.append("$.measurement.rounds: invalid value")
        if measurement.get("tokens") not in {"observed", "estimated", "unknown"}:
            errors.append("$.measurement.tokens: invalid value")
        for field in ("rounds_evidence_ref", "tokens_evidence_ref"):
            if measurement.get(field) is not None and (not isinstance(measurement.get(field), str) or len(measurement[field]) > 128):
                errors.append(f"$.measurement.{field}: invalid reference")

    metrics = payload.get("metrics")
    metric_names = {
        "model_visible_rounds", "underlying_tool_calls", "parallel_groups", "sequential_calls", "background_calls", "retries",
        "visible_result_bytes", "visible_result_tokens", "persisted_output_bytes", "partial_results", "failed_calls",
        "interrupted_calls", "blocked_calls",
    }
    if not isinstance(metrics, dict) or set(metrics) != metric_names:
        errors.append("$.metrics: invalid fields")
    elif any(not _is_int(metrics.get(name)) or metrics[name] < 0 for name in metric_names) or metrics.get("visible_result_bytes", 0) > MAX_BYTES:
        errors.append("$.metrics: invalid numeric value")

    preflight = payload.get("preflight")
    preflight_names = {"same_scope_verified", "authorization_verified", "secret_redaction_verified", "parallelization_allowed", "block_reason", "evidence_ref"}
    if not isinstance(preflight, dict) or set(preflight) != preflight_names:
        errors.append("$.preflight: invalid fields")
    elif any(not isinstance(preflight.get(name), bool) for name in ("same_scope_verified", "authorization_verified", "secret_redaction_verified", "parallelization_allowed")):
        errors.append("$.preflight: boolean checks are required")
    elif preflight.get("block_reason") is not None and (not isinstance(preflight.get("block_reason"), str) or len(preflight["block_reason"]) > 240):
        errors.append("$.preflight.block_reason: invalid value")
    elif preflight.get("evidence_ref") is not None and (not isinstance(preflight.get("evidence_ref"), str) or len(preflight["evidence_ref"]) > 128):
        errors.append("$.preflight.evidence_ref: invalid reference")

    round_events = payload.get("round_events")
    if not isinstance(round_events, list) or len(round_events) > 64:
        errors.append("$.round_events: expected at most 64 objects")
    else:
        for index, event in enumerate(round_events):
            if not isinstance(event, dict) or set(event) != {"round_id", "turn_id", "result_blocks", "observed"}:
                errors.append(f"$.round_events[{index}]: invalid fields")
                continue
            if not isinstance(event.get("round_id"), str) or not identifier.fullmatch(event["round_id"]):
                errors.append(f"$.round_events[{index}].round_id: invalid identifier")
            if not isinstance(event.get("turn_id"), str) or not identifier.fullmatch(event["turn_id"]):
                errors.append(f"$.round_events[{index}].turn_id: invalid identifier")
            if not _is_int(event.get("result_blocks")) or event["result_blocks"] < 1 or not isinstance(event.get("observed"), bool):
                errors.append(f"$.round_events[{index}]: invalid result metadata")

    operations = payload.get("operations")
    operation_names = {
        "operation_id", "tool_call_id", "parent_tool_call_id", "round_id", "scope", "tool_family", "access_mode", "execution_mode",
        "status", "attempts", "group_id", "visible_result_bytes", "persisted_output_bytes", "evidence_ref", "background_lifecycle",
    }
    if not isinstance(operations, list) or len(operations) > 64:
        errors.append("$.operations: expected at most 64 objects")
    else:
        for index, operation in enumerate(operations):
            required_operation_names = operation_names - {"group_id"}
            if not isinstance(operation, dict) or not required_operation_names.issubset(operation.keys()) or set(operation) - operation_names:
                errors.append(f"$.operations[{index}]: invalid fields")
                continue
            for field in ("operation_id",):
                if not isinstance(operation.get(field), str) or not identifier.fullmatch(operation[field]):
                    errors.append(f"$.operations[{index}].{field}: invalid identifier")
            call_pattern = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
            if not isinstance(operation.get("tool_call_id"), str) or not call_pattern.fullmatch(operation["tool_call_id"]):
                errors.append(f"$.operations[{index}].tool_call_id: invalid identifier")
            if operation.get("parent_tool_call_id") is not None and (not isinstance(operation.get("parent_tool_call_id"), str) or not call_pattern.fullmatch(operation["parent_tool_call_id"])):
                errors.append(f"$.operations[{index}].parent_tool_call_id: invalid identifier")
            if operation.get("round_id") is not None and (not isinstance(operation.get("round_id"), str) or not identifier.fullmatch(operation["round_id"])):
                errors.append(f"$.operations[{index}].round_id: invalid identifier")
            if operation.get("tool_family") not in {"fastctx", "codex-shell", "mcp", "functions-exec", "browser", "image", "other"}:
                errors.append(f"$.operations[{index}].tool_family: invalid value")
            if operation.get("access_mode") not in {"read-only", "side-effecting"}:
                errors.append(f"$.operations[{index}].access_mode: invalid value")
            if operation.get("execution_mode") not in {"parallel", "sequential", "background"}:
                errors.append(f"$.operations[{index}].execution_mode: invalid value")
            if operation.get("status") not in {"complete", "partial", "failed", "interrupted", "blocked"}:
                errors.append(f"$.operations[{index}].status: invalid value")
            for field in ("attempts", "visible_result_bytes", "persisted_output_bytes"):
                if not _is_int(operation.get(field)) or operation[field] < 0:
                    errors.append(f"$.operations[{index}].{field}: invalid numeric value")
            if operation.get("status") != "blocked" and _is_int(operation.get("attempts")) and operation["attempts"] < 1:
                errors.append(f"$.operations[{index}].attempts: non-blocked operation requires an attempt")
            if operation.get("status") == "blocked" and operation.get("attempts") == 0:
                if operation.get("round_id") is not None:
                    errors.append(f"$.operations[{index}].round_id: zero-attempt blocked operation cannot reference a round")
                if operation.get("visible_result_bytes") != 0 or operation.get("persisted_output_bytes") != 0:
                    errors.append(f"$.operations[{index}]: zero-attempt blocked operation cannot claim output bytes")
                if operation.get("evidence_ref") is not None or operation.get("background_lifecycle") is not None:
                    errors.append(f"$.operations[{index}]: zero-attempt blocked operation cannot claim evidence or lifecycle")
            if operation.get("group_id") is not None and (not isinstance(operation.get("group_id"), str) or not identifier.fullmatch(operation["group_id"])):
                errors.append(f"$.operations[{index}].group_id: invalid identifier")
            if operation.get("evidence_ref") is not None and not isinstance(operation.get("evidence_ref"), str):
                errors.append(f"$.operations[{index}].evidence_ref: invalid reference")
            operation_scope = operation.get("scope")
            if not isinstance(operation_scope, dict) or set(operation_scope) != {"scope_kind", "scope_ref"}:
                errors.append(f"$.operations[{index}].scope: invalid fields")
            lifecycle = operation.get("background_lifecycle")
            lifecycle_names = {
                "adapter", "job_id", "terminal_state", "exit_code", "log_evidence_ref",
                "log_unit", "log_start", "log_end", "poll_count", "stop_reason",
            }
            if lifecycle is not None and (
                not isinstance(lifecycle, dict)
                or set(lifecycle) != lifecycle_names
                or not isinstance(lifecycle.get("adapter"), str)
                or not re.fullmatch(r"^[A-Za-z0-9._:-]{1,64}$", lifecycle.get("adapter", ""))
                or not isinstance(lifecycle.get("job_id"), str)
                or not re.fullmatch(r"^[A-Za-z0-9._:-]{1,160}$", lifecycle.get("job_id", ""))
                or lifecycle.get("terminal_state") not in {"running", "complete", "failed", "interrupted", "cancelled"}
                or (lifecycle.get("exit_code") is not None and not _is_int(lifecycle.get("exit_code")))
                or (lifecycle.get("log_evidence_ref") is not None and (not isinstance(lifecycle.get("log_evidence_ref"), str) or len(lifecycle["log_evidence_ref"]) > 128))
                or lifecycle.get("log_unit") != "byte"
                or not _is_int(lifecycle.get("log_start")) or lifecycle["log_start"] < 0
                or not _is_int(lifecycle.get("log_end")) or lifecycle["log_end"] < lifecycle["log_start"]
                or not _is_int(lifecycle.get("poll_count")) or not 0 <= lifecycle["poll_count"] <= 64
                or (lifecycle.get("stop_reason") is not None and (not isinstance(lifecycle.get("stop_reason"), str) or not lifecycle["stop_reason"] or len(lifecycle["stop_reason"]) > 240))
            ):
                errors.append(f"$.operations[{index}].background_lifecycle: invalid lifecycle")

    continuation = payload.get("continuation")
    if not isinstance(continuation, dict) or set(continuation) != {"has_more", "offsets"} or not isinstance(continuation.get("has_more"), bool) or not isinstance(continuation.get("offsets"), list) or len(continuation.get("offsets", [])) > 64:
        errors.append("$.continuation: invalid fields")
    else:
        for index, offset in enumerate(continuation["offsets"]):
            if not isinstance(offset, dict) or set(offset) != {"operation_id", "unit", "next"}:
                errors.append(f"$.continuation.offsets[{index}]: invalid fields")
            elif offset.get("unit") not in {"line", "record", "byte", "page", "cursor"} or not isinstance(offset.get("operation_id"), str) or not identifier.fullmatch(offset["operation_id"]):
                errors.append(f"$.continuation.offsets[{index}]: invalid offset")
            elif not ((_is_int(offset.get("next")) and offset["next"] >= 0) or (isinstance(offset.get("next"), str) and re.fullmatch(r"^[A-Za-z0-9._~:-]{1,256}$", offset["next"]))):
                errors.append(f"$.continuation.offsets[{index}].next: invalid offset value")

    evidence_refs = payload.get("evidence_refs")
    if not isinstance(evidence_refs, list) or len(evidence_refs) > 64:
        errors.append("$.evidence_refs: expected at most 64 objects")
    else:
        evidence_names = {"ref_id", "kind", "path", "artifact_id", "sha256", "hash_status", "run_id", "turn_id", "scope_kind", "scope_ref", "owner", "attestation_ref"}
        required_evidence_names = {"ref_id", "kind", "sha256", "hash_status", "run_id", "turn_id", "scope_kind", "scope_ref", "owner"}
        for index, evidence in enumerate(evidence_refs):
            if not isinstance(evidence, dict) or not required_evidence_names.issubset(evidence.keys()) or set(evidence) - evidence_names:
                errors.append(f"$.evidence_refs[{index}]: invalid fields")
                continue
            if not isinstance(evidence.get("ref_id"), str) or not identifier.fullmatch(evidence["ref_id"]):
                errors.append(f"$.evidence_refs[{index}].ref_id: invalid identifier")
            if evidence.get("kind") not in {"log", "summary", "artifact", "sidecar"}:
                errors.append(f"$.evidence_refs[{index}].kind: invalid value")
            if ("path" in evidence) == ("artifact_id" in evidence):
                errors.append(f"$.evidence_refs[{index}]: exactly one of path or artifact_id is required")
            if "path" in evidence and (not isinstance(evidence.get("path"), str) or "\r" in evidence.get("path", "") or "\n" in evidence.get("path", "") or _unsafe_workspace_member_ref(evidence.get("path", ""))):
                errors.append(f"$.evidence_refs[{index}].path: invalid workspace-relative path")
            if "artifact_id" in evidence and (not isinstance(evidence.get("artifact_id"), str) or not re.fullmatch(r"^[A-Za-z0-9._:-]{1,256}$", evidence["artifact_id"])):
                errors.append(f"$.evidence_refs[{index}].artifact_id: invalid artifact id")
            if not isinstance(evidence.get("sha256"), str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", evidence["sha256"]):
                errors.append(f"$.evidence_refs[{index}].sha256: invalid hash")
            if evidence.get("hash_status") not in {"verified", "external-unverified"}:
                errors.append(f"$.evidence_refs[{index}].hash_status: invalid value")
            for field in ("run_id", "turn_id", "owner"):
                if not isinstance(evidence.get(field), str) or not evidence[field]:
                    errors.append(f"$.evidence_refs[{index}].{field}: required")
            if isinstance(evidence.get("run_id"), str) and not identifier.fullmatch(evidence["run_id"]):
                errors.append(f"$.evidence_refs[{index}].run_id: invalid identifier")
            if isinstance(evidence.get("turn_id"), str) and not identifier.fullmatch(evidence["turn_id"]):
                errors.append(f"$.evidence_refs[{index}].turn_id: invalid identifier")
            if evidence.get("scope_kind") not in {"repository", "phase", "project", "workspace"} or not isinstance(evidence.get("scope_ref"), str) or len(evidence.get("scope_ref", "")) > 256 or "\r" in evidence.get("scope_ref", "") or "\n" in evidence.get("scope_ref", "") or _unsafe_relative_ref(evidence.get("scope_ref", "")):
                errors.append(f"$.evidence_refs[{index}].scope: invalid scope binding")
            if isinstance(evidence.get("owner"), str) and (evidence.get("owner") == "unknown" or not re.fullmatch(r"^[A-Za-z0-9._:-]{1,128}$", evidence["owner"])):
                errors.append(f"$.evidence_refs[{index}].owner: invalid owner")
            if evidence.get("attestation_ref") is not None and (not isinstance(evidence.get("attestation_ref"), str) or len(evidence["attestation_ref"]) > 128):
                errors.append(f"$.evidence_refs[{index}].attestation_ref: invalid reference")

    boundaries = payload.get("external_boundaries")
    if not isinstance(boundaries, list) or len(boundaries) > 32:
        errors.append("$.external_boundaries: expected at most 32 objects")
    else:
        for index, boundary in enumerate(boundaries):
            if not isinstance(boundary, dict) or set(boundary) != {"boundary", "observed", "reason"}:
                errors.append(f"$.external_boundaries[{index}]: invalid fields")
            elif boundary.get("boundary") not in {"functions.exec", "codex-service", "mcp-provider", "browser-provider", "image-provider", "token-accounting", "other"} or not isinstance(boundary.get("observed"), bool) or not isinstance(boundary.get("reason"), str) or not boundary["reason"] or len(boundary["reason"]) > 240:
                errors.append(f"$.external_boundaries[{index}]: invalid boundary")

    summary_errors = payload.get("errors")
    if not isinstance(summary_errors, list) or len(summary_errors) > 32:
        errors.append("$.errors: expected at most 32 structured objects")
    else:
        error_names = {"code", "family", "severity", "message", "operation_id"}
        for index, error in enumerate(summary_errors):
            if not isinstance(error, dict) or set(error) != error_names:
                errors.append(f"$.errors[{index}]: structured error fields are required")
            elif not isinstance(error.get("code"), str) or not re.fullmatch(r"^[a-z0-9._-]{1,96}$", error["code"]) or error.get("family") not in {"contract", "authorization", "scope", "redaction", "timeout", "tool", "evidence", "external", "unknown"} or error.get("severity") not in {"warning", "error", "fatal"} or not isinstance(error.get("message"), str) or not error["message"] or len(error["message"]) > 240 or (error.get("operation_id") is not None and (not isinstance(error.get("operation_id"), str) or not identifier.fullmatch(error["operation_id"]))):
                errors.append(f"$.errors[{index}]: invalid structured error")
    return errors


def _manual_preflight_schema_errors(payload: Any) -> list[str]:
    """Dependency-free structural check for the authoritative preflight sidecar."""
    if not isinstance(payload, dict):
        return ["sidecar must be an object"]
    required = {"schema_version", "run_id", "turn_id", "scope", "operation_ids", "operation_manifest_sha256", "checks", "authority", "generated_at"}
    if set(payload) != required:
        return ["sidecar fields are incomplete or unknown"]
    errors: list[str] = []
    identifier = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
    if payload.get("schema_version") != "model-visible-tool-preflight.v1":
        errors.append("sidecar schema_version is invalid")
    for field in ("run_id", "turn_id"):
        if not isinstance(payload.get(field), str) or not identifier.fullmatch(payload[field]):
            errors.append(f"sidecar {field} is invalid")
    scope = payload.get("scope")
    if not isinstance(scope, dict) or set(scope) != {"scope_kind", "scope_ref"} or scope.get("scope_kind") != "repository" or not isinstance(scope.get("scope_ref"), str) or len(scope.get("scope_ref", "")) > 256 or _unsafe_relative_ref(scope.get("scope_ref", "")):
        errors.append("sidecar scope is invalid")
    operation_ids = payload.get("operation_ids")
    if not isinstance(operation_ids, list) or not operation_ids or len(operation_ids) > 64 or any(not isinstance(item, str) or not identifier.fullmatch(item) for item in operation_ids) or len(operation_ids) != len(set(operation_ids)):
        errors.append("sidecar operation_ids are invalid")
    if not isinstance(payload.get("operation_manifest_sha256"), str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", payload["operation_manifest_sha256"]):
        errors.append("sidecar operation manifest hash is invalid")
    checks = payload.get("checks")
    check_names = {"same_scope_verified", "authorization_verified", "secret_redaction_verified", "read_only_verified"}
    if not isinstance(checks, dict) or set(checks) != check_names or any(item is not True for item in checks.values()):
        errors.append("sidecar checks must all be true")
    authority = payload.get("authority")
    if not isinstance(authority, dict) or set(authority) != {"kind", "source_path", "sha256", "adapter_id"} or authority.get("kind") != "repository-agent-contract" or authority.get("source_path") != "AGENTS.md" or not isinstance(authority.get("sha256"), str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", authority["sha256"]) or not isinstance(authority.get("adapter_id"), str) or not re.fullmatch(r"^[A-Za-z0-9._:-]{1,128}$", authority["adapter_id"]):
        errors.append("sidecar authority is invalid")
    if not isinstance(payload.get("generated_at"), str) or _parse_timestamp(payload["generated_at"]) is None:
        errors.append("sidecar generated_at must be timezone-aware")
    return errors


def _manual_measurement_schema_errors(payload: Any) -> list[str]:
    """Dependency-free structural check for round/token measurement evidence."""
    if not isinstance(payload, dict):
        return ["measurement sidecar must be an object"]
    required = {
        "schema_version", "run_id", "turn_id", "scope", "round_measurement", "round_events",
        "visible_result_bytes", "token_measurement", "recorded_at",
    }
    if set(payload) != required:
        return ["measurement sidecar fields are incomplete or unknown"]
    errors: list[str] = []
    identifier = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
    if payload.get("schema_version") != "model-visible-tool-measurement.v1":
        errors.append("measurement sidecar schema_version is invalid")
    for field in ("run_id", "turn_id"):
        if not isinstance(payload.get(field), str) or not identifier.fullmatch(payload[field]):
            errors.append(f"measurement sidecar {field} is invalid")
    scope = payload.get("scope")
    if not isinstance(scope, dict) or set(scope) != {"scope_kind", "scope_ref"} or scope.get("scope_kind") not in {"repository", "phase", "project", "workspace"} or not isinstance(scope.get("scope_ref"), str) or len(scope.get("scope_ref", "")) > 256 or _unsafe_relative_ref(scope.get("scope_ref", "")):
        errors.append("measurement sidecar scope is invalid")
    round_measurement = payload.get("round_measurement")
    if not isinstance(round_measurement, dict) or set(round_measurement) != {"mode", "model_visible_rounds"} or round_measurement.get("mode") not in {"observed", "estimated"} or not _is_int(round_measurement.get("model_visible_rounds")) or round_measurement["model_visible_rounds"] < 0:
        errors.append("measurement sidecar round measurement is invalid")
    round_events = payload.get("round_events")
    if not isinstance(round_events, list) or len(round_events) > 64:
        errors.append("measurement sidecar round_events are invalid")
    else:
        for event in round_events:
            if not isinstance(event, dict) or set(event) != {"round_id", "turn_id", "result_blocks", "observed"} or not isinstance(event.get("round_id"), str) or not identifier.fullmatch(event["round_id"]) or not isinstance(event.get("turn_id"), str) or not identifier.fullmatch(event["turn_id"]) or not _is_int(event.get("result_blocks")) or event["result_blocks"] < 1 or not isinstance(event.get("observed"), bool):
                errors.append("measurement sidecar round event is invalid")
                break
    if not _is_int(payload.get("visible_result_bytes")) or not 0 <= payload["visible_result_bytes"] <= MAX_BYTES:
        errors.append("measurement sidecar visible_result_bytes is invalid")
    token_measurement = payload.get("token_measurement")
    if not isinstance(token_measurement, dict) or set(token_measurement) != {"mode", "visible_result_tokens", "method"} or token_measurement.get("mode") not in {"observed", "estimated"} or not _is_int(token_measurement.get("visible_result_tokens")) or token_measurement["visible_result_tokens"] < 0 or token_measurement.get("method") not in {"provider", "utf8-bytes-ceil-div-4"}:
        errors.append("measurement sidecar token measurement is invalid")
    if not isinstance(payload.get("recorded_at"), str) or _parse_timestamp(payload["recorded_at"]) is None:
        errors.append("measurement sidecar recorded_at must be timezone-aware")
    return errors


def _evidence_errors(payload: dict[str, Any], root: Path) -> tuple[list[str], dict[str, dict[str, Any]], dict[str, int]]:
    errors: list[str] = []
    refs_by_id: dict[str, dict[str, Any]] = {}
    local_sizes: dict[str, int] = {}
    evidence_refs = payload.get("evidence_refs", [])
    if not isinstance(evidence_refs, list):
        return ["$.evidence_refs: expected an array"], refs_by_id, local_sizes

    for index, evidence in enumerate(evidence_refs):
        if not isinstance(evidence, dict):
            errors.append(f"$.evidence_refs[{index}]: expected an object")
            continue
        ref_id = evidence.get("ref_id")
        if isinstance(ref_id, str):
            refs_by_id[ref_id] = evidence
        if evidence.get("run_id") != payload.get("run_id"):
            errors.append(f"$.evidence_refs[{index}].run_id: must bind to summary run_id")
        if evidence.get("turn_id") != payload.get("turn_id"):
            errors.append(f"$.evidence_refs[{index}].turn_id: must bind to summary turn_id")
        summary_scope = payload.get("scope", {})
        if evidence.get("scope_kind") != summary_scope.get("scope_kind") or evidence.get("scope_ref") != summary_scope.get("scope_ref"):
            errors.append(f"$.evidence_refs[{index}].scope: must bind to summary scope")
        if not isinstance(evidence.get("owner"), str) or not evidence.get("owner") or evidence.get("owner") == "unknown":
            errors.append(f"$.evidence_refs[{index}].owner: required evidence owner")
        path = evidence.get("path")
        artifact_id = evidence.get("artifact_id")
        hash_status = evidence.get("hash_status")
        if isinstance(path, str):
            if hash_status != "verified":
                errors.append(f"$.evidence_refs[{index}].hash_status: local path evidence must be verified")
                continue
            resolved = _resolve_evidence_path(root, path)
            if resolved is None or not resolved.is_file():
                errors.append(f"$.evidence_refs[{index}].path: evidence file is missing or outside root")
                continue
            try:
                digest = _sha256_file(resolved)
                size = resolved.stat().st_size
            except OSError:
                errors.append(f"$.evidence_refs[{index}].path: evidence file cannot be read")
                continue
            if digest != evidence.get("sha256"):
                errors.append(f"$.evidence_refs[{index}].sha256: does not match evidence file")
            scan_error = _file_safety_scan(resolved, text_kind=evidence.get("kind") in {"log", "summary", "sidecar"})
            if scan_error is not None:
                errors.append(f"$.evidence_refs[{index}].path: {scan_error}")
            if isinstance(ref_id, str):
                local_sizes[ref_id] = size
        elif isinstance(artifact_id, str):
            if hash_status != "external-unverified":
                errors.append(f"$.evidence_refs[{index}].hash_status: external artifacts require external-unverified")
            if not isinstance(evidence.get("owner"), str) or evidence.get("owner") in {"", "unknown"}:
                errors.append(f"$.evidence_refs[{index}].owner: external artifact owner is not bound")
        else:
            errors.append(f"$.evidence_refs[{index}]: requires path or artifact_id")

    for index, operation in enumerate(payload.get("operations", [])):
        if not isinstance(operation, dict):
            continue
        expected_size = local_sizes.get(operation.get("evidence_ref"))
        if expected_size is not None and operation.get("persisted_output_bytes") != expected_size:
            errors.append(f"$.operations[{index}].persisted_output_bytes: does not match local evidence size")
    return errors, refs_by_id, local_sizes


def _local_evidence_ref(
    ref_id: Any,
    refs_by_id: dict[str, dict[str, Any]],
    root: Path,
    field: str,
    errors: list[str],
) -> None:
    if not isinstance(ref_id, str):
        errors.append(f"{field}: requires a local evidence ref")
        return
    evidence = refs_by_id.get(ref_id)
    if evidence is None:
        errors.append(f"{field}: unknown evidence ref")
        return
    if not isinstance(evidence.get("path"), str) or evidence.get("hash_status") != "verified":
        errors.append(f"{field}: must reference verified local evidence")
        return
    if _resolve_evidence_path(root, evidence["path"]) is None:
        errors.append(f"{field}: evidence path is not workspace-relative")


def _preflight_errors(
    payload: dict[str, Any],
    root: Path,
    refs_by_id: dict[str, dict[str, Any]],
    operation_ids: list[str],
) -> list[str]:
    errors: list[str] = []
    preflight = payload.get("preflight", {})
    operations = payload.get("operations", [])
    scope = payload.get("scope", {})
    parallel_operations = [item for item in operations if item.get("execution_mode") == "parallel"]
    has_parallel = bool(parallel_operations)
    verification_claimed = any(
        preflight.get(key) is True
        for key in ("same_scope_verified", "authorization_verified", "secret_redaction_verified")
    )
    if verification_claimed and preflight.get("evidence_ref") is None:
        errors.append("$.preflight: verification flags require an authoritative sidecar")

    # v1 deliberately fails closed outside repository scope until a real account/workspace adapter exists.
    if has_parallel and scope.get("scope_kind") != "repository" and any(
        not (item.get("status") == "blocked" and item.get("attempts") == 0)
        for item in parallel_operations
    ):
        errors.append("$.operations: parallel execution is supported only for repository scope in v1")
    if has_parallel and preflight.get("parallelization_allowed") is not True:
        if any(item.get("status") != "blocked" for item in parallel_operations):
            errors.append("$.preflight.parallelization_allowed: parallel operation was not authorized")
        if any(preflight.get(key) is True for key in ("same_scope_verified", "authorization_verified", "secret_redaction_verified")):
            errors.append("$.preflight: unbound verification flags cannot authorize parallel operations")

    requires_binding = preflight.get("parallelization_allowed") is True
    supplied_binding = preflight.get("evidence_ref") is not None
    if requires_binding or supplied_binding:
        ref_id = preflight.get("evidence_ref")
        evidence = refs_by_id.get(ref_id) if isinstance(ref_id, str) else None
        if evidence is None:
            errors.append("$.preflight.evidence_ref: authoritative preflight sidecar is required")
            return errors
        if evidence.get("kind") != "sidecar" or evidence.get("hash_status") != "verified" or not isinstance(evidence.get("path"), str):
            errors.append("$.preflight.evidence_ref: must reference a verified local sidecar")
            return errors
        sidecar_path = _resolve_evidence_path(root, evidence["path"])
        if sidecar_path is None or not sidecar_path.is_file():
            errors.append("$.preflight.evidence_ref: sidecar is missing or outside root")
            return errors
        sidecar = _load_json(sidecar_path, label="preflight sidecar")
        schema_errors = _schema_validation_errors(sidecar, PREFLIGHT_SCHEMA_PATH)
        schema_errors.extend(_manual_preflight_schema_errors(sidecar))
        if schema_errors:
            errors.append("$.preflight.evidence_ref: sidecar schema validation failed")
            return errors
        if sidecar.get("run_id") != payload.get("run_id") or sidecar.get("turn_id") != payload.get("turn_id"):
            errors.append("$.preflight.evidence_ref: sidecar run/turn binding mismatch")
        if sidecar.get("scope") != scope:
            errors.append("$.preflight.evidence_ref: sidecar scope binding mismatch")
        if sidecar.get("operation_ids") != sorted(operation_ids):
            errors.append("$.preflight.evidence_ref: sidecar operation binding mismatch")
        if sidecar.get("operation_manifest_sha256") != operation_manifest_hash(operations):
            errors.append("$.preflight.evidence_ref: sidecar operation manifest mismatch")
        generated_at = _parse_timestamp(sidecar.get("generated_at"))
        started_at = _parse_timestamp(payload.get("timing", {}).get("started_at"))
        if generated_at is not None and started_at is not None and generated_at > started_at:
            errors.append("$.preflight.evidence_ref: sidecar was generated after execution started")
        checks = sidecar.get("checks", {})
        if any(check is not True for check in checks.values()):
            errors.append("$.preflight.evidence_ref: sidecar contains a failed preflight check")
        if any(item.get("access_mode") != "read-only" for item in operations):
            errors.append("$.preflight.evidence_ref: read_only_verified conflicts with a side-effecting operation")
        authority = sidecar.get("authority", {})
        adapter_id = authority.get("adapter_id")
        if adapter_id not in REGISTERED_PREFLIGHT_ADAPTERS:
            errors.append("$.preflight.evidence_ref: no trusted preflight adapter is registered")
        authority_path = _resolve_evidence_path(root, "AGENTS.md")
        if authority_path is None or not authority_path.is_file() or is_reparse_point(authority_path):
            errors.append("$.preflight.evidence_ref: repository AGENTS.md is unavailable")
        else:
            try:
                if authority.get("sha256") != _sha256_file(authority_path):
                    errors.append("$.preflight.evidence_ref: AGENTS.md authority hash mismatch")
            except OSError:
                errors.append("$.preflight.evidence_ref: repository authority cannot be read")
        expected_booleans = {
            "same_scope_verified": True,
            "authorization_verified": True,
            "secret_redaction_verified": True,
        }
        for key, expected in expected_booleans.items():
            if preflight.get(key) is not expected:
                errors.append(f"$.preflight.{key}: does not match authoritative sidecar")
        if not requires_binding:
            errors.append("$.preflight.parallelization_allowed: conflicts with an authoritative allowed sidecar")
    return errors


def _measurement_evidence_errors(
    payload: dict[str, Any],
    root: Path,
    refs_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    """Read and bind the machine-generated round/token measurement sidecar."""
    errors: list[str] = []
    measurement = payload.get("measurement", {})
    refs_to_load = {
        ref_id
        for ref_id in (measurement.get("rounds_evidence_ref"), measurement.get("tokens_evidence_ref"))
        if isinstance(ref_id, str)
    }
    sidecars: dict[str, dict[str, Any]] = {}
    for ref_id in refs_to_load:
        evidence = refs_by_id.get(ref_id)
        if evidence is None:
            continue
        if evidence.get("kind") != "sidecar" or evidence.get("hash_status") != "verified" or not isinstance(evidence.get("path"), str):
            errors.append(f"$.measurement: evidence ref {ref_id!r} must be verified local measurement evidence")
            continue
        sidecar_path = _resolve_evidence_path(root, evidence["path"])
        if sidecar_path is None or not sidecar_path.is_file():
            errors.append(f"$.measurement: evidence ref {ref_id!r} is missing or outside root")
            continue
        sidecar = _load_json(sidecar_path, label="measurement sidecar")
        schema_errors = _schema_validation_errors(sidecar, MEASUREMENT_SCHEMA_PATH)
        schema_errors.extend(_manual_measurement_schema_errors(sidecar))
        if schema_errors:
            errors.append(f"$.measurement: evidence ref {ref_id!r} has an invalid measurement sidecar")
            continue
        sidecars[ref_id] = sidecar

    summary_scope = payload.get("scope", {})
    for ref_id, sidecar in sidecars.items():
        if sidecar.get("run_id") != payload.get("run_id") or sidecar.get("turn_id") != payload.get("turn_id"):
            errors.append(f"$.measurement: sidecar {ref_id!r} run/turn binding mismatch")
        if sidecar.get("scope") != summary_scope:
            errors.append(f"$.measurement: sidecar {ref_id!r} scope binding mismatch")
        if sidecar.get("visible_result_bytes") != payload.get("metrics", {}).get("visible_result_bytes"):
            errors.append(f"$.measurement: sidecar {ref_id!r} visible_result_bytes mismatch")

    rounds_ref = measurement.get("rounds_evidence_ref")
    if measurement.get("rounds") != "unknown" and isinstance(rounds_ref, str) and rounds_ref in sidecars:
        sidecar = sidecars[rounds_ref]
        if sidecar.get("round_measurement", {}).get("mode") != measurement.get("rounds"):
            errors.append("$.measurement.rounds: does not match measurement sidecar")
        if sidecar.get("round_measurement", {}).get("model_visible_rounds") != payload.get("metrics", {}).get("model_visible_rounds"):
            errors.append("$.metrics.model_visible_rounds: does not match measurement sidecar")
        if sidecar.get("round_events") != payload.get("round_events"):
            errors.append("$.round_events: does not match measurement sidecar")

    tokens_ref = measurement.get("tokens_evidence_ref")
    if measurement.get("tokens") != "unknown" and isinstance(tokens_ref, str) and tokens_ref in sidecars:
        sidecar = sidecars[tokens_ref]
        token_sidecar = sidecar.get("token_measurement", {})
        if token_sidecar.get("mode") != measurement.get("tokens"):
            errors.append("$.measurement.tokens: does not match measurement sidecar")
        if token_sidecar.get("visible_result_tokens") != payload.get("metrics", {}).get("visible_result_tokens"):
            errors.append("$.metrics.visible_result_tokens: does not match measurement sidecar")
        expected_method = "utf8-bytes-ceil-div-4" if measurement.get("tokens") == "estimated" else "provider"
        if token_sidecar.get("method") != expected_method:
            errors.append("$.measurement.tokens: sidecar method does not match measurement mode")
    return errors


def _background_lifecycle_errors(
    payload: dict[str, Any],
    root: Path,
    refs_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    """Validate started background jobs through the registered family adapter."""
    errors: list[str] = []
    for index, operation in enumerate(payload.get("operations", [])):
        if not isinstance(operation, dict):
            continue
        mode = operation.get("execution_mode")
        lifecycle = operation.get("background_lifecycle")
        field = f"$.operations[{index}].background_lifecycle"
        if mode != "background":
            if lifecycle is not None:
                errors.append(f"{field}: only background operations may carry lifecycle evidence")
            continue

        status = operation.get("status")
        attempts = operation.get("attempts")
        never_started = status == "blocked" and attempts == 0
        if lifecycle is None:
            if not never_started:
                errors.append(f"{field}: required for a started background operation")
            continue
        if not isinstance(lifecycle, dict):
            continue
        if never_started:
            errors.append(f"{field}: zero-attempt blocked operation cannot carry lifecycle evidence")
            continue

        tool_family = operation.get("tool_family")
        if lifecycle.get("adapter") != tool_family:
            errors.append(f"{field}.adapter: must match operation tool_family")
        if status == "complete" and tool_family not in REGISTERED_BACKGROUND_ADAPTERS:
            errors.append(f"{field}.adapter: no registered background adapter can prove complete")
        if lifecycle.get("poll_count", 0) < 1:
            errors.append(f"{field}.poll_count: a started job requires at least one status query")
        if lifecycle.get("stop_reason") is None:
            errors.append(f"{field}.stop_reason: required when lifecycle collection stops")

        log_ref = lifecycle.get("log_evidence_ref")
        if log_ref != operation.get("evidence_ref"):
            errors.append(f"{field}.log_evidence_ref: must match operation evidence_ref")
        evidence = refs_by_id.get(log_ref) if isinstance(log_ref, str) else None
        if evidence is None or evidence.get("kind") != "log" or evidence.get("hash_status") != "verified" or not isinstance(evidence.get("path"), str):
            errors.append(f"{field}.log_evidence_ref: must reference a verified local log")
        else:
            resolved = _resolve_evidence_path(root, evidence["path"])
            if resolved is None or not resolved.is_file():
                errors.append(f"{field}.log_evidence_ref: log is missing or outside root")
            else:
                log_size = resolved.stat().st_size
                if lifecycle.get("log_end", 0) > log_size:
                    errors.append(f"{field}.log_end: exceeds verified log size")
                if status == "complete" and (lifecycle.get("log_start") != 0 or lifecycle.get("log_end") != log_size):
                    errors.append(f"{field}: complete must bind the full zero-based byte range")

        state = lifecycle.get("terminal_state")
        exit_code = lifecycle.get("exit_code")
        if status == "complete" and (state != "complete" or exit_code != 0):
            errors.append(f"{field}: complete requires terminal_state=complete and exit_code=0")
        elif status == "failed" and (state != "failed" or not _is_int(exit_code) or exit_code == 0):
            errors.append(f"{field}: failed requires terminal_state=failed and a non-zero exit_code")
        elif status == "interrupted" and state not in {"interrupted", "cancelled"}:
            errors.append(f"{field}: interrupted requires an interrupted or cancelled terminal state")
        elif status == "partial" and (state != "running" or exit_code is not None):
            errors.append(f"{field}: partial requires terminal_state=running and a null exit_code")
        elif status == "blocked" and not never_started and state not in {"interrupted", "cancelled"}:
            errors.append(f"{field}: a started blocked job must be interrupted or cancelled")
    return errors


def _cross_field_errors(payload: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    status = payload.get("status")
    metrics = payload.get("metrics", {})
    preflight = payload.get("preflight", {})
    continuation = payload.get("continuation", {})
    operations = payload.get("operations", [])
    round_events = payload.get("round_events", [])
    measurement = payload.get("measurement", {})
    scope = payload.get("scope", {})

    if not isinstance(metrics, dict):
        return ["$.metrics: expected an object"]
    if not isinstance(preflight, dict):
        return ["$.preflight: expected an object"]
    if not isinstance(continuation, dict):
        return ["$.continuation: expected an object"]
    if not isinstance(measurement, dict):
        return ["$.measurement: expected an object"]
    if not isinstance(scope, dict):
        return ["$.scope: expected an object"]
    if not isinstance(operations, list) or any(not isinstance(item, dict) for item in operations):
        return ["$.operations: every item must be an object"]
    if not isinstance(round_events, list) or any(not isinstance(item, dict) for item in round_events):
        return ["$.round_events: every item must be an object"]

    timing = payload.get("timing", {})
    if not isinstance(timing, dict):
        return ["$.timing: expected an object"]
    started_at = _parse_timestamp(timing.get("started_at"))
    finished_at = _parse_timestamp(timing.get("finished_at"))
    if started_at is None:
        errors.append("$.timing.started_at: expected a timezone-aware ISO-8601 timestamp")
    if finished_at is None:
        errors.append("$.timing.finished_at: expected a timezone-aware ISO-8601 timestamp")
    if started_at is not None and finished_at is not None and finished_at < started_at:
        errors.append("$.timing.finished_at: cannot be earlier than started_at")

    try:
        serialized_size = _serialized_size(payload)
    except (TypeError, ValueError):
        serialized_size = 0
        errors.append("$: summary must be JSON serializable")
    if serialized_size > MAX_BYTES:
        errors.append(f"$: serialized summary exceeds {MAX_BYTES} bytes")
    if (serialized_size + 3) // 4 > MAX_ESTIMATED_TOKENS:
        errors.append(f"$: serialized summary exceeds {MAX_ESTIMATED_TOKENS} estimated transport tokens")

    visible_result_bytes = metrics.get("visible_result_bytes", 0)
    if isinstance(visible_result_bytes, int) and visible_result_bytes > MAX_BYTES:
        errors.append("$.metrics.visible_result_bytes: exceeds transport byte limit")

    operation_ids = [item.get("operation_id") for item in operations]
    call_ids = [item.get("tool_call_id") for item in operations]
    if len(operation_ids) != len(set(operation_ids)):
        errors.append("$.operations: operation_id values must be unique")
    if all(isinstance(item, str) for item in operation_ids) and operation_ids != sorted(operation_ids):
        errors.append("$.operations: must be sorted by operation_id")
    if len(call_ids) != len(set(call_ids)):
        errors.append("$.operations: tool_call_id values must be unique")
    known_call_ids = {item for item in call_ids if isinstance(item, str)}
    parent_map = {item.get("tool_call_id"): item.get("parent_tool_call_id") for item in operations}
    for index, operation in enumerate(operations):
        call_id = operation.get("tool_call_id")
        parent = operation.get("parent_tool_call_id")
        if parent is not None and parent not in known_call_ids:
            errors.append(f"$.operations[{index}].parent_tool_call_id: unknown parent tool call")
        if parent == call_id:
            errors.append(f"$.operations[{index}].parent_tool_call_id: cannot reference itself")
        if operation.get("scope") != scope:
            errors.append(f"$.operations[{index}].scope: does not match summary scope")
    for call_id in known_call_ids:
        seen: set[str] = set()
        cursor: str | None = call_id
        while cursor is not None:
            if cursor in seen:
                errors.append("$.operations: parent_tool_call_id lineage contains a cycle")
                break
            seen.add(cursor)
            parent = parent_map.get(cursor)
            cursor = parent if isinstance(parent, str) else None

    event_ids = [event.get("round_id") for event in round_events]
    if len(event_ids) != len(set(event_ids)):
        errors.append("$.round_events: round_id values must be unique")
    if all(isinstance(item, str) for item in event_ids) and event_ids != sorted(event_ids):
        errors.append("$.round_events: must be sorted by round_id")
    for index, event in enumerate(round_events):
        if event.get("turn_id") != payload.get("turn_id"):
            errors.append(f"$.round_events[{index}].turn_id: must match summary turn_id")

    rounds_mode = measurement.get("rounds")
    if rounds_mode == "unknown":
        if round_events:
            errors.append("$.round_events: must be empty when rounds measurement is unknown")
        if measurement.get("rounds_evidence_ref") is not None:
            errors.append("$.measurement.rounds_evidence_ref: must be null when rounds are unknown")
    else:
        if operations and not round_events:
            errors.append("$.round_events: required when operations exist and rounds are measured")
        if metrics.get("model_visible_rounds") != len(round_events):
            errors.append("$.metrics.model_visible_rounds: must equal round_events length")
        if measurement.get("rounds_evidence_ref") is None:
            errors.append("$.measurement.rounds_evidence_ref: required for measured rounds")
        if rounds_mode == "observed" and any(event.get("observed") is not True for event in round_events):
            errors.append("$.round_events: observed measurement requires observed events")
    if rounds_mode == "unknown" and metrics.get("model_visible_rounds") != 0:
        errors.append("$.metrics.model_visible_rounds: must be 0 when round measurement is unknown")

    event_id_set = {item for item in event_ids if isinstance(item, str)}
    referenced_round_ids = {
        item.get("round_id") for item in operations if isinstance(item.get("round_id"), str)
    }
    for event_id in event_id_set:
        if event_id not in referenced_round_ids:
            errors.append(f"$.round_events: round {event_id!r} is not referenced by an operation")
    for index, operation in enumerate(operations):
        round_id = operation.get("round_id")
        if rounds_mode == "unknown":
            if round_id is not None:
                errors.append(f"$.operations[{index}].round_id: must be null when rounds are unknown")
        elif operation.get("status") == "blocked" and operation.get("attempts") == 0 and round_id is None:
            continue
        elif round_id not in event_id_set:
            errors.append(f"$.operations[{index}].round_id: does not reference a round event")

    operation_attempts = sum(item.get("attempts", 0) for item in operations)
    expected_retries = sum(retry_count(item.get("attempts", 0)) for item in operations)
    visible_sum = sum(item.get("visible_result_bytes", 0) for item in operations)
    persisted_sum = sum(item.get("persisted_output_bytes", 0) for item in operations)
    parallel_operations = [item for item in operations if item.get("execution_mode") == "parallel"]
    parallel_group_ids = {item.get("group_id") for item in parallel_operations}
    if None in parallel_group_ids:
        errors.append("$.operations: parallel operations require group_id")
        parallel_group_ids.discard(None)
    expected_parallel_groups = len(parallel_group_ids)
    parallel_group_rounds: dict[str, set[Any]] = {}
    for operation in parallel_operations:
        group_id = operation.get("group_id")
        if isinstance(group_id, str):
            parallel_group_rounds.setdefault(group_id, set()).add(operation.get("round_id"))
    for group_id, group_round_ids in parallel_group_rounds.items():
        if len(group_round_ids) > 1:
            errors.append(f"$.operations: parallel group {group_id!r} spans multiple round events")
    expected_sequential_calls = sum(item.get("execution_mode") == "sequential" for item in operations)
    expected_background_calls = sum(item.get("execution_mode") == "background" for item in operations)
    expected_partial = sum(item.get("status") == "partial" for item in operations)
    expected_failed = sum(item.get("status") == "failed" for item in operations)
    expected_interrupted = sum(item.get("status") == "interrupted" for item in operations)
    expected_blocked = sum(item.get("status") == "blocked" for item in operations)
    metric_checks = {
        "underlying_tool_calls": operation_attempts,
        "retries": expected_retries,
        "parallel_groups": expected_parallel_groups,
        "sequential_calls": expected_sequential_calls,
        "background_calls": expected_background_calls,
        "visible_result_bytes": visible_sum,
        "persisted_output_bytes": persisted_sum,
        "partial_results": expected_partial,
        "failed_calls": expected_failed,
        "interrupted_calls": expected_interrupted,
        "blocked_calls": expected_blocked,
    }
    for name, expected in metric_checks.items():
        if metrics.get(name) != expected:
            errors.append(f"$.metrics.{name}: does not match operations")
    if measurement.get("tokens") == "estimated":
        expected_tokens = (visible_sum + 3) // 4
        if metrics.get("visible_result_tokens") != expected_tokens:
            errors.append("$.metrics.visible_result_tokens: does not match UTF-8 byte estimate")
    if measurement.get("tokens") == "unknown" and metrics.get("visible_result_tokens") != 0:
        errors.append("$.metrics.visible_result_tokens: must be 0 when token measurement is unknown")
    if measurement.get("tokens") in {"observed", "estimated"} and measurement.get("tokens_evidence_ref") is None:
        errors.append("$.measurement.tokens_evidence_ref: required for measured tokens")
    if measurement.get("tokens") == "unknown" and measurement.get("tokens_evidence_ref") is not None:
        errors.append("$.measurement.tokens_evidence_ref: must be null when tokens are unknown")

    evidence_errors, refs_by_id, local_sizes = _evidence_errors(payload, root)
    errors.extend(evidence_errors)
    evidence_ref_ids = [item.get("ref_id") for item in payload.get("evidence_refs", []) if isinstance(item, dict)]
    if len(evidence_ref_ids) != len(set(evidence_ref_ids)):
        errors.append("$.evidence_refs: ref_id values must be unique")
    if all(isinstance(item, str) for item in evidence_ref_ids) and evidence_ref_ids != sorted(evidence_ref_ids):
        errors.append("$.evidence_refs: must be sorted by ref_id")
    known_evidence_refs = set(evidence_ref_ids)
    operation_evidence_refs = [item.get("evidence_ref") for item in operations if item.get("evidence_ref") is not None]
    if len(operation_evidence_refs) != len(set(operation_evidence_refs)):
        errors.append("$.operations: non-null evidence_ref values must be unique")
    operation_evidence_identity: dict[tuple[str, str], str] = {}
    for index, operation in enumerate(operations):
        ref_id = operation.get("evidence_ref")
        if ref_id is None:
            continue
        evidence = refs_by_id.get(ref_id)
        if evidence is None:
            continue
        if evidence.get("kind") == "sidecar":
            errors.append(f"$.operations[{index}].evidence_ref: sidecar evidence cannot represent tool output")
        if isinstance(evidence.get("path"), str):
            resolved = _resolve_evidence_path(root, evidence["path"])
            identity = ("path:" + str(resolved) if resolved is not None else "path:" + evidence["path"], str(evidence.get("sha256")))
        elif isinstance(evidence.get("artifact_id"), str):
            identity = ("artifact:" + evidence["artifact_id"], str(evidence.get("sha256")))
        else:
            continue
        previous = operation_evidence_identity.get(identity)
        if previous is not None and previous != str(ref_id):
            errors.append(f"$.operations[{index}].evidence_ref: aliases evidence already used by operation {previous}")
        else:
            operation_evidence_identity[identity] = str(ref_id)
    for index, offset in enumerate(continuation.get("offsets", [])):
        if offset.get("operation_id") not in set(operation_ids):
            errors.append(f"$.continuation.offsets[{index}].operation_id: unknown operation")
    for index, operation in enumerate(operations):
        if operation.get("status") == "blocked" and operation.get("attempts") == 0:
            if operation.get("round_id") is not None:
                errors.append(f"$.operations[{index}].round_id: zero-attempt blocked operation cannot reference a round")
            if operation.get("visible_result_bytes") != 0 or operation.get("persisted_output_bytes") != 0:
                errors.append(f"$.operations[{index}]: zero-attempt blocked operation cannot claim output bytes")
            if operation.get("evidence_ref") is not None or operation.get("background_lifecycle") is not None:
                errors.append(f"$.operations[{index}]: zero-attempt blocked operation cannot claim evidence or lifecycle")
        if operation.get("execution_mode") == "parallel" and preflight.get("parallelization_allowed") is not True and operation.get("status") != "blocked":
            errors.append(f"$.operations[{index}]: parallel operation is not allowed by preflight")
        if operation.get("execution_mode") == "parallel" and operation.get("access_mode") != "read-only":
            errors.append(f"$.operations[{index}]: only read-only operations may run in parallel")
        if operation.get("execution_mode") != "parallel" and operation.get("group_id") is not None:
            errors.append(f"$.operations[{index}].group_id: only parallel operations may have a group_id")
        if operation.get("evidence_ref") is not None and operation.get("evidence_ref") not in known_evidence_refs:
            errors.append(f"$.operations[{index}].evidence_ref: does not reference evidence_refs.ref_id")
        if operation.get("persisted_output_bytes", 0) > 0 and operation.get("evidence_ref") is None:
            errors.append(f"$.operations[{index}].evidence_ref: required when persisted output is non-zero")
        if operation.get("evidence_ref") in local_sizes and operation.get("persisted_output_bytes") != local_sizes[operation.get("evidence_ref")]:
            errors.append(f"$.operations[{index}].persisted_output_bytes: does not match evidence size")

    for field in ("rounds_evidence_ref", "tokens_evidence_ref"):
        ref_id = measurement.get(field)
        if ref_id is not None:
            _local_evidence_ref(ref_id, refs_by_id, root, f"$.measurement.{field}", errors)
    errors.extend(_measurement_evidence_errors(payload, root, refs_by_id))
    errors.extend(_background_lifecycle_errors(payload, root, refs_by_id))
    if (
        parallel_operations
        or preflight.get("evidence_ref") is not None
        or any(preflight.get(key) is True for key in ("same_scope_verified", "authorization_verified", "secret_redaction_verified"))
    ):
        errors.extend(_preflight_errors(payload, root, refs_by_id, [item for item in operation_ids if isinstance(item, str)]))

    if continuation.get("has_more") is True and status not in {"partial", "interrupted"}:
        errors.append("$: has_more requires partial or interrupted status")
    if continuation.get("has_more") is False and continuation.get("offsets"):
        errors.append("$.continuation.offsets: must be empty when has_more is false")
    if status == "blocked" and not preflight.get("block_reason"):
        errors.append("$.preflight.block_reason: required for blocked summaries")
    if status == "failed" and not payload.get("errors"):
        errors.append("$.errors: failed summaries require at least one error")

    errors_payload = payload.get("errors", [])
    if isinstance(errors_payload, list):
        if all(isinstance(item, dict) for item in errors_payload):
            error_keys = [(str(item.get("operation_id") or ""), str(item.get("code") or "")) for item in errors_payload]
            if error_keys != sorted(error_keys):
                errors.append("$.errors: must be sorted by operation_id and code")
        for index, error in enumerate(errors_payload):
            if isinstance(error, dict) and error.get("operation_id") is not None and error.get("operation_id") not in set(operation_ids):
                errors.append(f"$.errors[{index}].operation_id: unknown operation")

    boundaries = [item for item in payload.get("external_boundaries", []) if isinstance(item, dict)]
    boundary_names = [item.get("boundary") for item in boundaries]
    if len(boundary_names) != len(set(boundary_names)):
        errors.append("$.external_boundaries: boundary values must be unique")
    if all(isinstance(item, str) for item in boundary_names) and boundary_names != sorted(boundary_names):
        errors.append("$.external_boundaries: must be sorted by boundary")
    for index, boundary in enumerate(boundaries):
        if boundary.get("observed") is True and boundary.get("boundary") not in REGISTERED_OBSERVED_BOUNDARIES:
            errors.append(f"$.external_boundaries[{index}].observed: no repository-registered adapter exists")
    boundary_families = {
        "functions.exec": "functions-exec",
        "codex-service": "codex-shell",
        "mcp-provider": "mcp",
        "browser-provider": "browser",
        "image-provider": "image",
        "other": "other",
    }
    operation_families = {item.get("tool_family") for item in operations}
    for index, boundary in enumerate(boundaries):
        family = boundary_families.get(boundary.get("boundary"))
        if boundary.get("observed") is False and family in operation_families and rounds_mode == "observed":
            errors.append(f"$.external_boundaries[{index}].observed: conflicts with observed round measurement")
    adapter_boundaries = {
        "mcp": "mcp-provider",
        "browser": "browser-provider",
        "image": "image-provider",
        "functions-exec": "functions.exec",
        "other": "other",
    }
    for family, required_boundary in adapter_boundaries.items():
        family_operations = [item for item in operations if item.get("tool_family") == family]
        if not family_operations or all(item.get("status") == "blocked" and item.get("attempts") == 0 for item in family_operations):
            continue
        matching_boundaries = [item for item in boundaries if item.get("boundary") == required_boundary]
        if not matching_boundaries:
            errors.append(f"$.external_boundaries: {required_boundary} must be recorded for {family} operations")
        elif rounds_mode == "observed" and not any(item.get("observed") is True for item in matching_boundaries):
            errors.append(f"$.external_boundaries: {required_boundary}=false conflicts with observed round measurement")
        elif rounds_mode == "unknown" and not any(item.get("observed") is False for item in matching_boundaries):
            errors.append(f"$.external_boundaries: {required_boundary}=true conflicts with unknown round measurement")
    for index, operation in enumerate(operations):
        required_boundary = adapter_boundaries.get(operation.get("tool_family"))
        if operation.get("status") == "complete" and required_boundary is not None:
            if not any(
                item.get("boundary") == required_boundary
                and item.get("observed") is True
                and required_boundary in REGISTERED_OBSERVED_BOUNDARIES
                for item in boundaries
            ):
                errors.append(f"$.operations[{index}].status: complete requires a registered observed provider boundary")
    if rounds_mode == "unknown" and not any(
        item.get("boundary") in {"functions.exec", "codex-service", "mcp-provider", "browser-provider", "image-provider", "other"}
        and item.get("observed") is False
        for item in boundaries
    ):
        errors.append("$.external_boundaries: unknown round measurement requires an unobserved execution boundary")
    if measurement.get("tokens") == "unknown" and not any(
        item.get("boundary") == "token-accounting" and item.get("observed") is False for item in boundaries
    ):
        errors.append("$.external_boundaries: unknown token measurement requires an unobserved token-accounting boundary")
    if measurement.get("tokens") == "observed" and "token-accounting" not in REGISTERED_OBSERVED_BOUNDARIES:
        errors.append("$.measurement.tokens: observed token accounting has no repository-registered adapter")

    unverified_refs = [
        item for item in payload.get("evidence_refs", [])
        if isinstance(item, dict) and item.get("hash_status") == "external-unverified"
    ]
    unverified_external = bool(unverified_refs)
    artifact_boundary_by_owner = {
        "mcp-provider": "mcp-provider",
        "browser-provider": "browser-provider",
        "image-provider": "image-provider",
        "functions-exec": "functions.exec",
        "codex-service": "codex-service",
    }
    artifact_boundary_by_namespace = {
        "mcp": "mcp-provider",
        "browser": "browser-provider",
        "image": "image-provider",
        "functions-exec": "functions.exec",
        "codex": "codex-service",
    }
    for evidence in unverified_refs:
        owner = str(evidence.get("owner", ""))
        artifact_id = str(evidence.get("artifact_id", ""))
        owner_boundary = artifact_boundary_by_owner.get(owner)
        namespace_boundary = artifact_boundary_by_namespace.get(artifact_id.split(":", 1)[0]) if ":" in artifact_id else None
        if owner_boundary is not None and namespace_boundary is not None and owner_boundary != namespace_boundary:
            errors.append("$.evidence_refs: external artifact owner conflicts with artifact namespace")
        required_boundary = namespace_boundary or owner_boundary
        if required_boundary is None:
            required_boundary = "other"
        if not any(item.get("boundary") == required_boundary and item.get("observed") is False for item in boundaries):
            errors.append(f"$.external_boundaries: {required_boundary}=false is required for external evidence")
    if status == "complete":
        if metrics.get("partial_results") != 0 or metrics.get("failed_calls") != 0 or metrics.get("interrupted_calls") != 0 or metrics.get("blocked_calls") != 0:
            errors.append("$: complete summaries cannot contain incomplete calls")
        if continuation.get("has_more") is not False or continuation.get("offsets"):
            errors.append("$: complete summaries cannot require continuation")
        if payload.get("errors"):
            errors.append("$: complete summaries cannot contain errors")
        if unverified_external:
            errors.append("$: complete summaries cannot rely on external-unverified evidence")

    operation_statuses = {item.get("status") for item in operations}
    error_severities = {item.get("severity") for item in errors_payload if isinstance(item, dict)}
    if "failed" in operation_statuses or error_severities & {"error", "fatal"}:
        expected_status = "failed"
    elif "interrupted" in operation_statuses:
        expected_status = "interrupted"
    elif "blocked" in operation_statuses:
        expected_status = "blocked"
    elif "partial" in operation_statuses or continuation.get("has_more") is True or unverified_external or errors_payload:
        expected_status = "partial"
    else:
        expected_status = "complete"
    if status != expected_status:
        errors.append(f"$.status: expected {expected_status!r} from evidence and operation states")
    return errors


def validate_payload(payload: Any, *, root: Path | None = None) -> None:
    if not isinstance(payload, dict):
        raise ToolRoundSummaryValidationError("$: expected an object")
    validation_root = _safe_workspace_root(root or ROOT)
    structural_errors = _manual_schema_errors(payload)
    if structural_errors:
        raise ToolRoundSummaryValidationError(
            "summary schema validation failed:\n" + "\n".join(f"- {error}" for error in structural_errors[:20])
        )
    if jsonschema is not None:
        schema_errors = _schema_validation_errors(payload, SCHEMA_PATH)
        if schema_errors:
            raise ToolRoundSummaryValidationError(
                "summary schema validation failed:\n" + "\n".join(f"- {error}" for error in schema_errors[:20])
            )
    errors = _cross_field_errors(payload, validation_root)
    for path, value in _walk_strings(payload):
        if _contains_secret(value):
            errors.append(f"{path}: contains an unredacted credential")
        if _contains_absolute_path(value):
            errors.append(f"{path}: absolute host paths are not allowed")
    if errors:
        raise ToolRoundSummaryValidationError("summary validation failed:\n" + "\n".join(f"- {error}" for error in errors[:20]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT, help="root used to resolve workspace-relative evidence paths")
    args = parser.parse_args()
    try:
        summary_path = _resolve_summary_input(args.root, args.summary)
        validate_payload(_load_json(summary_path), root=args.root)
    except (ToolRoundSummaryValidationError, OSError, ValueError) as exc:
        print(_redact_diagnostic(str(exc)), file=sys.stderr)
        return 2
    print("model-visible-tool-round-summary.v1: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

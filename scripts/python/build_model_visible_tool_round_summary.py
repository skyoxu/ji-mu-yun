#!/usr/bin/env python
"""Build an ADR-0038-aligned tool round summary from an operation ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

from validate_model_visible_tool_round_summary import (
    ToolRoundSummaryValidationError,
    _redact_diagnostic,
    _reject_duplicate_json_pairs,
    _reject_reparse_components,
    _safe_workspace_root,
    retry_count,
    validate_payload,
)
from skill_input_consumption import is_reparse_point


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_json_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ToolRoundSummaryValidationError(f"invalid input JSON ({path.name}): {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise ToolRoundSummaryValidationError("input ledger must be an object")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _relative_path(root: Path, raw: str) -> Path:
    normalized = raw.replace("\\", "/")
    if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized) or "://" in normalized or any(part == ".." for part in normalized.split("/")):
        raise ToolRoundSummaryValidationError("evidence path must be workspace-relative")
    resolved_root = _safe_workspace_root(root)
    joined = resolved_root.joinpath(*normalized.split("/"))
    _reject_reparse_components(joined, stop=resolved_root)
    if is_reparse_point(joined):
        raise ToolRoundSummaryValidationError("evidence path may not be a symlink or reparse point")
    resolved = joined.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ToolRoundSummaryValidationError("evidence path escapes workspace root") from exc
    return resolved


def _canonical_evidence_refs(raw_refs: Any, root: Path, run_id: str, turn_id: str, scope: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(raw_refs, list):
        raise ToolRoundSummaryValidationError("evidence_refs must be an array")
    refs: list[dict[str, Any]] = []
    for raw in raw_refs:
        if not isinstance(raw, dict):
            raise ToolRoundSummaryValidationError("each evidence ref must be an object")
        item = dict(raw)
        if "ref_id" not in item or "kind" not in item:
            raise ToolRoundSummaryValidationError("evidence refs require ref_id and kind")
        if item.get("run_id", run_id) != run_id or item.get("turn_id", turn_id) != turn_id:
            raise ToolRoundSummaryValidationError("evidence ref run/turn binding mismatch")
        if item.get("scope_kind", scope.get("scope_kind")) != scope.get("scope_kind") or item.get("scope_ref", scope.get("scope_ref")) != scope.get("scope_ref"):
            raise ToolRoundSummaryValidationError("evidence ref scope binding mismatch")
        item["run_id"] = run_id
        item["turn_id"] = turn_id
        item["scope_kind"] = scope.get("scope_kind")
        item["scope_ref"] = scope.get("scope_ref")
        if "path" in item:
            if not isinstance(item.get("path"), str):
                raise ToolRoundSummaryValidationError("evidence path must be a string")
            item.setdefault("owner", "toolchain")
            if not isinstance(item.get("owner"), str) or not item["owner"] or item["owner"] == "unknown":
                raise ToolRoundSummaryValidationError("evidence ref owner is required")
            path = _relative_path(root, str(item["path"]))
            if not path.is_file():
                raise ToolRoundSummaryValidationError("evidence file does not exist")
            digest = _sha256(path)
            supplied = item.get("sha256")
            if supplied is not None and supplied != digest:
                raise ToolRoundSummaryValidationError("evidence hash mismatch")
            item["sha256"] = digest
            item["hash_status"] = "verified"
        elif "artifact_id" in item:
            if not isinstance(item.get("artifact_id"), str):
                raise ToolRoundSummaryValidationError("artifact_id must be a string")
            if not isinstance(item.get("owner"), str) or not item["owner"] or item["owner"] == "unknown":
                raise ToolRoundSummaryValidationError("external artifact owner is required")
            if not isinstance(item.get("sha256"), str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", item["sha256"]):
                raise ToolRoundSummaryValidationError("external artifact requires a sha256 attestation")
            # A provider-owned artifact has no locally reproducible hash attestation in v1.
            item["hash_status"] = "external-unverified"
        else:
            raise ToolRoundSummaryValidationError("evidence ref requires path or artifact_id")
        refs.append(item)
    return sorted(refs, key=lambda item: str(item.get("ref_id", "")))


def _normalise_errors(raw_errors: Any) -> list[dict[str, Any]]:
    if raw_errors is None:
        return []
    if not isinstance(raw_errors, list):
        raise ToolRoundSummaryValidationError("errors must be an array of structured objects")
    errors: list[dict[str, Any]] = []
    for item in raw_errors:
        if not isinstance(item, dict):
            raise ToolRoundSummaryValidationError("errors must use structured objects, not free text")
        errors.append(dict(item))
    return sorted(errors, key=lambda item: (str(item.get("operation_id") or ""), str(item.get("code") or "")))


def _derive_status(
    operations: list[dict[str, Any]],
    continuation: dict[str, Any],
    errors: list[dict[str, Any]],
    preflight: dict[str, Any],
    evidence_refs: list[dict[str, Any]],
) -> str:
    if any(item.get("status") == "failed" for item in operations) or any(item.get("severity") in {"error", "fatal"} for item in errors):
        return "failed"
    if any(item.get("status") == "interrupted" for item in operations):
        return "interrupted"
    if any(item.get("status") == "blocked" for item in operations):
        return "blocked"
    if preflight.get("parallelization_allowed") is False and any(item.get("execution_mode") == "parallel" for item in operations):
        return "blocked"
    if continuation.get("has_more") is True or any(item.get("status") == "partial" for item in operations) or errors:
        return "partial"
    if any(item.get("hash_status") == "external-unverified" for item in evidence_refs):
        return "partial"
    return "complete"


def build(ledger: dict[str, Any], root: Path) -> dict[str, Any]:
    run_id = ledger.get("run_id")
    turn_id = ledger.get("turn_id")
    if not isinstance(run_id, str) or not isinstance(turn_id, str):
        raise ToolRoundSummaryValidationError("run_id and turn_id are required")

    raw_operations = ledger.get("operations")
    if not isinstance(raw_operations, list):
        raise ToolRoundSummaryValidationError("operations must be an array")
    if any(not isinstance(item, dict) for item in raw_operations):
        raise ToolRoundSummaryValidationError("every operation must be an object")
    operations = [dict(item) for item in sorted(raw_operations, key=lambda item: str(item.get("operation_id", "")))]
    scope = ledger.get("scope")
    if not isinstance(scope, dict):
        raise ToolRoundSummaryValidationError("scope must be an object")
    for operation in operations:
        # Scope is copied only when omitted; a conflicting caller assertion is rejected by the validator.
        operation.setdefault("scope", dict(scope))
        operation.setdefault("parent_tool_call_id", None)
        operation.setdefault("background_lifecycle", None)

    raw_round_events = ledger.get("round_events")
    if not isinstance(raw_round_events, list):
        raise ToolRoundSummaryValidationError("round_events must be supplied; model_visible_rounds is never accepted as a fact")
    if any(not isinstance(item, dict) for item in raw_round_events):
        raise ToolRoundSummaryValidationError("every round event must be an object")
    round_events = [dict(item) for item in sorted(raw_round_events, key=lambda item: str(item.get("round_id", "")))]

    continuation = ledger.get("continuation", {"has_more": False, "offsets": []})
    if not isinstance(continuation, dict):
        raise ToolRoundSummaryValidationError("continuation must be an object")
    errors = _normalise_errors(ledger.get("errors", []))
    evidence_refs = _canonical_evidence_refs(ledger.get("evidence_refs", []), root, run_id, turn_id, scope)
    evidence_by_id = {item["ref_id"]: item for item in evidence_refs}
    for operation in operations:
        reference = evidence_by_id.get(operation.get("evidence_ref"))
        if reference and "path" in reference:
            evidence_path = _relative_path(root, str(reference["path"]))
            operation["persisted_output_bytes"] = evidence_path.stat().st_size

    measurement = dict(ledger.get("measurement", {"rounds": "observed", "tokens": "estimated", "rounds_evidence_ref": None, "tokens_evidence_ref": None}))
    if not isinstance(measurement, dict):
        raise ToolRoundSummaryValidationError("measurement must be an object")
    measurement.setdefault("rounds_evidence_ref", None)
    measurement.setdefault("tokens_evidence_ref", None)
    visible_result_bytes = sum(int(item.get("visible_result_bytes", 0)) for item in operations)
    if measurement.get("tokens") == "estimated":
        visible_result_tokens = (visible_result_bytes + 3) // 4
    elif measurement.get("tokens") == "unknown":
        visible_result_tokens = 0
    else:
        visible_result_tokens = int(ledger.get("visible_result_tokens", 0))
    # round_events, rather than a caller-provided aggregate, is the only round fact.
    model_visible_rounds = 0 if measurement.get("rounds") == "unknown" else len(round_events)
    metrics = {
        "model_visible_rounds": model_visible_rounds,
        "underlying_tool_calls": sum(int(item.get("attempts", 0)) for item in operations),
        "parallel_groups": len({item.get("group_id") for item in operations if item.get("execution_mode") == "parallel" and item.get("group_id") is not None}),
        "sequential_calls": sum(item.get("execution_mode") == "sequential" for item in operations),
        "background_calls": sum(item.get("execution_mode") == "background" for item in operations),
        "retries": sum(retry_count(item.get("attempts", 0)) for item in operations),
        "visible_result_bytes": visible_result_bytes,
        "visible_result_tokens": visible_result_tokens,
        "persisted_output_bytes": sum(int(item.get("persisted_output_bytes", 0)) for item in operations),
        "partial_results": sum(item.get("status") == "partial" for item in operations),
        "failed_calls": sum(item.get("status") == "failed" for item in operations),
        "interrupted_calls": sum(item.get("status") == "interrupted" for item in operations),
        "blocked_calls": sum(item.get("status") == "blocked" for item in operations),
    }
    preflight = ledger.get("preflight")
    if not isinstance(preflight, dict):
        needs_parallel_preflight = any(item.get("execution_mode") == "parallel" for item in operations)
        preflight = {
            "same_scope_verified": False,
            "authorization_verified": False,
            "secret_redaction_verified": False,
            "parallelization_allowed": False,
            "block_reason": "preflight_not_provided" if needs_parallel_preflight else None,
            "evidence_ref": None,
        }
    raw_boundaries = ledger.get("external_boundaries", [])
    if not isinstance(raw_boundaries, list) or any(not isinstance(item, dict) for item in raw_boundaries):
        raise ToolRoundSummaryValidationError("external_boundaries must be an array of objects")
    external_boundaries = sorted((dict(item) for item in raw_boundaries), key=lambda item: str(item.get("boundary", "")))
    payload = {
        "schema_version": "model-visible-tool-round-summary.v1",
        "status": _derive_status(operations, continuation, errors, preflight, evidence_refs),
        "run_id": run_id,
        "turn_id": turn_id,
        "parent_turn_id": ledger.get("parent_turn_id"),
        "scope": scope,
        "timing": ledger.get("timing"),
        "measurement": measurement,
        "metrics": metrics,
        "preflight": preflight,
        "round_events": round_events,
        "operations": operations,
        "continuation": continuation,
        "evidence_refs": evidence_refs,
        "external_boundaries": external_boundaries,
        "errors": errors,
    }
    validate_payload(payload, root=root)
    return payload


def _safe_output_ref(output: Path, root: Path) -> str:
    try:
        return output.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return "artifact:" + output.name


def _authorized_workspace_path(path: Path, root: Path) -> Path:
    resolved_root = _safe_workspace_root(root)
    raw_output = path if path.is_absolute() else (resolved_root / path)
    _reject_reparse_components(raw_output, stop=resolved_root)
    if is_reparse_point(raw_output):
        raise ToolRoundSummaryValidationError("output path may not be a symlink or reparse point")
    resolved_output = raw_output.resolve()
    try:
        resolved_output.relative_to(resolved_root)
    except ValueError as exc:
        raise ToolRoundSummaryValidationError("output path must be inside the workspace root") from exc
    return resolved_output


def _safe_error(exc: BaseException) -> str:
    # Do not disclose host paths from OSError/JSON parser messages on stdout/stderr.
    message = _redact_diagnostic(str(exc))
    message = re.sub(r"(?i)[A-Za-z]:[\\/][^\n'\";]+", "<path>", message)
    message = re.sub(r"\\\\[^\n'\";]+", "<path>", message)
    message = re.sub(r"(?<![A-Za-z0-9])/(?!/)[^\s'\"]+", "<path>", message)
    return message[:500]


def _atomic_write_json(output: Path, payload: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        if output.exists() or output.is_symlink() or is_reparse_point(output):
            raise FileExistsError("summary output already exists; use a new append-only evidence path")
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Hard-link publication is atomic and fails if another writer won the path.
        os.link(temporary, output)
    finally:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        input_path = _authorized_workspace_path(args.input, args.root)
        payload = build(_load(input_path), args.root)
        output_path = _authorized_workspace_path(args.output, args.root)
        _atomic_write_json(output_path, payload)
    except (OSError, ValueError, TypeError, ToolRoundSummaryValidationError) as exc:
        print(f"model-visible tool round summary build failed: {_safe_error(exc)}", file=sys.stderr)
        return 2
    print(json.dumps({"status": payload["status"], "output_ref": _safe_output_ref(output_path, args.root)}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

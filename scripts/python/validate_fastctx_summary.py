#!/usr/bin/env python
"""Validate a bounded FastCtx summary without exposing raw source output."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "scripts" / "sc" / "schemas" / "fastctx-summary.v1.schema.json"

try:
    import jsonschema  # type: ignore
except ImportError:  # pragma: no cover
    jsonschema = None


class SummaryValidationError(ValueError):
    pass


MAX_SUMMARY_BYTES = 12000
MAX_SUMMARY_TOKENS = 3000


UNREDACTED_SECRET_PATTERN = re.compile(
    r"(?i)(token|secret|password|api[_-]?key|authorization)\s*[\"']?\s*[:=]\s*[\"']?(?!<redacted(?:-api-key)?>)[^\s,;\"']+"
)
UNREDACTED_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+(?!<redacted>)[A-Za-z0-9._~+/-]+=*")
UNREDACTED_API_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SummaryValidationError(f"invalid JSON input: {path}: {exc}") from exc


def _serialized_size(payload: dict[str, Any]) -> int:
    return len((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _enforce_transport_budget(payload: dict[str, Any]) -> None:
    size = _serialized_size(payload)
    if size > MAX_SUMMARY_BYTES:
        raise SummaryValidationError(f"summary exceeds serialized byte limit: {size}>{MAX_SUMMARY_BYTES}")
    estimated_tokens = (size + 3) // 4
    if estimated_tokens > MAX_SUMMARY_TOKENS:
        raise SummaryValidationError(
            f"summary exceeds transport token estimate: {estimated_tokens}>{MAX_SUMMARY_TOKENS}"
        )


def _fallback_errors(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["$: expected an object"]
    required = {
        "schema_version",
        "status",
        "source",
        "query",
        "stats",
        "findings",
        "offsets",
        "truncated",
        "omitted_records",
        "generated_at",
        "errors",
    }
    unknown = sorted(set(payload) - required)
    errors.extend(f"$.{key}: unknown property" for key in unknown)
    for key in sorted(required - payload.keys()):
        errors.append(f"$.{key}: required property is missing")
    if payload.get("schema_version") != "fastctx-summary.v1":
        errors.append("$.schema_version: must be fastctx-summary.v1")
    status = payload.get("status")
    if not isinstance(status, str) or status not in {"complete", "partial", "failed"}:
        errors.append("$.status: invalid status")
    source = payload.get("source")
    if not isinstance(source, dict):
        errors.append("$.source: expected an object")
    else:
        source_required = {"path", "kind", "sha256"}
        errors.extend(f"$.source.{key}: unknown property" for key in sorted(set(source) - source_required))
        for key in source_required:
            if key not in source:
                errors.append(f"$.source.{key}: required property is missing")
        if not isinstance(source.get("path"), str) or not source.get("path"):
            errors.append("$.source.path: expected a non-empty string")
        if source.get("kind") not in {"jsonl", "log", "text"}:
            errors.append("$.source.kind: invalid kind")
        digest = source.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            errors.append("$.source.sha256: expected sha256:<64 lowercase hex>")
    stats = payload.get("stats")
    if not isinstance(stats, dict):
        errors.append("$.stats: expected an object")
    else:
        stats_required = {"records", "bytes", "max_input_tokens"}
        errors.extend(f"$.stats.{key}: unknown property" for key in sorted(set(stats) - stats_required))
        for key in ("records", "bytes", "max_input_tokens"):
            if type(stats.get(key)) is not int or stats.get(key, -1) < 0:
                errors.append(f"$.stats.{key}: expected a non-negative integer")
    if not isinstance(payload.get("query"), dict):
        errors.append("$.query: expected an object")
    findings = payload.get("findings")
    if not isinstance(findings, list) or len(findings) > 200 or any(not isinstance(item, dict) for item in findings):
        errors.append("$.findings: expected an array with at most 200 entries")
    elif findings:
        for index, finding in enumerate(findings):
            allowed = {"line", "kind", "sample"}
            errors.extend(f"$.findings[{index}].{key}: unknown property" for key in sorted(set(finding) - allowed))
            if type(finding.get("line")) is not int or finding.get("line", 0) < 1:
                errors.append(f"$.findings[{index}].line: expected a positive integer")
            if not isinstance(finding.get("kind"), str) or not finding.get("kind"):
                errors.append(f"$.findings[{index}].kind: expected a non-empty string")
            sample = finding.get("sample")
            if sample is not None and (not isinstance(sample, str) or len(sample) > 240):
                errors.append(f"$.findings[{index}].sample: expected a string of at most 240 characters")
            if isinstance(sample, str) and (
                UNREDACTED_SECRET_PATTERN.search(sample)
                or UNREDACTED_BEARER_PATTERN.search(sample)
                or UNREDACTED_API_KEY_PATTERN.search(sample)
            ):
                errors.append(f"$.findings[{index}].sample: contains an unredacted credential")
    offsets = payload.get("offsets")
    if not isinstance(offsets, list):
        errors.append("$.offsets: expected an array")
    else:
        for index, offset in enumerate(offsets):
            if not isinstance(offset, dict):
                errors.append(f"$.offsets[{index}]: expected an object")
                continue
            allowed = {"unit", "next"}
            errors.extend(f"$.offsets[{index}].{key}: unknown property" for key in sorted(set(offset) - allowed))
            if offset.get("unit") not in {"line", "record", "byte"}:
                errors.append(f"$.offsets[{index}].unit: invalid unit")
            if type(offset.get("next")) is not int or offset.get("next", -1) < 0:
                errors.append(f"$.offsets[{index}].next: expected a non-negative integer")
    if type(payload.get("truncated")) is not bool:
        errors.append("$.truncated: expected a boolean")
    if type(payload.get("omitted_records")) is not int or payload.get("omitted_records", -1) < 0:
        errors.append("$.omitted_records: expected a non-negative integer")
    if not isinstance(payload.get("generated_at"), str) or not payload.get("generated_at"):
        errors.append("$.generated_at: expected a non-empty string")
    summary_errors = payload.get("errors")
    if not isinstance(summary_errors, list) or any(not isinstance(item, str) or not item for item in summary_errors):
        errors.append("$.errors: expected an array of non-empty strings")
    elif summary_errors:
        for index, error in enumerate(summary_errors):
            if len(error) > 240:
                errors.append(f"$.errors[{index}]: expected at most 240 characters")
            if (
                UNREDACTED_SECRET_PATTERN.search(error)
                or UNREDACTED_BEARER_PATTERN.search(error)
                or UNREDACTED_API_KEY_PATTERN.search(error)
            ):
                errors.append(f"$.errors[{index}]: contains an unredacted credential")
    if status == "complete" and (payload.get("truncated") is not False or payload.get("omitted_records") != 0 or summary_errors):
        errors.append("$: complete summaries cannot be truncated, omit records, or contain errors")
    if status == "partial" and (payload.get("truncated") is not True or not payload.get("offsets")):
        errors.append("$: partial summaries require truncation and continuation offsets")
    if status == "failed" and not payload.get("errors"):
        errors.append("$: failed summaries require errors")
    return errors


def validate_payload(payload: Any) -> None:
    if jsonschema is not None:
        schema = _load_json(SCHEMA_PATH)
        errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(payload), key=lambda error: list(error.path))
        if errors:
            raise SummaryValidationError("summary schema validation failed:\n" + "\n".join(f"- {error.message}" for error in errors[:20]))
        sensitive_errors = _fallback_errors(payload)
        sensitive_errors = [
            error
            for error in sensitive_errors
            if ("findings" in error or "$.errors" in error)
            and ("unknown property" in error or "credential" in error or "at most 240" in error)
        ]
        if sensitive_errors:
            raise SummaryValidationError("summary validation failed:\n" + "\n".join(f"- {error}" for error in sensitive_errors[:20]))
        _enforce_transport_budget(payload)
        return
    errors = _fallback_errors(payload)
    if errors:
        raise SummaryValidationError("summary validation failed:\n" + "\n".join(f"- {error}" for error in errors[:20]))
    _enforce_transport_budget(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    args = parser.parse_args()
    try:
        validate_payload(_load_json(args.summary))
    except SummaryValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print("fastctx-summary.v1: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

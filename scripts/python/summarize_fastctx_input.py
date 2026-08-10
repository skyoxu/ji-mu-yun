#!/usr/bin/env python
"""Aggregate a text, log, or JSONL source into a bounded FastCtx summary."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from validate_fastctx_summary import SummaryValidationError, validate_payload


DEFAULT_PATTERN = r"(?i)(error|exception|traceback|failed|warning)"
DEFAULT_MAX_SUMMARY_TOKENS = 3000
SECRET_PATTERN = re.compile(
    r"(?i)(token|secret|password|api[_-]?key|authorization)\s*[\"']?\s*[:=]\s*[\"']?(\"[^\"\r\n]*\"|'[^'\r\n]*'|[^,\r\n;]+)"
)
BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")
API_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")


def _redact(value: str) -> str:
    # Remove complete bearer/API credentials before generic key/value masking;
    # otherwise the generic matcher can consume the ``Bearer`` marker first.
    value = BEARER_PATTERN.sub("Bearer <redacted>", value)
    value = API_KEY_PATTERN.sub("<redacted-api-key>", value)
    value = SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=<redacted>", value)
    return value[:240]


def _iter_lines(path: Path) -> Iterable[tuple[int, bytes]]:
    with path.open("rb") as handle:
        for line_no, raw in enumerate(handle, 1):
            yield line_no, raw


def _summary_payload(
    *,
    source: Path,
    kind: str,
    source_hash: str,
    pattern: str,
    records: int,
    total_bytes: int,
    max_input_tokens: int,
    findings: list[dict[str, Any]],
    errors: list[str],
    truncated: bool,
    omitted_records: int,
    next_offset: int | None,
) -> dict[str, Any]:
    status = "failed" if errors else ("partial" if truncated else "complete")
    return {
        "schema_version": "fastctx-summary.v1",
        "status": status,
        "source": {"path": source.as_posix(), "kind": kind, "sha256": f"sha256:{source_hash}"},
        "query": {"pattern": pattern[:200], "kind": kind},
        "stats": {
            "records": records,
            "bytes": total_bytes,
            "max_input_tokens": max_input_tokens,
        },
        "findings": findings,
        "offsets": [] if next_offset is None else [{"unit": "line", "next": next_offset}],
        "truncated": truncated,
        "omitted_records": omitted_records,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "errors": errors,
    }


def _encoded_size(payload: dict[str, Any]) -> int:
    return len(_serialize_payload(payload))


def _serialize_payload(payload: dict[str, Any]) -> bytes:
    """Serialize exactly as the CLI writes the artifact, including newline."""
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _estimated_summary_tokens(payload: dict[str, Any]) -> int:
    return (len(_serialize_payload(payload)) + 3) // 4


def _over_budget(payload: dict[str, Any], max_summary_bytes: int) -> bool:
    return _encoded_size(payload) > max_summary_bytes or _estimated_summary_tokens(payload) > DEFAULT_MAX_SUMMARY_TOKENS


def _set_continuation_offset(payload: dict[str, Any], line_no: int) -> None:
    offsets = payload["offsets"]
    if offsets:
        offsets[0]["next"] = min(int(offsets[0]["next"]), line_no)
    else:
        offsets.append({"unit": "line", "next": line_no})


def summarize(
    source: Path,
    *,
    kind: str,
    pattern: str,
    max_findings: int,
    max_summary_bytes: int,
) -> dict[str, Any]:
    matcher = re.compile(pattern)
    digest = hashlib.sha256()
    findings: list[dict[str, Any]] = []
    errors: list[str] = []
    records = 0
    total_bytes = 0
    max_input_tokens = 0
    omitted_records = 0
    first_omitted_line: int | None = None

    try:
        lines = _iter_lines(source)
        for line_no, raw in lines:
            digest.update(raw)
            total_bytes += len(raw)
            records += 1
            try:
                text = raw.decode("utf-8").rstrip("\r\n")
            except UnicodeDecodeError as exc:
                errors.append(f"line {line_no}: invalid UTF-8 ({exc.start})")
                continue
            max_input_tokens = max(max_input_tokens, (len(text) + 3) // 4)
            if kind == "jsonl":
                try:
                    json.loads(text)
                except json.JSONDecodeError:
                    findings.append({"line": line_no, "kind": "invalid_json"})
            if matcher.search(text):
                findings.append(
                    {
                        "line": line_no,
                        "kind": "match",
                        "sample": _redact(text),
                    }
                )
    except OSError as exc:
        errors.append(f"source read failed: {exc}")

    max_findings = min(max_findings, 200)
    if len(findings) > max_findings:
        omitted_records += len(findings) - max_findings
        first_omitted_line = findings[max_findings].get("line")
        findings = findings[:max_findings]

    payload = _summary_payload(
        source=source,
        kind=kind,
        source_hash=digest.hexdigest(),
        pattern=pattern,
        records=records,
        total_bytes=total_bytes,
        max_input_tokens=max_input_tokens,
        findings=findings,
        errors=errors,
        truncated=first_omitted_line is not None,
        omitted_records=omitted_records,
        next_offset=first_omitted_line,
    )

    while _over_budget(payload, max_summary_bytes) and payload["findings"]:
        removed = payload["findings"].pop()
        payload["truncated"] = True
        payload["status"] = "partial"
        payload["omitted_records"] += 1
        _set_continuation_offset(payload, int(removed["line"]))

    if _over_budget(payload, max_summary_bytes):
        payload["findings"] = []
        payload["truncated"] = True
        payload["status"] = "partial" if not errors else "failed"
        payload["omitted_records"] = max(1, int(payload["omitted_records"]))
        _set_continuation_offset(payload, 1)

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--kind", choices=("jsonl", "log", "text"), default="text")
    parser.add_argument("--pattern", default=DEFAULT_PATTERN)
    parser.add_argument("--max-findings", type=int, default=100)
    parser.add_argument("--max-summary-bytes", type=int, default=12000)
    args = parser.parse_args()
    if args.max_findings < 0 or args.max_summary_bytes < 512 or args.max_summary_bytes > 12000:
        parser.error("max-findings must be non-negative and max-summary-bytes must be 512..12000")
    if not args.source.is_file():
        print("source must be an existing file", file=sys.stderr)
        return 2
    try:
        payload = summarize(
            args.source.resolve(),
            kind=args.kind,
            pattern=args.pattern,
            max_findings=args.max_findings,
            max_summary_bytes=args.max_summary_bytes,
        )
    except re.error as exc:
        print(f"invalid pattern: {exc}", file=sys.stderr)
        return 2
    try:
        validate_payload(payload)
    except SummaryValidationError as exc:
        print(f"summary generation failed validation: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_serialize_payload(payload))
    print(json.dumps({"status": payload["status"], "output": args.output.as_posix()}, separators=(",", ":")))
    return 0 if payload["status"] != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

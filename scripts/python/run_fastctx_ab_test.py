#!/usr/bin/env python
"""Run a deterministic bounded-reader versus FastCtx-contract benchmark."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUMMARY_SCRIPT = ROOT / "scripts" / "python" / "summarize_fastctx_input.py"
VALIDATOR_SCRIPT = ROOT / "scripts" / "python" / "validate_fastctx_summary.py"


def _token_estimate(byte_count: int) -> int:
    return max(1, (byte_count + 3) // 4) if byte_count else 0


def _write(path: Path, payload: bytes) -> dict[str, object]:
    path.write_bytes(payload)
    return {"status": "written", "path": path.as_posix()}


def _native_read(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {"status": "complete", "path": path.as_posix(), "bytes": len(payload), "tokens": _token_estimate(len(payload))}


def _fastctx_read(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    visible = payload[:12000]
    return {
        "schema_version": "fastctx-read-result.v1",
        "status": "complete" if len(visible) == len(payload) else "partial",
        "source": {"path": path.as_posix(), "sha256": "sha256:" + __import__("hashlib").sha256(payload).hexdigest()},
        "content": visible.decode("utf-8"),
        "bytes": len(visible),
        "tokens": _token_estimate(len(visible) + 220),
        "truncated": len(visible) != len(payload),
    }


def _operation_summary(item: dict[str, object]) -> dict[str, object]:
    read = item["read"]
    return {
        "write_status": item["write"]["status"],
        "read_status": read["status"],
        "read_bytes": read["bytes"],
        "read_estimated_tokens": read["tokens"],
        "read_truncated": bool(read.get("truncated", False)),
    }


def _run_summary(source: Path, output: Path) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, str(SUMMARY_SCRIPT), "--source", str(source), "--kind", "jsonl", "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"summary generation failed: {completed.stderr.strip()}")
    validated = subprocess.run(
        [sys.executable, str(VALIDATOR_SCRIPT), str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if validated.returncode != 0:
        raise RuntimeError(f"summary validation failed: {validated.stderr.strip()}")
    return json.loads(output.read_text(encoding="utf-8"))


def run(iterations: int) -> dict[str, object]:
    if iterations != 5:
        raise ValueError("the acceptance benchmark requires exactly five read/write iterations")
    with tempfile.TemporaryDirectory(prefix="fastctx-ab-") as temporary:
        root = Path(temporary)
        source = root / "fixture.txt"
        payload = ("line-0001\n" + "".join(f"line-{index:04d}: bounded fixture content\n" for index in range(2, 221))).encode("utf-8")
        native: list[dict[str, object]] = []
        fastctx: list[dict[str, object]] = []
        for index in range(iterations):
            native.append({"write": _write(source, payload), "read": _native_read(source)})
        for index in range(iterations):
            fastctx.append({"write": {"schema_version": "fastctx-write-result.v1", "status": _write(source, payload)["status"], "path": source.as_posix()}, "read": _fastctx_read(source)})
        jsonl = root / "diagnostic.jsonl"
        with jsonl.open("w", encoding="utf-8", newline="\n") as stream:
            for index in range(600):
                stream.write(json.dumps({"seq": index, "level": "ERROR" if index % 37 == 0 else "INFO", "message": "diagnostic fixture", "token": "sk-test-secret-value"}, separators=(",", ":")) + "\n")
        summary_path = root / "summary.json"
        summary = _run_summary(jsonl, summary_path)
        native_bytes = sum(int(item["read"]["bytes"]) for item in native)
        fastctx_bytes = sum(int(item["read"]["bytes"]) for item in fastctx)
        native_tokens = sum(int(item["read"]["tokens"]) for item in native)
        fastctx_tokens = sum(int(item["read"]["tokens"]) for item in fastctx)
        return {
            "schema_version": "fastctx-ab-test.v1",
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "measurement_kind": "repository-controlled-transport-policy-benchmark",
            "limitations": ["does not measure outer functions.exec serialization or Codex server token accounting"],
            "iterations": {"reads": iterations, "writes": iterations},
            "fixture": {"bytes": len(payload), "lines": payload.count(b"\n")},
            "baseline": {"strategy": "bounded-reader-baseline", "read_visible_bytes": native_bytes, "read_estimated_tokens": native_tokens, "operations": [_operation_summary(item) for item in native]},
            "fastctx_contract": {"strategy": "fastctx-bounded-result", "read_visible_bytes": fastctx_bytes, "read_estimated_tokens": fastctx_tokens, "operations": [_operation_summary(item) for item in fastctx]},
            "delta": {"bytes": fastctx_bytes - native_bytes, "estimated_tokens": fastctx_tokens - native_tokens},
            "high_output_summary": {"status": summary["status"], "source_records": summary["stats"]["records"], "summary_bytes": len(summary_path.read_bytes()), "summary_estimated_tokens": _token_estimate(len(summary_path.read_bytes())), "truncated": summary["truncated"], "omitted_records": summary["omitted_records"], "redaction_verified": any(marker in summary_path.read_text(encoding="utf-8") for marker in ("<redacted>", "<redacted-api-key>"))},
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()
    try:
        result = run(args.iterations)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"fastctx A/B test failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "complete", "output": args.output.resolve().as_posix()}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

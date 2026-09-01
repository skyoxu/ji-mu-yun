#!/usr/bin/env python3
"""Verify all Chapter 4/5/6 final evidence is bound to current candidate HEAD.

This step is intentionally read-only with respect to evidence. Deterministic
metrics must be produced through the fixed candidate-bound metric runner, while
live metrics bind themselves. Missing or mismatched source_head fails closed;
this verifier never promotes unbound bytes into current-candidate evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

SCHEMA = "ch456.final-evidence-candidate-seal.v1"


def _head() -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], text=True, capture_output=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"evidence must be a JSON object: {path}")
    return value


def seal(paths: list[Path], candidate_head: str) -> dict[str, Any]:
    if not candidate_head:
        raise ValueError("current git HEAD is unavailable")
    if not paths:
        raise ValueError("at least one evidence path is required")
    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for raw in paths:
        path = raw.resolve()
        if path in seen:
            raise ValueError(f"duplicate evidence path: {path}")
        seen.add(path)
        if not path.is_file():
            raise ValueError(f"missing evidence: {path}")
        value = _load(path)
        source_head = value.get("source_head")
        if not isinstance(source_head, str) or not source_head:
            raise ValueError(f"unsealed evidence: {path}: missing source_head")
        if source_head != candidate_head:
            raise ValueError(f"candidate binding mismatch: {path}: {source_head} != {candidate_head}")
        rows.append({
            "path": str(path),
            "schema": value.get("schema"),
            "source_head": source_head,
            "candidate_metric_producer": value.get("candidate_metric_producer"),
        })
    return {
        "schema": SCHEMA,
        "status": "pass",
        "candidate_head": candidate_head,
        "sealed_count": len(rows),
        "evidence": rows,
        "writes_performed": False,
        "authorizes": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", action="append", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        result = seal(list(args.evidence), _head())
        code = 0
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        result = {
            "schema": SCHEMA,
            "status": "blocked",
            "candidate_head": _head(),
            "writes_performed": False,
            "error": str(exc),
            "authorizes": [],
        }
        code = 1
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

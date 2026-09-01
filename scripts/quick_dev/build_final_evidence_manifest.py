#!/usr/bin/env python3
"""Freeze one Chapter 4/5/6 final-evidence set against the current candidate.

The manifest prevents the strict final-completion predicate from accidentally
mixing stale evidence from another local/CI run.  It binds the current git HEAD
to the exact bytes of every required evidence artifact.  Evidence that already
carries a source_head must agree with the same candidate before it can enter the
manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

SCHEMA = "ch456.final-evidence-manifest.v1"
REQUIRED = (
    "architecture_reconcile",
    "curated_semantic",
    "semantic_chain_mutations",
    "agent_context_mutations",
    "real_semantic",
    "stable_facade",
    "detached_mutations",
    "selective_replay",
    "live_blind",
    "legacy_replay",
)


def _head() -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], text=True, capture_output=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"evidence must be a JSON object: {path}")
    return value


def build(candidate_head: str, paths: dict[str, Path]) -> dict[str, Any]:
    if not candidate_head:
        raise ValueError("current git HEAD is unavailable")
    if set(paths) != set(REQUIRED):
        missing = sorted(set(REQUIRED) - set(paths))
        extra = sorted(set(paths) - set(REQUIRED))
        raise ValueError(f"evidence key mismatch: missing={missing} extra={extra}")

    evidence: dict[str, Any] = {}
    for key in REQUIRED:
        path = paths[key].resolve()
        if not path.is_file():
            raise ValueError(f"missing evidence: {key}: {path}")
        value = _load(path)
        source_head = value.get("source_head")
        if source_head is not None and str(source_head) != candidate_head:
            raise ValueError(f"candidate binding mismatch: {key}: {source_head} != {candidate_head}")
        evidence[key] = {
            "path": str(path),
            "sha256": _sha256(path),
            "schema": value.get("schema"),
            "source_head": source_head,
        }

    return {
        "schema": SCHEMA,
        "candidate_head": candidate_head,
        "required_evidence_keys": list(REQUIRED),
        "evidence": evidence,
        "authorizes": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    for key in REQUIRED:
        parser.add_argument("--" + key.replace("_", "-"), dest=key, type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("ch456-final-evidence-manifest.json"))
    args = parser.parse_args()
    try:
        paths = {key: getattr(args, key) for key in REQUIRED}
        result = build(_head(), paths)
        exit_code = 0
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        result = {
            "schema": SCHEMA,
            "candidate_head": _head(),
            "status": "blocked",
            "error": str(exc),
            "authorizes": [],
        }
        exit_code = 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

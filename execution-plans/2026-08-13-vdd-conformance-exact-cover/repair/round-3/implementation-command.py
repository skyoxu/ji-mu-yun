"""Registered Exact-cover implementation entry points.

These commands deliberately fail closed until the implementation evidence
contract exists. They must never report a green implementation result merely
because the plan metadata is internally consistent.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"
EVIDENCE = PLAN / "implementation-evidence.v1.json"

COMMANDS = {
    "vdd-source-freeze",
    "vdd-source-freeze-negative",
    "semantic-handoff",
    "semantic-handoff-negative",
    "authorization-preflight",
    "authorization-preflight-negative",
    "composition-negative",
    "retry-taxonomy",
    "retry-taxonomy-negative",
    "fingerprint-shard",
    "fingerprint-shard-negative",
    "exact-cover",
    "exact-cover-negative",
    "recovery-context",
    "recovery-context-negative",
}


def _load_evidence() -> dict:
    if not EVIDENCE.is_file():
        raise RuntimeError("implementation evidence is not present")
    value = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    if value.get("schema_version") != "vdd-exact-cover-implementation-evidence.v1":
        raise RuntimeError("implementation evidence schema is invalid")
    if value.get("status") != "implementation-ready":
        raise RuntimeError("implementation evidence is not ready")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True, choices=sorted(COMMANDS))
    parser.add_argument("--terminal-full", action="store_true")
    args = parser.parse_args()
    try:
        evidence = _load_evidence()
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"implementation-command=blocked command={args.command} reason={exc}")
        return 2
    accepted = set(evidence.get("implemented_commands", []))
    command_evidence = evidence.get("commands", {}).get(args.command)
    if args.command not in accepted or not isinstance(command_evidence, dict):
        print(f"implementation-command=blocked command={args.command} reason=command-not-evidenced")
        return 2
    if command_evidence.get("status") != "passed" or not command_evidence.get("acceptance_ids") or not command_evidence.get("validation_reference"):
        print(f"implementation-command=blocked command={args.command} reason=command-receipt-incomplete")
        return 2
    print(f"implementation-command=ready command={args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

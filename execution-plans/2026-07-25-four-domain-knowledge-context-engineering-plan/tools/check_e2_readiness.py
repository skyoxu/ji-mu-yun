#!/usr/bin/env python3
"""Compute E2 release readiness from the current generated Hosted inventories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PLAN_DIR = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(inventory_dir: Path) -> dict[str, object]:
    ledger = load_json(inventory_dir / "hosted-callsite-migration-ledger.v1.json")
    violations = load_json(inventory_dir / "direct-llm-invocation-violations.v1.json")
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        raise ValueError("migration ledger entries are invalid")

    reachable = [item for item in entries if item.get("reachability") == "hosted-route"]
    unknown = [item for item in entries if item.get("reachability") == "unknown"]
    not_enforced = [
        item
        for item in reachable
        if item.get("migration_status") != "enforced" or item.get("initial_gate_mode") != "enforce"
    ]
    direct_violations = violations.get("violations")
    if not isinstance(direct_violations, list):
        raise ValueError("direct invocation violations are invalid")

    release_evidence_path = inventory_dir.parent / "e2-release-evidence.v1.json"
    release_evidence: dict[str, object] | None = None
    if release_evidence_path.is_file():
        candidate = load_json(release_evidence_path)
        if isinstance(candidate, dict):
            release_evidence = candidate

    blockers: list[str] = []
    if not reachable:
        blockers.append("no_reachable_hosted_callsites")
    if unknown:
        blockers.append("unknown_callsite_reachability")
    if direct_violations:
        blockers.append("direct_llm_invocations_present")
    if not_enforced:
        blockers.append("reachable_callsite_not_enforced")
    if release_evidence is None:
        blockers.append("e2_release_evidence_missing")
    elif (
        release_evidence.get("status") != "current"
        or release_evidence.get("source_snapshot_id") != ledger.get("source_snapshot_id")
        or release_evidence.get("manifest_signature_lifecycle") is not True
        or release_evidence.get("targeted_tests_passed") is not True
        or release_evidence.get("rollback_evidence_current") is not True
    ):
        blockers.append("e2_release_evidence_not_current")

    return {
        "schema_version": "jimuyun.e2-readiness-result.v1",
        "source_snapshot_id": ledger.get("source_snapshot_id"),
        "ready": not blockers,
        "blockers": blockers,
        "evidence": {
            "reachable_hosted_callsite_count": len(reachable),
            "unknown_reachability_count": len(unknown),
            "direct_invocation_violation_count": len(direct_violations),
            "not_enforced_callsite_ids": [str(item.get("callsite_id")) for item in not_enforced],
            "release_evidence_path": release_evidence_path.relative_to(PLAN_DIR).as_posix(),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-dir", type=Path, default=PLAN_DIR / "inventories")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.inventory_dir.resolve())
    rendered = json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

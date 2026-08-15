#!/usr/bin/env python3
"""Validate the VDD plan and expose the Quick Dev candidate identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _run(*args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path.name}")
    return value


def _untracked_manifest() -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for raw in _run("ls-files", "--others", "--exclude-standard", "-z").split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8")
        path = REPOSITORY_ROOT / relative
        if path.is_file():
            values.append({"path": relative.replace("\\", "/"), "sha256": _sha(path.read_bytes())})
    return sorted(values, key=lambda item: item["path"])


def current_candidate_identity(_slice_id: str) -> dict[str, str]:
    contract = (PLAN_ROOT / "implementation-contract.v1.json").read_bytes()
    registry = (PLAN_ROOT / "command-registry.v1.json").read_bytes()
    authority = (PLAN_ROOT / "source-freeze-manifest.v1.json").read_bytes()
    tracked = _run("diff", "--binary", "HEAD", "--")
    untracked = json.dumps(_untracked_manifest(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    projection = b"\0".join((tracked, untracked, contract, registry, authority))
    return {
        "head": _run("rev-parse", "HEAD").decode("ascii").strip(),
        "index_tree": _run("write-tree").decode("ascii").strip(),
        "tracked_diff_hash": _sha(tracked),
        "untracked_manifest_hash": _sha(untracked),
        "contract_hash": _sha(contract),
        "command_registry_hash": _sha(registry),
        "validator_hash": _sha(Path(__file__).read_bytes()),
        "authority_manifest_hash": _sha(authority),
        "candidate_worktree_hash": _sha(projection),
    }


def validate_plan() -> dict[str, Any]:
    contract = _json(PLAN_ROOT / "implementation-contract.v1.json")
    registry = _json(PLAN_ROOT / "command-registry.v1.json")
    state = _json(PLAN_ROOT / "plan-state.v1.json")
    source = _json(PLAN_ROOT / "source-freeze-manifest.v1.json")
    required_files = {
        "00-index.md", "95-implementation-evolution-and-completion-report.md",
        "command-registry.v1.json", "implementation-contract.v1.json",
        "knowledge-context.freeze.v1.json", "knowledge-context.v1.json",
        "plan-state.v1.json", "requirements-and-acceptance.md",
        "source-freeze-manifest.v1.json",
    }
    missing = sorted(name for name in required_files if not (PLAN_ROOT / name).is_file())
    if missing:
        raise ValueError("missing plan artifacts: " + ", ".join(missing))
    if contract.get("plan_id") != registry.get("plan_id") or contract.get("plan_id") != state.get("plan_id"):
        raise ValueError("plan identity drift")
    if state.get("schema_version") != "vdd.plan-state.v2" or state.get("status") != "plan-ready":
        raise ValueError("lifecycle state is not VDD plan-ready")
    if state.get("state_owner") != "vdd-execution-plan" or state.get("authorizes") != ["plan-ready"]:
        raise ValueError("lifecycle owner or authorization drift")
    if contract.get("backend") != {"hidden_state": False}:
        raise ValueError("Quick Dev backend contract drift")
    if contract.get("protocol_artifacts") != {"context_layout": "context/<capsule-id>", "attempt_layout": "attempts/<attempt-id>"}:
        raise ValueError("Quick Dev protocol artifact contract drift")
    command_ids = [item.get("id") for item in registry.get("commands", [])]
    if len(command_ids) != len(set(command_ids)) or any(not item for item in command_ids):
        raise ValueError("command registry IDs are invalid")
    requirements: set[str] = set()
    acceptance: set[str] = set()
    slices = contract.get("slices")
    if not isinstance(slices, list) or [item.get("slice_id") for item in slices] != [f"S{value}" for value in range(7)]:
        raise ValueError("slice order or identity drift")
    for item in slices:
        requirements.update(item.get("requirement_ids", []))
        acceptance.update(item.get("acceptance_ids", []))
        tdd = item.get("tdd", {})
        referenced = [
            tdd.get("red", {}).get("command_id"),
            tdd.get("green", {}).get("command_id"),
            item.get("post_refactor_command_id"),
            *[entry.get("command_id") for entry in tdd.get("refactor", {}).get("invocations", [])],
        ]
        if any(value not in command_ids for value in referenced):
            raise ValueError(f"slice command is unregistered: {item.get('slice_id')}")
        if not item.get("recovery") or not item.get("depends_on") and item.get("slice_id") != "S0":
            raise ValueError(f"slice recovery or dependency is invalid: {item.get('slice_id')}")
    expected_requirements = {f"ARBE-{value:03d}" for value in range(1, 21)}
    expected_acceptance = {f"ARBE-A{value:02d}" for value in range(1, 42)}
    if requirements != expected_requirements:
        raise ValueError("requirement coverage is incomplete")
    if acceptance != expected_acceptance:
        raise ValueError("acceptance coverage is incomplete")
    if source.get("selection_hash") != "sha256:d5417f8767a7a8ba52998d4ac7e79b77a6d00a104fe280c1bb8b70ba5d38622b":
        raise ValueError("source freeze selection is stale")
    if source.get("authorizes") != [] or registry.get("authorizes") != [] or contract.get("authorizes") != []:
        raise ValueError("non-lifecycle artifact attempted authorization")
    return {
        "schema_version": "acceptance-review-bootstrap-efficiency.plan-validation.v1",
        "status": "passed",
        "requirements": len(requirements),
        "acceptance": len(acceptance),
        "slices": len(slices),
        "commands": len(command_ids),
        "authorizes": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-plan", action="store_true")
    parser.add_argument("--candidate-identity", metavar="SLICE_ID")
    args = parser.parse_args()
    if args.validate_plan == bool(args.candidate_identity):
        parser.error("select exactly one operation")
    result = validate_plan() if args.validate_plan else current_candidate_identity(args.candidate_identity)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

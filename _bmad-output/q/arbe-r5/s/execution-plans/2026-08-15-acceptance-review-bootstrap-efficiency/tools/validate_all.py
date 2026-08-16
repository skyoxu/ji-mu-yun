#!/usr/bin/env python3
"""Validate the VDD plan and expose the Quick Dev candidate identity."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]
CURRENT_SOURCE_FREEZE = PLAN_ROOT / "repair" / "round-2" / "source-freeze-manifest.v1.json"


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


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha(payload)


def _validate_bound_file(reference: Any, expected_path: str, label: str) -> Path:
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise ValueError(f"{label} reference is invalid")
    if reference["path"] != expected_path:
        raise ValueError(f"{label} path is invalid")
    path = REPOSITORY_ROOT / expected_path
    if not path.is_file() or reference["sha256"] != _sha(path.read_bytes()):
        raise ValueError(f"{label} hash is stale")
    return path


def _validate_implementation_authorization(state: dict[str, Any], source: dict[str, Any]) -> None:
    receipt_ref = state.get("authorization_receipt")
    receipt_path = _validate_bound_file(
        receipt_ref,
        "execution-plans/2026-08-15-acceptance-review-bootstrap-efficiency/implementation-authorization-receipt.v1.json",
        "implementation authorization receipt",
    )
    receipt = _json(receipt_path)
    required = {
        "schema_version", "plan_id", "source_freeze_manifest", "selection_pointer",
        "selection_record", "plan_validation", "known_red", "decision", "authorizes",
        "does_not_authorize",
    }
    if set(receipt) != required:
        raise ValueError("implementation authorization receipt fields are invalid")
    if (
        receipt["schema_version"] != "acceptance-review-bootstrap-efficiency.implementation-authorization-receipt.v1"
        or receipt["plan_id"] != "acceptance-review-bootstrap-efficiency"
        or receipt["authorizes"] != ["implementation-authorized"]
        or receipt["does_not_authorize"] != ["implementation-complete", "acceptance-passed", "archived", "release"]
    ):
        raise ValueError("implementation authorization receipt contract is invalid")

    source_ref = receipt["source_freeze_manifest"]
    if not isinstance(source_ref, dict) or set(source_ref) != {"path", "sha256", "canonical_hash"}:
        raise ValueError("source freeze manifest reference is invalid")
    source_path = CURRENT_SOURCE_FREEZE
    if source_ref["path"] != source_path.relative_to(REPOSITORY_ROOT).as_posix() or source_ref["sha256"] != _sha(source_path.read_bytes()):
        raise ValueError("source freeze manifest hash is stale")
    if source_ref["canonical_hash"] != source.get("canonical_hash"):
        raise ValueError("source freeze canonical hash is stale")
    _validate_bound_file(
        receipt["selection_pointer"],
        source["selection_pointer_path"],
        "selection pointer",
    )
    _validate_bound_file(
        receipt["selection_record"],
        source["selection_record_path"],
        "selection record",
    )
    if _json(source_path).get("selection_hash") != source.get("selection_hash"):
        raise ValueError("source freeze selection hash is stale")

    plan_validation = receipt["plan_validation"]
    expected_plan_result = {
        "acceptance": 46,
        "authorizes": [],
        "commands": 15,
        "requirements": 22,
        "schema_version": "acceptance-review-bootstrap-efficiency.plan-validation.v1",
        "slices": 7,
        "status": "passed",
    }
    if (
        not isinstance(plan_validation, dict)
        or plan_validation.get("command") != "python tools/validate_all.py --validate-plan"
        or plan_validation.get("result") != expected_plan_result
        or plan_validation.get("result_hash") != _canonical_hash(expected_plan_result)
    ):
        raise ValueError("authorization plan validation binding is invalid")
    _validate_bound_file(
        plan_validation.get("validator"),
        "execution-plans/2026-08-15-acceptance-review-bootstrap-efficiency/tools/validate_all.py",
        "plan validator",
    )

    known_red = receipt["known_red"]
    expected_red = {
        "status": "blocked",
        "family": "schema_error",
        "detail": "frozen authority lacks acceptance-contract companion",
        "authorizes": [],
    }
    if (
        not isinstance(known_red, dict)
        or known_red.get("command_id") != "canonical-migration-red"
        or known_red.get("result") != expected_red
        or known_red.get("result_hash") != _canonical_hash(expected_red)
    ):
        raise ValueError("authorization known RED binding is invalid")
    _validate_bound_file(
        known_red.get("fixture"),
        "execution-plans/2026-08-15-acceptance-review-bootstrap-efficiency/fixtures/current-package-exact-cover-red.v1.json",
        "known RED fixture",
    )
    _validate_bound_file(
        known_red.get("validator"),
        ".agents/skills/vdd-conformance-exact-cover/scripts/validate_conformance.py",
        "known RED validator",
    )
    decision = receipt["decision"]
    if decision != {
        "owner": "maintainer",
        "transition": "implementation-authorized",
        "reason": "self-hosted-exact-cover-bootstrap-exception",
    }:
        raise ValueError("implementation authorization decision is invalid")


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
    authority = CURRENT_SOURCE_FREEZE.read_bytes()
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


def _run_owner_validator(arguments: list[str], label: str) -> None:
    completed = subprocess.run(
        [sys.executable, *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        detail = (completed.stdout or completed.stderr).strip()[-1000:]
        raise ValueError(f"{label} failed: {detail}")


def _validate_freshness() -> None:
    source_path = CURRENT_SOURCE_FREEZE
    source_module_path = REPOSITORY_ROOT / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py"
    spec = importlib.util.spec_from_file_location("vdd_source_freeze_validator", source_module_path)
    if spec is None or spec.loader is None:
        raise ValueError("source-freeze validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_manifest(REPOSITORY_ROOT, _json(source_path))
    skill_contract = ".agents/skills/vdd-execution-plan/references/skill-input-contract.v1.json"
    receipt = "execution-plans/2026-08-15-acceptance-review-bootstrap-efficiency/in/freshness-r2/receipt.json"
    _run_owner_validator(
        ["scripts/python/validate_skill_input_consumption.py", "--repository-root", ".", "--contract", skill_contract, "--require-ready", receipt],
        "Skill Input validation",
    )
    _run_owner_validator(
        [".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py", "--input", "execution-plans/2026-08-15-acceptance-review-bootstrap-efficiency/knowledge-context.v1.json", "--repository-root", ".", "--skill-input-receipt", receipt, "--skill-input-operation", "create", "--skill-input-contract", skill_contract],
        "knowledge preflight",
    )


def validate_plan() -> dict[str, Any]:
    contract = _json(PLAN_ROOT / "implementation-contract.v1.json")
    registry = _json(PLAN_ROOT / "command-registry.v1.json")
    state = _json(PLAN_ROOT / "plan-state.v1.json")
    source = _json(CURRENT_SOURCE_FREEZE)
    required_files = {
        "00-index.md", "95-implementation-evolution-and-completion-report.md",
        "command-registry.v1.json", "implementation-contract.v1.json",
        "knowledge-context.freeze.v1.json", "knowledge-context.v1.json",
        "plan-state.v1.json", "requirements-and-acceptance.md",
        "source-freeze-manifest.v1.json",
        "authorization-bootstrap-override-contract.v1.json",
        "supervised-semantic-review-decision-contract.v1.json",
    }
    missing = sorted(name for name in required_files if not (PLAN_ROOT / name).is_file())
    if missing:
        raise ValueError("missing plan artifacts: " + ", ".join(missing))
    _validate_freshness()
    if contract.get("plan_id") != registry.get("plan_id") or contract.get("plan_id") != state.get("plan_id"):
        raise ValueError("plan identity drift")
    lifecycle_status = state.get("status")
    if state.get("schema_version") != "vdd.plan-state.v2" or lifecycle_status not in {"plan-ready", "implementation-authorized"}:
        raise ValueError("lifecycle state is not VDD plan-ready")
    if lifecycle_status == "plan-ready":
        if state.get("state_owner") != "vdd-execution-plan" or state.get("authorizes") != ["plan-ready"]:
            raise ValueError("lifecycle owner or authorization drift")
    else:
        if state.get("state_owner") != "maintainer" or state.get("authorizes") != ["plan-ready", "implementation-authorized"]:
            raise ValueError("lifecycle owner or authorization drift")
        _validate_implementation_authorization(state, source)
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
    expected_requirements = {f"ARBE-{value:03d}" for value in range(1, 23)}
    expected_acceptance = {f"ARBE-A{value:02d}" for value in range(1, 47)}
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

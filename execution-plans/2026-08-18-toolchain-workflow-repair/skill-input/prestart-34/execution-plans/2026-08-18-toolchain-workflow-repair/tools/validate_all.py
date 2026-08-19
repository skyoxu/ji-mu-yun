"""Deterministic, plan-local identity projections used by the Quick Dev router."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PLAN_ID = "toolchain-workflow-repair"
SLICES = tuple(f"W{index}" for index in range(7))
EXCLUDED_PREFIXES = ("logs/",)
EXCLUDED_NAMES = {"plan-state.v1.json", "resume-state.v1.json"}


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def _plan() -> Path:
    return Path(__file__).resolve().parents[1]


def _relative(path: str) -> Path:
    value = Path(path)
    if value.is_absolute() or ".." in value.parts:
        raise ValueError("repository path is invalid")
    return value


def _file_entry(path: str) -> dict[str, str]:
    relative = _relative(path)
    if relative.as_posix().startswith(EXCLUDED_PREFIXES) or relative.name in EXCLUDED_NAMES:
        raise ValueError("non-semantic path is not valid identity input")
    resolved = (_root() / relative).resolve()
    try:
        resolved.relative_to(_root())
    except ValueError as exc:
        raise ValueError("identity path escapes repository") from exc
    if resolved.is_symlink():
        raise ValueError("identity path may not be a symlink")
    return {"path": relative.as_posix(), "state": "present", "sha256": _sha(resolved.read_bytes())} if resolved.is_file() else {"path": relative.as_posix(), "state": "absent"}


def _load_contract() -> dict[str, Any]:
    payload = json.loads((_plan() / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    if payload.get("plan_id") != PLAN_ID or not isinstance(payload.get("slices"), list):
        raise ValueError("implementation contract is invalid")
    return payload


def _slice(slice_id: str) -> dict[str, Any]:
    if slice_id not in SLICES:
        raise ValueError("unknown slice")
    selected = next((item for item in _load_contract()["slices"] if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict):
        raise ValueError("slice is missing")
    return selected


def _flatten_paths(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if "*" not in value else []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_flatten_paths(item))
        return result
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_flatten_paths(item))
        return result
    return []


def _candidate_entries(slice_id: str) -> list[dict[str, str]]:
    selected = _slice(slice_id)
    paths = _flatten_paths(selected.get("allowed_changes", {})) + _flatten_paths(selected.get("planned_new_files", []))
    normalized = [
        f"execution-plans/2026-08-18-toolchain-workflow-repair/{path}" if path.startswith("tools/") else path
        for path in paths
    ]
    entries = [_file_entry(path) for path in normalized]
    return sorted({_canonical(entry).decode("utf-8"): entry for entry in entries}.values(), key=lambda item: item["path"])


def _dependency_identities(slice_id: str) -> list[dict[str, str]]:
    return [{"slice_id": dependency, "candidate_hash": current_candidate_identity(dependency)["candidate_hash"]} for dependency in _slice(slice_id).get("depends_on", [])]


def current_candidate_identity(slice_id: str) -> dict[str, str]:
    selected = _slice(slice_id)
    candidate = {"slice_id": slice_id, "write_manifest": _candidate_entries(slice_id), "dependencies": _dependency_identities(slice_id)}
    predicate = {
        "slice": selected,
        "contract": _file_entry("execution-plans/2026-08-18-toolchain-workflow-repair/implementation-contract.v1.json"),
        "registry": _file_entry("execution-plans/2026-08-18-toolchain-workflow-repair/command-registry.v1.json"),
        "candidate": candidate,
    }
    authority_paths = [
        "execution-plans/2026-08-18-toolchain-workflow-repair/authority-manifest.v1.json",
        "docs/adr/ADR-0060-skill-input-selection-generation-and-retention.md",
        ".agents/skills/quick-dev-tdd-adapter/references/skill-input-contract.v1.json",
        ".agents/skills/vdd-execution-plan/references/lifecycle-state-contract.json",
        "knowledge/policies/consumer-policies.v2.json",
    ]
    validator_paths = [
        "execution-plans/2026-08-18-toolchain-workflow-repair/tools/validate_all.py",
        "execution-plans/2026-08-18-toolchain-workflow-repair/tools/validate_plan_ready.py",
        "execution-plans/2026-08-18-toolchain-workflow-repair/tools/terminal_full.py",
        "execution-plans/2026-08-18-toolchain-workflow-repair/tools/migration_bridge.py",
        ".agents/skills/quick-dev-tdd-adapter/tools/route_plan_directory.py",
        ".agents/skills/quick-dev-tdd-adapter/tools/build_slice_invocation.py",
        ".agents/skills/quick-dev-tdd-adapter/tools/loop_plan_directory.py",
    ]
    return {
        "candidate_hash": _sha(_canonical(candidate)),
        "predicate_input_root": _sha(_canonical(predicate)),
        "authority_root": _sha(_canonical([_file_entry(path) for path in authority_paths])),
        "validator_root": _sha(_canonical([_file_entry(path) for path in validator_paths])),
        "validator_version": "toolchain-workflow-repair.validate-all.v1",
        "closure_definition_hash": _sha(_canonical({"slice": slice_id, "allowed_changes": selected.get("allowed_changes"), "planned_new_files": selected.get("planned_new_files"), "depends_on": selected.get("depends_on")})),
        "validator_hash": _file_entry("execution-plans/2026-08-18-toolchain-workflow-repair/tools/validate_all.py")["sha256"],
    }


def slice_validation_snapshot(slice_id: str) -> dict[str, str]:
    return current_candidate_identity(slice_id)


def validation_snapshot() -> dict[str, str]:
    return {"candidate_hash": _sha(_canonical([current_candidate_identity(slice_id) for slice_id in SLICES])), "predicate_input_root": _sha(_canonical([current_candidate_identity(slice_id)["predicate_input_root"] for slice_id in SLICES])), "authority_root": _sha(_canonical([current_candidate_identity(slice_id)["authority_root"] for slice_id in SLICES])), "validator_root": _sha(_canonical([current_candidate_identity(slice_id)["validator_root"] for slice_id in SLICES])), "validator_version": "toolchain-workflow-repair.validate-all.v1", "closure_definition_hash": _sha(_canonical([current_candidate_identity(slice_id)["closure_definition_hash"] for slice_id in SLICES])), "validator_hash": _file_entry("execution-plans/2026-08-18-toolchain-workflow-repair/tools/validate_all.py")["sha256"]}

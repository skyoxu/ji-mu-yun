"""Plan-local candidate identity bridge for the Quick Dev lifecycle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

PLAN_ID = "toolchain-core-skill-replay-portability-and-evaluation-seed"
PLAN_DIR = Path(__file__).resolve().parents[1]
ROOT = PLAN_DIR.parents[1]


def _sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _entry(relative: str) -> dict[str, str]:
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT)
    return {"path": relative, "state": "present" if path.is_file() else "absent", "sha256": _sha(path.read_bytes()) if path.is_file() else _sha(b"<absent>")}


def _slice(slice_id: str) -> dict[str, Any]:
    contract = json.loads((PLAN_DIR / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = next((item for item in contract.get("slices", []) if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict):
        raise ValueError("slice is not declared")
    return selected


def _paths(value: Any) -> list[str]:
    if isinstance(value, str):
        return [] if "*" in value else [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_paths(item))
        return result
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_paths(item))
        return result
    return []


def current_candidate_identity(slice_id: str) -> dict[str, str]:
    selected = _slice(slice_id)
    write_manifest = [_entry(path) for path in sorted(set(_paths(selected.get("allowed_changes", {})) + _paths(selected.get("planned_new_files", []))))]
    candidate = {"slice_id": slice_id, "write_manifest": write_manifest, "dependencies": []}
    predicate = {"slice": selected, "contract": _entry(f"execution-plans/{PLAN_ID}/implementation-contract.v1.json"), "registry": _entry(f"execution-plans/{PLAN_ID}/command-registry.v1.json"), "candidate": candidate}
    authority = [_entry(f"execution-plans/{PLAN_ID}/authority-manifest.v1.json"), _entry(".agents/skills/quick-dev-tdd-adapter/references/skill-input-contract.v1.json")]
    validators = [_entry(f"execution-plans/{PLAN_ID}/tools/validate_all.py"), _entry(".agents/skills/quick-dev-tdd-adapter/tools/build_slice_invocation.py"), _entry(".agents/skills/quick-dev-tdd-adapter/tools/loop_plan_directory.py")]
    return {
        "candidate_hash": _sha(_canonical(candidate)),
        "predicate_input_root": _sha(_canonical(predicate)),
        "authority_root": _sha(_canonical(authority)),
        "validator_root": _sha(_canonical(validators)),
        "validator_version": "tc-d1.validate-all.v1",
        "closure_definition_hash": _sha(_canonical({"slice": slice_id, "allowed_changes": selected.get("allowed_changes"), "planned_new_files": selected.get("planned_new_files")})),
        "validator_hash": _entry(f"execution-plans/{PLAN_ID}/tools/validate_all.py")["sha256"],
    }


def slice_validation_snapshot(slice_id: str) -> dict[str, str]:
    return current_candidate_identity(slice_id)


def validation_snapshot() -> dict[str, str]:
    return current_candidate_identity("RMAP-S0")

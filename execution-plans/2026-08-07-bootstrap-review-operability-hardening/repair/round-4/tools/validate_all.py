from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


PLAN_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_DIR.parents[3]
VALIDATOR_VERSION = "broh-round4-repair-v1"


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _file(name: str) -> str:
    return _sha((PLAN_DIR / name).read_bytes())


def _validator_hash() -> str:
    return _sha((PLAN_DIR / "tools" / "validate_repair_plan.py").read_bytes())


def _git(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=REPOSITORY_ROOT, capture_output=True, check=False)
    return completed.stdout.decode("utf-8", errors="replace").strip() if completed.returncode == 0 else "unknown"


def _contract() -> dict[str, Any]:
    return json.loads((PLAN_DIR / "implementation-contract.v1.json").read_text(encoding="utf-8"))


def predecessor_result_hashes(slice_id: str) -> dict[str, str]:
    selected = next(item for item in _contract()["slices"] if item["slice_id"] == slice_id)
    contract_hash = _file("implementation-contract.v1.json")
    root = REPOSITORY_ROOT / "logs" / "tdd-adapter" / _contract()["plan_id"]
    result: dict[str, str] = {}
    for predecessor in selected.get("depends_on", []):
        current = "missing"
        for path in sorted((root / predecessor).glob("*/slice-ready-result.json"), reverse=True):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if value.get("status") == "pass" and value.get("contract_hash") == contract_hash:
                current = _sha(path.read_bytes())
                break
        result[predecessor] = current
    return result


def slice_validation_snapshot(slice_id: str) -> dict[str, str]:
    contract = _contract()
    selected = next(item for item in contract["slices"] if item["slice_id"] == slice_id)
    registry = json.loads((PLAN_DIR / "command-registry.v1.json").read_text(encoding="utf-8"))
    commands = {item["id"]: item for item in registry["commands"]}
    tdd = selected["tdd"]
    command_ids = [tdd["red"]["command_id"], tdd["green"]["command_id"]]
    command_ids.extend(item["command_id"] for item in tdd["refactor"]["invocations"])
    command_ids.append(selected["post_refactor_command_id"])
    candidate = _sha(json.dumps({
        "slice": selected,
        "commands": {command_id: commands[command_id] for command_id in command_ids},
        "predecessors": predecessor_result_hashes(slice_id),
    }, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    closure = _sha(json.dumps({
        "finding_ids": selected["finding_ids"],
        "acceptance_ids": selected["acceptance_ids"],
        "allowed_changes": selected["allowed_changes"],
        "dependency_closure": selected["dependency_closure"],
    }, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    validator_root = _validator_hash()
    authority_root = _file("authority-manifest.v1.json")
    return {
        "candidate_hash": candidate,
        "predicate_input_root": candidate,
        "authority_root": authority_root,
        "validator_root": validator_root,
        "validator_version": VALIDATOR_VERSION,
        "closure_definition_hash": closure,
    }


def validation_snapshot() -> dict[str, str]:
    payload = b"".join((PLAN_DIR / name).read_bytes() for name in (
        "implementation-contract.v1.json", "command-registry.v1.json",
        "requirements.v1.json", "repair-findings.v1.json",
    ))
    candidate = _sha(payload)
    return {
        "candidate_hash": candidate,
        "predicate_input_root": candidate,
        "authority_root": _file("authority-manifest.v1.json"),
        "validator_root": _sha((PLAN_DIR / "tools" / "validate_repair_plan.py").read_bytes()),
        "validator_version": VALIDATOR_VERSION,
        "closure_definition_hash": _sha(payload + (PLAN_DIR / "repair-plan.v1.json").read_bytes()),
    }


def current_candidate_identity(slice_id: str = "BROH-R4-S1") -> dict[str, Any]:
    scoped = slice_validation_snapshot(slice_id)
    return {
        "head": _git("rev-parse", "HEAD"),
        "index_tree": _git("rev-parse", "HEAD^{tree}"),
        "tracked_diff_hash": _sha(_git("diff", "--binary", "HEAD").encode("utf-8")),
        "untracked_manifest_hash": _sha(_git("ls-files", "--others", "--exclude-standard").encode("utf-8")),
        "contract_hash": _file("implementation-contract.v1.json"),
        "command_registry_hash": _file("command-registry.v1.json"),
        "validator_hash": scoped["validator_root"],
        "authority_manifest_hash": scoped["authority_root"],
        "candidate_worktree_hash": scoped["candidate_hash"],
        **scoped,
        "predecessor_result_hashes": predecessor_result_hashes(slice_id),
    }

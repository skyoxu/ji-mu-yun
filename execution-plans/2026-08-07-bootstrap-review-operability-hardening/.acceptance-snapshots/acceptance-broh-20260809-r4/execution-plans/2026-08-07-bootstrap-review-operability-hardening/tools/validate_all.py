from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any


PLAN_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_DIR.parents[1]
VALIDATOR_VERSION = "broh-validator-v1"
STAGE_VALIDATOR_PATHS = (
    PLAN_DIR / "tools" / "validate_plan.py",
    PLAN_DIR / "tools" / "validate_all.py",
    PLAN_DIR / "tools" / "validate_slice.py",
    PLAN_DIR / "tools" / "single_maintainer_tdd_bridge.py",
    PLAN_DIR / "tools" / "stage_projection_builder.py",
)
TERMINAL_VALIDATOR_PATH = PLAN_DIR / "tools" / "validate_implementation.py"


def _sha_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes()) if path.is_file() else _sha_bytes(b"<missing>")


def _load_plan_validator() -> Any:
    path = PLAN_DIR / "tools" / "validate_plan.py"
    spec = importlib.util.spec_from_file_location("broh_plan_validator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("plan validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.decode("utf-8", errors="replace").strip()


def _untracked_manifest_hash() -> str:
    """Bind untracked candidate files by path and content, not names alone."""
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        return _sha_bytes(b"<untracked-manifest-unavailable>")
    entries: list[dict[str, str]] = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        path = REPOSITORY_ROOT / Path(relative)
        entries.append({"path": relative.replace("\\", "/"), "sha256": _sha_file(path)})
    payload = json.dumps(sorted(entries, key=lambda item: item["path"]), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha_bytes(payload)


def _tracked_diff_hash() -> str:
    result = subprocess.run(
        ["git", "diff", "--binary", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
    )
    return _sha_bytes(result.stdout if result.returncode == 0 else b"<tracked-diff-unavailable>")


def _candidate_binding() -> str:
    values = {
        "head": _git("rev-parse", "HEAD") or "unknown",
        "index_tree": _git("rev-parse", "HEAD^{tree}") or "unknown",
        "tracked_diff_hash": _tracked_diff_hash(),
        "untracked_manifest_hash": _untracked_manifest_hash(),
        "contract_hash": _contract_hash(),
        "command_registry_hash": _sha_file(PLAN_DIR / "command-registry.v1.json"),
        "validator_hash": _validator_hash(),
        "terminal_validator_hash": _terminal_validator_hash(),
        "authority_manifest_hash": _authority_hash(),
    }
    payload = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha_bytes(payload)


def _contract_hash() -> str:
    return _sha_file(PLAN_DIR / "implementation-contract.v1.json")


def _authority_hash() -> str:
    return _sha_file(PLAN_DIR / "authority-manifest.v1.json")


def _validator_hash() -> str:
    digest = hashlib.sha256()
    for path in STAGE_VALIDATOR_PATHS:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _terminal_validator_hash() -> str:
    return _sha_file(TERMINAL_VALIDATOR_PATH)


def validation_snapshot() -> dict[str, str]:
    candidate = _candidate_binding()
    authority = _authority_hash()
    validator = _validator_hash()
    closure = _sha_bytes(
        (PLAN_DIR / "implementation-contract.v1.json").read_bytes()
        + (PLAN_DIR / "baseline-and-scope.v1.json").read_bytes()
    )
    return {
        "candidate_hash": candidate,
        "predicate_input_root": candidate,
        "authority_root": authority,
        "validator_root": validator,
        "validator_version": VALIDATOR_VERSION,
        "closure_definition_hash": closure,
    }


def slice_validation_snapshot(slice_id: str | None = None) -> dict[str, str]:
    if not isinstance(slice_id, str) or not slice_id:
        raise ValueError("slice id is required for a slice-scoped snapshot")
    contract = json.loads((PLAN_DIR / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = next((item for item in contract.get("slices", []) if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict):
        raise ValueError(f"unknown slice identity scope: {slice_id}")
    registry = json.loads((PLAN_DIR / "command-registry.v1.json").read_text(encoding="utf-8"))
    commands = {item.get("id"): item for item in registry.get("commands", []) if isinstance(item, dict)}
    tdd = selected.get("tdd", {})
    command_ids = [tdd.get("red", {}).get("command_id"), tdd.get("green", {}).get("command_id")]
    command_ids.extend(item.get("command_id") for item in tdd.get("refactor", {}).get("invocations", []))
    command_ids.append(selected.get("post_refactor_command_id"))
    bound_commands = {command_id: commands.get(command_id) for command_id in command_ids}
    predecessors = predecessor_result_hashes(slice_id)
    candidate = _sha_bytes(json.dumps({
        "slice": selected,
        "commands": bound_commands,
        "predecessor_result_hashes": predecessors,
        "contract_hash": _contract_hash(),
    }, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    closure = _sha_bytes(json.dumps({
        "slice_id": slice_id,
        "depends_on": selected.get("depends_on", []),
        "allowed_changes": selected.get("allowed_changes", {}),
        "execution_read_set": selected.get("execution_read_set", []),
        "dependency_closure": selected.get("dependency_closure", []),
    }, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return {
        "candidate_hash": candidate,
        "predicate_input_root": candidate,
        "authority_root": _authority_hash(),
        "validator_root": _validator_hash(),
        "validator_version": VALIDATOR_VERSION,
        "closure_definition_hash": closure,
    }


def predecessor_result_hashes(slice_id: str) -> dict[str, str]:
    contract = json.loads((PLAN_DIR / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = next((item for item in contract.get("slices", []) if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict):
        raise ValueError(f"unknown slice identity scope: {slice_id}")
    contract_hash = _contract_hash()
    evidence_root = REPOSITORY_ROOT / "logs" / "tdd-adapter" / contract["plan_id"]
    result: dict[str, str] = {}
    for predecessor in selected.get("depends_on", []):
        candidates = sorted(
            (evidence_root / predecessor).glob("*/slice-ready-result.json"),
            key=lambda path: path.parent.name,
            reverse=True,
        )
        current = None
        for path in candidates:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if (
                value.get("status") == "pass"
                and value.get("predicate") == "slice-ready"
                and value.get("slice_id") == predecessor
                and value.get("contract_hash") == contract_hash
            ):
                current = _sha_file(path)
                break
        result[predecessor] = current or "missing"
    return result


def current_candidate_identity(slice_id: str = "BROH-S0") -> dict[str, str]:
    scoped = slice_validation_snapshot(slice_id)
    tracked_diff = _tracked_diff_hash()
    untracked_manifest = _untracked_manifest_hash()
    worktree = _candidate_binding()
    return {
        "head": _git("rev-parse", "HEAD") or "unknown",
        "index_tree": _git("rev-parse", "HEAD^{tree}") or "unknown",
        "tracked_diff_hash": tracked_diff,
        "untracked_manifest_hash": untracked_manifest,
        "contract_hash": _contract_hash(),
        "command_registry_hash": _sha_file(PLAN_DIR / "command-registry.v1.json"),
        "validator_hash": _validator_hash(),
        "authority_manifest_hash": _authority_hash(),
        "candidate_worktree_hash": worktree,
        "candidate_hash": scoped["candidate_hash"],
        "predicate_input_root": scoped["predicate_input_root"],
        "predecessor_result_hashes": predecessor_result_hashes(slice_id),
    }


def validate() -> list[str]:
    return list(_load_plan_validator().validate_plan())


def main() -> int:
    errors = validate()
    result = {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "predicate": "plan-ready",
        "validation_snapshot": validation_snapshot(),
        "authorizes": [],
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

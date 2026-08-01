"""Expose current candidate identity and the plan-local validation result."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from validate_plan import PLAN_ROOT, REPOSITORY_ROOT, validate_directory


VALIDATOR_VERSION = "tec.workflow-validator.v1"
ROOT_KEYS = (
    "candidate_hash",
    "predicate_input_root",
    "authority_root",
    "validator_root",
    "validator_version",
    "closure_definition_hash",
)
NORMATIVE_PLAN_FILES = (
    "01-requirements-and-acceptance.md",
    "authority-manifest.v1.json",
    "command-registry.v1.json",
    "implementation-contract.v1.json",
    "knowledge-context.freeze.v1.json",
    "tools/validate_all.py",
    "tools/validate_plan.py",
    "tools/slice_predicate.py",
    "tools/stage_projection_builder.py",
)


def _hash_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical_hash(value: Any) -> str:
    return _hash_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_names(*args: str) -> list[str]:
    completed = subprocess.run(["git", *args], cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
    if completed.returncode:
        raise ValueError(completed.stderr.strip())
    return completed.stdout.splitlines()


def _selected_slices(contract: dict[str, Any], slice_id: str) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for item in contract["slices"]:
        selected.append(item)
        if item.get("slice_id") == slice_id:
            return selected
    raise ValueError(f"unknown slice: {slice_id}")


def _patterns(selected: list[dict[str, Any]]) -> set[str]:
    values: set[str] = set()
    for item in selected:
        for paths in item.get("allowed_changes", {}).values():
            values.update(paths)
        values.update(item.get("execution_read_set", []))
        values.update(item.get("dependency_closure", []))
    return {value.replace("\\", "/").strip("/") for value in values if value and not value.casefold().startswith("logs/")}


def _matches(path: str, patterns: set[str]) -> bool:
    candidate = path.replace("\\", "/").casefold()
    for pattern in patterns:
        folded = pattern.casefold()
        if folded.endswith("/**") and (candidate == folded[:-3] or candidate.startswith(folded[:-2])):
            return True
        if fnmatch.fnmatchcase(candidate, folded):
            return True
    return False


def _path_manifest(paths: list[str], *, index: bool = False) -> str:
    digest = hashlib.sha256()
    for relative in sorted(set(paths), key=str.casefold):
        digest.update(relative.replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        if index:
            completed = subprocess.run(["git", "show", f":{relative}"], cwd=REPOSITORY_ROOT, capture_output=True, check=False)
            data = completed.stdout if completed.returncode == 0 else b"<deleted>"
        else:
            path = REPOSITORY_ROOT / relative
            data = path.read_bytes() if path.is_file() else b"<deleted>"
        digest.update(data)
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _validator_root() -> str:
    digest = hashlib.sha256()
    for relative in ("tools/validate_all.py", "tools/validate_plan.py", "tools/slice_predicate.py", "tools/stage_projection_builder.py"):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update((PLAN_ROOT / relative).read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _plan_hash() -> str:
    digest = hashlib.sha256()
    for relative in NORMATIVE_PLAN_FILES:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update((PLAN_ROOT / relative).read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _snapshot(slice_id: str) -> dict[str, str]:
    contract = _load(PLAN_ROOT / "implementation-contract.v1.json")
    selected = _selected_slices(contract, slice_id)
    patterns = _patterns(selected)
    tracked = [value for value in _git_names("diff", "--name-only", "HEAD") if _matches(value, patterns)]
    staged = [value for value in _git_names("diff", "--cached", "--name-only", "HEAD") if _matches(value, patterns)]
    untracked = [value for value in _git_names("ls-files", "--others", "--exclude-standard") if _matches(value, patterns)]
    head = _git_names("rev-parse", "HEAD")[0]
    validator_root = _validator_root()
    authority_root = _hash_bytes((PLAN_ROOT / "authority-manifest.v1.json").read_bytes())
    closure_definition_hash = _canonical_hash(
        {
            "slice_id": slice_id,
            "selected_slices": selected,
            "global_forbidden_changes": contract.get("global_forbidden_changes"),
            "terminal_validation": contract.get("terminal_validation"),
        }
    )
    candidate_hash = _canonical_hash(
        {
            "head": head,
            "tracked": _path_manifest(tracked),
            "staged": _path_manifest(staged, index=True),
            "untracked": _path_manifest(untracked),
            "plan_hash": _plan_hash(),
            "authority_root": authority_root,
            "validator_root": validator_root,
        }
    )
    predicate_input_root = _canonical_hash(
        {
            "candidate_hash": candidate_hash,
            "authority_root": authority_root,
            "validator_root": validator_root,
            "closure_definition_hash": closure_definition_hash,
        }
    )
    return {
        "candidate_hash": candidate_hash,
        "predicate_input_root": predicate_input_root,
        "authority_root": authority_root,
        "validator_root": validator_root,
        "validator_version": f"{VALIDATOR_VERSION}+{validator_root}",
        "closure_definition_hash": closure_definition_hash,
    }


def current_candidate_identity(slice_id: str = "TEC-S5") -> dict[str, str]:
    value = _snapshot(slice_id)
    value["head"] = _git_names("rev-parse", "HEAD")[0]
    value["plan_hash"] = _plan_hash()
    value["source_hash"] = _hash_bytes(value["head"].encode("utf-8"))
    value["contract_hash"] = _hash_bytes((PLAN_ROOT / "implementation-contract.v1.json").read_bytes())
    value["command_registry_hash"] = _hash_bytes((PLAN_ROOT / "command-registry.v1.json").read_bytes())
    value["authority_manifest_hash"] = _hash_bytes((PLAN_ROOT / "authority-manifest.v1.json").read_bytes())
    value["validator_hash"] = value["validator_root"]
    return value


def slice_validation_snapshot(slice_id: str) -> dict[str, str]:
    return _snapshot(slice_id)


def validation_snapshot() -> dict[str, str]:
    return _snapshot("TEC-S6")


def main() -> int:
    result = validate_directory()
    if result["status"] == "pass":
        try:
            result["validation_snapshot"] = validation_snapshot()
        except (OSError, UnicodeError, ValueError) as exc:
            result["status"] = "fail"
            result["findings"].append({"rule_id": "TEC-PLAN-SNAPSHOT", "path": "tools/validate_all.py", "detail": str(exc)})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

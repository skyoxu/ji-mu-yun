"""Expose Quick Dev freshness identities and run the plan-local validator."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from validate_plan import PLAN_ROOT, REPOSITORY_ROOT, strict_load, validate_directory


VALIDATOR_VERSION = "kwi.workflow-validator.v1"
NORMATIVE_PLAN_FILES = (
    "01-requirements-and-acceptance.md",
    "authority-manifest.v1.json",
    "implementation-contract.v1.json",
    "command-registry.v1.json",
    "fixtures/protocol-cases.v1.json",
    "fixtures/migration-cases.v1.json",
    "tools/knowledge_workflow_slice_bridge.py",
)
SNAPSHOT_ROOTS = (
    "candidate_hash",
    "predicate_input_root",
    "authority_root",
    "validator_root",
    "validator_version",
    "closure_definition_hash",
)


def _sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _canonical_hash(value: Any) -> str:
    return _sha_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _git_bytes(*args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def _git_text(*args: str) -> str:
    return _git_bytes(*args).decode("utf-8", errors="strict").strip()


def _selected_slices(contract: dict[str, Any], slice_id: str) -> list[dict[str, Any]]:
    slices = contract.get("slices")
    if not isinstance(slices, list):
        raise ValueError("implementation contract has no slices")
    selected: list[dict[str, Any]] = []
    for item in slices:
        if not isinstance(item, dict):
            raise ValueError("implementation contract contains an invalid slice")
        selected.append(item)
        if item.get("slice_id") == slice_id:
            return selected
    raise ValueError(f"unknown slice identity scope: {slice_id}")


def _scope_patterns(selected: list[dict[str, Any]]) -> set[str]:
    patterns: set[str] = set()
    for item in selected:
        allowed = item.get("allowed_changes", {})
        if isinstance(allowed, dict):
            for values in allowed.values():
                if isinstance(values, list):
                    patterns.update(value for value in values if isinstance(value, str))
        for field in ("execution_read_set", "dependency_closure"):
            values = item.get(field)
            if isinstance(values, list):
                patterns.update(value for value in values if isinstance(value, str))
    return {
        value.replace("\\", "/").strip("/")
        for value in patterns
        if value and not value.replace("\\", "/").casefold().startswith("logs/")
    }


def _matches(relative: str, patterns: set[str]) -> bool:
    candidate = relative.replace("\\", "/").casefold()
    for pattern in patterns:
        folded = pattern.casefold()
        if folded.endswith("/**") and (candidate == folded[:-3] or candidate.startswith(folded[:-2])):
            return True
        if fnmatch.fnmatchcase(candidate, folded):
            return True
    return False


def _scope_roots(patterns: set[str]) -> list[str]:
    roots: set[str] = set()
    for pattern in patterns:
        wildcard = min((index for index in (pattern.find("*"), pattern.find("?"), pattern.find("[")) if index >= 0), default=-1)
        prefix = pattern if wildcard < 0 else pattern[:wildcard].rstrip("/")
        if prefix and not prefix.casefold().startswith("logs/"):
            roots.add(prefix)
    return sorted(roots, key=str.casefold)


def _normative_worktree_path(relative: str) -> bool:
    candidate = relative.replace("\\", "/")
    if candidate.casefold().startswith("logs/"):
        return False
    plan_prefix = PLAN_ROOT.relative_to(REPOSITORY_ROOT).as_posix() + "/"
    if candidate.startswith(plan_prefix):
        name = candidate[len(plan_prefix) :]
        if name in {"00-index.md", "plan-state.v1.json", "resume-state.v1.json"} or Path(name).name.startswith("95-"):
            return False
    return True


def _git_names(args: list[str], roots: list[str]) -> list[str]:
    if not roots:
        return []
    output = _git_text(*args, "--", *roots)
    return output.splitlines() if output else []


def _worktree_manifest_hash(paths: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(paths, key=str.casefold):
        target = REPOSITORY_ROOT / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(target.read_bytes() if target.is_file() else b"<deleted>")
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _index_manifest_hash(paths: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(paths, key=str.casefold):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        result = subprocess.run(
            ["git", "show", f":{relative}"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            check=False,
        )
        digest.update(result.stdout if result.returncode == 0 else b"<deleted>")
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _validator_root() -> str:
    files = [PLAN_ROOT / "tools" / "validate_plan.py", PLAN_ROOT / "tools" / "validate_all.py", PLAN_ROOT / "tools" / "knowledge_workflow_slice_bridge.py"]
    files.extend(sorted((PLAN_ROOT / "tools" / "tests").glob("test_*.py"), key=lambda item: item.name.casefold()))
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(PLAN_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
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


def _authority_root(manifest: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    digest.update((PLAN_ROOT / "authority-manifest.v1.json").read_bytes())
    digest.update(b"\0")
    for item in manifest.get("sources", []):
        if not isinstance(item, dict) or item.get("role") not in {"authority", "migration-source"}:
            continue
        relative = item.get("path")
        if not isinstance(relative, str):
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update((REPOSITORY_ROOT / relative).read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _candidate_core(slice_id: str) -> dict[str, str]:
    contract = strict_load(PLAN_ROOT / "implementation-contract.v1.json")
    selected = _selected_slices(contract, slice_id)
    patterns = _scope_patterns(selected)
    roots = _scope_roots(patterns)
    tracked = [
        value
        for value in _git_names(["diff", "--name-only", "HEAD"], roots)
        if _matches(value, patterns) and _normative_worktree_path(value)
    ]
    staged = [
        value
        for value in _git_names(["diff", "--cached", "--name-only", "HEAD"], roots)
        if _matches(value, patterns) and _normative_worktree_path(value)
    ]
    untracked = [
        value
        for value in _git_names(["ls-files", "--others", "--exclude-standard"], roots)
        if _matches(value, patterns) and _normative_worktree_path(value)
    ]
    head = _git_text("rev-parse", "HEAD")
    index_tree = _index_manifest_hash(staged)
    tracked_diff_hash = _worktree_manifest_hash(tracked)
    untracked_manifest_hash = _worktree_manifest_hash(untracked)
    contract_hash = _sha_file(PLAN_ROOT / "implementation-contract.v1.json")
    registry_hash = _sha_file(PLAN_ROOT / "command-registry.v1.json")
    validator_hash = _validator_root()
    authority_manifest_hash = _sha_file(PLAN_ROOT / "authority-manifest.v1.json")
    candidate_worktree_hash = _canonical_hash(
        {
            "slice_id": slice_id,
            "head": head,
            "index_tree": index_tree,
            "tracked_diff_hash": tracked_diff_hash,
            "untracked_manifest_hash": untracked_manifest_hash,
            "contract_hash": contract_hash,
            "command_registry_hash": registry_hash,
            "validator_hash": validator_hash,
            "authority_manifest_hash": authority_manifest_hash,
        }
    )
    return {
        "head": head,
        "index_tree": index_tree,
        "tracked_diff_hash": tracked_diff_hash,
        "untracked_manifest_hash": untracked_manifest_hash,
        "contract_hash": contract_hash,
        "command_registry_hash": registry_hash,
        "validator_hash": validator_hash,
        "authority_manifest_hash": authority_manifest_hash,
        "candidate_worktree_hash": candidate_worktree_hash,
    }


def _snapshot(slice_id: str) -> dict[str, str]:
    contract = strict_load(PLAN_ROOT / "implementation-contract.v1.json")
    manifest = strict_load(PLAN_ROOT / "authority-manifest.v1.json")
    selected = _selected_slices(contract, slice_id)
    core = _candidate_core(slice_id)
    plan_hash = _plan_hash()
    authority_root = _authority_root(manifest)
    validator_root = core["validator_hash"]
    closure_definition_hash = _canonical_hash(
        {
            "slice_id": slice_id,
            "global_forbidden_changes": contract.get("global_forbidden_changes"),
            "selected_slices": selected,
            "terminal_validation": contract.get("terminal_validation"),
        }
    )
    predicate_input_root = _canonical_hash(
        {
            "candidate_hash": core["candidate_worktree_hash"],
            "plan_hash": plan_hash,
            "authority_root": authority_root,
            "validator_root": validator_root,
            "closure_definition_hash": closure_definition_hash,
        }
    )
    return {
        "candidate_hash": core["candidate_worktree_hash"],
        "predicate_input_root": predicate_input_root,
        "authority_root": authority_root,
        "validator_root": validator_root,
        "validator_version": f"{VALIDATOR_VERSION}+{validator_root}",
        "closure_definition_hash": closure_definition_hash,
    }


def current_candidate_identity(slice_id: str = "RMAP-S6") -> dict[str, str]:
    identity = _candidate_core(slice_id)
    identity["plan_hash"] = _plan_hash()
    identity["source_hash"] = _sha_bytes(identity["head"].encode("utf-8"))
    identity.update(_snapshot(slice_id))
    return identity


def slice_validation_snapshot(slice_id: str) -> dict[str, str]:
    return _snapshot(slice_id)


def validation_snapshot() -> dict[str, str]:
    return _snapshot("RMAP-S7")


def main() -> int:
    result = validate_directory()
    if result["status"] == "pass":
        try:
            result["validation_snapshot"] = validation_snapshot()
        except (OSError, UnicodeError, ValueError) as exc:
            result["status"] = "fail"
            result["findings"].append(
                {"rule_id": "KWI-PLAN-SNAPSHOT-IDENTITY", "path": "tools/validate_all.py", "detail": str(exc)}
            )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

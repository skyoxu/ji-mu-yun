"""Expose current Quick Dev identities for the 7-27 execution plan."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from validate_plan import PLAN_ROOT, REPOSITORY_ROOT, validate


ROOTS = ("candidate_hash", "predicate_input_root", "authority_root", "validator_root", "validator_version", "closure_definition_hash")


def _hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _files_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix().casefold()):
        digest.update(path.relative_to(REPOSITORY_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes() if path.is_file() else b"<deleted>")
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _contract() -> dict:
    return json.loads((PLAN_ROOT / "implementation-contract.v1.json").read_text(encoding="utf-8"))


def _repair_rounds() -> list[tuple[str, dict]]:
    rounds: list[tuple[str, dict]] = []
    paths = [
        *(PLAN_ROOT / "repair").glob("round-*/repair-plan.v1.json"),
        *(PLAN_ROOT / "successor").glob("round-*/repair-plan.v1.json"),
    ]
    for path in sorted(paths):
        rounds.append((path.relative_to(PLAN_ROOT).as_posix(), json.loads(path.read_text(encoding="utf-8"))))
    return rounds


def _slice(slice_id: str) -> dict:
    for item in _contract()["slices"]:
        if item["slice_id"] == slice_id:
            return {**item, "_identity_path": "implementation-contract.v1.json"}
    for identity_path, repair in _repair_rounds():
        for item in repair["slices"]:
            if item["id"] == slice_id:
                return {**item, "slice_id": item["id"], "depends_on": [], "candidate_paths": item["writeRoots"], "_identity_path": identity_path}
    raise ValueError("unknown slice")


def _slice_closure(slice_id: str) -> list[dict]:
    if (slice_id.startswith("R") or slice_id.startswith("SUC")) and not slice_id.startswith("RMAP-"):
        return [_slice(slice_id)]
    contract = _contract()
    by_rmap = {item["slice_id"]: item for item in contract["slices"]}
    selected: list[dict] = []
    seen: set[str] = set()

    def visit(current: str) -> None:
        if current in seen:
            return
        item = by_rmap.get(current)
        if item is None:
            raise ValueError("slice dependency is unknown")
        seen.add(current)
        for dependency in item.get("depends_on", []):
            visit(dependency)
        selected.append(item)

    visit(slice_id)
    return selected


def _matches(path: str, pattern: str) -> bool:
    pattern = pattern.replace("\\", "/")
    path = path.replace("\\", "/")
    return path.startswith(pattern[:-2]) if pattern.endswith("/**") else path == pattern


def _candidate_paths(slice_id: str) -> list[str]:
    roots = [
        root
        for item in _slice_closure(slice_id)
        for root in item.get("candidate_paths", item.get("write_roots", []))
    ]
    output: set[str] = set()
    for command in (["diff", "--name-only", "HEAD", "--"], ["diff", "--cached", "--name-only", "HEAD", "--"], ["ls-files", "--others", "--exclude-standard", "--"]):
        result = subprocess.run(["git", *command, *roots], cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
        if result.returncode == 0:
            output.update(path for path in result.stdout.splitlines() if any(_matches(path, root) for root in roots))
    return sorted(output, key=str.casefold)


def _worktree_hash(paths: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in paths:
        target = REPOSITORY_ROOT / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(target.read_bytes() if target.is_file() else b"<deleted>")
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def slice_validation_snapshot(slice_id: str) -> dict[str, str]:
    selected = _slice(slice_id)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True, encoding="utf-8").strip()
    contract_hash = _hash((PLAN_ROOT / selected["_identity_path"]).read_bytes())
    # A completed slice must not become stale merely because an independent
    # later slice adds a command, test, or predicate branch. The shared
    # snapshot algorithm plus the selected slice's actual candidate files are
    # the validator closure; the immutable implementation contract remains in
    # the candidate identity and still invalidates every slice when changed.
    validator_files = [PLAN_ROOT / "tools" / "validate_all.py"]
    validator_files.extend(REPOSITORY_ROOT / path for path in _candidate_paths(slice_id))
    validator_root = _files_hash(validator_files)
    authority_root = _files_hash([PLAN_ROOT / "authority-manifest.v1.json"])
    closure = _hash(json.dumps({"slice": selected, "forbidden": _contract()["global_forbidden_changes"]}, sort_keys=True).encode("utf-8"))
    candidate = _hash(json.dumps({"head": head, "slice": slice_id, "contract": contract_hash, "worktree": _worktree_hash(_candidate_paths(slice_id))}, sort_keys=True).encode("utf-8"))
    predicate = _hash(json.dumps({"candidate": candidate, "authority": authority_root, "validator": validator_root, "closure": closure}, sort_keys=True).encode("utf-8"))
    return {"candidate_hash": candidate, "predicate_input_root": predicate, "authority_root": authority_root, "validator_root": validator_root, "validator_version": "ria.workflow-validator.v1+" + validator_root, "closure_definition_hash": closure}


def current_candidate_identity(slice_id: str = "RMAP-S5") -> dict[str, str]:
    return slice_validation_snapshot(slice_id)


def validation_snapshot() -> dict[str, str]:
    return slice_validation_snapshot("RMAP-S5")


def main() -> int:
    findings = validate()
    result = {"status": "pass" if not findings else "fail", "findings": findings}
    if not findings:
        result["validation_snapshot"] = validation_snapshot()
    print(json.dumps(result, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())

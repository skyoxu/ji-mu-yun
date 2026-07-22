from __future__ import annotations

"""Build the non-authoritative S6 candidate from a frozen Git range.

This migration path is deliberately separate from the ordinary worktree-diff
candidate.  A replayed lifecycle proves current revalidation; the commit range
proves the already-committed implementation being revalidated.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from candidate_diff_guards import bytes_hash, scope_policy


def _value_hash(value: Any) -> str:
    return bytes_hash(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-c", "core.autocrlf=false", *args], cwd=root, capture_output=True, check=False)
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def _blob(root: Path, commit: str, path: str) -> bytes | None:
    result = subprocess.run(["git", "cat-file", "-e", f"{commit}:{path}"], cwd=root, capture_output=True, check=False)
    return None if result.returncode else _git(root, "show", f"{commit}:{path}")


def _matches(path: str, patterns: set[str]) -> bool:
    from candidate_diff_guards import _matches as match
    return match(path, patterns)


def _owner(contract: dict[str, Any], root: Path, plan: Path, path: str) -> str:
    # First owner is deterministic and rejects paths outside the declared S0-S6 closure.
    for index in range(7):
        policy = scope_policy(plan, root, contract, f"RMAP-S{index}")
        if _matches(path, policy["forbidden"]):
            raise ValueError(f"forbidden committed candidate path: {path}")
        if any(_matches(path, policy[key]) for key in ("production", "test", "documentation")):
            return f"RMAP-S{index}"
    raise ValueError(f"committed candidate path is outside S0-S6 write closure: {path}")


def build(plan: Path, run_dir: Path) -> dict[str, Any]:
    root = plan.parents[1]
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    policy = contract["candidate_identity_policy"]["committed_range"]
    base = str(policy["base_commit"])
    head = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    if not _git(root, "merge-base", "--is-ancestor", base, head) == b"":
        raise ValueError("committed candidate base is not an ancestor of HEAD")
    names = [item for item in _git(root, "diff", "--no-renames", "--name-only", "-z", base, head).decode("utf-8").split("\0") if item]
    files: list[dict[str, Any]] = []
    for path in sorted(names, key=str.casefold):
        before, after = _blob(root, base, path), _blob(root, head, path)
        change = "add" if before is None else "delete" if after is None else "modify"
        owner = _owner(contract, root, plan, path)
        files.append({"change_type": change, "baseline_path": None if change == "add" else path, "candidate_path": None if change == "delete" else path, "before_sha256": None if before is None else bytes_hash(before), "after_sha256": None if after is None else bytes_hash(after), "slice_id": owner, "commit_hashes": _git(root, "log", "--format=%H", f"{base}..{head}", "--", path).decode("ascii").split()})
    patch = _git(root, "diff", "--binary", "--full-index", "--no-renames", "--no-ext-diff", "--no-textconv", base, head, "--")
    range_map = {"schema_version": "jimuyun.committed-candidate-range.v1", "plan_id": contract["plan_id"], "slice_id": "RMAP-S6", "base_commit": base, "head_commit": head, "base_tree": _git(root, "rev-parse", f"{base}^{{tree}}").decode("ascii").strip(), "head_tree": _git(root, "rev-parse", "HEAD^{tree}").decode("ascii").strip(), "rename_policy": "delete-add-no-renames", "files": files, "authorizes": []}
    range_map["root_hash"] = _value_hash(range_map)
    manifest = {"schema_version": "jimuyun.candidate-diff-manifest.v2", "plan_id": contract["plan_id"], "slice_id": "RMAP-S6", "run_id": run_dir.name, "basis": "committed-range", "range_map_ref": {"path_type": "run_path", "path": "committed-candidate-range.json", "sha256": _value_hash(range_map)}, "files": files, "test_diff_ref": {"path_type": "run_path", "path": "test-diff.patch", "sha256": bytes_hash(patch)}}
    manifest["root_hash"] = _value_hash(manifest)
    lineage = {"schema_version": "jimuyun.candidate-lineage-manifest.v2", "plan_id": contract["plan_id"], "candidate_run_id": run_dir.name, "basis": "committed-range-revalidation", "committed_range_ref": manifest["range_map_ref"], "revalidation_run": {"slice_id": "RMAP-S6", "run_id": run_dir.name, "stage_projection_sha256": bytes_hash((run_dir / "stage-evidence-projection.v1.json").read_bytes())}, "authorizes": []}
    lineage["root_hash"] = _value_hash(lineage)
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, value in (("committed-candidate-range.json", range_map), ("changed-files.json", manifest), ("candidate-lineage-manifest.json", lineage)):
        (run_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (run_dir / "test-diff.patch").write_bytes(patch)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(); build(Path(__file__).resolve().parents[1], args.run_dir.resolve()); return 0


if __name__ == "__main__":
    raise SystemExit(main())

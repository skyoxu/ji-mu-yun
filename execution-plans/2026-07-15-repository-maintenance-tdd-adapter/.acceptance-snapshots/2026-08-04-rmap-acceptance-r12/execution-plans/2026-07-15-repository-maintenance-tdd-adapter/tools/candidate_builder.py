from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from candidate_diff_guards import bytes_hash, derive_candidate_snapshot, manifest_root_hash
from candidate_lineage_guards import load_candidate_lineage, value_hash
from validate_all import current_candidate_identity


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def build(plan_root: Path, run_dir: Path, lineage: dict[str, Any]) -> dict[str, Any]:
    root = plan_root.parents[1]
    contract = json.loads((plan_root / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    current = current_candidate_identity("RMAP-S6")
    files, patch, exclusions = derive_candidate_snapshot(plan_root, root, contract, replay_baseline_ref=lineage.get("replay_baseline_ref"))
    folded, fold_hash, findings = load_candidate_lineage(plan_root, root, lineage, run_dir.name, current, exclusions)
    if findings or [{key: item[key] for key in ("change_type", "baseline_path", "candidate_path", "before_sha256", "after_sha256")} for item in files] != folded:
        raise ValueError(f"candidate lineage does not equal current diff: {findings}")
    (run_dir / "test-diff.patch").write_bytes(patch)
    manifest = {"schema_version": "jimuyun.candidate-diff-manifest.v1", "plan_id": "repository-maintenance-tdd-adapter", "slice_id": "RMAP-S6", "run_id": run_dir.name, "rename_policy": "delete-add-no-renames", "baseline_identity": {key: current[key] for key in ("head", "index_tree")}, "candidate_identity": {key: current[key] for key in ("tracked_diff_hash", "untracked_manifest_hash", "candidate_worktree_hash")}, "files": files, "accepted_attempt_fold_hash": fold_hash, "test_diff_ref": {"path_type": "run_path", "path": "test-diff.patch", "sha256": bytes_hash(patch)}}
    manifest["root_hash"] = manifest_root_hash(manifest)
    _write(run_dir / "changed-files.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--lineage", type=Path, required=True)
    args = parser.parse_args()
    plan_root = Path(__file__).resolve().parents[1]
    lineage = json.loads(args.lineage.read_text(encoding="utf-8"))
    build(plan_root, args.run_dir, lineage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

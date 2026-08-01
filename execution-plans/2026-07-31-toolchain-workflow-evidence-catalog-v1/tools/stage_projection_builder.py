"""Build the plan-local stage effect projection consumed by Quick Dev."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


PLAN_ROOT = Path(__file__).resolve().parents[1]


def _hash(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _value_hash(value: Any) -> str:
    return _hash(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _head_bytes(root: Path, relative: str) -> bytes | None:
    completed = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=root, capture_output=True, check=False)
    return completed.stdout if completed.returncode == 0 else None


def _matches(relative: str, patterns: list[str]) -> bool:
    candidate = relative.replace("\\", "/").casefold()
    for pattern in patterns:
        folded = pattern.replace("\\", "/").casefold()
        if folded.endswith("/**") and (candidate == folded[:-3] or candidate.startswith(folded[:-2])):
            return True
        if fnmatch.fnmatchcase(candidate, folded):
            return True
    return False


def build(root: Path, run_dir: Path, slice_id: str, paths: list[str], baseline_paths: list[str] | None = None) -> dict[str, Any]:
    contract = json.loads((PLAN_ROOT / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = next((item for item in contract["slices"] if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict):
        raise ValueError("unknown slice")
    allowed = [value for values in selected["allowed_changes"].values() for value in values]
    normalized = [value.replace("\\", "/") for value in paths]
    if not normalized or any(any(token in value for token in ("*", "?", "[", "]")) or not _matches(value, allowed) for value in normalized):
        raise ValueError("projection paths must be explicit members of the slice write set")
    baseline: list[dict[str, str]] = []
    effects: list[dict[str, Any]] = []
    for relative in sorted(set((baseline_paths or normalized)), key=str.casefold):
        before = _head_bytes(root, relative)
        if before is not None:
            baseline.append({"path": relative, "sha256": _hash(before)})
    for relative in sorted(set(normalized), key=str.casefold):
        before = _head_bytes(root, relative)
        target = root / relative
        after = target.read_bytes() if target.is_file() else None
        if before is None and after is None:
            raise ValueError(f"projection path is absent from baseline and worktree: {relative}")
        if before == after:
            continue
        change = "add" if before is None else "delete" if after is None else "modify"
        effects.append(
            {
                "change_type": change,
                "baseline_path": None if before is None else relative,
                "candidate_path": None if after is None else relative,
                "before_sha256": None if before is None else _hash(before),
                "after_sha256": None if after is None else _hash(after),
            }
        )
    stage_hashes = {stage: _hash((run_dir / f"{stage}-result.json").read_bytes()) for stage in ("red", "green", "refactor")}
    document = {
        "schema_version": "jimuyun.stage-evidence-projection.v1",
        "plan_id": "toolchain-workflow-evidence-catalog-v1",
        "slice_id": slice_id,
        "run_id": run_dir.name,
        "baseline_files": baseline,
        "effects": effects,
        "stage_result_hashes": stage_hashes,
        "final_event_hash": stage_hashes["refactor"],
    }
    document["root_hash"] = _value_hash(document)
    return document

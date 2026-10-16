from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any

PLAN_DIR = Path(__file__).resolve().parents[1]


def _candidate_identity(slice_id: str) -> dict[str, str]:
    path = PLAN_DIR / "tools" / "validate_all.py"
    spec = importlib.util.spec_from_file_location("broh_stage_projection_validate_all", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("plan-local candidate identity helper is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.current_candidate_identity(slice_id)


def _hash(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _value_hash(value: Any) -> str:
    return _hash(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _head_bytes(root: Path, relative: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _allowed(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in patterns:
        candidate = pattern.replace("\\", "/")
        if candidate.endswith("/**") and normalized.startswith(candidate[:-3]):
            return True
        if normalized == candidate:
            return True
    return False


def build(root: Path, run_dir: Path, slice_id: str, paths: list[str], baseline_paths: list[str] | None = None) -> dict[str, Any]:
    contract = json.loads((PLAN_DIR / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = next((item for item in contract["slices"] if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict):
        raise ValueError(f"unknown slice: {slice_id}")
    if not paths or any(not isinstance(path, str) or not _allowed(path, [value for group in selected["allowed_changes"].values() for value in group]) for path in paths):
        raise ValueError("projection paths must be explicit members of the slice write set")

    baseline_files: list[dict[str, str]] = []
    effects: list[dict[str, str | None]] = []
    for relative in sorted(set(baseline_paths or paths), key=str.casefold):
        before = _head_bytes(root, relative)
        if before is not None:
            baseline_files.append({"path": relative, "sha256": _hash(before)})
    for relative in sorted(set(paths), key=str.casefold):
        before = _head_bytes(root, relative)
        current_path = root / relative
        current = current_path.read_bytes() if current_path.is_file() else None
        if before is None and current is None:
            raise ValueError(f"projection path is absent from both baseline and worktree: {relative}")
        if before == current:
            continue
        change_type = "add" if before is None else "delete" if current is None else "modify"
        effects.append({
            "change_type": change_type,
            "baseline_path": None if change_type == "add" else relative,
            "candidate_path": None if change_type == "delete" else relative,
            "before_sha256": None if before is None else _hash(before),
            "after_sha256": None if current is None else _hash(current),
        })

    stage_hashes = {
        stage: _hash((run_dir / f"{stage}-result.json").read_bytes())
        for stage in ("red", "green", "refactor")
    }
    document: dict[str, Any] = {
        "schema_version": "jimuyun.stage-evidence-projection.v1",
        "plan_id": contract["plan_id"],
        "slice_id": slice_id,
        "run_id": run_dir.name,
        "baseline_files": baseline_files,
        "effects": effects,
        "stage_result_hashes": stage_hashes,
        "final_event_hash": stage_hashes["refactor"],
        "candidate_identity": _candidate_identity(slice_id),
    }
    document["root_hash"] = _value_hash(document)
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--path", action="append", required=True)
    parser.add_argument("--baseline-path", action="append")
    args = parser.parse_args()
    root = PLAN_DIR.parents[1]
    output = args.run_dir / "stage-evidence-projection.v1.json"
    output.write_text(json.dumps(build(root, args.run_dir, args.slice_id, args.path, args.baseline_path), indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

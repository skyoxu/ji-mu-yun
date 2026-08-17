from __future__ import annotations

import hashlib
import json
from pathlib import Path


def build(root: Path, run_dir: Path, slice_id: str, paths: list[str], baseline_paths: list[str] | None = None) -> dict[str, object]:
    del root
    observations = {stage: "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() for stage in ("red", "green", "refactor") if (path := run_dir / "observations" / f"{stage}-observed.json").is_file()}
    result: dict[str, object] = {"schema_version": "quick-dev-tdd-stage-recovery.stage-projection.v1", "slice_id": slice_id, "run_id": run_dir.name, "paths": sorted(set(paths)), "baseline_paths": sorted(set(baseline_paths or paths)), "stage_observation_hashes": observations, "authorizes": []}
    result["root_hash"] = "sha256:" + hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return result

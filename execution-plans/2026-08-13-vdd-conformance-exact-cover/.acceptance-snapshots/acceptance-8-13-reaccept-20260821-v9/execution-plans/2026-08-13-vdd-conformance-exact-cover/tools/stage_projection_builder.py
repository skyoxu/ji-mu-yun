from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _hash(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def build(root: Path, run_dir: Path, slice_id: str, paths: list[str], baseline_paths: list[str] | None = None) -> dict[str, object]:
    stages = {}
    for stage in ("red", "green", "refactor"):
        path = run_dir / f"{stage}.json"
        if path.is_file():
            stages[stage] = _hash(path.read_bytes())
    document: dict[str, object] = {
        "schema_version": "vdd-conformance-exact-cover.stage-projection.v1",
        "slice_id": slice_id,
        "run_id": run_dir.name,
        "paths": sorted(set(paths)),
        "baseline_paths": sorted(set(baseline_paths or paths)),
        "stage_result_hashes": stages,
    }
    document["root_hash"] = _hash(json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return document

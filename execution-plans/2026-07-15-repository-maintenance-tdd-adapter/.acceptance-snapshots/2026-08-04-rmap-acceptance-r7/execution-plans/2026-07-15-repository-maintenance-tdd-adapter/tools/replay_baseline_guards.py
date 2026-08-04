from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from candidate_lineage_guards import bytes_hash, manifest_root_hash
from contract_guards import contained_file, schema_error


def _finding(target: str, message: str) -> dict[str, str]:
    return {"rule_id": "RMAP-REPLAY-BASELINE", "target": target, "message": message}


def load_replay_baseline(
    plan_root: Path, repository_root: Path, reference: dict[str, Any] | None,
    current_entries: dict[str, dict[str, Any]],
) -> tuple[set[str], list[dict[str, str]]]:
    if reference is None:
        return set(), []
    path = contained_file(repository_root, reference.get("path"))
    if path is None or reference.get("sha256") != bytes_hash(path.read_bytes()):
        return set(), [_finding("replay-baseline", "manifest reference is stale or outside the repository")]
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        schema = json.loads((plan_root / "schemas" / "replay-baseline-manifest.v1.schema.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return set(), [_finding(str(path), str(exc))]
    error = schema_error(manifest, schema)
    if error or manifest.get("root_hash") != manifest_root_hash(manifest):
        return set(), [_finding(str(path), error or "manifest root hash is stale")]
    source = contained_file(repository_root, manifest.get("source_mismatch_ref"))
    if source is None or manifest.get("source_mismatch_sha256") != bytes_hash(source.read_bytes()):
        return set(), [_finding(str(path), "source mismatch evidence is stale or outside the repository")]
    excluded: set[str] = set()
    for item in manifest["paths"]:
        target = str(item["path"])
        if target in excluded or item["candidate_change"] != current_entries.get(target):
            return set(), [_finding(str(path), f"bootstrap path is duplicate, missing, or stale: {target}")]
        excluded.add(target)
    return excluded, []

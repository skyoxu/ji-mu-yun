from __future__ import annotations
from typing import Any, Callable

def snapshot(contract: dict[str, Any], slice_id: str, source_hash: str, closure_hash: str, _authority_hash: str, validator: str, value_hash: Callable[[Any], str]) -> dict[str, str]:
    by_id = {item.get("slice_id"): item for item in contract.get("slices", [])}
    if slice_id not in by_id:
        raise ValueError(f"unknown slice identity scope: {slice_id}")
    included, pending = set(), [slice_id]
    while pending:
        current = pending.pop()
        if current in included:
            continue
        item = by_id.get(current)
        if not isinstance(item, dict):
            raise ValueError("slice dependency is invalid")
        included.add(current); pending.extend(item.get("depends_on", []))
    scoped = {"plan_id": contract.get("plan_id"), "slices": [item for item in contract.get("slices", []) if item.get("slice_id") in included]}
    scope_hash = value_hash(scoped)
    authority_scope = {"source_hashes": contract.get("authority", {}).get("source_hashes", {}), "slice_scope": scoped}
    return {"candidate_hash": scope_hash, "source_hash": source_hash, "validator_version": validator, "predicate_input_root": scope_hash, "closure_definition_hash": closure_hash, "authority_root": value_hash(authority_scope), "validator_root": "sha256:" + validator.rsplit("sha256:", 1)[1]}

"""Read-only compatibility inspection for historical Quick Dev/VDD plans."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def inspect_legacy_plan(plan_dir: Path) -> dict[str, Any]:
    current = plan_dir / "semantic-plan-bundle.v1.json"
    if current.is_file():
        return {"route": "current", "repair_required": False, "reason": "current semantic bundle present"}
    legacy = plan_dir / "implementation-contract.v1.json"
    if not legacy.is_file():
        return {"route": "reject", "repair_required": True, "reason": "no current or legacy implementation contract"}
    value = json.loads(legacy.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        return {"route": "reject", "repair_required": True, "reason": "legacy contract is not an object"}
    slices = value.get("slices")
    if not isinstance(slices, list) or not slices:
        return {"route": "compatibility", "repair_required": True, "reason": "legacy slice contract missing"}
    return {
        "route": "compatibility",
        "repair_required": True,
        "reason": "historical v1 lacks current atomic obligation/V5/V6/V6A authority",
        "legacy_schema": value.get("schema_version"),
        "slice_ids": [item.get("slice_id") for item in slices if isinstance(item, Mapping)],
        "authorizes_current_evidence": False,
        "authorizes": [],
    }

"""Expose the plan-local validator identity required by the Quick Dev adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


PLAN = Path(__file__).resolve().parents[1]


def _hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def current_candidate_identity(slice_id: str) -> dict[str, str]:
    contract = json.loads((PLAN / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    registry = json.loads((PLAN / "command-registry.v1.json").read_text(encoding="utf-8"))
    selected = next((item for item in contract["slices"] if item["slice_id"] == slice_id), None)
    if selected is None:
        raise ValueError("unknown slice")
    projection = {
        "plan_id": contract["plan_id"],
        "slice": selected,
        "registry": registry,
        "terminal": contract["terminal"],
    }
    return {"validator_hash": _hash(projection)}

"""Expose the plan-local validator identity required by Quick Dev."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1]

_CANDIDATE_SOURCES = {
    "R0": [".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py"],
    "R1": [".agents/skills/quick-dev-tdd-adapter/tools/loop_plan_directory.py"],
    "R2": [
        ".agents/skills/quick-dev-tdd-adapter/tools/knowledge_context.py",
        ".agents/skills/run-refactor-implementation-acceptance/scripts/knowledge_context.py",
    ],
    "R3": [".agents/skills/quick-dev-tdd-adapter/tools/route_plan_directory.py"],
    "R4": [".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py"],
}


def _identity(slice_id: str | None = None) -> dict[str, str]:
    contract = json.loads((PLAN / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    registry = json.loads((PLAN / "command-registry.v1.json").read_text(encoding="utf-8"))
    selected = None if slice_id is None else next((item for item in contract["slices"] if item["slice_id"] == slice_id), None)
    if slice_id is not None and selected is None:
        raise ValueError("unknown slice")
    payload = {"plan_id": contract["plan_id"], "slice": selected, "registry": registry, "terminal": contract["terminal"]}
    return {"validator_hash": "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()}


def current_candidate_identity(slice_id: str) -> dict[str, str]:
    identity = _identity(slice_id)
    root = PLAN.parents[1]
    sources = _CANDIDATE_SOURCES.get(slice_id)
    if not sources:
        raise ValueError("slice candidate sources are undefined")
    digest = hashlib.sha256()
    for relative in sources:
        source = root / relative
        digest.update(relative.encode("utf-8") + b"\0" + source.read_bytes())
    identity["candidate_hash"] = "sha256:" + digest.hexdigest()
    return identity


def validation_snapshot() -> dict[str, str]:
    return _identity(None) | {
        "candidate_hash": "sha256:" + hashlib.sha256((PLAN / "implementation-contract.v1.json").read_bytes()).hexdigest(),
        "predicate_input_root": "execution-plans/2026-08-18-acceptance-coordinator-trust-recovery",
        "authority_root": "execution-plans/2026-08-18-acceptance-coordinator-trust-recovery/authority-manifest.v1.json",
        "validator_root": "execution-plans/2026-08-18-acceptance-coordinator-trust-recovery/tools/validate_all.py",
        "validator_version": "acceptance-coordinator-trust-recovery-validator.v1",
        "closure_definition_hash": "sha256:" + hashlib.sha256((PLAN / "repair/round-1/repair-closure.json").read_bytes()).hexdigest(),
    }


def slice_validation_snapshot(slice_id: str) -> dict[str, str]:
    return validation_snapshot() | current_candidate_identity(slice_id)

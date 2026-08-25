from __future__ import annotations

import hashlib
from pathlib import Path
import json


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def current_candidate_identity(slice_id: str) -> dict[str, str]:
    root = Path(__file__).resolve().parents[3]
    contract = root / "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/implementation-contract.v1.json"
    registry = root / "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/command-registry.v1.json"
    return {
        "candidate_hash": _sha(contract),
        "predicate_input_root": _sha(registry),
        "authority_root": _sha(root / "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/knowledge-context.freeze.v1.json"),
        "validator_root": _sha(Path(__file__).resolve()),
        "validator_version": "plan-local-bootstrap-v1",
        "closure_definition_hash": _sha(contract),
        "validator_hash": _sha(Path(__file__).resolve()),
    }


def validation_snapshot(slice_id: str | None = None) -> dict[str, str]:
    return current_candidate_identity(slice_id or "S6")


def slice_validation_snapshot(slice_id: str | None = None) -> dict[str, str]:
    return validation_snapshot(slice_id)


def validate_terminal(plan_dir: Path) -> dict[str, object]:
    """Validate the closed evidence envelope before implementation-complete."""
    required = [plan_dir / "terminal-evidence" / f"S{i}.json" for i in range(1, 7)]
    fixtures = plan_dir / "false-green-fixtures" / "nine-fixtures.json"
    missing = [path.as_posix() for path in [*required, fixtures] if not path.is_file()]
    if missing:
        return {"status": "blocked", "predicate": "implementation-complete", "missing": missing}
    try:
        records = [json.loads(path.read_text(encoding="utf-8")) for path in required]
        fixture_doc = json.loads(fixtures.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"status": "blocked", "predicate": "implementation-complete", "reason": "invalid-evidence-json"}
    if any(item.get("status") != "pass" or item.get("slice_id") != f"S{i+1}" for i, item in enumerate(records)):
        return {"status": "blocked", "predicate": "implementation-complete", "reason": "slice-evidence-not-closed"}
    if not isinstance(fixture_doc, dict) or fixture_doc.get("count") != 9 or fixture_doc.get("status") != "pass":
        return {"status": "blocked", "predicate": "implementation-complete", "reason": "false-green-fixtures-not-closed"}
    return {"status": "pass", "predicate": "implementation-complete", "slice_count": 6, "false_green_fixture_count": 9}

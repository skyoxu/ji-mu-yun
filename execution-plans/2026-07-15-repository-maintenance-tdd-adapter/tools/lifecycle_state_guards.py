from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contract_guards import schema_error


LIFECYCLE_EXCLUSIONS = {"implementation-complete", "acceptance-passed", "archived"}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("document root must be an object")
    return value


def validate_implementation_authorization(
    plan_root: Path, document: dict[str, Any], document_path: str
) -> list[dict[str, str]]:
    error = schema_error(document, _load(plan_root / "schemas" / "implementation-authorization.v1.schema.json"))
    if error:
        return [{"rule_id": "RMAP-IMPLEMENTATION-AUTHORIZATION", "target": document_path, "message": error}]
    mode = document["mode"]
    if mode == "bootstrap-three-rounds":
        envelopes = document.get("bootstrap_envelopes", [])
        if len(envelopes) != 3 or not all(isinstance(item, dict) and item.get("finalStatus") in {"clean", "advisory"} for item in envelopes):
            return [{"rule_id": "RMAP-IMPLEMENTATION-AUTHORIZATION", "target": document_path, "message": "three finalized Bootstrap envelopes are required"}]
    if mode == "user-confirmed-override":
        override = document.get("operator_override_path", "")
        if not isinstance(override, str) or override.startswith("execution-plans/") or override.startswith(".agents/skills/quick-dev-tdd-adapter/"):
            return [{"rule_id": "RMAP-IMPLEMENTATION-AUTHORIZATION", "target": document_path, "message": "operator override must remain outside plan and Quick Dev write roots"}]
    if not LIFECYCLE_EXCLUSIONS.issubset(set(document["does_not_authorize"])):
        return [{"rule_id": "RMAP-IMPLEMENTATION-AUTHORIZATION", "target": document_path, "message": "implementation authorization escalates to a later lifecycle state"}]
    return []


def validate_legacy_migration(plan_root: Path, document: dict[str, Any]) -> list[dict[str, str]]:
    error = schema_error(document, _load(plan_root / "schemas" / "legacy-lifecycle-migration.v1.schema.json"))
    if error or document.get("authorizes") != [] or "implementation-authorized" not in document.get("does_not_authorize", []):
        return [{"rule_id": "RMAP-LEGACY-NOT-RETROACTIVE", "target": "legacy-lifecycle-migration", "message": "legacy migration must not authorize implementation or later states"}]
    return []

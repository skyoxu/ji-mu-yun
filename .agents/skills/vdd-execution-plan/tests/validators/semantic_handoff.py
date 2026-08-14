from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def _hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _valid() -> dict[str, object]:
    envelope = {"run_id": "RUN-semantic", "source_freeze_hash": _hash("freeze"), "affected_ids": ["VCEC-001"], "ambiguity_ids": ["AMB-001"], "allowed_repair_scope": ["requirements-and-acceptance.md"]}
    return {"schema_version": "vdd-repair-input.v1", "route": "bootstrap-upstream-plan", "envelope": envelope, "envelope_hash": _hash(envelope), "authorizes": [], "implementation_candidate": None}


def main() -> int:
    value = _valid()
    return 0 if value["route"] == "bootstrap-upstream-plan" and value["authorizes"] == [] and value["implementation_candidate"] is None and value["envelope_hash"] == _hash(value["envelope"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())

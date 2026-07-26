"""Build a VDD-owned, hash-bound knowledge-consumption preflight result."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def evaluate_consumption(*, required_modules: list[str], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    satisfied: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for decision in decisions:
        accepted = decision.get("decision") == "accepted"
        modules = decision.get("satisfies", [])
        if not isinstance(modules, list) or any(not isinstance(value, str) or not value for value in modules):
            raise ValueError("invalid consumption decision modules")
        if accepted and not modules:
            raise ValueError("accepted decision must satisfy a module")
        if not accepted and modules:
            raise ValueError("rejected decision cannot satisfy a module")
        if accepted:
            satisfied.update(modules)
        normalized.append({"decision": "accepted" if accepted else "rejected", "satisfies": modules})
    missing = sorted(set(required_modules) - satisfied)
    return {"status": "blocked" if missing else "ready", "missing_required_modules": missing, "decisions": normalized}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = evaluate_consumption(required_modules=payload.get("required_modules", []), decisions=payload.get("decisions", []))
    result["schema_version"] = "jimuyun.vdd-knowledge-preflight.v1"
    result["input_sha256"] = _sha(payload)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())

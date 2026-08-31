"""Production owner entrypoint for VDD semantic validation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from semantic_plan_contract import validate_semantic_bundle


def _legacy_validate(value: object) -> tuple[bool, list[str]]:
    if not isinstance(value, dict):
        return False, ["legacy-input:not-object"]
    required = {"acceptance_ids", "producer", "coverage", "fixture_class", "taxonomy"}
    missing = sorted(required - set(value))
    return (not missing, [f"legacy-input:missing:{name}" for name in missing])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-dir", required=True)
    parser.add_argument("--input", required=False)
    args = parser.parse_args()

    plan_dir = Path(args.plan_dir)
    candidate = Path(args.input) if args.input else plan_dir / "semantic-plan-bundle.v1.json"
    if not candidate.is_file():
        return 0

    try:
        value = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "findings": [f"input:{exc}"]}, sort_keys=True))
        print("FAILURE_ID:VDD-SEMANTIC-PLAN-INVALID")
        return 1

    if isinstance(value, dict) and value.get("schema_version") == "vdd.semantic-plan-bundle.v1":
        valid, findings = validate_semantic_bundle(value)
    else:
        valid, findings = _legacy_validate(value)
    print(json.dumps({"valid": valid, "findings": findings}, sort_keys=True))
    if not valid:
        print("FAILURE_ID:VDD-SEMANTIC-PLAN-INVALID")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

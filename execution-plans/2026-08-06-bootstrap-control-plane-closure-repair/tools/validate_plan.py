from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "00-index.md", "requirements.v1.json", "implementation-contract.v1.json",
    "command-registry.v1.json", "authority-manifest.v1.json", "baseline-and-scope.v1.json",
    "model-route-decision.v1.json", "knowledge-context.v1.json",
    "knowledge-context.freeze.v1.json", "plan-state.v1.json", "resume-state.v1.json",
]


def validate(root: Path = ROOT) -> list[str]:
    errors = [f"missing:{p}" for p in REQUIRED if not (root / p).is_file()]
    try:
        contract = json.loads((root / "implementation-contract.v1.json").read_text(encoding="utf-8"))
        slices = contract["slices"]
        ids = [item["slice_id"] for item in slices]
        if ids != ["CP-S0", "CP-S1", "CP-S2"] or len(ids) != len(set(ids)):
            errors.append("slice-set-invalid")
        registry = json.loads((root / "command-registry.v1.json").read_text(encoding="utf-8"))
        commands = registry.get("commands", [])
        if not commands or any(not isinstance(c.get("id"), str) or c.get("shell") is not False for c in commands):
            errors.append("command-registry-invalid")
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"contract-invalid:{exc}")
    return errors


if __name__ == "__main__":
    errors = validate()
    print(json.dumps({"status": "pass" if not errors else "fail", "errors": errors, "authorizes": ["plan-ready"] if not errors else []}))
    raise SystemExit(0 if not errors else 1)

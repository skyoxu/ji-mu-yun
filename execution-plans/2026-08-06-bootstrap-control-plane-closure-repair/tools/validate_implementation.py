from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate(root: Path = ROOT) -> list[str]:
    state = json.loads((root / "plan-state.v1.json").read_text(encoding="utf-8"))
    if state.get("state") != "plan-ready":
        return ["implementation-requires-plan-ready"]
    return []


if __name__ == "__main__":
    errors = validate()
    print(json.dumps({"status": "pass" if not errors else "fail", "errors": errors, "authorizes": []}))
    raise SystemExit(1 if errors else 0)

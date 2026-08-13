"""Implementation terminal gate; blocked until S0-S5 implementation evidence exists."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"


def main() -> int:
    contract = json.loads((PLAN / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    if contract.get("lifecycle_state") != "implementation-complete":
        print("terminal-full=blocked implementation-not-ready")
        return 2
    print("terminal-full=requires-current-producer-consumer-dogfood")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

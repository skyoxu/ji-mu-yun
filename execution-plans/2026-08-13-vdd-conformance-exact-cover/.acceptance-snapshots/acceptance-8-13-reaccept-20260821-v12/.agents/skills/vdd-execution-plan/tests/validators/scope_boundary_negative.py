"""Reject VDD code that embeds Exact-cover or Bootstrap implementation."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
VDD = ROOT / ".agents/skills/vdd-execution-plan"


def main() -> int:
    forbidden = ("vdd-conformance-exact-cover", "bootstrap-upstream-plan")
    for path in VDD.rglob("*.py"):
        if "tests" in path.parts:
            continue
        content = path.read_text(encoding="utf-8")
        if any(token in content for token in forbidden):
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Positive, negative, and mutation checks for FR/NFR/SM-C and A-* syntax."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import _expanded_ids, _expanded_acceptance_ids  # noqa: E402


def main() -> int:
    positive = "FR-1..FR-3, NFR-1..NFR-2, SM-1..SM-4, SM-C1..SM-C3"
    expected = {"FR-1", "FR-2", "FR-3", "NFR-1", "NFR-2", "SM-1", "SM-2", "SM-3", "SM-4", "SM-C1", "SM-C2", "SM-C3"}
    actual = {item for prefix in ("FR", "NFR", "SM", "SM-C") for item in _expanded_ids(positive, prefix)}
    if actual != expected:
        return 2
    if _expanded_acceptance_ids("A-SEMANTIC, A-TERMINAL", "A") != ["A-SEMANTIC", "A-TERMINAL"]:
        return 2
    negative = {item for prefix in ("FR", "NFR", "SM", "SM-C") for item in _expanded_ids("FR-1X SM-C-1", prefix)}
    if negative:
        return 2
    mutated = {item for prefix in ("FR", "NFR", "SM", "SM-C") for item in _expanded_ids("SM-C1..SM-C4", prefix)}
    if "SM-C4" not in mutated or len(mutated) != 4:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

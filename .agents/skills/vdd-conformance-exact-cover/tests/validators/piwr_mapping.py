"""PIWR exact-cover regression: canonical acceptance edges are not a Cartesian product."""
from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
PLAN = ROOT / "execution-plans/2026-08-24-phase-b-c-identity-isolation-workspace-recovery"
MAPPING = PLAN / "repair/round-2/requirements-acceptance.v1.json"


def _ids(text: str) -> set[str]:
    values: set[str] = set()
    for part in re.split(r"[,;]", text):
        numbers = [int(value) for value in re.findall(r"\d{3}", part)]
        if "PIWR" not in part and ".." not in part:
            continue
        if numbers:
            values.update(f"PIWR-{value:03d}" for value in range(numbers[0], numbers[-1] + 1 if ".." in part else numbers[0] + 1))
    return values


def main() -> int:
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    assert len(mapping["requirements"]) == 40
    assert len(mapping["acceptance_ids"]) == 18
    assert sum(len(item["acceptance_ids"]) for item in mapping["requirements"]) == 105
    assert sum(len(item) for item in mapping["reverse_mapping"].values()) == 105
    assert mapping["requirements"][0]["acceptance_ids"] == ["PIWR-A01", "PIWR-A18"]
    assert mapping["requirements"][4]["acceptance_ids"] == ["PIWR-A02", "PIWR-A18"]
    assert mapping["reverse_mapping"]["PIWR-A01"] == ["PIWR-001", "PIWR-002", "PIWR-010", "PIWR-036"]
    assert mapping["reverse_mapping"]["PIWR-A05"] == ["PIWR-015", "PIWR-016", "PIWR-020"]
    print("piwr-mapping-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

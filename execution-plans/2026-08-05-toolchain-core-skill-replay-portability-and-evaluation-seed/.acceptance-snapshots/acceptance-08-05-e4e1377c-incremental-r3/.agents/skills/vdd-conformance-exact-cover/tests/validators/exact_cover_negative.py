from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import exact_cover  # noqa: E402


def main() -> int:
    path = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover/repair/round-5/requirements-acceptance-slice-command.v1.json"
    data = copy.deepcopy(json.loads(path.read_text(encoding="utf-8")))
    data["reverse_mapping"]["VCEC-A01"] = []
    result = exact_cover(data["requirements"], data["acceptance_ids"], data["reverse_mapping"])
    return 1 if result["status"] == "blocked" and any(item["code"] == "wrong_binding" for item in result["errors"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())

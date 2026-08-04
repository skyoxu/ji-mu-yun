from __future__ import annotations

import json
import unittest
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[2]


class S2RedProbeContractTests(unittest.TestCase):
    def test_s2_red_uses_a_controlled_probe_distinct_from_green(self) -> None:
        contract = json.loads((PLAN_ROOT / "implementation-contract.v1.json").read_text(encoding="utf-8"))
        s2 = next(item for item in contract["slices"] if item["slice_id"] == "RMAP-S2")
        self.assertEqual("rmap-observe-adapter-red", s2["tdd"]["red"]["command_id"])
        self.assertEqual("rmap-adapter-tests", s2["tdd"]["green"]["command_id"])
        self.assertNotEqual(s2["tdd"]["red"]["command_id"], s2["tdd"]["green"]["command_id"])


if __name__ == "__main__":
    unittest.main()

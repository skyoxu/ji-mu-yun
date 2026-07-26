from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_PATH = SKILL_ROOT / "scripts" / "vdd_knowledge_preflight.py"


def load_preflight():
    if not PREFLIGHT_PATH.is_file():
        raise FileNotFoundError(PREFLIGHT_PATH)
    spec = importlib.util.spec_from_file_location("vdd_knowledge_preflight", PREFLIGHT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VddKnowledgePreflightTests(unittest.TestCase):
    def test_all_rejected_candidates_block_plan_ready(self) -> None:
        try:
            module = load_preflight()
        except FileNotFoundError:
            self.fail("KWI-CONSUMPTION-REQUIRED-UNCOVERED: VDD knowledge preflight is missing")
        result = module.evaluate_consumption(
            required_modules=["repository-rules"],
            decisions=[{"decision": "rejected", "satisfies": []}],
        )
        self.assertEqual("blocked", result["status"])
        self.assertEqual(["repository-rules"], result["missing_required_modules"])


if __name__ == "__main__":
    unittest.main()

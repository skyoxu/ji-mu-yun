from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]
MODULE_PATH = TOOLS / "knowledge_context.py"


def load_module():
    if not MODULE_PATH.is_file():
        raise FileNotFoundError(MODULE_PATH)
    spec = importlib.util.spec_from_file_location("quick_dev_knowledge_context", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QuickDevKnowledgeContextTests(unittest.TestCase):
    def test_locator_result_or_consumption_decision_cannot_expand_frozen_context(self) -> None:
        try:
            module = load_module()
        except FileNotFoundError:
            self.fail("KWI-QUICK-SCOPE-EXPANSION: verify-bound knowledge context is missing")
        frozen = {"accepted": [{"path": "docs/a.md", "source_sha256": "a" * 64, "satisfies": ["repository-rules"]}]}
        proposed = {"accepted": [{"path": "docs/a.md", "source_sha256": "a" * 64, "satisfies": ["repository-rules", "extra"]}]}
        result = module.verify_frozen_context(frozen, proposed)
        self.assertEqual("vdd-repair", result["status"])
        self.assertEqual("KWI-QUICK-SCOPE-EXPANSION", result["failure_code"])


if __name__ == "__main__":
    unittest.main()

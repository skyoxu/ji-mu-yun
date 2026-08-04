from __future__ import annotations

import json
from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
SHADOW_FIXTURE = REPOSITORY_ROOT / "execution-plans/2026-07-12-llm-review-evidence-gate-hardening/fixtures/tdd-adapter-shadow.v1.json"


class ShadowContractTests(unittest.TestCase):
    def test_shadow_contract_missing_is_rejected(self) -> None:
        self.assertTrue(SHADOW_FIXTURE.is_file(), "RMAP-SHADOW-CONTRACT-MISSING")
        document = json.loads(SHADOW_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual("rmap.tdd-adapter-shadow.v1", document.get("schema_version"), "RMAP-SHADOW-CONTRACT-MISSING")
        self.assertFalse(document.get("authoritative"), "RMAP-SHADOW-CONTRACT-MISSING")


if __name__ == "__main__":
    unittest.main()

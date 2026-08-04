from __future__ import annotations

import json
from pathlib import Path
import unittest


FIXTURE = Path(__file__).resolve().parents[5] / "execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/fixtures/tdd-adapter-shadow.v1.json"


class Shadow0711Tests(unittest.TestCase):
    def test_shadow_0711_contract_missing_is_rejected(self) -> None:
        self.assertTrue(FIXTURE.is_file(), "RMAP-SHADOW-CONTRACT-MISSING")
        value = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual("rmap.tdd-adapter-shadow.v1", value.get("schema_version"), "RMAP-SHADOW-CONTRACT-MISSING")
        self.assertFalse(value.get("authoritative"), "RMAP-SHADOW-CONTRACT-MISSING")


if __name__ == "__main__":
    unittest.main()

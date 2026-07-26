from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ADR_PATH = REPOSITORY_ROOT / "docs" / "adr" / "ADR-0048-repository-knowledge-locator-workflow-consumption.md"
ADR_INDEX_PATH = REPOSITORY_ROOT / "docs" / "architecture" / "ADR_INDEX_PHASE.md"


class KnowledgeLocatorAuthorityTests(unittest.TestCase):
    def test_missing_adr_blocks(self) -> None:
        if not ADR_PATH.is_file():
            self.fail("KWI-AUTH-ADR-MISSING: ADR-0048 must be accepted before locator implementation")

        adr = ADR_PATH.read_text(encoding="utf-8")
        self.assertIn("- Status: Accepted", adr, "KWI-AUTH-ADR-MISSING: ADR-0048 must be accepted")
        self.assertIn("Extends ADR-0044", adr, "KWI-AUTH-RELATIONSHIP: ADR-0048 must extend ADR-0044")
        self.assertIn("Complements ADR-0037, ADR-0041, and ADR-0043", adr, "KWI-AUTH-RELATIONSHIP: ADR-0048 complement set is incomplete")
        self.assertIn("does not supersede", adr.lower(), "KWI-AUTH-RELATIONSHIP: ADR-0048 must not supersede existing ADRs")
        self.assertIn("derived_cache", adr, "KWI-AUTH-DERIVED-CACHE: knowledge projections must remain derived")

        index = ADR_INDEX_PATH.read_text(encoding="utf-8")
        self.assertIn("ADR-0048", index, "KWI-AUTH-INDEX: ADR-0048 must be indexed")


if __name__ == "__main__":
    unittest.main()

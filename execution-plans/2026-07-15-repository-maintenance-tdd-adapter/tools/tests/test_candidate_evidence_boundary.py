from __future__ import annotations

import sys
import unittest
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLAN_ROOT / "tools"))

from evidence_guards import validate_candidate_document
from validate_all import current_candidate_identity


class CandidateEvidenceBoundaryTests(unittest.TestCase):
    def test_validation_envelope_is_not_a_candidate_entity(self) -> None:
        envelope = {
            "schema_version": "rmap.validation-result.v1",
            "predicate": "implementation-candidate",
            "status": "pass",
        }
        findings = validate_candidate_document(
            PLAN_ROOT,
            "logs/tdd-adapter/run/candidate-result.json",
            envelope,
            current_candidate_identity(),
        )
        self.assertIn("RMAP-REVIEW-EVIDENCE-BINDING", {item["rule_id"] for item in findings})


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from review_requirement import decide_review_requirement


class ReviewRequirementTests(unittest.TestCase):
    def test_broh_s4_acceptance_owns_review_requirement(self) -> None:
        required = decide_review_requirement({
            "candidate": {
                "candidateHash": "sha256:" + "a" * 64,
                "changedPaths": [".agents/skills/run-phase-bootstrap-review/SKILL.md"],
                "workflowControlPlaneChange": True,
            },
            "deterministicEvidence": {"status": "passed", "hash": "sha256:" + "b" * 64},
            "protectedFacts": {"highRiskBoundary": False},
            "maintainerIntent": "default",
            "callerRequirement": "not_required",
        })
        self.assertEqual(required["requirement"], "required")
        self.assertIn("workflow-control-plane-change", required["reasonCodes"])
        self.assertEqual(required["profile"], "bootstrap-implementation-conformance")
        self.assertEqual(required["decisionVersion"], "v9")
        self.assertRegex(required["decisionHash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(required["authorizes"], [])
        self.assertEqual(required["callerRequirement"], "not_required")

        low_risk = decide_review_requirement({
            "candidate": {
                "candidateHash": "sha256:" + "c" * 64,
                "changedPaths": ["docs/ordinary-note.md"],
                "workflowControlPlaneChange": False,
            },
            "deterministicEvidence": {"status": "passed", "hash": "sha256:" + "d" * 64},
            "protectedFacts": {"highRiskBoundary": False},
            "maintainerIntent": "default",
            "callerRequirement": "required",
        })
        self.assertEqual(low_risk["requirement"], "not_required")
        self.assertIn("deterministic-low-risk", low_risk["reasonCodes"])
        self.assertRegex(low_risk["decisionHash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(low_risk["authorizes"], [])


if __name__ == "__main__":
    unittest.main()

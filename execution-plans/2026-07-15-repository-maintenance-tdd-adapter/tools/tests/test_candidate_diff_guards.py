from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[2]
TOOLS = PLAN_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from candidate_diff_guards import fold_accepted_attempts, validate_candidate_fixture_suite  # noqa: E402


class CandidateDiffGuardTests(unittest.TestCase):
    def test_candidate_diff_mutation_suite_is_exact(self) -> None:
        self.assertEqual([], validate_candidate_fixture_suite(PLAN_ROOT))

    def test_add_then_delete_folds_to_no_candidate_change(self) -> None:
        path = "docs/transient.md"
        bundle = {
            "baseline_file_manifest": {"files": [{"path": path, "sha256": None}]},
            "attempts": [
                {"adapter_decision": {"attempt_id": "ATTEMPT-001", "decision": "accepted_for_validation"}, "diff_manifest": {"files": [{"path": path, "before_sha256": None, "after_sha256": "sha256:" + "1" * 64}]}},
                {"adapter_decision": {"attempt_id": "ATTEMPT-002", "decision": "accepted_for_validation"}, "diff_manifest": {"files": [{"path": path, "before_sha256": "sha256:" + "1" * 64, "after_sha256": None}]}},
            ],
        }
        folded, _, findings = fold_accepted_attempts(bundle)
        self.assertEqual([], findings)
        self.assertEqual([], folded)

    def test_fixture_registry_contains_required_999_counterexamples(self) -> None:
        document = json.loads((PLAN_ROOT / "fixtures" / "candidate-diff-cases.v1.json").read_text(encoding="utf-8"))
        ids = {item["id"] for item in document["cases"]}
        self.assertTrue({
            "candidate-changed-file-omitted", "candidate-extra-changed-file",
            "candidate-deleted-file-missing", "candidate-rename-not-closed",
            "candidate-after-hash-stale", "candidate-test-patch-empty-with-test-change",
            "candidate-test-patch-not-reproducible", "candidate-result-ref-stale",
        }.issubset(ids))


if __name__ == "__main__":
    unittest.main()

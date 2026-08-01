from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SC_ROOT = REPOSITORY_ROOT / "scripts" / "sc"
if str(SC_ROOT) not in sys.path:
    sys.path.insert(0, str(SC_ROOT))

import workflow_model_routing as routing  # noqa: E402
import workflow_model_routing_evaluation as evaluation  # noqa: E402


class WorkflowModelRoutingEvaluationTests(unittest.TestCase):
    def fixture(self) -> dict[str, object]:
        return json.loads(evaluation.DEFAULT_FIXTURE.read_text(encoding="utf-8"))

    def test_shadow_report_compares_predicates_latency_and_cost_without_authority(self) -> None:
        report = evaluation.evaluate_shadow_fixture(self.fixture())
        self.assertEqual("pass", report["status"])
        self.assertEqual([], report["authorizes"])
        self.assertEqual([], report["activationEligibleRoutes"])
        for cohort in report["cohorts"]:
            self.assertIn("quality", cohort)
            self.assertIn("latencyMs", cohort)
            self.assertIn("costUsd", cohort)
            self.assertEqual("keep_disabled", cohort["activationRecommendation"])
            self.assertEqual([], cohort["authorizes"])

    def test_luna_and_sol_max_remain_inactive_without_exact_representative_evidence(self) -> None:
        policy = routing.load_policy()
        report = evaluation.evaluate_shadow_fixture(self.fixture(), policy=policy)
        luna = policy["models"]["luna"]
        max_route = policy["routes"]["vdd.complex_recovery"]
        self.assertEqual("shadow_candidate", luna["activationState"])
        self.assertEqual("disabled_pending_evidence", max_route["activationState"])
        self.assertTrue(all(not item["activationEligible"] for item in report["cohorts"]))

    def test_synthetic_quality_success_alone_cannot_enable_a_route(self) -> None:
        fixture = self.fixture()
        for cohort in fixture["cohorts"]:
            cohort["exactCapabilityStatus"] = "passed"
            cohort["representativeExecution"] = False
        report = evaluation.evaluate_shadow_fixture(fixture)
        self.assertEqual([], report["activationEligibleRoutes"])

    def test_report_writer_is_atomic_and_non_authorizing(self) -> None:
        report = evaluation.evaluate_shadow_fixture(self.fixture())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "shadow-report.v1.json"
            evaluation.write_report(report, output)
            self.assertEqual(report, json.loads(output.read_text(encoding="utf-8")))
            unsafe = copy.deepcopy(report)
            unsafe["authorizes"] = ["activate"]
            with self.assertRaises(routing.RoutingError):
                evaluation.write_report(unsafe, output)


if __name__ == "__main__":
    unittest.main()

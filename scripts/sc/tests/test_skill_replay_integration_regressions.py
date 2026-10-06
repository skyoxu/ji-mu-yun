"""Native integration checks for the online repair (Accepted ADR-0058)."""
from __future__ import annotations

import copy
import os
import unittest
from pathlib import Path
from unittest import mock

import test_skill_replay_review_regressions as regression_support

replay = regression_support.replay


class ReplayIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = regression_support.NativeRuntimeTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_rollback_counts_consumers_and_retains_each_fixture_observation(self):
        result, code = replay.replay_package("candidate", "capability.json", "rollback")
        self.assertEqual(0, code)
        current = result["current_wrapper_replay"]
        rollback = current["rollback"]
        entries = current["consumer_manifest"]["entries"]
        self.assertEqual(len(entries), rollback["observed_count"])
        self.assertEqual(len(entries), len(rollback["baseline_observations"]))
        self.assertEqual(5, rollback["fixture_observed_count"])
        for observation in rollback["baseline_observations"]:
            self.assertTrue(observation["baseline_match"])
            for row in observation["fixture_observations"]:
                self.assertTrue(row["executed"])
                self.assertTrue(row["matched_expected"])
                self.assertEqual(row["baseline"]["exit_code"], row["exit_code"])
                self.assertEqual(row["baseline"]["verdict"], row["verdict"])
                self.assertEqual(row["baseline"]["diagnostic_category"], row["diagnostic_category"])

    def test_rollback_refuses_a_missing_negative_fixture(self):
        result, _ = replay.replay_package("candidate", "capability.json", "rollback")
        current = copy.deepcopy(result["current_wrapper_replay"])
        current["route_transitions"] = [row for row in current["route_transitions"] if not
            (row["transition"] == "rollback" and row["consumer"] == "vdd-execution-plan" and row["fixture"] == "invalid-package")]
        with self.assertRaisesRegex(ValueError, "rollback.*coverage"):
            replay.rollback_details("candidate", "capability.json", current)

    def test_environment_cannot_approve_joint_committed_validator_drift(self):
        fixture = self.fixture
        code = (fixture.root / "validator/check.py").read_text(encoding="utf-8") + "\n# jointly drifted authority\n"
        fixture.write("validator/check.py", code)
        fixture.write("authority/source.py", code)
        fixture.cap.update(validator_sha256=replay.digest(fixture.root / "validator/check.py"), validator_source_sha256=replay.digest(fixture.root / "authority/source.py"))
        import json
        fixture.write("capability.json", json.dumps(fixture.cap))
        fixture.git("add", ".")
        fixture.git("commit", "-qm", "Candidate-controlled joint trust drift")
        candidate_commit = fixture.git("rev-parse", "HEAD").strip()
        with mock.patch.dict(os.environ, {"TC_D1_TRUST_COMMIT": candidate_commit}):
            with self.assertRaisesRegex(ValueError, "Trust Approval"):
                replay.validate_package("candidate", "capability.json")

    def test_replay_identity_is_the_actual_inspected_package(self):
        result, code = replay.replay_package("candidate", "capability.json", "enable")
        self.assertEqual(0, code)
        current = result["current_wrapper_replay"]
        self.assertEqual(current["effective_inspected_content"]["identity"], current.get("replay_identity"))

    def test_probe_actual_target_comes_from_the_native_child_witness(self):
        receipt = replay.validate_package("candidate", "capability.json")
        probes = receipt["probes"]
        for row in probes:
            self.assertTrue(Path(row["actual_target"]).is_absolute())
            self.assertEqual(row["actual_target"], row["read_witness"]["target"])
            self.assertEqual("candidate", row["input"]["target"])
        self.assertNotEqual(probes[0]["actual_target"], probes[1]["actual_target"])
        self.assertEqual(probes[1]["actual_target"], probes[2]["actual_target"])

    def _bounded_matrix(self, **budget):
        import json
        fixture = self.fixture
        fixture.write("candidate/feature.py", "def result():\n    return 2\n")
        matrix = replay.runtime.prepare_matrix(fixture.root, "candidate", "capability.json", fixture.commit, "logs/budget/matrix.json")
        matrix["cases"][0].update(budget)
        fixture.write("logs/budget/matrix.json", json.dumps(matrix))
        return replay.replay_matrix("logs/budget/matrix.json")

    def test_zero_native_matrix_time_budget_is_not_ignored(self):
        result, code = self._bounded_matrix(aggregate_time_bound_ms=0)
        self.assertNotEqual(0, code)
        self.assertTrue(all(row["terminal_state"] == "budget-exhausted" for row in result["case_results"]))

    def test_tiny_native_matrix_output_budget_is_not_ignored(self):
        result, code = self._bounded_matrix(aggregate_output_bound_bytes=1)
        self.assertNotEqual(0, code)
        self.assertTrue(all(row["terminal_state"] == "budget-exhausted" for row in result["case_results"]))


if __name__ == "__main__":
    unittest.main()

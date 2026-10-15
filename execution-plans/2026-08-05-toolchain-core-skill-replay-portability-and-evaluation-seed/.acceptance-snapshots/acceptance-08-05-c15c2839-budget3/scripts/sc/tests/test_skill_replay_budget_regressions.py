"""Separate leaf and replay/Matrix deadlines (Accepted ADR-0058)."""
from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sc import skill_replay_runtime as runtime
import test_skill_replay_review_regressions as support


class ReplayBudgetTests(unittest.TestCase):
    def test_maintainer_tripled_deadlines_preserve_distinct_scopes(self):
        self.assertEqual(180, runtime.TIMEOUT_SECONDS)
        self.assertEqual(360, runtime.REPLAY_TIMEOUT_SECONDS)
        self.assertEqual(900, runtime.FRESH_REPLAY_ORCHESTRATION_SECONDS)
        self.assertEqual(360, runtime.MATRIX_TIMEOUT_SECONDS)
        self.assertEqual(1080, runtime.PROCESS_TRANSPORT_SECONDS)

    def setUp(self):
        self.assertTrue(callable(getattr(runtime, "execute_replay", None)),
                        "full replay has no deadline owner separate from native leaf execution")

    def test_orchestration_can_exceed_leaf_ceiling_without_relaxing_leaf(self):
        with tempfile.TemporaryDirectory() as directory:
            command = [sys.executable, "-c", "print('native-positive-control')"]
            timeout = runtime.TIMEOUT_SECONDS + 1
            result = runtime.execute_replay(command, Path(directory), timeout=timeout)
            self.assertEqual(0, result.returncode)
            self.assertEqual("native-positive-control", result.stdout.strip())
            with self.assertRaisesRegex(ValueError, "time budget"):
                runtime.execute(command, Path(directory), timeout=timeout)

    def test_orchestration_ceiling_remains_finite(self):
        with tempfile.TemporaryDirectory() as directory:
            for timeout in (runtime.REPLAY_TIMEOUT_SECONDS + 1, float("inf"), float("nan"), True, 0):
                with self.subTest(timeout=timeout), self.assertRaisesRegex(ValueError, "time budget"):
                    runtime.execute_replay([sys.executable, "-c", "pass"], Path(directory), timeout=timeout)

    def test_real_work_can_finish_after_a_leaf_sized_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            command = [sys.executable, "-c", "import time; time.sleep(.3); print('finished')"]
            result = runtime.execute_replay(command, Path(directory), timeout=2)
            self.assertEqual(0, result.returncode)
            self.assertEqual("finished", result.stdout.strip())
            with self.assertRaisesRegex(ValueError, "validator or Consumer timed out"):
                runtime.execute(command, Path(directory), timeout=.1)

    def test_orchestration_timeout_is_not_positive_or_defect_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "replay orchestration timed out"):
                runtime.execute_replay([sys.executable, "-c", "import time; time.sleep(10)"],
                                       Path(directory), timeout=.1)

    def test_exit_124_is_unsuccessful_for_orchestration(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "replay orchestration timed out"):
                    runtime.execute_replay([sys.executable, "-c", "raise SystemExit(124)"], Path(directory))

    def test_fresh_orchestration_and_transport_have_separate_safe_ceilings(self):
        self.assertGreaterEqual(runtime.FRESH_REPLAY_ORCHESTRATION_SECONDS, 240)
        self.assertGreaterEqual(runtime.PROCESS_TRANSPORT_SECONDS, 300)
        with tempfile.TemporaryDirectory() as directory:
            result = runtime.capture_process([sys.executable, "-c", "print('transport-positive-control')"],
                                             Path(directory), timeout=300)
            self.assertEqual(0, result.returncode)
            self.assertEqual("transport-positive-control", result.stdout.strip())


class MatrixBudgetTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.NativeRuntimeTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.replay = support.replay
        self.fixture.write("candidate/feature.py", "def result():\n    return 2\n")
        self.matrix = self.replay.runtime.prepare_matrix(
            self.fixture.root, "candidate", "capability.json", self.fixture.commit, "logs/budget/matrix.json")

    def test_matrix_total_is_independent_and_every_native_call_retains_leaf_limit(self):
        for case in self.matrix["cases"]:
            case["aggregate_time_bound_ms"] = (runtime.MATRIX_TIMEOUT_SECONDS + 60) * 1000
        calls = []
        original = self.replay.runtime.execute

        def execute(command, root, timeout, output_limit):
            calls.append(timeout)
            return original(command, root, timeout, output_limit)

        with patch.object(self.replay.runtime, "execute", side_effect=execute):
            result, code = self.replay.runtime.replay_matrix(self.fixture.root, self.matrix)
        self.assertEqual(0, code, result)
        self.assertEqual(6, len(result["case_results"]))
        self.assertIn("budget_observation", result, "Matrix has no independent observable aggregate budget")
        self.assertEqual(runtime.MATRIX_TIMEOUT_SECONDS, result["budget_observation"]["aggregate_time_limit_seconds"])
        self.assertIn("Stable materialization", result["budget_observation"]["includes_preparation"])
        self.assertGreaterEqual(len(calls), 24)
        self.assertTrue(all(0 < timeout <= runtime.TIMEOUT_SECONDS for timeout in calls), calls)

    def test_stricter_declared_matrix_budget_cannot_be_silently_expanded(self):
        matrix = copy.deepcopy(self.matrix)
        matrix["cases"][0]["aggregate_time_bound_ms"] = .001
        result, code = self.replay.runtime.replay_matrix(self.fixture.root, matrix)
        self.assertNotEqual(0, code)
        self.assertFalse(result["aggregate_valid"])
        self.assertIn("budget_observation", result, "the actual exhausted Matrix budget is unobservable")
        self.assertEqual(.000001, result["budget_observation"]["aggregate_time_limit_seconds"])
        self.assertTrue(all(not case["executed"] for case in result["case_results"]))
        self.assertEqual([], result["completed_case_results"])


if __name__ == "__main__":
    unittest.main()

"""Separate trusted validator execution from candidate inputs (ADR-0058)."""
import json
import unittest
from pathlib import Path

import test_skill_replay_review_regressions as support

replay = support.replay


class HistoricalValidatorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.NativeRuntimeTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root
        self.target = replay.PRIMARY_TARGET
        self.capability = replay.PRIMARY_CAPABILITY
        self.validator_path = self.target + "/scripts/acceptance_cli.py"
        code = (self.root / "validator/check.py").read_text(encoding="utf-8")
        self.fixture.write(self.validator_path, code)
        self.source_path = "scripts/sc/config/skill-package-validator-source.v1.json"
        self.cap = dict(self.fixture.cap, allowed_root=self.target,
                        validator_entrypoint="scripts/acceptance_cli.py",
                        validator_source=self.source_path)
        self.publish_declarations()
        self.fixture.git("add", ".")
        self.fixture.git("commit", "-qm", "Independent historical package validator")
        self.commit = self.fixture.git("rev-parse", "HEAD").strip()
        self.fixture.pin_fixture_authority(self.commit)

    def publish_declarations(self):
        identity = replay.digest(self.root / self.validator_path)
        self.fixture.write(self.source_path, json.dumps({
            "validator_path": self.validator_path, "validator_sha256": identity,
            "authorizes": []}))
        self.cap.update(validator_sha256=identity,
                        validator_source_sha256=replay.digest(self.root / self.source_path))
        self.fixture.write(self.capability, json.dumps(self.cap))

    def test_historical_validator_reads_changed_current_package_with_three_real_controls(self):
        # Candidate code must not replace the validator that executes. The
        # independent source/descriptor are also changed to the new code.
        self.fixture.write(self.validator_path, "raise SystemExit(91)\n")
        self.fixture.write(self.target + "/SKILL.md", "Current candidate content\n")
        self.publish_declarations()
        receipt = replay.validate_package(self.target, self.capability)
        self.assertEqual("pass", receipt["status"])
        self.assertEqual([0, 0, 2], [p["exit_code"] for p in receipt["probes"]])
        self.assertEqual(str((self.root / self.target).resolve()), receipt["probes"][0]["actual_target"])
        self.assertEqual(["fixture.json"], receipt["effective_read_witness"]["observed_paths"])
        trusted = receipt["independent_validator_verification"]
        self.assertEqual(self.commit, trusted["trust_commit"])
        self.assertEqual(replay.runtime.sha(replay.runtime.git_bytes(self.root, self.commit, self.validator_path)),
                         receipt["resolved_validator"]["sha256"])
        self.assertNotEqual(replay.digest(self.root / self.validator_path), receipt["resolved_validator"]["sha256"])
        self.assertTrue(replay.candidate_external_trust(self.target, self.capability, receipt)["complete"])
        self.assertEqual([], receipt["authorizes"])

    def test_candidate_cannot_expand_historical_capability_scope(self):
        self.cap["probe_args"] = ["--other-operation", "{target}"]
        self.publish_declarations()
        with self.assertRaisesRegex(ValueError, "historical capability scope"):
            replay.validate_package(self.target, self.capability)

    def test_materialized_dependency_mutation_fails_before_success(self):
        with self.assertRaisesRegex(ValueError, "Trust Approval"):
            with replay.runtime.trusted_validator(self.root, self.capability) as (validator, value, proof):
                self.assertFalse(validator.is_relative_to(self.root))
                self.assertEqual(self.commit, proof["trust_commit"])
                validator.with_name("unreached.json").write_bytes(b"{}")

    def test_matrix_executes_both_subjects_with_the_historical_judge(self):
        self.fixture.write(self.validator_path, "raise SystemExit(91)\n")
        self.publish_declarations()
        matrix = replay.runtime.prepare_matrix(self.root, self.target, self.capability,
                                              self.commit, "logs/current-matrix.json")
        result, code = replay.runtime.replay_matrix(self.root, matrix)
        self.assertEqual(0, code, result)
        self.assertEqual(6, len(result["case_results"]))
        self.assertTrue(result["independent_validator_verification"]["candidate_separated"])
        for case in result["case_results"]:
            self.assertEqual(["Stable", "Candidate"],
                             [subject["subject"] for subject in case["subject_executions"]])
            self.assertTrue(all(subject["executed"] for subject in case["subject_executions"]))


if __name__ == "__main__":
    unittest.main()

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"


@pytest.mark.cer_assertion("RMAP-FIX-ASSERTIONS")
class SkillPackageReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "logs")
        self.root = Path(self.temp.name)
        self.validator_root = self.root / "validator"
        self.validator_root.mkdir()
        self.validator = self.validator_root / "validator.py"
        self.validator.write_text(
            "import argparse, pathlib\n"
            "p=argparse.ArgumentParser(); p.add_argument('--skill-root', required=True); a=p.parse_args()\n"
            "root=pathlib.Path(a.skill_root)\n"
            "raise SystemExit(0 if (root / 'VALID').is_file() else 3)\n",
            encoding="utf-8",
        )
        self.capability = self.root / "capability.json"
        self._write_capability()

    def tearDown(self):
        self.temp.cleanup()

    def _relative(self, path):
        return path.relative_to(ROOT).as_posix()

    def _sha256(self, path):
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_capability(self, **changes):
        value = {
            "schema_version": "jimuyun.skill-package-validator-capability.v1",
            "capability_id": "test-validator",
            "allowed_root": self._relative(self.validator_root),
            "validator_entrypoint": "validator.py",
            "probe_args": ["--skill-root", "{target}"],
            "validator_sha256": self._sha256(self.validator),
            "package_identity": "test-validator-v1",
            "state": "active",
            "authorizes": [],
        }
        value.update(changes)
        self.capability.write_text(json.dumps(value), encoding="utf-8")

    def _package(self, name, valid=True):
        package = self.root / name
        package.mkdir()
        if valid:
            (package / "VALID").write_text("valid\n", encoding="utf-8")
        return package

    def _run(self, operation, *args):
        return subprocess.run(
            [sys.executable, str(ENTRY), operation, *map(str, args)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def _validate(self, target):
        return self._run(
            "validate-package",
            "--target", self._relative(target),
            "--capability", self._relative(self.capability),
        )

    def test_validate_package_runs_validator_against_requested_target(self):
        valid = self._package("valid")
        invalid = self._package("invalid", valid=False)
        self.assertEqual(self._validate(valid).returncode, 0)
        self.assertNotEqual(self._validate(invalid).returncode, 0)

    def test_missing_target_is_rejected_before_validator_runs(self):
        result = self._validate(self.root / "missing")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("target package is absent", result.stderr)

    def test_always_successful_validator_cannot_approve_invalid_package(self):
        invalid = self._package("invalid", valid=False)
        self.validator.write_text("raise SystemExit(0)\n", encoding="utf-8")
        self._write_capability(validator_sha256=self._sha256(self.validator))
        result = self._validate(invalid)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("negative compatibility probe unexpectedly passed", result.stderr)

    def test_validator_content_drift_is_rejected(self):
        valid = self._package("valid")
        self.validator.write_text(self.validator.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")
        result = self._validate(valid)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("validator identity drift", result.stderr)

    def test_illegal_package_is_rejected(self):
        invalid = self._package("invalid", valid=False)
        self.assertNotEqual(self._validate(invalid).returncode, 0)

    def test_matrix_executes_each_case_and_rejects_unexecuted_matrix(self):
        valid = self._package("valid")
        invalid = self._package("invalid", valid=False)
        matrix = self.root / "matrix.json"
        matrix.write_text(json.dumps({
            "schema_version": "jimuyun.stable-candidate-replay-matrix.v2",
            "authorizes": [],
            "cases": [
                {"case_id": "valid", "target": self._relative(valid), "capability": self._relative(self.capability), "expected_exit": 0},
                {"case_id": "invalid", "target": self._relative(invalid), "capability": self._relative(self.capability), "expected_exit": "nonzero"},
            ],
        }), encoding="utf-8")
        result = self._run("replay-matrix", "--matrix", self._relative(matrix))
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual([0, 3], [case["observed_exit_code"] for case in receipt["case_results"]])
        self.assertTrue(all(case["executed"] for case in receipt["case_results"]))

        empty = self.root / "empty.json"
        empty.write_text(json.dumps({"schema_version": "jimuyun.stable-candidate-replay-matrix.v2", "authorizes": [], "cases": []}), encoding="utf-8")
        self.assertNotEqual(self._run("replay-matrix", "--matrix", self._relative(empty)).returncode, 0)

    def test_disabled_and_rolled_back_capabilities_fail_closed(self):
        valid = self._package("valid")
        for state in ("disabled", "rolled_back"):
            with self.subTest(state=state):
                self._write_capability(state=state)
                result = self._validate(valid)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("capability is not active", result.stderr)

    def test_route_lifecycle_enable_rollback_reenable_uses_real_entry(self):
        valid = self._package("route-valid")

        enable = self._run(
            "replay-package",
            "--target", self._relative(valid),
            "--capability", self._relative(self.capability),
            "--probe-mode", "enable",
        )
        rollback = self._run(
            "replay-package",
            "--target", self._relative(valid),
            "--capability", self._relative(self.capability),
            "--probe-mode", "rollback",
        )
        reenable = self._run(
            "replay-package",
            "--target", self._relative(valid),
            "--capability", self._relative(self.capability),
            "--probe-mode", "re-enable",
        )

        self.assertEqual(enable.returncode, 0, enable.stderr)
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(reenable.returncode, 0, reenable.stderr)

        enable_replay = json.loads(enable.stdout)["current_wrapper_replay"]
        rollback_replay = json.loads(rollback.stdout)["current_wrapper_replay"]
        reenable_replay = json.loads(reenable.stdout)["current_wrapper_replay"]
        invocation = enable_replay["consumer_invocation"]
        rollback_info = rollback_replay["rollback"]
        reenable_info = reenable_replay["consumer_invocation"]

        self.assertEqual(invocation["transition"], "enable")
        self.assertTrue(invocation["real_call"])
        self.assertEqual(invocation["route"], "Candidate Route")
        self.assertEqual(reenable_info["transition"], "re-enable")
        self.assertTrue(reenable_info["real_call"])
        self.assertEqual(reenable_info["route"], "Candidate Route")
        self.assertTrue(rollback_info["real_call"])
        self.assertEqual(rollback_info["route_identity"], rollback_info["prior_route_identity"])
        self.assertEqual(rollback_info["verdict"], rollback_info["prior_verdict"])
        self.assertEqual(
            rollback_info["diagnostic_category"],
            rollback_info["prior_diagnostic_category"],
        )


if __name__ == "__main__":
    unittest.main()

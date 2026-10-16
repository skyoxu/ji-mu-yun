import importlib.util
import unittest
from pathlib import Path
from unittest import mock


PLAN_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_all", PLAN_DIR / "validate_all.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ValidateAllTests(unittest.TestCase):
    def test_plan_validator_identity_is_available(self):
        identity = MODULE.current_candidate_identity("BROH-S0")
        self.assertTrue(identity["validator_hash"])
        self.assertTrue(identity["contract_hash"])

    def test_snapshot_exposes_all_adapter_roots(self):
        snapshot = MODULE.slice_validation_snapshot("BROH-S0")
        self.assertEqual(
            {
                "candidate_hash",
                "predicate_input_root",
                "authority_root",
                "validator_root",
                "validator_version",
                "closure_definition_hash",
            },
            set(snapshot),
        )

    def test_slice_identity_uses_slice_scoped_roots_and_keeps_worktree_diagnostics(self):
        snapshot = MODULE.slice_validation_snapshot("BROH-S0")
        identity = MODULE.current_candidate_identity("BROH-S0")
        self.assertNotEqual(snapshot["candidate_hash"], identity["contract_hash"])
        self.assertEqual(snapshot["candidate_hash"], identity["candidate_hash"])
        self.assertEqual(snapshot["predicate_input_root"], identity["predicate_input_root"])
        self.assertRegex(identity["candidate_worktree_hash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(71, len(snapshot["candidate_hash"]))

    def test_untracked_manifest_hash_is_content_bound(self):
        self.assertRegex(MODULE._untracked_manifest_hash(), r"^sha256:[0-9a-f]{64}$")

    def test_stage_validator_identity_excludes_mutable_terminal_validator(self):
        self.assertNotIn(MODULE.TERMINAL_VALIDATOR_PATH, MODULE.STAGE_VALIDATOR_PATHS)
        self.assertRegex(MODULE._validator_hash(), r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(MODULE._terminal_validator_hash(), r"^sha256:[0-9a-f]{64}$")

    def test_candidate_binding_changes_when_worktree_root_changes(self):
        with mock.patch.object(MODULE, "_tracked_diff_hash", side_effect=["sha256:" + "a" * 64, "sha256:" + "b" * 64]):
            first = MODULE.validation_snapshot()["candidate_hash"]
            second = MODULE.validation_snapshot()["candidate_hash"]
        self.assertNotEqual(first, second)

    def test_slice_root_changes_when_a_predecessor_result_changes(self):
        with mock.patch.object(
            MODULE,
            "predecessor_result_hashes",
            side_effect=[{"BROH-S0": "sha256:" + "a" * 64}, {"BROH-S0": "sha256:" + "b" * 64}],
        ):
            first = MODULE.slice_validation_snapshot("BROH-S1")["candidate_hash"]
            second = MODULE.slice_validation_snapshot("BROH-S1")["candidate_hash"]
        self.assertNotEqual(first, second)

    def test_slice_root_does_not_follow_unrelated_worktree_churn(self):
        with mock.patch.object(MODULE, "_tracked_diff_hash", side_effect=AssertionError("not slice scoped")):
            first = MODULE.slice_validation_snapshot("BROH-S0")
            second = MODULE.slice_validation_snapshot("BROH-S0")
        self.assertEqual(first, second)

    def test_validation_remains_non_authorizing(self):
        self.assertEqual([], MODULE.validate())


if __name__ == "__main__":
    unittest.main()

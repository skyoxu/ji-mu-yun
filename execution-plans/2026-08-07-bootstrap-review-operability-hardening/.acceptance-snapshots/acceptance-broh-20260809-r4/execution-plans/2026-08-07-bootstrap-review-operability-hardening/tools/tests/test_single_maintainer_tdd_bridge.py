import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "single_maintainer_tdd_bridge",
    TOOLS_DIR / "single_maintainer_tdd_bridge.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class SingleMaintainerTddBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(
            (MODULE.PLAN_DIR / "implementation-contract.v1.json").read_text(encoding="utf-8")
        )
        cls.selected = next(item for item in cls.contract["slices"] if item["slice_id"] == "BROH-S0")
        cls.write_set = MODULE._write_set(cls.selected)
        cls.snapshots = MODULE._snapshot_paths(cls.selected, cls.write_set)

    def test_snapshot_paths_exactly_cover_the_declared_write_set(self):
        expected = set().union(*self.write_set.values())
        self.assertEqual(expected, set(self.snapshots))

    def test_projection_builder_is_loaded_from_the_target_plan(self):
        self.assertEqual(
            (MODULE.PLAN_DIR / "tools" / "stage_projection_builder.py").resolve(),
            Path(MODULE.stage_projection_builder.__file__).resolve(),
        )

    def test_protocol_identity_binds_plan_tests(self):
        identity = MODULE._protocol_identity()
        self.assertRegex(identity["plan_test_hash"], r"^sha256:[0-9a-f]{64}$")

    def test_missing_snapshot_is_allowed_only_when_explicitly_planned(self):
        selected = dict(self.selected)
        selected["planned_new_files"] = ["missing-new.py"]
        selected["execution_snapshot_paths"] = ["missing-new.py"]
        write_set = {"production": {"missing-new.py"}, "tests": set(), "documentation": set()}
        self.assertEqual(["missing-new.py"], MODULE._snapshot_paths(selected, write_set))
        selected["planned_new_files"] = []
        with self.assertRaisesRegex(ValueError, "planned new files"):
            MODULE._snapshot_paths(selected, write_set)

    def test_planned_new_file_must_exist_before_its_stage(self):
        with self.assertRaisesRegex(RuntimeError, "materialized"):
            MODULE._require_materialized({"missing-new.py"}, "GREEN")

    def test_red_requires_a_real_declared_test_change(self):
        with self.assertRaisesRegex(RuntimeError, "declared tests"):
            MODULE._validate_red_changes(set(self.write_set["documentation"]), self.write_set)
        MODULE._validate_red_changes({next(iter(self.write_set["tests"]))}, self.write_set)
        with self.assertRaisesRegex(RuntimeError, "declared tests"):
            MODULE._validate_red_changes(
                {next(iter(self.write_set["tests"])), next(iter(self.write_set["documentation"]))},
                self.write_set,
            )

    def test_green_requires_only_declared_production_changes(self):
        MODULE._validate_green_changes({next(iter(self.write_set["production"]))}, self.write_set)
        with self.assertRaisesRegex(RuntimeError, "production"):
            MODULE._validate_green_changes(
                {next(iter(self.write_set["production"])), next(iter(self.write_set["tests"]))},
                self.write_set,
            )

    def test_refactor_accepts_documentation_but_rejects_outside_paths(self):
        MODULE._validate_refactor_changes(set(self.write_set["documentation"]), self.write_set)
        with self.assertRaisesRegex(RuntimeError, "escaped"):
            MODULE._validate_refactor_changes({"README.md"}, self.write_set)

    def test_command_manifest_rejects_undeclared_side_effects(self):
        before = {"declared.py": "sha256:old"}
        after = {"declared.py": "sha256:new", "rogue.log": "sha256:rogue"}
        with self.assertRaisesRegex(RuntimeError, "undeclared worktree paths"):
            MODULE._assert_manifest_delta(before, after, {"declared.py"}, "test command")

    def test_stable_terminal_guard_rejects_validator_identity_drift(self):
        expected_snapshot = {
            "candidate_hash": "sha256:candidate",
            "predicate_input_root": "sha256:candidate",
            "authority_root": "sha256:authority",
            "validator_root": "sha256:validator",
            "validator_version": "broh-validator-v1",
            "closure_definition_hash": "sha256:closure",
        }

        class StableValidation:
            @staticmethod
            def validation_snapshot():
                return expected_snapshot

            @staticmethod
            def slice_validation_snapshot(slice_id):
                self.assertEqual("BROH-S7", slice_id)
                return expected_snapshot

            @staticmethod
            def _validator_hash():
                return "sha256:stable"

        with tempfile.TemporaryDirectory(dir=MODULE.REPOSITORY_ROOT) as temp:
            run_dir = Path(temp) / "RUN-TEST"
            run_dir.mkdir()
            for stage in ("red", "green", "refactor"):
                (run_dir / f"{stage}-result.json").write_text(
                    json.dumps({"contract_hash": MODULE._hash_file(MODULE.PLAN_DIR / "implementation-contract.v1.json"), "validator_hash": "sha256:drift"}),
                    encoding="utf-8",
                )
            stage_hashes = {
                stage: MODULE._hash_file(run_dir / f"{stage}-result.json")
                for stage in ("red", "green", "refactor")
            }
            projection = {
                "schema_version": "jimuyun.stage-evidence-projection.v1",
                "plan_id": self.contract["plan_id"],
                "slice_id": "BROH-S7",
                "run_id": run_dir.name,
                "stage_result_hashes": stage_hashes,
                "candidate_identity": {
                    "contract_hash": MODULE._hash_file(MODULE.PLAN_DIR / "implementation-contract.v1.json"),
                    "validator_hash": "sha256:drift",
                },
            }
            projection["root_hash"] = "sha256:" + hashlib.sha256(
                json.dumps(projection, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            (run_dir / "stage-evidence-projection.v1.json").write_text(json.dumps(projection), encoding="utf-8")
            predicate = {
                "status": "pass",
                "predicate": "implementation-complete",
                "slice_id": "BROH-S7",
                "contract_hash": MODULE._hash_file(MODULE.PLAN_DIR / "implementation-contract.v1.json"),
                **expected_snapshot,
                "validation_snapshot": expected_snapshot,
                "authorizes": [],
            }
            with mock.patch.object(MODULE, "_validation_module", return_value=StableValidation):
                with self.assertRaisesRegex(RuntimeError, "verifier identity"):
                    MODULE._stable_terminal_guard(run_dir, predicate, "BROH-S7", "implementation-complete")

    def test_first_call_pauses_before_running_red(self):
        with tempfile.TemporaryDirectory(dir=MODULE.REPOSITORY_ROOT) as temp:
            evidence = Path(temp) / "evidence"
            state_path = Path(temp) / "state.json"
            with (
                mock.patch.object(MODULE, "_state_paths", return_value=(evidence, state_path)),
                mock.patch.object(MODULE.build_slice_invocation, "build", return_value={}),
                mock.patch.object(MODULE.stage_observation_runner, "freeze", return_value={}),
                mock.patch.object(MODULE.stage_observation_runner, "run") as stage_run,
                mock.patch.object(MODULE, "_worktree_manifest", return_value={}),
            ):
                result = MODULE.run("BROH-S0", self.snapshots)
            self.assertEqual("paused", result["status"])
            self.assertEqual("awaiting-red-test", json.loads(state_path.read_text(encoding="utf-8"))["phase"])
            stage_run.assert_not_called()

    def test_green_observation_pauses_before_refactor(self):
        production = next(iter(self.write_set["production"]))
        with tempfile.TemporaryDirectory(dir=MODULE.REPOSITORY_ROOT) as temp:
            run_dir = Path(temp) / "run"
            state_path = Path(temp) / "state.json"
            state = {
                "slice_id": "BROH-S0",
                "run_id": "RUN-TEST",
                "run_dir": run_dir.relative_to(MODULE.REPOSITORY_ROOT).as_posix(),
                "write_set": {key: sorted(value) for key, value in self.write_set.items()},
                "red_worktree_manifest": {},
                "red_after_snapshots": {path: None for path in self.snapshots},
                "snapshot_paths": self.snapshots,
                "invocation": {"green": {}},
            }
            observation = {
                "stage": "green",
                "exit_code": 0,
                "observed_at": "2026-08-08T00:00:00Z",
                "changed_files": [
                    {
                        "path": path,
                        "before_bytes_base64": None,
                        "after_bytes_base64": "changed" if path == production else None,
                    }
                    for path in self.snapshots
                ],
                "commands_attempted": ["broh-s0-target-test"],
                "response_summary": "green",
            }
            with (
                mock.patch.object(MODULE, "_worktree_manifest", return_value={production: "sha256:new"}),
                mock.patch.object(MODULE.stage_observation_runner, "run", return_value=observation),
                mock.patch.object(MODULE.stage_observation_runner, "record_observation"),
            ):
                result = MODULE._observe_green(state, state_path)
            saved = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual("paused", result["status"])
            self.assertEqual("awaiting-refactor", saved["phase"])

    def test_caller_must_supply_every_snapshot_path(self):
        with self.assertRaisesRegex(ValueError, "complete declared write set"):
            MODULE.run("BROH-S0", self.snapshots[:1])

    def test_completed_result_becomes_stale_when_predecessor_roots_change(self):
        class Validation:
            @staticmethod
            def slice_validation_snapshot(slice_id):
                return {"candidate_hash": "sha256:new"}

            @staticmethod
            def predecessor_result_hashes(slice_id):
                return {}

        result = {
            "status": "pass",
            "predicate": "slice-ready",
            "slice_id": "BROH-S0",
            "contract_hash": MODULE._hash_file(MODULE.PLAN_DIR / "implementation-contract.v1.json"),
            "candidate_hash": "sha256:old",
            "predecessor_result_hashes": {},
        }
        with mock.patch.object(MODULE, "_validation_module", return_value=Validation):
            self.assertFalse(MODULE._result_is_current(result, self.selected, "BROH-S0"))
            result["candidate_hash"] = "sha256:new"
            self.assertTrue(MODULE._result_is_current(result, self.selected, "BROH-S0"))

    def test_stale_bridge_identity_starts_a_successor_run(self):
        with tempfile.TemporaryDirectory(dir=MODULE.REPOSITORY_ROOT) as temp:
            evidence = Path(temp) / "evidence"
            state_path = Path(temp) / "state.json"
            common = (
                mock.patch.object(MODULE, "_state_paths", return_value=(evidence, state_path)),
                mock.patch.object(MODULE.build_slice_invocation, "build", return_value={}),
                mock.patch.object(MODULE.stage_observation_runner, "freeze", return_value={}),
                mock.patch.object(MODULE, "_worktree_manifest", return_value={}),
            )
            with common[0], common[1], common[2], common[3], mock.patch.object(
                MODULE, "_protocol_identity", return_value={"bridge_hash": "old"}
            ):
                MODULE.run("BROH-S0", self.snapshots)
            with (
                mock.patch.object(MODULE, "_state_paths", return_value=(evidence, state_path)),
                mock.patch.object(MODULE, "_protocol_identity", return_value={"bridge_hash": "new"}),
                mock.patch.object(MODULE.build_slice_invocation, "build", return_value={}),
                mock.patch.object(MODULE.stage_observation_runner, "freeze", return_value={}),
                mock.patch.object(MODULE, "_worktree_manifest", return_value={}),
            ):
                result = MODULE.run("BROH-S0", self.snapshots)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual("paused", result["status"])
            self.assertEqual("awaiting-red-test", state["phase"])
            self.assertIsNotNone(state["predecessor_run_id"])


if __name__ == "__main__":
    unittest.main()

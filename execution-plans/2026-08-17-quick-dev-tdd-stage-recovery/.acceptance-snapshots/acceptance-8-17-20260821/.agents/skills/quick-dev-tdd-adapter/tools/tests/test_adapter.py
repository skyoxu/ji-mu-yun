import importlib.util
import json
import base64
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock


TOOLS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("adapter", TOOLS / "adapter.py")
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)
BUILDER_SPEC = importlib.util.spec_from_file_location("protocol_bundle_builder", TOOLS / "protocol_bundle_builder.py")
PROTOCOL_BUILDER = importlib.util.module_from_spec(BUILDER_SPEC)
BUILDER_SPEC.loader.exec_module(PROTOCOL_BUILDER)
OBSERVATION_SPEC = importlib.util.spec_from_file_location("stage_observation", TOOLS / "stage_observation.py")
STAGE_OBSERVATION = importlib.util.module_from_spec(OBSERVATION_SPEC)
OBSERVATION_SPEC.loader.exec_module(STAGE_OBSERVATION)
COMPOSER_SPEC = importlib.util.spec_from_file_location("stage_artifact_composer", TOOLS / "stage_artifact_composer.py")
STAGE_COMPOSER = importlib.util.module_from_spec(COMPOSER_SPEC)
COMPOSER_SPEC.loader.exec_module(STAGE_COMPOSER)
RUNNER_SPEC = importlib.util.spec_from_file_location("stage_observation_runner", TOOLS / "stage_observation_runner.py")
STAGE_RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(STAGE_RUNNER)
LIFECYCLE_SPEC = importlib.util.spec_from_file_location("stage_lifecycle_runner", TOOLS / "stage_lifecycle_runner.py")
LIFECYCLE = importlib.util.module_from_spec(LIFECYCLE_SPEC)
LIFECYCLE_SPEC.loader.exec_module(LIFECYCLE)

PLAN_ROOT = Path(__file__).resolve().parents[5] / "execution-plans" / "2026-07-15-repository-maintenance-tdd-adapter"
if str(PLAN_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(PLAN_ROOT / "tools"))
TEST_SUPPORT = Path(__file__).resolve().parents[5] / "scripts" / "python" / "tests"
if str(TEST_SUPPORT) not in sys.path:
    sys.path.insert(0, str(TEST_SUPPORT))

from protocol_fixture_support import hydrate_protocol_fixture, load_protocol_run  # noqa: E402
from protocol_validation_guards import validate_protocol_bundle  # noqa: E402
from skill_input_composition_support import publish_ready_receipt  # noqa: E402


class AdapterTests(unittest.TestCase):
    def test_prepare_consumes_real_ready_skill_input_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            plan = repository / "execution-plans" / "feature-a"
            plan.mkdir(parents=True)
            target = plan / "implementation-contract.v1.json"
            target.write_text("{}\n", encoding="utf-8", newline="\n")
            artifacts = publish_ready_receipt(
                repository,
                consumer="quick-dev-tdd-adapter",
                operation="execute",
                target="execution-plans/feature-a",
                role_paths={
                    "plan_directory": ["execution-plans/feature-a"],
                    "target_files": ["execution-plans/feature-a/implementation-contract.v1.json"],
                },
            )
            prepared = ADAPTER.prepare_with_skill_input(
                self._contract(),
                "RMAP-S2",
                {"contract_hash": "sha256:" + "a" * 64, "validator_hash": "sha256:" + "b" * 64},
                receipt_path=artifacts["receipt"],
                repository_root=repository,
                skill_contract_path=artifacts["contract"],
            )
            self.assertEqual("prepared", prepared["state"])
            self.assertEqual(artifacts["context"].as_posix(), prepared["skill_input"]["context_artifact"])

    def test_prepare_blocks_missing_wrong_and_stale_ready_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            plan = repository / "execution-plans" / "feature-a"
            plan.mkdir(parents=True)
            target = plan / "implementation-contract.v1.json"
            target.write_text("{}\n", encoding="utf-8", newline="\n")
            artifacts = publish_ready_receipt(
                repository,
                consumer="quick-dev-tdd-adapter",
                operation="execute",
                target="execution-plans/feature-a",
                role_paths={
                    "plan_directory": ["execution-plans/feature-a"],
                    "target_files": ["execution-plans/feature-a/implementation-contract.v1.json"],
                },
            )
            call = lambda receipt_path, contract_path: ADAPTER.prepare_with_skill_input(
                self._contract(),
                "RMAP-S2",
                {"contract_hash": "sha256:" + "a" * 64, "validator_hash": "sha256:" + "b" * 64},
                receipt_path=receipt_path,
                repository_root=repository,
                skill_contract_path=contract_path,
            )
            with self.assertRaises(ValueError):
                call(repository / "missing-receipt.json", artifacts["contract"])
            with self.assertRaises(ValueError):
                call(artifacts["candidate_receipt"], artifacts["contract"])
            wrong = publish_ready_receipt(
                repository,
                consumer="wrong-quick-dev-consumer",
                operation="execute",
                target="execution-plans/feature-a",
                role_paths={
                    "plan_directory": ["execution-plans/feature-a"],
                    "target_files": ["execution-plans/feature-a/implementation-contract.v1.json"],
                },
                protocol_name=".skill-input-composition-wrong",
            )
            with self.assertRaises(ValueError):
                call(wrong["receipt"], wrong["contract"])
            target.write_text('{"stale":true}\n', encoding="utf-8", newline="\n")
            with self.assertRaises(ValueError):
                call(artifacts["receipt"], artifacts["contract"])

    def _contract(self) -> dict:
        return {
            "backend": {"hidden_state": False},
            "command_registry": "schemas/command-registry.v1.json",
            "slices": [{
                "slice_id": "RMAP-S2",
                "allowed_changes": {
                    "production": [".agents/skills/quick-dev-tdd-adapter/**"],
                    "tests": [".agents/skills/quick-dev-tdd-adapter/tools/tests/**"],
                    "documentation": [],
                },
            }],
        }

    def _prepared(self) -> dict:
        return ADAPTER._prepare_core(self._contract(), "RMAP-S2", {"contract_hash": "sha256:contract", "validator_hash": "sha256:validator"})

    def _execute(self, run_dir: Path, events: list[dict], **kwargs):
        context = run_dir.parent / "skill-input-context.v1.json"
        context.parent.mkdir(parents=True, exist_ok=True)
        context.write_text("{}\n", encoding="utf-8", newline="\n")
        gate = {
            "context_artifact": context,
            "context_artifact_hash": "sha256:" + "b" * 64,
            "binding_hash": "sha256:" + "a" * 64,
        }
        with mock.patch.object(ADAPTER, "require_ready_skill_input", return_value=gate):
            return ADAPTER.execute(
                run_dir,
                self._contract(),
                "RMAP-S2",
                {"contract_hash": "sha256:contract", "validator_hash": "sha256:validator"},
                events,
                receipt_path=Path("receipt.json"),
                **kwargs,
            )

    def test_prepare_requires_current_hashes(self) -> None:
        result = ADAPTER._prepare_core(self._contract(), "RMAP-S2", {"contract_hash": ""})
        self.assertEqual("RMAP-HASH-AUTHORITY", result["diagnostic"]["rule_id"])

    def test_implementation_before_red_is_rejected(self) -> None:
        result = ADAPTER.transition(
            self._prepared(), "red",
            {"exit_code": 1, "expected_failure_id": "RMAP-TDD-RED-NOT-OBSERVED", "changed_paths": [".agents/skills/quick-dev-tdd-adapter/tools/adapter.py"]},
        )
        self.assertEqual("RMAP-TDD-IMPLEMENTATION-BEFORE-RED", result["diagnostic"]["rule_id"])

    def test_green_without_observed_red_is_rejected(self) -> None:
        result = ADAPTER.transition(
            {"state": "prepared", "slice_id": "RMAP-S2", "stages": []},
            "green",
            {"changed_paths": [".agents/skills/quick-dev-tdd-adapter/tools/adapter.py"]},
        )
        self.assertEqual("blocked", result["state"])
        self.assertEqual("RMAP-TDD-RED-NOT-OBSERVED", result["diagnostic"]["rule_id"])

    def test_green_outside_production_write_set_is_rejected(self) -> None:
        red = ADAPTER.transition(self._prepared(), "red", {"exit_code": 1, "expected_failure_id": "RMAP-TDD-RED-NOT-OBSERVED", "changed_paths": [".agents/skills/quick-dev-tdd-adapter/tools/tests/test_adapter.py"]})
        result = ADAPTER.transition(red, "green", {"exit_code": 0, "changed_paths": ["scripts/python/unrelated.py"]})
        self.assertEqual("RMAP-TDD-EXIT-PROOF", result["diagnostic"]["rule_id"])

    def test_refactor_before_green_is_rejected(self) -> None:
        result = ADAPTER.transition(self._prepared(), "refactor", {"exit_code": 0, "changed_paths": []})
        self.assertEqual("RMAP-TDD-EXIT-PROOF", result["diagnostic"]["rule_id"])

    def test_resume_rejects_stale_identity(self) -> None:
        result = ADAPTER.resume(self._prepared(), {"contract_hash": "sha256:new", "validator_hash": "sha256:validator"})
        self.assertEqual("RMAP-HASH-AUTHORITY", result["diagnostic"]["rule_id"])

    def test_execute_persists_a_complete_lifecycle(self) -> None:
        events = [
            {"stage": "red", "exit_code": 1, "expected_failure_id": "RMAP-TDD-RED-NOT-OBSERVED", "changed_paths": [".agents/skills/quick-dev-tdd-adapter/tools/tests/test_adapter.py"]},
            {"stage": "green", "exit_code": 0, "changed_paths": [".agents/skills/quick-dev-tdd-adapter/tools/adapter.py"]},
            {"stage": "refactor", "exit_code": 0, "changed_paths": [".agents/skills/quick-dev-tdd-adapter/tools/adapter.py"]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            result = self._execute(Path(tmp) / "run-001", events)
            recovery = json.loads((Path(tmp) / "run-001" / "recovery-state.json").read_text(encoding="utf-8"))
        self.assertEqual("refactor-verified", result["state"])
        self.assertEqual(["red", "green", "refactor"], recovery["stages"])
        self.assertEqual("sha256:" + "a" * 64, recovery["skill_input"]["binding_hash"])
        self.assertRegex(recovery["skill_input"]["context_artifact_hash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual([], recovery["authorizes"])

    def test_execute_rejects_existing_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-001"
            run_dir.mkdir()
            result = self._execute(run_dir, [])
        self.assertEqual("RMAP-RECOVERY-NEW-RUN-STATE", result["diagnostic"]["rule_id"])

    def test_execute_persists_immutable_protocol_artifacts(self) -> None:
        fixtures = json.loads((PLAN_ROOT / "fixtures" / "capsule-attempt-cases.v1.json").read_text(encoding="utf-8"))
        bundle, store, versions = hydrate_protocol_fixture(fixtures["valid_bundle"])
        events = [
            {"stage": "red", "exit_code": 1, "expected_failure_id": "RMAP-TDD-RED-NOT-OBSERVED", "changed_paths": [".agents/skills/quick-dev-tdd-adapter/tools/tests/test_adapter.py"]},
            {"stage": "green", "exit_code": 0, "changed_paths": [".agents/skills/quick-dev-tdd-adapter/tools/adapter.py"]},
            {"stage": "refactor", "exit_code": 0, "changed_paths": [".agents/skills/quick-dev-tdd-adapter/tools/adapter.py"]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "RUN-001"
            result = self._execute(run_dir, events, protocol_bundle=bundle, artifact_store=store)
            persisted, findings = load_protocol_run(PLAN_ROOT, run_dir)
        self.assertEqual("refactor-verified", result["state"])
        self.assertFalse(any(item["rule_id"] == "RMAP-ATTEMPT-PARTIAL" for item in findings))
        self.assertEqual([], validate_protocol_bundle(PLAN_ROOT, persisted, artifact_store=store, file_versions=versions, require_complete=True))

    def test_protocol_persistence_rejects_conflicting_existing_stage_evidence(self) -> None:
        fixtures = json.loads((PLAN_ROOT / "fixtures" / "capsule-attempt-cases.v1.json").read_text(encoding="utf-8"))
        bundle, store, _ = hydrate_protocol_fixture(fixtures["valid_bundle"])
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "RUN-001"
            run_dir.mkdir()
            (run_dir / "red-result.json").write_bytes(b"conflicting-history")
            with self.assertRaisesRegex(ValueError, "existing protocol artifact"):
                ADAPTER.persist_protocol_bundle(run_dir, bundle, store)

    def test_protocol_persistence_rejects_undeclared_existing_artifact(self) -> None:
        fixtures = json.loads((PLAN_ROOT / "fixtures" / "capsule-attempt-cases.v1.json").read_text(encoding="utf-8"))
        bundle, store, _ = hydrate_protocol_fixture(fixtures["valid_bundle"])
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "RUN-001"
            run_dir.mkdir()
            (run_dir / "unknown-history.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "undeclared existing artifact"):
                ADAPTER.persist_protocol_bundle(run_dir, bundle, store)

    def test_protocol_persistence_preserves_lifecycle_observations(self) -> None:
        fixtures = json.loads((PLAN_ROOT / "fixtures" / "capsule-attempt-cases.v1.json").read_text(encoding="utf-8"))
        bundle, store, _ = hydrate_protocol_fixture(fixtures["valid_bundle"])
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "RUN-001"
            observation_dir = run_dir / "observations"; observation_dir.mkdir(parents=True)
            for stage in ("red", "green", "refactor"):
                (observation_dir / f"{stage}-observed.json").write_text("{}", encoding="utf-8")
            ADAPTER.persist_protocol_bundle(run_dir, bundle, store)
            self.assertTrue((observation_dir / "refactor-observed.json").is_file())

    def test_protocol_persistence_preserves_staged_boundary_metadata(self) -> None:
        fixtures = json.loads((PLAN_ROOT / "fixtures" / "capsule-attempt-cases.v1.json").read_text(encoding="utf-8"))
        bundle, store, _ = hydrate_protocol_fixture(fixtures["valid_bundle"])
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "RUN-001"
            run_dir.mkdir()
            (run_dir / "stage-state.json").write_text("{}", encoding="utf-8")
            (run_dir / "red-basis.v1.json").write_text("{}", encoding="utf-8")
            ADAPTER.persist_protocol_bundle(run_dir, bundle, store)
            self.assertTrue((run_dir / "attempt-ledger-manifest.v1.json").is_file())

    def test_compose_stage_binding_is_derived_from_protocol_documents(self) -> None:
        fixtures = json.loads((PLAN_ROOT / "fixtures" / "capsule-attempt-cases.v1.json").read_text(encoding="utf-8"))
        bundle, _, _ = hydrate_protocol_fixture(fixtures["valid_bundle"])
        binding = ADAPTER.compose_stage_binding(bundle, "green")
        context = bundle["contexts"][1]["context_manifest"]
        attempt = bundle["attempts"][1]
        self.assertEqual("STAGE-GREEN", binding["stage_binding_id"])
        self.assertEqual("ATTEMPT-002", binding["attempt_id"])
        self.assertEqual(context["capsule_ref"]["sha256"], binding["capsule_hash"])
        self.assertEqual(context["context_hash"], binding["context_hash"])
        self.assertTrue(binding["decision_hash"].startswith("sha256:"))
        self.assertEqual([], attempt["adapter_decision"]["authorizes"])

    def test_skill_protocol_builder_produces_a_guard_valid_bundle(self) -> None:
        fixtures = json.loads((PLAN_ROOT / "fixtures" / "capsule-attempt-cases.v1.json").read_text(encoding="utf-8"))
        bundle, store, versions = PROTOCOL_BUILDER.build_fixture_bundle(fixtures["valid_bundle"])
        self.assertEqual([], validate_protocol_bundle(PLAN_ROOT, bundle, artifact_store=store, file_versions=versions, require_complete=True))

    def test_skill_owns_protocol_fixture_core(self) -> None:
        self.assertTrue((TOOLS / "protocol_fixture_support.py").is_file())

    def test_protocol_persistence_rejects_reparse_point_history(self) -> None:
        fixtures = json.loads((PLAN_ROOT / "fixtures" / "capsule-attempt-cases.v1.json").read_text(encoding="utf-8"))
        bundle, store, _ = hydrate_protocol_fixture(fixtures["valid_bundle"])
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "RUN-001"
            run_dir.mkdir()
            marker = run_dir / "linked-history.json"
            marker.write_text("{}", encoding="utf-8")
            original = Path.is_symlink
            with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=lambda path: path == marker or original(path)):
                with self.assertRaisesRegex(ValueError, "reparse point"):
                    ADAPTER.persist_protocol_bundle(run_dir, bundle, store)

    def test_stage_observation_requires_safe_base64_snapshots(self) -> None:
        observation = {
            "stage": "green", "exit_code": 0, "observed_at": "2026-07-21T00:00:00Z",
            "changed_files": [{"path": "file.txt", "before_bytes_base64": "YmVmb3Jl", "after_bytes_base64": "YWZ0ZXI="}],
            "commands_attempted": ["rmap-adapter-tests"], "response_summary": "passed",
        }
        parsed = STAGE_OBSERVATION.parse(observation)
        self.assertEqual(b"before", parsed["changed_files"][0]["before_bytes"])
        invalid = {**observation, "changed_files": [{"path": "file.txt", "before_bytes_base64": "not-base64", "after_bytes_base64": "YWZ0ZXI="}]}
        with self.assertRaisesRegex(ValueError, "base64"):
            STAGE_OBSERVATION.parse(invalid)

    def test_stage_observation_sequence_requires_observed_tdd_order(self) -> None:
        def observation(stage: str, exit_code: int, when: str) -> dict:
            return {"stage": stage, "exit_code": exit_code, "observed_at": when, "changed_files": [], "commands_attempted": ["rmap-adapter-tests"], "response_summary": "observed"}
        sequence = [observation("red", 1, "2026-07-21T00:00:01Z"), observation("green", 0, "2026-07-21T00:00:02Z"), observation("refactor", 0, "2026-07-21T00:00:03Z")]
        self.assertEqual(["red", "green", "refactor"], [item["stage"] for item in STAGE_OBSERVATION.parse_sequence(sequence)])
        with self.assertRaisesRegex(ValueError, "RED"):
            STAGE_OBSERVATION.parse_sequence([observation("red", 0, "2026-07-21T00:00:01Z")])

    def test_stage_observation_derives_canonical_snapshot_diff(self) -> None:
        parsed = STAGE_OBSERVATION.parse({
            "stage": "green", "exit_code": 0, "observed_at": "2026-07-21T00:00:00Z",
            "changed_files": [
                {"path": "modify.txt", "before_bytes_base64": "b2xk", "after_bytes_base64": "bmV3"},
                {"path": "add.txt", "before_bytes_base64": None, "after_bytes_base64": "bmV3"},
                {"path": "delete.txt", "before_bytes_base64": "b2xk", "after_bytes_base64": None},
            ], "commands_attempted": ["rmap-adapter-tests"], "response_summary": "passed",
        })
        diff = STAGE_OBSERVATION.canonical_diff(parsed)
        self.assertEqual(["add", "delete", "modify"], [entry["change_type"] for entry in diff])
        self.assertTrue(all(entry["after_sha256"] is None or entry["after_sha256"].startswith("sha256:") for entry in diff))

    def test_stage_observation_builds_untrusted_minimized_response(self) -> None:
        parsed = STAGE_OBSERVATION.parse({"stage": "green", "exit_code": 0, "observed_at": "2026-07-21T00:00:00Z", "changed_files": [{"path": "file.txt", "before_bytes_base64": "b2xk", "after_bytes_base64": "bmV3"}], "commands_attempted": ["rmap-adapter-tests"], "response_summary": "passed"})
        response = STAGE_OBSERVATION.backend_response(parsed, "repository-maintenance-tdd-adapter", "RMAP-S2", "RUN-001", "ATTEMPT-002")
        self.assertEqual(["file.txt"], response["changed_files"])
        self.assertTrue(response["untrusted"])
        self.assertFalse(response["raw_body_persisted"])

    def test_stage_observation_builds_minimized_request(self) -> None:
        request = STAGE_OBSERVATION.backend_request("repository-maintenance-tdd-adapter", "RMAP-S2", "RUN-001", "ATTEMPT-002", "green", "sha256:" + "1" * 64, ["rmap-adapter-tests"], "ATTEMPT-001")
        self.assertEqual("make-red-green", request["goal"])
        self.assertFalse(request["raw_body_persisted"])
        self.assertFalse(request["actor"]["identity_authoritative"])

    def test_stage_artifact_composer_closes_explicit_observations(self) -> None:
        contract_bytes = (PLAN_ROOT / "implementation-contract.v1.json").read_bytes()
        authority_bytes = (PLAN_ROOT / "schemas/authority-manifest.v1.json").read_bytes()
        observations = [
            {"stage": "red", "exit_code": 1, "observed_at": "2026-07-21T00:00:01Z", "commands_attempted": ["rmap-s2-slice-validate"], "response_summary": "RED observed", "changed_files": [{"path": ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_adapter.py", "before_bytes_base64": "YmFzZWxpbmU=", "after_bytes_base64": "cmVk"}]},
            {"stage": "green", "exit_code": 0, "observed_at": "2026-07-21T00:00:02Z", "commands_attempted": ["rmap-s2-slice-validate"], "response_summary": "GREEN observed", "changed_files": [{"path": ".agents/skills/quick-dev-tdd-adapter/tools/adapter.py", "before_bytes_base64": "YmFzZWxpbmU=", "after_bytes_base64": "Z3JlZW4="}]},
            {"stage": "refactor", "exit_code": 0, "observed_at": "2026-07-21T00:00:03Z", "commands_attempted": ["rmap-s2-slice-validate"], "response_summary": "REFACTOR observed", "changed_files": [{"path": ".agents/skills/quick-dev-tdd-adapter/tools/adapter.py", "before_bytes_base64": "Z3JlZW4=", "after_bytes_base64": "cmVmYWN0b3I="}]},
        ]
        context = {
            "plan_id": "repository-maintenance-tdd-adapter", "slice_id": "RMAP-S2", "run_id": "RUN-OBSERVED-001",
            "authority_refs": [{"role": "authority-manifest", "path_type": "plan_path", "path": "schemas/authority-manifest.v1.json", "payload": authority_bytes}],
            "implementation_contract": {"role": "implementation-contract", "path_type": "plan_path", "path": "implementation-contract.v1.json", "payload": contract_bytes},
            "requirement_ids": ["RMAP-S2"], "acceptance_ids": ["RMAP-S2-AC1"], "source_refs": ["explicit-test-observation"],
            "boundaries": {"allowed_write_set": [".agents/skills/quick-dev-tdd-adapter/**"], "forbidden_write_set": ["PhaseA.Platform/**"], "execution_read_set": [".agents/skills/quick-dev-tdd-adapter/**"], "dependency_closure": [".agents/skills/quick-dev-tdd-adapter/**"]},
            "target_command_ids": ["rmap-s2-slice-validate"],
            "stage_results": {stage: {"schema_version": "rmap.tdd-stage-result.v1", "stage": stage} for stage in ("red", "green", "refactor")},
        }
        bundle, store, versions = STAGE_COMPOSER.compose(context, observations, {})
        self.assertEqual([], validate_protocol_bundle(PLAN_ROOT, bundle, artifact_store=store, file_versions=versions, require_complete=True))
        self.assertEqual("ATTEMPT-003", bundle["attempts"][-1]["backend_request"]["attempt_id"])
        self.assertIn(("run_path", "refactor-result.json"), store)
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "RUN-OBSERVED-001"
            ADAPTER.persist_protocol_bundle(run_dir, bundle, store)
            loaded, findings = load_protocol_run(PLAN_ROOT, run_dir, verify_final_worktree=False)
        self.assertEqual([], findings)
        self.assertEqual(bundle["attempt_ledger_manifest"], loaded["attempt_ledger_manifest"])

    def test_stage_artifact_composer_preserves_absent_planned_file_baseline(self) -> None:
        contract_bytes = (PLAN_ROOT / "implementation-contract.v1.json").read_bytes()
        authority_bytes = (PLAN_ROOT / "schemas/authority-manifest.v1.json").read_bytes()
        path = ".agents/skills/quick-dev-tdd-adapter/schemas/planned-new.v1.schema.json"
        observations = [
            {"stage": "red", "exit_code": 1, "observed_at": "2026-07-21T00:00:01Z", "commands_attempted": ["rmap-s2-slice-validate"], "response_summary": "RED observed", "changed_files": []},
            {"stage": "green", "exit_code": 0, "observed_at": "2026-07-21T00:00:02Z", "commands_attempted": ["rmap-s2-slice-validate"], "response_summary": "GREEN observed", "changed_files": [{"path": path, "before_bytes_base64": None, "after_bytes_base64": "bmV3"}]},
            {"stage": "refactor", "exit_code": 0, "observed_at": "2026-07-21T00:00:03Z", "commands_attempted": ["rmap-s2-slice-validate"], "response_summary": "REFACTOR observed", "changed_files": [{"path": path, "before_bytes_base64": "bmV3", "after_bytes_base64": "bmV3"}]},
        ]
        context = {
            "plan_id": "repository-maintenance-tdd-adapter", "slice_id": "RMAP-S2", "run_id": "RUN-PLANNED-NEW-001",
            "authority_refs": [{"role": "authority-manifest", "path_type": "plan_path", "path": "schemas/authority-manifest.v1.json", "payload": authority_bytes}],
            "implementation_contract": {"role": "implementation-contract", "path_type": "plan_path", "path": "implementation-contract.v1.json", "payload": contract_bytes},
            "requirement_ids": ["RMAP-S2"], "acceptance_ids": ["RMAP-S2-AC1"], "source_refs": ["explicit-test-observation"],
            "boundaries": {"allowed_write_set": [".agents/skills/quick-dev-tdd-adapter/**"], "forbidden_write_set": ["PhaseA.Platform/**"], "execution_read_set": [".agents/skills/quick-dev-tdd-adapter/**"], "dependency_closure": [".agents/skills/quick-dev-tdd-adapter/**"]},
            "target_command_ids": ["rmap-s2-slice-validate"],
            "stage_results": {stage: {"schema_version": "rmap.tdd-stage-result.v1", "stage": stage} for stage in ("red", "green", "refactor")},
        }

        bundle, _, _ = STAGE_COMPOSER.compose(context, observations, {})

        self.assertEqual([], bundle["baseline_file_manifest"]["files"])
        self.assertEqual("add", bundle["attempts"][1]["diff_manifest"]["files"][0]["change_type"])

    def test_stage_observation_runner_captures_declared_bytes_after_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "changed.txt"
            target.write_bytes(b"before")
            baseline = STAGE_RUNNER.freeze(root, ["changed.txt"])
            target.write_bytes(b"red-test-write")
            command = {"id": "write", "executable": sys.executable, "argv": ["-c", "from pathlib import Path; Path('changed.txt').write_bytes(b'after')"], "cwd": ".", "timeout_seconds": 10, "shell": False}
            observation = STAGE_RUNNER.run(root, "green", command, ["changed.txt"], "command completed", before_snapshots=baseline)
            evidence = STAGE_RUNNER.record_observation(root / "evidence", observation)
            self.assertTrue(evidence.is_file())
            with self.assertRaisesRegex(ValueError, "already exists"):
                STAGE_RUNNER.record_observation(root / "evidence", observation)
        change = observation["changed_files"][0]
        self.assertEqual(b"before", base64.b64decode(change["before_bytes_base64"]))
        self.assertEqual(b"after", base64.b64decode(change["after_bytes_base64"]))
        self.assertEqual(["write"], observation["commands_attempted"])
        self.assertEqual(0, observation["exit_code"])

    def test_lifecycle_runner_requires_order_and_carries_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "changed.txt"
            target.write_bytes(b"baseline")
            command = {"id": "write", "executable": sys.executable, "argv": ["-c", "from pathlib import Path; Path('changed.txt').write_bytes(b'after')"], "cwd": ".", "timeout_seconds": 10, "shell": False}
            runner = LIFECYCLE.LifecycleRunner(root, root / "evidence", ["changed.txt"])
            with self.assertRaisesRegex(ValueError, "not next"):
                runner.observe("green", command, "invalid order")
            red = runner.observe("red", command, "red command")
            self.assertEqual("YmFzZWxpbmU=", red["changed_files"][0]["before_bytes_base64"])
            green = runner.observe("green", command, "green command")
            self.assertEqual("YWZ0ZXI=", green["changed_files"][0]["before_bytes_base64"])

    def test_record_observation_rejects_naive_timestamp(self) -> None:
        observation = {"stage": "red", "exit_code": 1, "observed_at": "2026-07-21T05:00:00", "changed_files": [], "commands_attempted": ["rmap-adapter-tests"], "response_summary": "observed"}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "observed_at"):
                STAGE_RUNNER.record_observation(Path(tmp), observation)

    def test_record_observation_rejects_empty_response_summary(self) -> None:
        observation = {"stage": "red", "exit_code": 1, "observed_at": "2026-07-21T05:00:00Z", "changed_files": [], "commands_attempted": ["rmap-adapter-tests"], "response_summary": ""}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "response_summary"):
                STAGE_RUNNER.record_observation(Path(tmp), observation)



if __name__ == "__main__":
    unittest.main()

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


TOOLS = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
STAGE_RECOVERY_PLAN = REPOSITORY_ROOT / "execution-plans" / "2026-08-17-quick-dev-tdd-stage-recovery"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROUTER = load("route_plan_directory")
BUILDER = load("build_slice_invocation")
LIFECYCLE = load("run_slice_lifecycle")
CONTROLLER = load("persistent_plan_loop")
with mock.patch.dict(sys.modules, {"route_plan_directory": ROUTER}):
    DRIVER = load("loop_plan_directory")
MIGRATION_BRIDGE = load_path("stage_recovery_migration_bridge", STAGE_RECOVERY_PLAN / "tools" / "migration_bridge.py")


class PlanDirectoryLoopTests(unittest.TestCase):
    def _plan(self, root: Path, slices: list[dict]) -> Path:
        plan = root / "execution-plans" / "target"
        plan.mkdir(parents=True)
        (plan / "implementation-contract.v1.json").write_text(json.dumps({"plan_id": "target", "slices": slices}), encoding="utf-8")
        return plan

    def test_quick_dev_compiles_vdd_failure_intent_without_a_prebound_red_command(self) -> None:
        red = BUILDER._generated_red_descriptor("S3", {
            "test_selector": ".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator.py::CoordinatorTests::test_replays_binding",
            "expected_failure_ids": ["ACE-S3-EXIT"],
        })
        self.assertEqual("quick-dev-generated-red-S3", red["id"])
        self.assertEqual(["-3", "-B", "-m", "pytest"], red["argv"][:4])

    def test_quick_dev_rejects_vdd_red_evidence_binding(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not bind"):
            BUILDER._generated_red_descriptor("S3", {
                "test_selector": ".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator.py",
                "expected_failure_ids": ["ACE-S3-EXIT"],
                "legacy_predecessor": {"path": "logs/red.json", "sha256": "sha256:bad"},
            })

    def test_quick_dev_allows_only_the_declared_repository_test_root(self) -> None:
        descriptor = BUILDER._generated_red_descriptor("S0", {
            "test_selector": "scripts/python/tests/test_target.py::test_target",
            "expected_failure_ids": ["S0-EXIT"],
        }, ["scripts/python/tests/test_target.py"])
        self.assertEqual("scripts/python/tests/test_target.py::test_target", descriptor["argv"][-2])
        with self.assertRaisesRegex(ValueError, "invalid"):
            BUILDER._generated_red_descriptor("S0", {
                "test_selector": "scripts/python/tests/test_other.py",
                "expected_failure_ids": ["S0-EXIT"],
            }, ["scripts/python/tests/test_target.py"])

    def test_run_red_only_executes_no_later_tdd_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = DRIVER.run_red_only(Path(tmp), {
                "id": "red-only",
                "executable": sys.executable,
                "argv": ["-c", "raise SystemExit(1)"],
                "cwd": ".",
                "timeout_seconds": 10,
                "shell": False,
            })

        self.assertEqual(1, result.returncode)

    def test_plan_owned_schema_distinguishes_quick_dev_red_intent(self) -> None:
        schema = json.loads((REPOSITORY_ROOT / ".agents/skills/quick-dev-tdd-adapter/schemas/plan-owned-implementation-contract.v1.schema.json").read_text(encoding="utf-8"))
        quick = schema["$defs"]["quickDevRedIntent"]
        legacy = schema["$defs"]["legacyRedIntent"]
        self.assertEqual(["test_selector", "expected_failure_ids"], quick["required"])
        self.assertFalse(quick["additionalProperties"])
        self.assertIn("command_id", legacy["required"])
        self.assertEqual("#/$defs/quickDevRedIntent", schema["allOf"][0]["then"]["properties"]["slices"]["items"]["properties"]["tdd"]["properties"]["red"]["$ref"])

    def test_migration_bridge_materializes_only_current_slice_test_before_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "execution-plans" / "stage-recovery"
            plan.mkdir(parents=True)
            contract = json.loads((STAGE_RECOVERY_PLAN / "implementation-contract.v1.json").read_text(encoding="utf-8"))
            contract["plan_id"] = "stage-recovery"
            (plan / "implementation-contract.v1.json").write_text(json.dumps(contract), encoding="utf-8")

            run_dir = MIGRATION_BRIDGE.run_red(root, plan, "S0")

            created = root / ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_stage_lifecycle.py"
            handoff = json.loads((run_dir / "implementation-needed-result.json").read_text(encoding="utf-8"))
            self.assertTrue(created.is_file())
            self.assertFalse((root / ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_stage_recovery.py").exists())
            self.assertEqual("implementation-needed", handoff["predicate"])
            self.assertEqual("red", handoff["stage"])
            self.assertNotEqual(0, handoff["exit_code"])
            self.assertTrue(MIGRATION_BRIDGE.materialize_red_test(root, contract["slices"][0]).is_file())

    def test_matching_bridge_handoff_is_reused_as_the_red_predecessor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "execution-plans" / "stage-recovery"
            plan.mkdir(parents=True)
            contract = json.loads((STAGE_RECOVERY_PLAN / "implementation-contract.v1.json").read_text(encoding="utf-8"))
            contract["plan_id"] = "stage-recovery"
            (plan / "implementation-contract.v1.json").write_text(json.dumps(contract), encoding="utf-8")
            MIGRATION_BRIDGE.run_red(root, plan, "S0")

            handoff = DRIVER._current_bridge_handoff(root, plan, contract, "S0")

            self.assertIsNotNone(handoff)
            self.assertTrue(handoff["path"].endswith("implementation-needed-result.json"))
            self.assertTrue(handoff["sha256"].startswith("sha256:"))

    def test_bridge_handoff_with_test_hash_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "execution-plans" / "stage-recovery"
            plan.mkdir(parents=True)
            contract = json.loads((STAGE_RECOVERY_PLAN / "implementation-contract.v1.json").read_text(encoding="utf-8"))
            contract["plan_id"] = "stage-recovery"
            (plan / "implementation-contract.v1.json").write_text(json.dumps(contract), encoding="utf-8")
            MIGRATION_BRIDGE.run_red(root, plan, "S0")
            test_path = root / ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_stage_lifecycle.py"
            test_path.write_text(test_path.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")

            self.assertIsNone(DRIVER._current_bridge_handoff(root, plan, contract, "S0"))

    def test_loop_uses_current_bridge_handoff_for_green_continuation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "execution-plans" / "target"
            plan.mkdir(parents=True)
            (plan / "implementation-contract.v1.json").write_text(json.dumps({
                "plan_id": "target", "adapter_bridge": {"runner": "tools/migration_bridge.py"},
            }), encoding="utf-8")
            calls: list[list[str]] = []

            def fake_run(arguments: list[str], *, timeout_seconds: int = 0) -> None:
                calls.append(arguments)
                if Path(arguments[0]).name != "build_slice_invocation.py":
                    return
                out = Path(arguments[arguments.index("--out-dir") + 1])
                out.mkdir(parents=True)
                command = {"id": "command", "executable": "py", "argv": ["-3", "-B", "-c", "pass"], "cwd": ".", "timeout_seconds": 1, "shell": False}
                (out / "run-context.json").write_text(json.dumps({"stage_results": {"red": {"mode": "red", "prior_red": None, "legacy_predecessor": None}}}), encoding="utf-8")
                for name, value in {
                    "red-command.json": command,
                    "green-command.json": command,
                    "terminal-command.json": command,
                    "refactor-commands.json": [command],
                    "preparation-commands.json": [],
                }.items():
                    (out / name).write_text(json.dumps(value), encoding="utf-8")

            handoff = {"path": "logs/tdd-adapter/target/S0/RUN/red.json", "sha256": "sha256:" + "a" * 64}
            with mock.patch.object(DRIVER, "_current_bridge_handoff", return_value=handoff), mock.patch.object(DRIVER, "_run", side_effect=fake_run):
                DRIVER._run_slice(root, plan, "S0", ["implementation-contract.v1.json"])

            self.assertEqual("build_slice_invocation.py", Path(calls[0][0]).name)
            self.assertEqual("run_slice_lifecycle.py", Path(calls[1][0]).name)
            self.assertEqual("green", calls[1][calls[1].index("--stage") + 1])
            context_path = Path(calls[1][calls[1].index("--run-context") + 1])
            context = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual("prior-red-successor", context["stage_results"]["red"]["mode"])
            self.assertEqual(handoff, context["stage_results"]["red"]["prior_red"])

    def test_router_rejects_plan_path_outside_execution_plans(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"; outside.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "execution-plans"):
                ROUTER.route(root, outside)

    def test_router_cli_requires_its_caller_identity(self) -> None:
        command = [
            sys.executable,
            str(TOOLS / "route_plan_directory.py"),
            "--repository-root", str(REPOSITORY_ROOT),
            "--plan-dir", str(REPOSITORY_ROOT / "execution-plans/2026-08-15-acceptance-review-bootstrap-efficiency"),
        ]
        missing = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertNotEqual(0, missing.returncode)
        wrong = subprocess.run(command + ["--caller", "bmad-quick-dev"], capture_output=True, text=True, check=False)
        self.assertNotEqual(0, wrong.returncode)

    def test_router_ignores_stale_slice_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = self._plan(root, [{"slice_id": "S0", "depends_on": []}])
            stale = root / "logs/tdd-adapter/target/S0/old"; stale.mkdir(parents=True)
            (stale / "slice-ready-result.json").write_text(json.dumps({"predicate": "slice-ready", "status": "pass", "contract_hash": "sha256:stale"}), encoding="utf-8")
            self.assertEqual("run-slice", ROUTER.route(root, plan)["next_action"])

    def test_router_reuses_an_unaffected_slice_from_the_head_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = {
                "plan_id": "target",
                "slices": [
                    {"slice_id": "S0", "depends_on": [], "behavior": "stable"},
                    {"slice_id": "S1", "depends_on": ["S0"], "behavior": "old"},
                ],
            }
            current = {
                "plan_id": "target",
                "slices": [
                    {"slice_id": "S0", "depends_on": [], "behavior": "stable"},
                    {"slice_id": "S1", "depends_on": ["S0"], "behavior": "repaired"},
                ],
            }
            plan = self._plan(root, current["slices"])
            (plan / "command-registry.v1.json").write_text('{"commands":[]}', encoding="utf-8")
            baseline_bytes = json.dumps(baseline, sort_keys=True).encode("utf-8")
            (root / "logs/tdd-adapter/target/S0/current").mkdir(parents=True)
            result = root / "logs/tdd-adapter/target/S0/current/slice-ready-result.json"
            result.write_text(json.dumps({
                "predicate": "slice-ready",
                "status": "pass",
                "contract_hash": "sha256:" + __import__("hashlib").sha256(baseline_bytes).hexdigest(),
            }), encoding="utf-8")

            def head_bytes(_root: Path, relative: Path) -> bytes | None:
                return baseline_bytes if relative.name == "implementation-contract.v1.json" else b'{"commands":[]}'

            with mock.patch.object(ROUTER, "_head_artifact_bytes", side_effect=head_bytes), mock.patch.object(
                ROUTER,
                "_historical_contract_and_registry",
                return_value=(baseline_bytes, b'{"commands":[]}'),
            ):
                routed = ROUTER.route(root, plan)

            self.assertEqual({"next_action": "run-slice", "slice_id": "S1", "authorizes": []}, routed)

    def test_router_reuses_unaffected_slice_when_contract_hash_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = {
                "plan_id": "target",
                "slices": [{"slice_id": "S0", "depends_on": [], "behavior": "stable"}],
            }
            current = {
                "plan_id": "target",
                "slices": [{"slice_id": "S0", "depends_on": [], "behavior": "stable"}],
                "contract_note": "updated terminal evidence",
            }
            plan = self._plan(root, current["slices"])
            plan_contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
            plan_contract["contract_note"] = current["contract_note"]
            (plan / "implementation-contract.v1.json").write_text(json.dumps(plan_contract), encoding="utf-8")
            (plan / "command-registry.v1.json").write_text('{"commands":[]}', encoding="utf-8")
            baseline_bytes = json.dumps(baseline, sort_keys=True).encode("utf-8")
            current_bytes = (plan / "implementation-contract.v1.json").read_bytes()
            evidence = root / "logs/tdd-adapter/target/S0/current"
            evidence.mkdir(parents=True)
            (evidence / "slice-ready-result.json").write_text(json.dumps({
                "predicate": "slice-ready",
                "status": "pass",
                "contract_hash": "sha256:" + __import__("hashlib").sha256(baseline_bytes).hexdigest(),
            }), encoding="utf-8")

            def head_bytes(_root: Path, relative: Path) -> bytes | None:
                return current_bytes if relative.name == "implementation-contract.v1.json" else b'{"commands":[]}'

            with mock.patch.object(ROUTER, "_head_artifact_bytes", side_effect=head_bytes), mock.patch.object(
                ROUTER,
                "_historical_contract_and_registry",
                return_value=(baseline_bytes, b'{"commands":[]}'),
            ):
                routed = ROUTER.route(root, plan)

            self.assertEqual("validate-terminal", routed["next_action"])

    def test_router_requires_implementation_authorization_before_run_slice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan(root, [{"slice_id": "S0", "depends_on": []}])
            (plan / "plan-state.v1.json").write_text(json.dumps({
                "schema_version": "vdd.plan-state.v2",
                "plan_id": "target",
                "status": "plan-ready",
                "authorizes": ["plan-ready"],
            }), encoding="utf-8")

            result = ROUTER.route(root, plan)

            self.assertEqual("awaiting-implementation-authorization", result["next_action"])
            self.assertEqual("implementation-authorization-required", result["reason"])
            self.assertEqual([], result["authorizes"])

    def test_router_runs_slice_after_explicit_implementation_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan(root, [{"slice_id": "S0", "depends_on": []}])
            bindings = {
                "implementation_contract": "implementation-contract.v1.json",
                "command_registry": "command-registry.v1.json",
                "authority_manifest": "authority-manifest.v1.json",
                "knowledge_context_freeze": "knowledge-context.freeze.v1.json",
                "skill_input_receipt": "skill-input-receipt.successor.v1.json",
                "skill_input_request": "skill-input-request.v1.json",
                "plan_validation": "repair/round-1/plan-validation-receipt.v2.json",
                "repair_closure": "repair/round-1/repair-closure.v1.json",
                "bootstrap_preexisting_delta": "repair/round-1/bootstrap-preexisting-delta.v1.json",
                "candidate_manifest": "repair/round-1/repair-candidate-manifest.v1.json",
                "validate_all": "tools/validate_all.py",
                "terminal_validator": "tools/terminal_full.py",
                "immutable_predecessor": "repair/round-1/authorization-predecessor.v1.json",
            }
            for name in list(bindings.values())[1:]:
                path = plan / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}\n", encoding="utf-8")
            (plan / "plan-state.v1.json").write_text(json.dumps({
                "schema_version": "vdd.plan-state.v2",
                "plan_id": "target",
                "status": "implementation-authorized",
                "authorizes": ["plan-ready", "implementation-authorized"],
            }), encoding="utf-8")
            receipt_bindings = {}
            for field, name in bindings.items():
                path = plan / name
                receipt_bindings[field] = {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": "sha256:" + __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
                }
            (plan / "implementation-authorization-receipt.successor.v1.json").write_text(json.dumps({
                "plan_id": "target",
                **receipt_bindings,
                "decision": {"owner": "maintainer", "transition": "implementation-authorized"},
                "authorizes": ["implementation-authorized"],
            }), encoding="utf-8")

            self.assertEqual("run-slice", ROUTER.route(root, plan)["next_action"])

            changed_contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
            changed_contract["changed"] = True
            (plan / "implementation-contract.v1.json").write_text(json.dumps(changed_contract), encoding="utf-8")
            result = ROUTER.route(root, plan)
            self.assertEqual("awaiting-implementation-authorization", result["next_action"])
            self.assertEqual("implementation-authorization-stale", result["reason"])

    def test_top_level_active_route_exposes_implementation_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "logs/tdd-adapter/target/S0/RUN-001"
            observations = run / "observations"
            observations.mkdir(parents=True)
            (run / "stage-state.json").write_text(json.dumps({"stage": "red", "next_stage": "implement"}), encoding="utf-8")
            (observations / "red-observed.json").write_text(json.dumps({"stage": "red", "exit_code": 1}), encoding="utf-8")
            (run / "red-basis.v1.json").write_text(json.dumps({
                "contract_hash": "sha256:contract",
                "validator_hash": "sha256:validator",
                "pre_implementation_candidate": {"candidate_binding_hash": "sha256:before"},
            }), encoding="utf-8")
            self.assertEqual("implement", ROUTER._active_slice_action(root, "target", "S0"))

    def test_router_rejects_abbreviated_v2_implementation_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan(root, [{"slice_id": "S0", "depends_on": []}])
            (plan / "plan-state.v1.json").write_text(json.dumps({
                "schema_version": "vdd.plan-state.v2",
                "plan_id": "target",
                "status": "implementation-authorized",
                "authorizes": ["implementation-authorized"],
            }), encoding="utf-8")

            result = ROUTER.route(root, plan)

            self.assertEqual("external-repair-required", result["next_action"])
            self.assertEqual("invalid-plan-state", result["reason"])

    def test_router_rejects_contradictory_lifecycle_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan(root, [{"slice_id": "S0", "depends_on": []}])
            (plan / "plan-state.v1.json").write_text(json.dumps({
                "schema_version": "vdd.plan-state.v2",
                "plan_id": "target",
                "status": "plan-ready",
                "state": "implementation-authorized",
                "authorizes": ["implementation-authorized"],
            }), encoding="utf-8")

            result = ROUTER.route(root, plan)

            self.assertEqual("external-repair-required", result["next_action"])
            self.assertEqual("invalid-plan-state", result["reason"])

    def test_router_rejects_slice_execution_from_completed_plan_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan(root, [{"slice_id": "S0", "depends_on": []}])
            (plan / "plan-state.v1.json").write_text(json.dumps({
                "schema_version": "vdd.plan-state.v2",
                "plan_id": "target",
                "status": "implementation-complete",
                "authorizes": ["implementation-complete"],
            }), encoding="utf-8")

            result = ROUTER.route(root, plan)

            self.assertEqual("external-repair-required", result["next_action"])
            self.assertEqual("plan-state-precludes-slice-execution", result["reason"])

    def test_router_routes_s7_as_an_ordinary_completion_slice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); slices = [{"slice_id": "S0", "depends_on": []}, {"slice_id": "RMAP-S7", "depends_on": ["S0"]}]
            plan = self._plan(root, slices)
            contract_hash = "sha256:" + __import__("hashlib").sha256((plan / "implementation-contract.v1.json").read_bytes()).hexdigest()
            result = root / "logs/tdd-adapter/target/S0/current"; result.mkdir(parents=True)
            (result / "slice-ready-result.json").write_text(json.dumps({"predicate": "slice-ready", "status": "pass", "contract_hash": contract_hash}), encoding="utf-8")
            self.assertEqual("run-slice", ROUTER.route(root, plan)["next_action"])

    def test_router_replays_stale_implementation_candidate_before_s7(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slices = [
                {"slice_id": "RMAP-S6", "depends_on": [], "exit_predicate": "implementation-candidate"},
                {"slice_id": "RMAP-S7", "depends_on": ["RMAP-S6"]},
            ]
            plan = self._plan(root, slices)
            evidence = root / "logs/tdd-adapter/target/RMAP-S6/old"; evidence.mkdir(parents=True)
            (evidence / "implementation-candidate-result.json").write_text("{}", encoding="utf-8")
            (evidence / "candidate-evidence.json").write_text("{}", encoding="utf-8")
            (evidence / "implementation-candidate-result.json").write_text(json.dumps({
                "predicate": "implementation-candidate", "status": "pass",
                "candidate_hash": "sha256:stale",
                "current_candidate_hash": "sha256:current", "predicate_input_root": "sha256:current",
            }), encoding="utf-8")
            self.assertEqual("run-slice", ROUTER.route(root, plan)["next_action"])

    def test_router_replays_implementation_candidate_with_missing_current_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slices = [
                {"slice_id": "RMAP-S6", "depends_on": [], "exit_predicate": "implementation-candidate"},
                {"slice_id": "RMAP-S7", "depends_on": ["RMAP-S6"]},
            ]
            plan = self._plan(root, slices)
            contract_hash = "sha256:" + __import__("hashlib").sha256(
                (plan / "implementation-contract.v1.json").read_bytes()
            ).hexdigest()
            evidence = root / "logs/tdd-adapter/target/RMAP-S6/current"
            evidence.mkdir(parents=True)
            (evidence / "implementation-candidate-result.json").write_text(json.dumps({
                "predicate": "implementation-candidate",
                "status": "pass",
                "contract_hash": contract_hash,
                "candidate_hash": "sha256:candidate",
            }), encoding="utf-8")
            (evidence / "candidate-evidence.json").write_text("{}", encoding="utf-8")

            result = ROUTER.route(root, plan)

            self.assertEqual("run-slice", result["next_action"])
            self.assertEqual("RMAP-S6", result["slice_id"])

    def test_router_accepts_current_slice_evidence_with_targeted_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = self._plan(root, [{"slice_id": "S0", "depends_on": []}])
            run = root / "logs/tdd-adapter/target/S0/targeted"; run.mkdir(parents=True)
            contract_hash = "sha256:" + __import__("hashlib").sha256((plan / "implementation-contract.v1.json").read_bytes()).hexdigest()
            (run / "slice-ready-result.json").write_text(json.dumps({"predicate": "slice-ready", "status": "pass", "contract_hash": contract_hash}), encoding="utf-8")
            (run / "targeted-validation.v1.json").write_text("{}", encoding="utf-8")
            self.assertEqual("validate-terminal", ROUTER.route(root, plan)["next_action"])

    def test_router_uses_global_snapshot_for_implementation_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan(root, [{
                "slice_id": "S7",
                "depends_on": [],
                "exit_predicate": "implementation-complete",
            }])
            run = root / "logs/tdd-adapter/target/S7/current"
            run.mkdir(parents=True)
            current = {
                "candidate_hash": "sha256:current",
                "predicate_input_root": "sha256:current",
                "authority_root": "sha256:authority",
                "validator_root": "sha256:validator",
                "validator_version": "validator-v1",
                "closure_definition_hash": "sha256:closure",
            }
            result = dict(current, predicate="implementation-complete", status="pass")
            (run / "implementation-complete-result.json").write_text(
                json.dumps(result), encoding="utf-8"
            )

            with mock.patch.object(ROUTER, "_validation_snapshot", return_value=current) as snapshot:
                self.assertEqual("validate-terminal", ROUTER.route(root, plan)["next_action"])

            snapshot.assert_called_once_with(plan.resolve(), None)

    def test_terminal_requires_an_explicit_plan_owned_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan(root, [{"slice_id": "S0", "depends_on": []}])
            with self.assertRaisesRegex(ValueError, "terminal contract"):
                DRIVER._terminal_contract(plan)

    def test_router_replays_authority_stale_implementation_candidate_before_s7(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slices = [
                {"slice_id": "RMAP-S6", "depends_on": [], "exit_predicate": "implementation-candidate"},
                {"slice_id": "RMAP-S7", "depends_on": ["RMAP-S6"]},
            ]
            plan = self._plan(root, slices)
            evidence = root / "logs/tdd-adapter/target/RMAP-S6/old"; evidence.mkdir(parents=True)
            current = {
                "candidate_hash": "sha256:current",
                "predicate_input_root": "sha256:current",
                "authority_root": "sha256:current-authority",
                "validator_root": "sha256:current-validator",
                "validator_version": "validator-v1",
                "closure_definition_hash": "sha256:current-closure",
            }
            stale = dict(current, authority_root="sha256:stale-authority")
            stale.update({"predicate": "implementation-candidate", "status": "pass"})
            (evidence / "implementation-candidate-result.json").write_text(json.dumps(stale), encoding="utf-8")
            (evidence / "candidate-evidence.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(ROUTER, "_validation_snapshot", return_value=current):
                self.assertEqual("run-slice", ROUTER.route(root, plan)["next_action"])

    def test_controller_consumes_only_explicit_snapshot_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan(root, [{
                "slice_id": "RMAP-S7",
                "depends_on": [],
                "allowed_changes": {"production": [], "tests": ["tools/tests/**"], "documentation": []},
                "execution_snapshot_paths": ["tools/tests/test_final.py"],
            }])
            self.assertEqual("tools/tests/test_final.py", CONTROLLER._snapshot(plan, "RMAP-S7"))

    def test_controller_rejects_missing_snapshot_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan(root, [{"slice_id": "RMAP-S7", "depends_on": [], "allowed_changes": {}}])
            with self.assertRaisesRegex(ValueError, "declared execution snapshot"):
                CONTROLLER._snapshot(plan, "RMAP-S7")

    def test_persistent_controller_dispatches_refresh_and_terminal_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self._plan(root, [{"slice_id": "S0", "depends_on": []}])
            state = root / "logs" / "controller-state.json"
            routes = iter([
                {"next_action": "refresh-knowledge-context"},
                {"next_action": "validate-terminal"},
                {"next_action": "implementation-complete"},
            ])
            with mock.patch.object(CONTROLLER.subprocess, "check_output", side_effect=lambda *_args, **_kwargs: json.dumps(next(routes))), \
                 mock.patch.object(CONTROLLER.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run, \
                 mock.patch.object(CONTROLLER.time, "sleep"), \
                 mock.patch.object(sys, "argv", ["persistent_plan_loop.py", "--repository-root", str(root), "--plan-dir", str(plan), "--state-file", str(state), "--poll-seconds", "0"]):
                self.assertEqual(0, CONTROLLER.main())

            self.assertEqual(2, run.call_count)
            self.assertEqual("implementation-complete", json.loads(state.read_text(encoding="utf-8"))["action"])

    def test_builder_expands_run_path_and_serializes_base64_context(self) -> None:
        plan = REPOSITORY_ROOT / "execution-plans/2026-07-15-repository-maintenance-tdd-adapter"
        result = BUILDER.build(REPOSITORY_ROOT, plan, "RMAP-S0", "RUN-TEST")
        self.assertIn("logs/tdd-adapter/repository-maintenance-tdd-adapter/RMAP-S0/RUN-TEST", result["terminal"]["argv"])
        self.assertIn("payload_base64", result["run_context"]["implementation_contract"])
        self.assertTrue(__import__("base64").b64decode(result["run_context"]["implementation_contract"]["payload_base64"], validate=True))
        self.assertIsInstance(result["run_context"]["boundaries"]["allowed_write_set"], list)

    def test_builder_expands_a_declared_slice_id_placeholder(self) -> None:
        self.assertEqual("S4", BUILDER._expand(
            {"type": "slice_id", "value": "<slice-id>"},
            plan_rel="execution-plans/target", plan_id="target", slice_id="S4",
            run_id="RUN-TEST", candidate_run_id="",
        ))

    def test_lifecycle_rejects_shell_command_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "command.json"
            path.write_text(json.dumps({"id": "x", "executable": "py", "argv": [], "cwd": ".", "timeout_seconds": 1, "shell": True}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "shell-free"):
                LIFECYCLE._command(str(path))

    def test_lifecycle_rejects_existing_run_before_consuming_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = root / "execution-plans" / "target"; plan.mkdir(parents=True)
            run = root / "logs" / "tdd-adapter" / "target" / "S0" / "existing"; run.mkdir(parents=True)
            command = [sys.executable, str(TOOLS / "run_slice_lifecycle.py"), "--workspace", str(root), "--plan-dir", str(plan), "--run-dir", str(run), "--slice-id", "S0", "--run-context", str(root / "missing.json"), "--snapshot-path", "x.txt", "--command", "red=x", "--command", "green=x", "--command", "refactor=x", "--terminal-command", str(root / "terminal.json")]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("run directory already exists", result.stderr)

    def test_legacy_regression_requires_a_bound_prior_failed_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "logs" / "prior-red.json"
            evidence.parent.mkdir(parents=True)
            evidence.write_text(json.dumps({
                "stage": "red",
                "exit_code": 4,
                "commands_attempted": ["canonical-evidence-red"],
            }), encoding="utf-8")
            digest = "sha256:" + __import__("hashlib").sha256(evidence.read_bytes()).hexdigest()

            result = BUILDER._legacy_predecessor(root, {
                "command_id": "canonical-evidence-red",
                "mode": "legacy-regression",
                "legacy_predecessor": {"path": "logs/prior-red.json", "sha256": digest},
            })

            self.assertEqual({"path": "logs/prior-red.json", "sha256": digest}, result)

    def test_legacy_regression_rejects_an_unbound_or_passing_prior_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "logs" / "prior-red.json"
            evidence.parent.mkdir(parents=True)
            evidence.write_text(json.dumps({
                "stage": "red",
                "exit_code": 0,
                "commands_attempted": ["canonical-evidence-red"],
            }), encoding="utf-8")
            digest = "sha256:" + __import__("hashlib").sha256(evidence.read_bytes()).hexdigest()

            with self.assertRaisesRegex(ValueError, "prior RED"):
                BUILDER._legacy_predecessor(root, {
                    "command_id": "canonical-evidence-red",
                    "mode": "legacy-regression",
                    "legacy_predecessor": {"path": "logs/prior-red.json", "sha256": digest},
                })

    def test_legacy_regression_accepts_current_green_and_preserves_normal_red(self) -> None:
        LIFECYCLE._validate_red_exit("legacy-regression", 0)
        LIFECYCLE._validate_red_exit("red", 4)
        with self.assertRaisesRegex(RuntimeError, "legacy regression command failed"):
            LIFECYCLE._validate_red_exit("legacy-regression", 4)
        with self.assertRaisesRegex(RuntimeError, "unexpectedly passed"):
            LIFECYCLE._validate_red_exit("red", 0)

    def test_prior_red_successor_binds_failed_predecessor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prior = root / "logs" / "prior-red.json"
            prior.parent.mkdir(parents=True)
            prior.write_text(json.dumps({"stage": "red", "exit_code": 3, "commands_attempted": ["red-command"]}), encoding="utf-8")
            digest = "sha256:" + __import__("hashlib").sha256(prior.read_bytes()).hexdigest()
            self.assertEqual(
                {"path": "logs/prior-red.json", "sha256": digest},
                LIFECYCLE._prior_red_successor(root, {"path": "logs/prior-red.json", "sha256": digest}, "red-command"),
            )

    def test_prior_red_successor_rejects_passing_or_wrong_command_predecessor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prior = root / "logs" / "prior-red.json"
            prior.parent.mkdir(parents=True)
            prior.write_text(json.dumps({"stage": "red", "exit_code": 0, "commands_attempted": ["other"]}), encoding="utf-8")
            digest = "sha256:" + __import__("hashlib").sha256(prior.read_bytes()).hexdigest()
            with self.assertRaisesRegex(RuntimeError, "matching failed RED"):
                LIFECYCLE._prior_red_successor(root, {"path": "logs/prior-red.json", "sha256": digest}, "red-command")

    def test_driver_derives_outer_timeout_from_registered_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            invocation = Path(tmp)
            (invocation / "preparation-commands.json").write_text(json.dumps([
                {"timeout_seconds": 10},
            ]), encoding="utf-8")
            (invocation / "refactor-commands.json").write_text(json.dumps([
                {"timeout_seconds": 20},
                {"timeout_seconds": 30},
            ]), encoding="utf-8")
            for name, timeout in (
                ("red-command.json", 40),
                ("green-command.json", 50),
                ("terminal-command.json", 60),
            ):
                (invocation / name).write_text(json.dumps({"timeout_seconds": timeout}), encoding="utf-8")
            self.assertEqual(270, DRIVER._lifecycle_timeout_seconds(invocation))


if __name__ == "__main__":
    unittest.main()

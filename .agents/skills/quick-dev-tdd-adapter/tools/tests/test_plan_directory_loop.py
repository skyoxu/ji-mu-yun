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


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROUTER = load("route_plan_directory")
BUILDER = load("build_slice_invocation")
LIFECYCLE = load("run_slice_lifecycle")
CONTROLLER = load("persistent_plan_loop")
with mock.patch.dict(sys.modules, {"route_plan_directory": ROUTER}):
    DRIVER = load("loop_plan_directory")


class PlanDirectoryLoopTests(unittest.TestCase):
    def _plan(self, root: Path, slices: list[dict]) -> Path:
        plan = root / "execution-plans" / "target"
        plan.mkdir(parents=True)
        (plan / "implementation-contract.v1.json").write_text(json.dumps({"plan_id": "target", "slices": slices}), encoding="utf-8")
        return plan

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
            (plan / "plan-state.v1.json").write_text(json.dumps({
                "schema_version": "vdd.plan-state.v2",
                "plan_id": "target",
                "status": "implementation-authorized",
                "authorizes": ["plan-ready", "implementation-authorized"],
            }), encoding="utf-8")

            self.assertEqual("run-slice", ROUTER.route(root, plan)["next_action"])

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

    def test_builder_expands_run_path_and_serializes_base64_context(self) -> None:
        plan = REPOSITORY_ROOT / "execution-plans/2026-07-15-repository-maintenance-tdd-adapter"
        result = BUILDER.build(REPOSITORY_ROOT, plan, "RMAP-S0", "RUN-TEST")
        self.assertIn("logs/tdd-adapter/repository-maintenance-tdd-adapter/RMAP-S0/RUN-TEST", result["terminal"]["argv"])
        self.assertIn("payload_base64", result["run_context"]["implementation_contract"])
        self.assertTrue(__import__("base64").b64decode(result["run_context"]["implementation_contract"]["payload_base64"], validate=True))
        self.assertIsInstance(result["run_context"]["boundaries"]["allowed_write_set"], list)

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

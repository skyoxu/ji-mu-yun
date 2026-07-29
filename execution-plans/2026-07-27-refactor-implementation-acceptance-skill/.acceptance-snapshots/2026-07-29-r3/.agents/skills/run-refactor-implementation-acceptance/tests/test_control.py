from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


class ExecutionControlTests(unittest.TestCase):
    def test_next_action_uses_declared_topology_then_order_then_command_id(self) -> None:
        import execution_control

        actions = [
            {"actionId": "later", "dependsOn": [], "order": 2, "commandId": "z", "activation": True},
            {"actionId": "first", "dependsOn": [], "order": 1, "commandId": "z", "activation": True},
            {"actionId": "blocked", "dependsOn": ["first"], "order": 1, "commandId": "a", "activation": True},
        ]
        self.assertEqual("first", execution_control.next_action(actions, set())["actionId"])

    def test_next_action_projects_inactive_and_external_waiting_without_resuming_them(self) -> None:
        import execution_control

        actions = [
            {"actionId": "bootstrap", "dependsOn": [], "order": 1, "commandId": "bootstrap", "activation": "external"},
            {"actionId": "unused", "dependsOn": [], "order": 2, "commandId": "unused", "activation": False},
        ]
        projection = execution_control.project_action_states(actions, set())
        self.assertEqual("waiting-external", projection["bootstrap"])
        self.assertEqual("not-applicable", projection["unused"])
        with self.assertRaisesRegex(execution_control.ControlError, "ready action"):
            execution_control.next_action(actions, set())

    def test_next_action_rejects_unknown_dependencies_and_order_ties(self) -> None:
        import execution_control

        with self.assertRaisesRegex(execution_control.ControlError, "unknown dependency"):
            execution_control.next_action([{"actionId": "a", "dependsOn": ["missing"], "order": 1, "commandId": "a", "activation": True}], set())
        with self.assertRaisesRegex(execution_control.ControlError, "sorting collision"):
            execution_control.next_action([
                {"actionId": "a", "dependsOn": [], "order": 1, "commandId": "x", "activation": True},
                {"actionId": "b", "dependsOn": [], "order": 1, "commandId": "x", "activation": True},
            ], set())

    def test_controlled_command_emits_hash_bound_process_receipt(self) -> None:
        import tempfile
        import execution_control

        descriptor = {"id": "probe", "executable": sys.executable, "argv": ["-c", "print('ok')"], "cwd": ".", "timeout_seconds": 10, "shell": False, "allowed_write_roots": [], "forbidden_write_roots": [], "registry_hash": "sha256:" + "a" * 64, "environment_allowlist": [], "typed_placeholders": {}, "placeholder_values": {}}
        with tempfile.TemporaryDirectory() as directory:
            receipt = execution_control.run_controlled_command(Path(directory), descriptor)
        self.assertEqual("probe", receipt["commandId"])
        self.assertEqual(0, receipt["exitCode"])
        self.assertTrue(receipt["invocationHash"].startswith("sha256:"))
        self.assertTrue(receipt["processResultHash"].startswith("sha256:"))
        self.assertEqual(descriptor["registry_hash"], receipt["commandRegistryHash"])

    def test_controlled_command_records_timeout_as_closed_failure(self) -> None:
        import tempfile
        import execution_control

        descriptor = {"id": "timeout", "executable": sys.executable, "argv": ["-c", "import time; time.sleep(2)"], "cwd": ".", "timeout_seconds": 1, "shell": False, "allowed_write_roots": [], "forbidden_write_roots": [], "registry_hash": "sha256:" + "a" * 64, "environment_allowlist": [], "typed_placeholders": {}, "placeholder_values": {}}
        with tempfile.TemporaryDirectory() as directory:
            receipt = execution_control.run_controlled_command(Path(directory), descriptor)
        self.assertIsNone(receipt["exitCode"])
        self.assertTrue(receipt["processResult"]["timedOut"])
        self.assertTrue(receipt["processResult"]["processTreeTerminated"])

    def test_receipt_publication_is_append_only(self) -> None:
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            execution_control.publish_receipt(path, {"authorizes": []})
            with self.assertRaisesRegex(execution_control.ControlError, "append-only"):
                execution_control.publish_receipt(path, {"authorizes": []})

    def test_create_run_directory_is_identity_bound_and_append_only(self) -> None:
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = execution_control.create_run_directory(root, "run-001")
            self.assertEqual((root / "run-001").resolve(), run)
            with self.assertRaisesRegex(execution_control.ControlError, "already exists"):
                execution_control.create_run_directory(root, "run-001")
            with self.assertRaises(execution_control.ControlError):
                execution_control.create_run_directory(root, "../escape")

    def test_inspect_run_projects_next_action_without_authorization(self) -> None:
        import execution_control

        inspection = execution_control.inspect_run(
            [{"actionId": "run", "dependsOn": [], "order": 1, "commandId": "check", "activation": True}],
            set(),
        )
        self.assertEqual("run", inspection["nextAction"]["actionId"])
        self.assertEqual("ready", inspection["actionStates"]["run"])
        self.assertEqual([], inspection["authorizes"])
        self.assertEqual(["run"], inspection["readyActionIds"])
        self.assertEqual([], inspection["missingDependencies"]["run"])

    def test_resume_executes_only_the_unique_ready_registered_command(self) -> None:
        import tempfile
        import execution_control

        actions = [{"actionId": "run", "dependsOn": [], "order": 1, "commandId": "probe", "activation": True}]
        registry = {"probe": {"id": "probe", "executable": sys.executable, "argv": ["-c", "print('ok')"], "cwd": ".", "timeout_seconds": 10, "shell": False, "allowed_write_roots": [], "forbidden_write_roots": [], "registry_hash": "sha256:" + "a" * 64, "environment_allowlist": [], "typed_placeholders": {}, "placeholder_values": {}}}
        with tempfile.TemporaryDirectory() as directory:
            result = execution_control.resume_run(Path(directory), actions, set(), registry)
        self.assertEqual("run", result["actionId"])
        self.assertEqual(0, result["receipt"]["exitCode"])
        self.assertEqual([], result["authorizes"])

    def test_cli_exposes_inspect_and_resume_commands(self) -> None:
        import acceptance_cli

        self.assertTrue(callable(acceptance_cli.inspect_run))
        self.assertTrue(callable(acceptance_cli.resume_run))
        self.assertTrue(callable(acceptance_cli.inspect_persisted_run))
        self.assertTrue(callable(acceptance_cli.resume_persisted_run))

    def test_command_descriptor_rejects_shell_execution(self) -> None:
        import execution_control

        with self.assertRaises(execution_control.ControlError):
            execution_control.validate_command_descriptor({"id": "unsafe", "executable": "cmd", "argv": ["/c", "x"], "cwd": ".", "timeout_seconds": 1, "shell": True, "allowed_write_roots": [], "forbidden_write_roots": [], "registry_hash": "sha256:" + "a" * 64, "environment_allowlist": [], "typed_placeholders": {}, "placeholder_values": {}})

    def test_command_descriptor_rejects_untyped_placeholder(self) -> None:
        import execution_control

        descriptor = {"id": "placeholder", "executable": sys.executable, "argv": ["-c", "print('${RUN_DIR}')"], "cwd": ".", "timeout_seconds": 1, "shell": False, "allowed_write_roots": [], "forbidden_write_roots": [], "registry_hash": "sha256:" + "a" * 64, "environment_allowlist": [], "typed_placeholders": {}, "placeholder_values": {}}
        with self.assertRaisesRegex(execution_control.ControlError, "placeholder"):
            execution_control.validate_command_descriptor(descriptor)

    def test_typed_placeholder_resolution_requires_declared_allowed_root(self) -> None:
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "isolated").mkdir()
            argv = execution_control.resolve_typed_argv(
                ["--root", "${DISPOSABLE_ROOT}"],
                {"DISPOSABLE_ROOT": "path:allowed-write-root"},
                {"DISPOSABLE_ROOT": "isolated"},
                root,
                ["isolated/**"],
            )
            self.assertEqual(str((root / "isolated").resolve()), argv[1])
            with self.assertRaisesRegex(execution_control.ControlError, "allowed write root"):
                execution_control.resolve_typed_argv(
                    ["${DISPOSABLE_ROOT}"], {"DISPOSABLE_ROOT": "path:allowed-write-root"},
                    {"DISPOSABLE_ROOT": "outside"}, root, ["isolated/**"],
                )

    def test_write_set_rejects_live_phase_path(self) -> None:
        import execution_control

        with self.assertRaises(execution_control.ControlError):
            execution_control.validate_write_set(["logs/phase-a-innernet/data/x"], ["logs/tdd-adapter/**"], ["logs/phase-a-innernet/**"])

    def test_lock_is_exclusive(self) -> None:
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "run.lock"
            execution_control.acquire_lock(lock, "run-1")
            with self.assertRaises(execution_control.ControlError):
                execution_control.acquire_lock(lock, "run-2")

    def test_persisted_run_reconstructs_action_state_and_rejects_duplicate_terminal_event(self) -> None:
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = execution_control.create_persisted_run(root, "run-001", "sha256:" + "a" * 64, "sha256:" + "b" * 64)
            execution_control.append_action_event(run, {"actionId": "scan", "status": "completed", "commandId": "scan-command"})
            self.assertEqual({"scan"}, execution_control.reconstruct_completed_actions(run))
            with self.assertRaisesRegex(execution_control.ControlError, "duplicate terminal"):
                execution_control.append_action_event(run, {"actionId": "scan", "status": "completed", "commandId": "scan-command"})

    def test_persisted_resume_executes_unique_ready_action_and_records_receipt_event(self) -> None:
        import tempfile
        import execution_control

        actions = [{"actionId": "run", "dependsOn": [], "order": 1, "commandId": "probe", "activation": True}]
        registry = {"probe": {"id": "probe", "executable": sys.executable, "argv": ["-c", "print('ok')"], "cwd": ".", "timeout_seconds": 10, "shell": False, "allowed_write_roots": [], "forbidden_write_roots": [], "registry_hash": "sha256:" + "a" * 64, "environment_allowlist": [], "typed_placeholders": {}, "placeholder_values": {}}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = execution_control.create_persisted_run(root, "run-002", "sha256:" + "a" * 64, "sha256:" + "b" * 64)
            result = execution_control.resume_persisted_run(root, run, actions, registry, "sha256:" + "a" * 64, "sha256:" + "b" * 64)
            self.assertEqual("run", result["actionId"])
            self.assertEqual({"run"}, execution_control.reconstruct_completed_actions(run))
            self.assertIsNone(execution_control.inspect_persisted_run(run, actions, "sha256:" + "a" * 64, "sha256:" + "b" * 64)["nextAction"])
            lifecycle = (run / "acceptance-events.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(3, len(lifecycle))

    def test_persisted_action_claim_is_exclusive_before_command_execution(self) -> None:
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = execution_control.create_persisted_run(root, "run-003", "sha256:" + "a" * 64, "sha256:" + "b" * 64)
            execution_control.claim_persisted_action(run, "scan", "scan-command")
            with self.assertRaisesRegex(execution_control.ControlError, "already claimed"):
                execution_control.claim_persisted_action(run, "scan", "scan-command")

    def test_not_applicable_event_closes_a_dependency_for_persisted_inspection(self) -> None:
        import tempfile
        import execution_control

        actions = [
            {"actionId": "optional", "dependsOn": [], "order": 1, "commandId": "optional-command", "activation": False},
            {"actionId": "followup", "dependsOn": ["optional"], "order": 2, "commandId": "followup-command", "activation": True},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = execution_control.create_persisted_run(root, "run-optional", "sha256:" + "a" * 64, "sha256:" + "b" * 64)
            execution_control.append_action_event(run, {"actionId": "optional", "status": "not_applicable", "commandId": "optional-command"})
            inspection = execution_control.inspect_persisted_run(run, actions, "sha256:" + "a" * 64, "sha256:" + "b" * 64)
            self.assertEqual("followup", inspection["nextAction"]["actionId"])

    def test_write_manifest_rejects_changes_outside_declared_roots(self) -> None:
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "isolated").mkdir()
            before = execution_control.build_write_manifest(root)
            (root / "production.py").write_text("changed\n", encoding="utf-8")
            after = execution_control.build_write_manifest(root)
            with self.assertRaisesRegex(execution_control.ControlError, "write set violates"):
                execution_control.validate_write_manifest_delta(before, after, ["isolated/**"], ["production.py"])

    def test_controlled_command_fails_closed_for_observed_undeclared_write(self) -> None:
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            descriptor = {
                "id": "mutate", "executable": sys.executable,
                "argv": ["-c", "from pathlib import Path; Path('production.py').write_text('x', encoding='utf-8')"],
                "cwd": ".", "timeout_seconds": 10, "shell": False,
                "allowed_write_roots": ["isolated/**"], "forbidden_write_roots": ["production.py"], "registry_hash": "sha256:" + "a" * 64, "environment_allowlist": [], "typed_placeholders": {}, "placeholder_values": {},
            }
            with self.assertRaisesRegex(execution_control.ControlError, "write set violates"):
                execution_control.run_controlled_command(root, descriptor)

    def test_lifecycle_event_creates_immutable_attempt_evidence(self) -> None:
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = execution_control.create_persisted_run(root, "run-events", "sha256:" + "a" * 64, "sha256:" + "b" * 64)
            event = execution_control.record_lifecycle_event(
                run, action_id="scan", attempt_id="attempt-001", action_type="run-command",
                event_type="action-reserved", input_hashes={"runInputHash": "sha256:" + "a" * 64},
                owner_token="owner-001", formal_write_set=["isolated/**"], command_id="scan-command",
            )
            self.assertEqual("action-reserved", event["eventType"])
            self.assertEqual("run-events", event["runId"])
            self.assertTrue((run / "actions" / "scan" / "attempt-001" / "request.json").is_file())
            with self.assertRaisesRegex(execution_control.ControlError, "append-only"):
                execution_control.record_lifecycle_event(
                    run, action_id="scan", attempt_id="attempt-001", action_type="run-command",
                    event_type="action-reserved", input_hashes={"runInputHash": "sha256:" + "a" * 64},
                    owner_token="owner-001", formal_write_set=["isolated/**"], command_id="scan-command",
                )

    def test_stale_recovery_creates_successor_without_overwriting_predecessor(self) -> None:
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            predecessor = execution_control.create_persisted_run(root, "run-004", "sha256:" + "a" * 64, "sha256:" + "b" * 64)
            predecessor_state = (predecessor / "run-state.json").read_bytes()
            successor = execution_control.create_stale_linked_successor(root, "run-005", predecessor, "sha256:" + "c" * 64, "sha256:" + "d" * 64)
            state = json.loads((successor / "run-state.json").read_text(encoding="utf-8"))
            self.assertEqual("run-004", state["predecessorRunId"])
            self.assertEqual(predecessor_state, (predecessor / "run-state.json").read_bytes())
            events = [json.loads(line) for line in (successor / "acceptance-events.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual("run-superseded", events[0]["eventType"])


if __name__ == "__main__":
    unittest.main()

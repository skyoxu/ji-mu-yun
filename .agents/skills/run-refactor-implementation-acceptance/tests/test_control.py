from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock


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

    def test_controlled_command_rejects_duplicate_normalized_input_paths(self) -> None:
        import tempfile
        import execution_control

        descriptor = {"id": "probe", "executable": sys.executable, "argv": ["-c", "print('ok')"], "cwd": ".", "timeout_seconds": 10, "shell": False, "allowed_write_roots": [], "forbidden_write_roots": [], "registry_hash": "sha256:" + "a" * 64, "environment_allowlist": [], "typed_placeholders": {}, "placeholder_values": {}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "input.py").write_text("pass\n", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(execution_control.ControlError, "duplicated"):
                execution_control.run_controlled_command(
                    root, descriptor, input_paths=["src/input.py", "src\\input.py"]
                )

    def test_controlled_command_records_timeout_as_closed_failure(self) -> None:
        import tempfile
        import execution_control

        descriptor = {"id": "timeout", "executable": sys.executable, "argv": ["-c", "import time; time.sleep(2)"], "cwd": ".", "timeout_seconds": 1, "shell": False, "allowed_write_roots": [], "forbidden_write_roots": [], "registry_hash": "sha256:" + "a" * 64, "environment_allowlist": [], "typed_placeholders": {}, "placeholder_values": {}}
        with tempfile.TemporaryDirectory() as directory:
            receipt = execution_control.run_controlled_command(Path(directory), descriptor)
        self.assertIsNone(receipt["exitCode"])
        self.assertTrue(receipt["processResult"]["timedOut"])
        self.assertTrue(receipt["processResult"]["processTreeTerminated"])

    def test_registered_command_rejects_unbound_or_tampered_descriptor(self) -> None:
        import execution_control

        command = {"id": "probe", "executable": sys.executable, "argv": ["-c", "print('ok')"], "cwd": ".", "timeout_seconds": 10, "shell": False, "allowed_write_roots": [], "forbidden_write_roots": [], "registry_hash": "", "environment_allowlist": [], "typed_placeholders": {}, "placeholder_values": {}}
        material = {"schemaVersion": "acceptance-command-registry.v1", "commands": [{key: value for key, value in command.items() if key != "registry_hash"}]}
        registry_hash = execution_control._canonical_hash(material)
        command["registry_hash"] = registry_hash
        registry = {"schemaVersion": "acceptance-command-registry.v1", "commands": [command], "registryHash": registry_hash}
        self.assertEqual(command, execution_control.resolve_registered_command(registry, "probe"))
        command["argv"] = ["-c", "from pathlib import Path; Path(r'C:/outside').write_text('x')"]
        with self.assertRaisesRegex(execution_control.ControlError, "registry hash is stale"):
            execution_control.resolve_registered_command(registry, "probe")

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

    def test_persisted_resume_releases_claim_and_retries_after_controlled_failure(self) -> None:
        import tempfile
        import execution_control

        actions = [{"actionId": "run", "dependsOn": [], "order": 1, "commandId": "probe", "activation": True}]
        failing = {"probe": {"id": "probe", "executable": sys.executable, "argv": ["-c", "from pathlib import Path; Path('production.py').write_text('x', encoding='utf-8')"], "cwd": ".", "timeout_seconds": 10, "shell": False, "allowed_write_roots": ["isolated/**"], "forbidden_write_roots": ["production.py"], "registry_hash": "sha256:" + "a" * 64, "environment_allowlist": [], "typed_placeholders": {}, "placeholder_values": {}}}
        succeeding = {"probe": {"id": "probe", "executable": sys.executable, "argv": ["-c", "print('ok')"], "cwd": ".", "timeout_seconds": 10, "shell": False, "allowed_write_roots": [], "forbidden_write_roots": [], "registry_hash": "sha256:" + "a" * 64, "environment_allowlist": [], "typed_placeholders": {}, "placeholder_values": {}}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = execution_control.create_persisted_run(root, "run-retry", "sha256:" + "a" * 64, "sha256:" + "b" * 64)
            with self.assertRaisesRegex(execution_control.ControlError, "write set violates"):
                execution_control.resume_persisted_run(root, run, actions, failing, "sha256:" + "a" * 64, "sha256:" + "b" * 64)
            self.assertFalse((run / "action-claims" / "run.json").exists())
            retried = execution_control.resume_persisted_run(root, run, actions, succeeding, "sha256:" + "a" * 64, "sha256:" + "b" * 64)
            self.assertEqual("run", retried["actionId"])
            self.assertEqual({"run"}, execution_control.reconstruct_completed_actions(run))
            events = [json.loads(line) for line in (run / "acceptance-events.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(["attempt-001", "attempt-001", "attempt-001", "attempt-002", "attempt-002", "attempt-002"], [event["attemptId"] for event in events])

    def test_plan_owned_legacy_registry_resolves_to_hash_bound_descriptor(self) -> None:
        import execution_control

        registry_path = SKILL_ROOT.parents[2] / "execution-plans" / "2026-07-27-refactor-implementation-acceptance-skill" / "command-registry.v1.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        descriptor = execution_control.resolve_registered_command(registry, "r3-candidate-suite")
        self.assertEqual("r3-candidate-suite", descriptor["id"])
        self.assertTrue(descriptor["registry_hash"].startswith("sha256:"))
        self.assertFalse(descriptor["shell"])
        self.assertIn("TEMP", descriptor["environment_allowlist"])
        self.assertIn("TMP", descriptor["environment_allowlist"])
        self.assertIn("USERNAME", descriptor["environment_allowlist"])
        self.assertIn("USERPROFILE", descriptor["environment_allowlist"])
        self.assertIn("APPDATA", descriptor["environment_allowlist"])
        self.assertIn("PROGRAMFILES", descriptor["environment_allowlist"])
        self.assertIn("PROGRAMFILES(X86)", descriptor["environment_allowlist"])

    def test_persisted_resume_consumes_plan_owned_legacy_registry_directly(self) -> None:
        import subprocess
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            run = execution_control.create_persisted_run(
                root, "run-legacy", "sha256:" + "a" * 64, "sha256:" + "b" * 64
            )
            actions = [{
                "actionId": "probe", "dependsOn": [], "order": 1,
                "commandId": "probe", "activation": True,
            }]
            registry = {
                "schema_version": "ria.command-registry.v1",
                "commands": [{
                    "id": "probe", "executable": sys.executable,
                    "argv": ["-c", "print('ok')"],
                    "cwd": {"type": "repo_path", "value": "."},
                    "timeout_seconds": 10, "shell": False,
                }],
            }

            result = execution_control.resume_persisted_run(
                root, run, actions, registry,
                "sha256:" + "a" * 64, "sha256:" + "b" * 64,
            )

            self.assertEqual(0, result["receipt"]["exitCode"])
            self.assertEqual("completed", result["actionEvent"]["status"])

    def test_cli_resume_persisted_run_propagates_controlled_command_failure(self) -> None:
        import acceptance_cli

        result = {
            "schemaVersion": "acceptance-persisted-resume-result.v1",
            "receipt": {"exitCode": 1},
            "authorizes": [],
        }
        argv = [
            "acceptance_cli.py", "resume-persisted-run",
            "--repository-root", ".", "--run-dir", "run",
            "--actions", "actions.json", "--command-registry", "registry.json",
            "--run-input-hash", "sha256:" + "a" * 64,
            "--contract-hash", "sha256:" + "b" * 64,
        ]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(acceptance_cli, "_read_json", return_value={}),
            mock.patch.object(acceptance_cli, "resume_persisted_run", return_value=result),
        ):
            self.assertEqual(1, acceptance_cli.main())

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

    def test_read_only_command_detects_same_status_dirty_file_rewrite(self) -> None:
        import subprocess
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            dirty = root / "dirty.py"
            dirty.write_text("before\n", encoding="utf-8", newline="\n")
            subprocess.run(["git", "add", "dirty.py"], cwd=root, check=True)
            dirty.write_text("already dirty\n", encoding="utf-8", newline="\n")
            descriptor = {
                "id": "rewrite-dirty", "executable": sys.executable,
                "argv": ["-c", "from pathlib import Path; Path('dirty.py').write_text('after\\n', encoding='utf-8')"],
                "cwd": ".", "timeout_seconds": 10, "shell": False,
                "allowed_write_roots": [], "forbidden_write_roots": [],
                "registry_hash": "sha256:" + "a" * 64, "environment_allowlist": [],
                "typed_placeholders": {}, "placeholder_values": {},
            }
            with self.assertRaisesRegex(execution_control.ControlError, "changed repository bytes"):
                execution_control.run_controlled_command(root, descriptor)

    def test_read_only_command_accepts_existing_tracked_tombstone(self) -> None:
        import subprocess
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            deleted = root / "deleted.py"
            deleted.write_text("before\n", encoding="utf-8", newline="\n")
            subprocess.run(["git", "add", "deleted.py"], cwd=root, check=True)
            deleted.unlink()
            descriptor = {
                "id": "validate-tombstone", "executable": sys.executable,
                "argv": ["-c", "print('ok')"], "cwd": ".", "timeout_seconds": 10,
                "shell": False, "allowed_write_roots": [], "forbidden_write_roots": [],
                "registry_hash": "sha256:" + "a" * 64, "environment_allowlist": [],
                "typed_placeholders": {}, "placeholder_values": {},
            }

            receipt = execution_control.run_controlled_command(root, descriptor)

            self.assertEqual(0, receipt["processResult"]["exitCode"])
            self.assertEqual([], receipt["writeManifestDelta"]["changedPaths"])

    def test_repository_manifest_uses_index_identity_only_for_clean_tracked_files(self) -> None:
        import subprocess
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            clean = root / "clean.py"
            dirty = root / "dirty.py"
            clean.write_text("clean\n", encoding="utf-8", newline="\n")
            dirty.write_text("before\n", encoding="utf-8", newline="\n")
            subprocess.run(["git", "add", "clean.py", "dirty.py"], cwd=root, check=True)
            dirty.write_text("dirty\n", encoding="utf-8", newline="\n")

            original_hash = execution_control._hash_repository_file
            hashed: list[str] = []

            def recording_hash(path: Path) -> str:
                hashed.append(path.name)
                return original_hash(path)

            with mock.patch.object(execution_control, "_hash_repository_file", side_effect=recording_hash):
                manifest = execution_control._repository_content_manifest(root)

            self.assertTrue(manifest["clean.py"].startswith("git-index:100644:"))
            self.assertTrue(manifest["dirty.py"].startswith("sha256:"))
            self.assertEqual(["dirty.py"], hashed)

    def test_repository_manifest_hashes_untracked_and_ignored_log_bytes(self) -> None:
        import hashlib
        import subprocess
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            (root / ".gitignore").write_text("logs/\n", encoding="utf-8", newline="\n")
            subprocess.run(["git", "add", ".gitignore"], cwd=root, check=True)
            untracked = root / "candidate.txt"
            ignored = root / "logs" / "evidence.txt"
            ignored.parent.mkdir()
            untracked.write_bytes(b"candidate\n")
            ignored.write_bytes(b"evidence\n")

            manifest = execution_control._repository_content_manifest(root)

            self.assertEqual("sha256:" + hashlib.sha256(b"candidate\n").hexdigest(), manifest["candidate.txt"])
            self.assertEqual("sha256:" + hashlib.sha256(b"evidence\n").hexdigest(), manifest["logs/evidence.txt"])

    def test_repository_manifest_expands_ignored_nested_repository(self) -> None:
        import hashlib
        import subprocess
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            (root / ".gitignore").write_text("logs/\n", encoding="utf-8", newline="\n")
            subprocess.run(["git", "add", ".gitignore"], cwd=root, check=True)
            nested = root / "logs" / "nested"
            nested.mkdir(parents=True)
            subprocess.run(["git", "init", "--quiet"], cwd=nested, check=True)
            payload = nested / "evidence.txt"
            payload.write_bytes(b"nested evidence\n")

            manifest = execution_control._repository_content_manifest(root)

            self.assertEqual(
                "sha256:" + hashlib.sha256(b"nested evidence\n").hexdigest(),
                manifest["logs/nested/evidence.txt"],
            )

    def test_read_only_command_detects_ignored_evidence_rewrite(self) -> None:
        import subprocess
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            (root / ".gitignore").write_text("logs/\n", encoding="utf-8", newline="\n")
            subprocess.run(["git", "add", ".gitignore"], cwd=root, check=True)
            evidence = root / "logs" / "evidence.txt"
            evidence.parent.mkdir()
            evidence.write_text("before\n", encoding="utf-8", newline="\n")
            descriptor = {
                "id": "rewrite-evidence", "executable": sys.executable,
                "argv": ["-c", "from pathlib import Path; Path('logs/evidence.txt').write_text('after\\n', encoding='utf-8')"],
                "cwd": ".", "timeout_seconds": 10, "shell": False,
                "allowed_write_roots": [], "forbidden_write_roots": [],
                "registry_hash": "sha256:" + "a" * 64, "environment_allowlist": [],
                "typed_placeholders": {}, "placeholder_values": {},
            }

            with self.assertRaisesRegex(execution_control.ControlError, "changed repository bytes"):
                execution_control.run_controlled_command(root, descriptor)

    def test_stale_action_recovery_preserves_attempt_evidence_and_releases_claim(self) -> None:
        import tempfile
        import execution_control

        run_input_hash = "sha256:" + "a" * 64
        contract_hash = "sha256:" + "b" * 64
        context_hash = "sha256:" + "c" * 64
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = execution_control.create_persisted_run(
                root, "run-stale", run_input_hash, contract_hash,
                knowledge_context_hash=context_hash,
            )
            claim = execution_control.claim_persisted_action(run, "validate", "validator")
            lifecycle = {
                "action_id": "validate", "attempt_id": "attempt-001",
                "action_type": "run-command",
                "input_hashes": {
                    "runInputHash": run_input_hash, "contractHash": contract_hash,
                    "knowledgeContextHash": context_hash,
                },
                "owner_token": "owner-run-stale", "formal_write_set": [],
                "command_id": "validator",
            }
            execution_control.record_lifecycle_event(run, event_type="action-reserved", **lifecycle)
            execution_control.record_lifecycle_event(run, event_type="action-started", **lifecycle)
            claim_value = json.loads(claim.read_text(encoding="utf-8"))
            claim_value["claimedUtc"] = "2026-01-01T00:00:00Z"
            claim.write_text(json.dumps(claim_value) + "\n", encoding="utf-8", newline="\n")

            with mock.patch.object(execution_control, "_process_is_running", return_value=False):
                result = execution_control.recover_stale_persisted_action(
                    run, "validate", run_input_hash, contract_hash, context_hash
                )

            self.assertEqual("stale-recovered", result["status"])
            self.assertFalse(claim.exists())
            events = [json.loads(line) for line in (run / "acceptance-events.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual("action-stale", events[-1]["eventType"])
            self.assertTrue((run / "actions" / "validate" / "attempt-001" / "request.json").is_file())

    def test_stale_action_recovery_rejects_a_live_process(self) -> None:
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = execution_control.create_persisted_run(
                root, "run-live", "sha256:" + "a" * 64, "sha256:" + "b" * 64
            )
            claim = execution_control.claim_persisted_action(run, "validate", "validator")
            lifecycle = {
                "action_id": "validate", "attempt_id": "attempt-001",
                "action_type": "run-command",
                "input_hashes": {"runInputHash": "sha256:" + "a" * 64, "contractHash": "sha256:" + "b" * 64},
                "owner_token": "owner-run-live", "formal_write_set": [], "command_id": "validator",
            }
            execution_control.record_lifecycle_event(run, event_type="action-reserved", **lifecycle)
            execution_control.record_lifecycle_event(run, event_type="action-started", **lifecycle)
            claim_value = json.loads(claim.read_text(encoding="utf-8"))
            claim_value["claimedUtc"] = "2026-01-01T00:00:00Z"
            claim.write_text(json.dumps(claim_value) + "\n", encoding="utf-8", newline="\n")

            with mock.patch.object(execution_control, "_process_is_running", return_value=True):
                with self.assertRaisesRegex(execution_control.ControlError, "still running"):
                    execution_control.recover_stale_persisted_action(
                        run, "validate", "sha256:" + "a" * 64, "sha256:" + "b" * 64
                    )
            self.assertTrue(claim.exists())

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

    def test_target_run_entry_creates_then_resumes_the_same_bound_run(self) -> None:
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            target = repository / "execution-plans" / "feature-a"
            target.mkdir(parents=True)
            run_input_hash = "sha256:" + "a" * 64
            contract_hash = "sha256:" + "b" * 64
            knowledge_context_hash = "sha256:" + "c" * 64
            created = execution_control.start_or_resume_target_run(
                repository,
                "execution-plans/feature-a",
                run_input_hash,
                contract_hash,
                knowledge_context_hash,
            )
            self.assertEqual("created", created["disposition"])
            self.assertRegex(created["runId"], r"^acceptance-[a-f0-9]{16}$")
            run_dir = repository / created["runDirectory"]
            state_before = (run_dir / "run-state.json").read_bytes()

            resumed = execution_control.start_or_resume_target_run(
                repository,
                "execution-plans/feature-a",
                run_input_hash,
                contract_hash,
                knowledge_context_hash,
            )
            self.assertEqual("resumed", resumed["disposition"])
            self.assertEqual(created["runDirectory"], resumed["runDirectory"])
            self.assertEqual(state_before, (run_dir / "run-state.json").read_bytes())
            actions = [{
                "actionId": "validate", "dependsOn": [], "order": 1,
                "commandId": "validate", "activation": True,
            }]
            with self.assertRaisesRegex(execution_control.ControlError, "binding is required"):
                execution_control.inspect_persisted_run(
                    run_dir, actions, run_input_hash, contract_hash
                )
            inspection = execution_control.inspect_persisted_run(
                run_dir, actions, run_input_hash, contract_hash, knowledge_context_hash
            )
            self.assertEqual("validate", inspection["nextAction"]["actionId"])
            with self.assertRaisesRegex(execution_control.ControlError, "binding is stale"):
                execution_control.start_or_resume_target_run(
                    repository,
                    "execution-plans/feature-a",
                    "sha256:" + "c" * 64,
                    contract_hash,
                    knowledge_context_hash,
                    run_id=created["runId"],
                )
            with self.assertRaisesRegex(execution_control.ControlError, "knowledge context"):
                execution_control.start_or_resume_target_run(
                    repository,
                    "execution-plans/feature-a",
                    run_input_hash,
                    contract_hash,
                    "sha256:" + "d" * 64,
                    run_id=created["runId"],
                )
            state = json.loads(state_before)
            state["runId"] = "acceptance-wrong-run"
            (run_dir / "run-state.json").write_text(
                json.dumps(state), encoding="utf-8", newline="\n"
            )
            with self.assertRaisesRegex(execution_control.ControlError, "identity is stale"):
                execution_control.start_or_resume_target_run(
                    repository,
                    "execution-plans/feature-a",
                    run_input_hash,
                    contract_hash,
                    knowledge_context_hash,
                )

    def test_target_run_entry_does_not_migrate_legacy_artifact_only_run(self) -> None:
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            target = repository / "execution-plans" / "feature-a"
            legacy = target / "acceptance-runs" / "legacy-run"
            legacy.mkdir(parents=True)
            marker = legacy / "historical-evidence.json"
            marker.write_text("{}\n", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(execution_control.ControlError, "legacy artifact-only"):
                execution_control.start_or_resume_target_run(
                    repository,
                    "execution-plans/feature-a",
                    "sha256:" + "a" * 64,
                    "sha256:" + "b" * 64,
                    "sha256:" + "c" * 64,
                    run_id="legacy-run",
                )
            self.assertEqual(b"{}\n", marker.read_bytes())

    def test_stale_successor_preserves_the_knowledge_context_binding(self) -> None:
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            knowledge_context_hash = "sha256:" + "c" * 64
            predecessor = execution_control.create_persisted_run(
                root,
                "run-bound",
                "sha256:" + "a" * 64,
                "sha256:" + "b" * 64,
                knowledge_context_hash=knowledge_context_hash,
            )
            successor = execution_control.create_stale_linked_successor(
                root,
                "run-successor",
                predecessor,
                "sha256:" + "d" * 64,
                "sha256:" + "e" * 64,
            )
            state = json.loads((successor / "run-state.json").read_text(encoding="utf-8"))
            self.assertEqual(knowledge_context_hash, state["knowledgeContextHash"])
            event = json.loads(
                (successor / "acceptance-events.jsonl").read_text(encoding="utf-8").strip()
            )
            self.assertEqual(
                knowledge_context_hash, event["inputHashes"]["knowledgeContextHash"]
            )

    def test_target_run_entry_rejects_non_plan_directories(self) -> None:
        import tempfile
        import execution_control

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            (repository / "docs").mkdir(parents=True)
            with self.assertRaisesRegex(execution_control.ControlError, "execution-plans"):
                execution_control.start_or_resume_target_run(
                    repository,
                    "docs",
                    "sha256:" + "a" * 64,
                    "sha256:" + "b" * 64,
                    "sha256:" + "c" * 64,
                )


if __name__ == "__main__":
    unittest.main()

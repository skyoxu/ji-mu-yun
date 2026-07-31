from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


class PackageTests(unittest.TestCase):
    def test_package_validator_requires_all_slice_modules(self) -> None:
        import package_validation

        self.assertEqual([], package_validation.validate_package(SKILL_ROOT))

    def test_fixture_catalog_covers_required_execution_contexts(self) -> None:
        import package_validation

        fixture = json.loads((SKILL_ROOT / "fixtures" / "negative-cases.v1.json").read_text(encoding="utf-8"))
        self.assertEqual([], package_validation.validate_fixture_catalog(fixture))
        fixture["categories"].remove("fresh-context")
        self.assertIn("missing-fixture-category:fresh-context", package_validation.validate_fixture_catalog(fixture))

    def test_cli_exposes_required_workflow_transitions(self) -> None:
        expected = {
            "prepare", "resolve-code-review-policy", "inventory", "audit-task-checklist",
            "audit-repair-completeness",
            "collect-evidence", "run-command", "run-static-analysis", "run-security-scan",
            "analyze-diff-coverage", "evaluate", "render", "decide-bootstrap",
            "bind-bootstrap-capabilities", "prepare-attestation", "prepare-bootstrap",
            "import-bootstrap-launch-authorization", "import-bootstrap", "map-findings",
            "import-mapping-approval", "project-acceptance-impact", "finalize", "inspect-run", "resume",
            "route-acceptance", "start-or-resume",
        }
        result = subprocess.run(
            [sys.executable, "-B", str(SKILL_ROOT / "scripts" / "acceptance_cli.py"), "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(all(command in result.stdout for command in expected))

    def test_registered_bootstrap_import_commands_consume_requests_and_publish_outputs(self) -> None:
        hashes = {name: "sha256:" + character * 64 for name, character in {
            "decisionHash": "a", "bindingHash": "b", "launchAuthorizationHash": "c", "localReceiptHash": "d",
            "reviewInputHash": "e", "artifactViewHash": "f", "roleBundleHash": "0", "attestationHash": "1",
            "candidateHash": "2", "baseMatrixHash": "3", "findingPolicyHash": "4", "profileHash": "5",
            "policyHash": "6", "routeHash": "7", "companionSchemaHash": "8", "finalResultHash": "9",
            "verifierHash": "a", "p2DispositionsHash": "b",
        }.items()}
        requests = {
            "import-bootstrap": {"repositoryRoot": ".", "bootstrapRunDir": "missing-run", "binding": {}, "scope": {}},
            "map-findings": {"mapping": {"schemaVersion": "bootstrap-finding-acceptance-map.v1", "findingId": "F-1", "findingHash": "sha256:" + "a" * 64, "mappingKind": "check", "checkId": "RA-SKILL-001", "authorizes": []}, "liveCheckIds": ["RA-SKILL-001"], "tombstonedCheckIds": []},
            "import-mapping-approval": {"approval": {"schemaVersion": "bootstrap-finding-mapping-approval.v1", "approverRole": "acceptance_owner", "identityEvidenceHash": "sha256:" + "a" * 64, "expiresAtUtc": "2099-01-01T00:00:00Z", "findingHash": "sha256:" + "b" * 64, "mappingHash": "sha256:" + "c" * 64, "matrixHash": "sha256:" + "d" * 64, "lineageHash": "sha256:" + "e" * 64, "importEnvelopeHash": "sha256:" + "f" * 64, "authorizes": []}, "requiredApproverRole": "acceptance_owner", "findingHash": "sha256:" + "b" * 64, "matrixHash": "sha256:" + "d" * 64, "lineageHash": "sha256:" + "e" * 64, "importEnvelopeHash": "sha256:" + "f" * 64},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command, request in requests.items():
                request_path, output_path = root / f"{command}.request.json", root / f"{command}.out.json"
                request_path.write_text(json.dumps(request), encoding="utf-8")
                result = subprocess.run([sys.executable, "-B", str(SKILL_ROOT / "scripts" / "acceptance_cli.py"), command, "--request", str(request_path), "--out", str(output_path)], capture_output=True, text=True, encoding="utf-8", check=False)
                if command == "import-bootstrap":
                    self.assertNotEqual(0, result.returncode)
                    self.assertFalse(output_path.exists())
                else:
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertTrue(output_path.is_file(), command)

    def test_registered_bootstrap_import_command_rejects_missing_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing, output = Path(directory) / "missing.json", Path(directory) / "out.json"
            result = subprocess.run([sys.executable, "-B", str(SKILL_ROOT / "scripts" / "acceptance_cli.py"), "import-bootstrap", "--request", str(missing), "--out", str(output)], capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(output.exists())

    def test_route_acceptance_is_the_prepare_bootstrap_thin_alias(self) -> None:
        request = {
            "decision": {"requirement": "not_required"},
            "binding": None,
            "launch_authorization": None,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = root / "route.request.json"
            output_path = root / "route.v1.json"
            request_path.write_text(json.dumps(request), encoding="utf-8", newline="\n")
            result = subprocess.run(
                [
                    sys.executable, "-B", str(SKILL_ROOT / "scripts" / "acceptance_cli.py"),
                    "route-acceptance", "--request", str(request_path), "--out", str(output_path),
                ],
                capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            route = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual("deterministic_only", route["routeKind"])
            self.assertEqual("deterministic-only-evaluation", route["nextAction"])

            injected_path = root / "injected.request.json"
            injected_output = root / "injected-route.v1.json"
            injected_path.write_text(
                json.dumps({**request, "review_history_baseline": "logs/baseline.json"}),
                encoding="utf-8",
                newline="\n",
            )
            rejected = subprocess.run(
                [
                    sys.executable, "-B", str(SKILL_ROOT / "scripts" / "acceptance_cli.py"),
                    "route-acceptance", "--request", str(injected_path), "--out", str(injected_output),
                ],
                capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertNotEqual(0, rejected.returncode)
            self.assertFalse(injected_output.exists())

            help_result = subprocess.run(
                [
                    sys.executable, "-B", str(SKILL_ROOT / "scripts" / "acceptance_cli.py"),
                    "route-acceptance", "--help",
                ],
                capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(0, help_result.returncode, help_result.stderr)
            self.assertIn("route-acceptance", help_result.stdout)

    def test_start_or_resume_cli_allocates_and_reuses_the_bound_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            (repository / "execution-plans" / "feature-a").mkdir(parents=True)
            command = [
                sys.executable, "-B", str(SKILL_ROOT / "scripts" / "acceptance_cli.py"),
                "start-or-resume", "--repository-root", str(repository),
                "--target-plan", "execution-plans/feature-a",
                "--run-input-hash", "sha256:" + "a" * 64,
                "--contract-hash", "sha256:" + "b" * 64,
                "--knowledge-context-hash", "sha256:" + "c" * 64,
            ]
            created = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8", check=False
            )
            self.assertEqual(0, created.returncode, created.stderr)
            created_value = json.loads(created.stdout)
            self.assertEqual("created", created_value["disposition"])
            run_dir = repository / created_value["runDirectory"]
            self.assertTrue((run_dir / "run-state.json").is_file())

            resumed = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8", check=False
            )
            self.assertEqual(0, resumed.returncode, resumed.stderr)
            self.assertEqual("resumed", json.loads(resumed.stdout)["disposition"])

            actions = Path(directory) / "actions.json"
            actions.write_text(
                json.dumps([{
                    "actionId": "validate", "dependsOn": [], "order": 1,
                    "commandId": "validate", "activation": True,
                }]),
                encoding="utf-8",
                newline="\n",
            )
            inspect_command = [
                sys.executable, "-B", str(SKILL_ROOT / "scripts" / "acceptance_cli.py"),
                "inspect-persisted-run", "--run-dir", str(run_dir),
                "--actions", str(actions), "--run-input-hash", "sha256:" + "a" * 64,
                "--contract-hash", "sha256:" + "b" * 64,
            ]
            missing_context = subprocess.run(
                inspect_command, capture_output=True, text=True, encoding="utf-8", check=False
            )
            self.assertNotEqual(0, missing_context.returncode)
            inspected = subprocess.run(
                inspect_command + ["--knowledge-context-hash", "sha256:" + "c" * 64],
                capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(0, inspected.returncode, inspected.stderr)


if __name__ == "__main__":
    unittest.main()

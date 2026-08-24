from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
TEST_SUPPORT = SKILL_ROOT.parents[2] / "scripts" / "python" / "tests"
if str(TEST_SUPPORT) not in sys.path:
    sys.path.insert(0, str(TEST_SUPPORT))

from skill_input_composition_support import publish_ready_receipt  # noqa: E402


class PackageTests(unittest.TestCase):
    def test_start_or_resume_consumes_real_ready_skill_input_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            plan = repository / "execution-plans" / "feature-a"
            plan.mkdir(parents=True)
            implementation = plan / "implementation.py"
            requirements = plan / "acceptance.md"
            implementation.write_text("VALUE = 1\n", encoding="utf-8", newline="\n")
            requirements.write_text("# Acceptance\n", encoding="utf-8", newline="\n")
            artifacts = publish_ready_receipt(
                repository,
                consumer="run-refactor-implementation-acceptance",
                operation="acceptance",
                target="execution-plans/feature-a",
                role_paths={
                    "implementation_target": ["execution-plans/feature-a/implementation.py"],
                    "acceptance_requirements": ["execution-plans/feature-a/acceptance.md"],
                },
            )
            command = [
                sys.executable, "-B", str(SKILL_ROOT / "scripts" / "acceptance_cli.py"),
                "start-or-resume", "--repository-root", str(repository),
                "--target-plan", "execution-plans/feature-a",
                "--run-input-hash", "sha256:" + "a" * 64,
                "--contract-hash", "sha256:" + "b" * 64,
                "--knowledge-context-hash", "sha256:" + "c" * 64,
                "--skill-input-receipt", str(artifacts["receipt"]),
                "--skill-input-contract", str(artifacts["contract"]),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(0, completed.returncode, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(
                artifacts["context"].resolve().relative_to(repository.resolve()).as_posix(),
                result["skillInputContextSourcePath"],
            )
            state = json.loads((repository / result["runDirectory"] / "run-state.json").read_text(encoding="utf-8"))
            custody = repository / result["skillInputContextPath"]
            self.assertTrue(custody.is_file())
            self.assertEqual(state["skillInputContextPath"], custody.relative_to(repository / result["runDirectory"]).as_posix())

    def test_start_or_resume_blocks_missing_wrong_and_stale_ready_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repo"
            plan = repository / "execution-plans" / "feature-a"
            plan.mkdir(parents=True)
            implementation = plan / "implementation.py"
            requirements = plan / "acceptance.md"
            implementation.write_text("VALUE = 1\n", encoding="utf-8", newline="\n")
            requirements.write_text("# Acceptance\n", encoding="utf-8", newline="\n")
            artifacts = publish_ready_receipt(
                repository,
                consumer="run-refactor-implementation-acceptance",
                operation="acceptance",
                target="execution-plans/feature-a",
                role_paths={
                    "implementation_target": ["execution-plans/feature-a/implementation.py"],
                    "acceptance_requirements": ["execution-plans/feature-a/acceptance.md"],
                },
            )

            def invoke(receipt_path: Path, contract_path: Path) -> subprocess.CompletedProcess[str]:
                return subprocess.run([
                    sys.executable, "-B", str(SKILL_ROOT / "scripts" / "acceptance_cli.py"),
                    "start-or-resume", "--repository-root", str(repository),
                    "--target-plan", "execution-plans/feature-a",
                    "--run-input-hash", "sha256:" + "a" * 64,
                    "--contract-hash", "sha256:" + "b" * 64,
                    "--knowledge-context-hash", "sha256:" + "c" * 64,
                    "--skill-input-receipt", str(receipt_path),
                    "--skill-input-contract", str(contract_path),
                ], capture_output=True, text=True, encoding="utf-8", check=False)

            self.assertNotEqual(0, invoke(repository / "missing.json", artifacts["contract"]).returncode)
            self.assertNotEqual(
                0,
                invoke(artifacts["candidate_receipt"], artifacts["contract"]).returncode,
            )
            wrong = publish_ready_receipt(
                repository,
                consumer="wrong-acceptance-consumer",
                operation="acceptance",
                target="execution-plans/feature-a",
                role_paths={
                    "implementation_target": ["execution-plans/feature-a/implementation.py"],
                    "acceptance_requirements": ["execution-plans/feature-a/acceptance.md"],
                },
                protocol_name=".skill-input-composition-wrong",
            )
            self.assertNotEqual(0, invoke(wrong["receipt"], wrong["contract"]).returncode)
            implementation.write_text("VALUE = 2\n", encoding="utf-8", newline="\n")
            self.assertNotEqual(0, invoke(artifacts["receipt"], artifacts["contract"]).returncode)

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
            "decline-review-reentry",
            "prepare-manual-pause-closure", "finalize-manual-pause-closure",
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
        import acceptance_cli
        from review_requirement import decide_review_requirement

        policy = json.loads((SKILL_ROOT / "policies" / "semantic-review-trigger-policy.v1.json").read_text(encoding="utf-8"))
        request = {
            "decision": decide_review_requirement({
                "candidateIdentity": {"changedPaths": ["docs/ordinary-note.md"], "knowledgeArtifacts": []},
                "deterministicEvidence": {"status": "passed", "hash": "sha256:" + "a" * 64},
                "policy": policy,
            }),
            "decision_request": {
                "repository_root": ".",
                "prepared_run_input": "prepared.json",
                "deterministic_evidence": {
                    "path": "evidence.json",
                    "sha256": "sha256:" + "a" * 64,
                },
                "maintainer_intent": "default",
            },
            "binding": None,
            "launch_authorization=<redacted>,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = root / "route.request.json"
            output_path = root / "route.v1.json"
            request_path.write_text(json.dumps(request), encoding="utf-8", newline="\n")
            with mock.patch.object(
                acceptance_cli,
                "_derive_current_bootstrap_decision",
                return_value=request["decision"],
            ):
                route = acceptance_cli.prepare_bootstrap_command(
                    str(request_path), str(output_path)
                )
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

    def test_start_or_resume_cli_requires_skill_input_receipt(self) -> None:
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
            self.assertNotEqual(0, created.returncode)
            self.assertIn("--skill-input-receipt", created.stderr)
            self.assertFalse((repository / "execution-plans" / "feature-a" / "acceptance-runs").exists())


if __name__ == "__main__":
    unittest.main()

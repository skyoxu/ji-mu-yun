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


if __name__ == "__main__":
    unittest.main()

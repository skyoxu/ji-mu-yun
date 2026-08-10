import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PYTHON_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PYTHON_ROOT))

from prepare_skill_input_consumption import prepare  # noqa: E402
from skill_input_consumption import SkillInputError, redact_bytes, sha256_bytes  # noqa: E402
from validate_skill_input_consumption import ReceiptValidationError, publish_ready, validate_receipt  # noqa: E402
from launch_skill_input_consumer import ChildRequestError, run_semantic_child, validate_child_request  # noqa: E402
from skill_input_gate import require_ready_skill_input  # noqa: E402


class SkillInputConsumptionTests(unittest.TestCase):
    def _fixture(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=root, check=True)
        basis = root / "budget.txt"
        source = root / "requirements.md"
        basis.write_text("fixture\n", encoding="utf-8")
        source.write_text("token: abc\nRequirement text\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
        contract = {
            "schema_version": "skill-input-contract.v1",
            "consumer": "demo-skill",
            "mode": "strict",
            "trigger": "test",
            "source_roles": {"requirements": {"selector": "requirements", "required": True, "root": "repository", "allowed_kinds": ["file"], "reference_kinds": []}},
            "operations": {"create": {"required_inputs": ["requirements"]}},
            "reference_policy": "declared-in-root-and-contained",
            "max_reference_depth": 4,
            "max_sources": 10,
            "max_context_bytes": 512,
            "budget_basis": {"path": "budget.txt", "sha256": sha256_bytes(basis.read_bytes())},
            "sensitivity_policy": "deny-credential-values",
            "redaction_profile": "credential-values-v1",
            "forbidden_sources": ["logs-as-recovery-source"],
            "semantic_acceptance": "all-required-inputs-are-sufficient",
        }
        contract_path = root / "contract.json"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        receipt = root / "run" / "receipt.json"
        args = argparse.Namespace(repository_root=root, contract=contract_path, consumer="demo-skill", operation="create", route_identity="test-route", target="requirements.md", source_role=["requirements=requirements.md"], request_json=None, snapshot_root=root / "run" / "snapshot", receipt=receipt)
        return temporary, root, contract_path, receipt, args

    def test_candidate_receipt_validates_and_redacts(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        result = validate_receipt(receipt, root, contract)
        self.assertEqual("candidate", result["status"])
        safe = (root / "run" / "snapshot" / "requirements.md").read_text(encoding="utf-8")
        self.assertNotIn("abc", safe)

    def test_bearer_token_redaction_removes_complete_credential(self):
        redacted, sensitivity, status = redact_bytes(b"Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.secret.payload\n")
        self.assertEqual("credential-bearing", sensitivity)
        self.assertEqual("complete", status)
        self.assertNotIn(b"eyJhbGciOiJIUzI1NiJ9.secret.payload", redacted)

    def test_multiword_secret_redaction_removes_complete_value(self):
        redacted, _sensitivity, _status = redact_bytes(b'password: "correct horse battery staple"\n')
        self.assertEqual(b"password=<redacted>\n", redacted)

    def test_source_drift_fails_closed(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        (root / "requirements.md").write_text("changed\n", encoding="utf-8")
        with self.assertRaises(ReceiptValidationError):
            validate_receipt(receipt, root, contract)

    def test_missing_required_role_is_rejected(self):
        temporary, _root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        args.source_role = []
        with self.assertRaises(SkillInputError):
            prepare(args)

    def test_ready_requires_sidecars(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        payload["ready"] = True
        receipt.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(ReceiptValidationError):
            validate_receipt(receipt, root, contract, require_ready=True)

    def test_child_request_is_bound_to_snapshot_manifest(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        request = {
            "schema_version": "skill-input-child-request.v1",
            "consumer": "demo-skill",
            "operation": "create",
            "contract_hash": payload["contract_hash"],
            "source_manifest_hash": payload["source_manifest"]["sha256"],
            "snapshot_root": "run/snapshot",
            "output_root": "run/output",
            "execution_identity": "sha256:" + "1" * 64,
            "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"],
            "authorizes": [],
        }
        result = validate_child_request(request, root, payload["contract_hash"], request["execution_identity"])
        self.assertEqual("validated", result["status"])
        self.assertTrue((root / "run" / "output").is_dir())
        request["allowed_capabilities"] = ["read-frozen-snapshot", "run-shell"]
        with self.assertRaises(ChildRequestError):
            validate_child_request(request, root)

    def test_publish_ready_binds_sidecars_and_recomputes_gate(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        source_path = payload["sources"][0]["path"]
        decision = root / "run" / "semantic-decision.v1.json"
        context = root / "run" / "skill-input-context.v1.json"
        context.write_text(json.dumps({"schema_version": "skill-input-context.v1", "source_manifest_hash": payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "Requirement text"}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"}), encoding="utf-8")
        context_hash = sha256_bytes(context.read_bytes())
        decision.write_text(json.dumps({"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": "sha256:" + "1" * 64, "source_manifest_hash": payload["source_manifest"]["sha256"], "context_artifact_hash": context_hash, "source_statuses": {source_path: "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": "sha256:" + "2" * 64, "authorizes": []}), encoding="utf-8")
        publish_ready(receipt, decision, context)
        self.assertEqual("ready", validate_receipt(receipt, root, contract, require_ready=True)["status"])
        gated = require_ready_skill_input(receipt_path=receipt, repository_root=root, contract_path=contract, consumer="demo-skill", operation="create")
        self.assertEqual(context.resolve(), gated["context_artifact"])
        with self.assertRaises(ValueError):
            require_ready_skill_input(receipt_path=receipt, repository_root=root, contract_path=contract, consumer="other-skill", operation="create")

    def test_semantic_child_runner_is_typed_and_isolated(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        request = {
            "schema_version": "skill-input-child-request.v1", "consumer": "demo-skill", "operation": "create",
            "contract_hash": payload["contract_hash"], "source_manifest_hash": payload["source_manifest"]["sha256"],
            "snapshot_root": "run/snapshot", "output_root": "run/output", "execution_identity": "sha256:" + "1" * 64,
            "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"], "authorizes": [],
        }

        def fake_runner(**kwargs):
            output = {
                "context": {"schema_version": "skill-input-context.v1", "source_manifest_hash": payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "Requirement text"}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"},
                "decision": {"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": request["execution_identity"], "source_manifest_hash": payload["source_manifest"]["sha256"], "context_artifact_hash": "sha256:" + "0" * 64, "source_statuses": {"requirements.md": "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": "sha256:" + "2" * 64, "authorizes": []},
            }
            kwargs["output_last_message"].write_text(json.dumps(output), encoding="utf-8")
            return 0, "", ["fake"]

        result = run_semantic_child(request, root, backend="codex-cli", model="test-model", runner=fake_runner)
        self.assertEqual("complete", result["status"])
        self.assertTrue(Path(result["context_artifact"]).is_file())
        self.assertTrue(Path(result["semantic_decision"]).is_file())


if __name__ == "__main__":
    unittest.main()

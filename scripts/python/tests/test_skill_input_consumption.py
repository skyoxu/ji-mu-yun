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
from skill_input_consumption import SkillInputError, canonical_hash, redact_bytes, sha256_bytes, validate_contract, write_json_atomic  # noqa: E402
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

    def test_unknown_contract_field_is_rejected(self):
        temporary, root, contract, _receipt, _args = self._fixture()
        self.addCleanup(temporary.cleanup)
        payload = json.loads(contract.read_text(encoding="utf-8"))
        payload["unknown"] = True
        with self.assertRaisesRegex(SkillInputError, "unknown fields"):
            validate_contract(payload, root)

    def test_declared_markdown_reference_is_added_to_source_graph(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        contract_payload["source_roles"]["requirements"]["reference_kinds"] = ["markdown-link"]
        contract.write_text(json.dumps(contract_payload), encoding="utf-8")
        (root / "requirements.md").write_text("[Details](referenced.md)\n", encoding="utf-8")
        (root / "referenced.md").write_text("Referenced requirement\n", encoding="utf-8")
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual({"requirements.md", "referenced.md"}, {item["path"] for item in payload["sources"]})

    def test_declared_json_path_fields_support_camel_and_snake_case_without_treating_target_as_path(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        contract_payload["source_roles"]["requirements"]["reference_kinds"] = ["json-path-field"]
        contract.write_text(json.dumps(contract_payload), encoding="utf-8")
        (root / "requirements.md").unlink()
        (root / "requirements.json").write_text(
            json.dumps({
                "target": "semantic-label",
                "profile": "self-hosted",
                "evidenceDirectory": "preflight",
                "ownedPaths": ["src/**"],
                "knowledgeContextPath": "context.json",
                "changed_paths": ["details.md"],
            }),
            encoding="utf-8",
        )
        (root / "context.json").write_text("{}\n", encoding="utf-8")
        (root / "details.md").write_text("Details\n", encoding="utf-8")
        args.target = "requirements.json"
        args.source_role = ["requirements=requirements.json"]
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(
            {"requirements.json", "context.json", "details.md"},
            {item["path"] for item in payload["sources"]},
        )

    def test_directory_json_reference_can_resolve_from_declared_input_root(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        contract_payload["source_roles"]["requirements"]["allowed_kinds"] = ["directory"]
        contract_payload["source_roles"]["requirements"]["reference_kinds"] = ["json-path-field"]
        contract.write_text(json.dumps(contract_payload), encoding="utf-8")
        plan = root / "plan"
        (plan / "nested").mkdir(parents=True)
        (plan / "details.md").write_text("Details\n", encoding="utf-8")
        (root / "external.json").write_text(
            json.dumps({"historicalPath": "missing-history.md"}), encoding="utf-8"
        )
        (plan / "nested" / "bundle.json").write_text(
            json.dumps({"reportFilename": ["details.md", "../../external.json"]}), encoding="utf-8"
        )
        args.target = "plan"
        args.source_role = ["requirements=plan"]
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(
            {"plan/details.md", "plan/nested/bundle.json", "external.json"},
            {item["path"] for item in payload["sources"]},
        )

    def test_reference_cycle_is_rejected(self):
        temporary, root, contract, _receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        contract_payload["source_roles"]["requirements"]["reference_kinds"] = ["markdown-link"]
        contract.write_text(json.dumps(contract_payload), encoding="utf-8")
        (root / "requirements.md").write_text("[Details](referenced.md)\n", encoding="utf-8")
        (root / "referenced.md").write_text("[Back](requirements.md)\n", encoding="utf-8")
        with self.assertRaisesRegex(SkillInputError, "reference cycle"):
            prepare(args)

    def test_external_markdown_reference_with_query_is_rejected(self):
        temporary, root, contract, _receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        contract_payload["source_roles"]["requirements"]["reference_kinds"] = ["markdown-link"]
        contract.write_text(json.dumps(contract_payload), encoding="utf-8")
        (root / "requirements.md").write_text(
            "[External](https://example.invalid/spec?version=1)\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(SkillInputError, "external reference"):
            prepare(args)

    def test_request_binding_cannot_drop_required_source_roles(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        payload["request_binding"]["source_roles"] = {}
        payload["request_hash"] = canonical_hash(payload["request_binding"])
        payload["binding_hash"] = canonical_hash({key: value for key, value in payload.items() if key != "binding_hash"})
        receipt.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ReceiptValidationError, "required source role"):
            validate_receipt(receipt, root, contract)

    def test_nested_logs_receipt_path_is_rejected(self):
        temporary, root, _contract, _receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        args.receipt = root / "logs" / "nested" / "receipt.json"
        with self.assertRaisesRegex(SkillInputError, "under logs"):
            prepare(args)

    def test_atomic_writer_rejects_unbound_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            write_json_atomic(path, {"value": 1})
            write_json_atomic(path, {"value": 1})
            with self.assertRaisesRegex(SkillInputError, "not absent or byte-identical"):
                write_json_atomic(path, {"value": 2})

    def test_prepare_does_not_overwrite_snapshot_from_another_binding(self):
        temporary, root, _contract, _receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        destination = root / "run" / "snapshot" / "requirements.md"
        destination.parent.mkdir(parents=True)
        destination.write_text("another binding\n", encoding="utf-8")
        with self.assertRaisesRegex(SkillInputError, "not absent or byte-identical"):
            prepare(args)
        self.assertEqual("another binding\n", destination.read_text(encoding="utf-8"))

    def test_request_binding_rejects_credentials_and_absolute_machine_paths(self):
        temporary, root, _contract, _receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        request = root / "request.json"
        request.write_text(json.dumps({"token": "secret-value"}), encoding="utf-8")
        args.request_json = request
        with self.assertRaisesRegex(SkillInputError, "credential material"):
            prepare(args)
        request.write_text(json.dumps({"working_directory": "C:\\private\\task"}), encoding="utf-8")
        with self.assertRaisesRegex(SkillInputError, "absolute machine path"):
            prepare(args)

    def test_repository_identity_drift_fails_closed(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        subprocess.run(["git", "commit", "--allow-empty", "-qm", "identity drift"], cwd=root, check=True)
        with self.assertRaisesRegex(ReceiptValidationError, "repository identity is stale"):
            validate_receipt(receipt, root, contract)

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
            "max_context_bytes": 512,
            "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"],
            "authorizes": [],
        }
        result = validate_child_request(request, root, payload["contract_hash"], request["execution_identity"])
        self.assertEqual("validated", result["status"])
        self.assertTrue((root / "run" / "output").is_dir())
        request["operation"] = "repair"
        with self.assertRaisesRegex(ChildRequestError, "manifest consumer or operation"):
            validate_child_request(request, root)
        request["operation"] = "create"
        request["allowed_capabilities"] = ["read-frozen-snapshot", "run-shell"]
        with self.assertRaises(ChildRequestError):
            validate_child_request(request, root)

    def test_publish_ready_binds_sidecars_and_recomputes_gate(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        source_path = payload["sources"][0]["path"]
        output_root = root / "run" / "output"
        output_root.mkdir()
        child_request = root / "run" / "skill-input-child-request.v1.json"
        child_request.write_text(json.dumps({
            "schema_version": "skill-input-child-request.v1", "consumer": "demo-skill", "operation": "create",
            "contract_hash": payload["contract_hash"], "source_manifest_hash": payload["source_manifest"]["sha256"],
            "snapshot_root": "run/snapshot", "output_root": "run/output", "execution_identity": "sha256:" + "1" * 64,
            "max_context_bytes": 512, "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"], "authorizes": [],
        }), encoding="utf-8")
        decision = output_root / "semantic-decision.v1.json"
        context = output_root / "skill-input-context.v1.json"
        context.write_text(json.dumps({"schema_version": "skill-input-context.v1", "source_manifest_hash": payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "Requirement text"}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"}), encoding="utf-8")
        context_hash = sha256_bytes(context.read_bytes())
        decision.write_text(json.dumps({"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": "sha256:" + "1" * 64, "source_manifest_hash": payload["source_manifest"]["sha256"], "context_artifact_hash": context_hash, "source_statuses": {source_path: "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": "sha256:" + "2" * 64, "authorizes": []}), encoding="utf-8")
        publish_ready(receipt, child_request, decision, context, root, contract)
        self.assertFalse((root / "run" / "snapshot" / "requirements.md").exists())
        self.assertEqual("ready", validate_receipt(receipt, root, contract, require_ready=True)["status"])
        gated = require_ready_skill_input(receipt_path=receipt, repository_root=root, contract_path=contract, consumer="demo-skill", operation="create")
        self.assertEqual(context.resolve(), gated["context_artifact"])
        self.assertEqual(sha256_bytes(context.read_bytes()), gated["context_artifact_hash"])
        with self.assertRaises(ValueError):
            require_ready_skill_input(receipt_path=receipt, repository_root=root, contract_path=contract, consumer="other-skill", operation="create")

    def test_oversized_context_artifact_fails_closed(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        source_path = payload["sources"][0]["path"]
        output_root = root / "run" / "output"
        output_root.mkdir()
        child_request = root / "run" / "skill-input-child-request.v1.json"
        child_request.write_text(json.dumps({
            "schema_version": "skill-input-child-request.v1", "consumer": "demo-skill", "operation": "create",
            "contract_hash": payload["contract_hash"], "source_manifest_hash": payload["source_manifest"]["sha256"],
            "snapshot_root": "run/snapshot", "output_root": "run/output", "execution_identity": "sha256:" + "1" * 64,
            "max_context_bytes": 512, "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"], "authorizes": [],
        }), encoding="utf-8")
        decision = output_root / "semantic-decision.v1.json"
        context = output_root / "skill-input-context.v1.json"
        context.write_text(json.dumps({"schema_version": "skill-input-context.v1", "source_manifest_hash": payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "x" * 2000}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"}), encoding="utf-8")
        context_hash = sha256_bytes(context.read_bytes())
        decision.write_text(json.dumps({"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": "sha256:" + "1" * 64, "source_manifest_hash": payload["source_manifest"]["sha256"], "context_artifact_hash": context_hash, "source_statuses": {source_path: "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": "sha256:" + "2" * 64, "authorizes": []}), encoding="utf-8")
        candidate_bytes = receipt.read_bytes()
        with self.assertRaisesRegex(ReceiptValidationError, "max_context_bytes"):
            publish_ready(receipt, child_request, decision, context, root, contract)
        self.assertEqual(candidate_bytes, receipt.read_bytes())
        self.assertEqual("candidate", validate_receipt(receipt, root, contract)["status"])

    def test_semantic_child_runner_is_typed_and_isolated(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        request = {
            "schema_version": "skill-input-child-request.v1", "consumer": "demo-skill", "operation": "create",
            "contract_hash": payload["contract_hash"], "source_manifest_hash": payload["source_manifest"]["sha256"],
            "snapshot_root": "run/snapshot", "output_root": "run/output", "execution_identity": "sha256:" + "1" * 64,
            "max_context_bytes": 512,
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

    def test_semantic_child_rejects_oversized_context_before_publishing_sidecars(self):
        temporary, root, _contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        request = {
            "schema_version": "skill-input-child-request.v1", "consumer": "demo-skill", "operation": "create",
            "contract_hash": payload["contract_hash"], "source_manifest_hash": payload["source_manifest"]["sha256"],
            "snapshot_root": "run/snapshot", "output_root": "run/output", "execution_identity": "sha256:" + "1" * 64,
            "max_context_bytes": 512,
            "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"], "authorizes": [],
        }

        def fake_runner(**kwargs):
            output = {
                "context": {"schema_version": "skill-input-context.v1", "source_manifest_hash": payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "x" * 2000}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"},
                "decision": {"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": request["execution_identity"], "source_manifest_hash": payload["source_manifest"]["sha256"], "context_artifact_hash": "sha256:" + "0" * 64, "source_statuses": {"requirements.md": "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": "sha256:" + "2" * 64, "authorizes": []},
            }
            kwargs["output_last_message"].write_text(json.dumps(output), encoding="utf-8")
            return 0, "", ["fake"]

        with self.assertRaisesRegex(ReceiptValidationError, "max_context_bytes"):
            run_semantic_child(request, root, backend="codex-cli", model="test-model", runner=fake_runner)
        self.assertFalse((root / "run" / "output" / "skill-input-context.v1.json").exists())
        self.assertFalse((root / "run" / "output" / "semantic-decision.v1.json").exists())


if __name__ == "__main__":
    unittest.main()

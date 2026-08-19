import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PYTHON_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PYTHON_ROOT))

from prepare_skill_input_consumption import prepare  # noqa: E402
from skill_input_consumption import SkillInputError, artifact_identity_hash, canonical_hash, contained_path, expand_source_graph, generated_artifact_exclusions, redact_bytes, redaction_profile_hash, sha256_bytes, validate_contract, write_json_atomic  # noqa: E402
from validate_skill_input_consumption import ReceiptValidationError, _artifact, _remove_model_snapshot_payload, publish_ready, validate_receipt  # noqa: E402
from launch_skill_input_consumer import ChildRequestError, _validate_segment_summary, create_child_request, run_semantic_child, semantic_child_execution_identity, validate_child_request  # noqa: E402
from skill_input_gate import require_ready_skill_input  # noqa: E402


class SkillInputConsumptionTests(unittest.TestCase):
    @staticmethod
    def _backend_inspector(backend):
        return {
            "backend": backend,
            "available": True,
            "executable": "missing-test-codex",
            "executable_sha256": "sha256:" + "e" * 64,
        }

    def _execution_identity(self, model="test-model"):
        return semantic_child_execution_identity(
            "codex-cli",
            model,
            backend_inspector=self._backend_inspector,
        )

    def _fixture(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=root, check=True)
        basis = root / "budget.json"
        source = root / "requirements.md"
        basis.write_text(json.dumps({
            "schema_version": "skill-input-budget.v1",
            "max_context_bytes": 512,
            "max_snapshot_bytes": 262144,
            "max_sources": 10,
            "max_reference_depth": 4,
        }), encoding="utf-8")
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
            "max_snapshot_bytes": 262144,
            "budget_basis": {"path": "budget.json", "sha256": sha256_bytes(basis.read_bytes())},
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

    def test_source_graph_allows_only_declared_missing_planned_test(self):
        temporary, root, contract_path, _receipt, _args = self._fixture()
        self.addCleanup(temporary.cleanup)
        source = root / "requirements.md"
        source.write_text("[planned](tools/tests/test_future.py)\n", encoding="utf-8")
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["source_roles"]["requirements"]["reference_kinds"] = ["markdown-link"]
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

        with self.assertRaisesRegex(SkillInputError, "referenced source does not exist"):
            expand_source_graph(root, contract, "create", {"requirements": ["requirements.md"]})
        expanded = expand_source_graph(
            root,
            contract,
            "create",
            {"requirements": ["requirements.md"]},
            frozenset({"tools/tests/test_future.py"}),
        )

        self.assertEqual(["requirements.md"], [relative for _path, relative in expanded])

    def test_opaque_reference_path_is_hashed_without_recursive_expansion(self):
        temporary, root, contract_path, _receipt, _args = self._fixture()
        self.addCleanup(temporary.cleanup)
        plan = root / "plan"
        plan.mkdir()
        (plan / "knowledge-context.v1.json").write_text('{"path":"../large.py"}\n', encoding="utf-8")
        (root / "large.py").write_text("x = 'unrelated'\n", encoding="utf-8")
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["source_roles"] = {
            "requirements": {
                "selector": "requirements",
                "required": True,
                "root": "repository",
                "allowed_kinds": ["directory"],
                "reference_kinds": ["json-path-field"],
                "opaque_reference_paths": ["knowledge-context.v1.json"],
            }
        }
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

        expanded = expand_source_graph(root, contract, "create", {"requirements": ["plan"]})

        self.assertEqual(["plan/knowledge-context.v1.json"], [relative for _path, relative in expanded])

    def test_opaque_directory_is_excluded_from_directory_members(self):
        temporary, root, contract_path, _receipt, _args = self._fixture()
        self.addCleanup(temporary.cleanup)
        plan = root / "plan"
        repair = plan / "repair"
        repair.mkdir(parents=True)
        (repair / "closure.json").write_text('{"path":"logs/old.json"}\n', encoding="utf-8")
        (plan / "current.md").write_text("current\n", encoding="utf-8")
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["source_roles"] = {
            "requirements": {
                "selector": "requirements",
                "required": True,
                "root": "repository",
                "allowed_kinds": ["directory"],
                "reference_kinds": ["json-path-field"],
                "opaque_reference_paths": ["repair"],
            }
        }
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

        expanded = expand_source_graph(root, contract, "create", {"requirements": ["plan"]})

        self.assertEqual(["plan/current.md"], [relative for _path, relative in expanded])

    def test_knowledge_context_artifacts_are_excluded_from_target_source_graph(self):
        temporary, root, _contract_path, _receipt, _args = self._fixture()
        self.addCleanup(temporary.cleanup)
        plan = root / "plan"
        plan.mkdir()
        (plan / "knowledge-context.v1.json").write_text("{}\n", encoding="utf-8")
        (plan / "knowledge-context.freeze.v1.json").write_text("{}\n", encoding="utf-8")
        (plan / "plan-state.v1.json").write_text("{}\n", encoding="utf-8")
        (plan / "resume-state.v1.json").write_text("{}\n", encoding="utf-8")
        (plan / "current.md").write_text("current\n", encoding="utf-8")

        excluded = generated_artifact_exclusions(root, plan)

        self.assertEqual(
            {"plan/knowledge-context.v1.json", "plan/knowledge-context.freeze.v1.json"},
            {path for path in excluded if "knowledge-context" in path},
        )
        self.assertEqual(
            {"plan/plan-state.v1.json", "plan/resume-state.v1.json"},
            {path for path in excluded if path.endswith(("plan-state.v1.json", "resume-state.v1.json"))},
        )

    def test_derived_reports_and_evidence_directories_are_excluded(self):
        temporary, root, _contract_path, _receipt, _args = self._fixture()
        self.addCleanup(temporary.cleanup)
        plan = root / "plan"
        (plan / "terminal-results").mkdir(parents=True)
        (plan / "attempts" / "A1").mkdir(parents=True)
        (plan / "knowledge-context.history").mkdir()
        (plan / "95-implementation-evolution-and-completion-report.md").write_text("report\n", encoding="utf-8")
        (plan / "terminal-results" / "terminal-full.json").write_text("{}\n", encoding="utf-8")
        (plan / "attempts" / "A1" / "page-1.json").write_text("{}\n", encoding="utf-8")

        excluded = generated_artifact_exclusions(root, plan)

        self.assertIn("plan/95-implementation-evolution-and-completion-report.md", excluded)
        self.assertIn("plan/terminal-results", excluded)
        self.assertIn("plan/attempts", excluded)
        self.assertIn("plan/knowledge-context.history", excluded)

    def test_excluded_snapshot_directory_is_not_reingested(self):
        temporary, root, contract_path, _receipt, _args = self._fixture()
        self.addCleanup(temporary.cleanup)
        plan = root / "plan"
        snapshot = plan / "snapshot"
        snapshot.mkdir(parents=True)
        (plan / "requirements.md").write_text("current\n", encoding="utf-8")
        (snapshot / "old.md").write_text("stale\n", encoding="utf-8")
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["source_roles"] = {
            "requirements": {
                "selector": "requirements",
                "required": True,
                "root": "repository",
                "allowed_kinds": ["directory"],
                "reference_kinds": [],
            }
        }
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

        expanded = expand_source_graph(
            root,
            contract,
            "create",
            {"requirements": ["plan"]},
            excluded_paths=frozenset({"plan/snapshot"}),
        )

        self.assertEqual(["plan/requirements.md"], [relative for _path, relative in expanded])

    def test_legacy_v1_contract_uses_default_snapshot_budget(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        contract_payload.pop("max_snapshot_bytes")
        contract.write_text(json.dumps(contract_payload), encoding="utf-8")
        prepare(args)
        receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
        request = create_child_request(
            receipt_payload,
            contract_payload,
            root,
            contract_path=contract,
            receipt_root=receipt.parent,
            output_root="run/output",
            backend="codex-cli",
            model="test-model",
            backend_inspector=self._backend_inspector,
        )
        self.assertEqual(262144, request["max_snapshot_bytes"])

    def test_budget_basis_values_are_bound_to_contract(self):
        temporary, root, contract, _receipt, _args = self._fixture()
        self.addCleanup(temporary.cleanup)
        payload = json.loads(contract.read_text(encoding="utf-8"))
        payload["max_context_bytes"] = 1024
        with self.assertRaisesRegex(SkillInputError, "budget_basis does not bind max_context_bytes"):
            validate_contract(payload, root)

    def test_protocol_manifest_name_is_reserved(self):
        temporary, root, _contract, _receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        reserved = root / "source-manifest.v1.json"
        reserved.write_text("source\n", encoding="utf-8")
        args.target = "source-manifest.v1.json"
        args.source_role = ["requirements=source-manifest.v1.json"]
        with self.assertRaisesRegex(SkillInputError, "reserved for the protocol manifest"):
            prepare(args)

    def test_protocol_manifest_name_is_reserved_case_insensitively(self):
        temporary, root, _contract, _receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        reserved = root / "SOURCE-MANIFEST.V1.JSON"
        reserved.write_text("source\n", encoding="utf-8")
        args.target = "SOURCE-MANIFEST.V1.JSON"
        args.source_role = ["requirements=SOURCE-MANIFEST.V1.JSON"]
        with self.assertRaisesRegex(SkillInputError, "reserved for the protocol manifest"):
            prepare(args)

    def test_intermediate_junction_is_rejected_when_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            (target / "file.txt").write_text("x\n", encoding="utf-8")
            junction = root / "junction"
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(target)], capture_output=True, text=True)
            if result.returncode:
                self.skipTest("directory junctions unavailable")
            with self.assertRaisesRegex(SkillInputError, "symlink source is not allowed"):
                contained_path(root, "junction/file.txt")

    def test_bearer_token_redaction_removes_complete_credential(self):
        redacted, sensitivity, status = redact_bytes(b"Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.secret.payload\n")
        self.assertEqual("credential-bearing", sensitivity)
        self.assertEqual("complete", status)
        self.assertNotIn(b"eyJhbGciOiJIUzI1NiJ9.secret.payload", redacted)

    def test_json_authorization_object_redaction_preserves_valid_json(self):
        redacted, sensitivity, status = redact_bytes(
            b'{"implementation_authorization":{"maintainer_override_allowed":true},"states":["plan-ready"]}'
        )
        self.assertEqual("credential-bearing", sensitivity)
        self.assertEqual("complete", status)
        self.assertEqual(
            {"implementation_authorization": "<redacted>", "states": ["plan-ready"]},
            json.loads(redacted),
        )

    def test_empty_utf8_source_has_complete_zero_range_coverage(self):
        temporary, _root, _contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        args.repository_root.joinpath("requirements.md").write_text("", encoding="utf-8")
        prepare(args)
        source = json.loads(receipt.read_text(encoding="utf-8"))["sources"][0]
        self.assertEqual("complete", source["transport_status"])
        self.assertEqual(0, source["line_count"])
        self.assertEqual([], source["ranges_consumed"])

    def test_non_utf8_source_fails_closed(self):
        temporary, _root, _contract, _receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        args.repository_root.joinpath("requirements.md").write_bytes(b"\xff\xfe")
        prepare(args)
        payload = json.loads(args.receipt.read_text(encoding="utf-8"))
        self.assertEqual("failed", payload["sources"][0]["transport_status"])
        with self.assertRaisesRegex(SkillInputError, "not UTF-8"):
            validate_receipt(args.receipt, args.repository_root, args.contract)

    def test_multiline_source_has_exact_full_range_coverage(self):
        temporary, _root, _contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        args.repository_root.joinpath("requirements.md").write_text(
            "".join(f"line {index}\n" for index in range(1, 301)),
            encoding="utf-8",
        )
        prepare(args)
        source = json.loads(receipt.read_text(encoding="utf-8"))["sources"][0]
        self.assertEqual(300, source["line_count"])
        self.assertEqual([{"unit": "line", "start": 1, "end": 300}], source["ranges_consumed"])

    def test_logs_source_is_rejected_even_for_current_diagnostic_input(self):
        temporary, root, _contract, _receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        log_source = root / "logs" / "current.txt"
        log_source.parent.mkdir()
        log_source.write_text("diagnostic\n", encoding="utf-8")
        args.source_role = ["requirements=logs/current.txt"]
        with self.assertRaisesRegex(SkillInputError, "forbidden source path"):
            prepare(args)

    def test_common_tokens_and_private_keys_are_redacted(self):
        raw = (
            b"ghp_abcdefghijklmnopqrstuvwxyz123456\n"
            b"-----BEGIN PRIVATE KEY-----\nsecret-material\n-----END PRIVATE KEY-----\n"
        )
        redacted, sensitivity, status = redact_bytes(raw)
        self.assertEqual("credential-bearing", sensitivity)
        self.assertEqual("complete", status)
        self.assertNotIn(b"ghp_", redacted)
        self.assertNotIn(b"secret-material", redacted)

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

    def test_direct_self_reference_is_ignored(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        contract_payload["source_roles"]["requirements"]["reference_kinds"] = ["json-path-field"]
        contract.write_text(json.dumps(contract_payload), encoding="utf-8")
        (root / "requirements.md").write_text(
            json.dumps({"dependency_closure": ["requirements.md"]}),
            encoding="utf-8",
        )
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual({"requirements.md"}, {item["path"] for item in payload["sources"]})

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

    def test_reference_style_markdown_link_enters_source_manifest(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        contract_payload["source_roles"]["requirements"]["reference_kinds"] = ["markdown-link"]
        contract.write_text(json.dumps(contract_payload), encoding="utf-8")
        (root / "requirements.md").write_text(
            "[Details][spec]\n\n[spec]: referenced.md\n", encoding="utf-8"
        )
        (root / "referenced.md").write_text("Referenced requirement\n", encoding="utf-8")
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(
            ["referenced.md", "requirements.md"],
            [source["path"] for source in payload["sources"]],
        )

    def test_shortcut_markdown_reference_enters_source_manifest(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        contract_payload["source_roles"]["requirements"]["reference_kinds"] = ["markdown-link"]
        contract.write_text(json.dumps(contract_payload), encoding="utf-8")
        (root / "requirements.md").write_text(
            "[Specification]\n\n[specification]: referenced.md\n", encoding="utf-8"
        )
        (root / "referenced.md").write_text("Referenced requirement\n", encoding="utf-8")
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(
            {"requirements.md", "referenced.md"},
            {source["path"] for source in payload["sources"]},
        )

    def test_markdown_literal_regions_and_escaped_links_are_not_references(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        contract_payload["source_roles"]["requirements"]["reference_kinds"] = ["markdown-link"]
        contract.write_text(json.dumps(contract_payload), encoding="utf-8")
        (root / "requirements.md").write_text(
            "`[inline](missing-inline.md)`\n"
            "```markdown\n[fenced](missing-fenced.md)\n```\n"
            "<!-- [comment](missing-comment.md) -->\n"
            "\\[escaped](missing-escaped.md)\n"
            "[Real](referenced.md)\n",
            encoding="utf-8",
        )
        (root / "referenced.md").write_text("Referenced requirement\n", encoding="utf-8")
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(
            {"requirements.md", "referenced.md"},
            {source["path"] for source in payload["sources"]},
        )

    def test_angle_bracket_markdown_destination_requires_a_valid_close_or_title(self):
        temporary, root, contract, _receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        contract_payload["source_roles"]["requirements"]["reference_kinds"] = ["markdown-link"]
        contract.write_text(json.dumps(contract_payload), encoding="utf-8")
        (root / "requirements.md").write_text(
            '[Details](<referenced.md> invalid title)\n', encoding="utf-8"
        )
        (root / "referenced.md").write_text("Referenced requirement\n", encoding="utf-8")
        with self.assertRaisesRegex(SkillInputError, "inline reference"):
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
        request.write_text(
            json.dumps({"header": "Authorization: Bearer actual-secret-value"}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(SkillInputError, "credential material"):
            prepare(args)

    def test_directory_membership_change_during_prepare_fails_closed(self):
        temporary, root, contract, _receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        contract_payload["source_roles"]["requirements"]["allowed_kinds"] = ["directory"]
        contract.write_text(json.dumps(contract_payload), encoding="utf-8")
        source_dir = root / "requirements"
        source_dir.mkdir()
        (source_dir / "initial.md").write_text("Initial\n", encoding="utf-8")
        args.target = "requirements"
        args.source_role = ["requirements=requirements"]
        import prepare_skill_input_consumption as prepare_module

        original_expand = prepare_module.expand_source_graph

        def expand_then_mutate(*expand_args, **expand_kwargs):
            expanded = original_expand(*expand_args, **expand_kwargs)
            (source_dir / "added.md").write_text("Added during preparation\n", encoding="utf-8")
            return expanded

        with patch.object(prepare_module, "expand_source_graph", side_effect=expand_then_mutate):
            with self.assertRaisesRegex(SkillInputError, "directory source membership changed"):
                prepare(args)

    def test_artifact_path_rejects_intermediate_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            artifact = target / "context.json"
            artifact.write_text("{}\n", encoding="utf-8")
            link = root / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")
            with self.assertRaisesRegex(ReceiptValidationError, "symlink"):
                _artifact(
                    root,
                    {"path": "link/context.json", "sha256": sha256_bytes(artifact.read_bytes())},
                    "context",
                )

    def test_repository_head_drift_without_source_drift_remains_valid(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        subprocess.run(["git", "commit", "--allow-empty", "-qm", "identity drift"], cwd=root, check=True)
        self.assertEqual("candidate", validate_receipt(receipt, root, contract)["status"])

    def test_dirty_to_clean_provenance_drift_without_source_drift_remains_valid(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        (root / "requirements.md").write_text("dirty but selected\n", encoding="utf-8")
        prepare(args)
        subprocess.run(["git", "add", "requirements.md"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "commit selected source"], cwd=root, check=True)
        self.assertEqual("candidate", validate_receipt(receipt, root, contract)["status"])

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
            "max_snapshot_bytes": 262144,
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
        request["allowed_capabilities"] = ["read-frozen-snapshot", "write-context-output"]
        request["output_root"] = "run/snapshot/output"
        with self.assertRaisesRegex(ChildRequestError, "must be disjoint"):
            validate_child_request(request, root)
        self.assertFalse((root / "run" / "snapshot" / "output").exists())

    def test_child_request_is_constructed_from_actual_execution_identity(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        request = create_child_request(
            receipt_payload,
            contract_payload,
            root,
            contract_path=contract,
            receipt_root=receipt.parent,
            output_root="run/output",
            backend="codex-cli",
            model="test-model",
            backend_inspector=self._backend_inspector,
        )
        self.assertEqual(self._execution_identity(), request["execution_identity"])
        called = False

        def fake_runner(**_kwargs):
            nonlocal called
            called = True
            return 1, "", []

        with self.assertRaisesRegex(ChildRequestError, "execution identity"):
            run_semantic_child(
                request,
                root,
                backend="codex-cli",
                model="different-model",
                runner=fake_runner,
                backend_inspector=self._backend_inspector,
            )
        self.assertFalse(called)

    def test_child_request_rejects_unbound_contract_or_receipt_before_creating_output(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        altered_contract = dict(contract_payload)
        altered_contract["max_context_bytes"] = 1024
        with self.assertRaisesRegex(ChildRequestError, "payload does not match artifact"):
            create_child_request(
                receipt_payload,
                altered_contract,
                root,
                contract_path=contract,
                receipt_root=receipt.parent,
                output_root="run/untrusted-output",
                backend="codex-cli",
                model="test-model",
                backend_inspector=self._backend_inspector,
            )
        self.assertFalse((root / "run" / "untrusted-output").exists())
        receipt_payload["route_identity"] = "tampered"
        with self.assertRaisesRegex(ChildRequestError, "receipt binding"):
            create_child_request(
                receipt_payload,
                contract_payload,
                root,
                contract_path=contract,
                receipt_root=receipt.parent,
                output_root="run/untrusted-output",
                backend="codex-cli",
                model="test-model",
                backend_inspector=self._backend_inspector,
            )
        self.assertFalse((root / "run" / "untrusted-output").exists())

    def test_semantic_child_uses_one_normalized_configuration_snapshot(self):
        temporary, root, _contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        isolation = {
            "user_config": "ignored", "session": "ephemeral", "skip_git_repo_check": True,
            "disabled_features": [], "web_search": "disabled", "project_doc_max_bytes": 0,
            "provider": "default", "provider_config_hash": canonical_hash({}),
        }
        request = {
            "schema_version": "skill-input-child-request.v1", "consumer": "demo-skill", "operation": "create",
            "contract_hash": payload["contract_hash"], "source_manifest_hash": payload["source_manifest"]["sha256"],
            "snapshot_root": "run/snapshot", "output_root": "run/output",
            "execution_identity": semantic_child_execution_identity(
                "codex-cli", " test-model ", " HIGH ",
                backend_inspector=self._backend_inspector, isolation=isolation,
            ),
            "max_context_bytes": 512,
            "max_snapshot_bytes": 262144,
            "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"], "authorizes": [],
        }

        def fake_runner(**kwargs):
            self.assertEqual("test-model", kwargs["codex_model"])
            self.assertIn("model_reasoning_effort=high", kwargs["codex_configs"])
            self.assertIn(
                "schema_version, source_manifest_hash, sections, truncated, omitted_items, generated_at",
                kwargs["prompt"],
            )
            self.assertIn(
                "context_artifact_hash, source_statuses, status, rationale, redaction_status",
                kwargs["prompt"],
            )
            output = {
                "context": {"schema_version": "skill-input-context.v1", "source_manifest_hash": payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "Requirement text"}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"},
                "decision": {"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": request["execution_identity"], "source_manifest_hash": payload["source_manifest"]["sha256"], "context_artifact_hash": "sha256:" + "0" * 64, "source_statuses": {"requirements.md": "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": redaction_profile_hash(), "authorizes": []},
            }
            kwargs["output_last_message"].write_text(json.dumps(output), encoding="utf-8")
            return 0, "", ["fake"]

        with patch(
            "launch_skill_input_consumer._isolated_codex_configuration",
            return_value=(["features.shell_tool=false"], isolation),
        ) as isolated_config:
            run_semantic_child(
                request,
                root,
                backend="codex-cli",
                model=" test-model ",
                reasoning_effort=" HIGH ",
                runner=fake_runner,
                backend_inspector=self._backend_inspector,
            )
        self.assertEqual(1, isolated_config.call_count)

    def test_semantic_child_rejects_unknown_reasoning_effort_before_launch(self):
        with self.assertRaisesRegex(ChildRequestError, "reasoning effort"):
            semantic_child_execution_identity(
                "codex-cli",
                "test-model",
                "turbo",
                backend_inspector=self._backend_inspector,
            )

    def test_execution_identity_binds_safe_provider_config_and_rejects_literal_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory)
            config = codex_home / "config.toml"
            config.write_text(
                'model_provider = "test-provider"\n'
                '[model_providers.test-provider]\n'
                'name = "Test"\n'
                'base_url = "https://one.example.invalid"\n'
                'wire_api = "responses"\n',
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
                first = self._execution_identity()
                config.write_text(
                    config.read_text(encoding="utf-8").replace("one.example", "two.example"),
                    encoding="utf-8",
                )
                second = self._execution_identity()
                self.assertNotEqual(first, second)
                config.write_text(
                    config.read_text(encoding="utf-8")
                    + '[model_providers.test-provider.http_headers]\nAuthorization = "secret"\n',
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ChildRequestError, "not safe to replay"):
                    self._execution_identity()
                config.write_text(
                    'model_provider = "test-provider"\n'
                    '[model_providers.test-provider]\n'
                    'name = "Test"\n'
                    'base_url = "https://example.invalid?api_key=sk-actualsecret123"\n'
                    'wire_api = "responses"\n',
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ChildRequestError, "credential-like value"):
                    self._execution_identity()

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
            "max_context_bytes": 512,
            "max_snapshot_bytes": 262144, "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"], "authorizes": [],
        }), encoding="utf-8")
        decision = output_root / "semantic-decision.v1.json"
        context = output_root / "skill-input-context.v1.json"
        context.write_text(json.dumps({"schema_version": "skill-input-context.v1", "source_manifest_hash": payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "Requirement text"}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"}), encoding="utf-8")
        context_hash = artifact_identity_hash(context)
        decision.write_text(json.dumps({"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": "sha256:" + "1" * 64, "source_manifest_hash": payload["source_manifest"]["sha256"], "context_artifact_hash": context_hash, "source_statuses": {source_path: "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": redaction_profile_hash(), "authorizes": []}), encoding="utf-8")
        publish_ready(receipt, child_request, decision, context, root, contract)
        self.assertFalse((root / "run" / "snapshot" / "requirements.md").exists())
        self.assertEqual("ready", validate_receipt(receipt, root, contract, require_ready=True)["status"])
        gated = require_ready_skill_input(receipt_path=receipt, repository_root=root, contract_path=contract, consumer="demo-skill", operation="create")
        self.assertEqual(context.resolve(), gated["context_artifact"])
        self.assertEqual(artifact_identity_hash(context), gated["context_artifact_hash"])
        with self.assertRaises(ValueError):
            require_ready_skill_input(receipt_path=receipt, repository_root=root, contract_path=contract, consumer="other-skill", operation="create")

    def test_publish_ready_rejects_failed_redaction_decision(self):
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
            "max_context_bytes": 512,
            "max_snapshot_bytes": 262144, "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"], "authorizes": [],
        }), encoding="utf-8")
        context = output_root / "skill-input-context.v1.json"
        context.write_text(json.dumps({"schema_version": "skill-input-context.v1", "source_manifest_hash": payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "Requirement text"}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"}), encoding="utf-8")
        context_hash = artifact_identity_hash(context)
        decision = output_root / "semantic-decision.v1.json"
        decision.write_text(json.dumps({"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": "sha256:" + "1" * 64, "source_manifest_hash": payload["source_manifest"]["sha256"], "context_artifact_hash": context_hash, "source_statuses": {source_path: "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "failed", "redaction_profile_hash": redaction_profile_hash(), "authorizes": []}), encoding="utf-8")
        candidate_bytes = receipt.read_bytes()
        with self.assertRaisesRegex(ReceiptValidationError, "insufficient semantic input"):
            publish_ready(receipt, child_request, decision, context, root, contract)
        self.assertEqual(candidate_bytes, receipt.read_bytes())

    def test_publish_ready_keeps_candidate_when_snapshot_cleanup_fails(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        output_root = root / "run" / "output"
        output_root.mkdir()
        child_request = root / "run" / "skill-input-child-request.v1.json"
        child_request.write_text(json.dumps({
            "schema_version": "skill-input-child-request.v1", "consumer": "demo-skill", "operation": "create",
            "contract_hash": payload["contract_hash"], "source_manifest_hash": payload["source_manifest"]["sha256"],
            "snapshot_root": "run/snapshot", "output_root": "run/output", "execution_identity": "sha256:" + "1" * 64,
            "max_context_bytes": 512, "max_snapshot_bytes": 262144,
            "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"], "authorizes": [],
        }), encoding="utf-8")
        context = output_root / "skill-input-context.v1.json"
        context.write_text(json.dumps({"schema_version": "skill-input-context.v1", "source_manifest_hash": payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "Requirement text"}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"}), encoding="utf-8")
        context_hash = artifact_identity_hash(context)
        source_path = payload["sources"][0]["path"]
        decision = output_root / "semantic-decision.v1.json"
        decision.write_text(json.dumps({"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": "sha256:" + "1" * 64, "source_manifest_hash": payload["source_manifest"]["sha256"], "context_artifact_hash": context_hash, "source_statuses": {source_path: "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": redaction_profile_hash(), "authorizes": []}), encoding="utf-8")
        candidate_bytes = receipt.read_bytes()
        with patch("validate_skill_input_consumption._remove_model_snapshot_payload", side_effect=OSError("cleanup unavailable")):
            with self.assertRaisesRegex(OSError, "cleanup unavailable"):
                publish_ready(receipt, child_request, decision, context, root, contract)
        self.assertEqual(candidate_bytes, receipt.read_bytes())
        self.assertEqual("candidate", validate_receipt(receipt, root, contract)["status"])

    def test_snapshot_cleanup_restores_files_after_midway_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / "snapshot"
            snapshot.mkdir()
            manifest = snapshot / "source-manifest.v1.json"
            manifest.write_text("{}\n", encoding="utf-8")
            first = snapshot / "first.md"
            second = snapshot / "second.md"
            first.write_text("first\n", encoding="utf-8")
            second.write_text("second\n", encoding="utf-8")
            original_unlink = Path.unlink
            calls = 0

            def fail_second(path, *args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("second cleanup failed")
                return original_unlink(path, *args, **kwargs)

            with patch.object(Path, "unlink", new=fail_second):
                with self.assertRaisesRegex(OSError, "second cleanup failed"):
                    _remove_model_snapshot_payload(
                        root,
                        manifest,
                        [{"path": "first.md"}, {"path": "second.md"}],
                    )
            self.assertEqual("first\n", first.read_text(encoding="utf-8"))
            self.assertEqual("second\n", second.read_text(encoding="utf-8"))

    def test_publish_ready_restores_snapshot_when_final_cas_fails(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        output_root = root / "run" / "output"
        output_root.mkdir()
        child_request = output_root / "skill-input-child-request.v1.json"
        child_request.write_text(json.dumps({
            "schema_version": "skill-input-child-request.v1", "consumer": "demo-skill", "operation": "create",
            "contract_hash": payload["contract_hash"], "source_manifest_hash": payload["source_manifest"]["sha256"],
            "snapshot_root": "run/snapshot", "output_root": "run/output", "execution_identity": "sha256:" + "1" * 64,
            "max_context_bytes": 512, "max_snapshot_bytes": 262144,
            "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"], "authorizes": [],
        }), encoding="utf-8")
        context = output_root / "skill-input-context.v1.json"
        context.write_text(json.dumps({"schema_version": "skill-input-context.v1", "source_manifest_hash": payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "Requirement text"}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"}), encoding="utf-8")
        context_hash = artifact_identity_hash(context)
        source_path = payload["sources"][0]["path"]
        decision = output_root / "semantic-decision.v1.json"
        decision.write_text(json.dumps({"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": "sha256:" + "1" * 64, "source_manifest_hash": payload["source_manifest"]["sha256"], "context_artifact_hash": context_hash, "source_statuses": {source_path: "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": redaction_profile_hash(), "authorizes": []}), encoding="utf-8")
        import validate_skill_input_consumption as validator_module
        original_writer = validator_module.write_json_atomic
        def fail_final(path, value, **kwargs):
            if "expected_bytes" in kwargs:
                raise OSError("final CAS unavailable")
            return original_writer(path, value, **kwargs)
        with patch.object(validator_module, "write_json_atomic", side_effect=fail_final):
            with self.assertRaisesRegex(OSError, "final CAS unavailable"):
                publish_ready(receipt, child_request, decision, context, root, contract)
        self.assertTrue((root / "run" / "snapshot" / "requirements.md").is_file())
        self.assertEqual("candidate", validate_receipt(receipt, root, contract)["status"])

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
            "max_context_bytes": 512,
            "max_snapshot_bytes": 262144, "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"], "authorizes": [],
        }), encoding="utf-8")
        decision = output_root / "semantic-decision.v1.json"
        context = output_root / "skill-input-context.v1.json"
        context.write_text(json.dumps({"schema_version": "skill-input-context.v1", "source_manifest_hash": payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "x" * 2000}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"}), encoding="utf-8")
        context_hash = artifact_identity_hash(context)
        decision.write_text(json.dumps({"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": "sha256:" + "1" * 64, "source_manifest_hash": payload["source_manifest"]["sha256"], "context_artifact_hash": context_hash, "source_statuses": {source_path: "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": redaction_profile_hash(), "authorizes": []}), encoding="utf-8")
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
            "snapshot_root": "run/snapshot", "output_root": "run/output", "execution_identity": self._execution_identity(),
            "max_context_bytes": 512,
            "max_snapshot_bytes": 262144,
            "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"], "authorizes": [],
        }

        def fake_runner(**kwargs):
            self.assertEqual("read-only", kwargs["codex_sandbox"])
            self.assertTrue(kwargs["codex_skip_git_repo_check"])
            self.assertEqual(["--ephemeral", "--ignore-user-config"], kwargs["codex_extra_args"])
            self.assertIn("features.shell_tool=false", kwargs["codex_configs"])
            self.assertIn("features.view_image=false", kwargs["codex_configs"])
            self.assertIn('web_search="disabled"', kwargs["codex_configs"])
            self.assertIn("SNAPSHOT_JSON_BEGIN", kwargs["prompt"])
            self.assertIn("Requirement text", kwargs["prompt"])
            self.assertFalse((kwargs["root"] / "snapshot").exists())
            output = {
                "context": {"schema_version": "skill-input-context.v1", "source_manifest_hash": payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "Requirement text"}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"},
                "decision": {"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": request["execution_identity"], "source_manifest_hash": payload["source_manifest"]["sha256"], "context_artifact_hash": "sha256:" + "0" * 64, "source_statuses": {"requirements.md": "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": redaction_profile_hash(), "authorizes": []},
            }
            kwargs["output_last_message"].write_text(json.dumps(output), encoding="utf-8")
            return 0, "", ["fake"]

        result = run_semantic_child(request, root, backend="codex-cli", model="test-model", runner=fake_runner, backend_inspector=self._backend_inspector)
        self.assertEqual("complete", result["status"])
        self.assertTrue(Path(result["context_artifact"]).is_file())
        self.assertTrue(Path(result["semantic_decision"]).is_file())

    def test_transport_failures_preserve_same_binding_for_retry(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        request = create_child_request(
            payload,
            json.loads(contract.read_text(encoding="utf-8")),
            root,
            contract_path=contract,
            receipt_root=receipt.parent,
            output_root="run/output",
            backend="codex-cli",
            model="test-model",
            backend_inspector=self._backend_inspector,
        )

        def failed_runner(**_kwargs):
            return 1, "", ["fake"]

        with self.assertRaisesRegex(ChildRequestError, "failed without a typed output"):
            run_semantic_child(request, root, backend="codex-cli", model="test-model", runner=failed_runner, backend_inspector=self._backend_inspector)
        self.assertTrue((root / "run" / "snapshot" / "requirements.md").is_file())

        def timed_out_runner(**_kwargs):
            raise subprocess.TimeoutExpired(["codex", "exec"], 1)

        with self.assertRaises(subprocess.TimeoutExpired):
            run_semantic_child(request, root, backend="codex-cli", model="test-model", runner=timed_out_runner, backend_inspector=self._backend_inspector)

        def malformed_runner(**kwargs):
            kwargs["output_last_message"].write_text("not-json", encoding="utf-8")
            return 0, "", ["fake"]

        with self.assertRaisesRegex(ChildRequestError, "not valid JSON"):
            run_semantic_child(request, root, backend="codex-cli", model="test-model", runner=malformed_runner, backend_inspector=self._backend_inspector)

        def successful_runner(**kwargs):
            output = {
                "context": {"schema_version": "skill-input-context.v1", "source_manifest_hash": payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "Requirement text"}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"},
                "decision": {"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": request["execution_identity"], "source_manifest_hash": payload["source_manifest"]["sha256"], "context_artifact_hash": "sha256:" + "0" * 64, "source_statuses": {"requirements.md": "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": redaction_profile_hash(), "authorizes": []},
            }
            kwargs["output_last_message"].write_text(json.dumps(output), encoding="utf-8")
            return 0, "", ["fake"]

        result = run_semantic_child(request, root, backend="codex-cli", model="test-model", runner=successful_runner, backend_inspector=self._backend_inspector)
        self.assertEqual("complete", result["status"])

    def test_semantic_child_rejects_oversized_serialized_snapshot_before_launch(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        snapshot_source = root / "run" / "snapshot" / "requirements.md"
        snapshot_source.write_text("x" * 70000, encoding="utf-8", newline="")
        manifest_path = root / "run" / "snapshot" / "source-manifest.v1.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["sources"][0]["semantic_snapshot_sha256"] = sha256_bytes(snapshot_source.read_bytes())
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8", newline="\n")
        request = {
            "schema_version": "skill-input-child-request.v1",
            "consumer": "demo-skill", "operation": "create",
            "contract_hash": payload["contract_hash"],
            "source_manifest_hash": artifact_identity_hash(manifest_path),
            "snapshot_root": "run/snapshot", "output_root": "run/output",
            "execution_identity": self._execution_identity(),
            "max_context_bytes": 512, "max_snapshot_bytes": 65536,
            "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"],
            "authorizes": [],
        }
        with self.assertRaisesRegex(ChildRequestError, "max_snapshot_bytes"):
            run_semantic_child(
                request,
                root,
                backend="codex-cli",
                model="test-model",
                runner=unittest.mock.Mock(),
                backend_inspector=self._backend_inspector,
            )

    def test_paged_snapshot_reader_covers_every_page_and_binds_coverage(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        basis = root / "budget.json"
        basis.write_text(json.dumps({
            "schema_version": "skill-input-budget.v1", "max_context_bytes": 512,
            "max_snapshot_bytes": 131072, "max_sources": 10, "max_reference_depth": 4,
        }), encoding="utf-8")
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        contract_payload.update({
            "max_snapshot_bytes": 131072,
            "semantic_input_mode": "paged-frozen-snapshot-stdin",
            "max_snapshot_chunk_bytes": 16384,
            "budget_basis": {"path": "budget.json", "sha256": sha256_bytes(basis.read_bytes())},
        })
        contract.write_text(json.dumps(contract_payload), encoding="utf-8")
        (root / "requirements.md").write_text(
            'password: "redact-this-value"\n' + "Requirement text\n" * 5000,
            encoding="utf-8",
        )
        prepare(args)
        receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
        request = create_child_request(
            receipt_payload, contract_payload, root, contract_path=contract,
            receipt_root=receipt.parent, output_root="run/output", backend="codex-cli",
            model="test-model", backend_inspector=self._backend_inspector,
        )
        request_path = root / "run" / "skill-input-child-request.v1.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        calls = []

        def fake_runner(**kwargs):
            calls.append(kwargs["prompt"])
            if "PAGE_DESCRIPTOR_BEGIN" in kwargs["prompt"]:
                self.assertIn("PAGE_CONTENT_BEGIN", kwargs["prompt"])
                output = {"status": "accepted", "summary": "Page requirements are sufficient."}
            else:
                self.assertIn("PAGED_READ_COVERAGE_BEGIN", kwargs["prompt"])
                self.assertIn("PAGED_READ_SUMMARIES_BEGIN", kwargs["prompt"])
                output = {
                    "context": {"schema_version": "skill-input-context.v1", "source_manifest_hash": receipt_payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "All pages were consumed."}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"},
                    "decision": {"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": request["execution_identity"], "source_manifest_hash": receipt_payload["source_manifest"]["sha256"], "context_artifact_hash": "sha256:" + "0" * 64, "source_statuses": {"requirements.md": "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": redaction_profile_hash(), "authorizes": []},
                }
            kwargs["output_last_message"].write_text(json.dumps(output), encoding="utf-8")
            return 0, "", ["fake"]

        result = run_semantic_child(
            request, root, backend="codex-cli", model="test-model", runner=fake_runner,
            backend_inspector=self._backend_inspector,
        )
        self.assertGreater(len(calls), 2)
        coverage = Path(result["snapshot_read_coverage"])
        self.assertTrue(coverage.is_file())
        coverage_payload = json.loads(coverage.read_text(encoding="utf-8"))
        safe_source, _sensitivity, _redaction = redact_bytes(
            (root / "requirements.md").read_bytes()
        )
        line_cursor = 1
        for segment in coverage_payload["segments"]:
            page = safe_source[segment["start_byte"]:segment["end_byte"]]
            self.assertEqual(line_cursor, segment["start_line"])
            self.assertEqual(line_cursor + page.count(b"\n"), segment["end_line"])
            line_cursor = segment["end_line"]
        decision = json.loads(Path(result["semantic_decision"]).read_text(encoding="utf-8"))
        self.assertEqual(artifact_identity_hash(coverage), decision["snapshot_read_coverage"]["sha256"])
        publish_ready(receipt, request_path, Path(result["semantic_decision"]), Path(result["context_artifact"]), root, contract)
        self.assertEqual("ready", validate_receipt(receipt, root, contract, require_ready=True)["status"])
        coverage.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ReceiptValidationError, "coverage"):
            validate_receipt(receipt, root, contract, require_ready=True)

    def test_paged_snapshot_reader_accepts_a_summary_within_the_transport_budget(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        basis = root / "budget.json"
        basis.write_text(json.dumps({
            "schema_version": "skill-input-budget.v1", "max_context_bytes": 512,
            "max_snapshot_bytes": 131072, "max_sources": 10, "max_reference_depth": 4,
        }), encoding="utf-8")
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        contract_payload.update({
            "max_snapshot_bytes": 131072,
            "semantic_input_mode": "paged-frozen-snapshot-stdin",
            "max_snapshot_chunk_bytes": 16384,
            "budget_basis": {"path": "budget.json", "sha256": sha256_bytes(basis.read_bytes())},
        })
        contract.write_text(json.dumps(contract_payload), encoding="utf-8")
        prepare(args)
        receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
        request = create_child_request(
            receipt_payload, contract_payload, root, contract_path=contract,
            receipt_root=receipt.parent, output_root="run/output", backend="codex-cli",
            model="test-model", backend_inspector=self._backend_inspector,
        )

        def fake_runner(**kwargs):
            if "PAGE_DESCRIPTOR_BEGIN" in kwargs["prompt"]:
                output = {"status": "accepted", "summary": "x" * 4096}
            else:
                output = {
                    "context": {"schema_version": "skill-input-context.v1", "source_manifest_hash": receipt_payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "Requirement text"}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"},
                    "decision": {"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": request["execution_identity"], "source_manifest_hash": receipt_payload["source_manifest"]["sha256"], "context_artifact_hash": "sha256:" + "0" * 64, "source_statuses": {"requirements.md": "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": redaction_profile_hash(), "authorizes": []},
                }
            kwargs["output_last_message"].write_text(json.dumps(output), encoding="utf-8")
            return 0, "", ["fake"]

        result = run_semantic_child(
            request, root, backend="codex-cli", model="test-model", runner=fake_runner,
            backend_inspector=self._backend_inspector,
        )
        self.assertEqual("complete", result["status"])

    def test_paged_snapshot_reader_rejects_an_insufficient_page(self):
        segment = {"source_path": "requirements.md"}
        with self.assertRaisesRegex(ChildRequestError, "insufficient"):
            _validate_segment_summary(
                {"status": "insufficient", "summary": "The page cannot be interpreted."},
                segment,
            )

    def test_paged_snapshot_reader_applies_summary_budget_after_redaction(self):
        segment = {"source_path": "requirements.md"}
        summary = "\n".join("token: a" for _ in range(300))
        self.assertLessEqual(len(summary.encode("utf-8")), 4096)
        with self.assertRaisesRegex(ChildRequestError, "transport budget"):
            _validate_segment_summary(
                {"status": "accepted", "summary": summary},
                segment,
            )

    def test_semantic_child_rejects_snapshot_modification(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        request = create_child_request(
            payload,
            json.loads(contract.read_text(encoding="utf-8")),
            root,
            contract_path=contract,
            receipt_root=receipt.parent,
            output_root="run/output",
            backend="codex-cli",
            model="test-model",
            backend_inspector=self._backend_inspector,
        )

        def fake_runner(**kwargs):
            (root / "run" / "snapshot" / "requirements.md").write_text("mutated\n", encoding="utf-8")
            kwargs["output_last_message"].write_text("{}", encoding="utf-8")
            return 0, "", ["fake"]

        with self.assertRaisesRegex(ChildRequestError, "modified the frozen snapshot"):
            run_semantic_child(
                request,
                root,
                backend="codex-cli",
                model="test-model",
                runner=fake_runner,
                backend_inspector=self._backend_inspector,
            )

    def test_semantic_child_redacts_credential_like_typed_output_before_publishing(self):
        temporary, root, contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        request = create_child_request(
            payload,
            json.loads(contract.read_text(encoding="utf-8")),
            root,
            contract_path=contract,
            receipt_root=receipt.parent,
            output_root="run/output",
            backend="codex-cli",
            model="test-model",
            backend_inspector=self._backend_inspector,
        )

        def fake_runner(**kwargs):
            output = {
                "context": {"schema_version": "skill-input-context.v1", "source_manifest_hash": payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "Authorization: Bearer actual-looking-secret"}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"},
                "decision": {"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": request["execution_identity"], "source_manifest_hash": payload["source_manifest"]["sha256"], "context_artifact_hash": "sha256:" + "0" * 64, "source_statuses": {"requirements.md": "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": redaction_profile_hash(), "authorizes": []},
            }
            kwargs["output_last_message"].write_text(json.dumps(output), encoding="utf-8")
            return 0, "", ["fake"]

        result = run_semantic_child(
            request,
            root,
            backend="codex-cli",
            model="test-model",
            runner=fake_runner,
            backend_inspector=self._backend_inspector,
        )
        context = Path(result["context_artifact"]).read_text(encoding="utf-8")
        self.assertNotIn("actual-looking-secret", context)
        self.assertIn("<redacted>", context)

    def test_semantic_child_rejects_oversized_context_before_publishing_sidecars(self):
        temporary, root, _contract, receipt, args = self._fixture()
        self.addCleanup(temporary.cleanup)
        prepare(args)
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        request = {
            "schema_version": "skill-input-child-request.v1", "consumer": "demo-skill", "operation": "create",
            "contract_hash": payload["contract_hash"], "source_manifest_hash": payload["source_manifest"]["sha256"],
            "snapshot_root": "run/snapshot", "output_root": "run/output", "execution_identity": self._execution_identity(),
            "max_context_bytes": 512,
            "max_snapshot_bytes": 262144,
            "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"], "authorizes": [],
        }

        def fake_runner(**kwargs):
            output = {
                "context": {"schema_version": "skill-input-context.v1", "source_manifest_hash": payload["source_manifest"]["sha256"], "sections": [{"title": "requirements", "content": "x" * 2000}], "truncated": False, "omitted_items": 0, "generated_at": "2026-01-01T00:00:00Z"},
                "decision": {"schema_version": "skill-semantic-decision.v1", "producer_role": "semantic-child", "execution_identity": request["execution_identity"], "source_manifest_hash": payload["source_manifest"]["sha256"], "context_artifact_hash": "sha256:" + "0" * 64, "source_statuses": {"requirements.md": "accepted"}, "status": "accepted", "rationale": "sufficient", "redaction_status": "complete", "redaction_profile_hash": redaction_profile_hash(), "authorizes": []},
            }
            kwargs["output_last_message"].write_text(json.dumps(output), encoding="utf-8")
            return 0, "", ["fake"]

        with self.assertRaisesRegex(ReceiptValidationError, "max_context_bytes"):
            run_semantic_child(request, root, backend="codex-cli", model="test-model", runner=fake_runner, backend_inspector=self._backend_inspector)
        self.assertFalse((root / "run" / "output" / "skill-input-context.v1.json").exists())
        self.assertFalse((root / "run" / "output" / "semantic-decision.v1.json").exists())


if __name__ == "__main__":
    unittest.main()

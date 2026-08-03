#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import copy
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock


PLAN_DIR = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_module(
    "knowledge_plan_validator", PLAN_DIR / "tools/validate_whole_directory.py"
)
inventory_builder = load_module(
    "knowledge_inventory_builder", PLAN_DIR / "tools/build_hosted_inventory.py"
)
completion_publisher = load_module(
    "knowledge_completion_publisher",
    PLAN_DIR / "tools/publish_implementation_complete.py",
)


class FixtureSemanticsTests(unittest.TestCase):
    def test_all_positive_fixtures_pass(self) -> None:
        index = validator.load_json(PLAN_DIR / "fixtures/fixture-cases.v1.json")
        positives = [case for case in index["cases"] if case["kind"] == "positive"]
        self.assertGreater(len(positives), 0)
        for case in positives:
            fixture = validator.load_json(PLAN_DIR / case["path"])
            passed, failure = validator.semantic_fixture_result(fixture["payload"])
            self.assertTrue(passed, case["fixture_id"])
            self.assertIsNone(failure, case["fixture_id"])

    def test_all_negative_fixtures_return_exact_code(self) -> None:
        index = validator.load_json(PLAN_DIR / "fixtures/fixture-cases.v1.json")
        negatives = [case for case in index["cases"] if case["kind"] == "negative"]
        self.assertGreater(len(negatives), 0)
        for case in negatives:
            fixture = validator.load_json(PLAN_DIR / case["path"])
            passed, failure = validator.semantic_fixture_result(fixture["payload"])
            self.assertFalse(passed, case["fixture_id"])
            self.assertEqual(case["expected_failure_code"], failure, case["fixture_id"])


class KnowledgeInterfaceFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schemas = validator.validate_schema_documents()
        self.index = validator.load_json(
            PLAN_DIR / "fixtures/knowledge-interface-cases.v1.json"
        )

    def test_all_positive_interfaces_pass(self) -> None:
        positives = [case for case in self.index["cases"] if case["kind"] == "positive"]
        self.assertGreater(len(positives), 0)
        for case in positives:
            fixture = validator.load_json(PLAN_DIR / case["path"])
            failure = validator.knowledge_interface_fixture_failure(
                fixture, self.schemas
            )
            self.assertIsNone(failure, case["fixture_id"])

    def test_all_negative_interfaces_return_exact_code(self) -> None:
        negatives = [case for case in self.index["cases"] if case["kind"] == "negative"]
        self.assertGreater(len(negatives), 0)
        for case in negatives:
            fixture = validator.load_json(PLAN_DIR / case["path"])
            failure = validator.knowledge_interface_fixture_failure(
                fixture, self.schemas
            )
            self.assertEqual(case["expected_failure_code"], failure, case["fixture_id"])

    def test_matched_low_confidence_fails_semantic_guard(self) -> None:
        fixture = validator.load_json(
            PLAN_DIR / "fixtures/knowledge-interface/positive/valid-locator-llm-intent.json"
        )
        result = copy.deepcopy(fixture["result"])
        result["confidence"]["level"] = "low"
        self.assertEqual(
            "locator_matched_confidence",
            validator.locator_fixture_failure(fixture["request"], result),
        )

    def test_maintenance_before_snapshot_must_match_request(self) -> None:
        fixture = validator.load_json(
            PLAN_DIR / "fixtures/knowledge-interface/positive/valid-maintenance-existing-only.json"
        )
        result = copy.deepcopy(fixture["result"])
        result["before_snapshot_id"] = "knowledge-snapshot-other"
        self.assertEqual(
            "maintenance_before_snapshot_mismatch",
            validator.maintenance_fixture_failure(fixture["request"], result),
        )

    def test_path_policy_uses_component_boundaries(self) -> None:
        allowed = ["docs/standards"]
        self.assertTrue(validator.repo_path_is_within_policy("docs/standards/phase-service.md", allowed))
        self.assertTrue(validator.repo_path_is_within_policy("docs/standards", allowed))
        self.assertFalse(validator.repo_path_is_within_policy("docs/standards-old/phase-service.md", allowed))


class StrictJsonTests(unittest.TestCase):
    def test_duplicate_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="knowledge-json-test-") as temporary:
            path = Path(temporary) / "duplicate.json"
            path.write_text('{"value":1,"value":2}\n', encoding="utf-8", newline="\n")
            with self.assertRaises(validator.PlanValidationError) as raised:
                validator.load_json(path)
            self.assertEqual("json_duplicate_key", raised.exception.code)

    def test_closed_schema_rejects_unknown_property(self) -> None:
        schema = {
            "type": "object",
            "required": ["known"],
            "additionalProperties": False,
            "properties": {"known": {"type": "string"}},
        }
        with self.assertRaises(validator.PlanValidationError) as raised:
            validator.validate_instance({"known": "yes", "unknown": "no"}, schema)
        self.assertEqual("schema_extra_property", raised.exception.code)

    def test_plan_index_status_mismatch_is_rejected(self) -> None:
        with self.assertRaises(validator.PlanValidationError) as raised:
            validator.validate_plan_index_status("- Status: draft\n", "plan-ready")
        self.assertEqual("plan_index_status_mismatch", raised.exception.code)


class ProvenanceTests(unittest.TestCase):
    def test_evolution_source_hashes_match_repository_lf_bytes(self) -> None:
        provenance = validator.load_json(PLAN_DIR / "source-provenance.v1.json")
        for entry in provenance["evolution_sources"]:
            source = validator.repo_path(entry["path"])
            self.assertNotIn(b"\r\n", source.read_bytes(), entry["path"])
            self.assertEqual(
                entry["sha256"],
                validator.sha256_path(source),
                entry["path"],
            )


class GitAuthorityTests(unittest.TestCase):
    def test_source_commit_may_be_an_ancestor_of_candidate_head(self) -> None:
        source = "a" * 40
        candidate = "b" * 40
        with mock.patch.object(
            validator.subprocess,
            "run",
            side_effect=[
                subprocess.CompletedProcess([], 0, candidate + "\n", ""),
                subprocess.CompletedProcess([], 0, "", ""),
            ],
        ):
            validator.validate_git_head({"git_head": source})

    def test_divergent_source_commit_is_rejected(self) -> None:
        source = "a" * 40
        candidate = "b" * 40
        with mock.patch.object(
            validator.subprocess,
            "run",
            side_effect=[
                subprocess.CompletedProcess([], 0, candidate + "\n", ""),
                subprocess.CompletedProcess([], 1, "", ""),
            ],
        ):
            with self.assertRaises(validator.PlanValidationError) as raised:
                validator.validate_git_head({"git_head": source})
        self.assertEqual("git_head_not_ancestor", raised.exception.code)


class CompletionPublisherTests(unittest.TestCase):
    def test_completion_mode_distinguishes_initial_and_repair_runs(self) -> None:
        self.assertEqual(
            "initial",
            completion_publisher.completion_mode("implementation-authorized"),
        )
        self.assertEqual(
            "repair",
            completion_publisher.completion_mode("implementation-complete"),
        )

    def test_completion_mode_rejects_other_lifecycle_states(self) -> None:
        with self.assertRaises(RuntimeError):
            completion_publisher.completion_mode("plan-ready")


class InventoryScannerTests(unittest.TestCase):
    def test_direct_scan_ignores_help_text_but_finds_argv_literal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="knowledge-inventory-test-") as temporary:
            root = Path(temporary)
            (root / "PhaseA.Platform").mkdir()
            scripts = root / "scripts/sc"
            scripts.mkdir(parents=True)
            (scripts / "help_only.py").write_text(
                'HELP = "codex exec timeout in seconds"\n',
                encoding="utf-8",
                newline="\n",
            )
            (scripts / "bad.py").write_text(
                'command = ["codex", "exec", "-"]\n',
                encoding="utf-8",
                newline="\n",
            )
            sources = list(inventory_builder.iter_production_sources(root))
            violations, excluded = inventory_builder.scan_direct_invocations(root, sources)
            self.assertEqual([], excluded)
            self.assertEqual(1, len(violations))
            self.assertEqual("scripts/sc/bad.py", violations[0]["path"])
            self.assertEqual("direct_llm_invocation_bypass", violations[0]["failure_code"])

    def test_inventory_build_is_deterministic(self) -> None:
        first = inventory_builder.build_outputs(validator.REPO_ROOT)
        second = inventory_builder.build_outputs(validator.REPO_ROOT)
        self.assertEqual(first, second)


class ContextEnvelopeCryptoTests(unittest.TestCase):
    def test_jcs_is_order_independent_and_preserves_unicode(self) -> None:
        first = {"z": None, "a": ["\u77e5\u8bc6", 1, True]}
        second = {"a": ["\u77e5\u8bc6", 1, True], "z": None}
        first_bytes = validator.canonicalize_jcs(first)
        self.assertEqual(first_bytes, validator.canonicalize_jcs(second))
        self.assertIn("\u77e5\u8bc6".encode("utf-8"), first_bytes)

    def test_manifest_identity_branch_fails_closed(self) -> None:
        vector = validator.load_json(
            PLAN_DIR / "fixtures/reference-vectors/jcs-hmac-reference-vector.v1.json"
        )
        manifest = copy.deepcopy(vector["manifest"])
        manifest["signed_payload"]["identity_mode"] = "account-bound"
        schemas = validator.validate_schema_documents()
        with self.assertRaises(validator.PlanValidationError) as raised:
            validator.validate_instance(
                manifest,
                schemas["hosted-context-manifest.v1.schema.json"],
            )
        self.assertEqual("schema_one_of", raised.exception.code)

    def test_manifest_e2_requires_enforce_gate(self) -> None:
        vector = validator.load_json(
            PLAN_DIR / "fixtures/reference-vectors/jcs-hmac-reference-vector.v1.json"
        )
        manifest = copy.deepcopy(vector["manifest"])
        manifest["signed_payload"]["gate_mode"] = "observe"
        schemas = validator.validate_schema_documents()
        with self.assertRaises(validator.PlanValidationError) as raised:
            validator.validate_instance(
                manifest,
                schemas["hosted-context-manifest.v1.schema.json"],
            )
        self.assertEqual("schema_one_of", raised.exception.code)


if __name__ == "__main__":
    unittest.main()

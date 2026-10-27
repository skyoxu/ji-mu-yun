"""ADR-0044/0048: administrator-operated BMAD reads published knowledge only."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/python"))
import _knowledge_catalog_builder as builder
import _knowledge_locator_core as locator
import evaluate_knowledge_queries as evaluation
import publish_knowledge_catalog as publication


class BmadReadonlyConsumerTests(unittest.TestCase):
    def policy(self):
        document = json.loads((ROOT / "knowledge/policies/consumer-policies.v2.json").read_text())
        result = locator._policy_for({"consumer": "bmad-planning", "policy_revision": document["policy_revision"]}, document)
        self.assertIsNotNone(result, "BMAD must have its own admitted reader identity")
        return result

    def entry(self, **changes):
        result = {"source_path": "scripts/python/example.py", "module_id": "example",
                  "consumer_ids": ["bmad-planning"], "semantic_eligible": True,
                  "status": "active", "lifecycle": "repository-source",
                  "visibility": {"workspace": "active"}}
        result.update(changes)
        return result

    def test_registered_identity_does_not_impersonate_existing_workflows(self):
        self.assertEqual("bmad-planning", self.policy()["consumer"])

    def test_existing_consumer_policies_are_unchanged(self):
        new = json.loads((ROOT / "knowledge/policies/consumer-policies.v2.json").read_text())["policies"]
        previous = [p for p in new if p["consumer"] != "bmad-planning"]
        self.assertEqual("3499f4364fa85f46df29d1f3f41852499e22bc6ad1fb1f05d87e9f52af4e4d28", hashlib.sha256(json.dumps(previous, sort_keys=True, separators=(",", ":")).encode()).hexdigest())

    def test_request_and_publication_schemas_admit_only_the_named_extension(self):
        for name in ("knowledge-locator-request.v1.schema.json", "knowledge-consumer-projections.v1.schema.json",
                     "repository-knowledge-query-suite.v1.schema.json", "repository-knowledge-query-report.v1.schema.json"):
            document = json.loads((ROOT / "knowledge/contracts" / name).read_text())
            def consumer_enums(value):
                if isinstance(value, dict):
                    if "consumer" in value.get("properties", {}):
                        yield value["properties"]["consumer"]["enum"]
                    for child in value.values():
                        yield from consumer_enums(child)
                elif isinstance(value, list):
                    for child in value:
                        yield from consumer_enums(child)
            enums = list(consumer_enums(document))
            self.assertEqual(1, len(enums))
            self.assertIn("bmad-planning", enums[0])
            self.assertNotIn("unknown-admin", enums[0])

    def test_all_existing_content_domains_and_statuses_remain_queryable(self):
        policy = self.policy()
        for domain in builder.DOMAINS:
            for status in ("active", "conditional", "historical"):
                with self.subTest(domain=domain, status=status):
                    self.assertTrue(locator._policy_allows(self.entry(status=status, visibility={domain: "active"}), "related facts", policy))
        for path in ("docs/adr/example.md", "execution-plans/example/00-index.md", "runtime/phase-a/example.ps1", ".agents/skills/example/SKILL.md"):
            self.assertTrue(locator._policy_allows(self.entry(source_path=path), "related facts", policy))

    def test_existing_exclusions_ineligible_sources_and_identity_still_deny(self):
        policy = self.policy()
        for changes in ({"source_path": "docs/migration/old.md"}, {"semantic_eligible": False},
                        {"status": "excluded"}, {"consumer_ids": ["vdd"]},
                        {"lifecycle": "live-workspace"}, {"visibility": {"workspace": "excluded"}}):
            with self.subTest(changes=changes):
                self.assertFalse(locator._policy_allows(self.entry(**changes), "related facts", policy))
        self.assertIsNone(locator._policy_for({"consumer": "unknown-admin"}, {"policies": [policy]}))

    def test_module_reader_addition_preserves_explicit_owner_readers(self):
        class Snapshot:
            def contains(self, path): return True
            def digest(self, path): return "0" * 64
            def read_text(self, path): return "# Example\nRepository facts.\n"
        instance = builder.CatalogBuilder(Snapshot(), {}, {"rules": []})
        module = instance.add_module(module_id="example", kind="example", source_path="docs/example.md",
                                     source_role="example", primary_domain="toolchain", consumer_ids=("vdd",))
        self.assertEqual(["bmad-planning", "vdd"], module["consumer_ids"])
        self.assertTrue(builder._module_allowed(module, self.policy()))

    def test_publication_accepts_legacy_and_extended_exact_registry_only(self):
        original = json.loads((ROOT / "knowledge/policies/consumer-policies.v2.json").read_text())
        snapshot, catalog, _, _ = builder.build_layers(ROOT, policy=original, exclusions=json.loads((ROOT / "knowledge/policies/source-exclusions.v1.json").read_text()))
        exclusions = json.loads((ROOT / "knowledge/policies/source-exclusions.v1.json").read_text())
        for policies in (original, {**original, "policies": [p for p in original["policies"] if p["consumer"] != "bmad-planning"]}):
            projections = builder.build_consumer_projections(catalog, policies)
            publication._validate_layers(snapshot, catalog, projections, builder.compatibility_catalog(catalog), policies, exclusions)
        invalid = copy.deepcopy(original)
        invalid["policies"].append({**self.policy(), "consumer": "unknown-admin"})
        with self.assertRaisesRegex(ValueError, "projection_schema_invalid"):
            publication._validate_layers(snapshot, catalog, builder.build_consumer_projections(catalog, invalid), builder.compatibility_catalog(catalog), invalid, exclusions)
        projections = builder.build_consumer_projections(catalog, original)
        projections["projections"] = [p for p in projections["projections"] if p["consumer"] != "bmad-planning"]
        with self.assertRaisesRegex(ValueError, "projection_schema_invalid"):
            publication._validate_layers(snapshot, catalog, projections, builder.compatibility_catalog(catalog), original, exclusions)

    def test_new_suite_identity_is_validated_without_executing_queries(self):
        suite = json.loads((ROOT / "knowledge/evaluation/repository-knowledge-query-suite.v1.json").read_text())
        previous = [case for case in suite["cases"] if case["consumer"] != "bmad-planning"]
        self.assertEqual(108, len(previous))
        untouched = [c for c in previous if c["case_id"] not in {"TOOL-006", "TOOL-016"}]
        self.assertEqual(106, len(untouched))
        self.assertEqual("75216ae9642041a3d060a8a911a6b05bb5f53dd077346f8ce4b35492c2353d47", hashlib.sha256(json.dumps(untouched, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
        evaluation._validate_suite(suite)
        cases = [c for c in suite["cases"] if c["consumer"] == "bmad-planning"]
        self.assertGreaterEqual(len(cases), 2)
        invalid = copy.deepcopy(suite)
        invalid["cases"][-1]["consumer"] = "unknown-admin"
        with self.assertRaisesRegex(ValueError, "invalid consumer"):
            evaluation._validate_suite(invalid)

    def test_knowledge_query_requires_publication_and_source_identity(self):
        self.policy()
        catalog = json.loads((ROOT / "knowledge/catalogs/repository-knowledge-catalog.v2.json").read_text())
        request = {"schema_version": "jimuyun.knowledge-locator-request.v1", "request_id": "bmad-denied",
                   "consumer": "bmad-planning", "query": "repository-rules", "snapshot": {"ref": "refs/heads/main", "commit": catalog["source_snapshot"]["commit"]},
                   "policy_revision": "knowledge-consumer-policies.v2"}
        with mock.patch.object(locator, "verify_current_publication", return_value=False):
            result = locator.query_with_diagnostics(request, ROOT)
        self.assertEqual("blocked", result["result"]["status"])
        self.assertEqual([], result["result"]["candidates"])


if __name__ == "__main__":
    unittest.main()

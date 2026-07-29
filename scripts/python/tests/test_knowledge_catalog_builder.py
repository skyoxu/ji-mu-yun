from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts" / "python"))
from _knowledge_catalog_builder import is_policy_excluded
CATALOG_PATH = REPOSITORY_ROOT / "knowledge/catalogs/repository-knowledge-catalog.v2.json"
SNAPSHOT_PATH = REPOSITORY_ROOT / "knowledge/snapshots/repository-source-snapshot.v1.json"
PROJECTION_PATH = REPOSITORY_ROOT / "knowledge/projections/consumer-projections.v1.json"
BUILDER_PATH = REPOSITORY_ROOT / "scripts/python/build_knowledge_catalog.py"


class KnowledgeCatalogBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        cls.projections = json.loads(PROJECTION_PATH.read_text(encoding="utf-8"))
        cls.modules = {item["module_id"]: item for item in cls.catalog["modules"]}

    def test_layers_are_main_pinned_and_reproducible(self) -> None:
        main = subprocess.check_output(
            ["git", "rev-parse", "refs/heads/main"], cwd=REPOSITORY_ROOT, text=True, encoding="utf-8"
        ).strip()
        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", self.snapshot["commit"], main],
            cwd=REPOSITORY_ROOT,
            check=False,
        )
        self.assertEqual(0, ancestry.returncode)
        self.assertEqual(self.snapshot, self.catalog["source_snapshot"])
        completed = subprocess.run(
            [sys.executable, "-B", str(BUILDER_PATH), "--repository-root", str(REPOSITORY_ROOT), "--check"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_migration_tree_is_hard_excluded_from_every_layer(self) -> None:
        self.assertFalse(any(item["path"].startswith("docs/migration/") for item in self.snapshot["sources"]))
        self.assertFalse(any(item["source_path"].startswith("docs/migration/") for item in self.catalog["modules"]))
        self.assertIn("docs/migration/", self.catalog["exclusion_policy"]["excluded_path_prefixes"])

    def test_plan_derived_consumer_artifacts_are_excluded_without_excluding_plan_authority(self) -> None:
        exclusions = json.loads((REPOSITORY_ROOT / "knowledge/policies/source-exclusions.v1.json").read_text(encoding="utf-8"))
        derived_paths = (
            "execution-plans/example/knowledge-context.v1.json",
            "execution-plans/example/knowledge-context.freeze.v1.json",
            "execution-plans/example/knowledge-context.history/previous.v1.json",
            "execution-plans/example/acceptance-runs/r3/candidate-content-manifest.v1.json",
            "execution-plans/example/.acceptance-snapshots/r3/.agents/skills/example/SKILL.md",
        )
        for path in derived_paths:
            self.assertTrue(is_policy_excluded(path, exclusions))
        self.assertFalse(is_policy_excluded("execution-plans/example/00-index.md", exclusions))

    def test_adr_status_and_scope_layers_are_typed(self) -> None:
        self.assertEqual("active", self.modules["adr.ADR-0003"]["status"])
        self.assertEqual("conditional", self.modules["adr.ADR-0017"]["status"])
        self.assertEqual("historical", self.modules["adr.ADR-0001"]["status"])
        self.assertEqual("excluded", self.modules["adr.ADR-0016"]["status"])
        collections = {item["collection_id"]: set(item["member_module_ids"]) for item in self.catalog["collections"]}
        self.assertIn("adr.ADR-0048", collections["adr.phase"])
        self.assertIn("adr.ADR-0018", collections["adr.godot-workspace"])
        self.assertIn("adr.ADR-0048", collections["adr.toolchain-governance"])
        self.assertTrue(collections["adr.unscoped"])

    def test_architecture_uses_modules_while_fixtures_stay_integrity_only(self) -> None:
        phase_modules = [item for item in self.catalog["modules"] if item["module_id"].startswith("architecture.phase-service.")]
        self.assertEqual(10, len(phase_modules))
        self.assertIn("architecture.phase-service.auth-and-accounts", self.modules)
        self.assertTrue(self.modules["architecture.phase-service.auth-and-accounts"]["anchors"])
        semantic_paths = {item["source_path"] for item in self.catalog["modules"]}
        self.assertNotIn("docs/architecture/base/ZZZ-encoding-fixture-bad.md", semantic_paths)
        source_roles = {item["path"]: item["source_role"] for item in self.snapshot["sources"]}
        self.assertEqual("integrity-only", source_roles["docs/architecture/base/ZZZ-encoding-fixture-bad.md"])
        accepted = {item["module_id"] for item in self.catalog["modules"] if item["kind"] == "adr" and item["status"] == "active"}
        for module in phase_modules:
            governed = {item["target"] for item in module["relations"] if item["type"] == "governed_by"}
            self.assertTrue(governed.issubset(accepted))

    def test_governance_components_bind_skill_cli_orchestrator_and_route(self) -> None:
        expected = {
            "governance.vdd-execution-plan",
            "governance.quick-dev-tdd-adapter",
            "governance.bootstrap-review",
            "governance.refactor-implementation-acceptance",
            "governance.knowledge-locator",
            "governance.knowledge-maintenance",
        }
        self.assertTrue(expected.issubset(self.modules))
        for module_id in expected - {"governance.knowledge-maintenance"}:
            roles = {item["role"] for item in self.modules[module_id]["resources"]}
            self.assertTrue("cli" in roles or self.modules[module_id]["source_role"] == "cli-entrypoint")
        route_components = {item["component_id"] for item in self.catalog["routes"]}
        self.assertTrue(expected.issubset(route_components))

    def test_execution_plan_directories_have_one_bounded_module_each(self) -> None:
        plans = [item for item in self.catalog["modules"] if item["kind"] == "execution-plan"]
        self.assertEqual(7, len(plans))
        for plan in plans:
            self.assertTrue(plan["source_path"].endswith("/00-index.md"))
            self.assertFalse(any("/fixtures/" in item["path"] or "/tools/" in item["path"] or "/95-" in item["path"] for item in plan["resources"]))
            self.assertNotIn("knowledge-context", {item["role"] for item in plan["resources"]})
        self.assertFalse(any(item["path"].endswith("/knowledge-context.v1.json") for item in self.snapshot["sources"]))
        self.assertEqual("historical", self.modules["plan.2026-07-25-four-domain-knowledge-context-engineering-plan"]["status"])
        self.assertEqual("conditional", self.modules["plan.2026-07-11-phase-frontend-boundary-hardening-execution-plan"]["status"])

    def test_consumer_projections_are_hash_bound_and_quick_dev_is_empty(self) -> None:
        values = {item["consumer"]: item for item in self.projections["projections"]}
        self.assertEqual(set(values), {"vdd", "quick-dev", "bootstrap", "refactor-acceptance"})
        self.assertEqual([], values["quick-dev"]["eligible_module_ids"])
        self.assertTrue(values["vdd"]["eligible_module_ids"])
        self.assertEqual(self.snapshot["snapshot_id"], self.projections["source_snapshot_id"])

    def test_registered_source_hash_matches_main_blob(self) -> None:
        module = self.modules["adr.ADR-0048"]
        blob = subprocess.check_output(
            ["git", "show", f"{self.snapshot['commit']}:{module['source_path']}"], cwd=REPOSITORY_ROOT
        )
        self.assertEqual(hashlib.sha256(blob).hexdigest(), module["source_sha256"])


if __name__ == "__main__":
    unittest.main()

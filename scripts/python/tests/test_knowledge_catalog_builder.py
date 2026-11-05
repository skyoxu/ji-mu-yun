from __future__ import annotations

import hashlib
import io
from unittest import mock
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts" / "python"))
from _knowledge_catalog_builder import CommittedBlobBatch, MainSnapshot, build_layers, is_policy_excluded, read_commit_blob, select_versioned_plan_resource
import publish_knowledge_catalog as publication
CATALOG_PATH = REPOSITORY_ROOT / "knowledge/catalogs/repository-knowledge-catalog.v2.json"
SNAPSHOT_PATH = REPOSITORY_ROOT / "knowledge/snapshots/repository-source-snapshot.v1.json"
PROJECTION_PATH = REPOSITORY_ROOT / "knowledge/projections/consumer-projections.v1.json"
BUILDER_PATH = REPOSITORY_ROOT / "scripts/python/build_knowledge_catalog.py"


class CommittedBlobReaderTests(unittest.TestCase):
    """ADR-0044: long worktree paths never replace pinned Git blob authority."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.root = base / ("r" * max(1, 190 - len(str(base)) - 1))
        self.root.mkdir()
        self.source = "docs/facts-" + "x" * 30 + ".bin"
        self.payload = b"\xef\xbb\xbfcommitted\r\n\x00\xff\n"
        files = {
            self.source: self.payload,
            "docs/migration/excluded.md": b"historical excluded input\n",
            "execution-plans/example/00-index.md": b"# Committed plan\n",
            **{path.as_posix(): b"committed control\n" for path in publication.CONTROL_PATHS},
        }
        for relative, raw in files.items():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        self._git("init", "--initial-branch=main")
        self._git("config", "core.longpaths", "false")
        self._git("add", "--", ".")
        self._git("commit", "-m", "Commit exact knowledge fixtures")
        self.commit = self._git("rev-parse", "refs/heads/main").decode("ascii").strip()
        # git show's ambiguous revision/path probe exceeds Windows MAX_PATH,
        # while every actual source and Git object remains below that boundary.
        self.assertGreater(len(str(self.root / f"{self.commit}:{self.source}")), 260)
        (self.root / self.source).write_bytes(b"dirty worktree must never become fact\n")

    def _git(self, *arguments: str) -> bytes:
        return subprocess.check_output(
            ["git", "-c", "core.longpaths=false", "-c", "core.autocrlf=false",
             "-c", "user.name=Knowledge Fixture", "-c", "user.email=fixture@example.invalid",
             "-C", str(self.root), *arguments],
            stderr=subprocess.PIPE,
        )

    def test_long_path_readers_return_exact_committed_bytes_and_hash(self) -> None:
        snapshot = MainSnapshot(self.root)
        self.assertEqual(self.commit, snapshot.commit)
        self.assertEqual(self.payload, snapshot.read_bytes(self.source))
        self.assertEqual(hashlib.sha256(self.payload).hexdigest(), snapshot.digest(self.source))
        self.assertEqual(self.payload, publication._main_blob(self.root, self.commit, Path(self.source)))
        self.assertNotEqual(self.payload, (self.root / self.source).read_bytes())

    def test_invalid_commit_path_tree_and_excluded_source_remain_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid_blob_commit"):
            read_commit_blob(self.root, "refs/heads/main", self.source)
        with self.assertRaisesRegex(ValueError, "invalid_repository_path"):
            read_commit_blob(self.root, self.commit, "../outside.bin")
        with self.assertRaisesRegex(ValueError, "main_input_unavailable"):
            publication._main_blob(self.root, "0" * 40, Path(self.source))
        with self.assertRaisesRegex(ValueError, "main_input_unavailable"):
            publication._main_blob(self.root, self.commit, Path("docs"))
        with self.assertRaises(subprocess.CalledProcessError):
            MainSnapshot(self.root, authority_ref="refs/heads/missing")
        with self.assertRaisesRegex(ValueError, "hard_excluded_source"):
            MainSnapshot(self.root).read_bytes("docs/migration/excluded.md")

    def test_batch_reuses_only_transport_and_preserves_binary_committed_bytes(self) -> None:
        original = subprocess.Popen
        with mock.patch("_knowledge_catalog_builder.subprocess.Popen", wraps=original) as launches:
            with CommittedBlobBatch(self.root, self.commit) as reader:
                self.assertEqual(self.payload, reader.read(self.source))
                self.assertEqual(b"committed control\n", reader.read("scripts/python/publish_knowledge_catalog.py"))
                self.assertEqual(self.payload, reader.read(self.source))
                child = reader.process
            self.assertEqual(1, launches.call_count)
            self.assertIsNotNone(child.poll())
        self.assertNotEqual(self.payload, (self.root / self.source).read_bytes())

    def test_batch_missing_and_tree_fail_without_poisoning_next_object(self) -> None:
        with CommittedBlobBatch(self.root, self.commit) as reader:
            for path in ("docs/missing.bin", "docs"):
                with self.assertRaises(subprocess.CalledProcessError) as error:
                    reader.read(path)
                self.assertTrue(error.exception.stderr.strip())
                self.assertEqual(self.payload, reader.read(self.source))
            snapshot = MainSnapshot(self.root)
            snapshot._batch = reader
            with self.assertRaisesRegex(ValueError, "hard_excluded_source"):
                snapshot.read_bytes("docs/migration/excluded.md")

    def test_batch_malformed_truncated_and_wrong_separator_are_rejected(self) -> None:
        for wire in (b"bad header\n", b"a" * 40 + b" blob 4\nx", b"a" * 40 + b" blob 1\nx!"):
            child = mock.Mock(stdin=io.BytesIO(), stdout=io.BytesIO(wire), args=["git"])
            child.poll.return_value = None
            child.wait.return_value = 0
            with self.subTest(wire=wire), mock.patch("_knowledge_catalog_builder.subprocess.Popen", return_value=child):
                with self.assertRaises(ValueError), CommittedBlobBatch(self.root, self.commit) as reader:
                    reader.read(self.source)
            child.kill.assert_called_once()
            child.wait.assert_called_once()

    def test_publication_still_requires_main_bound_maintainer_authorization(self) -> None:
        request = {
            "schema_version": publication.PUBLICATION_REQUEST_SCHEMA_VERSION,
            "request_id": "committed-blob-regression",
            "caller": "maintain-knowledge-base",
            "trigger": "operator-requested",
            "target_plan": "execution-plans/example",
            "main_commit": self.commit,
            "automatic": False,
            "maintainer_confirmation": True,
            "recorded_at": "2026-11-03T00:00:00+00:00",
            "authorizes": ["knowledge-publication"],
            "source_route": None,
        }
        summary = publication._validate_publication_request(
            request, expected_main=self.commit, repository_root=self.root
        )
        self.assertEqual(request["request_id"], summary["request_id"])
        for field, value, reason in (
            ("caller", "refactor-acceptance", "caller_invalid"),
            ("main_commit", "0" * 40, "main_mismatch"),
            ("automatic", True, "confirmation_required"),
            ("maintainer_confirmation", False, "confirmation_required"),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, reason):
                publication._validate_publication_request(
                    {**request, field: value}, expected_main=self.commit, repository_root=self.root
                )
        self.assertFalse((self.root / "knowledge/indexes/current.json").exists())

    def test_publication_controls_still_require_pinned_main_bytes(self) -> None:
        publication._require_main_controls(self.root, self.commit)
        changed = self.root / publication.CONTROL_PATHS[0]
        changed.write_bytes(b"dirty control\n")
        with self.assertRaisesRegex(ValueError, "dirty_or_stale_publication_control"):
            publication._require_main_controls(self.root, self.commit)


class KnowledgeCatalogBuilderTests(unittest.TestCase):
    def test_plan_resource_selection_accepts_current_names_and_highest_version(self) -> None:
        directory = "execution-plans/example"
        paths = [
            f"{directory}/requirements.v1.json",
            f"{directory}/requirements.v2.json",
            f"{directory}/implementation-contract.v1.json",
            f"{directory}/implementation-contract.v2.json",
            f"{directory}/repair/command-registry.v9.json",
        ]
        self.assertEqual(f"{directory}/requirements.v2.json", select_versioned_plan_resource(directory, paths, ("requirements-ledger", "requirements")))
        self.assertEqual(f"{directory}/implementation-contract.v2.json", select_versioned_plan_resource(directory, paths, ("implementation-contract",)))
        self.assertIsNone(select_versioned_plan_resource(directory, paths, ("command-registry",)))

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
        before = {path: path.read_bytes() for path in (CATALOG_PATH, SNAPSHOT_PATH, PROJECTION_PATH)}
        completed = subprocess.run(
            [sys.executable, "-B", str(BUILDER_PATH), "--repository-root", str(REPOSITORY_ROOT), "--check"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertIn(completed.returncode, {0, 2}, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        if completed.returncode == 0:
            self.assertEqual("current", result["status"])
        else:
            self.assertEqual("stale", result["status"])
            self.assertTrue(result["stale_outputs"])
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_builder_cli_defaults_to_read_only_check(self) -> None:
        before = {path: path.read_bytes() for path in (CATALOG_PATH, SNAPSHOT_PATH, PROJECTION_PATH)}
        completed = subprocess.run(
            [sys.executable, "-B", str(BUILDER_PATH), "--repository-root", str(REPOSITORY_ROOT)],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertIn(completed.returncode, {0, 2})
        self.assertNotIn('"status": "generated"', completed.stdout)
        self.assertEqual(before, {path: path.read_bytes() for path in before})

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
            "execution-plans/example/repair-closure-r3-round2.json",
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
        expected_plan_indexes = {item["path"] for item in self.snapshot["sources"] if item["path"].startswith("execution-plans/") and item["path"].endswith("/00-index.md")}
        self.assertEqual(expected_plan_indexes, {item["source_path"] for item in plans})
        for plan in plans:
            self.assertTrue(plan["source_path"].endswith("/00-index.md"))
            self.assertFalse(any("/fixtures/" in item["path"] or "/tools/" in item["path"] or "/95-" in item["path"] for item in plan["resources"]))
            self.assertNotIn("knowledge-context", {item["role"] for item in plan["resources"]})
        self.assertFalse(any(item["path"].endswith("/knowledge-context.v1.json") for item in self.snapshot["sources"]))
        self.assertEqual("historical", self.modules["plan.2026-07-25-four-domain-knowledge-context-engineering-plan"]["status"])
        self.assertEqual("conditional", self.modules["plan.2026-07-11-phase-frontend-boundary-hardening-execution-plan"]["status"])

    def test_in_memory_plan_layers_exclude_recursive_lifecycle_artifacts(self) -> None:
        policy = json.loads((REPOSITORY_ROOT / "knowledge/policies/consumer-policies.v2.json").read_text(encoding="utf-8"))
        exclusions = json.loads((REPOSITORY_ROOT / "knowledge/policies/source-exclusions.v1.json").read_text(encoding="utf-8"))
        snapshot, catalog, _projections, _legacy = build_layers(
            REPOSITORY_ROOT, policy=policy, exclusions=exclusions, authority_ref="refs/heads/main"
        )
        plan_resources = [item for item in catalog["modules"] if item["kind"] == "execution-plan"]
        self.assertFalse(any(resource["role"] == "authority-manifest" for plan in plan_resources for resource in plan["resources"]))
        source_paths = {item["path"] for item in snapshot["sources"]}
        self.assertFalse(any(path.endswith("/authority-manifest.v1.json") for path in source_paths))
        self.assertFalse(any("/knowledge-context" in path for path in source_paths))

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

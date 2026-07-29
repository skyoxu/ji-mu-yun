from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CORE_PATH = REPOSITORY_ROOT / "scripts" / "python" / "_knowledge_locator_core.py"
CLI_PATH = REPOSITORY_ROOT / "scripts" / "python" / "knowledge_locator.py"


def load_core():
    if not CORE_PATH.is_file():
        raise FileNotFoundError(CORE_PATH)
    spec = importlib.util.spec_from_file_location("knowledge_locator_core", CORE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KnowledgeLocatorCoreTests(unittest.TestCase):
    def test_stable_tie_break_and_location_only_output(self) -> None:
        try:
            core = load_core()
        except FileNotFoundError:
            self.fail("KWI-LOCATOR-ORDER: deterministic Locator core is missing")
        catalog = {
            "entries": [
                {"path": "docs/zeta.md", "source_sha256": "a" * 64, "content": "locator contract"},
                {"path": "docs/alpha.md", "source_sha256": "b" * 64, "content": "locator contract"},
            ]
        }
        result = core.locate({"query": "locator contract", "consumer": "vdd"}, catalog, max_candidates=2)
        self.assertEqual("matched", result["status"])
        self.assertEqual(["docs/alpha.md", "docs/zeta.md"], [item["path"] for item in result["candidates"]])
        self.assertNotIn("answer", result)
        self.assertEqual({"path", "anchor", "line_start", "line_end", "source_sha256", "provenance", "rank_evidence"}, set(result["candidates"][0]))

    def test_index_build_concurrency_atomic_publish_and_lkg_recovery(self) -> None:
        try:
            core = load_core()
        except FileNotFoundError:
            self.fail("KWI-INDEX-LOCK-CONFLICT: index builder core is missing")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            index = root / "indexes"
            generation = core.publish_index_generation(index, {"entries": []}, "snapshot-a", "policy-v1")
            self.assertTrue((index / "current.json").is_file())
            self.assertEqual(generation["generation_id"], core.publish_index_generation(index, {"entries": []}, "snapshot-a", "policy-v1")["generation_id"])
            self.assertEqual(generation["generation_id"], core.last_known_good(index)["generation_id"])

    def test_cli_emits_result_bound_to_current_main_after_publication_commit(self) -> None:
        request = {
            "schema_version": "jimuyun.knowledge-locator-request.v1",
            "request_id": "test-request",
            "consumer": "vdd",
            "query": "zzzxxyy-unmatched-catalog-token",
            "snapshot": {"ref": "refs/heads/main", "commit": "a" * 40},
            "policy_revision": "test-policy",
        }
        catalog = json.loads((REPOSITORY_ROOT / "knowledge/catalogs/repository-knowledge-catalog.v2.json").read_text(encoding="utf-8"))
        current_main = subprocess.run(
            ["git", "-C", str(REPOSITORY_ROOT), "rev-parse", "refs/heads/main"],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        ).stdout.strip()
        request["snapshot"] = {"ref": "refs/heads/main", "commit": current_main}
        request["policy_revision"] = "knowledge-consumer-policies.v2"
        result = subprocess.run(
            [sys.executable, "-B", str(CLI_PATH), "--catalog", str(REPOSITORY_ROOT / "knowledge/catalogs/repository-knowledge-catalog.v2.json")],
            input=json.dumps(request), text=True, encoding="utf-8", capture_output=True, check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual("jimuyun.knowledge-locator-result.v1", output.get("schema_version"))
        self.assertEqual(request["request_id"], output.get("request_id"))
        self.assertEqual(request["snapshot"], output.get("snapshot"))
        self.assertEqual("insufficient_match", output.get("status"))

    def test_catalog_covers_gdd_prototype_route_module(self) -> None:
        core = load_core()
        catalog = json.loads((REPOSITORY_ROOT / "knowledge/catalogs/repository-knowledge-catalog.v2.json").read_text(encoding="utf-8"))
        result = core.locate({"query": "GDD prototype route"}, catalog, max_candidates=12)
        self.assertEqual("matched", result["status"])
        self.assertIn("docs/architecture/phase-service/prototype-routes-and-recovery.md", [item["path"] for item in result["candidates"]])

    def test_typed_policy_rejects_migration_and_non_exact_history(self) -> None:
        core = load_core()
        policy = {
            "consumer": "vdd", "domains": ["toolchain"], "visibility": ["active", "dependency"],
            "lifecycles": ["repository-source"], "statuses": ["active", "historical"],
            "historical_mode": "exact-only", "path_prefixes": ["docs/"], "exact_paths": [],
        }
        catalog = {"modules": [
            {
                "module_id": "migration.fake", "source_path": "docs/migration/legacy.md", "source_sha256": "a" * 64,
                "content": "legacy migration", "semantic_eligible": True, "status": "active", "lifecycle": "repository-source",
                "primary_domain": "toolchain", "visibility": {"toolchain": "active"}, "consumer_ids": ["vdd"],
            },
            {
                "module_id": "plan.completed", "source_path": "docs/completed.md", "source_sha256": "b" * 64,
                "title": "Completed Plan", "content": "completed knowledge plan", "semantic_eligible": True,
                "status": "historical", "lifecycle": "repository-source", "primary_domain": "toolchain",
                "visibility": {"toolchain": "active"}, "consumer_ids": ["vdd"],
            },
        ]}
        hidden = core.locate({"query": "legacy migration", "consumer": "vdd"}, catalog, policy=policy)
        self.assertEqual("insufficient_match", hidden["status"])
        exact = core.locate({"query": "plan.completed", "consumer": "vdd"}, catalog, policy=policy)
        self.assertEqual("matched", exact["status"])
        self.assertEqual("plan.completed", exact["candidates"][0]["module_id"])

    def test_cli_blocks_stale_catalog_or_snapshot_mismatch(self) -> None:
        request = {
            "schema_version": "jimuyun.knowledge-locator-request.v1",
            "request_id": "test-request",
            "consumer": "vdd",
            "query": "repository rules",
            "snapshot": {"ref": "refs/heads/main", "commit": "a" * 40},
            "policy_revision": "test-policy",
        }
        catalog = {
            "authority_ref": "refs/heads/main",
            "source_snapshot": {"ref": "refs/heads/main", "commit": "b" * 40, "sources": []},
            "entries": [],
        }
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "catalog.json"
            path.write_text(json.dumps(catalog), encoding="utf-8", newline="\n")
            result = subprocess.run(
                [sys.executable, "-B", str(CLI_PATH), "--catalog", str(path)],
                input=json.dumps(request), text=True, capture_output=True, check=False,
            )
        self.assertEqual(0, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual("blocked", output["status"])
        self.assertEqual([], output["candidates"])


if __name__ == "__main__":
    unittest.main()

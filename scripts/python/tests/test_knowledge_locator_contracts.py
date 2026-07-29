from __future__ import annotations

import json
import hashlib
import subprocess
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CONSUMPTION_SCHEMA_PATH = REPOSITORY_ROOT / "knowledge" / "contracts" / "knowledge-consumption-decision.v1.schema.json"
POLICY_PATH = REPOSITORY_ROOT / "knowledge" / "policies" / "consumer-policies.v1.json"
CATALOG_PATH = REPOSITORY_ROOT / "knowledge" / "catalogs" / "repository-knowledge-catalog.v1.json"
CATALOG_V2_PATH = REPOSITORY_ROOT / "knowledge" / "catalogs" / "repository-knowledge-catalog.v2.json"
POLICY_V2_PATH = REPOSITORY_ROOT / "knowledge" / "policies" / "consumer-policies.v2.json"


class KnowledgeLocatorContractTests(unittest.TestCase):
    def test_llm_owned_envelope_is_rejected(self) -> None:
        if not CONSUMPTION_SCHEMA_PATH.is_file() or not POLICY_PATH.is_file():
            self.fail("KWI-CONTRACT-LLM-OWNER: stable trusted-envelope contracts are missing")

        schema = json.loads(CONSUMPTION_SCHEMA_PATH.read_text(encoding="utf-8"))
        owner = schema.get("properties", {}).get("owner", {}).get("const")
        self.assertEqual("adapter", owner, "KWI-CONTRACT-LLM-OWNER: only an adapter may own the envelope")
        policies = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        consumers = {item.get("consumer") for item in policies.get("policies", [])}
        self.assertEqual({"vdd", "quick-dev", "bootstrap"}, consumers, "KWI-CONTRACT-LLM-OWNER: trusted consumer policies are incomplete")

        policies_v2 = json.loads(POLICY_V2_PATH.read_text(encoding="utf-8"))
        consumers_v2 = {item.get("consumer") for item in policies_v2.get("policies", [])}
        self.assertEqual({"vdd", "quick-dev", "bootstrap", "refactor-acceptance"}, consumers_v2)

    def test_catalog_binds_source_snapshot_not_its_own_commit(self) -> None:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        self.assertEqual("refs/heads/main", catalog.get("authority_ref"))
        snapshot = catalog.get("source_snapshot", {})
        self.assertEqual("refs/heads/main", snapshot.get("ref"))
        self.assertRegex(snapshot.get("commit", ""), r"^[0-9a-f]{40}$")
        entry = next((item for item in catalog.get("entries", []) if item.get("entry_id") == "repository-rules"), None)
        self.assertIsNotNone(entry, "KWI-CATALOG-BOOTSTRAP: repository rules must be indexed")
        snapshot_bytes = subprocess.check_output(["git", "show", f"{snapshot['commit']}:AGENTS.md"], cwd=REPOSITORY_ROOT)
        self.assertEqual(hashlib.sha256(snapshot_bytes).hexdigest(), entry.get("source_sha256"))

    def test_typed_catalog_binds_four_dimensions_and_excludes_migration(self) -> None:
        catalog = json.loads(CATALOG_V2_PATH.read_text(encoding="utf-8"))
        self.assertEqual("derived_cache", catalog["authority_class"])
        self.assertFalse(catalog["instruction_authority"])
        self.assertFalse(catalog["may_override_source"])
        self.assertTrue(catalog["modules"])
        for module in catalog["modules"]:
            self.assertIn(module["primary_domain"], {"toolchain", "phase", "workspace", "marketplace"})
            self.assertEqual({"toolchain", "phase", "workspace", "marketplace"}, set(module["visibility"]))
            self.assertEqual("repository-source", module["lifecycle"])
            self.assertEqual("E1", module["enforcement_level"])
            self.assertFalse(module["source_path"].startswith("docs/migration/"))


if __name__ == "__main__":
    unittest.main()

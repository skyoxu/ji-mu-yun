from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PYTHON_ROOT = REPOSITORY_ROOT / "scripts" / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

import publish_knowledge_catalog as publication
from _knowledge_catalog_builder import build_layers
from _knowledge_locator_core import verify_current_publication


class KnowledgePublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        policy = json.loads((REPOSITORY_ROOT / publication.INPUT_PATHS["policy"]).read_text(encoding="utf-8"))
        exclusions = json.loads((REPOSITORY_ROOT / publication.INPUT_PATHS["exclusions"]).read_text(encoding="utf-8"))
        cls.layers = build_layers(REPOSITORY_ROOT, policy=policy, exclusions=exclusions)
        cls.policy = policy
        cls.exclusions = exclusions

    def test_layer_gate_accepts_current_builder_output_and_rejects_hash_drift(self) -> None:
        snapshot, catalog, projections, legacy = self.layers
        publication._validate_layers(snapshot, catalog, projections, legacy, self.policy, self.exclusions)
        broken = json.loads(json.dumps(projections))
        broken["catalog_sha256"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "projection_binding_invalid"):
            publication._validate_layers(snapshot, catalog, broken, legacy, self.policy, self.exclusions)

    def test_evaluation_gate_requires_full_adapter_decision_coverage(self) -> None:
        suite = {"cases": [{} for _ in range(100)]}
        categories = {
            name: {"matched_cases": 25, "failed": 0}
            for name in ("adr", "execution-plan", "architecture", "toolchain")
        }
        results = [
            {
                "status": "passed",
                "expected_result_status": "matched",
                "candidate_count": 1,
                "consumption_decisions": [{"decision": "accepted"}],
            }
            for _ in range(100)
        ]
        report = {
            "schema_version": "jimuyun.repository-knowledge-query-report.v1",
            "summary": {"status": "passed", "total": 100, "passed": 100, "failed": 0, "protocol_total": 4, "protocol_passed": 4},
            "categories": categories,
            "results": results,
        }
        publication._validate_evaluation(report, suite)
        report["results"][0]["consumption_decisions"] = []
        with self.assertRaisesRegex(ValueError, "adapter_consumption_decision_gate_failed"):
            publication._validate_evaluation(report, suite)

    def test_generation_pointer_verifies_all_runtime_artifact_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            layer_bytes = {name: b"{}\n" for name in publication.LAYER_PATHS}
            input_bytes = {name: b"{}\n" for name in publication.INPUT_PATHS}
            report = {
                "snapshot": {"snapshot_id": "sha256:" + "1" * 64},
                "policy_revision": "policy-v1",
                "summary": {"status": "passed"},
            }
            for name, path in publication.INPUT_PATHS.items():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(input_bytes[name])
            publication._publish_bundle(
                root,
                main_commit="a" * 40,
                layer_bytes=layer_bytes,
                input_bytes=input_bytes,
                report_bytes=b"{}\n",
                report=report,
            )
            self.assertTrue(
                verify_current_publication(
                    root,
                    catalog_path=root / publication.LAYER_PATHS["catalog_v2"],
                    policy_path=root / publication.INPUT_PATHS["policy"],
                    projections_path=root / publication.LAYER_PATHS["projections"],
                )
            )
            (root / publication.LAYER_PATHS["projections"]).write_bytes(b"tampered\n")
            self.assertFalse(
                verify_current_publication(
                    root,
                    catalog_path=root / publication.LAYER_PATHS["catalog_v2"],
                    policy_path=root / publication.INPUT_PATHS["policy"],
                    projections_path=root / publication.LAYER_PATHS["projections"],
                )
            )

    def test_lock_conflict_preserves_current_and_last_known_good(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            index_root = root / "knowledge" / "indexes"
            index_root.mkdir(parents=True)
            current = b'{"generation_id":"current"}\n'
            last_known_good = b'{"generation_id":"lkg"}\n'
            (index_root / "current.json").write_bytes(current)
            (index_root / "last-known-good.json").write_bytes(last_known_good)
            (index_root / "publication.lock").write_text("{}\n", encoding="utf-8", newline="\n")
            result = publication.run(root, publish=True, repeat=1)
            self.assertEqual("blocked", result["status"])
            self.assertEqual("knowledge_publication_lock_conflict", result["error"])
            self.assertEqual(current, (index_root / "current.json").read_bytes())
            self.assertEqual(last_known_good, (index_root / "last-known-good.json").read_bytes())


if __name__ == "__main__":
    unittest.main()

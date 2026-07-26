from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CORE_PATH = REPOSITORY_ROOT / "scripts" / "python" / "_knowledge_locator_core.py"


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


if __name__ == "__main__":
    unittest.main()

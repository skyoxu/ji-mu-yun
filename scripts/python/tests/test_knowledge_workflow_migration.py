from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


CORE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "python" / "_knowledge_locator_core.py"


def load_core():
    spec = importlib.util.spec_from_file_location("knowledge_locator_core", CORE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KnowledgeWorkflowMigrationTests(unittest.TestCase):
    def test_stale_catalog_requires_explicit_maintenance(self) -> None:
        core = load_core()
        result = core.require_fresh_catalog({"authority_ref": "refs/heads/main", "main_commit": "a" * 40}, "b" * 40)
        self.assertEqual("knowledge_refresh_required", result["status"])


if __name__ == "__main__":
    unittest.main()

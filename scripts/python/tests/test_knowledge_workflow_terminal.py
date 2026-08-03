from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts" / "python" / "validate_knowledge_workflow_integration.py"


class KnowledgeWorkflowTerminalTests(unittest.TestCase):
    def test_terminal_requires_all_consumers(self) -> None:
        if not VALIDATOR_PATH.is_file():
            self.fail("KWI-TERMINAL-CONSUMER: terminal knowledge workflow validator is missing")
        spec = importlib.util.spec_from_file_location("knowledge_workflow_terminal", VALIDATOR_PATH)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(
            ("vdd", "quick-dev", "bootstrap", "refactor-acceptance"),
            module.CONSUMERS,
        )
        check_names = {name for name, _command in module._declared_checks()}
        self.assertTrue(
            {"vdd", "quick-dev", "bootstrap", "refactor-acceptance"}
            <= check_names
        )


if __name__ == "__main__":
    unittest.main()

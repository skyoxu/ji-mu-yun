from __future__ import annotations

import json
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


class SchemaTests(unittest.TestCase):
    def test_s1_machine_contract_schemas_are_valid_json_schema_documents(self) -> None:
        names = [
            "acceptance-baseline-content-manifest.v1.schema.json",
            "acceptance-candidate-content-manifest.v1.schema.json",
            "code-review-policy-binding.v1.schema.json",
            "phase-diff-coverage-result.v1.schema.json",
            "task-checklist-closure.v1.schema.json",
            "phase-scan-bundle-result.v1.schema.json",
        ]
        for name in names:
            value = json.loads((SKILL_ROOT / "schemas" / name).read_text(encoding="utf-8"))
            self.assertEqual("https://json-schema.org/draft/2020-12/schema", value["$schema"])
            self.assertEqual("object", value["type"])
            self.assertIn("schemaVersion", value["required"])


if __name__ == "__main__":
    unittest.main()

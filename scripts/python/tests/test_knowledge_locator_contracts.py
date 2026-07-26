from __future__ import annotations

import json
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CONSUMPTION_SCHEMA_PATH = REPOSITORY_ROOT / "knowledge" / "contracts" / "knowledge-consumption-decision.v1.schema.json"
POLICY_PATH = REPOSITORY_ROOT / "knowledge" / "policies" / "consumer-policies.v1.json"


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


if __name__ == "__main__":
    unittest.main()

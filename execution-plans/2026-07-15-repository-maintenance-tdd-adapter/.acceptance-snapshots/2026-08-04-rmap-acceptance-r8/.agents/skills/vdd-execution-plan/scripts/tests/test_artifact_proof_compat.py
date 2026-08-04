from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = SKILL_ROOT / "scripts" / "artifact_proof_compat.py"


def load_module():
    spec = importlib.util.spec_from_file_location("vdd_artifact_proof_compat", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ArtifactProofCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()
        fixture = json.loads(
            (SKILL_ROOT / "scripts" / "fixtures" / "artifact-proof-root-policy-pass.json").read_text(encoding="utf-8")
        )
        cls.proof = fixture["proof"]

    def test_current_detached_root_is_valid(self) -> None:
        self.assertEqual([], self.module.validate_artifact_proof_trust_roots(SKILL_ROOT))

    def test_each_dimension_fails_closed(self) -> None:
        mutations = {
            "VDD-ARTIFACT-PROOF-PRODUCER": lambda value: value["schema_producer_authority"].update(authority_sha256="sha256:" + "0" * 64),
            "VDD-ARTIFACT-PROOF-IDENTITY": lambda value: value["immutable_identity"].update(mode="content-hash"),
            "VDD-ARTIFACT-PROOF-DERIVATION": lambda value: value["source_of_truth_derivation"].update(rules=[]),
            "VDD-ARTIFACT-PROOF-RULE": lambda value: value["independent_recomputation"].update(callable="validate_skill"),
            "VDD-ARTIFACT-PROOF-STALENESS": lambda value: value["staleness_propagation"].update(invalidates=[]),
            "VDD-ARTIFACT-PROOF-LINEAGE": lambda value: value["recovery_supersession"].update(predecessor_sha256=None),
            "VDD-ARTIFACT-PROOF-CONSUMER": lambda value: value["consumer_authorization_boundary"].update(authorizes=["plan-ready"]),
            "VDD-ARTIFACT-PROOF-APPLICABILITY": lambda value: value.update(proof_scope="runtime-instance"),
        }
        for rule_id, mutate in mutations.items():
            with self.subTest(rule_id=rule_id):
                proof = copy.deepcopy(self.proof)
                mutate(proof)
                findings = self.module.validate_artifact_proof_trust_roots(SKILL_ROOT, proof)
                self.assertEqual({rule_id}, {item["rule_id"] for item in findings})


if __name__ == "__main__":
    unittest.main()

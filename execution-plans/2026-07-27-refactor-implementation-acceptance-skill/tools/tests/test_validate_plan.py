from __future__ import annotations

import importlib.util
import copy
import json
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ria_plan_validator", TOOLS / "validate_plan.py")
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class RefactorAcceptancePlanTests(unittest.TestCase):
    def test_draft_directory_is_structurally_valid(self) -> None:
        self.assertEqual([], validator.validate())

    def test_required_ra_ids_are_unique_and_complete(self) -> None:
        ledger = validator.load("requirements-ledger.v1.json")
        ids = [value for item in ledger["coverage"] for value in item["ra_ids"]]
        self.assertEqual(list(range(1, 74)), sorted(ids))

    def test_stale_knowledge_snapshot_is_rejected(self) -> None:
        context = validator.load("knowledge-context.v1.json")
        catalog = json.loads((validator.REPOSITORY_ROOT / "knowledge/catalogs/repository-knowledge-catalog.v1.json").read_text(encoding="utf-8"))
        stale = copy.deepcopy(context)
        stale["locator_request"]["snapshot"]["commit"] = "0" * 40
        self.assertFalse(validator.validate_knowledge_context(stale, catalog))

    def test_stale_authority_manifest_is_rejected(self) -> None:
        manifest = validator.load("authority-manifest.v1.json")
        stale = copy.deepcopy(manifest)
        stale["sources"][-1]["sha256"] = "0" * 64
        self.assertFalse(validator.validate_authority_manifest(stale))

    def test_resume_rejects_unmet_slice_dependency(self) -> None:
        contract = validator.load("implementation-contract.v1.json")
        resume = validator.load("resume-state.v1.json")
        invalid = copy.deepcopy(resume)
        invalid["slice_status"]["S1-deterministic-core"] = "pending"
        invalid["slice_status"]["S2-matrix-phase"] = "in_progress"
        self.assertFalse(validator.validate_resume_dependencies(contract, invalid))


if __name__ == "__main__":
    unittest.main()

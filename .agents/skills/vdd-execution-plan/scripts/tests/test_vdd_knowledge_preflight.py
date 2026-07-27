from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_PATH = SKILL_ROOT / "scripts" / "vdd_knowledge_preflight.py"


def load_preflight():
    if not PREFLIGHT_PATH.is_file():
        raise FileNotFoundError(PREFLIGHT_PATH)
    spec = importlib.util.spec_from_file_location("vdd_knowledge_preflight", PREFLIGHT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VddKnowledgePreflightTests(unittest.TestCase):
    def test_all_rejected_candidates_block_plan_ready(self) -> None:
        try:
            module = load_preflight()
        except FileNotFoundError:
            self.fail("KWI-CONSUMPTION-REQUIRED-UNCOVERED: VDD knowledge preflight is missing")
        result = module.evaluate_consumption(
            required_modules=["repository-rules"],
            decisions=[{"decision": "rejected", "satisfies": []}],
        )
        self.assertEqual("blocked", result["status"])
        self.assertEqual(["repository-rules"], result["missing_required_modules"])

    def test_matched_locator_candidate_allows_required_module(self) -> None:
        module = load_preflight()
        snapshot = {"ref": "refs/heads/main", "commit": "a" * 40}
        result = module.evaluate_preflight(
            {
                "required_modules": ["repository-rules"],
                "locator_request": {
                    "schema_version": "jimuyun.knowledge-locator-request.v1",
                    "request_id": "request-1",
                    "snapshot": snapshot,
                },
                "locator_result": {
                    "schema_version": "jimuyun.knowledge-locator-result.v1",
                    "request_id": "request-1",
                    "snapshot": snapshot,
                    "status": "matched",
                    "candidates": [{"path": "AGENTS.md", "source_sha256": "b" * 64}],
                },
                "decisions": [{
                    "decision": "accepted",
                    "satisfies": ["repository-rules"],
                    "candidate": {"path": "AGENTS.md", "source_sha256": "b" * 64},
                }],
            }
        )
        self.assertEqual("ready", result["status"])

    def test_snapshot_mismatch_blocks_preflight(self) -> None:
        module = load_preflight()
        result = module.evaluate_preflight(
            {
                "required_modules": [],
                "locator_request": {"schema_version": "jimuyun.knowledge-locator-request.v1", "request_id": "request-1", "snapshot": {"ref": "refs/heads/main", "commit": "a" * 40}},
                "locator_result": {"schema_version": "jimuyun.knowledge-locator-result.v1", "request_id": "request-1", "snapshot": {"ref": "refs/heads/main", "commit": "b" * 40}, "status": "matched", "candidates": []},
                "decisions": [],
            }
        )
        self.assertEqual("blocked", result["status"])
        self.assertEqual("locator_snapshot_mismatch", result["failure_code"])

    def test_accepted_candidate_outside_locator_result_blocks_preflight(self) -> None:
        module = load_preflight()
        snapshot = {"ref": "refs/heads/main", "commit": "a" * 40}
        result = module.evaluate_preflight(
            {
                "required_modules": ["repository-rules"],
                "locator_request": {"schema_version": "jimuyun.knowledge-locator-request.v1", "request_id": "request-1", "snapshot": snapshot},
                "locator_result": {"schema_version": "jimuyun.knowledge-locator-result.v1", "request_id": "request-1", "snapshot": snapshot, "status": "matched", "candidates": [{"path": "README.md", "source_sha256": "a" * 64}]},
                "decisions": [{"decision": "accepted", "satisfies": ["repository-rules"], "candidate": {"path": "AGENTS.md", "source_sha256": "b" * 64}}],
            }
        )
        self.assertEqual("blocked", result["status"])
        self.assertEqual("accepted_candidate_not_locator_bound", result["failure_code"])


if __name__ == "__main__":
    unittest.main()

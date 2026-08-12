from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

from scripts.python._knowledge_catalog_builder import build_layers
from scripts.python._knowledge_locator_core import locate


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SUITE_PATH = REPOSITORY_ROOT / "knowledge" / "evaluation" / "repository-knowledge-query-suite.v1.json"
EVALUATOR_PATH = REPOSITORY_ROOT / "scripts" / "python" / "evaluate_knowledge_queries.py"
POLICY_PATH = REPOSITORY_ROOT / "knowledge" / "policies" / "consumer-policies.v2.json"
EXCLUSIONS_PATH = REPOSITORY_ROOT / "knowledge" / "policies" / "source-exclusions.v1.json"


def _load_evaluator():
    spec = importlib.util.spec_from_file_location("evaluate_knowledge_queries", EVALUATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load knowledge query evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KnowledgeQueryEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = json.loads(SUITE_PATH.read_text(encoding="utf-8"))

    def test_suite_has_25_distinct_queries_in_each_category(self) -> None:
        cases = self.suite["cases"]
        counts = Counter(case["category"] for case in cases)
        self.assertEqual(
            {"adr": 27, "execution-plan": 27, "architecture": 27, "toolchain": 27},
            dict(counts),
        )
        for category in counts:
            queries = [case["query"].casefold() for case in cases if case["category"] == category]
            self.assertEqual(27, len(set(queries)), f"duplicate query in {category}")

    def test_suite_has_positive_and_negative_oracles_per_category(self) -> None:
        for category in self.suite["categories"]:
            cases = [case for case in self.suite["cases"] if case["category"] == category]
            positive = [case for case in cases if case["expected"].get("result_status", "matched") == "matched"]
            negative = [case for case in cases if case["expected"].get("result_status") == "insufficient_match"]
            self.assertEqual(25, len(positive), category)
            self.assertEqual(2, len(negative), category)

    def test_suite_is_distributed_across_expected_modules(self) -> None:
        modules = {
            category: {
                case["expected"]["module_id"]
                for case in self.suite["cases"]
                if case["category"] == category and "module_id" in case["expected"]
            }
            for category in self.suite["categories"]
        }
        self.assertEqual(25, len(modules["adr"]))
        self.assertEqual(7, len(modules["execution-plan"]))
        self.assertEqual(25, len(modules["architecture"]))
        self.assertEqual(6, len(modules["toolchain"]))

    def test_canonical_toolchain_owner_queries_stay_within_rank_gate(self) -> None:
        # ADR-0048 requires deterministic ranking evidence for workflow consumers.
        policies = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        exclusions = json.loads(EXCLUSIONS_PATH.read_text(encoding="utf-8"))
        _, catalog, projections, _ = build_layers(
            REPOSITORY_ROOT,
            policy=policies,
            exclusions=exclusions,
            authority_ref="refs/heads/main",
        )
        policy_by_consumer = {item["consumer"]: item for item in policies["policies"]}
        eligible_by_consumer = {
            item["consumer"]: set(item["eligible_module_ids"])
            for item in projections["projections"]
        }
        cases = {
            case["case_id"]: case
            for case in self.suite["cases"]
            if case["case_id"] in {"TOOL-007", "TOOL-008", "TOOL-011"}
        }

        self.assertEqual({"TOOL-007", "TOOL-008", "TOOL-011"}, set(cases))
        for case_id, case in cases.items():
            consumer = case["consumer"]
            result = locate(
                {"query": case["query"]},
                catalog,
                policy=policy_by_consumer[consumer],
                eligible_module_ids=eligible_by_consumer[consumer],
            )
            ranked_ids = [candidate.get("module_id") for candidate in result["candidates"]]
            expected = case["expected"]
            rank = ranked_ids.index(expected["module_id"]) + 1
            self.assertLessEqual(rank, expected["max_rank"], case_id)

    def test_suite_validator_rejects_undercovered_category(self) -> None:
        evaluator = _load_evaluator()
        broken = {
            **self.suite,
            "cases": [
                case
                for case in self.suite["cases"]
                if case["case_id"] not in {"TOOL-025", "TOOL-N01", "TOOL-N02"}
            ],
        }
        with self.assertRaisesRegex(ValueError, "coverage"):
            evaluator._validate_suite(broken)

    def test_cli_runs_real_locator_and_verifies_one_case(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(EVALUATOR_PATH), "--case-id", "ADR-018", "--repeat", "1"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        catalog = json.loads((REPOSITORY_ROOT / "knowledge/catalogs/repository-knowledge-catalog.v2.json").read_text(encoding="utf-8"))
        current_main = subprocess.check_output(
            ["git", "rev-parse", "refs/heads/main"], cwd=REPOSITORY_ROOT, text=True, encoding="ascii"
        ).strip()
        if catalog["source_snapshot"]["commit"] != current_main:
            self.assertEqual(2, completed.returncode)
            self.assertEqual("blocked", json.loads(completed.stdout)["status"])
        else:
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            summary = json.loads(completed.stdout)
            self.assertEqual("passed", summary["status"])
            self.assertEqual((1, 1, 0), (summary["total"], summary["passed"], summary["failed"]))
            self.assertEqual((4, 4, 0), (summary["protocol_total"], summary["protocol_passed"], summary["protocol_failed"]))

    def test_generated_answer_fields_are_rejected_recursively(self) -> None:
        evaluator = _load_evaluator()
        response = {"candidates": [{"rank_evidence": {"answer": "not allowed"}}]}
        self.assertEqual(["$.candidates[0].rank_evidence.answer"], evaluator._forbidden_response_paths(response))

    def test_consumption_decisions_are_adapter_owned_and_complete(self) -> None:
        evaluator = _load_evaluator()
        candidates = [
            {"module_id": "expected", "path": "docs/a.md", "source_sha256": "a" * 64},
            {"module_id": "other", "path": "docs/b.md", "source_sha256": "b" * 64},
        ]
        decisions = evaluator._consumption_decisions("ADR-001", candidates, "expected", True)
        self.assertEqual(2, len(decisions))
        self.assertEqual(("accepted", ["ADR-001"], None), (decisions[0]["decision"], decisions[0]["satisfies"], decisions[0]["rejection_reason"]))
        self.assertEqual(("rejected", [], "insufficient_specificity"), (decisions[1]["decision"], decisions[1]["satisfies"], decisions[1]["rejection_reason"]))


if __name__ == "__main__":
    unittest.main()

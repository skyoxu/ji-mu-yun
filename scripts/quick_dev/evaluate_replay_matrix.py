#!/usr/bin/env python3
"""Measure Chapter 4/5/6 selective replay decisions against the frozen matrix.

This is intentionally independent of change-impact-matrix.v1.json: expected
outcomes are encoded from the normative SPEC so the evaluator cannot simply
compare the matrix to itself.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from current_router import recommendation

HASH = "sha256:" + "a" * 64

EXPECTED = {
    "requirement_or_acceptance": {"coverage", "red", "green", "refactor", "terminal"},
    "selector_fixture_target_case_source": {"red", "green", "refactor", "terminal"},
    "production_owner": {"green", "refactor", "terminal"},
    "failure_semantics": {"red", "green", "refactor", "terminal"},
    "descriptor_compiler": {"descriptor", "red", "green", "refactor", "terminal"},
    "validator_or_judge": {"red", "green", "refactor", "terminal"},
    "predecessor": {"successors", "terminal"},
    "ordinary_documentation": set(),
    "development_governance": set(),
}

LIFECYCLE = {
    "planned-only": "run-preflight",
    "preflight-passed": "author-red",
    "red-materialized": "run-red",
    "red-observed": "implement",
    "implementation-successor": "run-green",
    "green-observed": "run-refactor",
    "refactor-observed": "validate-slice",
    "slice-ready": "run-terminal",
    "whole-plan-terminal": "stop",
}

OBSERVATIONS = [
    {"observation_id": "OBS-RED", "slice_id": "S1", "stage": "red", "current_snapshot_sha256": HASH},
    {"observation_id": "OBS-GREEN", "slice_id": "S1", "stage": "green", "current_snapshot_sha256": HASH},
    {"observation_id": "OBS-REFACTOR", "slice_id": "S1", "stage": "refactor", "current_snapshot_sha256": HASH},
    {"observation_id": "OBS-TERMINAL", "slice_id": "S1", "stage": "terminal", "current_snapshot_sha256": HASH},
]

BUNDLE = {
    "plan_id": "PLAN-METRIC",
    "slices": [{
        "slice_id": "S1",
        "production_owners": ["src/subject.py"],
        "execution_snapshot_paths": ["tests/test_subject.py", "tests/fixture.json"],
    }],
}


def _expected_action(stages: set[str], lifecycle: str) -> str:
    if "red" in stages:
        return "run-red"
    if "green" in stages:
        return "run-green"
    return LIFECYCLE[lifecycle]


def _expected_observations(stages: set[str]) -> tuple[list[str], list[str]]:
    invalidated = sorted(
        item["observation_id"] for item in OBSERVATIONS if item["stage"] in stages
    )
    reusable = sorted(
        item["observation_id"] for item in OBSERVATIONS if item["stage"] not in stages
    )
    return reusable, invalidated


def _case(case_id: str, kinds: Iterable[str], lifecycle: str) -> dict:
    kinds = tuple(sorted(set(kinds)))
    stages: set[str] = set()
    for kind in kinds:
        stages.update(EXPECTED[kind])
    return {
        "case_id": case_id,
        "change_kinds": kinds,
        "lifecycle": lifecycle,
        "expected_stages": stages,
        "expected_action": _expected_action(stages, lifecycle),
    }


def corpus() -> list[dict]:
    cases: list[dict] = []
    # 81 unique single-change/lifecycle combinations.
    for kind in EXPECTED:
        for lifecycle in LIFECYCLE:
            cases.append(_case(f"single-{kind}-{lifecycle}", [kind], lifecycle))
    # 19 mixed changes exercise union/transitive behavior without inflating one class.
    mixed = [
        ("requirement_or_acceptance", "ordinary_documentation"),
        ("selector_fixture_target_case_source", "development_governance"),
        ("production_owner", "ordinary_documentation"),
        ("failure_semantics", "production_owner"),
        ("descriptor_compiler", "validator_or_judge"),
        ("validator_or_judge", "predecessor"),
        ("predecessor", "ordinary_documentation"),
        ("requirement_or_acceptance", "descriptor_compiler"),
        ("selector_fixture_target_case_source", "validator_or_judge"),
        ("production_owner", "predecessor"),
        ("failure_semantics", "development_governance"),
        ("descriptor_compiler", "ordinary_documentation"),
        ("requirement_or_acceptance", "failure_semantics"),
        ("selector_fixture_target_case_source", "production_owner"),
        ("validator_or_judge", "development_governance"),
        ("predecessor", "development_governance"),
        ("ordinary_documentation", "development_governance"),
        ("requirement_or_acceptance", "predecessor"),
        ("descriptor_compiler", "production_owner"),
    ]
    lifecycle_names = list(LIFECYCLE)
    for index, pair in enumerate(mixed):
        lifecycle = lifecycle_names[index % len(lifecycle_names)]
        cases.append(_case(f"mixed-{index + 1:02d}", pair, lifecycle))
    if len(cases) != 100:
        raise AssertionError(f"metric corpus must contain exactly 100 cases, got {len(cases)}")
    return cases


def evaluate() -> dict:
    failures: list[dict] = []
    for case in corpus():
        result = recommendation(
            bundle=BUNDLE,
            slice_id="S1",
            state={"state": case["lifecycle"]},
            changed_paths=[],
            change_kinds=list(case["change_kinds"]),
            profile="standard",
            observation_index=OBSERVATIONS,
            current_snapshot_sha256=HASH,
        )
        expected_reusable, expected_invalidated = _expected_observations(case["expected_stages"])
        checks = {
            "invalidated_stages": set(result["invalidated_stages"]) == case["expected_stages"],
            "recommended_action": result["recommended_action"] == case["expected_action"],
            "reusable_observations": result["reusable_observations"] == expected_reusable,
            "invalidated_observations": result["invalidated_observations"] == expected_invalidated,
        }
        if not all(checks.values()):
            failures.append({
                "case_id": case["case_id"],
                "change_kinds": list(case["change_kinds"]),
                "lifecycle": case["lifecycle"],
                "checks": checks,
                "actual": result,
            })
    total = 100
    passed = total - len(failures)
    accuracy = passed / total
    return {
        "schema": "quick-dev.selective-replay-metric.v1",
        "total_cases": total,
        "passed_cases": passed,
        "failed_cases": len(failures),
        "accuracy": accuracy,
        "required_accuracy": 0.99,
        "status": "pass" if accuracy >= 0.99 else "fail",
        "failures": failures,
        "authorizes": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = evaluate()
    text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

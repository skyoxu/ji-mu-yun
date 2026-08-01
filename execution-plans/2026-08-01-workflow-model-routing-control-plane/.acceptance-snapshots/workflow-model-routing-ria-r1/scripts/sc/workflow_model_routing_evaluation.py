#!/usr/bin/env python3
"""Non-authorizing shadow evaluation for workflow model route candidates."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import workflow_model_routing as routing


DEFAULT_FIXTURE = (
    Path(__file__).resolve().parent
    / "config"
    / "workflow_model_routing_shadow_cases.v1.json"
)


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6)


def evaluate_shadow_fixture(
    fixture: dict[str, Any], *, policy: dict[str, Any] | None = None
) -> dict[str, Any]:
    current = policy or routing.load_policy()
    if (
        not isinstance(fixture, dict)
        or fixture.get("schemaVersion")
        != "jimuyun.workflow-model-routing-shadow-fixture.v1"
        or fixture.get("evaluationMode") != "synthetic_contract_replay"
        or fixture.get("authorizes") != []
    ):
        raise routing.RoutingError("workflow model shadow fixture is invalid")
    cohorts = fixture.get("cohorts")
    if not isinstance(cohorts, list) or not cohorts:
        raise routing.RoutingError("workflow model shadow cohorts are missing")

    results: list[dict[str, Any]] = []
    for cohort in cohorts:
        if not isinstance(cohort, dict):
            raise routing.RoutingError("workflow model shadow cohort is invalid")
        route_id = cohort.get("routeId")
        route = current["routes"].get(route_id)
        samples = cohort.get("samples")
        if not isinstance(route, dict) or not isinstance(samples, list) or not samples:
            raise routing.RoutingError("workflow model shadow route or samples are invalid")
        candidate_model = cohort.get("candidateModel")
        if not isinstance(candidate_model, str) or not candidate_model.startswith("gpt-"):
            raise routing.RoutingError("workflow model shadow candidate identity is invalid")

        baseline_passes: list[float] = []
        candidate_passes: list[float] = []
        baseline_latency: list[float] = []
        candidate_latency: list[float] = []
        baseline_cost: list[float] = []
        candidate_cost: list[float] = []
        for sample in samples:
            if not isinstance(sample, dict):
                raise routing.RoutingError("workflow model shadow sample is invalid")
            boolean_fields = ("baselinePredicatePassed", "candidatePredicatePassed")
            numeric_fields = (
                "baselineLatencyMs", "candidateLatencyMs",
                "baselineCostUsd", "candidateCostUsd",
            )
            if any(not isinstance(sample.get(name), bool) for name in boolean_fields):
                raise routing.RoutingError("workflow model shadow predicate result is invalid")
            if any(
                not isinstance(sample.get(name), (int, float))
                or isinstance(sample.get(name), bool)
                or sample[name] < 0
                for name in numeric_fields
            ):
                raise routing.RoutingError("workflow model shadow metric is invalid")
            baseline_passes.append(float(sample["baselinePredicatePassed"]))
            candidate_passes.append(float(sample["candidatePredicatePassed"]))
            baseline_latency.append(float(sample["baselineLatencyMs"]))
            candidate_latency.append(float(sample["candidateLatencyMs"]))
            baseline_cost.append(float(sample["baselineCostUsd"]))
            candidate_cost.append(float(sample["candidateCostUsd"]))

        quality_ok = all(candidate_passes) and _mean(candidate_passes) >= _mean(baseline_passes)
        capability_ok = cohort.get("exactCapabilityStatus") == "passed"
        representative = cohort.get("representativeExecution") is True
        activation_eligible = quality_ok and capability_ok and representative
        results.append({
            "cohortId": cohort.get("cohortId"),
            "routeId": route_id,
            "candidateModel": candidate_model,
            "sampleCount": len(samples),
            "quality": {
                "baselinePredicatePassRate": _mean(baseline_passes),
                "candidatePredicatePassRate": _mean(candidate_passes),
                "passed": quality_ok,
            },
            "latencyMs": {
                "baselineMean": _mean(baseline_latency),
                "candidateMean": _mean(candidate_latency),
            },
            "costUsd": {
                "baselineMean": _mean(baseline_cost),
                "candidateMean": _mean(candidate_cost),
            },
            "exactCapabilityStatus": cohort.get("exactCapabilityStatus"),
            "representativeExecution": representative,
            "activationEligible": activation_eligible,
            "activationRecommendation": "eligible_for_policy_review" if activation_eligible else "keep_disabled",
            "authorizes": [],
        })

    report = {
        "schemaVersion": "jimuyun.workflow-model-routing-shadow-report.v1",
        "policyRevision": current["policyRevision"],
        "policyHash": routing.canonical_hash(current),
        "evaluationMode": fixture["evaluationMode"],
        "cohorts": results,
        "activationEligibleRoutes": [
            item["routeId"] for item in results if item["activationEligible"]
        ],
        "status": "pass",
        "authorizes": [],
    }
    report["reportId"] = routing.canonical_hash(report)
    return report


def write_report(report: dict[str, Any], output: Path) -> None:
    if report.get("authorizes") != []:
        raise routing.RoutingError("workflow model shadow report cannot authorize activation")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    report = evaluate_shadow_fixture(fixture)
    if args.output:
        write_report(report, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

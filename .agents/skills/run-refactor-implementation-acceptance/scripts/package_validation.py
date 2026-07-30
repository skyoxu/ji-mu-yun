"""Deterministic package closure for the implementation-acceptance Skill."""

from __future__ import annotations

import json
from pathlib import Path


REQUIRED = (
    "SKILL.md",
    "scripts/acceptance_cli.py",
    "scripts/acceptance_core.py",
    "scripts/knowledge_context.py",
    "scripts/prepare_knowledge_context.py",
    "scripts/evidence_analysis.py",
    "scripts/phase_scan.py",
    "scripts/task_checklist.py",
    "scripts/check_lineage.py",
    "scripts/source_clauses.py",
    "scripts/requirement_inventory.py",
    "scripts/matrix_phase.py",
    "scripts/execution_control.py",
    "scripts/bootstrap_integration.py",
    "scripts/repair_completeness.py",
    "scripts/review_cycle_policy.py",
    "policies/phase-service-code-review.v1.json",
    "schemas/acceptance-run-input.v1.schema.json",
    "schemas/bootstrap-import-envelope.v2.schema.json",
    "schemas/acceptance-repair-completeness.v1.schema.json",
    "schemas/acceptance-baseline-content-manifest.v1.schema.json",
    "schemas/acceptance-candidate-content-manifest.v1.schema.json",
    "schemas/code-review-policy-binding.v1.schema.json",
    "schemas/phase-diff-coverage-result.v1.schema.json",
    "schemas/task-checklist-closure.v1.schema.json",
    "schemas/phase-scan-bundle-result.v1.schema.json",
    "schemas/check-id-lineage.v1.schema.json",
    "schemas/typed-gate-result.v1.schema.json",
    "schemas/acceptance-impact-projection.v1.schema.json",
    "schemas/implementation-acceptance-matrix.v1.schema.json",
    "schemas/phase-graph.v1.schema.json",
    "schemas/phase-acceptance-candidate.v1.schema.json",
    "schemas/program-dod-candidate.v1.schema.json",
    "schemas/acceptance-source-clauses.v1.schema.json",
    "fixtures/negative-cases.v1.json",
    "tests/test_run_input.py",
    "tests/test_evidence_analysis.py",
    "tests/test_phase_scan.py",
    "tests/test_task_checklist.py",
    "tests/test_check_lineage.py",
    "tests/test_source_clauses.py",
    "tests/test_requirement_inventory.py",
    "tests/test_matrix_phase.py",
    "tests/test_control.py",
    "tests/test_bootstrap_integration.py",
    "tests/test_repair_completeness.py",
    "tests/test_package.py",
    "tests/test_knowledge_context.py",
)

REQUIRED_FIXTURE_CATEGORIES = (
    "positive",
    "negative",
    "mutation",
    "plan-7-07",
    "pure-godot",
    "mixed-domain",
    "fresh-context",
)


def validate_fixture_catalog(value: object) -> list[str]:
    """Validate that release-candidate fixtures cover the declared execution domains."""
    if not isinstance(value, dict) or value.get("schemaVersion") != "refactor-acceptance-negative-cases.v1":
        return ["fixture-catalog-invalid"]
    categories = value.get("categories")
    cases = value.get("cases")
    if not isinstance(categories, list) or any(not isinstance(category, str) or not category for category in categories) or len(categories) != len(set(categories)):
        return ["fixture-catalog-categories-invalid"]
    if not isinstance(cases, list) or not cases or any(not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"] or not isinstance(case.get("expect"), str) or not case["expect"] for case in cases):
        return ["fixture-catalog-cases-invalid"]
    findings: list[str] = []
    declared = set(categories)
    for category in REQUIRED_FIXTURE_CATEGORIES:
        if category not in declared:
            findings.append("missing-fixture-category:" + category)
            continue
        if category == "negative":
            covered = any(str(case.get("id", "")).startswith("RA-NEG-") for case in cases)
        else:
            covered = any(case.get("category") == category for case in cases)
        if not covered:
            findings.append("missing-fixture-case:" + category)
    return findings


def validate_package(skill_root: Path) -> list[str]:
    findings = [f"missing:{relative}" for relative in REQUIRED if not (skill_root / relative).is_file()]
    fixture_path = skill_root / "fixtures" / "negative-cases.v1.json"
    if fixture_path.is_file():
        try:
            findings.extend(validate_fixture_catalog(json.loads(fixture_path.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError):
            findings.append("fixture-catalog-unreadable")
    return findings

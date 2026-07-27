"""Validate the refactor implementation acceptance Skill execution plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]
SOURCE = "execution-plans/2026-07-15-refactor-implementation-acceptance-skill-requirements.md"
SLICES = [
    "S0-bootstrap-companion",
    "S1-deterministic-core",
    "S2-matrix-phase",
    "S3-execution-control",
    "S4-bootstrap-integration",
    "S5-finalize-release-candidate",
]
FORBIDDEN = {"logs/phase-a-innernet/**", "runtime/phase-a/**", "PhaseA.Platform/**", "PhaseA.Platform.Tests/**", SOURCE}


def load(relative: str) -> dict:
    return json.loads((PLAN_ROOT / relative).read_text(encoding="utf-8"))


def sha256(relative: str) -> str:
    return hashlib.sha256((REPOSITORY_ROOT / relative).read_bytes()).hexdigest()


def validate() -> list[str]:
    findings: list[str] = []
    required = [
        "00-index.md", "01-requirements-and-acceptance.md", "requirements-ledger.v1.json",
        "implementation-contract.v1.json", "knowledge-context.v1.json", "authority-manifest.v1.json",
        "plan-state.v1.json", "resume-state.v1.json", "fixtures/negative-cases.v1.json",
        "95-implementation-evolution-and-completion-report.md",
    ]
    for relative in required:
        if not (PLAN_ROOT / relative).is_file():
            findings.append(f"RIA-PLAN-REQUIRED-FILE:{relative}")
    if findings:
        return findings

    ledger = load("requirements-ledger.v1.json")
    source = ledger.get("source", {})
    if source.get("path") != SOURCE or source.get("sha256") != sha256(SOURCE):
        findings.append("RIA-PLAN-SOURCE-HASH")
    ids = [value for item in ledger.get("coverage", []) for value in item.get("ra_ids", [])]
    if sorted(ids) != list(range(1, 74)):
        findings.append("RIA-PLAN-RA-COVERAGE")

    contract = load("implementation-contract.v1.json")
    actual_slices = [item.get("id") for item in contract.get("slices", [])]
    if actual_slices != SLICES:
        findings.append("RIA-PLAN-SLICE-ORDER")
    elif contract.get("global_forbidden_changes") is None or not FORBIDDEN.issubset(set(contract["global_forbidden_changes"])):
        findings.append("RIA-PLAN-FORBIDDEN")
    else:
        by_id = {item["id"]: item for item in contract["slices"]}
        if by_id["S4-bootstrap-integration"].get("depends_on") != SLICES[:4] or by_id["S5-finalize-release-candidate"].get("depends_on") != SLICES[:5]:
            findings.append("RIA-PLAN-SLICE-DEPENDENCIES")

    context = load("knowledge-context.v1.json")
    state = load("plan-state.v1.json")
    index = (PLAN_ROOT / "00-index.md").read_text(encoding="utf-8")
    if state.get("status") == "draft":
        if context.get("status") != "blocked" or context.get("missing_required_modules") != ["repository-rules"] or context.get("decisions") != []:
            findings.append("RIA-PLAN-KNOWLEDGE-CONTEXT")
    elif state.get("status") == "plan-ready":
        decisions = context.get("decisions", [])
        accepted = [item for item in decisions if item.get("decision") == "accepted" and item.get("satisfies") == ["repository-rules"]]
        candidate = accepted[0].get("candidate", {}) if len(accepted) == 1 else {}
        if context.get("status") != "ready" or context.get("missing_required_modules") != [] or context.get("locator_result", {}).get("status") != "matched" or candidate != {"path": "AGENTS.md", "source_sha256": sha256("AGENTS.md")}:
            findings.append("RIA-PLAN-KNOWLEDGE-CONTEXT")
    else:
        findings.append("RIA-PLAN-KNOWLEDGE-CONTEXT")
    expected_authorizes = [] if state.get("status") == "draft" else ["plan-ready"]
    if state.get("authorizes") != expected_authorizes or not re.search(rf"^- Status: {re.escape(state.get('status', 'invalid'))}$", index, re.MULTILINE):
        findings.append("RIA-PLAN-DRAFT-PROJECTION")
    resume = load("resume-state.v1.json")
    if list(resume.get("slice_status", {})) != SLICES or set(resume.get("slice_status", {}).values()) != {"pending"} or resume.get("live_phase_paths_allowed") is not False:
        findings.append("RIA-PLAN-RESUME")
    report_index = json.loads((REPOSITORY_ROOT / "execution-plans/95-implementation-report-index.v1.json").read_text(encoding="utf-8"))
    report_entry = {"plan_directory": PLAN_ROOT.name, "report_filename": "95-implementation-evolution-and-completion-report.md"}
    if report_entry not in report_index.get("entries", []):
        findings.append("RIA-PLAN-REPORT-INDEX")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-plan-ready", action="store_true")
    args = parser.parse_args()
    findings = validate()
    state = load("plan-state.v1.json") if not findings else {"status": "invalid"}
    result = {"schema_version": "refactor-acceptance.plan-validation.v1", "status": "pass" if not findings else "fail", "plan_state": state["status"], "findings": findings, "authorizes": []}
    print(json.dumps(result, sort_keys=True))
    return 0 if not findings and (not args.require_plan_ready or state["status"] == "plan-ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Validate the refactor implementation acceptance Skill execution plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]
KNOWLEDGE_SCRIPTS = REPOSITORY_ROOT / "scripts" / "python"
if str(KNOWLEDGE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(KNOWLEDGE_SCRIPTS))

from knowledge_context_validation import validate_context

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


def object_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def locate(request: dict) -> dict:
    completed = subprocess.run(
        [sys.executable, "-B", str(REPOSITORY_ROOT / "scripts/python/knowledge_locator.py")],
        input=json.dumps(request),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError("locator invocation failed")
    return json.loads(completed.stdout)


def validate_knowledge_context(context: dict, catalog: dict) -> bool:
    del catalog
    return (
        validate_context(
            context,
            repository_root=REPOSITORY_ROOT,
            verify_catalog=True,
            verify_sources=True,
        ) is None
        and context.get("preflight", {}).get("status") == "ready"
    )


def validate_authority_manifest(manifest: dict) -> bool:
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        return False
    roles: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            return False
        path, role, expected_hash = source.get("path"), source.get("role"), source.get("sha256")
        if not all(isinstance(value, str) and value for value in (path, role, expected_hash)) or role in roles:
            return False
        candidate = (REPOSITORY_ROOT / path).resolve()
        try:
            candidate.relative_to(REPOSITORY_ROOT.resolve())
        except ValueError:
            return False
        if not candidate.is_file() or hashlib.sha256(candidate.read_bytes()).hexdigest() != expected_hash:
            return False
        roles.add(role)
    return True


def validate_resume_dependencies(contract: dict, resume: dict) -> bool:
    statuses = resume.get("slice_status")
    slices = contract.get("slices")
    if not isinstance(statuses, dict) or not isinstance(slices, list):
        return False
    dependencies = {
        item.get("id"): item.get("depends_on")
        for item in slices
        if isinstance(item, dict) and isinstance(item.get("id"), str) and isinstance(item.get("depends_on"), list)
    }
    if list(statuses) != SLICES or set(dependencies) != set(SLICES):
        return False
    allowed = {"pending", "in_progress", "completed"}
    for slice_id, status in statuses.items():
        if status not in allowed:
            return False
        if status != "pending" and any(statuses.get(dependency) != "completed" for dependency in dependencies[slice_id]):
            return False
    return True


def validate() -> list[str]:
    findings: list[str] = []
    required = [
        "00-index.md", "01-requirements-and-acceptance.md", "requirements-ledger.v1.json",
        "implementation-contract.v1.json", "knowledge-context.v1.json", "authority-manifest.v1.json",
        "plan-state.v1.json", "resume-state.v1.json", "fixtures/negative-cases.v1.json",
        "tools/bootstrap-preflight-commands.v1.json",
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

    if not validate_authority_manifest(load("authority-manifest.v1.json")):
        findings.append("RIA-PLAN-AUTHORITY-MANIFEST")

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
    catalog = json.loads((REPOSITORY_ROOT / "knowledge/catalogs/repository-knowledge-catalog.v1.json").read_text(encoding="utf-8"))
    state = load("plan-state.v1.json")
    index = (PLAN_ROOT / "00-index.md").read_text(encoding="utf-8")
    status = state.get("status")
    if status == "draft":
        if context.get("preflight", {}).get("status") != "blocked":
            findings.append("RIA-PLAN-KNOWLEDGE-CONTEXT")
    elif status in {"plan-ready", "implementation-authorized"}:
        if not validate_knowledge_context(context, catalog):
            findings.append("RIA-PLAN-KNOWLEDGE-CONTEXT")
    else:
        findings.append("RIA-PLAN-KNOWLEDGE-CONTEXT")
    expected_authorizes = [] if status == "draft" else [status]
    if state.get("authorizes") != expected_authorizes or not re.search(rf"^- Status: {re.escape(state.get('status', 'invalid'))}$", index, re.MULTILINE):
        findings.append("RIA-PLAN-DRAFT-PROJECTION")
    resume = load("resume-state.v1.json")
    if not validate_resume_dependencies(contract, resume) or resume.get("live_phase_paths_allowed") is not False:
        findings.append("RIA-PLAN-RESUME")
    report_index = json.loads((REPOSITORY_ROOT / "execution-plans/95-implementation-report-index.v1.json").read_text(encoding="utf-8"))
    report_entry = {"plan_directory": PLAN_ROOT.name, "report_filename": "95-implementation-evolution-and-completion-report.md"}
    if report_entry not in report_index.get("entries", []):
        findings.append("RIA-PLAN-REPORT-INDEX")
    registry = load("tools/bootstrap-preflight-commands.v1.json")
    expected_commands = {
        "scope-structure-and-links",
        "schema-and-fixture-parse",
        "plan-composite-validator",
    }
    command_ids = {item.get("id") for item in registry.get("commands", []) if isinstance(item, dict)}
    if command_ids != expected_commands:
        findings.append("RIA-PLAN-PREFLIGHT-REGISTRY")
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

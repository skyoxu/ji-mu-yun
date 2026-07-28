"""Validate the refactor implementation acceptance Skill execution plan."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
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
ACCEPTANCE_SKILL_SCRIPTS = REPOSITORY_ROOT / ".agents" / "skills" / "run-refactor-implementation-acceptance" / "scripts"
if str(ACCEPTANCE_SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ACCEPTANCE_SKILL_SCRIPTS))

from knowledge_context_validation import validate_context
from requirement_inventory import RequirementInventoryError, extract_requirement_inventory

SOURCE = "execution-plans/2026-07-15-refactor-implementation-acceptance-skill-requirements.md"
SLICES = [
    "S0-bootstrap-companion",
    "S1-deterministic-core",
    "S2-matrix-phase",
    "S3-execution-control",
    "S4-bootstrap-integration",
    "S5-finalize-release-candidate",
]
RMAP_SLICES = [f"RMAP-S{index}" for index in range(6)]
FORBIDDEN = {"logs/phase-a-innernet/**", "runtime/phase-a/**", "PhaseA.Platform/**", "PhaseA.Platform.Tests/**", SOURCE}
REPAIR_FINDINGS_BY_ROUND = {
    2: {
    "BSR-61F0256FC98B5843", "BSR-64AF933AD78CBC9C", "BSR-7C3C4102B3C9D0A1",
    "BSR-D29578D25669D4C4", "BSR-E6107BFF207C275C", "BSR-EF41592109D09BAE",
    "BSR-F0AB766557297612",
    },
    3: {
        "BSR-3BB3B873C4C0B09E", "BSR-4630976C15F6FDEA", "BSR-75E54594466B6EA2",
        "BSR-B757809A60227AD0", "BSR-FF35EB3EE83AF41E",
    },
}
SUCCESSOR_FINDINGS = {
    "BSR-1DA101461E3AB315", "BSR-483D0ED3EA11ED82",
    "BSR-4F4C6B99E5533234", "BSR-ED73EE2E7BF8E0E6",
    "BSR-45D6FEA28AE59B11", "BSR-59FC2E4560070011",
    "BSR-A835D3DFFBC54206",
}


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
    rmap_to_business = {
        item.get("slice_id"): item.get("id")
        for item in slices
        if isinstance(item, dict) and isinstance(item.get("slice_id"), str) and isinstance(item.get("id"), str)
    }
    dependencies = {
        item.get("id"): [rmap_to_business.get(value, value) for value in item.get("depends_on", [])]
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


def validate_repair_rounds() -> bool:
    root = PLAN_ROOT / "repair"
    if not root.exists():
        return True
    rounds = sorted(path for path in root.iterdir() if path.is_dir())
    if [path.name for path in rounds] != [f"round-{index}" for index in range(2, 2 + len(rounds))]:
        return False
    for index, directory in enumerate(rounds, start=2):
        expected_findings = REPAIR_FINDINGS_BY_ROUND.get(index)
        if expected_findings is None:
            return False
        path = directory / "repair-plan.v1.json"
        try:
            repair = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        slices = repair.get("slices")
        if (
            repair.get("schemaVersion") != "refactor-acceptance.repair-round.v1"
            or repair.get("round") != index
            or repair.get("status") not in {"planned", "in_progress", "implemented"}
            or not isinstance(repair.get("predecessorReview"), str)
            or not repair["predecessorReview"].startswith("logs/ci/")
            or set(repair.get("findingIds", [])) != expected_findings
            or not isinstance(slices, list)
            or not slices
            or len({item.get("id") for item in slices if isinstance(item, dict)}) != len(slices)
            or repair.get("authorizes") != []
        ):
            return False
        for item in slices:
            if not isinstance(item, dict) or not set(item.get("findings", [])).issubset(expected_findings):
                return False
            roots = item.get("writeRoots")
            if not isinstance(roots, list) or not roots or any(not isinstance(value, str) or not value.startswith(".agents/skills/") for value in roots):
                return False
            snapshots = item.get("execution_snapshot_paths")
            commands = item.get("commands")
            if (
                not isinstance(snapshots, list)
                or not snapshots
                or any(not isinstance(value, str) or value not in roots for value in snapshots)
                or not isinstance(commands, dict)
                or set(commands) != {"red", "green", "refactor"}
                or any(not isinstance(value, str) or not value for value in commands.values())
            ):
                return False
    return True


def validate_successor_round() -> bool:
    lineage_path = PLAN_ROOT / "successor-lineage.v1.json"
    round_path = PLAN_ROOT / "successor" / "round-1" / "repair-plan.v1.json"
    try:
        lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
        repair = json.loads(round_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    reference = lineage.get("policyDecisionRef") if isinstance(lineage, dict) else None
    if (
        lineage.get("schemaVersion") != "refactor-acceptance.successor-lineage.v1"
        or lineage.get("supersededRun") != "logs/ci/2026-07-28/review-gateway-bootstrap-rmap-7-27-round3"
        or lineage.get("successorChangeId") != "refactor-implementation-acceptance-skill-successor-v3"
        or lineage.get("authorizes") != []
        or not isinstance(reference, dict)
        or set(reference) != {"path", "sha256"}
        or reference["path"] != "decision-logs/2026-07-28-refactor-implementation-acceptance-successor/policy-decision.json"
        or reference["sha256"] != "sha256:" + sha256(reference["path"])
    ):
        return False
    try:
        spec = importlib.util.spec_from_file_location("bootstrap_review", REPOSITORY_ROOT / ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py")
        if spec is None or spec.loader is None:
            return False
        bootstrap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bootstrap)
        bootstrap.validate_successor_policy_authorization(REPOSITORY_ROOT, json.loads((REPOSITORY_ROOT / reference["path"]).read_text(encoding="utf-8")))
    except Exception:
        return False
    slices = repair.get("slices")
    return (
        repair.get("schemaVersion") == "refactor-acceptance.successor-round.v1"
        and repair.get("round") == 1
        and repair.get("status") in {"planned", "in_progress", "implemented"}
        and repair.get("lineage") == "successor-lineage.v1.json"
        and set(repair.get("findingIds", [])) == SUCCESSOR_FINDINGS
        and repair.get("authorizes") == []
        and isinstance(slices, list)
        and {item.get("id") for item in slices if isinstance(item, dict)} == {"SUC1-policy-path-coverage", "SUC1-changed-line-manifest-binding", "SUC1-phase-scan-policy-parity"}
        and all(
            isinstance(item, dict)
            and set(item.get("findings", [])).issubset(SUCCESSOR_FINDINGS)
            and item.get("writeRoots") == item.get("execution_snapshot_paths")
            and isinstance(item.get("commands"), dict)
            and set(item["commands"]) == {"red", "green", "refactor"}
            for item in slices
        )
    )


def validate() -> list[str]:
    findings: list[str] = []
    required = [
        "00-index.md", "01-requirements-and-acceptance.md", "requirements-ledger.v1.json",
        "implementation-contract.v1.json", "knowledge-context.v1.json", "authority-manifest.v1.json",
        "plan-state.v1.json", "resume-state.v1.json", "fixtures/negative-cases.v1.json",
        "tools/bootstrap-preflight-commands.v1.json",
        "command-registry.v1.json", "tools/validate_all.py", "tools/validate_slice.py", "tools/refactor_acceptance_slice_bridge.py",
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
    try:
        extracted = extract_requirement_inventory(REPOSITORY_ROOT / SOURCE, SOURCE)
        extracted_ids = [item["id"] for item in extracted["requirements"]]
        if extracted_ids != [f"RA-SKILL-{number:03d}" for number in range(1, 74)]:
            findings.append("RIA-PLAN-RA-ATOMIC-EXTRACTION")
    except (OSError, RequirementInventoryError):
        findings.append("RIA-PLAN-RA-ATOMIC-EXTRACTION")

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
        if (
            contract.get("command_registry") != "command-registry.v1.json"
            or contract.get("adapter_bridge", {}).get("runner") != "tools/refactor_acceptance_slice_bridge.py"
            or [item.get("slice_id") for item in contract["slices"]] != RMAP_SLICES
            or any(item.get("exit_predicate") != "slice-ready" or not item.get("execution_snapshot_paths") for item in contract["slices"])
            or by_id["S4-bootstrap-integration"].get("depends_on") != RMAP_SLICES[:4]
            or by_id["S5-finalize-release-candidate"].get("depends_on") != RMAP_SLICES[:5]
        ):
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
    if not validate_repair_rounds():
        findings.append("RIA-PLAN-REPAIR-ROUNDS")
    if not validate_successor_round():
        findings.append("RIA-PLAN-SUCCESSOR-ROUND")
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
    execution_registry = load("command-registry.v1.json")
    execution_command_ids = {item.get("id") for item in execution_registry.get("commands", []) if isinstance(item, dict)}
    expected_execution_commands = {"s0-companion-red", "s0-companion-suite", "bootstrap-regression-suite", "s1-core-red", "s1-core-suite", "s2-matrix-red", "s2-matrix-suite", "s3-control-red", "s3-control-suite", "s4-bootstrap-red", "s4-bootstrap-suite", "s5-package-red", "s5-package-suite", "plan-validator", "r2-baseline-suite", "r2-checklist-suite", "r2-bootstrap-dispatch-suite", "r2-attestation-scope-suite", "r3-candidate-suite", "r3-coverage-suite", "successor-policy-suite", "successor-coverage-suite", "successor-phase-scan-suite"}
    if execution_command_ids != expected_execution_commands:
        findings.append("RIA-PLAN-EXECUTION-REGISTRY")
    elif any(
        item["commands"][stage] not in execution_command_ids
        for directory in sorted([*(PLAN_ROOT / "repair").glob("round-*"), *(PLAN_ROOT / "successor").glob("round-*")])
        for item in json.loads((directory / "repair-plan.v1.json").read_text(encoding="utf-8"))["slices"]
        for stage in ("red", "green", "refactor")
    ):
        findings.append("RIA-PLAN-REPAIR-COMMANDS")
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

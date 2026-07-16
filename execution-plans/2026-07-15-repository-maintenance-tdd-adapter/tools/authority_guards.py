from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def _finding(rule_id: str, target: str, message: str) -> dict[str, str]:
    return {"rule_id": rule_id, "target": target, "message": message}


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate_plan_state(state: dict[str, Any], review_blocker: dict[str, Any], predicate_authority: dict[str, tuple[list[str], list[str]]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if state.get("status") != "blocked" or len(state.get("open_blockers", [])) != 1:
        findings.append(_finding("RMAP-REVIEW-MANUAL-PAUSE", "plan-state", "Round 3 manual pause is not represented as the active blocker"))
    blocking = state.get("blocking_disposition", {})
    if blocking.get("path") != "schemas/review-blocking-state.v1.json" or blocking.get("state") != "manual_pause_after_round_3" or blocking.get("reentry") != "new_review_policy_decision_required":
        findings.append(_finding("RMAP-REVIEW-MANUAL-PAUSE", "plan-state", "blocking disposition is missing or inconsistent"))
    required_blocker = {"schema_version": "rmap.review-blocking-state.v1", "plan_id": "repository-maintenance-tdd-adapter", "state": "manual_pause_after_round_3", "status": "blocked", "full_review_round": 3, "confirmed_p1_count": 8, "round_4_authorized": False}
    if any(review_blocker.get(key) != value for key, value in required_blocker.items()) or set(review_blocker.get("blocks_predicates", [])) != {"plan-ready", "slice-ready", "implementation-candidate", "implementation-accepted"}:
        findings.append(_finding("RMAP-REVIEW-MANUAL-PAUSE", "review-blocking-state", "review blocker projection does not match the finalized Round 3 disposition"))
    required_fields = {
        "schema_version", "plan_id", "state", "status", "review_id", "change_id", "full_review_round",
        "confirmed_p1_count", "policy_revision", "authority_revision", "input_hash", "source_evidence",
        "round_4_authorized", "blocks_predicates", "reentry", "does_not_authorize",
    }
    source_evidence = review_blocker.get("source_evidence")
    expected_sources = {"review_input_sha256", "review_result_sha256", "review_dispositions_sha256"}
    expected_exclusions = {"plan-ready", "slice-ready", "bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"}
    if (
        set(review_blocker) != required_fields
        or not isinstance(review_blocker.get("review_id"), str)
        or not review_blocker.get("review_id")
        or not isinstance(review_blocker.get("change_id"), str)
        or not review_blocker.get("change_id")
        or not HASH_RE.fullmatch(str(review_blocker.get("policy_revision")))
        or not COMMIT_RE.fullmatch(str(review_blocker.get("authority_revision")))
        or not HASH_RE.fullmatch(str(review_blocker.get("input_hash")))
        or not isinstance(source_evidence, dict)
        or set(source_evidence) != expected_sources
        or any(not HASH_RE.fullmatch(str(value)) for value in source_evidence.values())
        or set(review_blocker.get("does_not_authorize", [])) != expected_exclusions
    ):
        findings.append(_finding("RMAP-REVIEW-MANUAL-PAUSE", "review-blocking-state", "review blocker authority or source evidence binding is incomplete"))
    reentry = review_blocker.get("reentry", {})
    if reentry.get("condition") != "new_review_policy_decision_required" or reentry.get("same_change_round_4_allowed") is not False or reentry.get("requires_new_policy_revision") is not True:
        findings.append(_finding("RMAP-REVIEW-MANUAL-PAUSE", "review-blocking-state", "manual-pause reentry could bypass the Bootstrap hard limit"))
    predicates = state.get("predicates")
    if not isinstance(predicates, dict) or set(predicates) != set(predicate_authority):
        return findings + [_finding("RMAP-AUTH-PREDICATE", "plan-state", "predicate set mismatch")]
    for name, (authorizes, excludes) in predicate_authority.items():
        item = predicates.get(name, {})
        if item.get("authorizes") != authorizes or item.get("does_not_authorize") != excludes:
            findings.append(_finding("RMAP-AUTH-PREDICATE", name, "predicate authority set mismatch"))
    if any(state.get("current_capabilities", {}).values()):
        findings.append(_finding("RMAP-AUTH-FUTURE-CLAIM", "plan-state", "future capability is marked current"))
    return findings


def validate_script_sizes(plan_root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in (plan_root / "tools").rglob("*.py"):
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > 400:
            findings.append(_finding("RMAP-STRUCT-SCRIPT-SIZE", path.relative_to(plan_root).as_posix(), f"script has {lines} lines"))
    return findings


def validate_authority_manifest(plan_root: Path, manifest: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    required_categories = {"intent_authority", "repository_rules", "architecture_authority", "protocol_authority", "review_policy_authority", "plan_books", "machine_owners", "execution_dependencies"}
    categories = manifest.get("categories")
    if manifest.get("schema_version") != "rmap.authority-manifest.v1" or not isinstance(categories, dict) or set(categories) != required_categories:
        return [_finding("RMAP-HASH-AUTHORITY-MANIFEST", "authority-manifest", "authority categories are incomplete")]
    repository_root = plan_root.resolve().parents[1]
    seen: set[str] = set()
    for category, entries in categories.items():
        if not isinstance(entries, list) or not entries:
            findings.append(_finding("RMAP-HASH-AUTHORITY-MANIFEST", category, "authority category is empty")); continue
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
                findings.append(_finding("RMAP-HASH-AUTHORITY-MANIFEST", category, "authority entry shape is invalid")); continue
            relative = entry.get("path", "")
            normalized = relative.replace("\\", "/") if isinstance(relative, str) else ""
            if not isinstance(relative, str) or normalized != relative or normalized.casefold().startswith("logs/") or relative in seen:
                findings.append(_finding("RMAP-HASH-AUTHORITY-MANIFEST", relative or category, "authority path is ignored, duplicate, or invalid")); continue
            seen.add(relative)
            path = (repository_root / relative).resolve()
            try:
                path.relative_to(repository_root)
            except ValueError:
                findings.append(_finding("RMAP-HASH-AUTHORITY-MANIFEST", relative, "authority path escapes repository")); continue
            if not path.is_file() or entry.get("sha256") != _sha256_file(path):
                findings.append(_finding("RMAP-HASH-AUTHORITY-MANIFEST", relative, "authority hash is missing or stale"))
    expected = {
        "agentbuild.txt", "AGENTS.md", "docs/agents/12-execution-rules.md", "docs/architecture/ADR_INDEX_GODOT.md",
        ".agents/skills/vdd-execution-plan/references/strict-vdd-standard.md",
        "execution-plans/2026-07-12-llm-review-evidence-gate-hardening/09-bootstrap-review-operator-guide.md",
        "execution-plans/2026-07-12-llm-review-evidence-gate-hardening/bootstrap/review-profiles.v1.json",
    }
    prefix = "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/"
    expected.update(prefix + name for name in (
        "00-index.md", "01-intent-authority-and-non-goals.md", "02-executable-contracts-and-invariants.md",
        "03-validators-fixtures-and-control-gates.md", "04-behavior-slices-and-implementation-order.md",
        "05-diagnostics-repair-and-reentry.md", "06-testing-observability-and-evidence.md",
        "07-implementation-phases.md", "08-risks-dod-and-glossary.md", "96-global-review-and-validation.md",
        "97-requirements-ledger.md", "98-source-to-split-audit.md", "99-source-coverage.md",
        "implementation-contract.v1.json", "schemas/plan-state.v1.json", "schemas/requirements.v1.json",
        "schemas/source-coverage.v1.json", "schemas/spec-deltas.v1.json", "schemas/requirement-quality.v1.json",
        "schemas/acceptance-contracts.v1.json", "schemas/clarification-decisions.v1.json",
        "schemas/review-blocking-state.v1.json", "schemas/command-registry.v1.json",
        "schemas/implementation-contract.v1.schema.json", "schemas/shadow-backfill.v1.json",
        "schemas/shadow-protected-baseline.v1.json", "schemas/validation-result.v1.schema.json",
        "schemas/diagnostic.v1.schema.json", "fixtures/fixture-cases.v1.json", "tools/validate_all.py",
        "tools/rmap_checks.py", "tools/authority_guards.py", "tools/contract_guards.py",
        "tools/evidence_guards.py", "tools/fixture_checks.py", "tools/shadow_guards.py",
        "tools/slice_guards.py", "tools/source_guards.py", "tools/tests/test_plan_validator.py",
    ))
    if seen != expected:
        findings.append(_finding("RMAP-HASH-AUTHORITY-MANIFEST", "authority-manifest", "authority inventory differs from the closed required path set"))
    return findings


def validate_clarification_projection(projection: dict[str, Any], state: dict[str, Any] | None = None) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if projection.get("schema_version") != "rmap.clarification-decisions.v1":
        return [_finding("RMAP-REQ-CLARIFICATION-PROJECTION", "clarification-decisions", "projection schema is invalid")]
    sources = projection.get("sources", [])
    source_fields = {"kind", "run_id", "state_sha256", "authority_hash", "status", "write_disposition"}
    if [item.get("kind") for item in sources if isinstance(item, dict)] != ["creation", "repair"] or any(set(item) != source_fields or item.get("status") != "closed" for item in sources):
        findings.append(_finding("RMAP-REQ-CLARIFICATION-PROJECTION", "clarification-decisions", "source lineage is incomplete"))
    sets = projection.get("decision_sets", {})
    if [item.get("id") for item in sets.get("creation", [])] != [f"CQ-{index:03d}" for index in range(1, 18)] or [item.get("id") for item in sets.get("repair", [])] != [f"CQ-{index:03d}" for index in range(1, 6)]:
        findings.append(_finding("RMAP-REQ-CLARIFICATION-PROJECTION", "clarification-decisions", "decision identity set is incomplete"))
    if any(item.get("status") != "accepted" or not item.get("summary") or not item.get("decision") for group in sets.values() for item in group):
        findings.append(_finding("RMAP-REQ-CLARIFICATION-PROJECTION", "clarification-decisions", "decision projection is incomplete"))
    if state is not None:
        lineage = state.get("clarification", {})
        projected = {item.get("kind"): item.get("run_id") for item in sources if isinstance(item, dict)}
        if projected != {"creation": lineage.get("creation_run_id"), "repair": lineage.get("repair_run_id")}:
            findings.append(_finding("RMAP-REQ-CLARIFICATION-PROJECTION", "clarification-decisions", "projection run identities differ from plan state"))
    return findings


def validate_acceptance_contracts(acceptance: dict[str, Any], requirements: dict[str, Any], contract: dict[str, Any], commands: dict[str, Any], fixtures: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    requirement_map = {item.get("id"): item for item in requirements.get("requirements", []) if isinstance(item, dict)}
    slice_map = {item.get("slice_id"): item for item in contract.get("slices", []) if isinstance(item, dict)}
    command_ids = {item.get("id") for item in commands.get("commands", []) if isinstance(item, dict)}
    fixture_ids = {item.get("id") for item in fixtures.get("cases", []) if isinstance(item, dict)}
    entries = acceptance.get("acceptances")
    if acceptance.get("schema_version") != "rmap.acceptance-contracts.v1" or not isinstance(entries, list):
        return [_finding("RMAP-REQ-ACCEPTANCE-CONTRACT", "acceptance-contracts", "acceptance registry shape is invalid")]
    for item in entries:
        if not isinstance(item, dict):
            findings.append(_finding("RMAP-REQ-ACCEPTANCE-CONTRACT", "acceptance-contracts", "acceptance entry must be an object"))
            continue
        rid = item.get("requirement_id")
        requirement = requirement_map.get(rid, {})
        owner = slice_map.get(item.get("owner_slice_id"), {})
        if item.get("acceptance_id") != requirement.get("acceptance_id") or rid not in owner.get("requirement_ids", []) or item.get("phase_id") != owner.get("phase_id") or item.get("exit_predicate") != owner.get("exit_predicate"):
            findings.append(_finding("RMAP-REQ-ACCEPTANCE-CONTRACT", str(rid), "acceptance owner, phase, or predicate is inconsistent"))
        negative_ids = item.get("negative_fixture_ids", [])
        fixture_rules = {case.get("id"): case.get("expected_rule") for case in fixtures.get("cases", []) if isinstance(case, dict)}
        expected_rules = {fixture_rules.get(fid) for fid in negative_ids}
        command_map = {entry.get("id"): entry for entry in commands.get("commands", []) if isinstance(entry, dict)}
        command_binding_invalid = any(
            command_map.get(cid, {}).get("slice_id") not in {None, item.get("owner_slice_id")}
            or command_map.get(cid, {}).get("declared_predicate") not in {None, item.get("exit_predicate")}
            for cid in item.get("positive_command_ids", [])
        )
        if set(item.get("positive_command_ids", [])) - command_ids or set(negative_ids) - fixture_ids or None in expected_rules or set(item.get("expected_failure_ids", [])) != expected_rules or command_binding_invalid or not item.get("evidence_required"):
            findings.append(_finding("RMAP-REQ-ACCEPTANCE-CONTRACT", str(rid), "acceptance command, fixture, failure, or evidence binding is incomplete"))
        if any(sid not in slice_map or rid not in slice_map[sid].get("requirement_ids", []) for sid in item.get("supporting_slice_ids", [])):
            findings.append(_finding("RMAP-REQ-ACCEPTANCE-CONTRACT", str(rid), "supporting slice mapping is invalid"))
    return findings

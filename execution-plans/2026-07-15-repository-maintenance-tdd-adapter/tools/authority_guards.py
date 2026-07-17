from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

from contract_guards import contained_file, schema_error


HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def _finding(rule_id: str, target: str, message: str) -> dict[str, str]:
    return {"rule_id": rule_id, "target": target, "message": message}


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_bootstrap_runtime(repository_root: Path) -> Any:
    bootstrap_path = repository_root / ".agents" / "skills" / "run-phase-bootstrap-review" / "scripts" / "bootstrap_review.py"
    spec = importlib.util.spec_from_file_location("rmap_bootstrap_review", bootstrap_path)
    if spec is None or spec.loader is None:
        raise ValueError("Bootstrap validator cannot be loaded")
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    return bootstrap


def validate_review_reentry(plan_root: Path, review_blocker: dict[str, Any], reentry: dict[str, Any]) -> list[dict[str, str]]:
    schema = json.loads((plan_root / "schemas" / "review-policy-reentry.v1.schema.json").read_text(encoding="utf-8"))
    error = schema_error(reentry, schema)
    if error:
        return [_finding("RMAP-REVIEW-REENTRY", "review-policy-reentry", error)]
    blocker_path = plan_root / "schemas" / "review-blocking-state.v1.json"
    predecessor = reentry["supersedes_blocker"]
    if predecessor.get("sha256") != _sha256_file(blocker_path) or predecessor.get("review_id") != review_blocker.get("review_id") or predecessor.get("policy_revision") != review_blocker.get("policy_revision"):
        return [_finding("RMAP-REVIEW-REENTRY", "review-policy-reentry", "successor does not bind the immutable Round 3 blocker")]
    exclusions = {"plan-ready", "slice-ready", "bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"}
    if reentry.get("state") != "reentry_authorized":
        if reentry.get("authorizes") != [] or set(reentry.get("does_not_authorize", [])) != exclusions:
            return [_finding("RMAP-REVIEW-REENTRY", "review-policy-reentry", "pending reentry artifact gained authority")]
        return []
    policy = reentry["successor_policy"]
    closure = reentry["semantic_closure"]
    repository_root = plan_root.parents[1]
    decision_path = contained_file(repository_root, policy.get("decision_path"))
    envelope_path = contained_file(repository_root, closure.get("envelope_path"))
    bootstrap_run_value = closure.get("bootstrap_run_path")
    bootstrap_input_path = contained_file(repository_root, f"{bootstrap_run_value}/review-input.json" if isinstance(bootstrap_run_value, str) else None)
    bootstrap_run_path = bootstrap_input_path.parent if bootstrap_input_path is not None else None
    decision_hash_invalid = decision_path is None or policy.get("decision_sha256") != _sha256_file(decision_path)
    invalid = (
        policy.get("policy_revision") == review_blocker.get("policy_revision")
        or policy.get("change_id") == review_blocker.get("change_id")
        or policy.get("authority_revision") == review_blocker.get("authority_revision")
        or decision_hash_invalid
    )
    if invalid or envelope_path is None or bootstrap_run_path is None or closure.get("envelope_sha256") != _sha256_file(envelope_path):
        return [_finding("RMAP-REVIEW-REENTRY", "review-policy-reentry", "successor policy or semantic closure evidence is stale")]
    try:
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        bootstrap = _load_bootstrap_runtime(repository_root)
        decision_errors = bootstrap.schema_validation_errors("bootstrap-successor-policy-decision.v1.schema.json", decision)
        if decision_errors:
            raise ValueError("; ".join(decision_errors))
        bootstrap.validate_successor_policy_authorization(repository_root, decision)
        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
        manifest = bootstrap.read_json(bootstrap_run_path / "review-input.json")
        recomputed = bootstrap.validate_finalized_run_evidence(bootstrap_run_path, manifest, repository_root)
        envelope_errors = bootstrap.schema_validation_errors("bootstrap-finalized-run-validation.v1.schema.json", envelope)
        if envelope_errors or {key: value for key, value in envelope.items() if key != "generatedAt"} != {key: value for key, value in recomputed.items() if key != "generatedAt"}:
            raise ValueError("; ".join(envelope_errors) or "saved envelope differs from independent recomputation")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, RuntimeError):
        return [_finding("RMAP-REVIEW-REENTRY", "review-policy-reentry", "semantic closure envelope is unreadable")]
    independent = (
        decision.get("supersededReviewId") == review_blocker.get("review_id")
        and decision.get("supersededChangeId") == review_blocker.get("change_id")
        and decision.get("successorChangeId") == envelope.get("changeId") == policy.get("change_id")
        and decision.get("policyRevision") == envelope.get("policyRevision") == policy.get("policy_revision")
        and decision.get("authorityRevision") == envelope.get("authorityRevision") == policy.get("authority_revision")
        and envelope.get("inputHash") == policy.get("input_hash")
        and envelope.get("reviewId") != review_blocker.get("review_id")
        and envelope.get("inputHash") != review_blocker.get("input_hash")
        and decision.get("authorizes") == []
        and set(decision.get("doesNotAuthorize", [])) == exclusions
    )
    if not independent or envelope.get("reviewId") != closure.get("review_id") or envelope.get("validationStatus") != "passed" or envelope.get("finalStatus") != "clean" or envelope.get("authorizes") != [] or not {"plan-acceptance", "implementation-acceptance", "protected-handoff", "release", "commit", "done"}.issubset(set(envelope.get("doesNotAuthorize", []))) or reentry.get("authorizes") != ["plan-ready"] or set(reentry.get("does_not_authorize", [])) != exclusions - {"plan-ready"}:
        return [_finding("RMAP-REVIEW-REENTRY", "review-policy-reentry", "semantic closure does not authorize exact plan reentry")]
    return []


def validate_plan_state(plan_root: Path, state: dict[str, Any], review_blocker: dict[str, Any], reentry: dict[str, Any], predicate_authority: dict[str, tuple[list[str], list[str]]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    findings.extend(validate_review_reentry(plan_root, review_blocker, reentry))
    reentry_authorized = reentry.get("state") == "reentry_authorized" and not findings
    expected_status = "plan-ready" if reentry_authorized else "blocked"
    expected_blockers = 0 if reentry_authorized else 1
    if state.get("status") != expected_status or len(state.get("open_blockers", [])) != expected_blockers:
        findings.append(_finding("RMAP-REVIEW-MANUAL-PAUSE", "plan-state", "Round 3 manual pause is not represented as the active blocker"))
    blocking = state.get("blocking_disposition", {})
    if blocking.get("path") != "schemas/review-blocking-state.v1.json" or blocking.get("state") != "manual_pause_after_round_3" or blocking.get("reentry") != "schemas/review-policy-reentry.v1.json":
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
    projection = state.get("capability_projection", {})
    expected_capabilities = {
        "common_schema_skill_owned": ("RMAP-S1", "slice-ready"),
        "adapter_operational": ("RMAP-S2", "slice-ready"),
        "old_plan_backfill_complete": ("RMAP-S5", "slice-ready"),
        "implementation_accepted": ("RMAP-S7", "implementation-accepted"),
        "release_ready": (None, None),
    }
    capabilities = projection.get("capabilities", {})
    if projection.get("producer") != "tools/validate_all.py" or projection.get("source_of_truth") != "current hash-bound predicate evidence" or set(capabilities) != set(expected_capabilities) or any((capabilities.get(name, {}).get("first_slice"), capabilities.get(name, {}).get("predicate")) != expected for name, expected in expected_capabilities.items()):
        findings.append(_finding("RMAP-AUTH-FUTURE-CLAIM", "plan-state", "capability projection producer or lifecycle mapping is invalid"))
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
    required_categories = {"intent_authority", "repository_rules", "architecture_authority", "protocol_authority", "review_policy_authority", "compatibility_inputs", "plan_books", "machine_owners", "execution_dependencies"}
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
        "execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/validate_whole_directory.py",
        "execution-plans/2026-07-12-llm-review-evidence-gate-hardening/bootstrap/review-profiles.v1.json",
        "docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md",
        "docs/standards/bootstrap-review-control-plane.md",
        ".agents/skills/run-phase-bootstrap-review/SKILL.md",
        ".agents/skills/run-phase-bootstrap-review/references/review-profiles.v1.json",
        ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py",
        ".agents/skills/run-phase-bootstrap-review/scripts/_control_plane.py",
        ".agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py",
        ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-finalized-run-validation.v1.schema.json",
        ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-p2-command-registry.v1.schema.json",
        ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-p2-dispositions.v1.schema.json",
        ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-p2-evidence-result.v1.schema.json",
        ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-p2-owner-authority.v1.schema.json",
        ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-p2-process-result.v1.schema.json",
        ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-successor-policy-authority.v1.schema.json",
        ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-successor-policy-authorization.v1.schema.json",
        ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-successor-policy-decision.v1.schema.json",
        ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-verifier-output.v1.schema.json",
        ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-preflight-result.v1.schema.json",
        ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-review-gate-result.v1.schema.json",
        ".agents/skills/run-phase-bootstrap-review/schemas/review-finding.v1.schema.json",
        ".agents/skills/run-phase-bootstrap-review/schemas/review-result.v1.schema.json",
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
        "schemas/diagnostic.v1.schema.json", "schemas/context-manifest.v1.schema.json",
        "schemas/slice-capsule.v1.schema.json", "schemas/backend-request.v1.schema.json",
        "schemas/backend-response.v1.schema.json", "schemas/diff-manifest.v1.schema.json",
        "schemas/adapter-decision.v1.schema.json", "schemas/agent-attempt-event.v1.schema.json",
        "schemas/baseline-file-manifest.v1.schema.json", "schemas/attempt-ledger-manifest.v1.schema.json",
        "schemas/candidate-diff-manifest.v1.schema.json", "schemas/candidate-result-ref.v1.schema.json",
        "schemas/candidate-lineage-manifest.v1.schema.json", "schemas/candidate-slice-effect.v1.schema.json", "schemas/candidate-supersession-proof.v1.schema.json",
        "schemas/review-policy-reentry.v1.schema.json", "schemas/review-policy-reentry.v1.json",
        "schemas/artifact-proof.v1.schema.json", "schemas/artifact-proof-required.v1.json", "schemas/artifact-proof-registry.v1.json", "schemas/runtime-artifact-type-proof.v1.json",
        "fixtures/fixture-cases.v1.json", "fixtures/capsule-attempt-cases.v1.json", "fixtures/candidate-diff-cases.v1.json", "tools/validate_all.py",
        "tools/rmap_checks.py", "tools/authority_guards.py", "tools/contract_guards.py",
        "tools/evidence_guards.py", "tools/candidate_diff_guards.py", "tools/candidate_lineage_guards.py", "tools/current_state_guards.py", "tools/fixture_checks.py", "tools/shadow_guards.py",
        "tools/slice_guards.py", "tools/source_guards.py", "tools/protocol_guards.py",
        "tools/protocol_validation_guards.py", "tools/protocol_fixture_support.py",
        "tools/protocol_fixture_cases.py",
        "tools/protocol_fixture_mutations.py", "tools/protocol_artifact_guards.py",
        "tools/attempt_lineage_guards.py", "tools/refresh_projections.py", "tools/artifact_proof_guards.py",
        "tools/tests/test_plan_validator.py", "tools/tests/test_protocol_guards.py", "tools/tests/test_candidate_diff_guards.py",
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
    if [item.get("kind") for item in sources if isinstance(item, dict)] != ["creation", "repair", "repair", "repair", "repair", "repair"] or any(set(item) != source_fields or item.get("status") != "closed" for item in sources):
        findings.append(_finding("RMAP-REQ-CLARIFICATION-PROJECTION", "clarification-decisions", "source lineage is incomplete"))
    sets = projection.get("decision_sets", {})
    expected_sets = {
        "creation": [f"CQ-{index:03d}" for index in range(1, 18)],
        "repair": [f"CQ-{index:03d}" for index in range(1, 6)],
        "repair_20260717": [f"CQ-{index:03d}" for index in range(1, 8)],
        "repair_20260717_999": [f"CQ-{index:03d}" for index in range(1, 8)],
        "repair_20260717_1200": [f"CQ-{index:03d}" for index in range(1, 6)],
        "repair_20260717_1300": [f"CQ-{index:03d}" for index in range(1, 6)],
    }
    if set(sets) != set(expected_sets) or any([item.get("id") for item in sets.get(name, [])] != ids for name, ids in expected_sets.items()):
        findings.append(_finding("RMAP-REQ-CLARIFICATION-PROJECTION", "clarification-decisions", "decision identity set is incomplete"))
    if any(item.get("status") != "accepted" or not item.get("summary") or not item.get("decision") for group in sets.values() for item in group):
        findings.append(_finding("RMAP-REQ-CLARIFICATION-PROJECTION", "clarification-decisions", "decision projection is incomplete"))
    if state is not None:
        lineage = state.get("clarification", {})
        projected_creation = [item.get("run_id") for item in sources if isinstance(item, dict) and item.get("kind") == "creation"]
        projected_repairs = [item.get("run_id") for item in sources if isinstance(item, dict) and item.get("kind") == "repair"]
        if projected_creation != [lineage.get("creation_run_id")] or projected_repairs != lineage.get("repair_run_ids") or lineage.get("current_repair_run_id") != projected_repairs[-1]:
            findings.append(_finding("RMAP-REQ-CLARIFICATION-PROJECTION", "clarification-decisions", "projection run identities differ from plan state"))
    return findings


def validate_acceptance_contracts(acceptance: dict[str, Any], requirements: dict[str, Any], contract: dict[str, Any], commands: dict[str, Any], fixtures: dict[str, Any], protocol_fixtures: dict[str, Any] | None = None, candidate_fixtures: dict[str, Any] | None = None) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    requirement_map = {item.get("id"): item for item in requirements.get("requirements", []) if isinstance(item, dict)}
    slice_map = {item.get("slice_id"): item for item in contract.get("slices", []) if isinstance(item, dict)}
    command_ids = {item.get("id") for item in commands.get("commands", []) if isinstance(item, dict)}
    fixture_cases = [*fixtures.get("cases", []), *(protocol_fixtures or {}).get("cases", []), *(candidate_fixtures or {}).get("cases", [])]
    fixture_ids = {item.get("id") for item in fixture_cases if isinstance(item, dict)}
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
        fixture_rules = {case.get("id"): case.get("expected_rule") for case in fixture_cases if isinstance(case, dict)}
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

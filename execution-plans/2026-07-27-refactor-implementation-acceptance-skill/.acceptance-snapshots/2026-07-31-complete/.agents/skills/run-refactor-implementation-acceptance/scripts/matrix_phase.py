"""Deterministic phase-DAG and distinct DoD evaluation primitives."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from acceptance_core import InputError


_ROW_FIELDS = {
    "check_id", "source_clause_ids", "canonical_source_ref", "source_refs", "requirement", "phase_id",
    "requirement_refs", "policy_check_refs", "applicability", "implementation_owner", "verification_owner",
    "approval_owner", "implementation_refs", "test_definition_refs", "test_run_evidence_ids", "runtime_evidence_ids",
    "evidence_requirements", "disposition", "evaluation_state", "deterministic_gate_state",
    "deterministic_blocking_predecessors", "gap",
}
_DEFERRED_FIELDS = {
    "defer_owner", "defer_affected_routes", "defer_severity", "defer_severity_namespace",
    "defer_severity_source_refs", "defer_non_impact_evidence_ids", "defer_recheck_trigger",
    "defer_closure_test_definition_refs", "defer_closure_required_check_ids",
}
_GATE_FIELDS = {"gateId", "gateClass", "resultPath", "resultHash", "schemaPath", "schemaHash", "authorityRef", "authorizationScopes", "status"}


def _result_hash(value: Any) -> str:
    import hashlib
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _write_new_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, sort_keys=True, indent=2)
            handle.write("\n")
    except FileExistsError as exc:
        raise InputError("result publication is append-only") from exc


def publish_candidate_result(path: Path, candidate: Any, candidate_input_hash: str) -> dict[str, Any]:
    if not isinstance(candidate, dict) or not isinstance(candidate_input_hash, str) or not candidate_input_hash.startswith("sha256:"):
        raise InputError("candidate result input is invalid")
    result = {"schemaVersion": "acceptance-result-candidate.v1", "candidateInputHash": candidate_input_hash, "candidate": candidate, "candidateHash": _result_hash(candidate), "authorizes": []}
    _write_new_json(path, result)
    return result


def publish_final_result(path: Path, final: Any, candidate_path: Path, candidate_hash: str, projection_hash: str) -> dict[str, Any]:
    if path.resolve() == candidate_path.resolve():
        raise InputError("final result path must be distinct from candidate path")
    if not candidate_path.is_file() or not isinstance(final, dict) or any(not isinstance(value, str) or not value.startswith("sha256:") for value in (candidate_hash, projection_hash)):
        raise InputError("final result input is invalid")
    candidate_document = json.loads(candidate_path.read_text(encoding="utf-8"))
    if candidate_document.get("candidateHash") != candidate_hash or candidate_document.get("authorizes") != []:
        raise InputError("candidate result binding is stale")
    result = {"schemaVersion": "acceptance-result-final.v1", "candidatePath": str(candidate_path), "candidateHash": candidate_hash, "impactProjectionHash": projection_hash, "final": final, "authorizes": []}
    _write_new_json(path, result)
    return result


def _strings(value: Any, label: str, *, allow_empty: bool = False) -> None:
    if not isinstance(value, list) or (not allow_empty and not value) or any(not isinstance(item, str) or not item for item in value) or len(value) != len(set(value)):
        raise InputError(label + " is invalid")


def _validate_row(row: Any) -> None:
    if not isinstance(row, dict):
        raise InputError("base matrix row is invalid")
    disposition = row.get("disposition")
    expected_fields = _ROW_FIELDS | (_DEFERRED_FIELDS if disposition == "explicitly_deferred" else set())
    if set(row) != expected_fields:
        raise InputError("base matrix row fields are invalid")
    for field in ("check_id", "canonical_source_ref", "requirement", "phase_id", "implementation_owner", "verification_owner", "approval_owner"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            raise InputError("base matrix row identity is invalid")
    for field in ("source_clause_ids", "source_refs", "requirement_refs", "policy_check_refs", "implementation_refs", "test_definition_refs", "test_run_evidence_ids", "runtime_evidence_ids", "deterministic_blocking_predecessors"):
        _strings(row.get(field), "base matrix " + field, allow_empty=field in {"policy_check_refs", "runtime_evidence_ids", "deterministic_blocking_predecessors"})
    applicability = row.get("applicability")
    if not isinstance(applicability, dict) or set(applicability) != {"status", "activation_predicate", "authority_refs", "evidence_ids"}:
        raise InputError("base matrix applicability is invalid")
    if applicability.get("status") not in {"applicable", "not_applicable", "undetermined"} or not isinstance(applicability.get("activation_predicate"), str) or not applicability["activation_predicate"]:
        raise InputError("base matrix applicability status is invalid")
    _strings(applicability.get("authority_refs"), "base matrix applicability authority refs")
    _strings(applicability.get("evidence_ids"), "base matrix applicability evidence ids", allow_empty=applicability["status"] == "applicable")
    evidence = row.get("evidence_requirements")
    if not isinstance(evidence, dict) or set(evidence) != {"required_kinds", "minimum_by_kind", "freshness_policy", "waiver_allowed", "source_refs"}:
        raise InputError("base matrix evidence requirements are invalid")
    _strings(evidence.get("required_kinds"), "base matrix evidence kinds")
    minimum = evidence.get("minimum_by_kind")
    if not isinstance(minimum, dict) or set(minimum) - set(evidence["required_kinds"]) or any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in minimum.values()):
        raise InputError("base matrix evidence minimums are invalid")
    if evidence.get("freshness_policy") not in {"exact_candidate", "current_authority", "same_candidate_environment"} or not isinstance(evidence.get("waiver_allowed"), bool):
        raise InputError("base matrix evidence freshness is invalid")
    _strings(evidence.get("source_refs"), "base matrix evidence source refs")
    if disposition not in {"verified", "partial", "missing", "not_applicable", "explicitly_deferred", None}:
        raise InputError("base matrix disposition is invalid")
    if row.get("evaluation_state") not in {"not_evaluated", "evaluated", "stale"} or row.get("deterministic_gate_state") not in {"eligible", "blocked"}:
        raise InputError("base matrix orthogonal state is invalid")
    status = applicability["status"]
    if status == "not_applicable" and (disposition != "not_applicable" or row["evaluation_state"] != "evaluated" or not applicability["evidence_ids"]):
        raise InputError("not applicable matrix row violates orthogonal state")
    if status == "undetermined" and (disposition is not None or row["evaluation_state"] not in {"not_evaluated", "stale"} or row["deterministic_gate_state"] != "blocked"):
        raise InputError("undetermined matrix row violates orthogonal state")
    if status == "applicable" and disposition not in {"verified", "partial", "missing", "explicitly_deferred"}:
        raise InputError("applicable matrix row violates orthogonal state")
    if disposition == "verified" and (row["evaluation_state"] != "evaluated" or not row["implementation_refs"] or not row["test_definition_refs"] or not row["test_run_evidence_ids"]):
        raise InputError("verified matrix row lacks evidence closure")
    if disposition != "verified" and not row.get("gap"):
        raise InputError("non-verified matrix row requires a gap")
    if disposition == "explicitly_deferred":
        for field in _DEFERRED_FIELDS:
            value = row[field]
            if isinstance(value, list):
                _strings(value, "deferred " + field)
            elif not isinstance(value, str) or not value.strip():
                raise InputError("deferred matrix row is incomplete")


def validate_base_matrix(rows: Any, required_check_ids: Any) -> None:
    if not isinstance(rows, list) or not isinstance(required_check_ids, set) or not required_check_ids:
        raise InputError("base matrix is invalid")
    observed: set[str] = set()
    for row in rows:
        _validate_row(row)
        if row["check_id"] in observed:
            raise InputError("base matrix check identity is invalid")
        observed.add(row["check_id"])
    if observed != required_check_ids:
        raise InputError("base matrix does not exactly cover required checks")


def validate_phase_graph(value: Any) -> list[str]:
    if (
        not isinstance(value, dict)
        or set(value) != {"schemaVersion", "phases", "authorizes"}
        or value.get("schemaVersion") != "phase-graph.v1"
        or value.get("authorizes") != []
        or not isinstance(value.get("phases"), list)
        or not value["phases"]
    ):
        raise InputError("phase graph schema or authority boundary is invalid")
    phases = value["phases"]
    for phase in phases:
        if not isinstance(phase, dict) or set(phase) - {"phaseId", "dependsOn", "joinPolicy"}:
            raise InputError("phase graph node fields are invalid")
    by_id = {item.get("phaseId"): item for item in phases if isinstance(item, dict) and isinstance(item.get("phaseId"), str)}
    if len(by_id) != len(phases):
        raise InputError("phase ids are invalid")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(phase_id: str) -> None:
        if phase_id in visiting:
            raise InputError("phase graph has a cycle")
        if phase_id in visited:
            return
        visiting.add(phase_id)
        item = by_id[phase_id]
        dependencies = item.get("dependsOn", [])
        if not isinstance(dependencies, list) or any(dependency not in by_id for dependency in dependencies):
            raise InputError("phase graph dependency is unknown")
        if item.get("joinPolicy", "all") not in {"all", "any"}:
            raise InputError("phase graph join policy is invalid")
        for dependency in dependencies:
            visit(dependency)
        visiting.remove(phase_id)
        visited.add(phase_id)

    for phase_id in by_id:
        visit(phase_id)
    return list(by_id)


def evaluate_phase_readiness(graph: Any, completed_phases: Any) -> dict[str, str]:
    ids = validate_phase_graph(graph)
    if not isinstance(completed_phases, set) or not completed_phases.issubset(set(ids)):
        raise InputError("completed phase set is invalid")
    result: dict[str, str] = {}
    by_id = {item["phaseId"]: item for item in graph["phases"]}
    for phase_id in ids:
        if phase_id in completed_phases:
            result[phase_id] = "completed"
            continue
        dependencies = by_id[phase_id].get("dependsOn", [])
        policy = by_id[phase_id].get("joinPolicy", "all")
        ready = not dependencies or (all(item in completed_phases for item in dependencies) if policy == "all" else any(item in completed_phases for item in dependencies))
        result[phase_id] = "ready" if ready else "blocked"
    return result


def validate_external_protected_gates(gates: Any) -> dict[str, set[str]]:
    """Validate typed gate results and project only explicitly passed scopes."""
    if not isinstance(gates, list):
        raise InputError("external and protected gate results are invalid")
    seen: set[str] = set()
    passed: dict[str, set[str]] = {}
    for gate in gates:
        if not isinstance(gate, dict) or set(gate) != _GATE_FIELDS:
            raise InputError("external or protected gate fields are invalid")
        gate_id = gate.get("gateId")
        if not isinstance(gate_id, str) or not gate_id or gate_id in seen:
            raise InputError("external or protected gate identity is invalid")
        seen.add(gate_id)
        if gate.get("gateClass") not in {"external", "protected"} or gate.get("status") not in {"passed", "failed", "blocked", "incomplete", "stale"}:
            raise InputError("external or protected gate status is invalid")
        for field in ("resultPath", "schemaPath", "authorityRef"):
            if not isinstance(gate.get(field), str) or not gate[field].strip():
                raise InputError("external or protected gate location is invalid")
        for field in ("resultHash", "schemaHash"):
            value = gate.get(field)
            if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
                raise InputError("external or protected gate hash is invalid")
        scopes = gate.get("authorizationScopes")
        _strings(scopes, "external or protected gate scopes")
        if gate["status"] == "passed":
            for scope in scopes:
                passed.setdefault(scope, set()).add(gate_id)
    return passed


def evaluate_three_level_dod(
    *, first_slice_checks: set[str], phase_checks: set[str], program_checks: set[str],
    eligible_checks: set[str], required_gate_scopes: dict[str, set[str]], gates: Any,
) -> dict[str, dict[str, Any]]:
    if not all(isinstance(value, set) for value in (first_slice_checks, phase_checks, program_checks, eligible_checks)):
        raise InputError("DoD check sets are invalid")
    passed_gates = validate_external_protected_gates(gates)

    def level(name: str, checks: set[str]) -> dict[str, Any]:
        missing_checks = sorted(checks - eligible_checks)
        missing_gates = sorted(scope for scope in required_gate_scopes.get(name, set()) if not passed_gates.get(scope))
        status = "passed" if not missing_checks and not missing_gates else "blocked"
        return {"status": status, "failedCheckIds": missing_checks, "missingGateScopes": missing_gates, "authorizes": []}

    return {"first_slice": level("first_slice", first_slice_checks), "phase_exit": level("phase_exit", phase_checks), "program_dod": level("program_dod", program_checks)}


def project_acceptance_impact(
    *, base_rows: Any, required_check_ids: set[str], partitions: Any,
    phase_consumed_partitions: Any, gates: Any, code_review_policy_binding_hash: str,
    phase_policy_result_hashes: Any, phase_graph_hash: str, base_matrix_hash: str,
) -> dict[str, Any]:
    """Project effective gate state without mutating base implementation facts."""
    validate_base_matrix(base_rows, required_check_ids)
    if not isinstance(partitions, list) or not isinstance(phase_consumed_partitions, dict) or not isinstance(phase_policy_result_hashes, dict):
        raise InputError("impact projection inputs are invalid")
    if set(phase_policy_result_hashes) != {"taskChecklistClosure", "diffCoverage", "staticAnalysis", "securityScan"}:
        raise InputError("impact projection phase policy result hashes are incomplete")
    for value in [base_matrix_hash, code_review_policy_binding_hash, phase_graph_hash, *phase_policy_result_hashes.values()]:
        if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
            raise InputError("impact projection hash binding is invalid")
    ranks = {"deterministic_complete": 3, "semantically_attested_complete": 2, "candidate": 1, "incomplete": 0, "stale": -1}
    partition_by_id: dict[str, dict[str, Any]] = {}
    for partition in partitions:
        if not isinstance(partition, dict) or not isinstance(partition.get("partitionId"), str) or partition["partitionId"] in partition_by_id or partition.get("baseCompleteness") not in ranks or partition.get("effectiveCompleteness") not in ranks or partition.get("status") not in {"current", "incomplete", "stale"}:
            raise InputError("impact projection partition is invalid")
        partition_by_id[partition["partitionId"]] = partition
    passed_gates = validate_external_protected_gates(gates)
    scope_completeness: list[dict[str, Any]] = []
    for scope_id, consumed in phase_consumed_partitions.items():
        _strings(consumed, "impact projection consumed partitions")
        if any(partition_id not in partition_by_id for partition_id in consumed):
            raise InputError("impact projection consumes an unknown partition")
        weakest = min((partition_by_id[partition_id]["effectiveCompleteness"] for partition_id in consumed), key=ranks.get)
        scope_completeness.append({"scopeId": scope_id, "consumedPartitionIds": list(consumed), "scopeEffectiveCompleteness": weakest})
    overall = min((item["effectiveCompleteness"] for item in partitions), key=ranks.get) if partitions else "incomplete"
    impacts: list[dict[str, Any]] = []
    for row in base_rows:
        reasons = list(row["deterministic_blocking_predecessors"])
        phase_scope = "phase:" + row["phase_id"]
        scope = next((item for item in scope_completeness if item["scopeId"] == phase_scope), None)
        if scope is not None and ranks[scope["scopeEffectiveCompleteness"]] < ranks["deterministic_complete"]:
            reasons.append("scope_completeness:" + scope["scopeEffectiveCompleteness"])
        state = "eligible" if row["deterministic_gate_state"] == "eligible" and not reasons else "blocked"
        impacts.append({"checkId": row["check_id"], "effectiveGateState": state, "effectiveFindingRefs": [], "effectiveBlockingReasons": reasons})
    return {
        "schemaVersion": "acceptance-impact-projection.v1", "baseMatrixHash": base_matrix_hash,
        "codeReviewPolicyBindingHash": code_review_policy_binding_hash, "phasePolicyResultHashes": phase_policy_result_hashes,
        "bootstrapImportEnvelopeHash": None, "findingMapHash": None, "approvalImportReceiptHashes": [],
        "externalAndProtectedGateResults": gates, "passedGateScopes": {key: sorted(value) for key, value in passed_gates.items()},
        "phaseGraphHash": phase_graph_hash, "partitionImpacts": partitions, "effectiveOverallCompleteness": overall,
        "scopeCompleteness": scope_completeness, "checkImpacts": impacts, "status": "current", "authorizes": [],
    }


def three_level_dod(first_slice: Any, phase_exit: Any, program: Any) -> dict[str, str]:
    valid = {"passed", "failed", "blocked", "incomplete", "not_defined"}
    if any(value not in valid for value in (first_slice, phase_exit, program)):
        raise InputError("DoD status is invalid")
    return {"first_slice": first_slice, "phase_exit": phase_exit, "program_dod": program}

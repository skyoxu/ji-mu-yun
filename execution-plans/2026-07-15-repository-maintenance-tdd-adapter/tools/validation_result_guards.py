from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from contract_guards import schema_error


def value_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def validate_authorizing_result(
    result: dict[str, Any], current: dict[str, str],
    predicate_authority: dict[str, tuple[list[str], list[str]]],
    all_exclusions: list[str], runtime_evidence_root: str | None = None,
    predecessor_result: dict[str, Any] | None = None,
    predecessor_schema: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    expected_roots = {
        "candidate_hash": current["candidate_hash"],
        "current_candidate_hash": current["candidate_hash"],
        "source_hash": current["source_hash"],
        "validator_version": current["validator_version"],
        "predicate_input_root": current["predicate_input_root"],
        "closure_definition_hash": current["closure_definition_hash"],
        "authority_root": current["authority_root"],
        "validator_root": current["validator_root"],
    }
    if runtime_evidence_root is not None:
        expected_roots["runtime_evidence_root"] = runtime_evidence_root
    if any(result.get(key) != value for key, value in expected_roots.items()):
        return [{"rule_id": "RMAP-RESULT-STALE", "target": "validation-result", "message": "authorizing result roots differ from current inputs"}]
    permission = predicate_authority.get(result.get("predicate"))
    passed = result.get("status") == "pass"
    expected_authorizes = permission[0] if passed and permission else []
    expected_excludes = permission[1] if passed and permission else all_exclusions
    checks_pass = all(item.get("status") == "pass" for item in result.get("checks", []))
    if (
        permission is None or result.get("authorizes") != expected_authorizes
        or result.get("does_not_authorize") != expected_excludes
        or (passed and (result.get("diagnostics") or not checks_pass))
    ):
        return [{"rule_id": "RMAP-RESULT-AUTHORITY", "target": "validation-result", "message": "result status, checks, and exact permission lattice differ"}]
    lineage_mode = result.get("lineage_mode")
    if lineage_mode == "initial":
        valid_lineage = (
            predecessor_result is None
            and result.get("lineage_reason_code") == "INITIAL_RUN_NO_PREDECESSOR"
            and result.get("predecessor_run_id") is None
            and result.get("supersedes_run_id") is None
            and result.get("predecessor_result_hash") is None
        )
    else:
        predecessor_id = predecessor_result.get("run_id") if isinstance(predecessor_result, dict) else None
        valid_lineage = (
            lineage_mode == "successor"
            and result.get("lineage_reason_code") == "SUPERSEDES_PRIOR_RESULT"
            and isinstance(predecessor_id, str) and bool(predecessor_id)
            and isinstance(predecessor_schema, dict)
            and schema_error(predecessor_result, predecessor_schema) is None
            and result.get("predecessor_run_id") == predecessor_id
            and result.get("supersedes_run_id") == predecessor_id
            and result.get("predecessor_result_hash") == value_hash(predecessor_result)
            and result.get("run_id") != predecessor_id
        )
    if not valid_lineage:
        return [{"rule_id": "RMAP-RESULT-LINEAGE", "target": "validation-result", "message": "result lineage is not initial or recomputable from its predecessor envelope"}]
    return []


def build_result(
    plan_root: Path, predicate: str, checks: list[dict[str, Any]], findings: list[dict[str, str]],
    validated: dict[str, str], current: dict[str, str],
    predicate_authority: dict[str, tuple[list[str], list[str]]], all_exclusions: list[str],
    strict_load: Callable[[Path], dict[str, Any]], status_override: str | None = None,
    capabilities: dict[str, bool] | None = None, runtime_evidence_root: str | None = None,
    predecessor_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    passed = not findings and status_override is None
    authorizes, excludes = predicate_authority[predicate]
    result = {
        "schema_version": "rmap.validation-result.v1",
        "run_id": "rmap-plan-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ-") + uuid.uuid4().hex,
        "predicate": predicate, "status": status_override or ("pass" if passed else "fail"),
        "candidate_hash": validated["candidate_hash"], "current_candidate_hash": current["candidate_hash"],
        "source_hash": validated["source_hash"], "validator_version": validated["validator_version"],
        "predicate_input_root": validated["predicate_input_root"],
        "closure_definition_hash": validated["closure_definition_hash"],
        "authority_root": validated["authority_root"], "validator_root": validated["validator_root"],
        "runtime_evidence_root": runtime_evidence_root or value_hash([]),
        "lineage_mode": "successor" if predecessor_result else "initial",
        "lineage_reason_code": "SUPERSEDES_PRIOR_RESULT" if predecessor_result else "INITIAL_RUN_NO_PREDECESSOR",
        "predecessor_run_id": predecessor_result.get("run_id") if predecessor_result else None,
        "supersedes_run_id": predecessor_result.get("run_id") if predecessor_result else None,
        "predecessor_result_hash": value_hash(predecessor_result) if predecessor_result else None,
        "capabilities": capabilities or {name: False for name in ("common_schema_skill_owned", "adapter_operational", "old_plan_backfill_complete", "implementation_complete", "release_ready")},
        "authorizes": authorizes if passed else [],
        "does_not_authorize": excludes if passed else all_exclusions,
        "checks": checks, "diagnostics": findings,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    result_schema = strict_load(plan_root / "schemas" / "validation-result.v1.schema.json")
    envelope_error = schema_error(result, result_schema)
    if envelope_error:
        result.update(status="fail", authorizes=[], does_not_authorize=all_exclusions)
        result["diagnostics"].append({"rule_id": "RMAP-RESULT-ENVELOPE", "target": "validation-result", "message": envelope_error})
    consumer_findings = validate_authorizing_result(
        result, current, predicate_authority, all_exclusions,
        runtime_evidence_root or value_hash([]), predecessor_result, result_schema,
    )
    if consumer_findings:
        result.update(status="fail", authorizes=[], does_not_authorize=all_exclusions)
        result["diagnostics"].extend(consumer_findings)
    return result

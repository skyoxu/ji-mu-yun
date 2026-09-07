"""Deterministic staged semantic-plan validator for VDD Chapter 4/5/6.

VDD owns planning intent only. This validator enforces V5 -> V6 -> V6A ordering
and rejects runtime evidence in VDD-authored artifacts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


STAGE_SCOPE = ["red", "green", "refactor", "terminal"]
RUNTIME_ONLY_FIELDS = {
    "run_id", "receipt_ref", "receipt_sha256", "observation_id", "observation_ref",
    "observation_sha256", "runtime_edge_ref", "runtime_edge_sha256",
    "current_snapshot_sha256", "exit_code", "timed_out", "process_attempts",
    "test_executions", "cases", "verification_outcome", "failure_id", "failure_family",
}
PRE_SLICE_FIELDS = {"requirement_id", "obligation_id", "acceptance_id", "source_ref", "failure_intent_id"}
FINAL_COVER_FIELDS = PRE_SLICE_FIELDS | {"slice_id", "verification_lane", "terminal_predicate", "stage_scope"}
OBLIGATION_FIELDS = {
    "obligation_id", "requirement_id", "source_refs", "subject", "trigger", "state_before",
    "state_after", "expected_behavior", "observable_result", "forbidden_result",
    "requirement_type", "obligation_kind", "unresolved_fragments", "status", "depends_on",
}
SLICE_REQUIRED = {
    "slice_id", "obligation_ids", "acceptance_ids", "failure_intent_ids", "production_owners",
    "verification_lane", "behavior_change", "affected_subjects", "state_transition", "proof",
    "rollback_scope", "allowed_write_paths", "execution_snapshot_paths", "planned_new_files",
    "terminal_predicate",
}
AGENT_CONTEXT_REQUIRED = {
    "slice_id", "requirement_ids", "obligation_ids", "acceptance_ids", "source_refs", "contracts",
    "allowed_paths", "forbidden_paths", "selector_intents", "validation_commands",
}


def _strings(value: Any, *, nonempty: bool = False) -> bool:
    return isinstance(value, list) and (not nonempty or bool(value)) and all(isinstance(item, str) and bool(item) for item in value)


def _objects(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, Mapping) for item in value)


def _runtime_fields(value: Mapping[str, Any]) -> set[str]:
    return set(value) & RUNTIME_ONLY_FIELDS


def _id_index(items: Sequence[Mapping[str, Any]], field: str, findings: list[str], label: str) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(items):
        value = item.get(field)
        if not isinstance(value, str) or not value:
            findings.append(f"{label}[{index}]:missing-{field}")
            continue
        if value in result:
            findings.append(f"{label}:{value}:duplicate")
            continue
        result[value] = item
    return result


def validate_semantic_bundle(bundle: Mapping[str, Any]) -> tuple[bool, list[str]]:
    findings: list[str] = []
    if not isinstance(bundle, Mapping):
        return False, ["bundle:not-object"]
    if bundle.get("schema_version") != "vdd.semantic-plan-bundle.v1":
        findings.append("bundle:schema-version")

    obligations = bundle.get("obligations")
    acceptances = bundle.get("acceptances")
    failure_intents = bundle.get("failure_intents")
    pre_slice = bundle.get("pre_slice_coverage")
    slices = bundle.get("slices")
    final_cover = bundle.get("final_plan_coverage")
    contexts = bundle.get("agent_contexts")
    for name, value in (("obligations", obligations), ("acceptances", acceptances), ("failure_intents", failure_intents), ("pre_slice_coverage", pre_slice), ("slices", slices), ("final_plan_coverage", final_cover), ("agent_contexts", contexts)):
        if not _objects(value):
            findings.append(f"bundle:{name}:not-object-list")
    if findings:
        return False, findings

    if "behavior_routing" in bundle:
        from semantic_behavior_contract import validate_routing_intent
        findings.extend(validate_routing_intent(bundle))

    obligation_by_id = _id_index(obligations, "obligation_id", findings, "obligation")
    acceptance_by_id = _id_index(acceptances, "acceptance_id", findings, "acceptance")
    failure_by_id = _id_index(failure_intents, "failure_intent_id", findings, "failure-intent")
    slice_by_id = _id_index(slices, "slice_id", findings, "slice")
    context_by_slice = _id_index(contexts, "slice_id", findings, "agent-context")

    active_obligations: set[str] = set()
    for obligation_id, item in obligation_by_id.items():
        if not OBLIGATION_FIELDS.issubset(item):
            findings.append(f"obligation:{obligation_id}:shape-incomplete")
            continue
        if item.get("requirement_type") not in {"Product", "Platform", "Governance"}:
            findings.append(f"obligation:{obligation_id}:requirement-type")
        if item.get("obligation_kind") not in {"behavior", "quality", "constraint", "governance"}:
            findings.append(f"obligation:{obligation_id}:kind")
        if item.get("status") not in {"active", "deferred", "not_applicable"}:
            findings.append(f"obligation:{obligation_id}:status")
        if not _strings(item.get("source_refs"), nonempty=True):
            findings.append(f"obligation:{obligation_id}:source-refs")
        for field in ("subject", "trigger", "state_before", "state_after", "expected_behavior", "observable_result"):
            if not isinstance(item.get(field), str) or not item[field]:
                findings.append(f"obligation:{obligation_id}:{field}")
        if item.get("status") == "active":
            active_obligations.add(obligation_id)

    acceptance_to_obligations: dict[str, set[str]] = {}
    for acceptance_id, item in acceptance_by_id.items():
        obligation_ids = item.get("obligation_ids")
        if not _strings(obligation_ids, nonempty=True):
            findings.append(f"acceptance:{acceptance_id}:obligation-ids")
            continue
        if set(obligation_ids) - set(obligation_by_id):
            findings.append(f"acceptance:{acceptance_id}:unknown-obligation")
        if not _strings(item.get("source_refs"), nonempty=True):
            findings.append(f"acceptance:{acceptance_id}:source-refs")
        if not _strings(item.get("assertion_ids"), nonempty=True):
            findings.append(f"acceptance:{acceptance_id}:assertion-ids")
        if not _strings(item.get("red_intent_ids"), nonempty=True):
            findings.append(f"acceptance:{acceptance_id}:red-intent-ids")
        oracle = item.get("oracle")
        if not isinstance(oracle, Mapping) or not {"observable", "expected", "forbidden"}.issubset(oracle):
            findings.append(f"acceptance:{acceptance_id}:oracle")
        acceptance_to_obligations[acceptance_id] = set(obligation_ids)

    covered_active = set().union(*acceptance_to_obligations.values()) if acceptance_to_obligations else set()
    if active_obligations - covered_active:
        findings.append("acceptance:hard-uncovered-obligation:" + ",".join(sorted(active_obligations - covered_active)))

    for failure_id, item in failure_by_id.items():
        acceptance_ids = item.get("acceptance_ids")
        if not _strings(acceptance_ids, nonempty=True):
            findings.append(f"failure-intent:{failure_id}:acceptance-ids")
        elif set(acceptance_ids) - set(acceptance_by_id):
            findings.append(f"failure-intent:{failure_id}:unknown-acceptance")
        if not isinstance(item.get("selector_intent"), str) or not item["selector_intent"]:
            findings.append(f"failure-intent:{failure_id}:selector-intent")
        if item.get("expected_outcome") != "fail":
            findings.append(f"failure-intent:{failure_id}:expected-outcome")
        if _runtime_fields(item) - {"failure_id", "failure_family"}:
            findings.append(f"failure-intent:{failure_id}:contains-runtime-evidence")

    pre_edges = list(pre_slice)
    for index, edge in enumerate(pre_edges):
        if set(edge) != PRE_SLICE_FIELDS:
            findings.append(f"v5-edge[{index}]:shape")
        if _runtime_fields(edge) or any(field in edge for field in ("slice_id", "verification_lane", "terminal_predicate", "stage_scope")):
            findings.append(f"v5-edge[{index}]:future-field")
        if edge.get("obligation_id") not in obligation_by_id:
            findings.append(f"v5-edge[{index}]:unknown-obligation")
        if edge.get("acceptance_id") not in acceptance_by_id:
            findings.append(f"v5-edge[{index}]:unknown-acceptance")
        if edge.get("failure_intent_id") not in failure_by_id:
            findings.append(f"v5-edge[{index}]:unknown-failure-intent")
    active_acceptances = {acceptance_id for acceptance_id, obligation_ids in acceptance_to_obligations.items() if obligation_ids & active_obligations}
    v5_acceptances = {edge.get("acceptance_id") for edge in pre_edges if isinstance(edge.get("acceptance_id"), str)}
    if v5_acceptances != active_acceptances:
        findings.append("v5:acceptance-exact-cover")

    for slice_id, item in slice_by_id.items():
        if not SLICE_REQUIRED.issubset(item):
            findings.append(f"slice:{slice_id}:behavior-contract-incomplete")
        if _runtime_fields(item):
            findings.append(f"slice:{slice_id}:contains-runtime-evidence")
        for field in ("obligation_ids", "acceptance_ids", "failure_intent_ids", "production_owners", "affected_subjects", "execution_snapshot_paths"):
            if not _strings(item.get(field), nonempty=True):
                findings.append(f"slice:{slice_id}:{field}")
        if item.get("verification_lane") not in {"unit", "integration", "matrix", "runtime"}:
            findings.append(f"slice:{slice_id}:verification-lane")
        for field in ("behavior_change", "state_transition", "terminal_predicate"):
            if not isinstance(item.get(field), str) or not item[field]:
                findings.append(f"slice:{slice_id}:{field}")
        proof = item.get("proof")
        if not isinstance(proof, Mapping) or not {"acceptance_ids", "selector_intents", "assertion_ids"}.issubset(proof):
            findings.append(f"slice:{slice_id}:proof")
        rollback = item.get("rollback_scope")
        if not isinstance(rollback, Mapping) or not {"production_paths", "state_or_schema_compatibility"}.issubset(rollback):
            findings.append(f"slice:{slice_id}:rollback-scope")

    final_edges = list(final_cover)
    seen_semantic_keys: set[tuple[str, str, str, str, str]] = set()
    final_acceptances: set[str] = set()
    for index, edge in enumerate(final_edges):
        if set(edge) != FINAL_COVER_FIELDS:
            findings.append(f"v6a-edge[{index}]:shape")
        if _runtime_fields(edge):
            findings.append(f"v6a-edge[{index}]:contains-runtime-evidence")
        if edge.get("stage_scope") != STAGE_SCOPE:
            findings.append(f"v6a-edge[{index}]:stage-scope")
        slice_id = edge.get("slice_id")
        if slice_id not in slice_by_id:
            findings.append(f"v6a-edge[{index}]:unknown-slice")
        else:
            slice_item = slice_by_id[slice_id]
            if edge.get("acceptance_id") not in set(slice_item.get("acceptance_ids", [])):
                findings.append(f"v6a-edge[{index}]:acceptance-not-in-slice")
            if edge.get("verification_lane") != slice_item.get("verification_lane"):
                findings.append(f"v6a-edge[{index}]:lane-mismatch")
            if edge.get("terminal_predicate") != slice_item.get("terminal_predicate"):
                findings.append(f"v6a-edge[{index}]:terminal-mismatch")
        semantic_key = tuple(str(edge.get(field)) for field in ("requirement_id", "obligation_id", "acceptance_id", "source_ref", "failure_intent_id"))
        if semantic_key in seen_semantic_keys:
            findings.append(f"v6a-edge[{index}]:duplicate-semantic-edge")
        seen_semantic_keys.add(semantic_key)
        if isinstance(edge.get("acceptance_id"), str):
            final_acceptances.add(edge["acceptance_id"])
    if final_acceptances != active_acceptances:
        findings.append("v6a:acceptance-exact-cover")

    if set(context_by_slice) != set(slice_by_id):
        findings.append("agent-context:slice-set-mismatch")
    for slice_id, context in context_by_slice.items():
        if not AGENT_CONTEXT_REQUIRED.issubset(context):
            findings.append(f"agent-context:{slice_id}:shape-incomplete")
            continue
        selected = slice_by_id.get(slice_id)
        if selected is None:
            continue
        if set(context.get("obligation_ids", [])) != set(selected.get("obligation_ids", [])):
            findings.append(f"agent-context:{slice_id}:obligation-projection")
        if set(context.get("acceptance_ids", [])) != set(selected.get("acceptance_ids", [])):
            findings.append(f"agent-context:{slice_id}:acceptance-projection")
        proof = selected.get("proof", {})
        if set(context.get("selector_intents", [])) != set(proof.get("selector_intents", [])):
            findings.append(f"agent-context:{slice_id}:selector-projection")
        commands = context.get("validation_commands")
        if not isinstance(commands, list) or not commands or any(not isinstance(command, list) or not command or any(not isinstance(part, str) or not part for part in command) for command in commands):
            findings.append(f"agent-context:{slice_id}:validation-commands")

    return not findings, findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        bundle = json.loads(args.input.read_text(encoding="utf-8"))
        valid, findings = validate_semantic_bundle(bundle)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"valid": False, "findings": [f"input:{exc}"]}, sort_keys=True))
        return 1
    print(json.dumps({"valid": valid, "findings": findings}, sort_keys=True))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())


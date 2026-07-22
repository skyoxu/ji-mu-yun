from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from attempt_lineage_guards import validate_accepted_stage_order, validate_event_lifecycle
from contract_guards import schema_error
from protocol_artifact_guards import (
    bytes_hash,
    canonical_bytes,
    classify_scope,
    finding as _finding,
    ref_key,
    safe_relative,
    store_key,
    validate_context_artifacts,
    validate_ref,
    value_hash,
)


SCHEMA_FILES = {
    "context_manifest": "context-manifest.v1.schema.json",
    "slice_capsule": "slice-capsule.v1.schema.json",
    "backend_request": "backend-request.v1.schema.json",
    "backend_response": "backend-response.v1.schema.json",
    "diff_manifest": "diff-manifest.v1.schema.json",
    "adapter_decision": "adapter-decision.v1.schema.json",
    "event": "agent-attempt-event.v1.schema.json",
    "baseline_file_manifest": "baseline-file-manifest.v1.schema.json",
    "attempt_ledger_manifest": "attempt-ledger-manifest.v1.schema.json",
}
STAGES = ["red", "green", "refactor"]
STAGE_GOALS = {
    "red": "observe-red",
    "green": "make-red-green",
    "refactor": "preserve-green-refactor",
}
STAGE_STATES = {
    "red": "red-observed",
    "green": "green-observed",
    "refactor": "refactor-verified",
}


def validate_protocol_contract(contract: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    protocol = contract.get("protocol_artifacts", {})
    expected_schemas = {
        "context_manifest": ".agents/skills/quick-dev-tdd-adapter/schemas/context-manifest.v1.schema.json",
        "slice_capsule": ".agents/skills/quick-dev-tdd-adapter/schemas/slice-capsule.v1.schema.json",
        "backend_request": ".agents/skills/quick-dev-tdd-adapter/schemas/backend-request.v1.schema.json",
        "backend_response": ".agents/skills/quick-dev-tdd-adapter/schemas/backend-response.v1.schema.json",
        "diff_manifest": ".agents/skills/quick-dev-tdd-adapter/schemas/diff-manifest.v1.schema.json",
        "adapter_decision": ".agents/skills/quick-dev-tdd-adapter/schemas/adapter-decision.v1.schema.json",
        "attempt_event": ".agents/skills/quick-dev-tdd-adapter/schemas/agent-attempt-event.v1.schema.json",
        "baseline_file_manifest": ".agents/skills/quick-dev-tdd-adapter/schemas/baseline-file-manifest.v1.schema.json",
        "attempt_ledger_manifest": ".agents/skills/quick-dev-tdd-adapter/schemas/attempt-ledger-manifest.v1.schema.json",
    }
    capsule_policy = protocol.get("capsule_policy", {})
    attempt_policy = protocol.get("attempt_policy", {})
    if (
        protocol.get("context_layout") != "context/<capsule-id>"
        or protocol.get("attempt_layout") != "attempts/<attempt-id>"
        or protocol.get("schemas") != expected_schemas
        or not capsule_policy
        or any(value is not True for key, value in capsule_policy.items() if key != "standalone_authority")
        or capsule_policy.get("standalone_authority") is not False
    ):
        findings.append(_finding("RMAP-CAPSULE-CONTEXT", "protocol-artifacts", "persisted capsule policy is incomplete"))
    false_keys = {"adapter_decision_authoritative", "raw_body_persisted", "sensitive_data_allowed"}
    if (
        not attempt_policy
        or any(value is not True for key, value in attempt_policy.items() if key not in false_keys)
        or any(attempt_policy.get(key) is not False for key in false_keys)
    ):
        findings.append(_finding("RMAP-ATTEMPT-AUTHORITY", "protocol-artifacts", "attempt ledger policy is incomplete or authoritative"))
    return findings


def _precheck(bundle: dict[str, Any]) -> list[dict[str, str]]:
    for pair in bundle.get("contexts", []):
        if not isinstance(pair, dict):
            continue
        context = pair.get("context_manifest", {})
        capsule = pair.get("slice_capsule", {})
        blocker = capsule.get("latest_blocker_ref") if isinstance(capsule, dict) else None
        if blocker is not None and (
            not isinstance(blocker, dict)
            or set(blocker) != {"role", "path_type", "path", "sha256"}
        ):
            return [_finding("RMAP-CAPSULE-BLOCKER-REF", "latest_blocker_ref", "latest blocker must be a typed artifact reference or null")]
        refs = [context.get("capsule_ref"), *context.get("artifact_refs", [])]
        if isinstance(capsule, dict):
            refs.extend([*capsule.get("authority_refs", []), capsule.get("implementation_contract"), capsule.get("baseline_ref"), *capsule.get("stage_evidence_refs", [])])
            if blocker is not None:
                refs.append(blocker)
        for ref in refs:
            if isinstance(ref, dict) and ref.get("path_type") not in {"repo_path", "plan_path", "run_path"}:
                return [_finding("RMAP-PROTOCOL-PATH", "artifact-ref", "artifact reference has a missing or ambiguous typed root")]
    attempts = bundle.get("attempts")
    if not isinstance(attempts, list) or not attempts or any(not isinstance(item, dict) for item in attempts):
        return [_finding("RMAP-ATTEMPT-PARTIAL", "attempts", "attempt collection is missing or invalid")]
    for index, attempt in enumerate(attempts):
        response = attempt.get("backend_response", {})
        request = attempt.get("backend_request", {})
        actor = request.get("actor", {}) if isinstance(request, dict) else {}
        if response.get("raw_body_persisted") is not False or response.get("contains_sensitive_data") is not False:
            return [_finding("RMAP-ATTEMPT-SENSITIVE-EVIDENCE", f"attempts[{index}]", "raw or sensitive backend response content is persisted")]
        if request.get("raw_body_persisted") is not False or request.get("contains_sensitive_data") is not False or actor.get("identity_authoritative") is not False:
            return [_finding("RMAP-ATTEMPT-SENSITIVE-EVIDENCE", f"attempts[{index}]", "request content or actor attestation exceeds its authority")]
        decision = attempt.get("adapter_decision")
        if not isinstance(decision, dict):
            return [_finding("RMAP-ATTEMPT-PARTIAL", f"attempts[{index}]", "adapter decision is missing; attempt is incomplete")]
        if decision.get("authorizes") != []:
            return [_finding("RMAP-ATTEMPT-AUTHORITY", f"attempts[{index}]", "adapter decision claims standalone transition authority")]
    return []


def _schema_findings(plan_root: Path, bundle: dict[str, Any]) -> list[dict[str, str]]:
    schemas = {
        key: json.loads((plan_root.parents[1] / ".agents" / "skills" / "quick-dev-tdd-adapter" / "schemas" / name).read_text(encoding="utf-8"))
        for key, name in SCHEMA_FILES.items()
    }
    documents: list[tuple[str, Any]] = []
    for pair in bundle["contexts"]:
        documents.extend((kind, pair[kind]) for kind in ("context_manifest", "slice_capsule"))
    for attempt in bundle["attempts"]:
        documents.extend((key, attempt.get(key)) for key in ("backend_request", "backend_response", "diff_manifest", "adapter_decision"))
    documents.extend(("event", event) for event in bundle["events"])
    documents.extend([
        ("baseline_file_manifest", bundle.get("baseline_file_manifest")),
        ("attempt_ledger_manifest", bundle.get("attempt_ledger_manifest")),
    ])
    for index, (kind, document) in enumerate(documents):
        error = schema_error(document, schemas[kind])
        if error:
            return [_finding("RMAP-PROTOCOL-SCHEMA", f"{kind}[{index}]", error)]
    return []


def validate_protocol_bundle(
    plan_root: Path,
    bundle: dict[str, Any],
    *,
    artifact_store: dict[tuple[str, str], bytes],
    file_versions: dict[tuple[str, str, str], bytes | None],
    require_complete: bool = True,
) -> list[dict[str, str]]:
    findings = _precheck(bundle)
    if findings:
        return findings
    expected_keys = {
        "schema_version", "contexts", "attempts", "events",
        "baseline_file_manifest", "attempt_ledger_manifest",
    }
    if set(bundle) != expected_keys or bundle.get("schema_version") != "rmap.capsule-attempt-bundle.v1":
        return [_finding("RMAP-PROTOCOL-SCHEMA", "bundle", "protocol bundle shape is invalid")]
    contexts = bundle.get("contexts")
    if not isinstance(contexts, list) or not contexts or any(set(item) != {"context_manifest", "slice_capsule"} for item in contexts if isinstance(item, dict)):
        return [_finding("RMAP-PROTOCOL-SCHEMA", "bundle", "protocol context collection is invalid")]
    findings = _schema_findings(plan_root, bundle)
    if findings:
        return findings

    first_capsule = contexts[0]["slice_capsule"]
    identity = (first_capsule["plan_id"], first_capsule["slice_id"], first_capsule["run_id"])
    expected_exclusions = {"bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"}
    capsule_by_hash: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    previous_capsule_hash: str | None = None
    for pair in contexts:
        context, capsule = pair["context_manifest"], pair["slice_capsule"]
        if (
            (context["plan_id"], context["slice_id"], context["run_id"]) != identity
            or (capsule["plan_id"], capsule["slice_id"], capsule["run_id"]) != identity
            or context["capsule_id"] != capsule["capsule_id"]
            or context["stage"] != capsule["stage"]
        ):
            return [_finding("RMAP-CAPSULE-CONTEXT", "context", "manifest and capsule identities differ")]
        capsule_ref = context["capsule_ref"]
        capsule_hash = capsule_ref["sha256"]
        if context["predecessor_capsule_hash"] != previous_capsule_hash or capsule["predecessor_capsule_hash"] != previous_capsule_hash:
            return [_finding("RMAP-CAPSULE-CONTEXT", "context", "capsule predecessor hash is stale")]
        if capsule["slice_id"] == "RMAP-S2" and capsule["exit_predicate"] != "slice-ready":
            return [_finding("RMAP-CAPSULE-PREDICATE", "slice-capsule", "S2 capsule escalates beyond slice-ready")]
        if capsule.get("authorizes") != [] or not expected_exclusions.issubset(set(capsule.get("does_not_authorize", []))):
            return [_finding("RMAP-CAPSULE-PREDICATE", "slice-capsule", "capsule gained transition authority")]
        artifact_findings = validate_context_artifacts(context, capsule, artifact_store)
        if artifact_findings:
            return [artifact_findings[0]]
        capsule_by_hash[capsule_hash] = (context, capsule)
        previous_capsule_hash = capsule_hash

    attempts = bundle["attempts"]
    accepted_counts: dict[str, int] = {}
    for attempt in attempts:
        decision = attempt["adapter_decision"]
        if decision["decision"] == "accepted_for_validation":
            accepted_counts[decision["stage"]] = accepted_counts.get(decision["stage"], 0) + 1
    if any(count > 1 for count in accepted_counts.values()):
        return [_finding("RMAP-ATTEMPT-STAGE-UNIQUENESS", "attempts", "a stage has multiple accepted attempt lineages")]
    stage_findings = validate_accepted_stage_order(attempts, require_complete=require_complete)
    if stage_findings:
        return stage_findings

    previous_attempt: str | None = None
    previous_decision_hash: str | None = None
    ledger_attempts: list[dict[str, Any]] = []
    baseline_entries = {
        entry["path"]: entry for entry in bundle["baseline_file_manifest"]["files"]
    }
    observed_paths: set[str] = set()
    for index, attempt in enumerate(attempts):
        request, response, diff, decision = (
            attempt[key] for key in ("backend_request", "backend_response", "diff_manifest", "adapter_decision")
        )
        attempt_identity = (request["plan_id"], request["slice_id"], request["run_id"])
        attempt_id, stage = request["attempt_id"], request["stage"]
        if attempt_identity != identity or any(
            (doc["plan_id"], doc["slice_id"], doc["run_id"], doc["attempt_id"], doc["stage"])
            != (*identity, attempt_id, stage)
            for doc in (response, diff, decision)
        ):
            return [_finding("RMAP-ATTEMPT-LINEAGE", attempt_id, "attempt document identities differ")]
        stage_binding_id = f"STAGE-{stage.upper()}"
        if request["stage_binding_id"] != stage_binding_id or decision["stage_binding_id"] != stage_binding_id:
            return [_finding("RMAP-ATTEMPT-STAGE-RESULT-BINDING", attempt_id, "attempt does not bind the canonical stage identity")]
        capsule_hash = request["capsule_ref"]["sha256"]
        attempt_context = capsule_by_hash.get(capsule_hash, ({}, {}))[0]
        ref_errors = validate_ref(request["capsule_ref"], artifact_store, f"{attempt_id}.capsule_ref", role_required=False)
        expected_payload_hash = value_hash({
            "capsule_hash": capsule_hash,
            "stage_binding_id": stage_binding_id,
            "goal": request["goal"],
            "allowed_command_ids": request["allowed_command_ids"],
        })
        if ref_errors or not attempt_context or request["request_payload_hash"] != expected_payload_hash:
            return [_finding("RMAP-ATTEMPT-REQUEST-BINDING", attempt_id, "backend request is not bound to current Capsule bytes and stage")]
        expected_commands = capsule_by_hash[capsule_hash][1]["target_command_ids"]
        if request["allowed_command_ids"] != expected_commands:
            return [_finding("RMAP-ATTEMPT-COMMAND", attempt_id, "backend request commands do not equal bound Capsule command IDs")]
        diff_paths = [entry["path"] for entry in diff["files"]]
        if response["changed_files"] != diff_paths:
            return [_finding("RMAP-ATTEMPT-RESPONSE-DIFF", attempt_id, "backend response changed-file set differs from canonical diff")]
        if not set(response["commands_attempted"]).issubset(set(request["allowed_command_ids"])):
            return [_finding("RMAP-ATTEMPT-COMMAND", attempt_id, "backend attempted an unapproved command")]
        boundaries = capsule_by_hash[capsule_hash][1]["boundaries"]
        expected_forbidden = False
        for entry in diff["files"]:
            expected_scope = classify_scope(entry["path"], boundaries)
            if entry["scope"] != expected_scope:
                return [_finding("RMAP-ATTEMPT-DIFF-SCOPE", attempt_id, "diff scope label does not match Capsule boundaries")]
            expected_forbidden |= expected_scope == "forbidden"
            before = file_versions.get((attempt_id, "before", entry["path"]))
            after = file_versions.get((attempt_id, "after", entry["path"]))
            result_snapshot = entry.get("result_snapshot_ref")
            change_type = entry["change_type"]
            if (
                (change_type == "add" and (before is not None or after is None or result_snapshot is None))
                or (change_type == "modify" and (before is None or after is None or result_snapshot is None))
                or (change_type == "delete" and (before is None or after is not None or result_snapshot is not None))
            ):
                return [_finding("RMAP-ATTEMPT-DIFF-BINDING", attempt_id, "change type does not match before/after snapshot semantics")]
            if after is not None:
                snapshot_errors = validate_ref(result_snapshot, artifact_store, f"{attempt_id}.result_snapshot_ref", role_required=False)
                if snapshot_errors:
                    return [_finding("RMAP-ATTEMPT-AFTER-HASH", attempt_id, "result snapshot is missing or stale against actual bytes")]
                expected_snapshot_path = f"attempts/{attempt_id}/result-files/{entry['path']}"
                if result_snapshot["path_type"] != "run_path" or result_snapshot["path"] != expected_snapshot_path:
                    return [_finding("RMAP-ATTEMPT-AFTER-HASH", attempt_id, "result snapshot path does not bind the changed file path")]
            elif result_snapshot is not None:
                return [_finding("RMAP-ATTEMPT-AFTER-HASH", attempt_id, "deleted file cannot retain a result snapshot")]
            before_hash = None if before is None else bytes_hash(before)
            after_hash = None if after is None else bytes_hash(after)
            if entry["before_sha256"] != before_hash:
                return [_finding("RMAP-ATTEMPT-BEFORE-HASH", attempt_id, "diff before hash does not match baseline snapshot bytes")]
            if entry["after_sha256"] != after_hash:
                return [_finding("RMAP-ATTEMPT-AFTER-HASH", attempt_id, "diff after hash does not match current result bytes")]
            baseline = baseline_entries.get(entry["path"])
            first_add = entry.get("change_type") == "add" and before_hash is None and baseline is None
            if entry["path"] not in observed_paths and not first_add and (baseline is None or baseline.get("sha256") != before_hash):
                return [_finding("RMAP-ATTEMPT-BEFORE-HASH", attempt_id, "first observed file version is not bound to baseline file manifest")]
            observed_paths.add(entry["path"])
        expected_baseline_root = value_hash({entry["path"]: entry["before_sha256"] for entry in diff["files"]})
        expected_result_root = value_hash({entry["path"]: entry["after_sha256"] for entry in diff["files"]})
        if (
            diff["actual_diff_hash"] != value_hash(diff["files"])
            or diff["baseline_worktree_hash"] != expected_baseline_root
            or diff["result_worktree_hash"] != expected_result_root
            or diff["contains_forbidden_change"] != expected_forbidden
            or (decision["decision"] == "accepted_for_validation" and any(entry["scope"] != "allowed" for entry in diff["files"]))
        ):
            return [_finding("RMAP-ATTEMPT-DIFF-BINDING", attempt_id, "canonical diff or accepted scope is invalid")]
        if (
            decision["input_context_hash"] != attempt_context["context_hash"]
            or decision["backend_request_hash"] != value_hash(request)
            or decision["backend_response_hash"] != value_hash(response)
            or decision["actual_diff_hash"] != diff["actual_diff_hash"]
        ):
            return [_finding("RMAP-ATTEMPT-DECISION-BINDING", attempt_id, "adapter decision does not bind request, response, diff, and context")]
        if attempt_id != f"ATTEMPT-{index + 1:03d}" or request["previous_attempt_id"] != previous_attempt or decision["previous_attempt_id"] != previous_attempt or decision["previous_decision_hash"] != previous_decision_hash:
            return [_finding("RMAP-ATTEMPT-LINEAGE", attempt_id, "attempt predecessor identity or decision hash is invalid")]
        expected_state = STAGE_STATES[stage]
        if decision["decision"] == "accepted_for_validation":
            if decision["failure_ids"] or decision["next_allowed_state"] != expected_state:
                return [_finding("RMAP-ATTEMPT-STAGE", attempt_id, "accepted attempt has contradictory failure or next-state semantics")]
        elif not decision["failure_ids"] or decision["next_allowed_state"] not in {"blocked", "failed"}:
            return [_finding("RMAP-ATTEMPT-STAGE", attempt_id, "rejected or incomplete attempt lacks failure semantics")]
        stage_result_path = decision["stage_result_path"]
        if not safe_relative(stage_result_path):
            return [_finding("RMAP-PROTOCOL-PATH", attempt_id, "stage result path escapes run root")]
        stage_bytes = artifact_store.get(("run_path", stage_result_path))
        try:
            stage_result = json.loads(stage_bytes.decode("utf-8")) if stage_bytes is not None else None
        except (UnicodeError, ValueError):
            stage_result = None
        decision_hash = value_hash(decision)
        expected_stage_binding = {
            "stage_binding_id": stage_binding_id,
            "attempt_id": attempt_id,
            "decision_hash": decision_hash,
            "capsule_hash": capsule_hash,
            "context_hash": attempt_context["context_hash"],
        }
        if not isinstance(stage_result, dict) or any(stage_result.get(key) != value for key, value in expected_stage_binding.items()):
            return [_finding("RMAP-ATTEMPT-STAGE-RESULT-BINDING", attempt_id, "stage result does not bind the accepted decision and Capsule")]
        ledger_attempts.append({
            "attempt_id": attempt_id,
            "stage": stage,
            "request_hash": value_hash(request),
            "response_hash": value_hash(response),
            "diff_hash": value_hash(diff),
            "decision_hash": decision_hash,
            "stage_result_hash": bytes_hash(stage_bytes),
        })
        previous_attempt, previous_decision_hash = attempt_id, decision_hash

    event_findings = validate_event_lifecycle(identity, attempts, bundle["events"], artifact_store)
    if event_findings:
        return event_findings
    event_bytes = artifact_store.get(("run_path", "run-events.jsonl"))
    if event_bytes is None:
        return [_finding("RMAP-ATTEMPT-LEDGER", "run-events.jsonl", "raw event log bytes are missing")]
    ledger = bundle["attempt_ledger_manifest"]
    expected_ledger = {
        "schema_version": "jimuyun.attempt-ledger-manifest.v1",
        "plan_id": identity[0],
        "slice_id": identity[1],
        "run_id": identity[2],
        "attempts": ledger_attempts,
        "run_events_hash": bytes_hash(event_bytes),
        "final_event_hash": value_hash(bundle["events"][-1]),
    }
    if any(ledger.get(key) != value for key, value in expected_ledger.items()) or ledger.get("root_hash") != value_hash(expected_ledger):
        return [_finding("RMAP-ATTEMPT-LEDGER", "attempt-ledger-manifest", "ledger manifest does not exactly close attempts and raw event bytes")]
    return []

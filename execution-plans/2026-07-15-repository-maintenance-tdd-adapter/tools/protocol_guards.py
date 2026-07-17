from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from contract_guards import schema_error


SCHEMA_FILES = {
    "context_manifest": "context-manifest.v1.schema.json",
    "slice_capsule": "slice-capsule.v1.schema.json",
    "backend_request": "backend-request.v1.schema.json",
    "backend_response": "backend-response.v1.schema.json",
    "diff_manifest": "diff-manifest.v1.schema.json",
    "adapter_decision": "adapter-decision.v1.schema.json",
    "event": "agent-attempt-event.v1.schema.json",
}


def _finding(rule_id: str, target: str, message: str) -> dict[str, str]:
    return {"rule_id": rule_id, "target": target, "message": message}


def value_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def validate_protocol_contract(contract: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    protocol = contract.get("protocol_artifacts", {})
    expected_schemas = {
        "context_manifest": "schemas/context-manifest.v1.schema.json", "slice_capsule": "schemas/slice-capsule.v1.schema.json",
        "backend_request": "schemas/backend-request.v1.schema.json", "backend_response": "schemas/backend-response.v1.schema.json",
        "diff_manifest": "schemas/diff-manifest.v1.schema.json", "adapter_decision": "schemas/adapter-decision.v1.schema.json",
        "attempt_event": "schemas/agent-attempt-event.v1.schema.json",
    }
    capsule_policy = protocol.get("capsule_policy", {})
    attempt_policy = protocol.get("attempt_policy", {})
    if protocol.get("context_layout") != "context/<capsule-id>" or protocol.get("attempt_layout") != "attempts/<attempt-id>" or protocol.get("schemas") != expected_schemas or not capsule_policy or any(value is not True for key, value in capsule_policy.items() if key != "standalone_authority") or capsule_policy.get("standalone_authority") is not False:
        findings.append(_finding("RMAP-CAPSULE-CONTEXT", "protocol-artifacts", "persisted capsule policy is incomplete"))
    false_keys = {"adapter_decision_authoritative", "raw_body_persisted", "sensitive_data_allowed"}
    if not attempt_policy or any(value is not True for key, value in attempt_policy.items() if key not in false_keys) or any(attempt_policy.get(key) is not False for key in false_keys):
        findings.append(_finding("RMAP-ATTEMPT-AUTHORITY", "protocol-artifacts", "attempt ledger policy is incomplete or authoritative"))
    return findings


def _safe_relative(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and not any(":" in part for part in path.parts)


def _precheck(bundle: dict[str, Any]) -> list[dict[str, str]]:
    attempts = bundle.get("attempts")
    if not isinstance(attempts, list) or not attempts or any(not isinstance(item, dict) for item in attempts):
        return [_finding("RMAP-ATTEMPT-PARTIAL", "attempts", "attempt collection is missing or invalid")]
    for index, attempt in enumerate(attempts):
        response = attempt.get("backend_response", {})
        if response.get("raw_body_persisted") is not False or response.get("contains_sensitive_data") is not False:
            return [_finding("RMAP-ATTEMPT-SENSITIVE-EVIDENCE", f"attempts[{index}]", "raw or sensitive backend response content is persisted")]
        request = attempt.get("backend_request", {})
        actor = request.get("actor", {}) if isinstance(request, dict) else {}
        if request.get("raw_body_persisted") is not False or request.get("contains_sensitive_data") is not False or actor.get("identity_authoritative") is not False:
            return [_finding("RMAP-ATTEMPT-SENSITIVE-EVIDENCE", f"attempts[{index}]", "request content or actor attestation exceeds its authority")]
        decision = attempt.get("adapter_decision")
        if not isinstance(decision, dict):
            return [_finding("RMAP-ATTEMPT-PARTIAL", f"attempts[{index}]", "adapter decision is missing; attempt is incomplete")]
        if decision.get("authorizes") != []:
            return [_finding("RMAP-ATTEMPT-AUTHORITY", f"attempts[{index}]", "adapter decision claims standalone transition authority")]
    return []


def validate_protocol_bundle(plan_root: Path, bundle: dict[str, Any]) -> list[dict[str, str]]:
    findings = _precheck(bundle)
    if findings:
        return findings
    legacy = {"schema_version", "context_manifest", "slice_capsule", "attempts", "events"}
    plural = {"schema_version", "contexts", "attempts", "events"}
    if set(bundle) == legacy:
        contexts = [{"context_manifest": bundle["context_manifest"], "slice_capsule": bundle["slice_capsule"]}]
    elif set(bundle) == plural and isinstance(bundle.get("contexts"), list) and bundle["contexts"]:
        contexts = bundle["contexts"]
    else:
        return [_finding("RMAP-PROTOCOL-SCHEMA", "bundle", "protocol bundle shape is invalid")]
    if bundle.get("schema_version") != "rmap.capsule-attempt-bundle.v1" or any(set(item) != {"context_manifest", "slice_capsule"} for item in contexts if isinstance(item, dict)):
        return [_finding("RMAP-PROTOCOL-SCHEMA", "bundle", "protocol bundle shape is invalid")]
    schemas = {key: json.loads((plan_root / "schemas" / name).read_text(encoding="utf-8")) for key, name in SCHEMA_FILES.items()}
    documents = [(kind, pair[kind]) for pair in contexts for kind in ("context_manifest", "slice_capsule")]
    for index, attempt in enumerate(bundle["attempts"]):
        documents.extend((key, attempt.get(key)) for key in ("backend_request", "backend_response", "diff_manifest", "adapter_decision"))
    documents.extend(("event", event) for event in bundle["events"])
    for index, (kind, document) in enumerate(documents):
        error = schema_error(document, schemas[kind])
        if error:
            return [_finding("RMAP-PROTOCOL-SCHEMA", f"{kind}[{index}]", error)]
    context = contexts[0]["context_manifest"]
    capsule = contexts[0]["slice_capsule"]
    identity = (capsule["plan_id"], capsule["slice_id"], capsule["run_id"])
    expected_exclusions = {"bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"}
    capsule_by_hash: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    previous_capsule_hash: str | None = None
    paths: list[str] = []
    for pair in contexts:
        context, capsule = pair["context_manifest"], pair["slice_capsule"]
        if (context["plan_id"], context["slice_id"], context["run_id"]) != identity or (capsule["plan_id"], capsule["slice_id"], capsule["run_id"]) != identity or context["capsule_id"] != capsule["capsule_id"] or context["stage"] != capsule["stage"]:
            return [_finding("RMAP-CAPSULE-CONTEXT", "context", "manifest and capsule identities differ")]
        capsule_hash = value_hash(capsule)
        if context["capsule_ref"]["sha256"] != capsule_hash or context["context_hash"] != value_hash({"capsule_hash": capsule_hash, "artifact_refs": context["artifact_refs"]}) or context["predecessor_capsule_hash"] != previous_capsule_hash or capsule["predecessor_capsule_hash"] != previous_capsule_hash:
            return [_finding("RMAP-CAPSULE-CONTEXT", "context", "capsule, context, or predecessor hash is stale")]
        if capsule["slice_id"] == "RMAP-S2" and capsule["exit_predicate"] != "slice-ready":
            return [_finding("RMAP-CAPSULE-PREDICATE", "slice-capsule", "S2 capsule escalates beyond slice-ready")]
        if capsule.get("authorizes") != [] or not expected_exclusions.issubset(set(capsule.get("does_not_authorize", []))):
            return [_finding("RMAP-CAPSULE-PREDICATE", "slice-capsule", "capsule gained transition authority")]
        paths.extend([context["capsule_ref"]["path"], *[item["path"] for item in context["artifact_refs"]], capsule["implementation_contract"]["path"], capsule["baseline_ref"]["path"]])
        paths.extend(item["path"] for item in capsule["authority_refs"] + capsule["stage_evidence_refs"])
        capsule_by_hash[capsule_hash] = (context, capsule)
        previous_capsule_hash = capsule_hash
    if any(not _safe_relative(path) for path in paths):
        return [_finding("RMAP-PROTOCOL-PATH", "context", "protocol artifact path escapes its run or repository root")]
    accepted_counts: dict[str, int] = {}
    for attempt in bundle["attempts"]:
        decision = attempt["adapter_decision"]
        if decision["decision"] == "accepted_for_validation":
            accepted_counts[decision["stage"]] = accepted_counts.get(decision["stage"], 0) + 1
    if any(count > 1 for count in accepted_counts.values()):
        return [_finding("RMAP-ATTEMPT-STAGE-UNIQUENESS", "attempts", "a stage has multiple accepted attempt lineages")]
    accepted_by_stage: dict[str, int] = {}
    previous_attempt: str | None = None
    previous_decision_hash: str | None = None
    for index, attempt in enumerate(bundle["attempts"]):
        request, response, diff, decision = (attempt[key] for key in ("backend_request", "backend_response", "diff_manifest", "adapter_decision"))
        attempt_identity = (request["plan_id"], request["slice_id"], request["run_id"])
        attempt_id, stage = request["attempt_id"], request["stage"]
        if attempt_identity != identity or any((doc["plan_id"], doc["slice_id"], doc["run_id"], doc["attempt_id"], doc["stage"]) != (*identity, attempt_id, stage) for doc in (response, diff, decision)):
            return [_finding("RMAP-ATTEMPT-LINEAGE", attempt_id, "attempt document identities differ")]
        capsule_hash = request["capsule_ref"]["sha256"]
        attempt_context = capsule_by_hash.get(capsule_hash, ({}, {}))[0]
        if not attempt_context or request["request_payload_hash"] != value_hash({"capsule_hash": capsule_hash, "goal": request["goal"], "allowed_command_ids": request["allowed_command_ids"]}):
            return [_finding("RMAP-ATTEMPT-REQUEST-BINDING", attempt_id, "backend request is not bound to the current capsule")]
        if diff["actual_diff_hash"] != value_hash(diff["files"]) or (decision["decision"] == "accepted_for_validation" and diff["contains_forbidden_change"]):
            return [_finding("RMAP-ATTEMPT-DIFF-BINDING", attempt_id, "actual diff is stale or contains a forbidden change")]
        if decision["input_context_hash"] != attempt_context["context_hash"] or decision["backend_request_hash"] != value_hash(request) or decision["backend_response_hash"] != value_hash(response) or decision["actual_diff_hash"] != diff["actual_diff_hash"]:
            return [_finding("RMAP-ATTEMPT-DECISION-BINDING", attempt_id, "adapter decision does not bind request, response, diff, and context")]
        if attempt_id != f"ATTEMPT-{index + 1:03d}" or request["previous_attempt_id"] != previous_attempt or decision["previous_attempt_id"] != previous_attempt or decision["previous_decision_hash"] != previous_decision_hash:
            return [_finding("RMAP-ATTEMPT-LINEAGE", attempt_id, "attempt predecessor identity or decision hash is invalid")]
        expected_state = {"red": "red-observed", "green": "green-observed", "refactor": "refactor-verified"}[stage]
        if decision["decision"] == "accepted_for_validation":
            accepted_by_stage[stage] = accepted_by_stage.get(stage, 0) + 1
            if decision["failure_ids"] or decision["next_allowed_state"] != expected_state:
                return [_finding("RMAP-ATTEMPT-STAGE", attempt_id, "accepted attempt has contradictory failure or next-state semantics")]
        elif not decision["failure_ids"] or decision["next_allowed_state"] not in {"blocked", "failed"}:
            return [_finding("RMAP-ATTEMPT-STAGE", attempt_id, "rejected or incomplete attempt lacks failure semantics")]
        previous_attempt, previous_decision_hash = attempt_id, value_hash(decision)
    if any(count != 1 for count in accepted_by_stage.values()) or not accepted_by_stage:
        return [_finding("RMAP-ATTEMPT-STAGE-UNIQUENESS", "attempts", "each represented stage must have exactly one accepted attempt")]
    events = bundle["events"]
    if not events or [item["sequence"] for item in events] != list(range(1, len(events) + 1)):
        return [_finding("RMAP-ATTEMPT-LINEAGE", "events", "event sequence is missing or non-monotonic")]
    previous_event_hash: str | None = None
    for event in events:
        if (event["plan_id"], event["slice_id"], event["run_id"]) != identity or event["previous_event_hash"] != previous_event_hash:
            return [_finding("RMAP-ATTEMPT-LINEAGE", "events", "event identity or predecessor hash is invalid")]
        if any(not _safe_relative(item["path"]) for item in event["artifact_refs"]):
            return [_finding("RMAP-PROTOCOL-PATH", "events", "event artifact path escapes its run root")]
        previous_event_hash = value_hash(event)
    if events[-1]["event_type"] != "decision-finalized":
        return [_finding("RMAP-ATTEMPT-PARTIAL", "events", "accepted attempt is not finalized by the last event")]
    return []


def load_protocol_run(plan_root: Path, run_dir: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    contexts: list[dict[str, Any]] = []
    for directory in sorted((run_dir / "context").glob("CAP-*")):
        try:
            manifest = json.loads((directory / "context-manifest.v1.json").read_text(encoding="utf-8"))
            capsule = json.loads((directory / "slice-capsule.v1.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            findings.append(_finding("RMAP-ATTEMPT-PARTIAL", directory.as_posix(), str(exc))); continue
        if manifest.get("capsule_ref", {}).get("sha256") != value_hash(capsule):
            findings.append(_finding("RMAP-CAPSULE-CONTEXT", directory.as_posix(), "persisted capsule hash differs from its manifest"))
        contexts.append({"context_manifest": manifest, "slice_capsule": capsule})
    attempts: list[dict[str, Any]] = []
    for directory in sorted((run_dir / "attempts").glob("ATTEMPT-*")):
        attempt: dict[str, Any] = {}
        for key, name in (("backend_request", "backend-request.v1.json"), ("backend_response", "backend-response.v1.json"), ("diff_manifest", "diff-manifest.v1.json"), ("adapter_decision", "adapter-decision.v1.json")):
            try:
                attempt[key] = json.loads((directory / name).read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                findings.append(_finding("RMAP-ATTEMPT-PARTIAL", directory.as_posix(), str(exc))); break
        if len(attempt) == 4:
            attempts.append(attempt)
    events: list[dict[str, Any]] = []
    try:
        events = [json.loads(line) for line in (run_dir / "run-events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        findings.append(_finding("RMAP-ATTEMPT-PARTIAL", "run-events.jsonl", str(exc)))
    bundle = {"schema_version": "rmap.capsule-attempt-bundle.v1", "contexts": contexts, "attempts": attempts, "events": events}
    if not findings:
        findings.extend(validate_protocol_bundle(plan_root, bundle))
    return bundle, findings


def apply_protocol_mutations(bundle: dict[str, Any], mutations: list[dict[str, Any]]) -> dict[str, Any]:
    result = copy.deepcopy(bundle)
    for mutation in mutations:
        parts = [part.replace("~1", "/").replace("~0", "~") for part in mutation["path"].strip("/").split("/")]
        current: Any = result
        for part in parts[:-1]:
            current = current[int(part)] if isinstance(current, list) else current[part]
        key = parts[-1]
        if mutation["op"] == "replace":
            if isinstance(current, list):
                current[int(key)] = mutation["value"]
            else:
                current[key] = mutation["value"]
        elif mutation["op"] == "remove":
            if isinstance(current, list):
                del current[int(key)]
            else:
                del current[key]
        elif mutation["op"] == "add":
            if isinstance(current, list):
                current.append(mutation["value"]) if key == "-" else current.insert(int(key), mutation["value"])
            else:
                current[key] = mutation["value"]
        else:
            raise ValueError(f"unsupported mutation op: {mutation['op']}")
    return result


def evaluate_protocol_fixture(plan_root: Path, fixture_id: str, fixtures: dict[str, Any]) -> list[dict[str, str]]:
    case = next((item for item in fixtures.get("cases", []) if item.get("id") == fixture_id), None)
    if case is None:
        return [_finding("RMAP-STRUCT-FIXTURE", fixture_id, "unknown protocol fixture")]
    return validate_protocol_bundle(plan_root, apply_protocol_mutations(fixtures["valid_bundle"], case.get("mutations", [])))


def validate_protocol_fixture_suite(plan_root: Path, fixtures: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if validate_protocol_bundle(plan_root, fixtures.get("valid_bundle", {})):
        return [_finding("RMAP-STRUCT-FIXTURE", "valid-protocol-bundle", "valid capsule and attempt fixture failed")]
    for case in fixtures.get("cases", []):
        rules = sorted({item["rule_id"] for item in evaluate_protocol_fixture(plan_root, case.get("id", "fixture"), fixtures)})
        if rules != [case.get("expected_rule")]:
            findings.append(_finding("RMAP-STRUCT-FIXTURE", str(case.get("id")), f"expected {[case.get('expected_rule')]}, observed {rules}"))
    return findings

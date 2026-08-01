#!/usr/bin/env python3
"""Deterministic workflow model classification and route decisions."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import _llm_backend as llm_backend


SC_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SC_ROOT.parents[1]
DEFAULT_POLICY_PATH = SC_ROOT / "config" / "workflow_model_routes.v1.json"
DECISION_SCHEMA_VERSION = "jimuyun.workflow-model-route-decision.v1"
QUICK_DEV_CLASSES = ("small_mechanical", "normal", "complex", "architectural")
ARCHITECTURAL_FACTS = (
    "changes_adr_or_invariant",
    "changes_public_api",
    "changes_database_schema",
    "changes_auth_security",
    "changes_runtime_deployment",
    "changes_shared_llm_entrypoint",
    "touches_protected_path",
    "changes_workflow_control_plane_ownership",
)
COMPLEX_FACTS = (
    "has_cross_module_consumers",
    "changes_state_or_recovery_semantics",
    "changes_concurrency_or_idempotency",
    "has_unresolved_behavioral_boundary",
)
REQUIRED_QUICK_DEV_FACTS = {
    *ARCHITECTURAL_FACTS,
    *COMPLEX_FACTS,
    "production_write_roots",
    "matching_test_roots",
    "deterministic_transform",
    "behavior_fully_specified",
    "introduces_contract",
    "introduces_dependency",
    "unknown_facts",
    "contradictory_facts",
}


class RoutingError(ValueError):
    """Raised when policy or typed route input is invalid."""


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def load_policy(path: Path | None = None) -> dict[str, Any]:
    policy_path = path or DEFAULT_POLICY_PATH
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RoutingError("workflow model routing policy is unreadable") from exc
    validate_policy(policy)
    return policy


def validate_policy(policy: Any) -> None:
    if not isinstance(policy, dict) or policy.get("schemaVersion") != "jimuyun.workflow-model-routing-policy.v1":
        raise RoutingError("workflow model routing policy schema is invalid")
    if policy.get("rolloutMode") not in {"observe_only", "active", "disabled"}:
        raise RoutingError("workflow model routing rollout mode is invalid")
    consumer_controls = policy.get("consumerControls")
    if not isinstance(consumer_controls, dict) or set(consumer_controls) != {
        "vdd", "quick_dev", "refactor_acceptance"
    } or any(value not in {"enabled", "disabled"} for value in consumer_controls.values()):
        raise RoutingError("workflow model routing consumer controls are invalid")
    if policy.get("backend") != "codex-cli" or policy.get("sandbox") not in {"read-only", "workspace-write"}:
        raise RoutingError("workflow model routing execution boundary is invalid")
    efforts = policy.get("supportedEfforts")
    if efforts != ["medium", "high", "max"]:
        raise RoutingError("workflow model routing effort vocabulary is invalid")
    evidence_policy = policy.get("capabilityEvidencePolicy")
    if not isinstance(evidence_policy, dict) or set(evidence_policy) != {
        "producerId", "allowedEvidenceRoot", "probeReceiptSchemaVersion",
        "shadowReceiptSchemaVersion",
    } or evidence_policy != {
        "producerId": "workflow-model-capability-evidence-producer.v1",
        "allowedEvidenceRoot": "logs/workflow-model-routing/capability-evidence",
        "probeReceiptSchemaVersion": "jimuyun.workflow-model-capability-probe-receipt.v1",
        "shadowReceiptSchemaVersion": "jimuyun.workflow-model-shadow-execution-receipt.v1",
    }:
        raise RoutingError("workflow model routing capability evidence policy is invalid")
    models = policy.get("models")
    routes = policy.get("routes")
    if not isinstance(models, dict) or not isinstance(routes, dict) or not routes:
        raise RoutingError("workflow model routing registry is incomplete")
    model_ids: set[str] = set()
    for alias, model in models.items():
        if not isinstance(model, dict) or not isinstance(model.get("modelId"), str):
            raise RoutingError(f"model registry entry is invalid: {alias}")
        model_id = model["modelId"]
        if not model_id.startswith("gpt-") or model_id in models or model_id in model_ids:
            raise RoutingError(f"model registry must use unique full model IDs: {alias}")
        model_ids.add(model_id)
        if model.get("activationState") not in {"active", "shadow_candidate"}:
            raise RoutingError(f"model activation state is invalid: {alias}")
    for route_id, route in routes.items():
        if not isinstance(route, dict) or route.get("launchMode") not in {"child", "none", "external_profile"}:
            raise RoutingError(f"route is invalid: {route_id}")
        route_owner = route_id.split(".", 1)[0]
        if route.get("consumer") != route_owner:
            raise RoutingError(f"route ownership is invalid: {route_id}")
        if route["launchMode"] != "child":
            if "model" in route or "effort" in route:
                raise RoutingError(f"non-child route cannot select a model: {route_id}")
            continue
        alias = route.get("model")
        effort = route.get("effort")
        if alias not in models or effort not in efforts:
            raise RoutingError(f"route model or effort is invalid: {route_id}")
        if models[alias]["activationState"] != "active":
            raise RoutingError(f"shadow model cannot be an active route: {route_id}")
        if effort == "max" and not route.get("requiresCapabilityProbe"):
            raise RoutingError(f"max route requires a capability probe: {route_id}")
        if route.get("requiresCapabilityProbe"):
            evidence = route.get("capabilityEvidence")
            if not isinstance(evidence, dict) or set(evidence) != {"probeReceipt", "shadowReceipt"}:
                raise RoutingError(f"capability route evidence binding is invalid: {route_id}")
            for reference in evidence.values():
                if reference is not None and (
                    not isinstance(reference, dict)
                    or set(reference) != {"path", "sha256"}
                    or not isinstance(reference["path"], str)
                    or not isinstance(reference["sha256"], str)
                    or not reference["sha256"].startswith("sha256:")
                ):
                    raise RoutingError(f"capability route evidence reference is invalid: {route_id}")
        shadow = route.get("shadowCandidate")
        if shadow is not None:
            if not isinstance(shadow, dict) or shadow.get("model") not in models:
                raise RoutingError(f"shadow candidate is invalid: {route_id}")
            if models[shadow["model"]]["activationState"] != "shadow_candidate":
                raise RoutingError(f"shadow candidate must use a shadow-only model: {route_id}")
    expected_routes = {
        "vdd.standard", "vdd.resumable", "vdd.self_hosted", "vdd.complex_recovery",
        "quick_dev.small_mechanical", "quick_dev.normal", "quick_dev.complex", "quick_dev.architectural",
        "refactor_acceptance.deterministic", "refactor_acceptance.complex_recovery",
        "bootstrap_review.external_profile",
    }
    if set(routes) != expected_routes:
        raise RoutingError("workflow model routing route coverage is incomplete")
    classification = policy.get("quickDevClassification")
    if not isinstance(classification, dict) or classification.get("precedence") != list(QUICK_DEV_CLASSES):
        raise RoutingError("Quick Dev classification precedence is invalid")
    if classification.get("overridePolicy") != "upgrade_only":
        raise RoutingError("Quick Dev override policy is invalid")
    vdd_recovery = policy.get("vddComplexRecoveryTriggers")
    if not isinstance(vdd_recovery, list) or not vdd_recovery or any(
        not isinstance(item, str) or not item for item in vdd_recovery
    ) or len(vdd_recovery) != len(set(vdd_recovery)):
        raise RoutingError("VDD complex recovery triggers are invalid")
    acceptance_recovery = policy.get("refactorAcceptanceComplexRecoveryTriggers")
    if not isinstance(acceptance_recovery, list) or not acceptance_recovery or any(
        not isinstance(item, str) or not item for item in acceptance_recovery
    ) or len(acceptance_recovery) != len(set(acceptance_recovery)):
        raise RoutingError("Refactor Acceptance complex recovery triggers are invalid")
    if policy.get("authorizes") != []:
        raise RoutingError("workflow model routing policy cannot authorize lifecycle state")


def _file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_capability_reference(
    reference: Any, *, policy: dict[str, Any], repository_root: Path, label: str
) -> tuple[dict[str, Any], dict[str, str]]:
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise RoutingError(f"policy-bound {label} is unavailable")
    allowed_root = (repository_root / policy["capabilityEvidencePolicy"]["allowedEvidenceRoot"]).resolve()
    path = (repository_root / reference["path"]).resolve()
    try:
        path.relative_to(allowed_root)
    except ValueError as exc:
        raise RoutingError(f"policy-bound {label} is outside the capability evidence root") from exc
    if not path.is_file() or _file_hash(path) != reference["sha256"]:
        raise RoutingError(f"policy-bound {label} is missing or stale")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RoutingError(f"policy-bound {label} is unreadable") from exc
    return value, dict(reference)


def _validate_execution_evidence(
    value: Any, *, route_id: str, policy: dict[str, Any], route: dict[str, Any]
) -> None:
    requested = {
        "launchMode": "child",
        "backend": policy["backend"],
        "model": policy["models"][route["model"]]["modelId"],
        "effort": route["effort"],
        "sandbox": policy["sandbox"],
    }
    if not isinstance(value, dict) or value.get("status") != "completed" or value.get("authorizes") != []:
        raise RoutingError(f"policy-bound capability execution did not complete: {route_id}")
    if value.get("requestedExecution") != requested:
        raise RoutingError(f"policy-bound capability execution requested identity drifted: {route_id}")
    actual = value.get("actualExecution")
    if not isinstance(actual, dict) or any(
        actual.get(key) != expected for key, expected in {
            "backend": requested["backend"], "model": requested["model"],
            "effort": requested["effort"], "sandbox": requested["sandbox"],
        }.items()
    ) or actual.get("exitCode") != 0 or actual.get("launched") is not True:
        raise RoutingError(f"policy-bound capability execution actual identity drifted: {route_id}")


def build_capability_proof(
    *, route_id: str, policy: dict[str, Any] | None = None,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    current = policy or load_policy()
    validate_policy(current)
    route = current["routes"].get(route_id)
    if not isinstance(route, dict) or not route.get("requiresCapabilityProbe"):
        raise RoutingError("workflow route does not require capability evidence")
    root = (repository_root or REPOSITORY_ROOT).resolve()
    evidence = route["capabilityEvidence"]
    probe, probe_ref = _load_capability_reference(
        evidence.get("probeReceipt"), policy=current, repository_root=root,
        label="capability probe receipt",
    )
    shadow, shadow_ref = _load_capability_reference(
        evidence.get("shadowReceipt"), policy=current, repository_root=root,
        label="representative shadow receipt",
    )
    evidence_policy = current["capabilityEvidencePolicy"]
    common = {
        "producerId": evidence_policy["producerId"],
        "routeId": route_id,
        "policyRevision": current["policyRevision"],
        "authorizes": [],
    }
    if set(probe) != {
        "schemaVersion", "receiptId", "producerId", "routeId", "policyRevision",
        "status", "processResultRef", "observedAt", "authorizes",
    } or probe.get("schemaVersion") != evidence_policy["probeReceiptSchemaVersion"] or any(
        probe.get(key) != value for key, value in common.items()
    ) or probe.get("status") != "passed" or not isinstance(probe.get("receiptId"), str):
        raise RoutingError("policy-bound capability probe producer binding is invalid")
    process, _ = _load_capability_reference(
        probe.get("processResultRef"), policy=current, repository_root=root,
        label="capability probe process result",
    )
    _validate_execution_evidence(process, route_id=route_id, policy=current, route=route)
    if set(shadow) != {
        "schemaVersion", "receiptId", "producerId", "routeId", "policyRevision",
        "cohortId", "predicateStatus", "representativeExecutionRefs", "observedAt",
        "authorizes",
    } or shadow.get("schemaVersion") != evidence_policy["shadowReceiptSchemaVersion"] or any(
        shadow.get(key) != value for key, value in common.items()
    ) or shadow.get("predicateStatus") != "passed" or not isinstance(shadow.get("cohortId"), str):
        raise RoutingError("policy-bound representative shadow producer binding is invalid")
    execution_refs = shadow.get("representativeExecutionRefs")
    if (
        not isinstance(execution_refs, list) or not execution_refs
        or len({canonical_hash(reference) for reference in execution_refs}) != len(execution_refs)
    ):
        raise RoutingError("policy-bound representative shadow execution evidence is missing")
    for index, reference in enumerate(execution_refs):
        execution, _ = _load_capability_reference(
            reference, policy=current, repository_root=root,
            label=f"representative shadow execution {index}",
        )
        _validate_execution_evidence(execution, route_id=route_id, policy=current, route=route)
    proof = {
        "schemaVersion": "jimuyun.workflow-model-capability-proof.v2",
        "routeId": route_id,
        "producerBindingHash": canonical_hash(evidence_policy),
        "probeReceiptRef": probe_ref,
        "shadowReceiptRef": shadow_ref,
        "representativeExecutionCount": len(execution_refs),
        "status": "passed",
        "shadowPredicateStatus": "passed",
        "authorizes": [],
    }
    proof["proofId"] = canonical_hash(proof)
    return proof


def _capability_projection(
    policy: dict[str, Any], route_id: str
) -> tuple[dict[str, Any], list[str]]:
    route = policy["routes"][route_id]
    if not route.get("requiresCapabilityProbe"):
        return {
            "required": False, "state": "not_required", "proofHash": None,
            "shadowPredicateState": "not_required",
        }, []
    evidence = route["capabilityEvidence"]
    if evidence.get("probeReceipt") is None or evidence.get("shadowReceipt") is None:
        return {
            "required": True, "state": "missing", "proofHash": None,
            "shadowPredicateState": "missing" if route.get("requiresShadowPredicate") else "not_required",
        }, []
    try:
        proof = build_capability_proof(route_id=route_id, policy=policy)
    except RoutingError:
        return {
            "required": True, "state": "failed", "proofHash": None,
            "shadowPredicateState": "failed" if route.get("requiresShadowPredicate") else "not_required",
        }, ["route_capability_evidence_invalid"]
    return {
        "required": True, "state": "passed", "proofHash": canonical_hash(proof),
        "shadowPredicateState": proof["shadowPredicateStatus"],
    }, []


def _validate_quick_dev_facts(facts: Any) -> dict[str, Any]:
    if not isinstance(facts, dict) or set(facts) != REQUIRED_QUICK_DEV_FACTS:
        raise RoutingError("Quick Dev facts must use the closed typed fact vocabulary")
    for name in (*ARCHITECTURAL_FACTS, *COMPLEX_FACTS, "deterministic_transform", "behavior_fully_specified", "introduces_contract", "introduces_dependency"):
        if not isinstance(facts[name], bool):
            raise RoutingError(f"Quick Dev fact must be boolean: {name}")
    for name in ("production_write_roots", "matching_test_roots"):
        if not isinstance(facts[name], int) or isinstance(facts[name], bool) or facts[name] < 0:
            raise RoutingError(f"Quick Dev fact must be a non-negative integer: {name}")
    for name in ("unknown_facts", "contradictory_facts"):
        if not isinstance(facts[name], list) or any(not isinstance(item, str) or not item for item in facts[name]):
            raise RoutingError(f"Quick Dev fact list is invalid: {name}")
    return dict(facts)


def classify_quick_dev(facts: Any, *, requested_class: str | None = None) -> dict[str, Any]:
    typed = _validate_quick_dev_facts(facts)
    triggers: list[str] = []
    architectural = [name for name in ARCHITECTURAL_FACTS if typed[name]]
    complex_triggers = [name for name in COMPLEX_FACTS if typed[name]]
    if typed["production_write_roots"] > 1:
        complex_triggers.append("multiple_production_write_roots")
    blocking: list[str] = []
    if typed["unknown_facts"]:
        blocking.append("unknown_typed_facts")
    if typed["contradictory_facts"]:
        blocking.append("contradictory_typed_facts")
    if architectural:
        selected = "architectural"
        triggers.extend(architectural)
    elif complex_triggers or blocking:
        selected = "complex"
        triggers.extend(complex_triggers)
        triggers.extend(blocking)
    else:
        mechanical = (
            typed["deterministic_transform"]
            and typed["behavior_fully_specified"]
            and typed["production_write_roots"] <= 1
            and typed["matching_test_roots"] <= 1
            and not typed["introduces_contract"]
            and not typed["introduces_dependency"]
        )
        selected = "small_mechanical" if mechanical else "normal"
        triggers.append("mechanical_contract_satisfied" if mechanical else "bounded_default")
    override = {"requestedClass": requested_class, "disposition": "none", "reasonCode": None}
    if requested_class is not None:
        if requested_class not in QUICK_DEV_CLASSES:
            override.update(disposition="rejected_invalid", reasonCode="unknown_override_class")
            blocking.append("invalid_class_override")
        elif QUICK_DEV_CLASSES.index(requested_class) < QUICK_DEV_CLASSES.index(selected):
            override.update(disposition="rejected_downgrade", reasonCode="downgrade_cannot_clear_highest_match")
            blocking.append("unsafe_class_downgrade")
        elif QUICK_DEV_CLASSES.index(requested_class) > QUICK_DEV_CLASSES.index(selected):
            selected = requested_class
            triggers.append("user_forced_upgrade")
            override.update(disposition="accepted_upgrade", reasonCode="explicit_upgrade")
    return {
        "classification": selected,
        "typedInputs": typed,
        "triggers": sorted(set(triggers)),
        "blockingReasons": sorted(set(blocking)),
        "override": override,
    }


def _route_decision(
    policy: dict[str, Any],
    *,
    consumer: str,
    route_id: str,
    classification: str | None,
    typed_inputs: dict[str, Any],
    triggers: list[str],
    blocking_reasons: list[str],
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_policy(policy)
    route = policy["routes"].get(route_id)
    if not isinstance(route, dict) or route.get("consumer") != consumer:
        raise RoutingError("workflow route does not belong to the requested consumer")
    launch_mode = route["launchMode"]
    model = policy["models"].get(route.get("model"), {}).get("modelId") if launch_mode == "child" else None
    effort = route.get("effort") if launch_mode == "child" else None
    capability, capability_blocking = _capability_projection(policy, route_id)
    route_blocking = [*blocking_reasons, *capability_blocking]
    if route.get("activationState") == "disabled_pending_evidence" and (
        capability["state"] != "passed"
        or capability["shadowPredicateState"] not in {"passed", "not_required"}
    ):
        route_blocking.append("route_disabled_pending_capability_and_shadow_evidence")
    rollout = policy["rolloutMode"]
    consumer_state = "external" if consumer == "bootstrap_review" else policy["consumerControls"][consumer]
    if launch_mode == "external_profile":
        status = "external"
    elif consumer_state == "disabled":
        status = "disabled"
    elif route_blocking:
        status = "blocked"
    elif rollout == "disabled" or launch_mode == "none":
        status = "disabled"
    elif rollout == "observe_only":
        status = "observe_only"
    else:
        status = "ready"
    decision = {
        "schemaVersion": DECISION_SCHEMA_VERSION,
        "consumer": consumer,
        "consumerState": consumer_state,
        "routeId": route_id,
        "classification": classification,
        "typedInputs": typed_inputs,
        "triggers": sorted(set(triggers)),
        "blockingReasons": sorted(set(route_blocking)),
        "policyRevision": policy["policyRevision"],
        "policyHash": canonical_hash(policy),
        "rolloutMode": rollout,
        "requestedExecution": {
            "launchMode": launch_mode,
            "backend": policy["backend"] if launch_mode == "child" else None,
            "model": model,
            "effort": effort,
            "sandbox": policy["sandbox"] if launch_mode == "child" else None,
        },
        "actualExecution": None,
        "override": override or {"requestedClass": None, "disposition": "none", "reasonCode": None},
        "capability": capability,
        "status": status,
        "authorizes": [],
    }
    decision["decisionId"] = canonical_hash(decision)
    validate_decision(decision, policy)
    return decision


def quick_dev_decision(
    facts: Any, *, requested_class: str | None = None, policy: dict[str, Any] | None = None
) -> dict[str, Any]:
    current = policy or load_policy()
    classification = classify_quick_dev(facts, requested_class=requested_class)
    return _route_decision(
        current,
        consumer="quick_dev",
        route_id=f"quick_dev.{classification['classification']}",
        classification=classification["classification"],
        typed_inputs=classification["typedInputs"],
        triggers=classification["triggers"],
        blocking_reasons=classification["blockingReasons"],
        override=classification["override"],
    )


def vdd_decision(
    profile: str,
    *,
    complex_recovery: bool = False,
    recovery_trigger: str | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current = policy or load_policy()
    if profile not in {"standard", "resumable", "self-hosted"}:
        raise RoutingError("VDD profile is invalid")
    if complex_recovery and not recovery_trigger:
        raise RoutingError("VDD complex recovery requires a typed trigger")
    allowed_recovery = current.get("vddComplexRecoveryTriggers", [])
    if recovery_trigger is not None and recovery_trigger not in allowed_recovery:
        raise RoutingError("VDD complex recovery trigger is invalid")
    route_id = "vdd.complex_recovery" if complex_recovery else f"vdd.{profile.replace('-', '_')}"
    triggers = ["existing_vdd_profile"]
    typed_inputs = {"profile": profile, "complexRecovery": complex_recovery, "recoveryTrigger": recovery_trigger}
    if complex_recovery:
        triggers.append(str(recovery_trigger))
    return _route_decision(
        current,
        consumer="vdd",
        route_id=route_id,
        classification=profile,
        typed_inputs=typed_inputs,
        triggers=triggers,
        blocking_reasons=[],
    )


def refactor_acceptance_decision(
    *,
    complex_recovery_trigger: str | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current = policy or load_policy()
    allowed = current.get("refactorAcceptanceComplexRecoveryTriggers", [])
    if complex_recovery_trigger is not None and complex_recovery_trigger not in allowed:
        raise RoutingError("Refactor Acceptance complex recovery trigger is invalid")
    route_id = (
        "refactor_acceptance.complex_recovery"
        if complex_recovery_trigger is not None
        else "refactor_acceptance.deterministic"
    )
    return _route_decision(
        current,
        consumer="refactor_acceptance",
        route_id=route_id,
        classification="complex_recovery" if complex_recovery_trigger else "deterministic",
        typed_inputs={"complexRecoveryTrigger": complex_recovery_trigger},
        triggers=[complex_recovery_trigger] if complex_recovery_trigger else ["deterministic_next_action"],
        blocking_reasons=[],
    )


def bootstrap_external_decision(
    *, override_model: str | None = None, policy: dict[str, Any] | None = None
) -> dict[str, Any]:
    current = policy or load_policy()
    blocking = ["bootstrap_profile_override_forbidden"] if override_model else []
    return _route_decision(
        current,
        consumer="bootstrap_review",
        route_id="bootstrap_review.external_profile",
        classification="external_profile",
        typed_inputs={"overrideModel": override_model},
        triggers=["bootstrap_owned_profile"],
        blocking_reasons=blocking,
    )


def execute_decision(
    decision: dict[str, Any],
    *,
    root: Path,
    prompt: str,
    output_last_message: Path,
    timeout_sec: int,
    policy: dict[str, Any] | None = None,
    runner: Any = None,
) -> dict[str, Any]:
    current = load_policy()
    if policy is not None and canonical_hash(policy) != canonical_hash(current):
        raise RoutingError("workflow model execution requires the canonical policy")
    validate_decision(decision, current)
    requested = decision["requestedExecution"]
    result = {
        "schemaVersion": "jimuyun.workflow-model-execution-result.v1",
        "decisionId": decision["decisionId"],
        "policyRevision": decision["policyRevision"],
        "policyHash": decision["policyHash"],
        "requestedExecution": requested,
        "actualExecution": None,
        "status": "blocked",
        "authorizes": [],
    }
    if decision["status"] == "observe_only":
        result["status"] = "observed"
        return result
    if decision["status"] in {"blocked", "disabled", "external"}:
        return result
    if decision["status"] != "ready" or current["rolloutMode"] != "active":
        raise RoutingError("workflow model route is not launch-authorized")
    if requested["launchMode"] != "child" or not requested["model"] or not requested["effort"]:
        raise RoutingError("workflow model route has no executable child identity")
    capability = decision["capability"]
    if capability["required"] and (
        capability["state"] != "passed" or capability["shadowPredicateState"] not in {"passed", "not_required"}
    ):
        raise RoutingError("workflow model route capability evidence is incomplete")
    executor = runner or llm_backend.run_llm_exec
    rc, output, command = executor(
        backend=requested["backend"],
        root=root,
        prompt=prompt,
        output_last_message=output_last_message,
        timeout_sec=timeout_sec,
        codex_configs=[f'model_reasoning_effort="{requested["effort"]}"'],
        codex_model=requested["model"],
        codex_sandbox=requested["sandbox"],
    )
    command_values = [str(item) for item in command]
    model_bound = requested["model"] in command_values
    effort_bound = f'model_reasoning_effort="{requested["effort"]}"' in command_values
    actual = {
        "launched": True,
        "backend": requested["backend"],
        "model": requested["model"] if model_bound else None,
        "effort": requested["effort"] if effort_bound else None,
        "sandbox": requested["sandbox"],
        "exitCode": int(rc),
        "commandHash": canonical_hash(command_values),
        "outputHash": "sha256:" + hashlib.sha256(str(output).encode("utf-8")).hexdigest(),
    }
    result["actualExecution"] = actual
    result["status"] = "completed" if rc == 0 and model_bound and effort_bound else "failed"
    return result


def write_execution_evidence(result: dict[str, Any], path: Path) -> None:
    if result.get("authorizes") != [] or "prompt" in result:
        raise RoutingError("workflow model execution evidence is unsafe")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def validate_decision(decision: Any, policy: dict[str, Any] | None = None) -> None:
    if not isinstance(decision, dict) or decision.get("schemaVersion") != DECISION_SCHEMA_VERSION:
        raise RoutingError("workflow model route decision schema is invalid")
    required = {
        "schemaVersion", "decisionId", "consumer", "consumerState", "routeId", "classification", "typedInputs", "triggers",
        "blockingReasons", "policyRevision", "policyHash", "rolloutMode", "requestedExecution",
        "actualExecution", "override", "capability", "status", "authorizes",
    }
    if set(decision) != required or decision.get("authorizes") != []:
        raise RoutingError("workflow model route decision shape is invalid")
    current = policy or load_policy()
    if decision.get("policyRevision") != current["policyRevision"] or decision.get("policyHash") != canonical_hash(current):
        raise RoutingError("workflow model route decision policy binding is stale")
    unsigned = {key: value for key, value in decision.items() if key != "decisionId"}
    if decision.get("decisionId") != canonical_hash(unsigned):
        raise RoutingError("workflow model route decision hash is invalid")
    expected_consumer_state = (
        "external" if decision.get("consumer") == "bootstrap_review"
        else current["consumerControls"].get(decision.get("consumer"))
    )
    if decision.get("consumerState") != expected_consumer_state:
        raise RoutingError("workflow model route decision consumer control is stale")
    expected_capability, _ = _capability_projection(current, decision.get("routeId"))
    if decision.get("capability") != expected_capability:
        raise RoutingError("workflow model route decision capability binding is stale")
    requested = decision.get("requestedExecution")
    if not isinstance(requested, dict) or set(requested) != {"launchMode", "backend", "model", "effort", "sandbox"}:
        raise RoutingError("workflow model requested execution identity is invalid")
    if requested["model"] is not None and not str(requested["model"]).startswith("gpt-"):
        raise RoutingError("workflow model route decision must use a full model ID")

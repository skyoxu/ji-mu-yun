from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
_OBSERVATION_SPEC = importlib.util.spec_from_file_location("rmap_stage_observation", Path(__file__).with_name("stage_observation.py"))
if _OBSERVATION_SPEC is None or _OBSERVATION_SPEC.loader is None:
    raise RuntimeError("stage observation support is unavailable")
_OBSERVATIONS = importlib.util.module_from_spec(_OBSERVATION_SPEC)
_OBSERVATION_SPEC.loader.exec_module(_OBSERVATIONS)

from protocol_guards import STAGES, STAGE_GOALS, STAGE_STATES, bytes_hash, canonical_bytes, classify_scope, safe_relative, value_hash


def _ref(role: str, path_type: str, path: str, payload: bytes) -> dict[str, str]:
    return {"role": role, "path_type": path_type, "path": path, "sha256": bytes_hash(payload)}


def _plain_ref(path_type: str, path: str, payload: bytes) -> dict[str, str]:
    return {"path_type": path_type, "path": path, "sha256": bytes_hash(payload)}


def _put(store: dict[tuple[str, str], bytes], key: tuple[str, str], payload: bytes) -> None:
    existing = store.get(key)
    if existing is not None and existing != payload:
        raise ValueError(f"immutable artifact conflicts at {key[0]}:{key[1]}")
    store[key] = payload


def _context_ref(value: Any, store: dict[tuple[str, str], bytes]) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"role", "path_type", "path", "payload"}:
        raise ValueError("context artifact must declare role, typed path, and explicit bytes")
    role, path_type, path, payload = value["role"], value["path_type"], value["path"], value["payload"]
    if not isinstance(role, str) or path_type not in {"repo_path", "plan_path", "run_path"} or not safe_relative(path) or not isinstance(payload, bytes):
        raise ValueError("context artifact is invalid")
    _put(store, (path_type, path), payload)
    return _ref(role, path_type, path, payload)


def compose(
    run_context: dict[str, Any],
    observations: list[dict[str, Any]],
    artifact_store: dict[tuple[str, str], bytes],
) -> tuple[dict[str, Any], dict[tuple[str, str], bytes], dict[tuple[str, str, str], bytes | None]]:
    """Close one observed RED/GREEN/REFACTOR lifecycle without reading the worktree.

    ``run_context`` owns all authority bytes and stage-result document cores.  Snapshot
    bytes originate exclusively from ``observations`` and all returned stores are copies.
    """
    required = {
        "plan_id", "slice_id", "run_id", "authority_refs", "implementation_contract",
        "requirement_ids", "acceptance_ids", "source_refs", "boundaries",
        "target_command_ids", "stage_results",
    }
    if not isinstance(run_context, dict) or set(run_context) != required:
        raise ValueError("run context shape is invalid")
    if not isinstance(artifact_store, dict) or any(
        not isinstance(key, tuple) or len(key) != 2 or not all(isinstance(part, str) for part in key) or not isinstance(value, bytes)
        for key, value in artifact_store.items()
    ):
        raise ValueError("artifact store is invalid")
    plan_id, slice_id, run_id = (run_context[key] for key in ("plan_id", "slice_id", "run_id"))
    if not all(isinstance(value, str) and value for value in (plan_id, slice_id, run_id)):
        raise ValueError("run identity is invalid")
    parsed = _OBSERVATIONS.parse_sequence(observations)
    store = dict(artifact_store)
    authority_refs = [_context_ref(item, store) for item in run_context["authority_refs"]]
    contract_ref = _context_ref(run_context["implementation_contract"], store)
    if not authority_refs or contract_ref["role"] != "implementation-contract":
        raise ValueError("authority or implementation contract is invalid")
    boundaries = run_context["boundaries"]
    command_ids = run_context["target_command_ids"]
    if not isinstance(boundaries, dict) or not isinstance(command_ids, list) or not command_ids or any(not isinstance(item, str) or not item for item in command_ids):
        raise ValueError("run boundaries or command ids are invalid")
    if any(not isinstance(run_context[key], list) or any(not isinstance(item, str) or not item for item in run_context[key]) for key in ("requirement_ids", "acceptance_ids", "source_refs")):
        raise ValueError("run context identifiers are invalid")
    stage_cores = run_context["stage_results"]
    if not isinstance(stage_cores, dict) or set(stage_cores) != set(STAGES) or any(not isinstance(value, dict) for value in stage_cores.values()):
        raise ValueError("stage result cores are invalid")

    # Baseline is the first observed state, including an explicitly absent file.
    baseline_state: dict[str, bytes | None] = {}
    for observation in parsed:
        for change in observation["changed_files"]:
            if change["path"] not in baseline_state:
                baseline_state[change["path"]] = change["before_bytes"]
    baseline_bytes = {
        path: payload
        for path, payload in baseline_state.items()
        if payload is not None
    }
    baseline_files = []
    for path, payload in sorted(baseline_bytes.items()):
        snapshot_path = f"baseline/files/{path}"
        _put(store, ("run_path", snapshot_path), payload)
        baseline_files.append({"path": path, "sha256": bytes_hash(payload), "snapshot_ref": _plain_ref("run_path", snapshot_path, payload)})
    baseline_core = {"schema_version": "jimuyun.baseline-file-manifest.v1", "plan_id": plan_id, "slice_id": slice_id, "run_id": run_id, "files": baseline_files}
    baseline = {**baseline_core, "root_hash": value_hash(baseline_core)}
    baseline_payload = canonical_bytes(baseline)
    _put(store, ("run_path", "baseline-file-manifest.v1.json"), baseline_payload)

    contexts: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    versions: dict[tuple[str, str, str], bytes | None] = {}
    previous_capsule_hash: str | None = None
    previous_attempt: str | None = None
    previous_decision_hash: str | None = None
    previous_stage_refs: list[dict[str, str]] = []
    current: dict[str, bytes | None] = dict(baseline_state)
    event_specs = (("attempt-started", "backend-request.v1.json"), ("request-recorded", "backend-request.v1.json"), ("response-recorded", "backend-response.v1.json"), ("diff-recorded", "diff-manifest.v1.json"), ("decision-finalized", "adapter-decision.v1.json"))
    events: list[dict[str, Any]] = []
    previous_event_hash: str | None = None

    for index, observation in enumerate(parsed, start=1):
        stage, capsule_id, attempt_id = observation["stage"], f"CAP-{index:03d}", f"ATTEMPT-{index:03d}"
        capsule = {
            "schema_version": "jimuyun.slice-capsule.v1", "plan_id": plan_id, "slice_id": slice_id, "run_id": run_id,
            "capsule_id": capsule_id, "stage": stage, "authority_refs": authority_refs, "implementation_contract": contract_ref,
            "requirement_ids": list(run_context["requirement_ids"]), "acceptance_ids": list(run_context["acceptance_ids"]), "source_refs": list(run_context["source_refs"]),
            "baseline_ref": _ref("baseline", "run_path", "baseline-file-manifest.v1.json", baseline_payload), "stage_evidence_refs": copy.deepcopy(previous_stage_refs),
            "boundaries": copy.deepcopy(boundaries), "target_command_ids": list(command_ids), "exit_predicate": "slice-ready", "latest_blocker_ref": None,
            "predecessor_capsule_hash": previous_capsule_hash, "immutable": True, "authorizes": [],
            "does_not_authorize": ["bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"],
        }
        capsule_path = f"context/{capsule_id}/slice-capsule.v1.json"
        capsule_payload = canonical_bytes(capsule)
        _put(store, ("run_path", capsule_path), capsule_payload)
        capsule_ref = _ref("slice-capsule", "run_path", capsule_path, capsule_payload)
        artifact_refs = [*authority_refs, contract_ref, capsule["baseline_ref"], *previous_stage_refs]
        context = {
            "schema_version": "jimuyun.context-manifest.v1", "plan_id": plan_id, "slice_id": slice_id, "run_id": run_id,
            "capsule_id": capsule_id, "stage": stage, "capsule_ref": capsule_ref, "artifact_refs": artifact_refs,
            "context_hash": value_hash({"capsule_hash": capsule_ref["sha256"], "artifact_refs": artifact_refs}), "predecessor_capsule_hash": previous_capsule_hash,
            "immutable": True, "contains_sensitive_data": False,
        }
        _put(store, ("run_path", f"context/{capsule_id}/context-manifest.v1.json"), canonical_bytes(context))
        contexts.append({"context_manifest": context, "slice_capsule": capsule})
        request = _OBSERVATIONS.backend_request(plan_id, slice_id, run_id, attempt_id, stage, capsule_ref["sha256"], list(command_ids), previous_attempt)
        response = _OBSERVATIONS.backend_response(observation, plan_id, slice_id, run_id, attempt_id)
        entries = []
        for change in _OBSERVATIONS.canonical_diff(observation):
            path, before, after = change["path"], None, None
            observed = next(item for item in observation["changed_files"] if item["path"] == path)
            before, after = observed["before_bytes"], observed["after_bytes"]
            if path in current and current[path] != before:
                raise ValueError(f"observation before-image is not continuous for {path}")
            versions[(attempt_id, "before", path)] = before
            versions[(attempt_id, "after", path)] = after
            snapshot_ref = None
            if after is not None:
                snapshot_path = f"attempts/{attempt_id}/result-files/{path}"
                _put(store, ("run_path", snapshot_path), after)
                snapshot_ref = _plain_ref("run_path", snapshot_path, after)
            entries.append({**change, "result_snapshot_ref": snapshot_ref, "scope": classify_scope(path, boundaries)})
            current[path] = after
        diff = {
            "schema_version": "jimuyun.diff-manifest.v1", "plan_id": plan_id, "slice_id": slice_id, "run_id": run_id, "attempt_id": attempt_id, "stage": stage,
            "baseline_worktree_hash": value_hash({entry["path"]: entry["before_sha256"] for entry in entries}), "result_worktree_hash": value_hash({entry["path"]: entry["after_sha256"] for entry in entries}),
            "files": entries, "actual_diff_hash": value_hash(entries), "generated_by": "adapter", "canonical": True, "contains_forbidden_change": any(entry["scope"] == "forbidden" for entry in entries),
        }
        decision = {
            "schema_version": "jimuyun.adapter-decision.v1", "plan_id": plan_id, "slice_id": slice_id, "run_id": run_id, "attempt_id": attempt_id, "stage": stage,
            "stage_binding_id": f"STAGE-{stage.upper()}", "stage_result_path": f"{stage}-result.json", "actor": {"role": "repository-maintenance-tdd-adapter", "adapter_protocol_version": "1.0"},
            "input_context_hash": context["context_hash"], "backend_request_hash": value_hash(request), "backend_response_hash": value_hash(response), "actual_diff_hash": diff["actual_diff_hash"],
            "decision": "accepted_for_validation", "failure_ids": [], "evidence_refs": [], "previous_attempt_id": previous_attempt, "previous_decision_hash": previous_decision_hash,
            "next_allowed_state": STAGE_STATES[stage], "authorizes": [], "does_not_authorize": ["bootstrap-review", "implementation-accepted", "release-ready"], "finalized": True, "written_last": True,
        }
        decision_hash = value_hash(decision)
        stage_result = copy.deepcopy(stage_cores[stage])
        if stage_result.get("stage") not in (None, stage) or any(key in stage_result for key in ("stage_binding_id", "attempt_id", "decision_hash", "capsule_hash", "context_hash")):
            raise ValueError("stage result core conflicts with protocol binding")
        stage_result.update({"stage": stage, "stage_binding_id": decision["stage_binding_id"], "attempt_id": attempt_id, "decision_hash": decision_hash, "capsule_hash": capsule_ref["sha256"], "context_hash": context["context_hash"]})
        stage_result.setdefault("predecessor_stage_hash", None if not previous_stage_refs else previous_stage_refs[-1]["sha256"])
        stage_payload = canonical_bytes(stage_result)
        _put(store, ("run_path", decision["stage_result_path"]), stage_payload)
        for name, document in (("backend-request.v1.json", request), ("backend-response.v1.json", response), ("diff-manifest.v1.json", diff), ("adapter-decision.v1.json", decision)):
            _put(store, ("run_path", f"attempts/{attempt_id}/{name}"), canonical_bytes(document))
        attempts.append({"backend_request": request, "backend_response": response, "diff_manifest": diff, "adapter_decision": decision})
        for event_type, name in event_specs:
            path = f"attempts/{attempt_id}/{name}"
            event = {"schema_version": "jimuyun.agent-attempt-event.v1", "plan_id": plan_id, "slice_id": slice_id, "run_id": run_id, "sequence": len(events) + 1, "attempt_id": attempt_id, "stage": stage, "event_type": event_type, "attempt_status": "accepted" if event_type == "decision-finalized" else "in_progress", "artifact_refs": [_plain_ref("run_path", path, store[("run_path", path)])], "previous_event_hash": previous_event_hash, "observed_at": observation["observed_at"], "append_only": True}
            events.append(event)
            previous_event_hash = value_hash(event)
        previous_stage_refs.append(_ref(f"{stage}-result", "run_path", decision["stage_result_path"], stage_payload))
        previous_capsule_hash, previous_attempt, previous_decision_hash = capsule_ref["sha256"], attempt_id, decision_hash

    event_payload = b"".join(canonical_bytes(event) + b"\n" for event in events)
    _put(store, ("run_path", "run-events.jsonl"), event_payload)
    ledger_core = {"schema_version": "jimuyun.attempt-ledger-manifest.v1", "plan_id": plan_id, "slice_id": slice_id, "run_id": run_id, "attempts": [{"attempt_id": item["backend_request"]["attempt_id"], "stage": item["backend_request"]["stage"], "request_hash": value_hash(item["backend_request"]), "response_hash": value_hash(item["backend_response"]), "diff_hash": value_hash(item["diff_manifest"]), "decision_hash": value_hash(item["adapter_decision"]), "stage_result_hash": bytes_hash(store[("run_path", item["adapter_decision"]["stage_result_path"])])} for item in attempts], "run_events_hash": bytes_hash(event_payload), "final_event_hash": value_hash(events[-1])}
    ledger = {**ledger_core, "root_hash": value_hash(ledger_core)}
    _put(store, ("run_path", "attempt-ledger-manifest.v1.json"), canonical_bytes(ledger))
    return {"schema_version": "rmap.capsule-attempt-bundle.v1", "contexts": contexts, "attempts": attempts, "events": events, "baseline_file_manifest": baseline, "attempt_ledger_manifest": ledger}, store, versions

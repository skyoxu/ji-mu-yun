from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from protocol_artifact_guards import bytes_hash, canonical_bytes, safe_relative, store_key, value_hash
from protocol_validation_guards import STAGES, STAGE_GOALS, STAGE_STATES, _finding, validate_protocol_bundle

def _typed_ref(role: str, path_type: str, path: str, payload: bytes) -> dict[str, str]:
    return {"role": role, "path_type": path_type, "path": path, "sha256": bytes_hash(payload)}


def _unroled_ref(path_type: str, path: str, payload: bytes) -> dict[str, str]:
    return {"path_type": path_type, "path": path, "sha256": bytes_hash(payload)}


def hydrate_protocol_fixture(
    base: dict[str, Any],
    stage_documents: dict[str, dict[str, Any]] | None = None,
    external_artifacts: dict[str, bytes] | None = None,
    initial_bytes: bytes | None = b"baseline\n",
) -> tuple[
    dict[str, Any], dict[tuple[str, str], bytes], dict[tuple[str, str, str], bytes | None]
]:
    template_capsule = copy.deepcopy(base["slice_capsule"])
    template_attempt = copy.deepcopy(base["attempts"][0])
    store: dict[tuple[str, str], bytes] = {}
    file_versions: dict[tuple[str, str, str], bytes | None] = {}
    plan_id = template_capsule["plan_id"]
    slice_id = template_capsule["slice_id"]
    run_id = template_capsule["run_id"]
    external_artifacts = external_artifacts or {}
    contract_bytes = external_artifacts.get("implementation-contract.v1.json", b'{"fixture":"implementation-contract"}')
    authority_bytes = external_artifacts.get("schemas/authority-manifest.v1.json", b'{"fixture":"authority-manifest"}')
    store[("plan_path", "implementation-contract.v1.json")] = contract_bytes
    store[("plan_path", "schemas/authority-manifest.v1.json")] = authority_bytes
    target_path = template_attempt["diff_manifest"]["files"][0]["path"]
    snapshot_path = "baseline/files/adapter.py"
    if initial_bytes is not None:
        store[("run_path", snapshot_path)] = initial_bytes
    baseline_core = {
        "schema_version": "jimuyun.baseline-file-manifest.v1",
        "plan_id": plan_id,
        "slice_id": slice_id,
        "run_id": run_id,
        "files": [] if initial_bytes is None else [{
            "path": target_path,
            "sha256": bytes_hash(initial_bytes),
            "snapshot_ref": _unroled_ref("run_path", snapshot_path, initial_bytes),
        }],
    }
    baseline = {**baseline_core, "root_hash": value_hash(baseline_core)}
    baseline_bytes = canonical_bytes(baseline)
    store[("run_path", "baseline-file-manifest.v1.json")] = baseline_bytes

    contexts: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    previous_capsule_hash: str | None = None
    previous_attempt: str | None = None
    previous_decision_hash: str | None = None
    previous_stage_results: list[dict[str, str]] = []
    previous_stage_result_bytes: bytes | None = None
    current_bytes = initial_bytes
    stage_results_pending: list[tuple[str, dict[str, Any]]] = []
    for index, stage in enumerate(STAGES, start=1):
        capsule_id = f"CAP-{index:03d}"
        capsule = copy.deepcopy(template_capsule)
        capsule.update({"capsule_id": capsule_id, "stage": stage, "predecessor_capsule_hash": previous_capsule_hash})
        capsule["authority_refs"] = [_typed_ref("authority-manifest", "plan_path", "schemas/authority-manifest.v1.json", authority_bytes)]
        capsule["implementation_contract"] = _typed_ref("implementation-contract", "plan_path", "implementation-contract.v1.json", contract_bytes)
        capsule["baseline_ref"] = _typed_ref("baseline", "run_path", "baseline-file-manifest.v1.json", baseline_bytes)
        capsule["stage_evidence_refs"] = copy.deepcopy(previous_stage_results)
        capsule["latest_blocker_ref"] = None
        capsule_path = f"context/{capsule_id}/slice-capsule.v1.json"
        capsule_bytes = canonical_bytes(capsule)
        store[("run_path", capsule_path)] = capsule_bytes
        capsule_ref = _typed_ref("slice-capsule", "run_path", capsule_path, capsule_bytes)
        artifact_refs = copy.deepcopy([
            *capsule["authority_refs"], capsule["implementation_contract"], capsule["baseline_ref"],
            *capsule["stage_evidence_refs"],
        ])
        context = copy.deepcopy(base["context_manifest"])
        context.update({
            "capsule_id": capsule_id,
            "stage": stage,
            "capsule_ref": capsule_ref,
            "artifact_refs": artifact_refs,
            "context_hash": value_hash({"capsule_hash": capsule_ref["sha256"], "artifact_refs": artifact_refs}),
            "predecessor_capsule_hash": previous_capsule_hash,
        })
        context_path = f"context/{capsule_id}/context-manifest.v1.json"
        store[("run_path", context_path)] = canonical_bytes(context)
        contexts.append({"context_manifest": context, "slice_capsule": capsule})

        attempt_id = f"ATTEMPT-{index:03d}"
        request = copy.deepcopy(template_attempt["backend_request"])
        request.update({
            "plan_id": plan_id,
            "slice_id": slice_id,
            "run_id": run_id,
            "attempt_id": attempt_id,
            "stage": stage,
            "stage_binding_id": f"STAGE-{stage.upper()}",
            "capsule_ref": _unroled_ref("run_path", capsule_path, capsule_bytes),
            "goal": STAGE_GOALS[stage],
            "previous_attempt_id": previous_attempt,
        })
        request["request_payload_hash"] = value_hash({
            "capsule_hash": request["capsule_ref"]["sha256"],
            "stage_binding_id": request["stage_binding_id"],
            "goal": request["goal"],
            "allowed_command_ids": request["allowed_command_ids"],
        })
        response = copy.deepcopy(template_attempt["backend_response"])
        response.update({"plan_id": plan_id, "slice_id": slice_id, "run_id": run_id, "attempt_id": attempt_id, "stage": stage, "changed_files": [target_path]})
        after_bytes = (current_bytes or b"") + f"{stage}\n".encode("ascii")
        result_snapshot_path = f"attempts/{attempt_id}/result-files/adapter.py"
        store[("run_path", result_snapshot_path)] = after_bytes
        file_versions[(attempt_id, "before", target_path)] = current_bytes
        file_versions[(attempt_id, "after", target_path)] = after_bytes
        entry = {
            "path": target_path,
            "change_type": "add" if current_bytes is None else "modify",
            "before_sha256": None if current_bytes is None else bytes_hash(current_bytes),
            "after_sha256": bytes_hash(after_bytes),
            "result_snapshot_ref": _unroled_ref("run_path", result_snapshot_path, after_bytes),
            "scope": "allowed",
        }
        diff = copy.deepcopy(template_attempt["diff_manifest"])
        diff.update({
            "plan_id": plan_id,
            "slice_id": slice_id,
            "run_id": run_id,
            "attempt_id": attempt_id,
            "stage": stage,
            "baseline_worktree_hash": value_hash({target_path: entry["before_sha256"]}),
            "result_worktree_hash": value_hash({target_path: entry["after_sha256"]}),
            "files": [entry],
            "actual_diff_hash": value_hash([entry]),
            "contains_forbidden_change": False,
        })
        decision = copy.deepcopy(template_attempt["adapter_decision"])
        decision.update({
            "plan_id": plan_id,
            "slice_id": slice_id,
            "run_id": run_id,
            "attempt_id": attempt_id,
            "stage": stage,
            "stage_binding_id": f"STAGE-{stage.upper()}",
            "stage_result_path": f"{stage}-result.json",
            "input_context_hash": context["context_hash"],
            "backend_request_hash": value_hash(request),
            "backend_response_hash": value_hash(response),
            "actual_diff_hash": diff["actual_diff_hash"],
            "evidence_refs": [],
            "previous_attempt_id": previous_attempt,
            "previous_decision_hash": previous_decision_hash,
            "next_allowed_state": STAGE_STATES[stage],
        })
        decision_hash = value_hash(decision)
        stage_result = copy.deepcopy((stage_documents or {}).get(stage, {
            "schema_version": "rmap.stage-result.v1",
        }))
        stage_result.update({
            "stage_binding_id": decision["stage_binding_id"],
            "attempt_id": attempt_id,
            "decision_hash": decision_hash,
            "capsule_hash": capsule_ref["sha256"],
            "context_hash": context["context_hash"],
        })
        if "predecessor_stage_hash" in stage_result:
            stage_result["predecessor_stage_hash"] = (
                None if previous_stage_result_bytes is None else bytes_hash(previous_stage_result_bytes)
            )
        stage_bytes = canonical_bytes(stage_result)
        store[("run_path", decision["stage_result_path"])] = stage_bytes
        previous_stage_results.append(_typed_ref(f"{stage}-result", "run_path", decision["stage_result_path"], stage_bytes))
        previous_stage_result_bytes = stage_bytes
        for name, document in (
            ("backend-request.v1.json", request), ("backend-response.v1.json", response),
            ("diff-manifest.v1.json", diff), ("adapter-decision.v1.json", decision),
        ):
            store[("run_path", f"attempts/{attempt_id}/{name}")] = canonical_bytes(document)
        attempts.append({
            "backend_request": request,
            "backend_response": response,
            "diff_manifest": diff,
            "adapter_decision": decision,
        })
        previous_capsule_hash = capsule_ref["sha256"]
        previous_attempt = attempt_id
        previous_decision_hash = decision_hash
        current_bytes = after_bytes

    events: list[dict[str, Any]] = []
    previous_event_hash: str | None = None
    sequence = 0
    event_specs = [
        ("attempt-started", "backend-request.v1.json"),
        ("request-recorded", "backend-request.v1.json"),
        ("response-recorded", "backend-response.v1.json"),
        ("diff-recorded", "diff-manifest.v1.json"),
        ("decision-finalized", "adapter-decision.v1.json"),
    ]
    for attempt in attempts:
        request = attempt["backend_request"]
        for event_type, artifact_name in event_specs:
            sequence += 1
            path = f"attempts/{request['attempt_id']}/{artifact_name}"
            event = {
                "schema_version": "jimuyun.agent-attempt-event.v1",
                "plan_id": plan_id,
                "slice_id": slice_id,
                "run_id": run_id,
                "sequence": sequence,
                "attempt_id": request["attempt_id"],
                "stage": request["stage"],
                "event_type": event_type,
                "attempt_status": "accepted" if event_type == "decision-finalized" else "in_progress",
                "artifact_refs": [_unroled_ref("run_path", path, store[("run_path", path)])],
                "previous_event_hash": previous_event_hash,
                "observed_at": f"2026-07-17T00:00:{sequence:02d}Z",
                "append_only": True,
            }
            events.append(event)
            previous_event_hash = value_hash(event)
    event_bytes = b"".join(canonical_bytes(event) + b"\n" for event in events)
    store[("run_path", "run-events.jsonl")] = event_bytes
    ledger_core = {
        "schema_version": "jimuyun.attempt-ledger-manifest.v1",
        "plan_id": plan_id,
        "slice_id": slice_id,
        "run_id": run_id,
        "attempts": [
            {
                "attempt_id": attempt["backend_request"]["attempt_id"],
                "stage": attempt["backend_request"]["stage"],
                "request_hash": value_hash(attempt["backend_request"]),
                "response_hash": value_hash(attempt["backend_response"]),
                "diff_hash": value_hash(attempt["diff_manifest"]),
                "decision_hash": value_hash(attempt["adapter_decision"]),
                "stage_result_hash": bytes_hash(store[("run_path", attempt["adapter_decision"]["stage_result_path"])]),
            }
            for attempt in attempts
        ],
        "run_events_hash": bytes_hash(event_bytes),
        "final_event_hash": value_hash(events[-1]),
    }
    ledger = {**ledger_core, "root_hash": value_hash(ledger_core)}
    store[("run_path", "attempt-ledger-manifest.v1.json")] = canonical_bytes(ledger)
    bundle = {
        "schema_version": "rmap.capsule-attempt-bundle.v1",
        "contexts": contexts,
        "attempts": attempts,
        "events": events,
        "baseline_file_manifest": baseline,
        "attempt_ledger_manifest": ledger,
    }
    return bundle, store, file_versions


def load_protocol_run(plan_root: Path, run_dir: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    contexts: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    store: dict[tuple[str, str], bytes] = {}
    file_versions: dict[tuple[str, str, str], bytes | None] = {}
    for directory in sorted((run_dir / "context").glob("CAP-*")):
        try:
            manifest_path = directory / "context-manifest.v1.json"
            capsule_path = directory / "slice-capsule.v1.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            capsule = json.loads(capsule_path.read_text(encoding="utf-8"))
            store[("run_path", manifest_path.relative_to(run_dir).as_posix())] = manifest_path.read_bytes()
            store[("run_path", capsule_path.relative_to(run_dir).as_posix())] = capsule_path.read_bytes()
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            findings.append(_finding("RMAP-ATTEMPT-PARTIAL", directory.as_posix(), str(exc)))
            continue
        contexts.append({"context_manifest": manifest, "slice_capsule": capsule})
    for directory in sorted((run_dir / "attempts").glob("ATTEMPT-*")):
        attempt: dict[str, Any] = {}
        for key, name in (("backend_request", "backend-request.v1.json"), ("backend_response", "backend-response.v1.json"), ("diff_manifest", "diff-manifest.v1.json"), ("adapter_decision", "adapter-decision.v1.json")):
            path = directory / name
            try:
                attempt[key] = json.loads(path.read_text(encoding="utf-8"))
                store[("run_path", path.relative_to(run_dir).as_posix())] = path.read_bytes()
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                findings.append(_finding("RMAP-ATTEMPT-PARTIAL", directory.as_posix(), str(exc)))
                break
        if len(attempt) == 4:
            attempts.append(attempt)
    try:
        event_path = run_dir / "run-events.jsonl"
        events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        store[("run_path", "run-events.jsonl")] = event_path.read_bytes()
        baseline_path = run_dir / "baseline-file-manifest.v1.json"
        ledger_path = run_dir / "attempt-ledger-manifest.v1.json"
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        store[("run_path", "baseline-file-manifest.v1.json")] = baseline_path.read_bytes()
        store[("run_path", "attempt-ledger-manifest.v1.json")] = ledger_path.read_bytes()
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        findings.append(_finding("RMAP-ATTEMPT-PARTIAL", run_dir.as_posix(), str(exc)))
        events, baseline, ledger = [], {}, {}
    bundle = {
        "schema_version": "rmap.capsule-attempt-bundle.v1",
        "contexts": contexts,
        "attempts": attempts,
        "events": events,
        "baseline_file_manifest": baseline,
        "attempt_ledger_manifest": ledger,
    }
    if not findings:
        repo_root = plan_root.parents[1]
        roots = {"repo_path": repo_root, "plan_path": plan_root, "run_path": run_dir}
        refs: list[dict[str, Any]] = []
        for pair in contexts:
            context, capsule = pair["context_manifest"], pair["slice_capsule"]
            refs.extend([context.get("capsule_ref"), *context.get("artifact_refs", [])])
            refs.extend([*capsule.get("authority_refs", []), capsule.get("implementation_contract"), capsule.get("baseline_ref"), *capsule.get("stage_evidence_refs", [])])
            if capsule.get("latest_blocker_ref") is not None:
                refs.append(capsule["latest_blocker_ref"])
        for attempt in attempts:
            refs.append(attempt["backend_request"].get("capsule_ref"))
            refs.extend(attempt["adapter_decision"].get("evidence_refs", []))
            refs.extend(entry.get("result_snapshot_ref") for entry in attempt["diff_manifest"].get("files", []))
            stage_path = attempt["adapter_decision"].get("stage_result_path")
            if isinstance(stage_path, str):
                refs.append({"path_type": "run_path", "path": stage_path})
        for event in events:
            refs.extend(event.get("artifact_refs", []))
        for entry in baseline.get("files", []):
            if entry.get("snapshot_ref") is not None:
                refs.append(entry["snapshot_ref"])
        for ref in refs:
            if not isinstance(ref, dict) or ref.get("path_type") not in roots or not safe_relative(ref.get("path")):
                continue
            path = roots[ref["path_type"]] / ref["path"]
            if path.is_file():
                store[(ref["path_type"], ref["path"])] = path.read_bytes()
        baseline_map = {entry.get("path"): entry for entry in baseline.get("files", [])}
        prior_after: dict[str, bytes | None] = {}
        for index, attempt in enumerate(attempts):
            attempt_id = attempt["backend_request"]["attempt_id"]
            for entry in attempt["diff_manifest"]["files"]:
                path = entry["path"]
                if index == 0:
                    snapshot = baseline_map.get(path, {}).get("snapshot_ref")
                    before = store.get(store_key(snapshot)) if isinstance(snapshot, dict) else None
                else:
                    before = prior_after.get(path)
                snapshot = entry.get("result_snapshot_ref")
                after = store.get(store_key(snapshot)) if isinstance(snapshot, dict) else None
                file_versions[(attempt_id, "before", path)] = before
                file_versions[(attempt_id, "after", path)] = after
                prior_after[path] = after
        if attempts:
            for entry in attempts[-1]["diff_manifest"]["files"]:
                current_path = repo_root / entry["path"]
                current = current_path.read_bytes() if current_path.is_file() else None
                final_snapshot = file_versions.get((attempts[-1]["backend_request"]["attempt_id"], "after", entry["path"]))
                if current != final_snapshot:
                    findings.append(_finding("RMAP-ATTEMPT-AFTER-HASH", entry["path"], "final result snapshot differs from current repository bytes"))
        findings.extend(validate_protocol_bundle(plan_root, bundle, artifact_store=store, file_versions=file_versions, require_complete=True))
    return bundle, findings

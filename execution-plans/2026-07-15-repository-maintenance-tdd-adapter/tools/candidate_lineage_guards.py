from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from contract_guards import contained_file, schema_error
from protocol_guards import load_protocol_run


def _finding(rule_id: str, target: str, message: str) -> dict[str, str]:
    return {"rule_id": rule_id, "target": target, "message": message}


def bytes_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def value_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return bytes_hash(payload)


def manifest_root_hash(document: dict[str, Any]) -> str:
    value = dict(document)
    value.pop("root_hash", None)
    return value_hash(value)


def fold_accepted_attempts(bundle: dict[str, Any], initial: dict[str, str | None] | None = None) -> tuple[list[dict[str, Any]], str, list[dict[str, str]]]:
    baseline = dict(initial) if initial is not None else {entry.get("path"): entry.get("sha256") for entry in bundle.get("baseline_file_manifest", {}).get("files", [])}
    current = dict(baseline)
    touched: set[str] = set()
    findings: list[dict[str, str]] = []
    for attempt in bundle.get("attempts", []):
        decision = attempt.get("adapter_decision", {})
        if decision.get("decision") != "accepted_for_validation":
            continue
        attempt_id = str(decision.get("attempt_id"))
        for entry in attempt.get("diff_manifest", {}).get("files", []):
            path = entry.get("path")
            if path not in baseline:
                if entry.get("change_type") != "add" or entry.get("before_sha256") is not None:
                    findings.append(_finding("RMAP-CANDIDATE-LEDGER-FOLD", attempt_id, f"new path is not introduced by add with a null before hash: {path}"))
                    continue
                baseline[path] = None
                current[path] = None
            if entry.get("before_sha256") != current.get(path):
                findings.append(_finding("RMAP-CANDIDATE-LEDGER-FOLD", attempt_id, f"before hash does not continue accepted state for {path}"))
            current[path] = entry.get("after_sha256")
            touched.add(str(path))
    folded: list[dict[str, Any]] = []
    for path in sorted(touched, key=str.casefold):
        before, after = baseline.get(path), current.get(path)
        if before == after:
            continue
        change_type = "add" if before is None else "delete" if after is None else "modify"
        folded.append({"change_type": change_type, "baseline_path": None if change_type == "add" else path, "candidate_path": None if change_type == "delete" else path, "before_sha256": before, "after_sha256": after})
    return folded, value_hash(folded), findings


def validate_candidate_lineage_model(plan_root: Path, lineage: dict[str, Any], run_documents: list[tuple[dict[str, Any], bytes]], candidate_run_id: str, current: dict[str, str]) -> tuple[list[dict[str, Any]], str, list[dict[str, str]]]:
    schema = json.loads((plan_root / "schemas" / "candidate-lineage-manifest.v1.schema.json").read_text(encoding="utf-8"))
    error = schema_error(lineage, schema)
    if error:
        return [], value_hash([]), [_finding("RMAP-CANDIDATE-LINEAGE", "candidate-lineage-manifest", error)]
    refs = lineage.get("slice_runs", [])
    if [item.get("slice_id") for item in refs] != [f"RMAP-S{index}" for index in range(7)] or len(run_documents) != len(refs):
        return [], value_hash([]), [_finding("RMAP-CANDIDATE-LINEAGE", "candidate-lineage-manifest", "slice lineage must cover S0 through S6 exactly once")]
    if lineage.get("candidate_run_id") != candidate_run_id or lineage.get("baseline_identity") != {key: current.get(key) for key in ("head", "index_tree")}:
        return [], value_hash([]), [_finding("RMAP-CANDIDATE-LINEAGE", "candidate-lineage-manifest", "candidate or baseline identity is stale")]
    current_state: dict[str, str | None] = {}
    original: dict[str, str | None] = {}
    initialized = False
    previous_slice_id: str | None = None
    previous_run_id: str | None = None
    previous_effect_hash: str | None = None
    findings: list[dict[str, str]] = []
    effect_schema = json.loads((plan_root / "schemas" / "candidate-slice-effect.v1.schema.json").read_text(encoding="utf-8"))
    for ref, (effect, raw_bytes) in zip(refs, run_documents, strict=True):
        if (
            ref.get("previous_slice_id") != previous_slice_id
            or ref.get("previous_slice_run_id") != previous_run_id
            or ref.get("previous_slice_effect_hash") != previous_effect_hash
            or ref.get("run_artifact_sha256") != bytes_hash(raw_bytes)
        ):
            findings.append(_finding("RMAP-CANDIDATE-LINEAGE", str(ref.get("slice_id")), "previous-slice effect chain or artifact hash is stale"))
            continue
        run_id = str(ref.get("run_id"))
        effect_error = schema_error(effect, effect_schema)
        if effect_error:
            findings.append(_finding("RMAP-CANDIDATE-LINEAGE", str(ref.get("slice_id")), effect_error))
            continue
        if effect.get("run_id") != run_id or effect.get("slice_id") != ref.get("slice_id") or effect.get("root_hash") != manifest_root_hash(effect):
            findings.append(_finding("RMAP-CANDIDATE-LINEAGE", str(ref.get("slice_id")), "run artifact identity differs from lineage"))
        if not initialized:
            original = {entry.get("path"): entry.get("sha256") for entry in effect.get("baseline_files", [])}
            current_state = dict(original)
            initialized = True
        elif {entry.get("path"): entry.get("sha256") for entry in effect.get("baseline_files", [])} != original:
            findings.append(_finding("RMAP-CANDIDATE-LINEAGE", str(ref.get("slice_id")), "slice effect baseline differs from the lineage baseline"))
        effects = effect.get("effects", [])
        if value_hash(effects) != ref.get("accepted_attempt_fold_hash"):
            findings.append(_finding("RMAP-CANDIDATE-LINEAGE", str(ref.get("slice_id")), "accepted attempt fold hash is stale"))
        for entry in effects:
            path = str(entry.get("candidate_path") or entry.get("baseline_path"))
            if path not in original:
                if entry.get("change_type") != "add" or entry.get("before_sha256") is not None or path in current_state:
                    findings.append(_finding("RMAP-CANDIDATE-LINEAGE", str(ref.get("slice_id")), f"new path is not a first add for {path}"))
                original[path] = None
                current_state[path] = None
            if entry.get("before_sha256") != current_state.get(path):
                findings.append(_finding("RMAP-CANDIDATE-LINEAGE", str(ref.get("slice_id")), f"slice effect does not continue accepted state for {path}"))
            current_state[path] = entry.get("after_sha256")
        if ref.get("final_event_hash") != effect.get("final_event_hash"):
            findings.append(_finding("RMAP-CANDIDATE-LINEAGE", str(ref.get("slice_id")), "final event hash is stale"))
        previous_run_id = run_id
        previous_slice_id = str(ref.get("slice_id"))
        previous_effect_hash = bytes_hash(raw_bytes)
    cumulative = []
    for path in sorted(set(original) | set(current_state), key=str.casefold):
        before, after = original.get(path), current_state.get(path)
        if before != after:
            change_type = "add" if before is None else "delete" if after is None else "modify"
            cumulative.append({"change_type": change_type, "baseline_path": None if change_type == "add" else path, "candidate_path": None if change_type == "delete" else path, "before_sha256": before, "after_sha256": after})
    cumulative_hash = value_hash(cumulative)
    if lineage.get("cumulative_fold_hash") != cumulative_hash or lineage.get("root_hash") != manifest_root_hash(lineage):
        findings.append(_finding("RMAP-CANDIDATE-LINEAGE", "candidate-lineage-manifest", "cumulative or root hash is stale"))
    return cumulative, cumulative_hash, findings


def load_candidate_lineage(plan_root: Path, repository_root: Path, lineage: dict[str, Any], candidate_run_id: str, current: dict[str, str]) -> tuple[list[dict[str, Any]], str, list[dict[str, str]]]:
    schema = json.loads((plan_root / "schemas" / "candidate-lineage-manifest.v1.schema.json").read_text(encoding="utf-8"))
    error = schema_error(lineage, schema)
    if error:
        return [], value_hash([]), [_finding("RMAP-CANDIDATE-LINEAGE", "candidate-lineage-manifest", error)]
    refs = lineage.get("slice_runs", [])
    if [item.get("slice_id") for item in refs] != [f"RMAP-S{index}" for index in range(7)]:
        return [], value_hash([]), [_finding("RMAP-CANDIDATE-LINEAGE", "candidate-lineage-manifest", "slice lineage must cover S0 through S6 exactly once")]
    if lineage.get("candidate_run_id") != candidate_run_id or lineage.get("baseline_identity") != {key: current.get(key) for key in ("head", "index_tree")}:
        return [], value_hash([]), [_finding("RMAP-CANDIDATE-LINEAGE", "candidate-lineage-manifest", "candidate or baseline identity is stale")]
    effect_schema = json.loads((plan_root / "schemas" / "candidate-slice-effect.v1.schema.json").read_text(encoding="utf-8"))
    original: dict[str, str | None] = {}
    current_state: dict[str, str | None] = {}
    initialized = False
    previous_slice_id: str | None = None
    previous_run_id: str | None = None
    previous_effect_hash: str | None = None
    findings: list[dict[str, str]] = []
    for ref in refs:
        path = contained_file(repository_root, ref.get("run_path"))
        if path is None:
            return [], value_hash([]), [_finding("RMAP-CANDIDATE-LINEAGE", str(ref.get("slice_id")), "run artifact escapes repository or crosses a reparse point")]
        raw = path.read_bytes()
        effect = json.loads(raw.decode("utf-8"))
        effect_error = schema_error(effect, effect_schema)
        if effect_error:
            return [], value_hash([]), [_finding("RMAP-CANDIDATE-LINEAGE", str(ref.get("slice_id")), effect_error)]
        if (
            ref.get("previous_slice_id") != previous_slice_id
            or ref.get("previous_slice_run_id") != previous_run_id
            or ref.get("previous_slice_effect_hash") != previous_effect_hash
            or ref.get("run_artifact_sha256") != bytes_hash(raw)
        ):
            findings.append(_finding("RMAP-CANDIDATE-LINEAGE", str(ref.get("slice_id")), "previous-slice effect chain or artifact hash is stale"))
        bundle, protocol_findings = load_protocol_run(plan_root, path.parent)
        if protocol_findings:
            return [], value_hash([]), protocol_findings
        ledger_path = contained_file(path.parent, "attempt-ledger-manifest.v1.json")
        events_path = contained_file(path.parent, "run-events.jsonl")
        events = bundle.get("events", [])
        if ledger_path is None or events_path is None or not events:
            return [], value_hash([]), [_finding("RMAP-CANDIDATE-LINEAGE", str(ref.get("slice_id")), "complete ledger and event sources are required")]
        if not initialized:
            baseline_entries = bundle.get("baseline_file_manifest", {}).get("files", [])
            original = {str(entry.get("path")): entry.get("sha256") for entry in baseline_entries}
            current_state = dict(original)
            initialized = True
        projected_baseline = {str(entry.get("path")): entry.get("sha256") for entry in effect.get("baseline_files", [])}
        if projected_baseline != original:
            findings.append(_finding("RMAP-CANDIDATE-LINEAGE", str(ref.get("slice_id")), "slice effect global baseline is stale or predicts future paths"))
        derived_effects, derived_hash, fold_findings = fold_accepted_attempts(bundle, current_state)
        findings.extend(fold_findings)
        accepted_ids = [
            str(item.get("adapter_decision", {}).get("attempt_id"))
            for item in bundle.get("attempts", [])
            if item.get("adapter_decision", {}).get("decision") == "accepted_for_validation"
        ]
        final_event_hash = value_hash(events[-1])
        if (
            effect.get("run_id") != ref.get("run_id")
            or effect.get("slice_id") != ref.get("slice_id")
            or effect.get("effects") != derived_effects
            or effect.get("accepted_attempt_ids") != accepted_ids
            or effect.get("attempt_ledger_manifest_hash") != bytes_hash(ledger_path.read_bytes())
            or effect.get("run_events_hash") != bytes_hash(events_path.read_bytes())
            or effect.get("final_event_hash") != final_event_hash
            or effect.get("root_hash") != manifest_root_hash(effect)
            or ref.get("accepted_attempt_fold_hash") != derived_hash
            or ref.get("final_event_hash") != final_event_hash
        ):
            findings.append(_finding("RMAP-CANDIDATE-LEDGER-FOLD", str(ref.get("slice_id")), "slice effect is not the independently recomputed run projection"))
        for entry in derived_effects:
            current_state[str(entry.get("candidate_path") or entry.get("baseline_path"))] = entry.get("after_sha256")
        previous_slice_id = str(ref.get("slice_id"))
        previous_run_id = str(ref.get("run_id"))
        previous_effect_hash = bytes_hash(raw)
    cumulative = []
    for path in sorted(set(original) | set(current_state), key=str.casefold):
        before, after = original.get(path), current_state.get(path)
        if before != after:
            change_type = "add" if before is None else "delete" if after is None else "modify"
            cumulative.append({"change_type": change_type, "baseline_path": None if change_type == "add" else path, "candidate_path": None if change_type == "delete" else path, "before_sha256": before, "after_sha256": after})
    cumulative_hash = value_hash(cumulative)
    if lineage.get("cumulative_fold_hash") != cumulative_hash or lineage.get("root_hash") != manifest_root_hash(lineage):
        findings.append(_finding("RMAP-CANDIDATE-LINEAGE", "candidate-lineage-manifest", "cumulative or root hash is stale"))
    return cumulative, cumulative_hash, findings


def validate_candidate_supersession_model(plan_root: Path, proof: dict[str, Any], recovery: dict[str, Any], events: list[dict[str, Any]], successor_run_ids: list[str], candidate_run_id: str) -> list[dict[str, str]]:
    schema = json.loads((plan_root / "schemas" / "candidate-supersession-proof.v1.schema.json").read_text(encoding="utf-8"))
    error = schema_error(proof, schema)
    if error:
        return [_finding("RMAP-CANDIDATE-SUPERSESSION", "candidate-supersession-proof", error)]
    active = proof.get("candidate_run_id") == candidate_run_id == proof.get("active_run_id")
    active = active and recovery.get("run_id") == candidate_run_id and recovery.get("state") not in {"superseded", "stale"}
    active = active and successor_run_ids == []
    active = active and events and proof.get("final_event_hash") == value_hash(events[-1])
    if not active or any(event.get("event_type") == "attempt-superseded" for event in events):
        return [_finding("RMAP-CANDIDATE-SUPERSESSION", "candidate-supersession-proof", "authoritative recovery or event lineage shows the S6 candidate is not active")]
    return []


def discover_successor_run_ids(repository_root: Path, proof: dict[str, Any], candidate_run_id: str) -> tuple[list[str], list[dict[str, str]]]:
    scan_root = contained_file(repository_root, proof.get("successor_scan_root"), must_exist=False)
    if scan_root is None:
        return [], [_finding("RMAP-CANDIDATE-SUPERSESSION", "candidate-supersession-proof", "successor scan root escapes repository containment")]
    root = repository_root / str(proof.get("successor_scan_root"))
    if not root.exists():
        return [], []
    successors: list[str] = []
    for run_dir in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: item.name.casefold()):
        relative = (run_dir / "recovery-state.json").relative_to(repository_root).as_posix()
        recovery_path = contained_file(repository_root, relative)
        if recovery_path is None:
            continue
        try:
            recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            return [], [_finding("RMAP-CANDIDATE-SUPERSESSION", relative, "successor recovery state is unreadable")]
        if candidate_run_id in {recovery.get("predecessor_run_id"), recovery.get("supersedes_run_id")}:
            successors.append(str(recovery.get("run_id") or run_dir.name))
    return sorted(successors, key=str.casefold), []


def validate_candidate_result_ref(plan_root: Path, candidate_ref: dict[str, Any], ref_path: str, candidate_path: str, candidate_bytes: bytes, candidate: dict[str, Any], repository_root: Path | None = None) -> list[dict[str, str]]:
    schema = json.loads((plan_root / "schemas" / "candidate-result-ref.v1.schema.json").read_text(encoding="utf-8"))
    error = schema_error(candidate_ref, schema)
    if error:
        return [_finding("RMAP-CANDIDATE-REF", ref_path, error)]
    if candidate_ref.get("path") != candidate_path or candidate_ref.get("sha256") != bytes_hash(candidate_bytes) or candidate_ref.get("candidate_hash") != value_hash(candidate) or candidate_ref.get("run_id") != candidate.get("run_id"):
        return [_finding("RMAP-CANDIDATE-REF", ref_path, "S7 candidate reference is stale or points to different bytes")]
    if repository_root is None:
        return []
    proof_ref = candidate_ref["supersession_proof_ref"]
    proof_path = contained_file(repository_root, proof_ref.get("path"))
    if proof_path is None or proof_ref.get("sha256") != bytes_hash(proof_path.read_bytes()):
        return [_finding("RMAP-CANDIDATE-SUPERSESSION", ref_path, "supersession proof is missing, stale, or outside repository containment")]
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof_schema = json.loads((plan_root / "schemas" / "candidate-supersession-proof.v1.schema.json").read_text(encoding="utf-8"))
    error = schema_error(proof, proof_schema)
    if error:
        return [_finding("RMAP-CANDIDATE-SUPERSESSION", ref_path, error)]
    documents: dict[str, Any] = {}
    for key in ("recovery_state_ref", "event_log_ref"):
        artifact_ref = proof[key]
        artifact_path = contained_file(repository_root, artifact_ref.get("path"))
        if artifact_path is None or artifact_ref.get("sha256") != bytes_hash(artifact_path.read_bytes()):
            return [_finding("RMAP-CANDIDATE-SUPERSESSION", ref_path, f"{key} is stale or crosses a reparse point")]
        text = artifact_path.read_text(encoding="utf-8")
        documents[key] = [json.loads(line) for line in text.splitlines() if line] if key == "event_log_ref" else json.loads(text)
    successors, successor_findings = discover_successor_run_ids(repository_root, proof, str(candidate.get("run_id")))
    if successor_findings:
        return successor_findings
    return validate_candidate_supersession_model(plan_root, proof, documents["recovery_state_ref"], documents["event_log_ref"], successors, str(candidate.get("run_id")))

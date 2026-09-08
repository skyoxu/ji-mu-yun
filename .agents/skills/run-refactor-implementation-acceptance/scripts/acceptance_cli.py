"""Deterministic entry point for refactor implementation acceptance evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
if str(REPOSITORY_ROOT / "scripts" / "python") not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT / "scripts" / "python"))

from skill_input_gate import require_ready_skill_input  # noqa: E402

from acceptance_core import (
    InputError,
    canonical_hash,
    candidate_changed_paths,
    parse_run_input,
    resolve_code_review_policy,
    resolve_phase_policy,
    validate_baseline_manifest,
    validate_candidate_manifest,
    validate_run_input,
    verify_manifest_bytes,
)
from package_validation import validate_package
from requirement_inventory import extract_requirement_inventory
from execution_control import (
    ControlError,
    inspect_run,
    inspect_persisted_run,
    publish_receipt,
    recover_stale_persisted_action,
    resume_persisted_run,
    resume_run,
    run_controlled_command,
    start_or_resume_target_run,
    derive_target_run_identity,
)
from evidence_analysis import analyze_diff_coverage
from phase_scan import run_phase_scan
from task_checklist import audit_task_checklist
from source_clauses import extract_heading_clauses
from matrix_phase import project_acceptance_impact, publish_candidate_result, publish_final_result
from knowledge_context import freeze_knowledge_context
from repair_completeness import audit_repair_completeness
from manual_pause_closure import (
    finalize_manual_pause_closure,
    prepare_manual_pause_closure,
)
from review_reentry_decline import close_declined_review_reentry
from bootstrap_integration import (
    BootstrapBindingError,
    bind_capabilities,
    build_attestation_scope,
    build_minimal_review_scope,
    load_current_lineage_state,
    load_verified_bootstrap_import,
    validate_finding_mapping,
    validate_mapping_approval,
    project_bootstrap_execution_state,
    project_bounded_review_route,
    replay_finalized_bootstrap_run,
)
from review_requirement import decide_review_requirement
from semantic_import import finalize_acceptance, project_route
from deterministic_finalization import finalize_deterministic_run
from compact_vdd_projection import project_or_quick_dev_recovery


def _read_json(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _publish_new_json(output_path: str, value: dict) -> dict:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, sort_keys=True, indent=2) + "\n")
    except FileExistsError as exc:
        raise InputError("output is append-only") from exc
    return value


def _file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_current_review_decision(decision: object) -> dict:
    if not isinstance(decision, dict):
        raise InputError("bootstrap requirement decision is invalid")
    required = {
        "schemaVersion", "decisionVersion", "producer", "decisionStatus", "requirement", "profile", "reasonCodes",
        "requirementSources", "inputHashes", "policyHash", "candidateIdentityHash",
        "deterministicEvidenceHash", "maintainerIntent", "requiredCompanionCapabilityExpectations",
        "authorizes", "decisionHash",
    }
    if set(decision) != required | ({"profile"} if "profile" in decision else set()):
        raise InputError("current decision contract is incomplete")
    if decision.get("schemaVersion") != "acceptance-semantic-review-requirement-decision.v1" or decision.get("decisionVersion") != "v11" or decision.get("producer") != "refactor-implementation-acceptance":
        raise InputError("current decision contract revision is invalid")
    if decision.get("authorizes") != [] or decision.get("maintainerIntent") not in {"default", "request"}:
        raise InputError("current decision provenance is invalid")
    status = decision.get("decisionStatus")
    requirement = decision.get("requirement")
    if status == "blocked":
        if requirement is not None or decision.get("profile") is not None:
            raise InputError("blocked decision must not select a Bootstrap route")
    elif status == "ready":
        if requirement not in {"required", "not_required"}:
            raise InputError("ready decision requirement is invalid")
        if requirement == "required" and decision.get("profile") not in {"bootstrap-implementation-conformance", "bootstrap-skill-route"}:
            raise InputError("ready decision profile is invalid")
        if requirement == "not_required" and decision.get("profile") is not None:
            raise InputError("deterministic-only decision cannot select a profile")
    else:
        raise InputError("current decision status is invalid")
    if decision.get("decisionHash") != canonical_hash({key: value for key, value in decision.items() if key != "decisionHash"}):
        raise InputError("current decision hash is stale")
    return decision


def load_current_candidate_identity(repository_root: Path, prepared_run_input: str) -> dict:
    root = repository_root.resolve()
    prepared = (root / prepared_run_input).resolve()
    try:
        prepared.relative_to(root)
    except ValueError as exc:
        raise InputError("prepared acceptance run input escapes repository root") from exc
    document = _read_json(str(prepared))
    required = {"schemaVersion", "input", "inputHash", "candidateCustody", "authorizes"}
    if (
        not isinstance(document, dict)
        or set(document) not in {frozenset(required), frozenset(required | {"knowledgeContext"})}
        or document.get("schemaVersion") != "acceptance-run-input.v1"
        or document.get("authorizes") != []
    ):
        raise InputError("prepared acceptance run input is invalid")
    run_input = document["input"]
    validate_run_input(run_input)
    if document.get("inputHash") != canonical_hash(run_input):
        raise InputError("prepared acceptance run input hash is stale")
    target_root = Path(run_input["target"]).resolve()
    try:
        target_root.relative_to(root)
    except ValueError as exc:
        raise InputError("acceptance target escapes repository root") from exc

    def target_file(relative_path: str, label: str) -> Path:
        value = (target_root / relative_path).resolve()
        try:
            value.relative_to(target_root)
        except ValueError as exc:
            raise InputError(f"{label} escapes acceptance target") from exc
        return value

    baseline_path = target_file(
        run_input["baseline_content_manifest_path"], "baseline content manifest"
    )
    candidate_path = target_file(
        run_input["candidate_content_manifest_path"], "candidate content manifest"
    )
    baseline = _read_json(str(baseline_path))
    candidate = _read_json(str(candidate_path))
    validate_baseline_manifest(baseline)
    validate_candidate_manifest(candidate, baseline)
    if sorted(run_input.get("changed_paths", [])) != candidate_changed_paths(candidate):
        raise InputError("run input changed_paths does not match candidate content manifest")
    if canonical_hash(baseline) != run_input["baseline_content_manifest_hash"]:
        raise InputError("baseline content manifest hash is stale")
    if canonical_hash(candidate) != run_input["candidate_content_manifest_hash"]:
        raise InputError("candidate content manifest hash is stale")
    if verify_manifest_bytes(target_root, run_input, baseline, candidate) != document["candidateCustody"]:
        raise InputError("prepared acceptance candidate custody is stale")
    knowledge_context = document.get("knowledgeContext")
    if not isinstance(knowledge_context, dict) or not isinstance(
        knowledge_context.get("path"), str
    ):
        raise InputError("prepared acceptance knowledge context is required for exact reuse")
    if freeze_knowledge_context(target_root, knowledge_context["path"]) != knowledge_context:
        raise InputError("prepared acceptance knowledge context is stale")
    knowledge_path = target_file(knowledge_context["path"], "knowledge context")
    knowledge_artifacts = [{
        "path": knowledge_path.relative_to(root).as_posix(),
        "sha256": knowledge_context["sha256"],
    }]
    for decision in knowledge_context.get("acceptedDecisions", []):
        knowledge_candidate = (
            decision.get("candidate") if isinstance(decision, dict) else None
        )
        path = (
            knowledge_candidate.get("path")
            if isinstance(knowledge_candidate, dict)
            else None
        )
        digest = (
            knowledge_candidate.get("source_sha256")
            if isinstance(knowledge_candidate, dict)
            else None
        )
        if (
            not isinstance(path, str)
            or not path
            or not isinstance(digest, str)
            or not digest
        ):
            raise InputError("prepared acceptance knowledge source is invalid")
        knowledge_artifacts.append({
            "path": path.replace("\\", "/"),
            "sha256": digest if digest.startswith("sha256:") else "sha256:" + digest,
        })
    knowledge_by_path: dict[str, str] = {}
    for artifact in knowledge_artifacts:
        previous = knowledge_by_path.setdefault(artifact["path"], artifact["sha256"])
        if previous != artifact["sha256"]:
            raise InputError("prepared acceptance knowledge source binding is ambiguous")
    changed_path_bindings: list[dict[str, str]] = []

    def add_changed_binding(relative_path: str, state: str, digest: str) -> None:
        changed_path_bindings.append({
            # Candidate manifest paths are logical repository identities. The
            # target and frozen snapshot are custody locations, not path roots.
            "path": relative_path.replace("\\", "/"),
            "state": state,
            "sha256": digest,
        })

    for item in candidate["files"]:
        kind = item["change_type"]
        if kind == "unchanged":
            continue
        if kind in {"deleted", "renamed"}:
            add_changed_binding(item["baseline_path"], "deleted", item["baseline_sha256"])
        elif kind == "copied":
            add_changed_binding(item["baseline_path"], "present", item["baseline_sha256"])
        if kind != "deleted":
            add_changed_binding(item["candidate_path"], "present", item["candidate_sha256"])
    changed_path_bindings.sort(key=lambda item: item["path"])
    changed_paths = [item["path"] for item in changed_path_bindings]
    if changed_paths != sorted(
        path.replace("\\", "/")
        for path in candidate_changed_paths(candidate)
    ):
        raise InputError("candidate changed path bindings are incomplete")
    identity = {
        "schemaVersion": "acceptance-bootstrap-reuse-candidate.v2",
        "acceptanceRunInputPath": prepared.relative_to(root).as_posix(),
        "acceptanceRunInputFileHash": _file_hash(prepared),
        "candidateContentManifestPath": candidate_path.relative_to(root).as_posix(),
        "candidateContentManifestFileHash": _file_hash(candidate_path),
        "candidateContentManifestHash": canonical_hash(candidate),
        "candidateCustodyHash": canonical_hash(document["candidateCustody"]),
        "changedPaths": changed_paths,
        "changedPathBindings": changed_path_bindings,
        "knowledgeArtifacts": [
            {"path": path, "sha256": knowledge_by_path[path]}
            for path in sorted(knowledge_by_path)
        ],
        "authorizes": [],
    }
    return {**identity, "identityHash": canonical_hash(identity)}


def export_bootstrap_candidate_command(
    repository_root: str, prepared_run_input: str
) -> dict:
    """Replay the Acceptance-owned candidate identity without granting authority."""
    return load_current_candidate_identity(
        Path(repository_root), prepared_run_input
    )


def load_current_bootstrap_route(repository_root: Path, route_path: str) -> dict:
    root = repository_root.resolve()
    route_file = (root / route_path).resolve()
    try:
        relative = route_file.relative_to(root).as_posix()
    except ValueError as exc:
        raise InputError("bootstrap route escapes repository root") from exc
    route = _read_json(str(route_file))
    return {
        "path": relative,
        "fileHash": _file_hash(route_file),
        "route": route,
        "routeHash": canonical_hash(route),
    }


def _load_prerequisite_bundle(target_root: Path, bundle_path: str) -> tuple[str, dict[str, Any], str]:
    relative = Path(bundle_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise InputError("prerequisite bundle path must stay inside the target root")
    path = (target_root / relative).resolve()
    try:
        path.relative_to(target_root)
    except ValueError as exc:
        raise InputError("prerequisite bundle path escapes the target root") from exc
    bundle = _read_json(str(path))
    if not isinstance(bundle, dict) or bundle.get("schemaVersion") != "compact-vdd-acceptance-prerequisite-bundle.v1":
        raise InputError("prerequisite bundle is invalid")
    expected_hash = canonical_hash({key: value for key, value in bundle.items() if key != "bundleHash"})
    if bundle.get("bundleHash") != expected_hash:
        raise InputError("prerequisite bundle hash is stale")
    context = bundle.get("knowledgeContext")
    if not isinstance(context, dict) or not isinstance(context.get("path"), str) or not isinstance(context.get("sha256"), str):
        raise InputError("prerequisite bundle knowledge context is invalid")
    return context["path"], bundle, _file_hash(path)


def prepare_run(input_path: str, output_path: str, knowledge_context_path: str | None = None, prerequisite_bundle_path: str | None = None) -> dict:
    input_file = Path(input_path).resolve()
    value = _read_json(input_file)
    validate_run_input(value)
    declared_target = value["target"]
    if not isinstance(declared_target, str) or not declared_target:
        raise InputError("run input target is invalid")
    target_root = Path(declared_target).resolve() if Path(declared_target).is_absolute() else input_file.parent
    if input_file.parent != target_root:
        raise InputError("run input must be stored at its declared target root")
    if not Path(declared_target).is_absolute() and ".." in Path(declared_target).parts:
        raise InputError("run input target must be repository-relative")
    def target_file(relative_path: str, field: str) -> Path:
        resolved = (target_root / relative_path).resolve()
        try:
            resolved.relative_to(target_root)
        except ValueError as exc:
            raise InputError(f"{field} escapes the declared target root") from exc
        return resolved
    baseline = _read_json(target_file(value["baseline_content_manifest_path"], "baseline_content_manifest_path"))
    candidate = _read_json(target_file(value["candidate_content_manifest_path"], "candidate_content_manifest_path"))
    validate_baseline_manifest(baseline)
    validate_candidate_manifest(candidate, baseline)
    declared_paths = value.get("changed_paths")
    if sorted(declared_paths) != candidate_changed_paths(candidate):
        raise InputError("run input changed_paths does not match candidate content manifest")
    if canonical_hash(baseline) != value["baseline_content_manifest_hash"]:
        raise InputError("baseline content manifest hash is stale")
    if canonical_hash(candidate) != value["candidate_content_manifest_hash"]:
        raise InputError("candidate content manifest hash is stale")
    candidate_custody = verify_manifest_bytes(target_root, value, baseline, candidate)
    prerequisite_binding = None
    if prerequisite_bundle_path is not None:
        bundle_context_path, bundle, bundle_file_hash = _load_prerequisite_bundle(target_root, prerequisite_bundle_path)
        if knowledge_context_path is not None and knowledge_context_path != bundle_context_path:
            raise InputError("caller knowledge context cannot override prerequisite bundle")
        knowledge_context_path = bundle_context_path
        implementation_receipt = bundle.get("implementationReceipt")
        if (
            not isinstance(implementation_receipt, dict)
            or set(implementation_receipt) != {"path", "sha256", "terminalCommandId"}
            or not isinstance(implementation_receipt["path"], str)
            or not isinstance(implementation_receipt["sha256"], str)
            or not isinstance(implementation_receipt["terminalCommandId"], str)
        ):
            raise InputError("prerequisite bundle implementation receipt is invalid")
        receipt_path = ((REPOSITORY_ROOT / implementation_receipt["path"]).resolve()
                        if "currentQuickDev" in bundle else target_file(implementation_receipt["path"], "implementation receipt"))
        if "currentQuickDev" in bundle:
            from current_quick_dev_handoff import verify_current_handoff
            receipt_path.relative_to(REPOSITORY_ROOT.resolve())
            if bundle["currentQuickDev"].get("receipt") != {"path": implementation_receipt["path"], "sha256": implementation_receipt["sha256"]}:
                raise InputError("current Quick Dev receipt binding mismatch")
            verify_current_handoff(REPOSITORY_ROOT, bundle["currentQuickDev"])
        if not receipt_path.is_file() or _file_hash(receipt_path) != implementation_receipt["sha256"]:
            raise InputError("prerequisite bundle implementation receipt is stale")
        prerequisite_binding = {
            "path": Path(prerequisite_bundle_path).as_posix(),
            "sha256": bundle_file_hash,
            "bundleHash": bundle["bundleHash"],
            "implementationReceipt": implementation_receipt,
        }
    knowledge_context = (
        freeze_knowledge_context(target_root, knowledge_context_path)
        if knowledge_context_path is not None
        else None
    )
    result = {
        "schemaVersion": "acceptance-run-input.v1",
        "input": value,
        "inputHash": canonical_hash(value),
        "candidateCustody": candidate_custody,
        **({"prerequisiteBundle": prerequisite_binding} if prerequisite_binding is not None else {}),
        **({"knowledgeContext": knowledge_context} if knowledge_context is not None else {}),
        "authorizes": [],
    }
    return _publish_new_json(output_path, result)


def resolve_phase_policy_command(policy_path: str, baseline_path: str, candidate_path: str, adapter_hash: str) -> dict:
    return resolve_phase_policy(_read_json(policy_path), _read_json(candidate_path), _read_json(baseline_path), adapter_hash)


def resolve_code_review_policy_command(policy_path: str, baseline_path: str, candidate_path: str, adapter_hash: str) -> dict:
    return resolve_code_review_policy(_read_json(policy_path), _read_json(candidate_path), _read_json(baseline_path), adapter_hash)


def extract_requirements_command(source_path: str, repository_root: str, output_path: str | None = None) -> dict:
    source = Path(source_path).resolve()
    root = Path(repository_root).resolve()
    try:
        relative = source.relative_to(root).as_posix()
    except ValueError as exc:
        raise InputError("requirement source must be inside repository root") from exc
    result = extract_requirement_inventory(source, relative)
    if output_path is None:
        return result
    output = Path(output_path).resolve()
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise InputError("requirement inventory output must be inside repository root") from exc
    if output.exists():
        raise InputError("requirement inventory output is append-only")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def analyze_diff_coverage_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    if not isinstance(request, dict):
        raise InputError("coverage request must be an object")
    required = {
        "acceptance_run_id", "baseline_revision", "candidate_revision", "candidate_manifest_hash", "candidate_manifest",
        "changed_line_set", "cobertura_path", "source_map", "test_run_evidence_id",
    }
    if set(request) != required or not isinstance(request["source_map"], dict):
        raise InputError("coverage request fields are invalid")
    result = analyze_diff_coverage(
        acceptance_run_id=request["acceptance_run_id"], baseline_revision=request["baseline_revision"],
        candidate_revision=request["candidate_revision"], candidate_manifest_hash=request["candidate_manifest_hash"], candidate_manifest=request["candidate_manifest"],
        changed_line_set=request["changed_line_set"], cobertura_path=Path(request["cobertura_path"]),
        source_map=request["source_map"], test_run_evidence_id=request["test_run_evidence_id"],
    )
    output = Path(output_path)
    if output.exists():
        raise InputError("coverage result output is append-only")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def run_phase_scan_command(
    repository_root: str, kind: str, execution_mode: str, baseline_path: str, candidate_path: str,
    registry_path: str, command_id: str, candidate_snapshot_path: str, output_path: str,
) -> dict:
    result = run_phase_scan(
        repository_root=Path(repository_root), kind=kind, execution_mode=execution_mode, baseline_manifest=_read_json(baseline_path),
        candidate_manifest=_read_json(candidate_path), command_registry=_read_json(registry_path), command_id=command_id,
        candidate_snapshot_root=Path(candidate_snapshot_path),
    )
    output = Path(output_path)
    if output.exists():
        raise InputError("scan result output is append-only")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def run_command_command(
    repository_root: str,
    registry_path: str,
    command_id: str,
    output_path: str,
    input_paths: list[str] | None = None,
) -> dict:
    root = Path(repository_root).resolve()
    from execution_control import resolve_registered_command
    try:
        descriptor = resolve_registered_command(_read_json(registry_path), command_id)
    except ControlError as exc:
        raise InputError("controlled command must resolve from a hash-bound registry") from exc
    output = Path(output_path).resolve()
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise InputError("controlled command receipt must be inside repository root") from exc
    receipt = run_controlled_command(root, descriptor, input_paths=input_paths)
    publish_receipt(output, receipt)
    return receipt


def audit_task_checklist_command(repository_root: str, request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    if not isinstance(request, dict) or set(request) != {"acceptance_run_id", "candidate_manifest_hash", "sources", "evidence_by_item", "optional_items"}:
        raise InputError("task checklist request fields are invalid")
    result = audit_task_checklist(repository_root=Path(repository_root), **request)
    output = Path(output_path)
    if output.exists():
        raise InputError("task checklist output is append-only")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def audit_repair_completeness_command(request_path: str, output_path: str) -> dict:
    return _publish_new_json(
        output_path,
        audit_repair_completeness(_read_json(request_path)),
    )


def decline_review_reentry_command(request_path: str, output_path: str) -> dict:
    return _publish_new_json(
        output_path,
        close_declined_review_reentry(_read_json(request_path)),
    )


def prepare_manual_pause_closure_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    if not isinstance(request, dict) or not isinstance(request.get("repositoryRoot"), str):
        raise InputError("manual-pause closure repository root is invalid")
    repository_root = Path(request["repositoryRoot"]).resolve()
    try:
        source_request = Path(request_path).resolve().relative_to(repository_root).as_posix()
    except ValueError as exc:
        raise InputError("manual-pause closure request must be inside repository root") from exc
    return _publish_new_json(
        output_path,
        prepare_manual_pause_closure(request, source_request),
    )


def finalize_manual_pause_closure_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    if not isinstance(request, dict) or set(request) != {
        "repositoryRoot", "challengePath", "acknowledgement",
    }:
        raise InputError("manual-pause finalization request fields are invalid")
    return _publish_new_json(
        output_path,
        finalize_manual_pause_closure(
            Path(request["repositoryRoot"]),
            request["challengePath"],
            request["acknowledgement"],
        ),
    )


def extract_source_clauses_command(source_path: str, repository_root: str) -> dict:
    source, root = Path(source_path).resolve(), Path(repository_root).resolve()
    try:
        relative = source.relative_to(root).as_posix()
    except ValueError as exc:
        raise InputError("source clause authority must be inside repository root") from exc
    return extract_heading_clauses(source, relative)


def project_acceptance_impact_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    if not isinstance(request, dict):
        raise InputError("impact projection request must be an object")
    required_check_ids = request.get("required_check_ids")
    if (
        not isinstance(required_check_ids, list)
        or not required_check_ids
        or any(not isinstance(value, str) or not value for value in required_check_ids)
        or len(set(required_check_ids)) != len(required_check_ids)
    ):
        raise InputError("impact projection required_check_ids must be a unique string array")
    request = {**request, "required_check_ids": set(required_check_ids)}
    result = project_acceptance_impact(**request)
    output = Path(output_path)
    if output.exists():
        raise InputError("impact projection output is append-only")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def evaluate_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    if not isinstance(request, dict) or set(request) != {"candidate", "candidate_input_hash"}:
        raise InputError("candidate evaluation request fields are invalid")
    return publish_candidate_result(Path(output_path), request["candidate"], request["candidate_input_hash"])


def finalize_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    required = {"final", "candidate_path", "candidate_hash", "impact_projection_hash"}
    if not isinstance(request, dict) or set(request) != required:
        raise InputError("finalization request fields are invalid")
    return publish_final_result(
        Path(output_path),
        request["final"],
        Path(request["candidate_path"]),
        request["candidate_hash"],
        request["impact_projection_hash"],
    )


def project_semantic_route_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    if not isinstance(request, dict) or set(request) != {
        "acceptanceMode", "requestedRoute", "triggerIds",
    }:
        raise InputError("semantic route request fields are invalid")
    return _publish_new_json(
        output_path,
        project_route(
            request["acceptanceMode"], request["requestedRoute"], request["triggerIds"]
        ),
    )


def finalize_semantic_acceptance_command(request_path: str, output_path: str) -> dict:
    return _publish_new_json(output_path, finalize_acceptance(_read_json(request_path)))


def bind_bootstrap_capabilities_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    if not isinstance(request, dict) or set(request) != {"decision", "profile"}:
        raise InputError("bootstrap capability binding request fields are invalid")
    return _publish_new_json(output_path, bind_capabilities(request["decision"], request["profile"]))


def prepare_attestation_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    required = {"decision", "binding", "source_inventory", "source_clauses", "base_matrix", "artifact_view_manifest_hash"}
    if not isinstance(request, dict) or set(request) != required:
        raise InputError("attestation scope request fields are invalid")
    return _publish_new_json(output_path, build_attestation_scope(**request))


def render_command(input_path: str, output_path: str) -> dict:
    value = _read_json(input_path)
    if not isinstance(value, dict):
        raise InputError("render input must be an object")
    rendered = {
        "schemaVersion": "acceptance-rendered-view.v1",
        "inputPath": Path(input_path).as_posix(),
        "inputHash": canonical_hash(value),
        "content": value,
        "authorizes": [],
    }
    return _publish_new_json(output_path, rendered)


def collect_evidence_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    if not isinstance(request, dict) or request.get("authorizes") not in (None, []):
        raise InputError("evidence request is invalid")
    origin = request.get("origin")
    controlled = {"origin", "commandId", "commandRegistryHash", "invocationHash", "processResultPath", "processResultHash", "authorizes"}
    imported = {"origin", "sourcePath", "sourceHash", "custodyReceiptHash", "freshnessReceiptHash", "authorizes"}
    if origin == "controlled" and set(request) == controlled:
        pass
    elif origin == "imported" and set(request) == imported:
        pass
    else:
        raise InputError("evidence origin contract is invalid")
    if any(not isinstance(value, str) or not value for key, value in request.items() if key not in {"origin", "authorizes"}):
        raise InputError("evidence binding is invalid")
    return _publish_new_json(output_path, {"schemaVersion": "acceptance-evidence-record.v1", **request, "authorizes": []})


def _derive_current_bootstrap_decision(request: object) -> dict:
    required = {"repository_root", "prepared_run_input", "deterministic_evidence", "maintainer_intent"}
    if not isinstance(request, dict) or set(request) != required:
        raise InputError("current bootstrap decision requires repository-bound Acceptance references")
    repository_root = Path(request["repository_root"]).resolve()
    if not repository_root.is_dir():
        raise InputError("repository root is invalid")
    try:
        candidate_identity = load_current_candidate_identity(
            repository_root, request["prepared_run_input"]
        )
    except (OSError, ValueError, KeyError) as exc:
        raise InputError("current candidate identity is unavailable") from exc
    evidence_ref = request["deterministic_evidence"]
    if (
        not isinstance(evidence_ref, dict)
        or set(evidence_ref) != {"path", "sha256"}
        or not isinstance(evidence_ref["path"], str)
        or not isinstance(evidence_ref["sha256"], str)
    ):
        raise InputError("deterministic evidence reference is invalid")
    evidence_path = (repository_root / evidence_ref["path"]).resolve()
    try:
        evidence_path.relative_to(repository_root)
    except ValueError as exc:
        raise InputError("deterministic evidence escapes repository root") from exc
    if not evidence_path.is_file() or _file_hash(evidence_path) != evidence_ref["sha256"]:
        raise InputError("deterministic evidence is missing or stale")
    evidence = _read_json(str(evidence_path))
    policy_path = repository_root / ".agents/skills/run-refactor-implementation-acceptance/policies/semantic-review-trigger-policy.v1.json"
    if not policy_path.is_file():
        raise InputError("repository-owned semantic trigger policy is missing")
    policy = _read_json(str(policy_path))
    return decide_review_requirement({
        "candidateIdentity": candidate_identity,
        "deterministicEvidence": evidence,
        "policy": policy,
        "maintainerIntent": request["maintainer_intent"],
    })


def decide_bootstrap_command(request_path: str, output_path: str) -> dict:
    decision = _derive_current_bootstrap_decision(_read_json(request_path))
    return _publish_new_json(output_path, decision)


def prepare_bootstrap_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    base_fields = {"decision", "decision_request", "binding", "launch_authorization"}
    optional_fields = {
        "repository_root", "scope_inputs", "lineage_state", "repair_completeness",
        "repair_completeness_request",
    }
    if (
        not isinstance(request, dict)
        or not base_fields.issubset(request)
        or set(request) - (base_fields | optional_fields)
    ):
        raise InputError("bootstrap preparation request fields are invalid")
    decision = _validate_current_review_decision(request["decision"])
    if _derive_current_bootstrap_decision(request["decision_request"]) != decision:
        raise InputError("current decision provenance does not replay")
    if decision["decisionStatus"] == "blocked":
        raise InputError("deterministic Acceptance facts are blocked")
    required = decision.get("requirement") == "required"
    if required and (
        "scope_inputs" not in request
        or not isinstance(request.get("repository_root"), str)
        or not request["repository_root"].strip()
    ):
        raise InputError(
            "required bootstrap preparation needs repository root and minimal review scope inputs"
        )
    if isinstance(request.get("repository_root"), str) and request["repository_root"].strip():
        policy_path = Path(request["repository_root"]).resolve() / ".agents/skills/run-refactor-implementation-acceptance/policies/semantic-review-trigger-policy.v1.json"
        if not policy_path.is_file() or decision.get("policyHash") != canonical_hash(_read_json(str(policy_path))):
            raise InputError("current decision policy provenance is stale")
    try:
        review_scope = (
            build_minimal_review_scope(
                request["scope_inputs"],
                profile=decision["profile"],
                lineage_paths=(
                    [request["decision_request"]["prepared_run_input"]]
                    if decision["profile"] == "bootstrap-skill-route"
                    else None
                ),
            )
            if required
            else None
        )
    except BootstrapBindingError as exc:
        raise InputError(str(exc)) from exc
    if required:
        try:
            current_lineage = load_current_lineage_state(
                Path(request["repository_root"]), review_scope["lineageFamilyId"]
            )
        except BootstrapBindingError as exc:
            raise InputError(str(exc)) from exc
        if request.get("lineage_state") != current_lineage:
            raise InputError(
                "bootstrap lineage state is not the current repository-owned projection"
            )
        repair_projection = request.get("repair_completeness")
        repair_request = request.get("repair_completeness_request")
        if repair_projection is None:
            if repair_request is not None:
                raise InputError("initial bootstrap route cannot attach a repair request")
        else:
            if not isinstance(repair_request, dict):
                raise InputError("repair route requires its producer request for replay")
            replayed = audit_repair_completeness(repair_request)
            if replayed != repair_projection:
                raise InputError(
                    "repair completeness projection is stale or not producer-reproducible"
                )
    state = project_bootstrap_execution_state(
        request["decision"],
        binding=request["binding"],
        launch_authorization=request["launch_authorization"],
    )
    try:
        review_route = project_bounded_review_route(
            request["decision"],
            review_scope,
            request.get("lineage_state"),
            request.get("repair_completeness"),
        )
    except BootstrapBindingError as exc:
        raise InputError(str(exc)) from exc
    next_actions = {
        "deterministic_only": "deterministic-only-evaluation",
        "focused_repair_review": "run-phase-bootstrap-review",
        "focused_repair_verification": "run-phase-bootstrap-review",
        "full_implementation_conformance": "run-phase-bootstrap-review",
        "manual_pause": "manual-pause",
    }
    route = {
        "schemaVersion": "implementation-acceptance-bootstrap-route.v1",
        "bootstrapExecutionState": state,
        "reviewScope": review_scope,
        **review_route,
        "nextAction": next_actions[review_route["routeKind"]],
        "authorizes": [],
    }
    if request.get("repair_completeness") is not None:
        route["repairCompletenessRequest"] = request["repair_completeness_request"]
        route["repairCompletenessRequestHash"] = canonical_hash(
            request["repair_completeness_request"]
        )
    return _publish_new_json(output_path, route)


def import_focused_repair_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    required = {"repositoryRoot", "focusedRun", "acceptanceRepairRoute", "repairCompleteness"}
    if not isinstance(request, dict) or set(request) != required:
        raise InputError("focused repair import request fields are invalid")
    if not isinstance(request["repositoryRoot"], str) or not request["repositoryRoot"].strip():
        raise InputError("focused repair repository root is invalid")
    root = Path(request["repositoryRoot"]).resolve()
    run_relative = request["focusedRun"]
    if not isinstance(run_relative, str) or not run_relative.strip():
        raise InputError("focusedRun must be a repository-relative run directory")
    run_dir = (root / run_relative).resolve()
    try:
        run_dir.relative_to(root)
    except ValueError as exc:
        raise InputError("focusedRun escapes repository root") from exc
    try:
        envelope = replay_finalized_bootstrap_run(root, run_relative)
    except BootstrapBindingError as exc:
        raise InputError(str(exc)) from exc
    envelope_path = run_dir / "focused-repair-validation-envelope.json"
    if not envelope_path.is_file() or _read_json(str(envelope_path)) != envelope:
        raise InputError("focused repair envelope does not match canonical replay")

    def load_ref(name: str) -> tuple[dict, Path]:
        reference = request[name]
        if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
            raise InputError(f"{name} must be an exact path/hash reference")
        path = (root / str(reference["path"])).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise InputError(f"{name} escapes repository root") from exc
        if not path.is_file() or _file_hash(path) != reference["sha256"]:
            raise InputError(f"{name} is missing or stale")
        value = _read_json(str(path))
        if not isinstance(value, dict):
            raise InputError(f"{name} must reference a JSON object")
        return value, path

    route, route_path = load_ref("acceptanceRepairRoute")
    completeness, completeness_path = load_ref("repairCompleteness")
    exclusions = {"implementation-acceptance", "protected-handoff", "release", "commit", "done"}
    if (
        envelope.get("schemaVersion") != "bootstrap-focused-repair-validation-envelope.v1"
        or envelope.get("status") != "passed"
        or envelope.get("nextAction") != "deterministic-closure"
        or envelope.get("fullReviewRound") != 2
        or envelope.get("authorizes") != []
        or not exclusions.issubset(set(envelope.get("doesNotAuthorize", [])))
    ):
        raise InputError("focused repair envelope is not a passed non-authorizing result")
    if (
        route.get("schemaVersion") != "implementation-acceptance-bootstrap-route.v1"
        or route.get("routeKind") != "focused_repair_verification"
        or route.get("lineageFamilyId") != envelope.get("lineageFamilyId")
        or route.get("semanticRoundsConsumed") != 1
        or route.get("nextFullReviewRound") != 2
        or route.get("roundEntryReason") is not None
        or route.get("authorizes") != []
        or _file_hash(route_path) != envelope.get("acceptanceRepairRouteHash")
    ):
        raise InputError("focused repair route does not match the validation envelope")
    if (
        completeness.get("schemaVersion") != "acceptance-repair-completeness.v1"
        or completeness.get("status") != "passed"
        or completeness.get("lineageFamilyId") != envelope.get("lineageFamilyId")
        or completeness.get("semanticRoundsConsumed") != 1
        or completeness.get("authorizes") != []
        or _file_hash(completeness_path) != envelope.get("repairCompletenessHash")
        or canonical_hash(completeness) != route.get("repairCompletenessHash")
    ):
        raise InputError("repair completeness does not match the focused route and envelope")
    action_dag = {"actions": [{"actionId": "source-freeze", "state": "completed"}, {"actionId": "consumer-closure", "state": "completed"}, {"actionId": "finalization", "state": "completed"}]}
    result = {
        "schemaVersion": "implementation-acceptance-focused-repair-import.v1",
        "lineageFamilyId": envelope["lineageFamilyId"],
        "reviewId": envelope["reviewId"],
        "fullReviewRound": 2,
        "status": "ready_for_deterministic_evaluation",
        "focusedEnvelopeHash": _file_hash(envelope_path),
        "acceptanceRepairRouteHash": _file_hash(route_path),
        "repairCompletenessHash": _file_hash(completeness_path),
        "authorizes": [],
        "doesNotAuthorize": sorted(exclusions),
    }
    return _publish_new_json(output_path, result)


def import_bootstrap_launch_authorization_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    if not isinstance(request, dict) or set(request) != {"launchAuthorization"}:
        raise InputError("bootstrap launch authorization request fields are invalid")
    authorization = request["launchAuthorization"]
    if not isinstance(authorization, dict) or authorization.get("status") != "authorized" or not isinstance(authorization.get("authorizationHash"), str):
        raise InputError("bootstrap launch authorization is invalid")
    return _publish_new_json(output_path, authorization)


def import_bootstrap_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    required = {
        "repositoryRoot", "bootstrapRunDir", "binding", "scope", "acceptanceRunInput",
        "bootstrapRoute",
    }
    if not isinstance(request, dict) or set(request) != required:
        raise InputError("bootstrap import request fields are invalid")
    try:
        repository_root = Path(request["repositoryRoot"])
        candidate_identity = load_current_candidate_identity(
            repository_root, request["acceptanceRunInput"]
        )
        bootstrap_route = load_current_bootstrap_route(
            repository_root, request["bootstrapRoute"]
        )
        result = load_verified_bootstrap_import(
            repository_root, request["bootstrapRunDir"], request["binding"], request["scope"],
            candidate_identity, bootstrap_route,
        )
    except (TypeError, ValueError) as exc:
        raise InputError(str(exc)) from exc
    return _publish_new_json(output_path, {"schemaVersion": "bootstrap-import-envelope.v3", **result, "authorizes": []})


def map_findings_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    if not isinstance(request, dict) or set(request) != {"mapping", "liveCheckIds", "tombstonedCheckIds"}:
        raise InputError("finding mapping request fields are invalid")
    live, tombstoned = request["liveCheckIds"], request["tombstonedCheckIds"]
    if not isinstance(live, list) or not isinstance(tombstoned, list):
        raise InputError("finding mapping check identifiers are invalid")
    validate_finding_mapping(request["mapping"], set(live), set(tombstoned))
    return _publish_new_json(output_path, request["mapping"])


def import_mapping_approval_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    required = {"approval", "requiredApproverRole", "findingHash", "matrixHash", "lineageHash", "importEnvelopeHash"}
    if not isinstance(request, dict) or set(request) != required:
        raise InputError("mapping approval import request fields are invalid")
    validate_mapping_approval(
        request["approval"], request["requiredApproverRole"], request["findingHash"], request["matrixHash"],
        request["lineageHash"], request["importEnvelopeHash"],
    )
    return _publish_new_json(output_path, request["approval"])


def _load_bound_json(base: Path, reference: object, label: str) -> tuple[dict, dict[str, str]]:
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise InputError(f"{label} reference is invalid")
    relative, digest = reference.get("path"), reference.get("sha256")
    if not isinstance(relative, str) or not isinstance(digest, str):
        raise InputError(f"{label} reference is invalid")
    path = (base / relative).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError as exc:
        raise InputError(f"{label} reference escapes request root") from exc
    if not path.is_file() or _file_hash(path) != digest:
        raise InputError(f"{label} reference is stale")
    value = _read_json(str(path))
    if not isinstance(value, dict):
        raise InputError(f"{label} payload is invalid")
    return value, {"path": relative.replace("\\", "/"), "sha256": digest}


def _load_coordinator_evidence(base: Path, reference: object, binding: str, bundle_hash: str) -> tuple[dict, dict[str, str]]:
    evidence, ref = _load_bound_json(base, reference, "coordinator evidence")
    required = {
        "schemaVersion", "producerAuthority", "candidateBindingHash", "bundleHash",
        "deterministicSourceSufficient", "semanticReviewRequired", "actions", "authorizes",
    }
    if set(evidence) != required or evidence.get("schemaVersion") != "acceptance-coordinator-evidence.v1":
        raise InputError("coordinator evidence contract is invalid")
    if evidence.get("candidateBindingHash") != binding or evidence.get("bundleHash") != bundle_hash or evidence.get("authorizes") != []:
        raise InputError("coordinator evidence binding is stale")
    if not isinstance(evidence.get("deterministicSourceSufficient"), bool) or not isinstance(evidence.get("semanticReviewRequired"), bool):
        raise InputError("coordinator evidence route projection is invalid")
    authority, _ = _load_bound_json(base, evidence["producerAuthority"], "coordinator producer authority")
    if (
        authority.get("schemaVersion") != "acceptance-coordinator-producer-authority.v1"
        or authority.get("owner") != "run-refactor-implementation-acceptance"
        or authority.get("candidateBindingHash") != binding
        or authority.get("bundleHash") != bundle_hash
        or authority.get("authorizes") != []
    ):
        raise InputError("coordinator producer authority is invalid")
    expected_actions = ("source-freeze", "consumer-closure", "finalization")
    actions = evidence.get("actions")
    if not isinstance(actions, list) or [item.get("actionId") for item in actions if isinstance(item, dict)] != list(expected_actions):
        raise InputError("coordinator action evidence is invalid")
    observed = []
    for item in actions:
        if not isinstance(item, dict) or set(item) != {"actionId", "receipt"}:
            raise InputError("coordinator action evidence is invalid")
        receipt, receipt_ref = _load_bound_json(base, item["receipt"], f"coordinator {item['actionId']} receipt")
        if (
            receipt.get("schemaVersion") != "acceptance-coordinator-action-receipt.v1"
            or receipt.get("actionId") != item["actionId"]
            or receipt.get("status") != "completed"
            or receipt.get("candidateBindingHash") != binding
            or receipt.get("bundleHash") != bundle_hash
            or receipt.get("authorizes") != []
        ):
            raise InputError("coordinator action receipt is invalid")
        observed.append({"actionId": item["actionId"], "state": "completed", "receipt": receipt_ref})
    return evidence, {"path": ref["path"], "sha256": ref["sha256"], "actions": observed}


_COORDINATOR_FORBIDDEN_CALLER_FIELDS = {
    "candidateBindingHash", "bundle", "evidence", "deterministicSourceSufficient",
    "semanticReviewRequired", "route", "actionReceipts", "actionDag", "recovery",
    "successor", "telemetry", "publicationAuthorized",
}


_LEGACY_COORDINATOR_FIELDS = {
    "schemaVersion", "candidateBindingHash", "bundle", "evidence", "authorizes",
}


def _run_legacy_coordinator(request_path: str, output_path: str, request: dict) -> dict:
    """Replay the v2 evidence projection for persisted pre-trust-recovery inputs.

    Legacy requests remain read-only and fully hash-bound.  Mixed v2/v3 caller
    payloads never reach this adapter and are rejected by the current contract.
    """
    binding, bundle, evidence_ref = request["candidateBindingHash"], request["bundle"], request["evidence"]
    if (
        request["schemaVersion"] != "acceptance-coordinator-request.v3"
        or not isinstance(binding, str) or not __import__("re").fullmatch(r"sha256:[a-f0-9]{64}", binding)
        or not isinstance(bundle, dict)
        or request["authorizes"] != []
    ):
        raise InputError("coordinator legacy request is invalid")
    if bundle.get("schemaVersion") != "compact-vdd-acceptance-prerequisite-bundle.v1":
        raise InputError("coordinator bundle is invalid")
    if bundle.get("candidateBindingHash") != binding:
        raise InputError("coordinator bundle candidate binding is stale")
    if bundle.get("bundleHash") != canonical_hash({key: value for key, value in bundle.items() if key != "bundleHash"}):
        raise InputError("coordinator bundle hash is stale")
    evidence, evidence_record = _load_coordinator_evidence(Path(request_path).resolve().parent, evidence_ref, binding, bundle["bundleHash"])
    route = "semantic_review_required" if evidence["semanticReviewRequired"] else "deterministic_only"
    if not evidence["deterministicSourceSufficient"] and route == "deterministic_only":
        raise InputError("deterministic route lacks source sufficiency")
    bundle_hash = bundle["bundleHash"]
    action_dag = {"actions": evidence_record["actions"], "evidence": {"path": evidence_record["path"], "sha256": evidence_record["sha256"]}}
    result = {
        "schemaVersion": "acceptance-coordinator-result.v2", "candidateBindingHash": binding,
        "bundleHash": bundle_hash,
        "route": route, "status": "completed" if route == "deterministic_only" else "semantic_handoff_required",
        "authority": {"bundle": bundle_hash, "bundlePath": "bundle/compact-vdd-acceptance-prerequisite-bundle.v1.json", "candidate": binding},
        "routeProjection": {"deterministicSourceSufficient": evidence["deterministicSourceSufficient"], "semanticReviewRequired": evidence["semanticReviewRequired"], "projectionHash": canonical_hash({"deterministicSourceSufficient": evidence["deterministicSourceSufficient"], "semanticReviewRequired": evidence["semanticReviewRequired"]}), "sourceReadSetHash": canonical_hash(bundle.get("knowledgeContext", {}))},
        "recovery": {"latestSuccessorPointer": canonical_hash({"candidateBindingHash": binding, "bundleHash": bundle_hash}), "successorKind": "same-binding", "replayFingerprint": canonical_hash({"candidateBindingHash": binding, "bundleHash": bundle_hash, "route": route}), "successorReason": "same-binding-replay", "disposition": "successor-replay"},
        "bootstrapInvoked": False,
        "typedHandoff": None if route == "deterministic_only" else {"schemaVersion": "acceptance-semantic-handoff.v2", "candidateBindingHash": binding, "bundleHash": bundle_hash, "reason": "semantic-review-required", "authorizes": []},
        "actionDag": action_dag,
        "actionDagHash": canonical_hash(action_dag),
        "telemetry": {"elapsedMs": 0, "waitMs": 0, "interventionCount": 0, "replayed": False}, "authorizes": [],
    }
    output = Path(output_path)
    if output.exists():
        existing = _read_json(str(output))
        if existing != result:
            raise InputError("coordinator replay binding does not match existing result")
        return existing
    return _publish_new_json(str(output), result)


def _load_current_coordinator_inputs(request_path: Path, request: object) -> dict:
    required = {"schemaVersion", "targetPlan", "preparedRunInput", "skillInputReceipt", "skillInputContract", "authorizes"}
    if not isinstance(request, dict):
        raise InputError("coordinator request is invalid")
    if _COORDINATOR_FORBIDDEN_CALLER_FIELDS & set(request):
        raise InputError("coordinator caller control fields are forbidden")
    if set(request) not in (required, required | {"maintainerIntent"}) or request.get("maintainerIntent", "default") not in {"default", "request"} or request.get("schemaVersion") != "jimuyun.acceptance-coordinator-request.v3" or request.get("authorizes") != []:
        raise InputError("coordinator request is invalid")
    if not isinstance(request.get("targetPlan"), str) or not request["targetPlan"]:
        raise InputError("coordinator target plan is invalid")

    def load(field: str) -> tuple[dict, dict]:
        reference = request.get(field)
        if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
            raise InputError(f"coordinator {field} reference is invalid")
        raw = reference["path"]
        if not isinstance(raw, str) or not raw or Path(raw).is_absolute() or ".." in Path(raw).parts:
            raise InputError(f"coordinator {field} path is invalid")
        path = (request_path.parent / raw).resolve()
        try:
            path.relative_to(request_path.parent.resolve())
        except ValueError as exc:
            raise InputError(f"coordinator {field} path escapes request root") from exc
        if not path.is_file() or _file_hash(path) != reference["sha256"]:
            label = "prepared run input" if field == "preparedRunInput" else field
            raise InputError(f"coordinator {label} is stale")
        value = _read_json(str(path))
        if not isinstance(value, dict):
            raise InputError(f"coordinator {field} artifact is invalid")
        return value, {"path": raw.replace("\\", "/"), "sha256": reference["sha256"]}

    prepared, prepared_ref = load("preparedRunInput")
    receipt, receipt_ref = load("skillInputReceipt")
    contract, contract_ref = load("skillInputContract")
    if prepared.get("schemaVersion") != "acceptance-run-input.v1":
        raise InputError("coordinator prepared run input is invalid")
    if receipt.get("ready") is not True or receipt.get("authorizes") not in (None, []):
        raise InputError("coordinator Skill input receipt is not ready")
    if contract.get("schema_version") != "skill-input-contract.v1":
        raise InputError("coordinator Skill input contract is invalid")
    context_ref = receipt.get("context_artifact")
    if not isinstance(context_ref, dict) or set(context_ref) != {"path", "sha256"}:
        raise InputError("coordinator Skill input context reference is invalid")
    context_path = (request_path.parent / request["skillInputReceipt"]["path"]).parent.joinpath(str(context_ref["path"])).resolve()
    if not context_path.is_file() or canonical_hash(_read_json(str(context_path))) != context_ref["sha256"]:
        raise InputError("coordinator Skill input context is stale")
    try:
        ready = require_ready_skill_input(
            receipt_path=(request_path.parent / request["skillInputReceipt"]["path"]).resolve(),
            repository_root=REPOSITORY_ROOT,
            contract_path=(request_path.parent / request["skillInputContract"]["path"]).resolve(),
            consumer="run-refactor-implementation-acceptance", operation="acceptance",
        )
        relative_context = context_path.relative_to(REPOSITORY_ROOT.resolve()).as_posix()
    except (ValueError, OSError) as exc:
        raise InputError("coordinator Skill input is invalid: " + str(exc)) from exc
    if receipt.get("target") != request["targetPlan"]:
        raise InputError("coordinator Skill input target mismatch")
    run_input = prepared.get("input")
    validate_run_input(run_input)
    if {"semantic_review_required", "actions", "deterministicSourceSufficient"} & set(run_input):
        raise InputError("coordinator prepared caller route or action override is forbidden")
    if run_input.get("target") != request["targetPlan"] or prepared.get("inputHash") != canonical_hash(run_input) or prepared.get("authorizes") != []:
        raise InputError("coordinator prepared target or input hash mismatch")
    target = (REPOSITORY_ROOT / request["targetPlan"]).resolve()
    try:
        target.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError as exc:
        raise InputError("coordinator target escapes repository") from exc
    for field, validator in (("baseline", validate_baseline_manifest), ("candidate", None)):
        relative = run_input[field + "_content_manifest_path"]
        path = (target / relative).resolve()
        path.relative_to(target)
        value = _read_json(str(path))
        if canonical_hash(value) != run_input[field + "_content_manifest_hash"]:
            raise InputError("coordinator candidate manifest is stale")
        if field == "baseline":
            baseline = value
            validator(value)
        else:
            candidate = value
            validate_candidate_manifest(value, baseline)
    if verify_manifest_bytes(target, run_input, baseline, candidate) != prepared.get("candidateCustody"):
        raise InputError("coordinator candidate custody is stale")
    knowledge = prepared.get("knowledgeContext")
    if not isinstance(knowledge, dict) or freeze_knowledge_context(target, knowledge.get("path")) != knowledge:
        raise InputError("coordinator knowledge context is stale")
    return {"maintainer_intent": request.get("maintainerIntent", "default"), "prepared": prepared, "prepared_ref": prepared_ref, "receipt_ref": receipt_ref, "receipt": receipt, "contract_ref": contract_ref, "skill_context_ref": {"path": relative_context, "sha256": ready["context_artifact_hash"]}, "target_plan": request["targetPlan"]}


def _append_coordinator_telemetry(run_dir: Path, value: dict) -> None:
    path = run_dir / "coordinator-telemetry.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"schemaVersion": "acceptance-coordinator-telemetry.v1", **value}, sort_keys=True) + "\n")


def _coordinator_binding(entry: dict, run_input_hash: str, contract_hash: str, knowledge_hash: str, action_hash: str) -> dict:
    binding = {"runId": entry["runId"], "runDirectory": entry["runDirectory"], "runInputHash": run_input_hash, "contractHash": contract_hash, "knowledgeContextHash": knowledge_hash, "actionDagHash": action_hash}
    return {"runBinding": binding, "runBindingHash": canonical_hash(binding)}


def run_coordinator(request_path: str, output_path: str) -> dict:
    """Execute or resume the target-owned action DAG and project its route."""
    source = Path(request_path).resolve()
    request = _read_json(str(source))
    if isinstance(request, dict) and set(request) == _LEGACY_COORDINATOR_FIELDS:
        return _run_legacy_coordinator(str(source), output_path, request)
    loaded = _load_current_coordinator_inputs(source, request)
    prepared = loaded["prepared"]
    run_input = prepared.get("input")
    if not isinstance(run_input, dict):
        raise InputError("coordinator prepared run input is incomplete")
    run_input_hash = prepared.get("inputHash")
    context = prepared.get("knowledgeContext")
    knowledge_hash = context.get("sha256") if isinstance(context, dict) else None
    if not isinstance(run_input_hash, str) or not isinstance(knowledge_hash, str):
        raise InputError("coordinator prepared run input binding is invalid")
    contract_hash = canonical_hash({"preparedRunInput": loaded["prepared_ref"], "skillInputContract": loaded["contract_ref"]})
    skill_binding_hash = loaded.get("receipt_ref", {}).get("sha256")
    skill_context_ref = loaded.get("skill_context_ref")
    skill_context_hash = skill_context_ref.get("sha256") if isinstance(skill_context_ref, dict) else None
    target_root = (REPOSITORY_ROOT / loaded["target_plan"]).resolve()
    action_path = target_root / "action-dag.v1.json"
    registry_path = target_root / "command-registry.v1.json"
    prerequisite = prepared.get("prerequisiteBundle")
    if prerequisite is not None:
        bundle_path = (target_root / prerequisite["path"]).resolve()
        bundle_path.relative_to(target_root)
        if _file_hash(bundle_path) != prerequisite["sha256"]:
            raise InputError("coordinator prerequisite bundle is stale")
        bundle = _read_json(str(bundle_path))
        if bundle.get("bundleHash") != prerequisite["bundleHash"] or canonical_hash({k: v for k, v in bundle.items() if k != "bundleHash"}) != prerequisite["bundleHash"]:
            raise InputError("coordinator prerequisite bundle hash mismatch")
        for field in ("actionDag", "commandRegistry"):
            ref = bundle[field]
            path = (target_root / ref["path"]).resolve()
            path.relative_to(target_root)
            if _file_hash(path) != ref["sha256"]:
                raise InputError("coordinator persisted " + field + " is stale")
            if field == "actionDag":
                action_path = path
            else:
                registry_path = path
    action_doc = _read_json(str(action_path))
    actions = action_doc.get("actions") if isinstance(action_doc, dict) else action_doc
    if not isinstance(actions, list) or not actions:
        raise InputError("coordinator action DAG is invalid")
    command_registry = _read_json(str(registry_path))
    output = Path(output_path)
    expected_action_hash = canonical_hash({"actions": actions, "commandRegistry": command_registry})
    skill_kwargs = {}
    if isinstance(skill_binding_hash, str) and isinstance(skill_context_ref, dict) and isinstance(skill_context_hash, str):
        skill_kwargs = {"skill_input_binding_hash": skill_binding_hash,
                        "skill_input_context_hash": skill_context_hash,
                        "skill_input_context_path": skill_context_ref["path"]}
    identity = derive_target_run_identity(REPOSITORY_ROOT, loaded["target_plan"], run_input_hash, contract_hash, knowledge_hash, **skill_kwargs)
    expected_binding = _coordinator_binding({"runId": identity["runId"], "runDirectory": identity["runDirectory"]}, run_input_hash, contract_hash, knowledge_hash, expected_action_hash)
    existing = _read_json(str(output)) if output.exists() else None
    if existing is not None:
        if (not isinstance(existing, dict) or existing.get("schemaVersion") != "acceptance-coordinator-result.v4"
                or existing.get("runBinding") != expected_binding["runBinding"]
                or existing.get("runBindingHash") != expected_binding["runBindingHash"]):
            raise InputError("coordinator replay binding does not match existing result")
    entry = start_or_resume_target_run(REPOSITORY_ROOT, loaded["target_plan"], run_input_hash, contract_hash, knowledge_hash, **skill_kwargs)
    run_dir = (REPOSITORY_ROOT / entry["runDirectory"]).resolve()
    persisted = run_dir / "prepare-run.v1.json"
    if persisted.exists():
        if _read_json(str(persisted)) != prepared:
            raise InputError("coordinator persisted prepared input is stale")
    else:
        if existing is not None:
            raise InputError("coordinator persisted prepared input is missing")
        _publish_new_json(str(persisted), prepared)
    if existing is not None:
        if (existing.get("status") == "semantic_handoff_required") != (loaded.get("maintainer_intent", "default") == "request"):
            raise InputError("coordinator replay review intent changed")
        inspection = inspect_persisted_run(run_dir, actions, run_input_hash, contract_hash, knowledge_hash)
        if existing.get("status") == "completed":
            finalization = finalize_deterministic_run(REPOSITORY_ROOT, run_dir, persisted, actions, command_registry)
            if finalization != existing.get("finalization"):
                raise InputError("coordinator replay finalization mismatch")
        elif existing.get("status") != "semantic_handoff_required" and inspection != existing.get("persistedActionState"):
            raise InputError("coordinator waiting state changed; use a successor output")
        _append_coordinator_telemetry(run_dir, {"route": existing.get("route"), "replayed": True, "elapsedMs": 0, "waitMs": 0, "interventionCount": 0, "executedActionCount": 0})
        return existing
    semantic = loaded.get("maintainer_intent", "default") == "request"
    if semantic:
        # Semantic routes are a typed handoff boundary. They must not inspect,
        # resume, or finalize the action DAG before handing control upstream.
        typed_handoff = {
            "schemaVersion": "acceptance-semantic-handoff.v2",
            "runId": entry["runId"],
            "runInputHash": run_input_hash,
            "reason": "semantic-review-required",
            "authorizes": [],
        }
        result = {
            "schemaVersion": "acceptance-coordinator-result.v4", "runId": entry["runId"],
            "runDirectory": entry["runDirectory"], "runInputHash": run_input_hash,
            "requestAuthority": "none", "route": "semantic_review_required",
            "status": "semantic_handoff_required",
            "persistedActionState": {"status": "not-started"},
            "actionDag": {"actions": actions},
            "actionDagHash": expected_action_hash, "executedActionCount": 0,
            "finalization": None, "typedHandoff": typed_handoff,
            "bootstrapInvoked": False,
            "telemetry": {"schemaVersion": "acceptance-coordinator-telemetry.v1", "path": "coordinator-telemetry.jsonl"},
            "authorizes": [],
        }
        result.update(expected_binding)
        _append_coordinator_telemetry(run_dir, {"route": "semantic_review_required", "replayed": False, "elapsedMs": 0, "waitMs": 0, "interventionCount": 1, "executedActionCount": 0})
        return _publish_new_json(str(output), result)
    started = time.monotonic()
    initial = inspect_persisted_run(run_dir, actions, run_input_hash, contract_hash, knowledge_hash)
    replayed = not bool(initial.get("readyActionIds")) and initial.get("nextAction") is None
    executed = 0
    inspection = initial
    events_path = run_dir / "acceptance-events.jsonl"
    prior_failure = events_path.is_file() and any(
        json.loads(line).get("eventType") == "action-failed"
        for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    while inspection.get("nextAction") is not None and not prior_failure:
        resumed = resume_persisted_run(
            REPOSITORY_ROOT, run_dir, actions, command_registry,
            run_input_hash, contract_hash, knowledge_hash,
        )
        executed += 1
        inspection = inspect_persisted_run(run_dir, actions, run_input_hash, contract_hash, knowledge_hash)
        if resumed and resumed.get("receipt", {}).get("exitCode") != 0:
            break
    if inspection.get("actionStates") and all(state in {"completed", "not-applicable"} for state in inspection["actionStates"].values()):
        finalization = None
        if run_input.get("execution_mode", "evidence_only") == "evidence_only":
            try:
                finalization = finalize_deterministic_run(
                    REPOSITORY_ROOT, run_dir, run_dir / "prepare-run.v1.json", actions, command_registry,
                )
            except (InputError, ControlError, FileNotFoundError) as exc:
                finalization = {"status": "not-ready", "reason": str(exc), "authorizes": []}
        route, status = "deterministic_only", "completed" if finalization and finalization.get("status") == "acceptance-passed" else "waiting"
    else:
        finalization = None
        route, status = "waiting_for_persisted_action", "waiting"
    elapsed_ms = int((time.monotonic() - started) * 1000)
    completed_count = sum(state in {"completed", "not-applicable"} for state in inspection.get("actionStates", {}).values())
    _append_coordinator_telemetry(run_dir, {"route": route, "replayed": replayed, "elapsedMs": elapsed_ms, "waitMs": 0, "interventionCount": 0, "executedActionCount": executed})
    result = {
        "schemaVersion": "acceptance-coordinator-result.v4", "runId": entry["runId"],
        "runDirectory": entry["runDirectory"], "runInputHash": run_input_hash,
        "requestAuthority": "none", "route": route, "status": status,
        "persistedActionState": inspection, "actionDag": {"actions": actions},
        "actionDagHash": expected_action_hash, "executedActionCount": completed_count,
        "finalization": finalization, "typedHandoff": None,
        "bootstrapInvoked": False,
        "telemetry": {"schemaVersion": "acceptance-coordinator-telemetry.v1", "path": "coordinator-telemetry.jsonl"},
        "authorizes": [],
    }
    result.update(expected_binding)
    return _publish_new_json(str(output), result)


def project_compact_vdd_command(repository_root: str, request_path: str, output_path: str) -> dict:
    """Project compact VDD prerequisites or emit a Quick Dev recovery route.

    The recovery route is non-authorizing and only names the owner handoff;
    Quick Dev remains responsible for executing its terminal and publishing the
    successor receipt.  Bootstrap is intentionally outside this path.
    """
    result = project_or_quick_dev_recovery(Path(repository_root), Path(request_path))
    return _publish_new_json(output_path, result)


def main() -> int:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    parse = subcommands.add_parser("parse-run-input")
    parse.add_argument("--input", required=True)
    export_candidate = subcommands.add_parser("export-bootstrap-candidate")
    export_candidate.add_argument("--repository-root", required=True)
    export_candidate.add_argument("--prepared-run-input", required=True)
    prepare = subcommands.add_parser("prepare", aliases=("prepare-run",))
    prepare.add_argument("--input", required=True)
    prepare.add_argument("--out", required=True)
    prepare.add_argument("--knowledge-context", required=True, help="Target-root-relative Refactor Acceptance knowledge context")
    prepare.add_argument("--prerequisite-bundle", help="Target-root-relative Compact VDD prerequisite bundle")
    coordinator = subcommands.add_parser("run-coordinator")
    coordinator.add_argument("--request", required=True)
    coordinator.add_argument("--out", required=True)
    projection = subcommands.add_parser("project-compact-vdd")
    projection.add_argument("--repository-root", required=True)
    projection.add_argument("--request", required=True)
    projection.add_argument("--out", required=True)
    policy = subcommands.add_parser("resolve-code-review-policy", aliases=("resolve-phase-policy",))
    policy.add_argument("--policy", required=True)
    policy.add_argument("--baseline", required=True)
    policy.add_argument("--candidate", required=True)
    policy.add_argument("--adapter-hash", required=True)
    inventory = subcommands.add_parser("inventory", aliases=("extract-requirements",))
    inventory.add_argument("--source", required=True)
    inventory.add_argument("--repository-root", required=True)
    inventory.add_argument("--out")
    coverage = subcommands.add_parser("analyze-diff-coverage")
    coverage.add_argument("--request", required=True)
    coverage.add_argument("--out", required=True)
    scan = subcommands.add_parser("run-phase-scan")
    scan.add_argument("--repository-root", required=True)
    scan.add_argument("--kind", choices=("static-analysis", "security-scan"), required=True)
    scan.add_argument("--execution-mode", required=True)
    scan.add_argument("--baseline", required=True)
    scan.add_argument("--candidate", required=True)
    scan.add_argument("--command-registry", required=True)
    scan.add_argument("--command-id", required=True)
    scan.add_argument("--candidate-snapshot", required=True)
    scan.add_argument("--out", required=True)
    for command_name, scan_kind in (("run-static-analysis", "static-analysis"), ("run-security-scan", "security-scan")):
        scoped_scan = subcommands.add_parser(command_name)
        scoped_scan.set_defaults(scan_kind=scan_kind)
        scoped_scan.add_argument("--repository-root", required=True)
        scoped_scan.add_argument("--execution-mode", required=True)
        scoped_scan.add_argument("--baseline", required=True)
        scoped_scan.add_argument("--candidate", required=True)
        scoped_scan.add_argument("--command-registry", required=True)
        scoped_scan.add_argument("--command-id", required=True)
        scoped_scan.add_argument("--candidate-snapshot", required=True)
        scoped_scan.add_argument("--out", required=True)
    controlled = subcommands.add_parser("run-command")
    controlled.add_argument("--repository-root", required=True)
    controlled.add_argument("--command-registry", required=True)
    controlled.add_argument("--command-id", required=True)
    controlled.add_argument("--input-path", action="append", default=[])
    controlled.add_argument("--out", required=True)
    checklist = subcommands.add_parser("audit-task-checklist")
    checklist.add_argument("--repository-root", required=True)
    checklist.add_argument("--request", required=True)
    checklist.add_argument("--out", required=True)
    repair_completeness = subcommands.add_parser("audit-repair-completeness")
    repair_completeness.add_argument("--request", required=True)
    repair_completeness.add_argument("--out", required=True)
    decline_reentry = subcommands.add_parser("decline-review-reentry")
    decline_reentry.add_argument("--request", required=True)
    decline_reentry.add_argument("--out", required=True)
    for name in ("prepare-manual-pause-closure", "finalize-manual-pause-closure"):
        manual_pause = subcommands.add_parser(name)
        manual_pause.add_argument("--request", required=True)
        manual_pause.add_argument("--out", required=True)
    clauses = subcommands.add_parser("extract-source-clauses")
    clauses.add_argument("--source", required=True)
    clauses.add_argument("--repository-root", required=True)
    impact = subcommands.add_parser("project-acceptance-impact")
    impact.add_argument("--request", required=True)
    impact.add_argument("--out", required=True)
    evaluate = subcommands.add_parser("evaluate")
    evaluate.add_argument("--request", required=True)
    evaluate.add_argument("--out", required=True)
    finalize = subcommands.add_parser("finalize")
    finalize.add_argument("--request", required=True)
    finalize.add_argument("--out", required=True)
    deterministic_finalize = subcommands.add_parser("finalize-deterministic-run")
    deterministic_finalize.add_argument("--repository-root", required=True)
    deterministic_finalize.add_argument("--run-dir", required=True)
    deterministic_finalize.add_argument("--run-input", required=True)
    deterministic_finalize.add_argument("--actions", required=True)
    deterministic_finalize.add_argument("--command-registry", required=True)
    deterministic_finalize.add_argument("--out", required=True)
    for name in ("project-semantic-route", "finalize-semantic-acceptance"):
        semantic = subcommands.add_parser(name)
        semantic.add_argument("--request", required=True)
        semantic.add_argument("--out", required=True)
    bind = subcommands.add_parser("bind-bootstrap-capabilities")
    bind.add_argument("--request", required=True)
    bind.add_argument("--out", required=True)
    attestation = subcommands.add_parser("prepare-attestation")
    attestation.add_argument("--request", required=True)
    attestation.add_argument("--out", required=True)
    render = subcommands.add_parser("render")
    render.add_argument("--input", required=True)
    render.add_argument("--out", required=True)
    for name in ("collect-evidence", "decide-bootstrap", "import-bootstrap-launch-authorization", "import-bootstrap", "import-focused-repair", "map-findings", "import-mapping-approval"):
        action = subcommands.add_parser(name)
        action.add_argument("--request", required=True)
        action.add_argument("--out", required=True)
    for name in ("prepare-bootstrap", "route-acceptance"):
        route = subcommands.add_parser(name)
        route.add_argument("--request", required=True)
        route.add_argument("--out", required=True)
    start = subcommands.add_parser("start-or-resume")
    start.add_argument("--repository-root", required=True)
    start.add_argument("--target-plan", required=True)
    start.add_argument("--run-input-hash", required=True)
    start.add_argument("--contract-hash", required=True)
    start.add_argument("--knowledge-context-hash", required=True)
    start.add_argument("--run-id")
    start.add_argument("--skill-input-receipt", required=True)
    start.add_argument(
        "--skill-input-contract",
        default=str(REPOSITORY_ROOT / ".agents" / "skills" / "run-refactor-implementation-acceptance" / "references" / "skill-input-contract.v1.json"),
    )
    inspect = subcommands.add_parser("inspect-run")
    inspect.add_argument("--actions", required=True)
    inspect.add_argument("--completed", required=True)
    resume = subcommands.add_parser("resume", aliases=("resume-run",))
    resume.add_argument("--repository-root", required=True)
    resume.add_argument("--actions", required=True)
    resume.add_argument("--completed", required=True)
    resume.add_argument("--command-registry", required=True)
    inspect_persisted = subcommands.add_parser("inspect-persisted-run")
    inspect_persisted.add_argument("--run-dir", required=True)
    inspect_persisted.add_argument("--actions", required=True)
    inspect_persisted.add_argument("--run-input-hash", required=True)
    inspect_persisted.add_argument("--contract-hash", required=True)
    inspect_persisted.add_argument("--knowledge-context-hash")
    resume_persisted = subcommands.add_parser("resume-persisted-run")
    resume_persisted.add_argument("--repository-root", required=True)
    resume_persisted.add_argument("--run-dir", required=True)
    resume_persisted.add_argument("--actions", required=True)
    resume_persisted.add_argument("--command-registry", required=True)
    resume_persisted.add_argument("--run-input-hash", required=True)
    resume_persisted.add_argument("--contract-hash", required=True)
    resume_persisted.add_argument("--knowledge-context-hash")
    recover_stale = subcommands.add_parser("recover-stale-action")
    recover_stale.add_argument("--run-dir", required=True)
    recover_stale.add_argument("--action-id", required=True)
    recover_stale.add_argument("--run-input-hash", required=True)
    recover_stale.add_argument("--contract-hash", required=True)
    recover_stale.add_argument("--knowledge-context-hash")
    recover_stale.add_argument("--minimum-age-seconds", type=int, default=60)
    subcommands.add_parser("validate-package")
    args = parser.parse_args()
    if args.command == "parse-run-input":
        print(json.dumps(parse_run_input(json.loads(Path(args.input).read_text(encoding="utf-8"))), sort_keys=True))
        return 0
    if args.command == "export-bootstrap-candidate":
        print(json.dumps(export_bootstrap_candidate_command(
            args.repository_root, args.prepared_run_input
        ), sort_keys=True))
        return 0
    if args.command in {"prepare", "prepare-run"}:
        print(json.dumps(prepare_run(args.input, args.out, args.knowledge_context, args.prerequisite_bundle), sort_keys=True))
        return 0
    if args.command == "run-coordinator":
        print(json.dumps(run_coordinator(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "project-compact-vdd":
        print(json.dumps(project_compact_vdd_command(args.repository_root, args.request, args.out), sort_keys=True))
        return 0
    if args.command in {"resolve-code-review-policy", "resolve-phase-policy"}:
        command = resolve_phase_policy_command if args.command == "resolve-phase-policy" else resolve_code_review_policy_command
        print(json.dumps(command(args.policy, args.baseline, args.candidate, args.adapter_hash), sort_keys=True))
        return 0
    if args.command in {"inventory", "extract-requirements"}:
        print(json.dumps(extract_requirements_command(args.source, args.repository_root, args.out), sort_keys=True))
        return 0
    if args.command == "analyze-diff-coverage":
        print(json.dumps(analyze_diff_coverage_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "run-phase-scan":
        print(json.dumps(run_phase_scan_command(args.repository_root, args.kind, args.execution_mode, args.baseline, args.candidate, args.command_registry, args.command_id, args.candidate_snapshot, args.out), sort_keys=True))
        return 0
    if args.command in {"run-static-analysis", "run-security-scan"}:
        print(json.dumps(run_phase_scan_command(args.repository_root, args.scan_kind, args.execution_mode, args.baseline, args.candidate, args.command_registry, args.command_id, args.candidate_snapshot, args.out), sort_keys=True))
        return 0
    if args.command == "run-command":
        print(json.dumps(run_command_command(
            args.repository_root,
            args.command_registry,
            args.command_id,
            args.out,
            args.input_path,
        ), sort_keys=True))
        return 0
    if args.command == "audit-task-checklist":
        print(json.dumps(audit_task_checklist_command(args.repository_root, args.request, args.out), sort_keys=True))
        return 0
    if args.command == "audit-repair-completeness":
        print(json.dumps(audit_repair_completeness_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "decline-review-reentry":
        print(json.dumps(decline_review_reentry_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "prepare-manual-pause-closure":
        print(json.dumps(prepare_manual_pause_closure_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "finalize-manual-pause-closure":
        print(json.dumps(finalize_manual_pause_closure_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "extract-source-clauses":
        print(json.dumps(extract_source_clauses_command(args.source, args.repository_root), sort_keys=True))
        return 0
    if args.command == "project-acceptance-impact":
        print(json.dumps(project_acceptance_impact_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "evaluate":
        print(json.dumps(evaluate_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "finalize":
        print(json.dumps(finalize_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "finalize-deterministic-run":
        result = finalize_deterministic_run(
            Path(args.repository_root), Path(args.run_dir), Path(args.run_input),
            _read_json(args.actions), _read_json(args.command_registry),
        )
        output = Path(args.out)
        if output.exists():
            # The finalizer itself owns and publishes the canonical wrapper.
            # Allow callers to name that wrapper as --out; it is not the CLI's
            # smaller status summary and must not be compared to it.
            existing = _read_json(str(output))
            if existing.get("schemaVersion") == "acceptance-result-final.v1":
                print(json.dumps(result, sort_keys=True))
                return 0
            if existing != result:
                raise InputError("deterministic finalization summary is not append-only")
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps(result, sort_keys=True))
        return 0
    if args.command == "project-semantic-route":
        print(json.dumps(project_semantic_route_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "finalize-semantic-acceptance":
        print(json.dumps(finalize_semantic_acceptance_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "bind-bootstrap-capabilities":
        print(json.dumps(bind_bootstrap_capabilities_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "prepare-attestation":
        print(json.dumps(prepare_attestation_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "render":
        print(json.dumps(render_command(args.input, args.out), sort_keys=True))
        return 0
    if args.command == "collect-evidence":
        print(json.dumps(collect_evidence_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "decide-bootstrap":
        print(json.dumps(decide_bootstrap_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command in {"prepare-bootstrap", "route-acceptance"}:
        print(json.dumps(prepare_bootstrap_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "start-or-resume":
        skill_input = require_ready_skill_input(
            receipt_path=Path(args.skill_input_receipt),
            repository_root=Path(args.repository_root),
            contract_path=Path(args.skill_input_contract),
            consumer="run-refactor-implementation-acceptance",
            operation="acceptance",
        )
        repository_root = Path(args.repository_root).resolve()
        context_artifact = Path(skill_input["context_artifact"]).resolve()
        try:
            context_artifact_relative = context_artifact.relative_to(repository_root).as_posix()
        except ValueError as exc:
            raise InputError("Skill input context artifact must be repository-contained") from exc
        print(json.dumps(start_or_resume_target_run(
            repository_root,
            args.target_plan,
            args.run_input_hash,
            args.contract_hash,
            args.knowledge_context_hash,
            run_id=args.run_id,
            skill_input_binding_hash=skill_input["binding_hash"],
            skill_input_context_hash=skill_input["context_artifact_hash"],
            skill_input_context_path=context_artifact_relative,
        ), sort_keys=True))
        return 0
    if args.command == "import-bootstrap-launch-authorization":
        print(json.dumps(import_bootstrap_launch_authorization_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "import-bootstrap":
        print(json.dumps(import_bootstrap_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "import-focused-repair":
        print(json.dumps(import_focused_repair_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "map-findings":
        print(json.dumps(map_findings_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "import-mapping-approval":
        print(json.dumps(import_mapping_approval_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "inspect-run":
        print(json.dumps(inspect_run(_read_json(args.actions), set(_read_json(args.completed))), sort_keys=True))
        return 0
    if args.command in {"resume", "resume-run"}:
        print(json.dumps(resume_run(Path(args.repository_root), _read_json(args.actions), set(_read_json(args.completed)), _read_json(args.command_registry)), sort_keys=True))
        return 0
    if args.command == "inspect-persisted-run":
        print(json.dumps(inspect_persisted_run(
            Path(args.run_dir), _read_json(args.actions), args.run_input_hash,
            args.contract_hash, args.knowledge_context_hash,
        ), sort_keys=True))
        return 0
    if args.command == "resume-persisted-run":
        result = resume_persisted_run(
            Path(args.repository_root), Path(args.run_dir), _read_json(args.actions),
            _read_json(args.command_registry), args.run_input_hash, args.contract_hash,
            args.knowledge_context_hash,
        )
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("receipt", {}).get("exitCode") == 0 else 1
    if args.command == "recover-stale-action":
        print(json.dumps(recover_stale_persisted_action(
            Path(args.run_dir), args.action_id, args.run_input_hash, args.contract_hash,
            args.knowledge_context_hash, minimum_age_seconds=args.minimum_age_seconds,
        ), sort_keys=True))
        return 0
    findings = validate_package(Path(__file__).resolve().parents[1])
    print(json.dumps({"status": "pass" if not findings else "fail", "findings": findings, "authorizes": []}, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())

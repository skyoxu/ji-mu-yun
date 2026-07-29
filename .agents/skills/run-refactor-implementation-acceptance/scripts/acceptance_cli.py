"""Deterministic entry point for refactor implementation acceptance evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from acceptance_core import (
    InputError,
    canonical_hash,
    candidate_changed_paths,
    parse_run_input,
    resolve_phase_policy,
    validate_baseline_manifest,
    validate_candidate_manifest,
    validate_run_input,
    verify_manifest_bytes,
)
from package_validation import validate_package
from requirement_inventory import extract_requirement_inventory
from execution_control import (
    inspect_run,
    inspect_persisted_run,
    publish_receipt,
    resume_persisted_run,
    resume_run,
    run_controlled_command,
)
from evidence_analysis import analyze_diff_coverage
from phase_scan import run_phase_scan
from task_checklist import audit_task_checklist
from source_clauses import extract_heading_clauses
from matrix_phase import project_acceptance_impact, publish_candidate_result, publish_final_result
from knowledge_context import freeze_knowledge_context
from bootstrap_integration import (
    bind_capabilities,
    build_attestation_scope,
    build_minimal_review_scope,
    validate_import_envelope,
    validate_finding_mapping,
    validate_mapping_approval,
    project_bootstrap_execution_state,
)


def _read_json(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _publish_new_json(output_path: str, value: dict) -> dict:
    output = Path(output_path)
    if output.exists():
        raise InputError("output is append-only")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return value


def prepare_run(input_path: str, output_path: str, knowledge_context_path: str | None = None) -> dict:
    input_file = Path(input_path).resolve()
    value = _read_json(input_file)
    validate_run_input(value)
    target_root = Path(value["target"]).resolve()
    if input_file.parent != target_root:
        raise InputError("run input must be stored at its declared target root")
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
    knowledge_context = (
        freeze_knowledge_context(target_root, knowledge_context_path)
        if knowledge_context_path is not None
        else None
    )
    output = Path(output_path)
    if output.exists():
        raise InputError("run input output is append-only")
    result = {
        "schemaVersion": "acceptance-run-input.v1",
        "input": value,
        "inputHash": canonical_hash(value),
        "candidateCustody": candidate_custody,
        **({"knowledgeContext": knowledge_context} if knowledge_context is not None else {}),
        "authorizes": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def resolve_phase_policy_command(policy_path: str, baseline_path: str, candidate_path: str, adapter_hash: str) -> dict:
    return resolve_phase_policy(_read_json(policy_path), _read_json(candidate_path), _read_json(baseline_path), adapter_hash)


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


def run_command_command(repository_root: str, registry_path: str, command_id: str, output_path: str) -> dict:
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
    receipt = run_controlled_command(root, descriptor)
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


def decide_bootstrap_command(request_path: str, output_path: str) -> dict:
    decision = _read_json(request_path)
    if not isinstance(decision, dict) or decision.get("requirement") not in {"required", "not_required"} or not isinstance(decision.get("requirementSources"), list) or not decision["requirementSources"]:
        raise InputError("bootstrap requirement decision is invalid")
    if decision.get("authorizes", []) != []:
        raise InputError("bootstrap requirement decision cannot authorize")
    return _publish_new_json(output_path, decision)


def prepare_bootstrap_command(request_path: str, output_path: str) -> dict:
    request = _read_json(request_path)
    base_fields = {"decision", "binding", "launch_authorization"}
    if (
        not isinstance(request, dict)
        or not base_fields.issubset(request)
        or set(request) - (base_fields | {"scope_inputs"})
    ):
        raise InputError("bootstrap preparation request fields are invalid")
    required = request["decision"].get("requirement") == "required"
    if required and "scope_inputs" not in request:
        raise InputError("required bootstrap preparation needs minimal review scope inputs")
    try:
        review_scope = (
            build_minimal_review_scope(request["scope_inputs"])
            if required
            else None
        )
    except BootstrapBindingError as exc:
        raise InputError(str(exc)) from exc
    state = project_bootstrap_execution_state(
        request["decision"],
        binding=request["binding"],
        launch_authorization=request["launch_authorization"],
    )
    route = {
        "schemaVersion": "implementation-acceptance-bootstrap-route.v1",
        "bootstrapExecutionState": state,
        "reviewScope": review_scope,
        "nextAction": "run-phase-bootstrap-review" if request["decision"].get("requirement") == "required" else "deterministic-only-evaluation",
        "authorizes": [],
    }
    return _publish_new_json(output_path, route)


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
    if not isinstance(request, dict) or set(request) != {"envelope", "expectedHashes"}:
        raise InputError("bootstrap import request fields are invalid")
    validate_import_envelope(request["envelope"], request["expectedHashes"])
    return _publish_new_json(output_path, request["envelope"])


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


def main() -> int:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    parse = subcommands.add_parser("parse-run-input")
    parse.add_argument("--input", required=True)
    prepare = subcommands.add_parser("prepare", aliases=("prepare-run",))
    prepare.add_argument("--input", required=True)
    prepare.add_argument("--out", required=True)
    prepare.add_argument("--knowledge-context", required=True, help="Target-root-relative Refactor Acceptance knowledge context")
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
    controlled.add_argument("--out", required=True)
    checklist = subcommands.add_parser("audit-task-checklist")
    checklist.add_argument("--repository-root", required=True)
    checklist.add_argument("--request", required=True)
    checklist.add_argument("--out", required=True)
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
    bind = subcommands.add_parser("bind-bootstrap-capabilities")
    bind.add_argument("--request", required=True)
    bind.add_argument("--out", required=True)
    attestation = subcommands.add_parser("prepare-attestation")
    attestation.add_argument("--request", required=True)
    attestation.add_argument("--out", required=True)
    render = subcommands.add_parser("render")
    render.add_argument("--input", required=True)
    render.add_argument("--out", required=True)
    for name in ("collect-evidence", "decide-bootstrap", "prepare-bootstrap", "import-bootstrap-launch-authorization", "import-bootstrap", "map-findings", "import-mapping-approval"):
        action = subcommands.add_parser(name)
        action.add_argument("--request", required=True)
        action.add_argument("--out", required=True)
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
    resume_persisted = subcommands.add_parser("resume-persisted-run")
    resume_persisted.add_argument("--repository-root", required=True)
    resume_persisted.add_argument("--run-dir", required=True)
    resume_persisted.add_argument("--actions", required=True)
    resume_persisted.add_argument("--command-registry", required=True)
    resume_persisted.add_argument("--run-input-hash", required=True)
    resume_persisted.add_argument("--contract-hash", required=True)
    subcommands.add_parser("validate-package")
    args = parser.parse_args()
    if args.command == "parse-run-input":
        print(json.dumps(parse_run_input(json.loads(Path(args.input).read_text(encoding="utf-8"))), sort_keys=True))
        return 0
    if args.command in {"prepare", "prepare-run"}:
        print(json.dumps(prepare_run(args.input, args.out, args.knowledge_context), sort_keys=True))
        return 0
    if args.command in {"resolve-code-review-policy", "resolve-phase-policy"}:
        print(json.dumps(resolve_phase_policy_command(args.policy, args.baseline, args.candidate, args.adapter_hash), sort_keys=True))
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
        print(json.dumps(run_command_command(args.repository_root, args.command_registry, args.command_id, args.out), sort_keys=True))
        return 0
    if args.command == "audit-task-checklist":
        print(json.dumps(audit_task_checklist_command(args.repository_root, args.request, args.out), sort_keys=True))
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
    if args.command == "prepare-bootstrap":
        print(json.dumps(prepare_bootstrap_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "import-bootstrap-launch-authorization":
        print(json.dumps(import_bootstrap_launch_authorization_command(args.request, args.out), sort_keys=True))
        return 0
    if args.command == "import-bootstrap":
        print(json.dumps(import_bootstrap_command(args.request, args.out), sort_keys=True))
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
        print(json.dumps(inspect_persisted_run(Path(args.run_dir), _read_json(args.actions), args.run_input_hash, args.contract_hash), sort_keys=True))
        return 0
    if args.command == "resume-persisted-run":
        print(json.dumps(resume_persisted_run(Path(args.repository_root), Path(args.run_dir), _read_json(args.actions), _read_json(args.command_registry), args.run_input_hash, args.contract_hash), sort_keys=True))
        return 0
    findings = validate_package(Path(__file__).resolve().parents[1])
    print(json.dumps({"status": "pass" if not findings else "fail", "findings": findings, "authorizes": []}, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())

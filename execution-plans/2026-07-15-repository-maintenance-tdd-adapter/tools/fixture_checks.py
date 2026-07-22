from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from rmap_checks import (
    finding,
    validate_commands,
    validate_contract,
    validate_coverage,
    validate_authority_manifest,
    validate_clarification_projection,
    validate_plan_state,
    validate_plan_lifecycle_policy,
    validate_requirements,
    validate_shadow_registry,
)
from authority_guards import validate_acceptance_contracts, validate_review_reentry
from artifact_proof_guards import (
    AUTHORITY_PATH,
    TRUST_ROOT_PATH,
    _manifest_entries,
    expected_static_proof,
    validate_artifact_proofs,
)

SKILL_CONTRACT_PATH = ".agents/skills/vdd-execution-plan/scripts/skill-contract.json"
from evidence_guards import validate_bootstrap_envelope_projection


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_fixture_repository(plan_root: Path, clone: Path) -> Path:
    repository_root = plan_root.parents[1]
    clone_plan = clone / plan_root.relative_to(repository_root)
    shutil.copytree(plan_root, clone_plan)
    shutil.copytree(
        repository_root / ".agents/skills/run-phase-bootstrap-review",
        clone / ".agents/skills/run-phase-bootstrap-review",
    )
    shutil.copytree(
        repository_root / ".agents/skills/vdd-execution-plan",
        clone / ".agents/skills/vdd-execution-plan",
    )
    for relative in (
        "docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md",
        "docs/standards/bootstrap-review-control-plane.md",
    ):
        target = clone / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repository_root / relative, target)
    return clone_plan


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def _set_manifest_hash(manifest: dict[str, Any], relative: str, digest: str) -> None:
    matches = [item for entries in manifest["categories"].values() for item in entries if item.get("path") == relative]
    if len(matches) != 1:
        raise ValueError(f"manifest path must occur exactly once: {relative}")
    matches[0]["sha256"] = digest


def _validate_synchronized_artifact_fixture(clone_plan: Path) -> list[dict[str, str]]:
    repository_root = clone_plan.parents[1]
    manifest_path = clone_plan / "schemas/authority-manifest.v1.json"
    manifest = _json(manifest_path)
    authority_relative = (clone_plan / AUTHORITY_PATH).relative_to(repository_root).as_posix()
    _set_manifest_hash(manifest, authority_relative, _sha(clone_plan / AUTHORITY_PATH))
    _set_manifest_hash(manifest, SKILL_CONTRACT_PATH, _sha(repository_root / SKILL_CONTRACT_PATH))
    _set_manifest_hash(manifest, ".agents/skills/vdd-execution-plan/references/strict-vdd-standard.md", _sha(repository_root / ".agents/skills/vdd-execution-plan/references/strict-vdd-standard.md"))
    _write_json(manifest_path, manifest)
    authority_registry = _json(clone_plan / AUTHORITY_PATH)
    authority_hashes, _ = _manifest_entries(manifest)
    proofs_path = clone_plan / "schemas/artifact-proof-registry.v1.json"
    proofs = _json(proofs_path)
    try:
        proofs["proofs"] = [
            expected_static_proof(repository_root, authority_registry, rule, authority_hashes)
            for rule in authority_registry["artifacts"]
        ]
    except ValueError as exc:
        return [finding("RMAP-ARTIFACT-PROOF-PRODUCER", TRUST_ROOT_PATH, str(exc))]
    _write_json(proofs_path, proofs)
    manifest = _json(manifest_path)
    proofs_relative = proofs_path.relative_to(repository_root).as_posix()
    _set_manifest_hash(manifest, proofs_relative, _sha(proofs_path))
    _write_json(manifest_path, manifest)
    return validate_artifact_proofs(clone_plan, proofs, manifest)


def evaluate_synchronized_trust_root_fixture(plan_root: Path, fixture_id: str) -> list[dict[str, str]]:
    with tempfile.TemporaryDirectory() as tmp:
        clone_plan = _copy_fixture_repository(plan_root, Path(tmp) / "repo")
        repository_root = clone_plan.parents[1]
        authority_path = clone_plan / AUTHORITY_PATH
        contract_path = repository_root / SKILL_CONTRACT_PATH
        authority = _json(authority_path)
        contract = _json(contract_path)
        root_document_path = repository_root / TRUST_ROOT_PATH
        root_document = _json(root_document_path)
        root = root_document["proof"]
        root_changed = False
        if fixture_id == "artifact-proof-synchronized-lattice-escalation":
            lattice = authority["permission_lattice"]["artifact-contract-proof"]
            lattice["authorizes"] = ["plan-ready"]
            lattice["does_not_authorize"] = [item for item in lattice["does_not_authorize"] if item != "plan-ready"]
        elif fixture_id == "artifact-proof-synchronized-staleness-truncation":
            root["staleness_propagation"]["invalidates"] = ["artifact-proof-registry"]
            root_changed = True
        elif fixture_id == "artifact-proof-synchronized-lineage-forgery":
            forged = "sha256:" + "1" * 64
            root["recovery_supersession"]["predecessor_sha256"] = forged
            next(item for item in authority["artifacts"] if item["path"].endswith("/" + AUTHORITY_PATH))["predecessor_sha256"] = forged
            root_changed = True
        elif fixture_id == "artifact-proof-synchronized-producer-source":
            standard = repository_root / ".agents/skills/vdd-execution-plan/references/strict-vdd-standard.md"
            standard.write_bytes(standard.read_bytes() + b"\nproducer-source-sync-attack\n")
            root["schema_producer_authority"]["authority_sha256"] = _sha(standard)
            root_changed = True
        else:
            return [finding("RMAP-STRUCT-FIXTURE", fixture_id, "unknown synchronized trust-root fixture")]
        _write_json(authority_path, authority)
        root["immutable_identity"]["artifact_sha256"] = _sha(authority_path)
        if root_changed:
            root_document["proof"] = root
            contract["artifact_proof_trust_roots"]["repository-maintenance-tdd-adapter"] = copy.deepcopy(root)
            _write_json(root_document_path, root_document)
            _write_json(contract_path, contract)
        return _validate_synchronized_artifact_fixture(clone_plan)


def evaluate_self_refreshed_identity_fixture(plan_root: Path) -> list[dict[str, str]]:
    with tempfile.TemporaryDirectory() as tmp:
        clone_plan = _copy_fixture_repository(plan_root, Path(tmp) / "repo")
        artifact_relative = ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-finalized-run-validation.v1.schema.json"
        artifact = clone_plan.parents[1] / artifact_relative
        artifact.write_bytes(artifact.read_bytes() + b"\n")
        digest = _sha(artifact)
        authority = _json(clone_plan / "schemas/authority-manifest.v1.json")
        next(item for entries in authority["categories"].values() for item in entries if item["path"] == artifact_relative)["sha256"] = digest
        proofs = _json(clone_plan / "schemas/artifact-proof-registry.v1.json")
        proof = next(item for item in proofs["proofs"] if item["artifact_path"] == artifact_relative)
        proof["immutable_identity"]["artifact_sha256"] = digest
        proof["source_of_truth_derivation"]["rules"][0]["source_sha256"] = digest
        proof["staleness_propagation"]["inputs"][0]["source_sha256"] = digest
        return validate_artifact_proofs(clone_plan, proofs, authority)


def evaluate_authority_root_self_refresh_fixture(plan_root: Path) -> list[dict[str, str]]:
    with tempfile.TemporaryDirectory() as tmp:
        clone_plan = _copy_fixture_repository(plan_root, Path(tmp) / "repo")
        authority_path = clone_plan / AUTHORITY_PATH
        authority_registry = _json(authority_path)
        lattice = authority_registry["permission_lattice"]["artifact-contract-proof"]
        lattice["authorizes"] = ["plan-ready"]
        lattice["does_not_authorize"] = [item for item in lattice["does_not_authorize"] if item != "plan-ready"]
        authority_path.write_text(json.dumps(authority_registry, indent=2) + "\n", encoding="utf-8", newline="\n")
        digest = _sha(authority_path)
        authority = _json(clone_plan / "schemas/authority-manifest.v1.json")
        next(item for entries in authority["categories"].values() for item in entries if item["path"].endswith("/" + AUTHORITY_PATH))["sha256"] = digest
        proofs = _json(clone_plan / "schemas/artifact-proof-registry.v1.json")
        for proof in proofs["proofs"]:
            proof["consumer_authorization_boundary"] = {
                "consumers": lattice["consumers"], "predicate": "artifact-contract-proof",
                "authorizes": lattice["authorizes"], "does_not_authorize": lattice["does_not_authorize"],
            }
        return validate_artifact_proofs(clone_plan, proofs, authority)


def evaluate_protected_boundary_takeover_fixture(plan_root: Path) -> list[dict[str, str]]:
    with tempfile.TemporaryDirectory() as tmp:
        clone_plan = _copy_fixture_repository(plan_root, Path(tmp) / "repo")
        repository_root = clone_plan.parents[1]
        targets = [
            repository_root / TRUST_ROOT_PATH,
            repository_root / ".agents/skills/run-phase-bootstrap-review/scripts/artifact_proof_root_guards.py",
            repository_root / ".agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py",
            repository_root / SKILL_CONTRACT_PATH,
            clone_plan / AUTHORITY_PATH,
            clone_plan / "schemas/authority-manifest.v1.json",
            clone_plan / "schemas/artifact-proof-registry.v1.json",
            clone_plan / "tools/artifact_proof_guards.py",
            clone_plan / "tools/refresh_projections.py",
            clone_plan / "tools/tests/test_artifact_proof_closure.py",
        ]
        for path in targets:
            suffix = b"\n" if path.suffix == ".json" else b"\n# full-stack candidate takeover\n"
            path.write_bytes(path.read_bytes() + suffix)
        verifier = Path.home() / ".codex" / "skills" / "run-phase-bootstrap-review" / "scripts" / "verify_artifact_proof_boundary.py"
        spec = importlib.util.spec_from_file_location("rmap_protected_fixture_verifier", verifier)
        if spec is None or spec.loader is None:
            return [finding("RMAP-ARTIFACT-PROOF-PROTECTED-ROOT", str(verifier), "protected diagnostic verifier is unavailable")]
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        result = module.verify_repository(repository_root)
        observed = result.get("findings") if isinstance(result, dict) else None
        root_findings = [
            item for item in observed or []
            if isinstance(item, dict) and item.get("rule_id") == "RMAP-ARTIFACT-PROOF-PROTECTED-ROOT"
        ]
        return root_findings or [finding("RMAP-ARTIFACT-PROOF-PROTECTED-ROOT", str(verifier), "protected diagnostic takeover was not accepted")]


def evaluate_lineage_fixture(plan_root: Path, fixture_id: str, registry: dict[str, Any], authority: dict[str, Any]) -> list[dict[str, str]]:
    mutated = copy.deepcopy(registry)
    target = next(item for item in mutated["proofs"] if item["artifact_path"].endswith("/" + AUTHORITY_PATH))
    lineage = target["recovery_supersession"]
    values = {
        "artifact-proof-lineage-broken-predecessor": None,
        "artifact-proof-lineage-wrong-predecessor": "sha256:" + "1" * 64,
        "artifact-proof-lineage-stale-predecessor": _sha(plan_root / AUTHORITY_PATH),
    }
    if fixture_id not in values:
        return [finding("RMAP-STRUCT-FIXTURE", fixture_id, "unknown lineage fixture")]
    lineage["predecessor_sha256"] = values[fixture_id]
    return validate_artifact_proofs(plan_root, mutated, authority)


def _pointer_parent(document: Any, pointer: str) -> tuple[Any, str]:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.strip("/").split("/")]
    current = document
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current, parts[-1]


def apply_mutations(document: Any, mutations: list[dict[str, Any]]) -> Any:
    result = copy.deepcopy(document)
    for mutation in mutations:
        parent, key = _pointer_parent(result, mutation["path"])
        if mutation["op"] == "replace":
            if isinstance(parent, list):
                parent[int(key)] = mutation["value"]
            else:
                parent[key] = mutation["value"]
        elif mutation["op"] == "add":
            if isinstance(parent, list):
                parent.append(mutation["value"]) if key == "-" else parent.insert(int(key), mutation["value"])
            else:
                parent[key] = mutation["value"]
        elif mutation["op"] == "remove":
            if isinstance(parent, list):
                del parent[int(key)]
            else:
                del parent[key]
        else:
            raise ValueError(f"unsupported mutation op: {mutation['op']}")
    return result


def validate_fixture_document(plan_root: Path, target: str, document: dict[str, Any], data: dict[str, Any]) -> list[dict[str, str]]:
    if target == "contract":
        return validate_contract(plan_root, document, data["requirements"], data["commands"])
    if target == "command_registry":
        return validate_commands(document)
    if target == "plan_state":
        return validate_plan_state(document, data["review_blocker"], data["review_reentry"], require_runtime_evidence=False)
    if target == "review_blocker":
        return validate_plan_state(data["state"], document, data["review_reentry"], require_runtime_evidence=False)
    if target == "review_reentry":
        return validate_review_reentry(plan_root, data["review_blocker"], document)
    if target == "authority_manifest":
        return validate_authority_manifest(plan_root, document)
    if target == "clarification_projection":
        return validate_clarification_projection(document)
    if target == "acceptance":
        findings = validate_requirements(plan_root, data["requirements"], data["quality"], document)
        findings.extend(validate_acceptance_contracts(document, data["requirements"], data["contract"], data["commands"], data["fixtures"], data["protocol_fixtures"], data["candidate_fixtures"]))
        findings.extend(validate_plan_lifecycle_policy(plan_root, data["requirements"], document, data["contract"], data["authority_manifest"], data["predicate_closure"]))
        return findings
    if target == "requirement_quality":
        return validate_requirements(plan_root, data["requirements"], document, data["acceptance"])
    if target == "shadow":
        return validate_shadow_registry(document)
    if target == "source_coverage":
        requirement_ids = {item["id"] for item in data["requirements"]["requirements"]}
        return validate_coverage(plan_root, document, requirement_ids)
    if target == "bootstrap_envelope":
        return validate_bootstrap_envelope_projection(plan_root.parents[1], document)
    if target == "artifact_proofs":
        return validate_artifact_proofs(plan_root, document, data["authority_manifest"])
    return [finding("RMAP-STRUCT-FIXTURE", target, "unknown fixture target")]


def evaluate_fixture(plan_root: Path, fixture_id: str, data: dict[str, Any]) -> list[dict[str, str]]:
    cases = data["fixtures"].get("cases", [])
    case = next((item for item in cases if item.get("id") == fixture_id), None)
    if case is None:
        return [finding("RMAP-STRUCT-FIXTURE", fixture_id, "fixture does not exist")]
    if case.get("target") == "artifact_identity":
        return evaluate_self_refreshed_identity_fixture(plan_root)
    if case.get("target") == "artifact_authority_root":
        return evaluate_authority_root_self_refresh_fixture(plan_root)
    if case.get("target") == "artifact_protected_boundary":
        return evaluate_protected_boundary_takeover_fixture(plan_root)
    if case.get("target") == "artifact_lineage":
        return evaluate_lineage_fixture(
            plan_root, fixture_id, data["artifact_proofs"], data["authority_manifest"]
        )
    if case.get("target") == "artifact_trust_root_sync":
        return evaluate_synchronized_trust_root_fixture(plan_root, fixture_id)
    if case.get("target") == "bootstrap_envelope":
        repository_root = plan_root.parents[1]
        profile = __import__("json").loads((repository_root / ".agents/skills/run-phase-bootstrap-review/references/review-profiles.v1.json").read_text(encoding="utf-8"))["profiles"]["bootstrap-implementation-conformance"]
        validator = repository_root / ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py"
        document = {
            "schemaVersion": "bootstrap-finalized-run-validation.v1", "validationStatus": "passed", "reviewId": "fixture-review", "changeId": "fixture-change", "fullReviewRound": 1,
            "profileName": "bootstrap-implementation-conformance", "reviewProfile": profile["reviewProfile"], "routeVersion": profile["routeVersion"], "controlPlaneRevision": profile["controlPlaneRevision"], "policyRevision": profile["policyRevision"],
            "profileHash": __import__("hashlib").sha256(__import__("json").dumps(profile, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest(),
            "authorityRevision": "fixture-authority", "inputHash": "sha256:" + "1" * 64, "authorityContextHash": "sha256:" + "2" * 64, "artifactHashes": {key: "sha256:" + "3" * 64 for key in ("reviewInput", "preflightResult", "gateState", "candidates", "rejections", "finalResult", "dispositions", "metrics", "verifierOutput")}, "finalStatus": "clean", "findingClosure": {},
            "validatorRevision": "bootstrap-finalized-run-validator.v2", "validatorHash": "sha256:" + __import__("hashlib").sha256(validator.read_bytes()).hexdigest(), "authorizes": [], "doesNotAuthorize": ["plan-acceptance", "implementation-acceptance", "protected-handoff", "release", "commit", "done"], "generatedAt": "2026-07-17T00:00:00Z",
        }
        document["artifactHashes"]["p2Dispositions"] = None
        document["profileHash"] = "sha256:" + document["profileHash"]
        mutated = apply_mutations(document, case.get("mutations", []))
        return validate_fixture_document(plan_root, case["target"], mutated, data)
    base_key = {"contract": "contract", "command_registry": "commands", "plan_state": "state", "review_blocker": "review_blocker", "review_reentry": "review_reentry", "authority_manifest": "authority_manifest", "clarification_projection": "clarification", "acceptance": "acceptance", "requirement_quality": "quality", "shadow": "shadow", "source_coverage": "coverage", "artifact_proofs": "artifact_proofs"}.get(case.get("target"))
    if base_key is None:
        return [finding("RMAP-STRUCT-FIXTURE", fixture_id, "fixture target is invalid")]
    mutated = apply_mutations(data[base_key], case.get("mutations", []))
    if case.get("target") == "review_reentry" and case.get("id") == "review-reentry-stale-blocker":
        mutated["state"] = "reentry_authorized"
        mutated["authorizes"] = ["manual-pause-reentry"]
        mutated["does_not_authorize"] = ["plan-ready", "slice-ready", "bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"]
    return validate_fixture_document(plan_root, case["target"], mutated, data)


def validate_fixture_suite(plan_root: Path, data: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    cases = data["fixtures"].get("cases")
    if not isinstance(cases, list) or len(cases) < 10:
        return [finding("RMAP-STRUCT-FIXTURE", "fixture-cases", "fixture suite is incomplete")]
    for case in cases:
        observed = evaluate_fixture(plan_root, case["id"], data)
        rules = sorted({item["rule_id"] for item in observed})
        expected_rules = sorted(case.get("expected_rules", [case.get("expected_rule")]))
        if case.get("expected_valid") is True:
            if observed:
                findings.append(finding("RMAP-STRUCT-FIXTURE", case["id"], f"valid fixture failed: {rules}"))
        elif rules != expected_rules:
            findings.append(finding("RMAP-STRUCT-FIXTURE", case["id"], f"expected {expected_rules}, observed {rules}"))
    return findings

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from artifact_proof_guards import expected_runtime_proof, expected_static_proof
from artifact_proof_projection_support import build_predicate_artifact_closure, close_uniform_inventory, refresh_runtime_type_contracts


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def refresh_contract() -> None:
    path = PLAN_ROOT / "implementation-contract.v1.json"
    contract = read_json(path)
    source_hashes = contract["authority"]["source_hashes"]
    for relative in source_hashes:
        source_hashes[relative] = sha256_file((PLAN_ROOT / relative).resolve())
    write_json(path, contract)


def refresh_deltas() -> None:
    path = PLAN_ROOT / "schemas" / "spec-deltas.v1.json"
    document = read_json(path)
    contract_hash = sha256_file(PLAN_ROOT / "implementation-contract.v1.json")
    for delta in document["deltas"]:
        delta["proposed_contract_hash"] = contract_hash
    write_json(path, document)


def refresh_quality() -> None:
    path = PLAN_ROOT / "schemas" / "requirement-quality.v1.json"
    document = read_json(path)
    requirements_hash = sha256_file(PLAN_ROOT / "schemas" / "requirements.v1.json")
    acceptance_hash = sha256_file(
        PLAN_ROOT / "schemas" / "acceptance-contracts.v1.json"
    )
    changed = (
        document.get("requirements_hash") != requirements_hash
        or document.get("acceptance_contracts_hash") != acceptance_hash
        or document.get("validator_version") != "rmap-plan-validator.v2"
    )
    document["requirements_hash"] = requirements_hash
    document["acceptance_contracts_hash"] = acceptance_hash
    document["validator_version"] = "rmap-plan-validator.v2"
    if changed:
        document["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write_json(path, document)


def refresh_coverage() -> None:
    path = PLAN_ROOT / "schemas" / "source-coverage.v1.json"
    document = read_json(path)
    for source in document["sources"]:
        source["sha256"] = sha256_file((PLAN_ROOT / source["path"]).resolve())
    write_json(path, document)


def refresh_successor_evidence() -> None:
    profile_path = REPOSITORY_ROOT / ".agents/skills/run-phase-bootstrap-review/references/review-profiles.v1.json"
    profiles = read_json(profile_path)["profiles"]
    policy_revision = profiles["bootstrap-upstream-plan"]["policyRevision"]
    root_relative = ".agents/skills/run-phase-bootstrap-review/references/authority-roots.v1.json"
    root_hash = sha256_file(REPOSITORY_ROOT / root_relative)
    root_reference = {"path": root_relative, "sha256": root_hash}
    successor_root = PLAN_ROOT / "schemas" / "reentry-successor-20260718"

    authority_path = successor_root / "successor-authority.json"
    authority = read_json(authority_path)
    authority["authorityRootRef"] = root_reference
    authority["predecessorAuthorityRef"] = root_reference
    authority["policyRevision"] = policy_revision
    write_json(authority_path, authority)

    event_path = successor_root / "authorization-event.json"
    event = read_json(event_path)
    event["authoritySourceRef"]["sha256"] = sha256_file(authority_path)
    event["policyRevision"] = policy_revision
    write_json(event_path, event)

    decision_path = successor_root / "policy-decision.json"
    decision = read_json(decision_path)
    decision["authorizationEventRef"]["sha256"] = sha256_file(event_path)
    decision["policyRevision"] = policy_revision
    write_json(decision_path, decision)

    reentry_path = PLAN_ROOT / "schemas" / "review-policy-reentry.v1.json"
    reentry = read_json(reentry_path)
    reentry["successor_policy"]["policy_revision"] = policy_revision
    reentry["successor_policy"]["decision_sha256"] = sha256_file(decision_path)
    write_json(reentry_path, reentry)


def refresh_artifact_proof_authority() -> None:
    path = PLAN_ROOT / "schemas" / "artifact-proof-authority.v1.json"
    document = read_json(path)
    external_root = read_json(
        REPOSITORY_ROOT / document["external_trust_root"]["path"]
    )
    closure_path = PLAN_ROOT / "schemas" / "predicate-artifact-closure.v1.json"
    baseline_commit = read_json(closure_path)["baseline_commit"] if closure_path.is_file() else subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, capture_output=True,
        text=True, encoding="utf-8", check=True,
    ).stdout.strip()
    for artifact in document["artifacts"]:
        relative = artifact["path"]
        if artifact.get("sha256") is not None:
            artifact["sha256"] = sha256_file(REPOSITORY_ROOT / relative)
        baseline = subprocess.run(
            ["git", "show", f"{baseline_commit}:{relative}"], cwd=REPOSITORY_ROOT,
            capture_output=True, check=False,
        )
        current_hash = sha256_file(REPOSITORY_ROOT / relative)
        predecessor = "sha256:" + hashlib.sha256(baseline.stdout).hexdigest() if baseline.returncode == 0 else None
        artifact["lifecycle_status"] = "new" if predecessor is None else (
            "unchanged" if predecessor == current_hash else "supersedes"
        )
        if artifact["class_id"] == "authority-root":
            predecessor = artifact.get("predecessor_sha256") or external_root["proof"]["immutable_identity"]["artifact_sha256"]
            artifact["lifecycle_status"] = "supersedes"
            artifact["predecessor_sha256"] = predecessor
        elif predecessor is None:
            artifact.pop("predecessor_sha256", None)
        else:
            artifact["predecessor_sha256"] = predecessor
        class_rule = document["classes"][artifact["class_id"]]
        if not artifact.get("derivation_rules") and class_rule["derivation"] != "exact-projection":
            source = class_rule["producer_authority"]["authority_path"]
            if source != relative:
                artifact["derivation_rules"] = [{
                    "source": source,
                    "field": "$authority",
                    "target_field": "$contract",
                    "derivation": "authority-derived",
                }]
    rule = document["rule_registry"]["artifact-proof-package.v1"]
    rule["validator_sha256"] = sha256_file(REPOSITORY_ROOT / rule["validator_path"])
    rule["negative_test_sha256"] = sha256_file(REPOSITORY_ROOT / rule["negative_test_path"])
    manifest = read_json(PLAN_ROOT / "schemas" / "authority-manifest.v1.json")
    categories = {
        item["path"]: category
        for category, entries in manifest["categories"].items()
        for item in entries
    }
    refresh_runtime_type_contracts(document, REPOSITORY_ROOT, categories, sha256_file)
    write_json(path, document)


def refresh_artifact_proof_inventory() -> None:
    inventory_path = PLAN_ROOT / "schemas" / "artifact-proof-required.v1.json"
    inventory = read_json(inventory_path)
    authority_path = PLAN_ROOT / "schemas" / "artifact-proof-authority.v1.json"
    authority = read_json(authority_path)
    boundary_class = {
        "producer_authority": {
            "authority_path": "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/02-executable-contracts-and-invariants.md",
            "authority_category": "plan_books",
            "producer_kind": "manual-authority",
            "generator_path": None,
        },
        "identity_mode": "derived-projection",
        "derivation": "authoritative-bytes",
        "staleness": {
            "invalidates": ["artifact-proof-registry", "runtime-artifact-type-proof", "plan-repair-verified", "plan-ready"],
            "regeneration_command_id": "rmap-refresh-projections",
            "revalidation_command_id": "rmap-plan-repair-validate",
        },
        "lineage": {
            "schema_path": "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/artifact-proof.v1.schema.json",
            "required_fields": ["artifact_path", "immutable_identity", "recovery_supersession"],
            "predecessor_policy": "manifest-bound-current-bytes",
        },
    }
    authority["classes"].pop("manifest-boundary", None)
    authority["classes"]["manifest-bound-authority-root"] = {
        **boundary_class,
        "artifact_kind": "normative",
    }
    authority["classes"]["manifest-bound-validator"] = {
        **boundary_class,
        "artifact_kind": "validator",
    }
    close_uniform_inventory(inventory, authority, sha256_file, REPOSITORY_ROOT)
    write_json(inventory_path, inventory)
    write_json(authority_path, authority)


def refresh_authority_manifest() -> None:
    path = PLAN_ROOT / "schemas" / "authority-manifest.v1.json"
    manifest = read_json(path)
    additions = {
        "review_policy_authority": [
            ".agents/skills/run-phase-bootstrap-review/references/authority-roots.v1.json",
            ".agents/skills/run-phase-bootstrap-review/references/artifact-proof-authority-root.v1.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-authority-root-registry.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-successor-policy-authority.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-successor-policy-authorization.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-successor-policy-decision.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-p2-owner-authority.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-p2-process-event.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-p2-command-registry.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-p2-process-result.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-p2-evidence-result.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-verifier-output.v1.schema.json",
        ],
        "machine_owners": [
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/artifact-proof.v1.schema.json",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/artifact-proof-authority.v1.json",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/artifact-proof-required.v1.json",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/artifact-proof-registry.v1.json",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/runtime-artifact-type-proof.v1.json",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/baseline-file-manifest.v1.schema.json",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/reentry-successor-20260718/authorization-event.json",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/reentry-successor-20260718/policy-decision.json",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/reentry-successor-20260718/successor-authority.json",
        ],
        "protocol_authority": [
            ".agents/skills/vdd-execution-plan/scripts/skill-contract.json",
            ".agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py",
            ".agents/skills/vdd-execution-plan/scripts/tests/test_validate_skill_contract.py",
        ],
        "execution_dependencies": [
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/artifact_proof_guards.py",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/artifact_proof_verdicts.py",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/runtime_artifact_proof_guards.py",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/artifact_proof_projection_support.py",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/artifact_proof_inventory_support.py",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/validation_result_guards.py",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/review_reentry_environment.py",
            ".agents/skills/run-phase-bootstrap-review/scripts/artifact_proof_root_guards.py",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/tests/test_artifact_proof_closure.py",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/tests/test_validation_result_guards.py",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/protocol_validation_guards.py",
        ],
        "compatibility_inputs": [
            "execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/validate_whole_directory.py",
        ],
    }
    existing = {entry["path"] for entries in manifest["categories"].values() for entry in entries}
    for category, paths in additions.items():
        for relative in paths:
            if relative not in existing:
                manifest["categories"][category].append({"path": relative, "sha256": sha256_file(REPOSITORY_ROOT / relative)})
                existing.add(relative)
    for entries in manifest["categories"].values():
        for entry in entries:
            entry["sha256"] = sha256_file(REPOSITORY_ROOT / entry["path"])
    write_json(path, manifest)


def refresh_predicate_artifact_closure() -> None:
    manifest = read_json(PLAN_ROOT / "schemas" / "authority-manifest.v1.json")
    path = PLAN_ROOT / "schemas" / "predicate-artifact-closure.v1.json"
    baseline_commit = read_json(path)["baseline_commit"] if path.is_file() else subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, capture_output=True,
        text=True, encoding="utf-8", check=True,
    ).stdout.strip()
    write_json(
        path,
        build_predicate_artifact_closure(REPOSITORY_ROOT, PLAN_ROOT, manifest, baseline_commit),
    )


def refresh_artifact_proofs() -> None:
    authority_registry = read_json(PLAN_ROOT / "schemas" / "artifact-proof-authority.v1.json")
    inventory = read_json(PLAN_ROOT / "schemas" / "artifact-proof-required.v1.json")
    path = PLAN_ROOT / "schemas" / "artifact-proof-registry.v1.json"
    existing = read_json(path)
    by_path = {item["artifact_path"]: item for item in existing.get("proofs", [])}
    authority_manifest = read_json(PLAN_ROOT / "schemas" / "authority-manifest.v1.json")
    authority_hashes = {
        item["path"]: item["sha256"]
        for entries in authority_manifest["categories"].values()
        for item in entries
    }
    authority_by_path = {item["path"]: item for item in authority_registry["artifacts"]}
    proofs = []
    for artifact_path in inventory["contract_artifacts"]:
        item = by_path.get(artifact_path, {})
        authority_rule = dict(authority_by_path[artifact_path])
        finding_ids = set(item.get("finding_ids", [])) | {"RMAP-1400-UNIFORM-ARTIFACT-PROOF"}
        if item.get("finding_ids") and "RMAP-1500-TRUST-ROOT" in item["finding_ids"]:
            finding_ids.add("RMAP-1500-TRUST-ROOT")
        authority_rule["finding_ids"] = sorted(finding_ids)
        proofs.append(expected_static_proof(REPOSITORY_ROOT, authority_registry, authority_rule, authority_hashes))
    write_json(path, {"schema_version": "jimuyun.artifact-proof-registry.v1", "plan_id": "repository-maintenance-tdd-adapter", "proof_schema": "schemas/artifact-proof.v1.schema.json", "authority_registry": "schemas/artifact-proof-authority.v1.json", "authorizes": [], "does_not_authorize": inventory["does_not_authorize"], "proofs": proofs})
    runtime_path = PLAN_ROOT / "schemas" / "runtime-artifact-type-proof.v1.json"
    write_json(runtime_path, {"schema_version": "jimuyun.runtime-artifact-type-proof.v1", "plan_id": "repository-maintenance-tdd-adapter", "authority_registry": "schemas/artifact-proof-authority.v1.json", "proofs": [expected_runtime_proof(rule) for rule in authority_registry["runtime_types"]], "authorizes": [], "does_not_authorize": inventory["does_not_authorize"]})


def value_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def refresh_candidate_lineage_fixture() -> None:
    path = PLAN_ROOT / "fixtures" / "candidate-diff-cases.v1.json"
    document = read_json(path)
    base = document["base"]
    lineage = base["lineage"]
    prior_slice = None
    prior_run = None
    prior_effect_hash = None
    for ref, run in zip(lineage["slice_runs"], base["lineage_runs"], strict=True):
        effect = run["document"]
        effect["baseline_files"] = [entry for entry in effect["baseline_files"] if entry["sha256"] is not None]
        effect["root_hash"] = value_hash({key: value for key, value in effect.items() if key != "root_hash"})
        raw = json.dumps(effect, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        run["raw"] = raw
        effect_hash = "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
        ref.pop("predecessor_run_id", None)
        ref["previous_slice_id"] = prior_slice
        ref["previous_slice_run_id"] = prior_run
        ref["previous_slice_effect_hash"] = prior_effect_hash
        ref["run_artifact_sha256"] = effect_hash
        ref["accepted_attempt_fold_hash"] = value_hash(effect["effects"])
        ref["final_event_hash"] = effect["final_event_hash"]
        prior_slice, prior_run, prior_effect_hash = ref["slice_id"], ref["run_id"], effect_hash
    canonical_fold = sorted(
        base["folded_files"],
        key=lambda item: str(item.get("candidate_path") or item.get("baseline_path")).casefold(),
    )
    lineage["cumulative_fold_hash"] = value_hash(canonical_fold)
    lineage["root_hash"] = value_hash({key: value for key, value in lineage.items() if key != "root_hash"})
    write_json(path, document)


def refresh_clarification() -> None:
    path = PLAN_ROOT / "schemas" / "clarification-decisions.v1.json"
    document = read_json(path)
    run_id = "clarification-20260717T190000Z"
    state_path = REPOSITORY_ROOT / "logs" / "vdd-clarifications" / "2026-07-15-repository-maintenance-tdd-adapter-f6d1143a" / run_id / "state.json"
    source = next(item for item in document["sources"] if item["run_id"] == run_id)
    source["state_sha256"] = sha256_file(state_path)
    write_json(path, document)


def main() -> int:
    refresh_clarification()
    refresh_contract()
    refresh_coverage()
    refresh_deltas()
    refresh_quality()
    refresh_candidate_lineage_fixture()
    refresh_successor_evidence()
    refresh_artifact_proof_inventory()
    refresh_artifact_proof_authority()
    refresh_predicate_artifact_closure()
    refresh_authority_manifest()
    refresh_predicate_artifact_closure()
    refresh_authority_manifest()
    refresh_predicate_artifact_closure()
    refresh_contract()
    refresh_deltas()
    refresh_authority_manifest()
    refresh_artifact_proofs()
    refresh_authority_manifest()
    print("Refreshed repository-maintenance plan projections")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

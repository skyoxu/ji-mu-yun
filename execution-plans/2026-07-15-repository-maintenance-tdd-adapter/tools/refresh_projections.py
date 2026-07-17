from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def refresh_authority_manifest() -> None:
    path = PLAN_ROOT / "schemas" / "authority-manifest.v1.json"
    manifest = read_json(path)
    additions = {
        "review_policy_authority": [
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-successor-policy-authority.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-successor-policy-authorization.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-successor-policy-decision.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-p2-owner-authority.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-p2-command-registry.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-p2-process-result.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-p2-evidence-result.v1.schema.json",
            ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-verifier-output.v1.schema.json",
        ],
        "machine_owners": [
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/artifact-proof.v1.schema.json",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/artifact-proof-required.v1.json",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/artifact-proof-registry.v1.json",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/runtime-artifact-type-proof.v1.json",
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/baseline-file-manifest.v1.schema.json",
        ],
        "execution_dependencies": [
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/artifact_proof_guards.py",
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


def refresh_artifact_proofs() -> None:
    inventory = read_json(PLAN_ROOT / "schemas" / "artifact-proof-required.v1.json")
    path = PLAN_ROOT / "schemas" / "artifact-proof-registry.v1.json"
    existing = read_json(path)
    by_path = {item["artifact_path"]: item for item in existing.get("proofs", [])}
    exclusions = inventory["does_not_authorize"]
    proofs = []
    for artifact_path in inventory["contract_artifacts"]:
        item = by_path.get(artifact_path, {})
        bootstrap_owned = artifact_path.startswith(".agents/skills/run-phase-bootstrap-review/")
        producer = ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py" if bootstrap_owned else "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/02-executable-contracts-and-invariants.md"
        validator = "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/artifact_proof_guards.py"
        proofs.append({
            "artifact_path": artifact_path,
            "artifact_kind": item.get("artifact_kind", "normative" if artifact_path.endswith((".json", ".schema.json")) else "validator"),
            "finding_ids": sorted(set(item.get("finding_ids", [])) | {"RMAP-1400-UNIFORM-ARTIFACT-PROOF"}),
            "schema_producer_authority": {"producer_path": producer, "authority_owner": "Bootstrap control-plane owner" if bootstrap_owned else "repository-maintenance plan contract owner"},
            "immutable_identity": {"algorithm": "sha256-bytes", "manifest_path": "schemas/authority-manifest.v1.json"},
            "source_of_truth_derivation": {"source_paths": [producer], "projection_only": artifact_path.endswith(".v1.json") and "schema.json" not in artifact_path},
            "independent_recomputation": {"validator_path": validator, "rule_ids": ["RMAP-ARTIFACT-PROOF"]},
            "staleness_propagation": {"input_paths": [producer], "invalidates": ["artifact-proof-registry", "plan-repair-verified"]},
            "recovery_supersession": {"history_policy": "append-only-successor-no-rewrite", "lineage_fields": ["artifact_path", "finding_ids"]},
            "consumer_authorization_boundary": {"consumers": ["composite plan validator"], "predicate": "artifact-contract-proof", "authorizes": [], "does_not_authorize": exclusions},
        })
    write_json(path, {"schema_version": "jimuyun.artifact-proof-registry.v1", "plan_id": "repository-maintenance-tdd-adapter", "proof_schema": "schemas/artifact-proof.v1.schema.json", "proofs": proofs})


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
    refresh_artifact_proofs()
    refresh_authority_manifest()
    refresh_contract()
    refresh_deltas()
    refresh_authority_manifest()
    print("Refreshed repository-maintenance plan projections")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

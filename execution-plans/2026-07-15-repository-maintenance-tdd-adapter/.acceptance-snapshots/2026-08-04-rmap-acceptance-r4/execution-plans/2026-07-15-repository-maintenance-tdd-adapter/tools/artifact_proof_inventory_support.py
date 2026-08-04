from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


FAILURE_IDS = [
    "RMAP-ARTIFACT-PROOF-PRODUCER",
    "RMAP-ARTIFACT-PROOF-IDENTITY",
    "RMAP-ARTIFACT-PROOF-DERIVATION",
    "RMAP-ARTIFACT-PROOF-RULE",
    "RMAP-ARTIFACT-PROOF-STALENESS",
    "RMAP-ARTIFACT-PROOF-LINEAGE",
    "RMAP-ARTIFACT-PROOF-CONSUMER",
]

CONSUMER_ENTRYPOINTS = {
    "validation-result-instance": {
        "composite plan validator": (
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/validation_result_guards.py",
            "validate_authorizing_result",
        ),
    },
    "bootstrap-finalized-run-instance": {
        "S7 acceptance validator": (".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py", "validate_finalized_run_evidence"),
        "plan reentry validator": ("execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/authority_guards.py", "validate_review_reentry"),
    },
    "bootstrap-p2-disposition-instance": {
        "Bootstrap finalize": (".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py", "validate_finalized_run_evidence"),
        "S7 acceptance validator": (".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py", "validate_p2_dispositions"),
    },
    "bootstrap-p2-process-event-instance": {
        "Bootstrap P2 disposition validator": (".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py", "validate_p2_dispositions"),
    },
    "bootstrap-successor-authorization-instance": {
        "plan reentry validator": ("execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/authority_guards.py", "validate_review_reentry"),
    },
    "candidate-lineage-instance": {
        "S6 candidate validator": ("execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/candidate_diff_guards.py", "validate_candidate_diff"),
    },
    "review-policy-reentry-instance": {
        "plan-state validator": ("execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/authority_guards.py", "validate_review_reentry"),
    },
}


def refresh_runtime_type_contracts(
    document: dict[str, Any], repository_root: Path, categories: dict[str, str],
    sha256_file: Callable[[Path], str],
) -> None:
    for runtime_type in document["runtime_types"]:
        schema_path = runtime_type["schema_path"]
        producer = runtime_type["schema_producer_authority"]
        if isinstance(producer, str):
            producer = {"authority_path": producer, "authority_category": categories[producer]}
            runtime_type["schema_producer_authority"] = producer
        producer["authority_sha256"] = sha256_file(repository_root / producer["authority_path"])
        identity_fields = runtime_type.pop("immutable_identity_fields", runtime_type.get("immutable_identity", {}).get("identity_fields", []))
        runtime_type["immutable_identity"] = {
            "schema_path": schema_path,
            "schema_sha256": sha256_file(repository_root / schema_path),
            "algorithm": "sha256-canonical-json-fields",
            "identity_fields": identity_fields,
        }
        derivation = runtime_type["source_of_truth_derivation"]
        if isinstance(derivation, list):
            runtime_type["source_of_truth_derivation"] = {
                "rules": [{"source": source, "derivation": "validator-resolved-runtime-input"} for source in derivation]
            }
        recomputation = runtime_type["independent_recomputation"]
        recomputation["validator_sha256"] = sha256_file(repository_root / recomputation["validator"])
        recomputation["negative_test_sha256"] = sha256_file(repository_root / recomputation["negative_test"])
        recomputation["expected_failure_ids"] = FAILURE_IDS
        stale = runtime_type["staleness_propagation"]
        if isinstance(stale, list):
            runtime_type["staleness_propagation"] = {
                "inputs": [schema_path, recomputation["validator"], recomputation["negative_test"]],
                "invalidates": stale,
                "propagation_mode": "fail-closed-before-predicate",
                "revalidation_command_id": "rmap-plan-repair-validate",
            }
        recovery = runtime_type["recovery_supersession"]
        if isinstance(recovery, list):
            runtime_type["recovery_supersession"] = {
                "history_policy": "append-only-successor-no-rewrite",
                "lineage_fields": recovery,
                "predecessor_policy": "schema-required-lineage-or-explicit-null",
            }
        boundary = runtime_type["consumer_authorization_boundary"]
        boundary["consumer_entrypoints"] = [{
            "consumer": consumer,
            "validator": CONSUMER_ENTRYPOINTS[runtime_type["type_id"]][consumer][0],
            "callable": CONSUMER_ENTRYPOINTS[runtime_type["type_id"]][consumer][1],
            "failure_mode": "block-predicate-on-any-dimension-failure",
        } for consumer in boundary["consumers"]]


def close_uniform_inventory(
    inventory: dict[str, Any], authority: dict[str, Any],
    sha256_file: Callable[[Path], str], repository_root: Path,
) -> None:
    formal = inventory["contract_artifacts"]
    external_trust_inputs = {
        ".agents/skills/run-phase-bootstrap-review/references/artifact-proof-authority-root.v1.json",
        ".agents/skills/run-phase-bootstrap-review/scripts/artifact_proof_root_guards.py",
    }
    # The root and its verifier are an external, protected input pair. Including
    # either in this plan's generated authority package makes rotation recursive.
    formal[:] = [relative for relative in formal if relative not in external_trust_inputs]
    authority["artifacts"] = [
        item for item in authority["artifacts"] if item["path"] not in external_trust_inputs
    ]
    for relative in inventory.pop("provisional_diagnostic_artifacts", []):
        if relative not in formal:
            formal.append(relative)
    inventory["predicate_authority"]["manual-pause-reentry"] = {
        "authorizes": ["manual-pause-reentry"],
        "does_not_authorize": ["plan-ready", "slice-ready", "bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"],
    }
    inventory["predicate_authority"]["validation-result"] = {
        "authorizes": [],
        "does_not_authorize": ["plan-repair-verified", "plan-ready", "slice-ready", "bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"],
    }
    if "composite plan validator" not in inventory["registered_consumers"]:
        inventory["registered_consumers"].append("composite plan validator")
    if "validation-result-instance" not in inventory["runtime_types"]:
        inventory["runtime_types"].append("validation-result-instance")
    runtime_by_type = {item["type_id"]: item for item in authority["runtime_types"]}
    runtime_by_type["validation-result-instance"] = {
        "type_id": "validation-result-instance",
        "schema_path": "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/validation-result.v1.schema.json",
        "schema_producer_authority": "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/02-executable-contracts-and-invariants.md",
        "source_of_truth_derivation": ["predicate-artifact-closure", "authority-manifest", "validator-identity", "runtime-evidence-arguments", "predicate-authority-lattice"],
        "independent_recomputation": {
            "validator": "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/validation_result_guards.py",
            "callable": "validate_authorizing_result",
            "negative_test": "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/tests/test_validation_result_guards.py",
            "rule_ids": ["RMAP-RESULT-STALE", "RMAP-RESULT-AUTHORITY", "RMAP-RESULT-LINEAGE"],
        },
        "staleness_propagation": ["plan-repair-verified", "plan-ready", "slice-ready", "implementation-candidate", "implementation-accepted"],
        "recovery_supersession": {
            "history_policy": "append-only-successor-no-rewrite",
            "lineage_fields": [
                "lineage_mode", "lineage_reason_code", "predecessor_run_id",
                "supersedes_run_id", "predecessor_result_hash",
            ],
            "predecessor_policy": "initial-explicit-null-or-successor-recomputed-envelope",
            "reason_codes": [
                "INITIAL_RUN_NO_PREDECESSOR", "SUPERSEDES_PRIOR_RESULT",
            ],
        },
        "consumer_authorization_boundary": {
            "consumers": ["composite plan validator"], "predicate": "validation-result", "authorizes": [],
            "does_not_authorize": inventory["predicate_authority"]["validation-result"]["does_not_authorize"],
        },
        "immutable_identity_fields": [
            "predicate", "candidate_hash", "current_candidate_hash", "source_hash", "validator_version",
            "predicate_input_root", "closure_definition_hash", "authority_root", "validator_root",
            "runtime_evidence_root", "run_id", "lineage_mode", "lineage_reason_code",
            "predecessor_run_id", "supersedes_run_id", "predecessor_result_hash",
            "authorizes", "does_not_authorize",
        ],
    }
    authority["runtime_types"] = [runtime_by_type[key] for key in sorted(runtime_by_type)]
    by_path = {item["path"]: item for item in authority["artifacts"]}
    boundary_classes = {
        "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/runtime_artifact_proof_guards.py": "manifest-bound-validator",
        "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/artifact_proof_projection_support.py": "manifest-bound-validator",
        "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/artifact_proof_inventory_support.py": "manifest-bound-validator",
        "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/validation_result_guards.py": "manifest-bound-validator",
    }
    for relative, class_id in boundary_classes.items():
        if relative not in formal:
            formal.append(relative)
        item = by_path.setdefault(relative, {"path": relative})
        item["class_id"] = class_id
        item["sha256"] = None
    predicates = {"successor-policy-authorization": ["plan reentry validator"], "manual-pause-reentry": ["plan-state validator"]}
    reentry_paths = {
        "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/reentry-successor-20260718/successor-authority.json": "successor-policy-authorization",
        "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/reentry-successor-20260718/authorization-event.json": "successor-policy-authorization",
        "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/reentry-successor-20260718/policy-decision.json": "successor-policy-authorization",
        "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/review-policy-reentry.v1.json": "manual-pause-reentry",
    }
    for relative, predicate in reentry_paths.items():
        permission = inventory["predicate_authority"][predicate]
        by_path[relative]["proof_scope"] = "authorization-participating"
        by_path[relative]["consumer_authorization_boundary"] = {
            "consumers": predicates[predicate], "predicate": predicate,
            "authorizes": permission["authorizes"], "does_not_authorize": permission["does_not_authorize"],
        }
    authority["artifacts"] = [by_path[relative] for relative in formal]
    reentry = next(item for item in authority["runtime_types"] if item["type_id"] == "review-policy-reentry-instance")
    reentry["consumer_authorization_boundary"] = {
        "consumers": ["plan-state validator"], "predicate": "manual-pause-reentry",
        "authorizes": ["manual-pause-reentry"],
        "does_not_authorize": inventory["predicate_authority"]["manual-pause-reentry"]["does_not_authorize"],
    }

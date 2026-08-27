"""Publish a plan-scoped authorization for high-velocity TDD."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    return {"path": resolved.relative_to(ROOT.resolve()).as_posix(), "sha256": digest(resolved)}


def reference_is_current(reference: object) -> bool:
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        return False
    path = reference.get("path")
    expected = reference.get("sha256")
    if not isinstance(path, str) or not isinstance(expected, str) or not expected.startswith("sha256:"):
        return False
    target = (ROOT / path).resolve()
    try:
        target.relative_to(ROOT.resolve())
    except ValueError:
        return False
    return target.is_file() and ref(target) == reference


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-input", type=Path, required=True)
    parser.add_argument("--review-run", type=Path, required=True)
    parser.add_argument("--review-binding", type=Path, required=True)
    parser.add_argument("--conformance", type=Path, required=True)
    args = parser.parse_args()

    review_input, review_path, binding_path, conformance_path = (
        value.resolve()
        for value in (args.review_input, args.review_run, args.review_binding, args.conformance)
    )
    review = json.loads(review_path.read_text(encoding="utf-8"))
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    conformance = json.loads(conformance_path.read_text(encoding="utf-8"))
    input_value = json.loads(review_input.read_text(encoding="utf-8"))

    if (
        review.get("schema_version") != "vdd-review-run.v1"
        or review.get("status") != "accepted"
        or review.get("decision") != "accepted"
        or review.get("authorizes") != []
    ):
        raise SystemExit("accepted external review is required")
    if (
        conformance.get("status") != "conformant"
        or conformance.get("errors") != []
        or conformance.get("authorizes") != []
    ):
        raise SystemExit("conformant conformance result is required")

    refs = {
        "review_input": ref(review_input),
        "review_run": ref(review_path),
        "review_candidate_binding": ref(binding_path),
        "conformance_result": ref(conformance_path),
        "implementation_contract": ref(PLAN / "implementation-contract.v1.json"),
        "command_registry": ref(PLAN / "command-registry.v1.json"),
        "source_freeze": input_value.get("source_freeze"),
        "requirements_mapping": input_value.get("requirements_mapping"),
    }
    candidate = input_value.get("candidate")
    required_bindings = input_value.get("required_review_bindings")
    if (
        input_value.get("schema_version") != "vdd-external-semantic-review-input.v1"
        or input_value.get("required_output") != "vdd-review-run.v1"
        or input_value.get("authorizes") != []
        or not isinstance(candidate, dict)
        or not isinstance(candidate.get("head_commit"), str)
        or not candidate["head_commit"]
        or candidate.get("implementation_contract") != refs["implementation_contract"]
        or candidate.get("command_registry") != refs["command_registry"]
        or not isinstance(required_bindings, dict)
        or not reference_is_current(refs["source_freeze"])
        or not reference_is_current(refs["requirements_mapping"])
    ):
        raise SystemExit("external review input is stale")

    review_binding_fields = (
        "semantic_handoff_hash",
        "source_manifest_hash",
        "requirements_manifest_hash",
        "ambiguity_ids",
        "affected_requirement_ids",
    )
    if (
        review.get("profile") != input_value.get("profile")
        or any(review.get(field) != required_bindings.get(field) for field in review_binding_fields)
        or conformance.get("source_manifest_hash") != required_bindings.get("source_manifest_hash")
        or conformance.get("requirements_manifest_hash") != required_bindings.get("requirements_manifest_hash")
    ):
        raise SystemExit("external semantic review does not match its published input")

    external_refs = {
        key: refs[key]
        for key in (
            "review_input",
            "review_run",
            "conformance_result",
            "source_freeze",
            "requirements_mapping",
            "implementation_contract",
            "command_registry",
        )
    }
    if (
        binding.get("schema_version") != "vdd-review-candidate-binding.v1"
        or binding.get("status") != "accepted"
        or binding.get("decision") != "accepted"
        or binding.get("candidate_commit") != candidate.get("head_commit")
        or any(binding.get(key) != value for key, value in external_refs.items())
    ):
        raise SystemExit("semantic review binding is stale")

    value = {
        "schema_version": "quick-dev-tdd-adapter.implementation-authorization.v3",
        "plan_id": "vdd-quick-dev-semantic-oracle-recovery",
        "scope": "whole_plan",
        "mode": "high_velocity_tdd",
        **refs,
        "authority_manifest": ref(PLAN / "knowledge-context.freeze.v1.json"),
        "decision": {
            "owner": "maintainer",
            "transition": "implementation-authorized",
            "basis": "accepted semantic review for plan-scoped high-velocity TDD",
        },
        "binds": [
            "plan_id",
            "requirements_mapping",
            "source_freeze",
            "implementation_contract",
            "command_registry",
            "authority_manifest",
        ],
        "does_not_bind": ["candidate_commit", "implementation_source_hashes", "run_evidence"],
        "authorizes": ["implementation-authorized"],
    }
    out = PLAN / "implementation-authorization-receipt.v3.json"
    out.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    previous_state = json.loads((PLAN / "plan-state.v1.json").read_text(encoding="utf-8"))
    state = {
        "schema_version": "vdd.lifecycle.v2",
        "plan_id": "vdd-quick-dev-semantic-oracle-recovery",
        "state": "implementation-authorized",
        "owner": "maintainer",
        "profile": "self-hosted",
        "authorization_scope": "whole_plan",
        "mode": "high_velocity_tdd",
        "canonical_selection_hash": previous_state["canonical_selection_hash"],
        "authorization_receipt": ref(out),
        "authorizes": ["implementation-authorized"],
    }
    (PLAN / "plan-state.v1.json").write_text(
        json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


FIXTURE_PATH = Path("scripts/fixtures/artifact-proof-root-policy-pass.json")
AUTHORITY_PATH = ".agents/skills/vdd-execution-plan/references/strict-vdd-standard.md"
AUTHORITY_FILE = Path("references/strict-vdd-standard.md")
AUTHORITY_SHA256 = "sha256:6c640256b59b5bd400dd0104698a7b300538543371c9fa48d69cdfca6b932b72"
VALIDATOR_PATH = ".agents/skills/vdd-execution-plan/scripts/artifact_proof_compat.py"
NEGATIVE_TEST_PATH = ".agents/skills/vdd-execution-plan/scripts/tests/test_artifact_proof_compat.py"
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
DIMENSIONS = (
    "schema_producer_authority",
    "immutable_identity",
    "source_of_truth_derivation",
    "independent_recomputation",
    "staleness_propagation",
    "recovery_supersession",
    "consumer_authorization_boundary",
)
FAILURE_IDS = (
    "VDD-ARTIFACT-PROOF-PRODUCER",
    "VDD-ARTIFACT-PROOF-IDENTITY",
    "VDD-ARTIFACT-PROOF-DERIVATION",
    "VDD-ARTIFACT-PROOF-RULE",
    "VDD-ARTIFACT-PROOF-STALENESS",
    "VDD-ARTIFACT-PROOF-LINEAGE",
    "VDD-ARTIFACT-PROOF-CONSUMER",
    "VDD-ARTIFACT-PROOF-APPLICABILITY",
)
REQUIRED_FIELDS = (
    "artifact_path",
    "artifact_kind",
    "proof_scope",
    "finding_ids",
    "dimension_verdicts",
    *DIMENSIONS,
)
INVALIDATES = (
    "artifact-proof-registry",
    "runtime-artifact-type-proof",
    "plan-repair-verified",
    "plan-ready",
)
EXCLUSIONS = (
    "plan-ready",
    "slice-ready",
    "bootstrap-review",
    "implementation-accepted",
    "protected-handoff",
    "release-ready",
)


def _finding(rule_id: str, detail: str) -> dict[str, str]:
    return {"rule_id": rule_id, "target": FIXTURE_PATH.as_posix(), "detail": detail}


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_relative(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "." not in path.parts


def validate_artifact_proof_trust_roots(
    skill_root: Path,
    proof: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    if proof is None:
        try:
            fixture = json.loads((skill_root / FIXTURE_PATH).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            return [_finding(FAILURE_IDS[0], "the detached artifact-proof fixture is unreadable")]
        if (
            not isinstance(fixture, dict)
            or fixture.get("schema_version") != "vdd.artifact-proof-root-fixture.v1"
            or not isinstance(fixture.get("proof"), dict)
        ):
            return [_finding(FAILURE_IDS[0], "the detached artifact-proof fixture is invalid")]
        proof = fixture["proof"]

    if set(proof) != set(REQUIRED_FIELDS):
        return [_finding(FAILURE_IDS[0], "the complete artifact-proof template is required")]
    verdicts = proof.get("dimension_verdicts")
    if (
        proof.get("proof_scope") != "static-contract"
        or not isinstance(verdicts, dict)
        or set(verdicts) != set(DIMENSIONS)
        or any(
            verdicts.get(dimension) != {
                "status": "PASS",
                "evidence_rule_ids": [
                    {
                        "schema_producer_authority": "ARTIFACT-PROOF-PRODUCER",
                        "immutable_identity": "ARTIFACT-PROOF-IDENTITY",
                        "source_of_truth_derivation": "ARTIFACT-PROOF-DERIVATION",
                        "independent_recomputation": "ARTIFACT-PROOF-RULE",
                        "staleness_propagation": "ARTIFACT-PROOF-STALENESS",
                        "recovery_supersession": "ARTIFACT-PROOF-LINEAGE",
                        "consumer_authorization_boundary": "ARTIFACT-PROOF-CONSUMER",
                    }[dimension]
                ],
            }
            for dimension in DIMENSIONS
        )
    ):
        return [_finding(FAILURE_IDS[7], "complete executable PASS verdicts are required")]

    producer = proof["schema_producer_authority"]
    if (
        not _safe_relative(proof.get("artifact_path"))
        or proof.get("artifact_kind") != "normative"
        or not isinstance(proof.get("finding_ids"), list)
        or not proof["finding_ids"]
        or producer
        != {
            "authority_path": AUTHORITY_PATH,
            "authority_category": "protocol_authority",
            "authority_sha256": AUTHORITY_SHA256,
            "producer_kind": "manual-authority",
            "generator_path": None,
            "generator_sha256": None,
        }
        or _sha256(skill_root / AUTHORITY_FILE) != AUTHORITY_SHA256
    ):
        return [_finding(FAILURE_IDS[0], "the producer authority is not current")]

    identity = proof["immutable_identity"]
    if (
        set(identity) != {"mode", "algorithm", "artifact_sha256", "authority_revision", "manifest_path"}
        or identity.get("mode") != "semantic-root-policy"
        or identity.get("algorithm") != "vdd-root-policy-v1"
        or identity.get("artifact_sha256") is not None
        or not isinstance(identity.get("authority_revision"), str)
        or not identity["authority_revision"]
        or not _safe_relative(identity.get("manifest_path"))
    ):
        return [_finding(FAILURE_IDS[1], "the semantic root identity is invalid")]

    expected_input = {
        "source": AUTHORITY_PATH,
        "source_sha256": AUTHORITY_SHA256,
        "field": "/3-authority-intent-kernels-and-executable-contracts",
        "target_field": "$policy",
        "derivation": "semantic-policy-reference",
    }
    if proof["source_of_truth_derivation"] != {"rules": [expected_input]}:
        return [_finding(FAILURE_IDS[2], "the semantic authority derivation is invalid")]

    recomputation = proof["independent_recomputation"]
    validator_file = skill_root / "scripts" / "artifact_proof_compat.py"
    negative_test_file = skill_root / "scripts" / "tests" / "test_artifact_proof_compat.py"
    if (
        set(recomputation)
        != {"rule_id", "validator_path", "validator_sha256", "callable", "negative_test_path", "negative_test_sha256", "expected_failure_ids"}
        or recomputation.get("rule_id")
        not in {
            "vdd-skill-artifact-proof-root-policy.v1",
            "vdd-skill-artifact-proof-trust-root.v1",
        }
        or recomputation.get("validator_path") != VALIDATOR_PATH
        or recomputation.get("validator_sha256") != _sha256(validator_file)
        or recomputation.get("callable") != "validate_artifact_proof_trust_roots"
        or recomputation.get("negative_test_path") != NEGATIVE_TEST_PATH
        or recomputation.get("negative_test_sha256") != _sha256(negative_test_file)
        or recomputation.get("expected_failure_ids") != list(FAILURE_IDS)
    ):
        return [_finding(FAILURE_IDS[3], "the compatibility recomputation identity is stale")]

    stale = proof["staleness_propagation"]
    if (
        set(stale) != {"inputs", "invalidates", "regeneration_command_id", "revalidation_command_id"}
        or stale.get("inputs") != [expected_input]
        or stale.get("invalidates") != list(INVALIDATES)
        or not isinstance(stale.get("regeneration_command_id"), str)
        or not stale["regeneration_command_id"]
        or not isinstance(stale.get("revalidation_command_id"), str)
        or not stale["revalidation_command_id"]
    ):
        return [_finding(FAILURE_IDS[4], "the staleness closure is invalid")]

    recovery = proof["recovery_supersession"]
    if (
        set(recovery)
        != {"history_policy", "schema_path", "lineage_fields", "predecessor_policy", "lifecycle_status", "predecessor_sha256"}
        or recovery.get("history_policy") != "append-only-successor-no-rewrite"
        or not _safe_relative(recovery.get("schema_path"))
        or recovery.get("lineage_fields") != ["artifact_path", "immutable_identity", "recovery_supersession"]
        or recovery.get("predecessor_policy") != "external-vdd-skill-contract-revision"
        or recovery.get("lifecycle_status") != "supersedes"
        or not HASH_PATTERN.fullmatch(str(recovery.get("predecessor_sha256")))
    ):
        return [_finding(FAILURE_IDS[5], "the append-only predecessor lineage is invalid")]

    boundary = proof["consumer_authorization_boundary"]
    if (
        set(boundary) != {"consumers", "predicate", "authorizes", "does_not_authorize"}
        or not isinstance(boundary.get("consumers"), list)
        or not boundary["consumers"]
        or any(not isinstance(item, str) or not item for item in boundary["consumers"])
        or boundary.get("predicate") != "artifact-contract-proof"
        or boundary.get("authorizes") != []
        or boundary.get("does_not_authorize") != list(EXCLUSIONS)
    ):
        return [_finding(FAILURE_IDS[6], "the zero-authority consumer lattice is invalid")]
    return []

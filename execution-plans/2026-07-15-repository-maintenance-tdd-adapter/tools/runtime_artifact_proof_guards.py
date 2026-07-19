from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _callable_exists(path: Path, callable_name: str) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError):
        return False
    return any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == callable_name for node in tree.body)


def _schema_requires(schema: dict[str, Any], dotted_path: str) -> bool:
    current = schema
    for part in dotted_path.split("."):
        if part not in current.get("required", []):
            return False
        child = current.get("properties", {}).get(part)
        if not isinstance(child, dict):
            return False
        if "$ref" in child:
            ref = child["$ref"]
            if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
                return False
            child = schema.get("$defs", {}).get(ref.removeprefix("#/$defs/"), {})
        current = child
    return True


def validate_runtime_type_proof(
    repository_root: Path,
    proof: dict[str, Any],
    rule: dict[str, Any],
    authority_hashes: dict[str, str],
    authority_categories: dict[str, str],
    predicates: dict[str, Any],
    registered_consumers: list[str],
    expected_runtime_proof: Callable[[dict[str, Any]], dict[str, Any]],
    verdict_findings: Callable[[dict[str, Any], str], list[dict[str, str]]],
    dimension_rules: dict[str, str],
    command_ids: set[str],
) -> list[dict[str, str]]:
    type_id = str(rule.get("type_id", proof.get("type_id", "runtime-artifact-type")))
    finding = lambda dimension, message: [{"rule_id": dimension_rules[dimension], "target": type_id, "message": message}]
    verdict_errors = verdict_findings(proof, type_id)
    if proof.get("artifact_role") != "authorization-participating" or verdict_errors:
        return verdict_errors or [{"rule_id": "RMAP-ARTIFACT-PROOF-APPLICABILITY", "target": type_id, "message": "authorization-participating artifact has an invalid role"}]
    expected = expected_runtime_proof(rule)

    producer = proof.get("schema_producer_authority", {})
    authority_path = str(producer.get("authority_path", ""))
    if producer != expected.get("schema_producer_authority") or not (repository_root / authority_path).is_file() or producer.get("authority_sha256") != _sha(repository_root / authority_path) or authority_hashes.get(authority_path) != producer.get("authority_sha256") or authority_categories.get(authority_path) != producer.get("authority_category"):
        return finding("schema_producer_authority", "runtime producer authority is not hash- and category-bound")

    identity = proof.get("immutable_identity", {})
    schema_path = str(identity.get("schema_path", ""))
    artifact_schema = _json(repository_root / schema_path) if (repository_root / schema_path).is_file() else {}
    identity_fields = identity.get("identity_fields", [])
    if identity != expected.get("immutable_identity") or identity.get("schema_sha256") != _sha(repository_root / schema_path) or authority_hashes.get(schema_path) != identity.get("schema_sha256") or not identity_fields or any(not _schema_requires(artifact_schema, field) for field in identity_fields):
        return finding("immutable_identity", "runtime identity is not bound to the current schema and required fields")

    derivation = proof.get("source_of_truth_derivation", {})
    if derivation != expected.get("source_of_truth_derivation") or not derivation.get("rules"):
        return finding("source_of_truth_derivation", "runtime derivation rules are not the exact typed authority projection")

    recomputation = proof.get("independent_recomputation", {})
    validator_path = repository_root / str(recomputation.get("validator", ""))
    negative_path = repository_root / str(recomputation.get("negative_test", ""))
    if recomputation != expected.get("independent_recomputation") or not validator_path.is_file() or recomputation.get("validator_sha256") != _sha(validator_path) or authority_hashes.get(str(recomputation.get("validator"))) != recomputation.get("validator_sha256") or not negative_path.is_file() or recomputation.get("negative_test_sha256") != _sha(negative_path) or authority_hashes.get(str(recomputation.get("negative_test"))) != recomputation.get("negative_test_sha256") or not recomputation.get("expected_failure_ids") or not _callable_exists(validator_path, str(recomputation.get("callable", ""))):
        return finding("independent_recomputation", "runtime recomputation is not bound to executable validator and negative evidence")

    stale = proof.get("staleness_propagation", {})
    if stale != expected.get("staleness_propagation") or not stale.get("inputs") or not stale.get("invalidates") or stale.get("propagation_mode") != "fail-closed-before-predicate" or stale.get("revalidation_command_id") not in command_ids:
        return finding("staleness_propagation", "runtime staleness propagation is not executable and fail-closed")

    recovery = proof.get("recovery_supersession", {})
    lineage_fields = recovery.get("lineage_fields", [])
    if recovery != expected.get("recovery_supersession") or recovery.get("history_policy") != "append-only-successor-no-rewrite" or not lineage_fields or any(not _schema_requires(artifact_schema, field) for field in lineage_fields):
        return finding("recovery_supersession", "runtime recovery lineage is not schema-bound and append-only")

    boundary = proof.get("consumer_authorization_boundary", {})
    permission = predicates.get(boundary.get("predicate"))
    entrypoints = boundary.get("consumer_entrypoints", [])
    valid_entrypoints = bool(entrypoints) and {item.get("consumer") for item in entrypoints if isinstance(item, dict)} == set(boundary.get("consumers", []))
    for entrypoint in entrypoints if isinstance(entrypoints, list) else []:
        path = repository_root / str(entrypoint.get("validator", ""))
        valid_entrypoints = valid_entrypoints and path.is_file() and _callable_exists(path, str(entrypoint.get("callable", ""))) and entrypoint.get("failure_mode") == "block-predicate-on-any-dimension-failure"
    if boundary != expected.get("consumer_authorization_boundary") or set(boundary.get("consumers", [])) - set(registered_consumers) or permission is None or boundary.get("authorizes") != permission.get("authorizes") or boundary.get("does_not_authorize") != permission.get("does_not_authorize") or not valid_entrypoints:
        return finding("consumer_authorization_boundary", "runtime consumers are not bound to fail-closed predicate entrypoints")
    return []

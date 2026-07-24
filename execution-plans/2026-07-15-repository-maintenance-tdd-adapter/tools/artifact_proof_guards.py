from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from contract_guards import schema_error
from artifact_proof_verdicts import DIMENSION_RULES, pass_dimension_verdicts, verdict_findings
from artifact_proof_projection_support import validate_predicate_artifact_closure
from runtime_artifact_proof_guards import validate_runtime_type_proof as _validate_runtime_type_proof


AUTHORITY_PATH = "schemas/artifact-proof-authority.v1.json"
TRUST_ROOT_PATH = ".agents/skills/run-phase-bootstrap-review/references/artifact-proof-authority-root.v1.json"
TRUST_ROOT_ID = "repository-maintenance-tdd-adapter"
BOOTSTRAP_SCRIPTS = Path(__file__).resolve().parents[3] / ".agents" / "skills" / "run-phase-bootstrap-review" / "scripts"
if str(BOOTSTRAP_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_SCRIPTS))
from artifact_proof_root_guards import STANDARD_PATH as TRUST_ROOT_STANDARD_PATH, STANDARD_SHA256 as TRUST_ROOT_STANDARD_SHA256, load_artifact_proof_root  # noqa: E402
TRUST_ROOT_INVALIDATES = ["artifact-proof-registry", "runtime-artifact-type-proof", "plan-repair-verified", "plan-ready"]
TRUST_ROOT_BOUNDARY = {
    "consumers": ["composite plan validator"],
    "predicate": "artifact-contract-proof",
    "authorizes": [],
    "does_not_authorize": ["plan-ready", "slice-ready", "bootstrap-review", "implementation-accepted", "protected-handoff", "release-ready"],
}
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _finding(rule_id: str, target: str, message: str) -> dict[str, str]:
    return {"rule_id": rule_id, "target": target, "message": message}


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} root must be object")
    return value


def _manifest_entries(authority: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    hashes: dict[str, str] = {}
    categories: dict[str, str] = {}
    for category, entries in authority.get("categories", {}).items():
        for item in entries if isinstance(entries, list) else []:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                hashes[item["path"]] = str(item.get("sha256"))
                categories[item["path"]] = str(category)
    return hashes, categories


def _callable_exists(path: Path, callable_name: str) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError):
        return False
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == callable_name
        for node in tree.body
    )


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


def _pointer(document: Any, pointer: str) -> Any:
    if pointer == "$document":
        return document
    current = document
    for raw in pointer.strip("/").split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def _command_ids(plan_root: Path) -> set[str]:
    commands = _json(plan_root / "schemas" / "command-registry.v1.json")
    return {str(item.get("id")) for item in commands.get("commands", []) if isinstance(item, dict)}


def _external_trust_root(repository_root: Path) -> tuple[dict[str, Any], str]:
    return load_artifact_proof_root(repository_root)


def expected_static_proof(
    repository_root: Path,
    authority_registry: dict[str, Any],
    artifact_rule: dict[str, Any],
    authority_hashes: dict[str, str],
) -> dict[str, Any]:
    artifact_path = artifact_rule["path"]
    class_rule = authority_registry["classes"][artifact_rule["class_id"]]
    external_root, external_root_hash = _external_trust_root(repository_root)
    is_authority_root = artifact_path.endswith("/" + AUTHORITY_PATH)
    producer = copy.deepcopy(external_root["schema_producer_authority"] if is_authority_root else class_rule["producer_authority"])
    authority_path = producer["authority_path"]
    generator_path = producer["generator_path"]
    registry_rule = authority_registry["rule_registry"]["artifact-proof-package.v1"]
    validator_path = registry_rule["validator_path"]
    configured_rules = artifact_rule.get("derivation_rules")
    if is_authority_root:
        derivation_rules = [
            {**rule, "source_sha256": _sha(repository_root / rule["source"])}
            for rule in external_root["source_of_truth_derivation"]["rules"]
        ]
    elif configured_rules:
        derivation_rules = [
            {**rule, "source_sha256": _sha(repository_root / rule["source"])}
            for rule in configured_rules
        ]
    else:
        source = artifact_path if class_rule["derivation"] != "exact-projection" else (
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/" + AUTHORITY_PATH
        )
        derivation_rules = [{
            "source": source,
            "source_sha256": _sha(repository_root / source),
            "field": "$bytes" if class_rule["derivation"] != "exact-projection" else "/artifacts",
            "target_field": "$bytes" if class_rule["derivation"] != "exact-projection" else "$document",
            "derivation": class_rule["derivation"],
        }]
    pinned_hash = artifact_rule.get("sha256")
    if is_authority_root:
        identity = copy.deepcopy(external_root["immutable_identity"])
        recomputation = copy.deepcopy(external_root["independent_recomputation"])
        stale = copy.deepcopy(external_root["staleness_propagation"])
        stale["inputs"] = derivation_rules
        recovery = copy.deepcopy(external_root["recovery_supersession"])
        lattice = copy.deepcopy(external_root["consumer_authorization_boundary"])
    else:
        identity_hash = pinned_hash if class_rule["identity_mode"] == "pinned-bytes" else None
        predecessor_hash = artifact_rule.get("predecessor_sha256")
        lifecycle_status = artifact_rule.get("lifecycle_status", "new")
        identity = {
            "mode": class_rule["identity_mode"], "algorithm": "sha256-bytes",
            "artifact_sha256": identity_hash, "authority_revision": authority_registry["authority_revision"],
            "manifest_path": "schemas/authority-manifest.v1.json",
        }
        recomputation = {
            "rule_id": "artifact-proof-package.v1", "validator_path": validator_path,
            "validator_sha256": authority_hashes.get(validator_path), "callable": registry_rule["callable"],
            "negative_test_path": registry_rule["negative_test_path"], "negative_test_sha256": registry_rule["negative_test_sha256"],
            "expected_failure_ids": registry_rule["expected_failure_ids"],
        }
        stale = {"inputs": derivation_rules, **class_rule["staleness"]}
        lineage = artifact_rule.get("lineage", class_rule["lineage"])
        recovery = {
            "history_policy": "append-only-successor-no-rewrite", "schema_path": lineage["schema_path"],
            "lineage_fields": lineage["required_fields"], "predecessor_policy": lineage["predecessor_policy"],
            "lifecycle_status": lifecycle_status, "predecessor_sha256": predecessor_hash,
        }
        if artifact_rule.get("proof_scope") == "authorization-participating":
            lattice = copy.deepcopy(artifact_rule["consumer_authorization_boundary"])
        else:
            lattice = copy.deepcopy(authority_registry["permission_lattice"]["artifact-contract-proof"])
            lattice["predicate"] = "artifact-contract-proof"
    return {
        "artifact_path": artifact_path,
        "artifact_kind": class_rule["artifact_kind"],
        "proof_scope": artifact_rule.get("proof_scope", "static-contract"),
        "finding_ids": artifact_rule.get("finding_ids", ["RMAP-1400-UNIFORM-ARTIFACT-PROOF"]),
        "dimension_verdicts": pass_dimension_verdicts(),
        "schema_producer_authority": {
            "authority_path": authority_path,
            "authority_category": producer["authority_category"],
            "authority_sha256": external_root_hash if is_authority_root else authority_hashes.get(authority_path),
            "producer_kind": producer["producer_kind"],
            "generator_path": generator_path,
            "generator_sha256": authority_hashes.get(generator_path) if generator_path else None,
        },
        "immutable_identity": identity,
        "source_of_truth_derivation": {"rules": derivation_rules},
        "independent_recomputation": recomputation,
        "staleness_propagation": stale,
        "recovery_supersession": recovery,
        "consumer_authorization_boundary": lattice,
    }


def expected_runtime_proof(rule: dict[str, Any]) -> dict[str, Any]:
    return {
        **copy.deepcopy(rule),
        "artifact_role": "authorization-participating",
        "dimension_verdicts": pass_dimension_verdicts(),
    }


def validate_runtime_type_proof(
    repository_root: Path,
    proof: dict[str, Any],
    rule: dict[str, Any],
    authority_hashes: dict[str, str],
    authority_categories: dict[str, str],
    predicates: dict[str, Any],
    registered_consumers: list[str],
) -> list[dict[str, str]]:
    plan_root = repository_root / "execution-plans" / "2026-07-15-repository-maintenance-tdd-adapter"
    return _validate_runtime_type_proof(
        repository_root, proof, rule, authority_hashes, authority_categories,
        predicates, registered_consumers, expected_runtime_proof,
        verdict_findings, DIMENSION_RULES, _command_ids(plan_root),
    )


def validate_artifact_proofs(
    plan_root: Path,
    registry: dict[str, Any],
    authority: dict[str, Any],
) -> list[dict[str, str]]:
    repository_root = plan_root.parents[1]
    authority_path = plan_root / AUTHORITY_PATH
    try:
        proof_schema = _json(plan_root / "schemas" / "artifact-proof.v1.schema.json")
        inventory = _json(plan_root / "schemas" / "artifact-proof-required.v1.json")
        authority_registry = _json(authority_path)
        runtime = _json(plan_root / "schemas" / "runtime-artifact-type-proof.v1.json")
        external_root, _ = _external_trust_root(repository_root)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return [_finding("RMAP-ARTIFACT-PROOF-PRODUCER", "artifact-proof-authority", str(exc))]
    findings: list[dict[str, str]] = []
    try:
        closure = _json(plan_root / "schemas" / "predicate-artifact-closure.v1.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return [_finding("RMAP-ARTIFACT-PROOF-CLOSURE", "predicate-artifact-closure", str(exc))]
    authority_hashes, authority_categories = _manifest_entries(authority)
    authority_relative = authority_path.relative_to(repository_root).as_posix()
    if authority_registry.get("schema_version") != "jimuyun.artifact-proof-authority.v1" or authority_registry.get("plan_id") != "repository-maintenance-tdd-adapter":
        return [_finding("RMAP-ARTIFACT-PROOF-PRODUCER", AUTHORITY_PATH, "independent authority registry identity is invalid")]
    if authority_registry.get("external_trust_root") != {"path": TRUST_ROOT_PATH, "root_id": "artifact-proof-root.v1"}:
        return [_finding("RMAP-ARTIFACT-PROOF-PRODUCER", AUTHORITY_PATH, "authority registry does not name the fixed VDD Skill trust root")]
    root_schema_error = schema_error(external_root, proof_schema)
    if root_schema_error:
        return [_finding("RMAP-ARTIFACT-PROOF-PRODUCER", TRUST_ROOT_PATH, root_schema_error)]
    source = authority_registry.get("authority_source", {})
    source_path = Path(str(source.get("path", "")))
    if not source_path.is_file() or source.get("sha256") != _sha(source_path) or source.get("sha256") != authority_registry.get("authority_revision"):
        return [_finding("RMAP-ARTIFACT-PROOF-PRODUCER", AUTHORITY_PATH, "closure authority source is missing or stale")]
    plan_lattice = copy.deepcopy(authority_registry.get("permission_lattice", {}).get("artifact-contract-proof", {}))
    plan_lattice["predicate"] = "artifact-contract-proof"
    if plan_lattice != TRUST_ROOT_BOUNDARY:
        return [_finding("RMAP-ARTIFACT-PROOF-CONSUMER", AUTHORITY_PATH, "plan and external trust-root permission lattices differ")]
    root_identity = external_root["immutable_identity"]
    if external_root.get("artifact_path") != authority_relative or root_identity != {
        "mode": "semantic-root-policy",
        "algorithm": "vdd-root-policy-v1",
        "artifact_sha256": None,
        "authority_revision": "vdd-artifact-proof-root-policy.v2",
        "manifest_path": "schemas/authority-manifest.v1.json",
    } or authority_hashes.get(authority_relative) != _sha(authority_path):
        return [_finding("RMAP-ARTIFACT-PROOF-IDENTITY", AUTHORITY_PATH, "authority registry is not governed by the fixed semantic VDD trust-root policy")]
    if external_root["staleness_propagation"].get("invalidates") != TRUST_ROOT_INVALIDATES:
        return [_finding("RMAP-ARTIFACT-PROOF-STALENESS", AUTHORITY_PATH, "external trust-root invalidation closure is not exact")]
    if external_root["consumer_authorization_boundary"] != TRUST_ROOT_BOUNDARY:
        return [_finding("RMAP-ARTIFACT-PROOF-CONSUMER", AUTHORITY_PATH, "external trust-root permission lattice is not exact zero authority")]
    producer_root = external_root["schema_producer_authority"]
    if producer_root.get("authority_path") != TRUST_ROOT_STANDARD_PATH or producer_root.get("authority_sha256") != TRUST_ROOT_STANDARD_SHA256 or authority_hashes.get(TRUST_ROOT_STANDARD_PATH) != TRUST_ROOT_STANDARD_SHA256 or _sha(repository_root / TRUST_ROOT_STANDARD_PATH) != TRUST_ROOT_STANDARD_SHA256:
        return [_finding("RMAP-ARTIFACT-PROOF-PRODUCER", AUTHORITY_PATH, "strict VDD producer authority is not pinned to the provisional diagnostic baseline")]
    artifact_rules = authority_registry.get("artifacts", [])
    rule_paths = [item.get("path") for item in artifact_rules if isinstance(item, dict)]
    required_paths = inventory.get("contract_artifacts", [])
    proof_by_path = {item.get("artifact_path"): item for item in registry.get("proofs", []) if isinstance(item, dict)}
    if rule_paths != required_paths or set(proof_by_path) != set(required_paths) or len(proof_by_path) != len(registry.get("proofs", [])):
        findings.append(_finding("RMAP-ARTIFACT-PROOF-PRODUCER", "artifact-proof-registry", "authority, required inventory, and proof package paths differ"))
        return findings
    commands = _command_ids(plan_root)
    rule_registry = authority_registry.get("rule_registry", {})
    for artifact_rule in artifact_rules:
        target = str(artifact_rule["path"])
        proof = proof_by_path[target]
        error = schema_error(proof, proof_schema)
        if error:
            findings.append(_finding("RMAP-ARTIFACT-PROOF-SCHEMA", target, error))
            continue
        class_id = artifact_rule.get("class_id")
        class_rule = authority_registry.get("classes", {}).get(class_id)
        if not isinstance(class_rule, dict):
            findings.append(_finding("RMAP-ARTIFACT-PROOF-PRODUCER", target, "artifact class is not independently registered"))
            continue
        verdict_errors = verdict_findings(proof, target)
        expected_scope = artifact_rule.get("proof_scope", "static-contract")
        if proof.get("proof_scope") != expected_scope or verdict_errors:
            findings.extend(verdict_errors or [_finding("RMAP-ARTIFACT-PROOF-APPLICABILITY", target, "registered contract artifact has an invalid proof scope")])
            continue
        expected = expected_static_proof(repository_root, authority_registry, artifact_rule, authority_hashes)
        producer = expected["schema_producer_authority"]
        authority_owner_path = producer["authority_path"]
        generator_path = producer["generator_path"]
        if proof["schema_producer_authority"] != producer or authority_categories.get(authority_owner_path) != producer["authority_category"] or (generator_path and not (repository_root / generator_path).is_file()):
            findings.append(_finding(DIMENSION_RULES["schema_producer_authority"], target, "producer authority differs from independent inventory")); continue
        artifact = repository_root / target
        actual_hash = _sha(artifact) if artifact.is_file() else None
        pinned_hash = artifact_rule.get("sha256")
        identity = expected["immutable_identity"]
        if proof["immutable_identity"] != identity or authority_hashes.get(target) != actual_hash or (identity["mode"] == "pinned-bytes" and (not HASH_RE.fullmatch(str(pinned_hash)) or pinned_hash != actual_hash)):
            findings.append(_finding(DIMENSION_RULES["immutable_identity"], target, "artifact identity does not match pinned authority and current bytes")); continue
        derivation = proof["source_of_truth_derivation"]
        derivation_valid = derivation == expected["source_of_truth_derivation"]
        if derivation_valid:
            try:
                target_document = _json(artifact) if any(rule["derivation"] == "hash-bound-reference" for rule in derivation["rules"]) else None
                for rule in derivation["rules"]:
                    source_path = repository_root / rule["source"]
                    if rule["source_sha256"] != _sha(source_path):
                        derivation_valid = False; break
                    if rule["derivation"] == "external-hash-pin":
                        source_document = _json(source_path)
                        if _pointer(source_document, rule["field"]) != actual_hash:
                            derivation_valid = False; break
                    if rule["derivation"] == "hash-bound-reference":
                        expected_ref = {"path": rule["source"], "sha256": rule["source_sha256"]}
                        if _pointer(target_document, rule["target_field"]) != expected_ref:
                            derivation_valid = False; break
            except (OSError, UnicodeError, ValueError, KeyError, IndexError, json.JSONDecodeError):
                derivation_valid = False
        if not derivation_valid:
            findings.append(_finding(DIMENSION_RULES["source_of_truth_derivation"], target, "typed source derivation differs from independent inventory")); continue
        recomputation = proof["independent_recomputation"]
        is_authority_root = target.endswith("/" + AUTHORITY_PATH)
        registered = rule_registry.get(recomputation.get("rule_id"))
        validator_path = repository_root / str(recomputation.get("validator_path", ""))
        negative_path = repository_root / str(recomputation.get("negative_test_path", ""))
        local_rule_valid = is_authority_root or (registered is not None and registered.get("validator_sha256") == _sha(validator_path) and set(recomputation["expected_failure_ids"]).issubset(set(registered["expected_failure_ids"])))
        if recomputation != expected["independent_recomputation"] or not local_rule_valid or authority_hashes.get(recomputation["validator_path"]) != recomputation["validator_sha256"] or not validator_path.is_file() or recomputation.get("validator_sha256") != _sha(validator_path) or recomputation.get("negative_test_sha256") != _sha(negative_path) or not _callable_exists(validator_path, recomputation["callable"]):
            findings.append(_finding(DIMENSION_RULES["independent_recomputation"], target, "rule is not bound to an implemented callable and negative test")); continue
        stale = proof["staleness_propagation"]
        if stale != expected["staleness_propagation"] or not stale["inputs"] or not stale["invalidates"] or stale["regeneration_command_id"] not in commands or stale["revalidation_command_id"] not in commands:
            findings.append(_finding(DIMENSION_RULES["staleness_propagation"], target, "staleness propagation is not executable or exact")); continue
        lineage = proof["recovery_supersession"]
        lineage_schema_path = repository_root / str(lineage.get("schema_path", ""))
        try:
            lineage_schema = _json(lineage_schema_path)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            lineage_schema = {}
        lifecycle_valid = (
            (lineage.get("lifecycle_status") == "new" and lineage.get("predecessor_sha256") is None)
            or (lineage.get("lifecycle_status") == "unchanged" and lineage.get("predecessor_sha256") == actual_hash)
            or (lineage.get("lifecycle_status") == "supersedes" and HASH_RE.fullmatch(str(lineage.get("predecessor_sha256"))) and lineage.get("predecessor_sha256") != actual_hash)
        )
        if lineage != expected["recovery_supersession"] or not lifecycle_valid or not lineage["lineage_fields"] or any(not _schema_requires(lineage_schema, field) for field in lineage["lineage_fields"]):
            findings.append(_finding(DIMENSION_RULES["recovery_supersession"], target, "lineage fields are not required by the registered schema")); continue
        if proof["consumer_authorization_boundary"] != expected["consumer_authorization_boundary"]:
            findings.append(_finding(DIMENSION_RULES["consumer_authorization_boundary"], target, "consumer permission lattice differs from independent registry")); continue
        if expected_scope == "static-contract" and proof["consumer_authorization_boundary"] != TRUST_ROOT_BOUNDARY:
            findings.append(_finding(DIMENSION_RULES["consumer_authorization_boundary"], target, "static proof permission differs from the external zero-authority lattice")); continue
    runtime_rules = {item["type_id"]: item for item in authority_registry.get("runtime_types", [])}
    runtime_proofs = {item.get("type_id"): item for item in runtime.get("proofs", []) if isinstance(item, dict)}
    predicates = inventory.get("predicate_authority", {})
    consumers = set(inventory.get("registered_consumers", []))
    if set(runtime_rules) != set(inventory.get("runtime_types", [])) or set(runtime_proofs) != set(runtime_rules):
        findings.append(_finding("RMAP-ARTIFACT-PROOF-PRODUCER", "runtime-artifact-type-proof", "runtime proof inventory differs from independent authority"))
    for type_id, rule in runtime_rules.items():
        findings.extend(validate_runtime_type_proof(
            repository_root,
            runtime_proofs.get(type_id, {}),
            rule,
            authority_hashes,
            authority_categories,
            predicates,
            list(consumers),
        ))
    if registry.get("authorizes", []) or runtime.get("authorizes", []) or inventory.get("authorizes", []):
        findings.append(_finding("RMAP-ARTIFACT-PROOF-CONSUMER", "artifact-proof-metadata", "proof metadata cannot authorize transitions"))
    if not findings:
        findings.extend(validate_predicate_artifact_closure(repository_root, closure))
    return findings

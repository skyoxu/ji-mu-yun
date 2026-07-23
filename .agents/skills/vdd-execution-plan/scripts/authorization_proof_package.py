#!/usr/bin/env python3
"""Portable, deterministic authorization-proof package validator and runner."""
from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DIMENSIONS = (
    "schema_producer_authority", "immutable_identity", "source_of_truth_derivation",
    "independent_recomputation", "staleness_propagation", "recovery_supersession",
    "consumer_authorization_boundary",
)
SOURCE_CLOSURE_MUTATION_EXPECTATIONS = {
    "source-omit": "VDD-PACKAGE-SOURCE-INVENTORY",
    "source-extra": "VDD-PACKAGE-SOURCE-CLOSURE:plan-ready",
    "source-identity-drift": "VDD-PACKAGE-SOURCE-IDENTITY",
    "source-role-change": "VDD-PACKAGE-SOURCE-IDENTITY",
    "source-predicate-unlink": "VDD-PACKAGE-SOURCE-CLOSURE:plan-ready",
    "source-proof-unlink": "VDD-PACKAGE-SOURCE-PROOF",
    "source-binding-replay": "VDD-PACKAGE-SOURCE-BINDING",
    "source-copied-hash": "VDD-PACKAGE-SOURCE-HASH-STALE",
}
BINDING_FIELDS = (
    "candidate_hash", "source_hash", "validator_root", "authority_root", "closure_definition_hash",
)
DEFAULT_ROOT_REGISTRY = ".agents/skills/vdd-execution-plan/references/vdd-artifact-proof-roots.v1.json"
SEMANTIC_ROOT = Path(__file__).resolve().parents[1] / "references" / "vdd-artifact-proof-semantic-contract.v1.json"
SEMANTIC_DIMENSION_FIELDS = {
    "schema_producer_authority": "producer_authority",
    "source_of_truth_derivation": "derivation",
    "independent_recomputation": "recomputation",
    "staleness_propagation": "staleness",
    "consumer_authorization_boundary": "consumer_authorization",
}
SOURCE_INVENTORY_FIELDS = {
    "source_id", "source_role", "context_classes", "canonical_path", "identity",
    "source_binding", "applicable_predicates", "consumer", "proof_id",
    "classification", "disposition",
}
SOURCE_BINDING_BINDINGS = [
    "plan", "package", "source", "proof", "predicate", "result", "review", "input",
]


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("package must be an object")
    return data


def canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def git_identity(root: Path, identity: dict) -> tuple[str, str, str] | None:
    try:
        output = subprocess.check_output(
            ["git", "ls-tree", identity["tree"], "--", identity["path"]],
            cwd=root, text=True, encoding="utf-8", stderr=subprocess.DEVNULL,
        ).strip()
    except (KeyError, OSError, subprocess.CalledProcessError):
        return None
    fields = output.split(maxsplit=3)
    if len(fields) != 4 or fields[1] != "blob":
        return None
    return fields[0], fields[2], fields[3].split("\t", 1)[-1]


def proof_value(proof: dict) -> str | None:
    identity = proof.get("identity", {})
    if identity.get("kind") == "git-tracked":
        return identity.get("blob")
    if identity.get("kind") == "binary":
        return identity.get("sha256")
    if identity.get("kind") in {"generated-text", "external-text"}:
        return identity.get("normalized_sha256")
    return None


def text_identity(root: Path, proof: dict, identity: dict) -> bool:
    if set(identity) != {"kind", "canonicalization_rule", "normalized_sha256", "raw_sha256"}:
        return False
    if identity.get("canonicalization_rule") != "utf8-lf-v1":
        return False
    content_path = proof.get("content_path")
    target = root / content_path if isinstance(content_path, str) else None
    if target is None or not target.is_file():
        return False
    raw = target.read_bytes()
    try:
        normalized = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    except UnicodeDecodeError:
        return False
    return (
        identity.get("raw_sha256") == "sha256:" + hashlib.sha256(raw).hexdigest()
        and identity.get("normalized_sha256") == "sha256:" + hashlib.sha256(normalized).hexdigest()
    )


def validate_external_envelope(
    envelope_path: Path, registry_path: Path, package_path: Path,
) -> tuple[list[str], dict | None]:
    try:
        envelope = load(envelope_path)
        registry = load(registry_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return ["VDD-PACKAGE-EXTERNAL-ENVELOPE"], None
    if registry.get("schema_version") != "vdd.artifact-proof-roots.v1":
        return ["VDD-PACKAGE-ROOT-REGISTRY"], None
    roots = registry.get("roots")
    if not isinstance(roots, dict):
        return ["VDD-PACKAGE-ROOT-REGISTRY"], None
    root = roots.get(envelope.get("root_id"))
    if not isinstance(root, dict):
        return ["VDD-PACKAGE-EXTERNAL-ENVELOPE"], None
    signing_key = os.environ.get("VDD_AUTHORIZATION_PROOF_SIGNING_KEY")
    expected = {
        "signer": root.get("trusted_signer"),
        "validator_identity": root.get("validator_identity"),
        "package_sha256": "sha256:" + hashlib.sha256(package_path.read_bytes()).hexdigest(),
    }
    signature_payload = {key: value for key, value in envelope.items() if key != "signature"}
    signature = hmac.new(
        signing_key.encode("utf-8"), canonical_hash(signature_payload).encode("ascii"), hashlib.sha256,
    ).hexdigest() if signing_key else None
    if envelope.get("schema_version") != "vdd.external-validation-envelope.v1" or any(
        envelope.get(key) != value for key, value in expected.items()
    ) or not isinstance(envelope.get("signature"), str) or signature is None or not hmac.compare_digest(envelope["signature"], signature):
        return ["VDD-PACKAGE-EXTERNAL-ENVELOPE"], None
    return [], {
        "envelope_sha256": "sha256:" + hashlib.sha256(envelope_path.read_bytes()).hexdigest(),
        "root_id": envelope["root_id"], "signer": envelope["signer"],
        "permission_ceiling": root.get("permission_ceiling"),
        "expires_at": envelope.get("expires_at"),
    }


def local_validation_provenance(package_path: Path, external: dict | None = None) -> dict:
    provenance = {
        "root_id": "vdd-local-deterministic",
        "signer": "repository-local-deterministic-runner",
        "validator_identity": "vdd.authorization_proof_package.validate.v1",
        "package_sha256": "sha256:" + hashlib.sha256(package_path.read_bytes()).hexdigest(),
    }
    if external is not None:
        provenance["external_validation"] = external
    signing_key = os.environ.get("VDD_AUTHORIZATION_PROOF_SIGNING_KEY")
    if signing_key:
        provenance["signature_algorithm"] = "hmac-sha256-v1"
        provenance["signature"] = hmac.new(
            signing_key.encode("utf-8"), canonical_hash(provenance).encode("ascii"), hashlib.sha256,
        ).hexdigest()
    return provenance


def discover_external_members(
    entry: object,
    predicate: str,
    expected_kind: str,
    package_path: Path | None,
    repository_root: Path | None,
) -> list[str] | None:
    if not isinstance(entry, dict) or set(entry) != {"id", "kind", "reference"}:
        return None
    if entry.get("kind") != expected_kind or not isinstance(entry.get("id"), str):
        return None
    reference = entry.get("reference")
    if (
        not isinstance(reference, dict)
        or set(reference) != {"path", "sha256"}
        or not isinstance(reference.get("path"), str)
        or not isinstance(reference.get("sha256"), str)
    ):
        return None
    root = repository_root or Path.cwd()
    target = (root / reference["path"]).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return None
    if not target.is_file() or reference["sha256"] != "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest():
        return None
    try:
        document = load(target)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if document.get("discovery_id") != entry["id"]:
        return None
    if expected_kind == "plan-links":
        if document.get("schema_version") != "vdd.plan-link-discovery.v1":
            return None
        links = document.get("links")
        if not isinstance(links, list):
            return None
        members = [
            item.get("proof_id")
            for item in links
            if isinstance(item, dict) and item.get("predicate") == predicate
        ]
    else:
        if document.get("schema_version") != "vdd.validator-read-set-discovery.v1":
            return None
        read_sets = document.get("read_sets")
        members = read_sets.get(predicate) if isinstance(read_sets, dict) else None
    if not isinstance(members, list) or any(not isinstance(item, str) or not item for item in members):
        return None
    return sorted(members)


def semantic_dimension_findings(proof: dict, contract: object) -> list[str]:
    """Validate executable references for the non-identity/lineage proof dimensions."""
    if not isinstance(contract, dict):
        return ["VDD-PACKAGE-SEMANTIC-CONTRACT"]
    registries = {
        "producer_authority": "authorities",
        "derivation": "derivation_rules",
        "recomputation": "validators",
        "staleness": "invalidation_contracts",
        "consumer_authorization": "consumers",
    }
    findings: list[str] = []
    for dimension, field in SEMANTIC_DIMENSION_FIELDS.items():
        value = proof.get(field)
        registry = contract.get(registries[field])
        identifier = value.get("id") if isinstance(value, dict) else None
        if not isinstance(registry, dict) or not isinstance(identifier, str) or registry.get(identifier) != value:
            findings.append("VDD-PACKAGE-DIMENSION:" + dimension)
            continue
        if field == "producer_authority":
            valid = set(value) == {"id", "path", "kind"} and all(
                isinstance(value.get(key), str) and value[key] for key in ("id", "path", "kind")
            )
        elif field == "derivation":
            valid = set(value) == {"id", "source", "target", "rule_id"} and all(
                isinstance(value.get(key), str) and value[key]
                for key in ("id", "source", "target", "rule_id")
            ) and value["source"] != value["target"]
        elif field == "recomputation":
            valid = set(value) == {"id", "path", "callable", "rule_id"} and all(
                isinstance(value.get(key), str) and value[key]
                for key in ("id", "path", "callable", "rule_id")
            )
        elif field == "staleness":
            valid = set(value) == {"id", "inputs", "invalidates", "rule_id"} and all(
                isinstance(value.get(key), str) and value[key] for key in ("id", "rule_id")
            ) and isinstance(value.get("inputs"), list) and bool(value["inputs"]) and isinstance(value.get("invalidates"), list) and bool(value["invalidates"])
        else:
            valid = set(value) == {"id", "predicate", "authorizes", "does_not_authorize"} and isinstance(value.get("id"), str) and bool(value["id"]) and isinstance(value.get("predicate"), str) and bool(value["predicate"]) and isinstance(value.get("authorizes"), list) and isinstance(value.get("does_not_authorize"), list) and not (set(value["authorizes"]) & set(value["does_not_authorize"]))
        if not valid:
            findings.append("VDD-PACKAGE-DIMENSION:" + dimension)
    return findings


def resolve_semantic_contract(package: dict, package_path: Path | None) -> tuple[object, bool]:
    reference = package.get("semantic_contract_reference")
    if reference is None:
        try:
            return load(SEMANTIC_ROOT), True
        except (OSError, ValueError, json.JSONDecodeError):
            return None, False
    if (
        package_path is None
        or not isinstance(reference, dict)
        or set(reference) != {"path", "sha256"}
        or not isinstance(reference.get("path"), str)
        or not isinstance(reference.get("sha256"), str)
    ):
        return None, False
    target = (package_path.parent / reference["path"]).resolve()
    if target.parent != package_path.parent.resolve() or not target.is_file():
        return None, False
    raw = target.read_bytes()
    if reference["sha256"] != "sha256:" + hashlib.sha256(raw).hexdigest():
        return None, False
    try:
        return load(target), True
    except (OSError, ValueError, json.JSONDecodeError):
        return None, False


def canonical_source_inventory(package: dict) -> list[dict] | None:
    inventory = package.get("source_inventory")
    if not isinstance(inventory, list) or not inventory:
        return []
    normalized: list[dict] = []
    source_ids: set[str] = set()
    proof_ids: set[str] = set()
    for member in inventory:
        if not isinstance(member, dict) or set(member) != SOURCE_INVENTORY_FIELDS:
            return []
        source_id = member.get("source_id")
        proof_id = member.get("proof_id")
        predicates = member.get("applicable_predicates")
        context_classes = member.get("context_classes")
        if (
            not isinstance(source_id, str) or not source_id
            or not isinstance(proof_id, str) or not proof_id
            or source_id in source_ids or proof_id in proof_ids
            or not isinstance(member.get("source_role"), str) or not member["source_role"]
            or not isinstance(context_classes, list) or not context_classes
            or any(not isinstance(item, str) or not item for item in context_classes)
            or len(context_classes) != len(set(context_classes))
            or member["source_role"] not in context_classes
            or not isinstance(member.get("canonical_path"), str) or not member["canonical_path"]
            or not isinstance(member.get("identity"), dict) or not member["identity"]
            or not isinstance(predicates, list) or not predicates
            or any(not isinstance(item, str) or not item for item in predicates)
            or not isinstance(member.get("consumer"), str) or not member["consumer"]
            or member.get("classification") not in {"IN-CLOSURE", "OUT-OF-CLOSURE"}
            or not isinstance(member.get("disposition"), str) or not member["disposition"]
        ):
            return []
        source_ids.add(source_id)
        proof_ids.add(proof_id)
        normalized.append(copy.deepcopy(member))
    return sorted(normalized, key=lambda item: item["source_id"])


def valid_source_binding_reference(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"schema_version", "binding_id", "required_bindings"}
        and value.get("schema_version") == "vdd.plan-source-binding.v1"
        and isinstance(value.get("binding_id"), str)
        and bool(value["binding_id"])
        and value.get("required_bindings") == SOURCE_BINDING_BINDINGS
    )


def recompute_bindings(package: dict, package_path: Path | None) -> dict[str, str] | None:
    semantic_contract, valid = resolve_semantic_contract(package, package_path)
    if not valid:
        return None
    reference = package.get("semantic_contract_reference")
    semantic_bytes = (package_path.parent / reference["path"]).read_bytes() if isinstance(reference, dict) else SEMANTIC_ROOT.read_bytes()
    source_inventory = canonical_source_inventory(package)
    if source_inventory == []:
        return None
    return {
        "candidate_hash": canonical_hash(package.get("proofs")),
        "source_hash": canonical_hash(source_inventory),
        "validator_root": "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "authority_root": "sha256:" + hashlib.sha256(semantic_bytes).hexdigest(),
        "closure_definition_hash": canonical_hash(package.get("predicate_closures")),
    }


def validate(package: dict, repository_root: Path | None = None, package_path: Path | None = None) -> list[str]:
    findings: list[str] = []
    if package.get("schema_version") != "vdd.authorization-proof-package.v1":
        findings.append("VDD-PACKAGE-SCHEMA")
    if package.get("assurance_level") != "deterministic-package":
        findings.append("VDD-PACKAGE-ASSURANCE")
    bindings = package.get("bindings")
    if not isinstance(bindings, dict) or set(bindings) != set(BINDING_FIELDS) or any(
        not isinstance(bindings.get(field), str) or not bindings[field].startswith("sha256:")
        for field in BINDING_FIELDS
    ):
        findings.append("VDD-PACKAGE-BINDINGS")
    source_inventory = canonical_source_inventory(package)
    recomputed = recompute_bindings(package, package_path)
    if source_inventory == []:
        findings.append("VDD-PACKAGE-SOURCE-INVENTORY")
    binding_ids = [
        member.get("source_binding", {}).get("binding_id")
        for member in source_inventory or []
        if isinstance(member.get("source_binding"), dict)
    ]
    if (
        any(
            not valid_source_binding_reference(member.get("source_binding"))
            or member.get("disposition") != "consumed"
            for member in source_inventory or []
        )
        or len(binding_ids) != len(source_inventory or [])
        or len(binding_ids) != len(set(binding_ids))
    ):
        findings.append("VDD-PACKAGE-SOURCE-BINDING")
    if recomputed is None or not isinstance(bindings, dict) or any(
        bindings.get(field) != recomputed.get(field) for field in BINDING_FIELDS if field != "source_hash"
    ):
        findings.append("VDD-PACKAGE-BINDINGS")
    if recomputed is None or not isinstance(bindings, dict) or bindings.get("source_hash") != recomputed.get("source_hash"):
        findings.append("VDD-PACKAGE-SOURCE-HASH-STALE")
    roles = package.get("roles")
    required_roles = ("normative", "projection", "execution")
    if not isinstance(roles, dict) or any(not roles.get(layer) for layer in required_roles):
        findings.append("VDD-PACKAGE-ROLES")
    semantic_contract = package.get("semantic_contract")
    if not isinstance(semantic_contract, dict):
        findings.append("VDD-PACKAGE-SEMANTIC-CONTRACT")
    trusted_semantic_contract, semantic_root_valid = resolve_semantic_contract(package, package_path)
    if not semantic_root_valid or semantic_contract != trusted_semantic_contract:
        findings.append("VDD-PACKAGE-SEMANTIC-ROOT")

    closures = package.get("predicate_closures")
    closure_members: set[str] = set()
    if not isinstance(closures, dict) or not closures:
        findings.append("VDD-PACKAGE-CLOSURE")
    else:
        for predicate, closure in closures.items():
            rule = "VDD-PACKAGE-CLOSURE:" + str(predicate)
            if not isinstance(closure, dict) or closure.get("producer") == closure.get("verifier"):
                findings.append(rule)
                continue
            declared = closure.get("members")
            producer = closure.get("producer_members", declared)
            verifier = closure.get("verifier_members", declared)
            producer_entry = closure.get("producer_discovery")
            verifier_entry = closure.get("verifier_discovery")
            if (
                not isinstance(producer_entry, dict)
                or not isinstance(verifier_entry, dict)
                or producer_entry.get("id") == verifier_entry.get("id")
                or producer_entry.get("reference") == verifier_entry.get("reference")
            ):
                findings.append(rule)
                continue
            discovered_producer = discover_external_members(
                producer_entry, str(predicate), "plan-links", package_path, repository_root
            )
            discovered_verifier = discover_external_members(
                verifier_entry, str(predicate), "validator-read-set", package_path, repository_root
            )
            if not all(isinstance(value, list) for value in (declared, producer, verifier)):
                findings.append(rule)
                continue
            predicate_source_proofs = {
                member["proof_id"]
                for member in source_inventory
                if member["classification"] == "IN-CLOSURE"
                and str(predicate) in member["applicable_predicates"]
            } if source_inventory else set()
            if set(declared) != predicate_source_proofs:
                findings.append("VDD-PACKAGE-SOURCE-CLOSURE:" + str(predicate))
            if (
                set(declared) != set(producer)
                or set(declared) != set(verifier)
                or discovered_producer is None
                or discovered_verifier is None
                or set(declared) != set(discovered_producer)
                or set(declared) != set(discovered_verifier)
            ):
                findings.append(rule)
            if closure.get("closure_root") and closure["closure_root"] != canonical_hash(sorted(declared)):
                findings.append(rule)
            if closure.get("mode") == "shared-superset":
                dependencies = set(closure.get("actual_dependencies", []))
                if closure.get("coverage_proof") is not True or not dependencies.issubset(set(declared)):
                    findings.append(rule)
            elif closure.get("mode") != "exact":
                findings.append(rule)
            closure_members.update(declared)

    proofs = package.get("proofs")
    proof_ids: set[str] = set()
    baseline = package.get("baseline", {}).get("records", {})
    if not isinstance(baseline, dict):
        findings.append("VDD-PACKAGE-LINEAGE")
        baseline = {}
    static_seen = runtime_seen = False
    if not isinstance(proofs, list) or not proofs:
        findings.append("VDD-PACKAGE-PROOFS")
    else:
        for proof in proofs:
            if not isinstance(proof, dict) or not isinstance(proof.get("id"), str):
                findings.append("VDD-PACKAGE-PROOFS")
                continue
            proof_id = proof["id"]
            proof_ids.add(proof_id)
            artifact_type = proof.get("artifact_type", "static")
            static_seen |= artifact_type == "static"
            runtime_seen |= artifact_type == "runtime"
            if artifact_type not in {"static", "runtime"} or (artifact_type == "runtime" and not proof.get("runtime_kind")):
                findings.append("VDD-PACKAGE-ARTIFACT-TYPE")
            verdicts = proof.get("dimension_verdicts", {})
            if set(verdicts) != set(DIMENSIONS):
                findings.append("VDD-PACKAGE-DIMENSIONS")
            else:
                for dimension, verdict in verdicts.items():
                    if proof.get("classification") != "OUT-OF-CLOSURE" and verdict not in {"PASS", "N/A"}:
                        findings.append("VDD-PACKAGE-DIMENSION:" + dimension)
            findings.extend(semantic_dimension_findings(proof, semantic_contract))
            if proof.get("classification") == "OUT-OF-CLOSURE":
                if proof.get("authorizes") != [] or not proof.get("reason_code") or not proof.get("machine_checks"):
                    findings.append("VDD-PACKAGE-OUT-OF-CLOSURE")
            elif proof.get("classification") != "IN-CLOSURE":
                findings.append("VDD-PACKAGE-CLASSIFICATION")
            identity = proof.get("identity", {})
            if identity.get("kind") == "git-tracked":
                if set(identity) != {"kind", "tree", "path", "mode", "blob"}:
                    findings.append("VDD-PACKAGE-IDENTITY")
                elif repository_root is not None:
                    observed = git_identity(repository_root, identity)
                    if observed is None or observed != (identity["mode"], identity["blob"], identity["path"]):
                        findings.append("VDD-PACKAGE-IDENTITY")
            elif identity.get("kind") == "binary":
                if set(identity) != {"kind", "sha256", "byte_length"}:
                    findings.append("VDD-PACKAGE-IDENTITY")
                elif repository_root is not None:
                    content_path = proof.get("content_path")
                    target = repository_root / content_path if isinstance(content_path, str) else None
                    if target is None or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != identity["sha256"] or target.stat().st_size != identity["byte_length"]:
                        findings.append("VDD-PACKAGE-IDENTITY")
            elif identity.get("kind") in {"generated-text", "external-text"}:
                if repository_root is not None and not text_identity(repository_root, proof, identity):
                    findings.append("VDD-PACKAGE-IDENTITY")
            else:
                findings.append("VDD-PACKAGE-IDENTITY")
                findings.append("VDD-PACKAGE-DIMENSION:immutable_identity")
            lineage = proof.get("lineage", {})
            status, predecessor, current = lineage.get("status"), lineage.get("predecessor"), proof_value(proof)
            expected = baseline.get(proof_id)
            valid_lineage = (
                (status == "new" and expected is None and predecessor is None)
                or (status == "unchanged" and expected is not None and current == expected and predecessor == expected)
                or (status == "supersedes" and expected is not None and current != expected and predecessor == expected)
            )
            if not valid_lineage:
                findings.append("VDD-PACKAGE-LINEAGE")
                findings.append("VDD-PACKAGE-DIMENSION:recovery_supersession")
    if closure_members and not closure_members.issubset(proof_ids):
        findings.append("VDD-PACKAGE-CLOSURE-MEMBER")
    if proofs and not (static_seen and runtime_seen):
        findings.append("VDD-PACKAGE-ARTIFACT-TYPE")
    proof_by_id = {
        proof.get("id"): proof
        for proof in proofs or []
        if isinstance(proof, dict) and isinstance(proof.get("id"), str)
    }
    in_closure_proof_ids = [
        proof["id"]
        for proof in proofs or []
        if isinstance(proof, dict)
        and isinstance(proof.get("id"), str)
        and proof.get("classification") == "IN-CLOSURE"
    ]
    inventory_in_closure_proof_ids = [
        member["proof_id"]
        for member in source_inventory or []
        if member["classification"] == "IN-CLOSURE"
    ]
    if (
        len(in_closure_proof_ids) != len(set(in_closure_proof_ids))
        or set(in_closure_proof_ids) != set(inventory_in_closure_proof_ids)
    ):
        findings.append("VDD-PACKAGE-SOURCE-PROOF")
    for member in source_inventory or []:
        proof = proof_by_id.get(member["proof_id"])
        if not isinstance(proof, dict):
            findings.append("VDD-PACKAGE-SOURCE-PROOF")
        proof_identity = proof.get("identity") if isinstance(proof, dict) else None
        observed_path = (
            proof_identity.get("path")
            if isinstance(proof_identity, dict) and proof_identity.get("kind") == "git-tracked"
            else proof.get("content_path") if isinstance(proof, dict) else None
        )
        if (
            not isinstance(proof, dict)
            or member["identity"] != proof_identity
            or member["canonical_path"] != observed_path
            or member["source_role"] != proof.get("source_role")
        ):
            findings.append("VDD-PACKAGE-SOURCE-IDENTITY")
    return sorted(set(findings))


def mutation_checks(package: dict) -> list[dict]:
    checks = []
    for dimension in DIMENSIONS:
        mutated = copy.deepcopy(package)
        proof = mutated["proofs"][0]
        if dimension == "schema_producer_authority":
            proof["producer_authority"]["path"] = "forged-producer"
        elif dimension == "immutable_identity":
            proof["identity"]["kind"] = "forged-identity"
        elif dimension == "source_of_truth_derivation":
            proof["derivation"]["source"] = proof["derivation"]["target"]
        elif dimension == "independent_recomputation":
            proof["recomputation"]["callable"] = "forged_validator"
        elif dimension == "staleness_propagation":
            proof["staleness"]["invalidates"] = []
        elif dimension == "recovery_supersession":
            proof["lineage"]["status"] = "supersedes"
            proof["lineage"]["predecessor"] = None
        else:
            proof["consumer_authorization"]["authorizes"] = ["release-ready"]
        findings = validate(mutated)
        rule = "VDD-PACKAGE-DIMENSION:" + dimension
        checks.append(
            {
                "dimension": dimension,
                "expected_rule_id": rule,
                "status": "rejected" if rule in findings else "failed",
            }
        )
    for mutation, rule in SOURCE_CLOSURE_MUTATION_EXPECTATIONS.items():
        mutated = copy.deepcopy(package)
        inventory = mutated["source_inventory"]
        if mutation == "source-omit":
            mutated["source_inventory"] = []
        elif mutation == "source-extra":
            member = copy.deepcopy(inventory[0])
            member["source_id"] = "source-mutation-extra"
            member["proof_id"] = "mutation-extra-proof"
            member["source_binding"]["binding_id"] = "PSB-mutation-extra"
            inventory.append(member)
            proof = copy.deepcopy(mutated["proofs"][0])
            proof["id"] = member["proof_id"]
            mutated["proofs"].append(proof)
        elif mutation == "source-identity-drift":
            inventory[0]["identity"] = copy.deepcopy(inventory[0]["identity"])
            inventory[0]["identity"]["kind"] = "forged-identity"
        elif mutation == "source-role-change":
            inventory[0]["source_role"] = "forged-role"
            inventory[0]["context_classes"] = ["forged-role"]
        elif mutation == "source-predicate-unlink":
            inventory[0]["applicable_predicates"] = ["unlinked-predicate"]
        elif mutation == "source-proof-unlink":
            inventory[0]["proof_id"] = "unlinked-source-proof"
        elif mutation == "source-binding-replay":
            if len(inventory) > 1:
                inventory[1]["source_binding"] = copy.deepcopy(inventory[0]["source_binding"])
            else:
                member = copy.deepcopy(inventory[0])
                member["source_id"] = "source-mutation-source_binding-replay"
                member["proof_id"] = "mutation-source_binding-replay-proof"
                inventory.append(member)
                proof = copy.deepcopy(mutated["proofs"][0])
                proof["id"] = member["proof_id"]
                mutated["proofs"].append(proof)
        else:
            inventory[0]["consumer"] = "copied-hash-consumer"
        findings = validate(mutated)
        checks.append(
            {
                "dimension": mutation,
                "expected_rule_id": rule,
                "status": "rejected" if rule in findings else "failed",
            }
        )
    return checks


def refresh_projections(package: dict, repository_root: Path, package_path: Path) -> list[str]:
    """Refresh only derived closure roots and observed file identities."""
    findings: list[str] = []
    for predicate, closure in package.get("predicate_closures", {}).items():
        if not isinstance(closure, dict) or not isinstance(closure.get("producer_members"), list):
            findings.append("VDD-PACKAGE-REFRESH:" + str(predicate))
            continue
        closure["members"] = sorted(set(closure["producer_members"]))
        closure["closure_root"] = canonical_hash(closure["members"])
    for proof in package.get("proofs", []):
        if not isinstance(proof, dict):
            findings.append("VDD-PACKAGE-REFRESH")
            continue
        identity = proof.get("identity", {})
        if identity.get("kind") == "git-tracked":
            observed = git_identity(repository_root, identity)
            if observed is None:
                findings.append("VDD-PACKAGE-REFRESH")
            else:
                identity["mode"], identity["blob"], _ = observed
        elif identity.get("kind") == "binary":
            content_path = proof.get("content_path")
            target = repository_root / content_path if isinstance(content_path, str) else None
            if target is None or not target.is_file():
                findings.append("VDD-PACKAGE-REFRESH")
            else:
                content = target.read_bytes()
                identity["sha256"] = hashlib.sha256(content).hexdigest()
                identity["byte_length"] = len(content)
        elif identity.get("kind") in {"generated-text", "external-text"}:
            content_path = proof.get("content_path")
            target = repository_root / content_path if isinstance(content_path, str) else None
            if target is None or not target.is_file():
                findings.append("VDD-PACKAGE-REFRESH")
            else:
                raw = target.read_bytes()
                try:
                    normalized = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
                except UnicodeDecodeError:
                    findings.append("VDD-PACKAGE-REFRESH")
                else:
                    identity["canonicalization_rule"] = "utf8-lf-v1"
                    identity["raw_sha256"] = "sha256:" + hashlib.sha256(raw).hexdigest()
                    identity["normalized_sha256"] = "sha256:" + hashlib.sha256(normalized).hexdigest()
    proof_by_id = {
        proof.get("id"): proof
        for proof in package.get("proofs", [])
        if isinstance(proof, dict) and isinstance(proof.get("id"), str)
    }
    for member in package.get("source_inventory", []):
        if not isinstance(member, dict):
            findings.append("VDD-PACKAGE-REFRESH")
            continue
        proof = proof_by_id.get(member.get("proof_id"))
        identity = proof.get("identity") if isinstance(proof, dict) else None
        content_path = (
            identity.get("path")
            if isinstance(identity, dict) and identity.get("kind") == "git-tracked"
            else proof.get("content_path") if isinstance(proof, dict) else None
        )
        if not isinstance(identity, dict) or not isinstance(content_path, str):
            findings.append("VDD-PACKAGE-REFRESH")
            continue
        member["identity"] = copy.deepcopy(identity)
        member["canonical_path"] = content_path
        member["source_role"] = proof.get("source_role")
    bindings = recompute_bindings(package, package_path)
    if bindings is None:
        findings.append("VDD-PACKAGE-REFRESH-BINDINGS")
    else:
        package["bindings"] = bindings
    return sorted(set(findings))


def validate_integration_registry(repository_root: Path, registry_path: Path) -> list[str]:
    registry = load(registry_path)
    if registry.get("schema_version") != "vdd.authorization-proof-package-integration.v1":
        return ["VDD-PACKAGE-INTEGRATION-SCHEMA"]
    fixtures = registry.get("fixtures")
    if not isinstance(fixtures, list) or {item.get("kind") for item in fixtures if isinstance(item, dict)} < {"golden", "integration"}:
        return ["VDD-PACKAGE-INTEGRATION-REGISTRY"]
    findings = []
    for item in fixtures:
        if not isinstance(item, dict) or item.get("expected_assurance") != "deterministic-package":
            findings.append("VDD-PACKAGE-INTEGRATION-ASSURANCE")
            continue
        if not (repository_root / item.get("package", "")).is_file():
            findings.append("VDD-PACKAGE-INTEGRATION-PATH")
        validator = item.get("validator")
        if item.get("kind") == "integration" and (not isinstance(validator, str) or not (repository_root / validator).is_file()):
            findings.append("VDD-PACKAGE-INTEGRATION-PATH")
            continue
        if item.get("kind") == "integration":
            arguments = item.get("arguments", [])
            if not isinstance(arguments, list) or any(not isinstance(value, str) for value in arguments):
                findings.append("VDD-PACKAGE-INTEGRATION-EXECUTION")
                continue
            command = [os.environ.get("PYTHON", os.sys.executable), str(repository_root / validator), *arguments]
            completed = subprocess.run(command, cwd=repository_root, capture_output=True, text=True, encoding="utf-8")
            if completed.returncode != 0:
                findings.append("VDD-PACKAGE-INTEGRATION-EXECUTION")
                continue
            try:
                result = json.loads(completed.stdout)
            except json.JSONDecodeError:
                findings.append("VDD-PACKAGE-INTEGRATION-RESULT")
                continue
            required_bindings = item.get("required_bindings")
            if (
                not isinstance(result, dict)
                or result.get("schema_version") != item.get("expected_result_schema")
                or result.get("predicate") != item.get("expected_predicate")
                or result.get("status") != item.get("expected_status")
                or not isinstance(required_bindings, list)
                or any(not isinstance(result.get(field), str) or not result[field].startswith("sha256:") for field in required_bindings)
                or result.get("candidate_hash") != result.get("current_candidate_hash")
            ):
                findings.append("VDD-PACKAGE-INTEGRATION-RESULT")
    return sorted(set(findings))


def legacy_read_only_result(package_path: Path, package: dict) -> dict:
    schema_version = package.get("schema_version")
    if (
        not isinstance(schema_version, str)
        or not schema_version.startswith("vdd.authorization-proof-package.")
        or schema_version == "vdd.authorization-proof-package.v1"
    ):
        raise ValueError("VDD-PACKAGE-LEGACY-ADAPTER: package is not a supported legacy package")
    return {
        "schema_version": "vdd.authorization-proof-package-legacy-read.v1",
        "status": "legacy_read_only",
        "source_schema_version": schema_version,
        "package_sha256": "sha256:" + hashlib.sha256(package_path.read_bytes()).hexdigest(),
        "authorizes": [],
        "does_not_authorize": [
            "deterministic-package-validation", "plan-ready", "phase-authorized",
            "implementation-accepted", "protected-handoff", "release-ready",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--integration-registry", type=Path)
    parser.add_argument("--external-envelope", type=Path)
    parser.add_argument("--root-registry", type=Path)
    parser.add_argument("--orchestrate", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--legacy-read-only", action="store_true")
    args = parser.parse_args()
    root = args.repository_root.resolve() if args.repository_root else None
    package = load(args.package)
    if args.legacy_read_only:
        if args.refresh or args.orchestrate or args.result is not None:
            raise ValueError("VDD-PACKAGE-LEGACY-ADAPTER: read-only mode cannot refresh, orchestrate, or write a result")
        print(json.dumps(legacy_read_only_result(args.package, package), indent=2))
        return 0
    findings = []
    if args.refresh:
        if root is None:
            findings.append("VDD-PACKAGE-REFRESH-ROOT")
        else:
            findings.extend(refresh_projections(package, root, args.package))
            if not findings:
                args.package.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8", newline="\n")
    findings.extend(validate(package, root, args.package))
    external_provenance = None
    if args.external_envelope is not None:
        registry = args.root_registry or ((root or Path.cwd()) / DEFAULT_ROOT_REGISTRY)
        external_findings, external_provenance = validate_external_envelope(args.external_envelope, registry, args.package)
        findings.extend(external_findings)
    if args.integration_registry is not None:
        findings = sorted(set(findings + validate_integration_registry((root or Path.cwd()), args.integration_registry)))
    mutations = mutation_checks(package) if args.orchestrate else []
    if any(item["status"] != "rejected" for item in mutations):
        findings.append("VDD-PACKAGE-MUTATION")
    status = "PASS" if not findings else "BLOCKED"
    checks = [
        {"rule_id": "VDD-PACKAGE-DIMENSION:" + dimension, "status": "pass" if status == "PASS" else "fail", "evidence": ["package-dimension-verdicts"]}
        for dimension in DIMENSIONS
    ]
    envelope = {"schema_version": "vdd.authorization-proof-package-result.v1", "assurance_level": "deterministic-package", "package_sha256": "sha256:" + hashlib.sha256(args.package.read_bytes()).hexdigest(), "validation_provenance": local_validation_provenance(args.package, external_provenance), "status": status, "findings": sorted(set(findings)), "checks": checks, "mutation_checks": mutations, "authorizes": [] if findings else ["deterministic-package-validation"], "does_not_authorize": ["fresh-context-observed", "cross-model-stability", "protected-handoff", "release-ready"], "generated_at": datetime.now(timezone.utc).isoformat()}
    if "signature" not in envelope["validation_provenance"]:
        envelope["findings"] = sorted(set(envelope["findings"] + ["VDD-PACKAGE-PROVENANCE-SIGNATURE"]))
        envelope["status"] = "BLOCKED"
        envelope["authorizes"] = []
    if isinstance(package.get("bindings"), dict):
        envelope.update({field: package["bindings"].get(field) for field in BINDING_FIELDS})
    if args.result is not None:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(envelope, indent=2))
    return 0 if envelope["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

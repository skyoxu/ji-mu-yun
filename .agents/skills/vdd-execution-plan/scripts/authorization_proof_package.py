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
) -> list[str]:
    try:
        envelope = load(envelope_path)
        registry = load(registry_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return ["VDD-PACKAGE-EXTERNAL-ENVELOPE"]
    if registry.get("schema_version") != "vdd.artifact-proof-roots.v1":
        return ["VDD-PACKAGE-ROOT-REGISTRY"]
    roots = registry.get("roots")
    if not isinstance(roots, dict):
        return ["VDD-PACKAGE-ROOT-REGISTRY"]
    root = roots.get(envelope.get("root_id"))
    if not isinstance(root, dict):
        return ["VDD-PACKAGE-EXTERNAL-ENVELOPE"]
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
        return ["VDD-PACKAGE-EXTERNAL-ENVELOPE"]
    return []


def local_validation_provenance(package_path: Path) -> dict:
    provenance = {
        "root_id": "vdd-local-deterministic",
        "signer": "repository-local-deterministic-runner",
        "validator_identity": "vdd.authorization_proof_package.validate.v1",
        "package_sha256": "sha256:" + hashlib.sha256(package_path.read_bytes()).hexdigest(),
    }
    signing_key = os.environ.get("VDD_AUTHORIZATION_PROOF_SIGNING_KEY")
    if signing_key:
        provenance["signature_algorithm"] = "hmac-sha256-v1"
        provenance["signature"] = hmac.new(
            signing_key.encode("utf-8"), canonical_hash(provenance).encode("ascii"), hashlib.sha256,
        ).hexdigest()
    return provenance


def discover_in_closure_proofs(package: dict, _predicate: str) -> list[str]:
    return sorted(
        proof["id"] for proof in package.get("proofs", [])
        if isinstance(proof, dict) and proof.get("classification") == "IN-CLOSURE"
    )


def discover_typed_proofs(package: dict, _predicate: str) -> list[str]:
    return sorted(
        proof["id"] for proof in package.get("proofs", [])
        if isinstance(proof, dict)
        and proof.get("classification") == "IN-CLOSURE"
        and proof.get("artifact_type") in {"static", "runtime"}
    )


DISCOVERY_ENTRYPOINTS = {
    "builtin:in-closure-proofs": discover_in_closure_proofs,
    "builtin:typed-proofs": discover_typed_proofs,
}


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


def validate(package: dict, repository_root: Path | None = None) -> list[str]:
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
    roles = package.get("roles")
    required_roles = ("normative", "projection", "execution")
    if not isinstance(roles, dict) or any(not roles.get(layer) for layer in required_roles):
        findings.append("VDD-PACKAGE-ROLES")
    semantic_contract = package.get("semantic_contract")
    if not isinstance(semantic_contract, dict):
        findings.append("VDD-PACKAGE-SEMANTIC-CONTRACT")
    else:
        try:
            trusted_semantic_contract = load(SEMANTIC_ROOT)
        except (OSError, ValueError, json.JSONDecodeError):
            findings.append("VDD-PACKAGE-SEMANTIC-ROOT")
        else:
            if semantic_contract != trusted_semantic_contract:
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
                or set(producer_entry) != {"id"}
                or set(verifier_entry) != {"id"}
                or producer_entry.get("id") == verifier_entry.get("id")
                or producer_entry.get("id") not in DISCOVERY_ENTRYPOINTS
                or verifier_entry.get("id") not in DISCOVERY_ENTRYPOINTS
            ):
                findings.append(rule)
                continue
            discovered_producer = DISCOVERY_ENTRYPOINTS[producer_entry["id"]](package, str(predicate))
            discovered_verifier = DISCOVERY_ENTRYPOINTS[verifier_entry["id"]](package, str(predicate))
            if not all(isinstance(value, list) for value in (declared, producer, verifier)):
                findings.append(rule)
                continue
            if (
                set(declared) != set(producer)
                or set(declared) != set(verifier)
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
    return checks


def refresh_projections(package: dict, repository_root: Path) -> list[str]:
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
    return sorted(set(findings))


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
    args = parser.parse_args()
    root = args.repository_root.resolve() if args.repository_root else None
    package = load(args.package)
    findings = []
    if args.refresh:
        if root is None:
            findings.append("VDD-PACKAGE-REFRESH-ROOT")
        else:
            findings.extend(refresh_projections(package, root))
            if not findings:
                args.package.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8", newline="\n")
    findings.extend(validate(package, root))
    if args.external_envelope is not None:
        registry = args.root_registry or ((root or Path.cwd()) / DEFAULT_ROOT_REGISTRY)
        findings.extend(validate_external_envelope(args.external_envelope, registry, args.package))
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
    envelope = {"schema_version": "vdd.authorization-proof-package-result.v1", "assurance_level": "deterministic-package", "package_sha256": "sha256:" + hashlib.sha256(args.package.read_bytes()).hexdigest(), "validation_provenance": local_validation_provenance(args.package), "status": status, "findings": sorted(set(findings)), "checks": checks, "mutation_checks": mutations, "authorizes": [] if findings else ["deterministic-package-validation"], "does_not_authorize": ["fresh-context-observed", "cross-model-stability", "protected-handoff", "release-ready"], "generated_at": datetime.now(timezone.utc).isoformat()}
    if isinstance(package.get("bindings"), dict):
        envelope.update({field: package["bindings"].get(field) for field in BINDING_FIELDS})
    if args.result is not None:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(envelope, indent=2))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())

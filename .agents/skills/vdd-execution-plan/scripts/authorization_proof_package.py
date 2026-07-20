#!/usr/bin/env python3
"""Portable, deterministic authorization-proof package validator and runner."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
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
    return None


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
            if not all(isinstance(value, list) for value in (declared, producer, verifier)):
                findings.append(rule)
                continue
            if set(declared) != set(producer) or set(declared) != set(verifier):
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
            else:
                findings.append("VDD-PACKAGE-IDENTITY")
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
    if closure_members and not closure_members.issubset(proof_ids):
        findings.append("VDD-PACKAGE-CLOSURE-MEMBER")
    if proofs and not (static_seen and runtime_seen):
        findings.append("VDD-PACKAGE-ARTIFACT-TYPE")
    return sorted(set(findings))


def mutation_checks(package: dict) -> list[dict]:
    checks = []
    for dimension in DIMENSIONS:
        mutated = copy.deepcopy(package)
        mutated["proofs"][0]["dimension_verdicts"][dimension] = "NON-AUTHORITATIVE"
        findings = validate(mutated)
        rule = "VDD-PACKAGE-DIMENSION:" + dimension
        checks.append({"dimension": dimension, "expected_rule": rule, "findings": findings, "rejected": rule in findings})
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
    return sorted(set(findings))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--integration-registry", type=Path)
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
    if args.integration_registry is not None:
        findings = sorted(set(findings + validate_integration_registry((root or Path.cwd()), args.integration_registry)))
    mutations = mutation_checks(package) if args.orchestrate else []
    if any(not item["rejected"] for item in mutations):
        findings.append("VDD-PACKAGE-MUTATION")
    status = "PASS" if not findings else "BLOCKED"
    checks = [
        {"rule_id": "VDD-PACKAGE-DIMENSION:" + dimension, "status": "pass" if status == "PASS" else "fail", "evidence": ["package-dimension-verdicts"]}
        for dimension in DIMENSIONS
    ]
    envelope = {"schema_version": "vdd.authorization-proof-package-result.v1", "assurance_level": "deterministic-package", "package_sha256": "sha256:" + hashlib.sha256(args.package.read_bytes()).hexdigest(), "status": status, "findings": sorted(set(findings)), "checks": checks, "mutation_checks": mutations, "authorizes": [] if findings else ["deterministic-package-validation"], "does_not_authorize": ["fresh-context-observed", "cross-model-stability", "protected-handoff", "release-ready"], "generated_at": datetime.now(timezone.utc).isoformat()}
    if isinstance(package.get("bindings"), dict):
        envelope.update({field: package["bindings"].get(field) for field in BINDING_FIELDS})
    if args.result is not None:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(envelope, indent=2))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path
from typing import Any

from artifact_proof_inventory_support import (
    close_uniform_inventory,
    refresh_runtime_type_contracts,
)


FAILURE_IDS = [
    "RMAP-ARTIFACT-PROOF-PRODUCER",
    "RMAP-ARTIFACT-PROOF-IDENTITY",
    "RMAP-ARTIFACT-PROOF-DERIVATION",
    "RMAP-ARTIFACT-PROOF-RULE",
    "RMAP-ARTIFACT-PROOF-STALENESS",
    "RMAP-ARTIFACT-PROOF-LINEAGE",
    "RMAP-ARTIFACT-PROOF-CONSUMER",
]

PREDICATES = [
    "plan-repair-verified",
    "plan-ready",
    "slice-ready",
    "implementation-candidate",
    "implementation-accepted",
]
DOES_NOT_AUTHORIZE = [
    "plan-repair-verified",
    "plan-ready",
    "slice-ready",
    "bootstrap-review",
    "implementation-candidate",
    "implementation-accepted",
    "protected-handoff",
    "release-ready",
]
DIMENSIONS = {
    "schema_producer_authority",
    "immutable_identity",
    "source_of_truth_derivation",
    "independent_recomputation",
    "staleness_propagation",
    "recovery_supersession",
    "consumer_authorization_boundary",
}
DIMENSION_RULES = {
    "schema_producer_authority": "RMAP-ARTIFACT-PROOF-PRODUCER",
    "immutable_identity": "RMAP-ARTIFACT-PROOF-IDENTITY",
    "source_of_truth_derivation": "RMAP-ARTIFACT-PROOF-DERIVATION",
    "independent_recomputation": "RMAP-ARTIFACT-PROOF-RULE",
    "staleness_propagation": "RMAP-ARTIFACT-PROOF-STALENESS",
    "recovery_supersession": "RMAP-ARTIFACT-PROOF-LINEAGE",
    "consumer_authorization_boundary": "RMAP-ARTIFACT-PROOF-CONSUMER",
}
TYPE_VALIDATOR_PATH = "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/artifact_proof_projection_support.py"
TYPE_VALIDATOR_CALLABLE = "validate_predicate_artifact_closure"


def _finding(rule_id: str, target: str, message: str) -> dict[str, str]:
    return {"rule_id": rule_id, "target": target, "message": message}


def _git(repository_root: Path, *args: str) -> bytes | None:
    result = subprocess.run(
        ["git", *args], cwd=repository_root, capture_output=True, check=False
    )
    return result.stdout if result.returncode == 0 else None


def _git_hash(repository_root: Path, revision: str, relative: str) -> str | None:
    value = _git(repository_root, "show", f"{revision}:{relative}")
    return None if value is None else "sha256:" + hashlib.sha256(value).hexdigest()


def _assignment(tree: ast.AST, owner: str, name: str) -> ast.AST | None:
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.Module)) or (
            isinstance(node, ast.FunctionDef) and node.name != owner
        ):
            continue
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.Assign, ast.AnnAssign)):
                targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                    return child.value
    return None


def discover_predicate_consumers(
    repository_root: Path, plan_root: Path, manifest: dict[str, Any]
) -> set[str]:
    prefix = plan_root.relative_to(repository_root).as_posix()
    validate_tree = ast.parse((plan_root / "tools" / "validate_all.py").read_text(encoding="utf-8"))
    names_node = _assignment(validate_tree, "validator_identity", "names")
    validator_names = {
        item.value for item in (names_node.elts if isinstance(names_node, ast.List) else [])
        if isinstance(item, ast.Constant) and isinstance(item.value, str)
    }
    rmap_tree = ast.parse((plan_root / "tools" / "rmap_checks.py").read_text(encoding="utf-8"))
    machine_node = _assignment(rmap_tree, "load_machine", "names")
    machine_inputs = {
        f"{prefix}/{item.value}" for item in (machine_node.values if isinstance(machine_node, ast.Dict) else [])
        if isinstance(item, ast.Constant) and isinstance(item.value, str)
    }
    required_node = _assignment(rmap_tree, "", "REQUIRED_FILES")
    required = {
        f"{prefix}/{item.value}"
        for item in (required_node.elts if isinstance(required_node, (ast.Set, ast.List, ast.Tuple)) else [])
        if isinstance(item, ast.Constant) and isinstance(item.value, str)
    }
    manifest_paths = {
        item["path"] for entries in manifest["categories"].values() for item in entries
    }
    tests = {
        f"{prefix}/tools/tests/{path.name}"
        for path in (plan_root / "tools" / "tests").glob("test_*.py")
    }
    validators = {f"{prefix}/tools/{name}" for name in validator_names}
    return manifest_paths | tests | validators | machine_inputs | required


def independently_discover_predicate_consumers(
    repository_root: Path, plan_root: Path, manifest: dict[str, Any]
) -> set[str]:
    prefix = plan_root.relative_to(repository_root).as_posix()
    validate_tree = ast.parse((plan_root / "tools" / "validate_all.py").read_text(encoding="utf-8"))
    validator_names: set[str] = set()
    for node in ast.walk(validate_tree):
        if isinstance(node, ast.FunctionDef) and node.name == "validator_identity":
            for child in ast.walk(node):
                if isinstance(child, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "names" for target in child.targets
                ) and isinstance(child.value, ast.List):
                    validator_names.update(
                        item.value for item in child.value.elts
                        if isinstance(item, ast.Constant) and isinstance(item.value, str)
                    )
    rmap_tree = ast.parse((plan_root / "tools" / "rmap_checks.py").read_text(encoding="utf-8"))
    machine_inputs: set[str] = set()
    required: set[str] = set()
    for node in ast.walk(rmap_tree):
        if isinstance(node, ast.FunctionDef) and node.name == "load_machine":
            for child in ast.walk(node):
                if isinstance(child, ast.Dict):
                    machine_inputs.update(
                        f"{prefix}/{item.value}" for item in child.values
                        if isinstance(item, ast.Constant) and isinstance(item.value, str)
                    )
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "REQUIRED_FILES" for target in node.targets
        ) and isinstance(node.value, (ast.Set, ast.List, ast.Tuple)):
            required.update(
                f"{prefix}/{item.value}" for item in node.value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            )
    manifest_paths = {
        item["path"] for entries in manifest["categories"].values() for item in entries
    }
    test_paths = {
        path.relative_to(repository_root).as_posix()
        for path in (plan_root / "tools" / "tests").glob("test_*.py")
    }
    validator_paths = {f"{prefix}/tools/{name}" for name in validator_names}
    return manifest_paths | test_paths | validator_paths | machine_inputs | required


def _artifact_type(relative: str, category: str) -> str:
    if "/tools/tests/" in relative or relative.endswith("/tests/test_bootstrap_review.py"):
        return "validator-test"
    if relative.endswith(".py"):
        return "validator"
    if category in {"intent_authority", "repository_rules", "architecture_authority", "protocol_authority", "review_policy_authority", "compatibility_inputs"}:
        return "external-trust-anchor"
    if category == "plan_books":
        return "static-normative"
    return "machine-contract"


def build_predicate_artifact_closure(
    repository_root: Path,
    plan_root: Path,
    manifest: dict[str, Any],
    baseline_commit: str,
) -> dict[str, Any]:
    prefix = plan_root.relative_to(repository_root).as_posix()
    categories = {
        item["path"]: category
        for category, entries in manifest["categories"].items()
        for item in entries
    }
    members = discover_predicate_consumers(repository_root, plan_root, manifest)
    plan_files = {
        path.relative_to(repository_root).as_posix()
        for path in plan_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }
    records = []
    for relative in sorted(members, key=str.casefold):
        current_hash = "sha256:" + hashlib.sha256((repository_root / relative).read_bytes()).hexdigest()
        predecessor = _git_hash(repository_root, baseline_commit, relative)
        lifecycle = "new" if predecessor is None else ("unchanged" if predecessor == current_hash else "supersedes")
        category = categories.get(relative, "derived-machine-owner")
        artifact_type = _artifact_type(relative, category)
        normative_owner = artifact_type in {"external-trust-anchor", "static-normative"}
        source_path = None if normative_owner else (
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/authority-manifest.v1.json"
            if relative in categories else
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/rmap_checks.py"
        )
        source_derivation = "N/A" if normative_owner else (
            "manifest-category-bound" if relative in categories else "consumer-discovered"
        )
        records.append({
            "path": relative,
            "classification": "IN-CLOSURE",
            "artifact_type": artifact_type,
            "type_contract_id": artifact_type,
            "producer_category": category,
            "source_path": source_path,
            "source_derivation": source_derivation,
            "source_reason_code": (
                "EXTERNAL_ROOT_AUTHORITY" if artifact_type == "external-trust-anchor"
                else "NORMATIVE_OWNER" if artifact_type == "static-normative" else None
            ),
            "lifecycle_status": lifecycle,
            "predecessor_sha256": None if lifecycle == "new" else predecessor,
            "invalidates": PREDICATES,
            "authorizes": [],
            "does_not_authorize": DOES_NOT_AUTHORIZE,
        })
    excluded = [{
        "path": relative,
        "classification": "OUT-OF-CLOSURE",
        "reason_code": "NOT_CONSUMED_BY_AUTHORIZING_PREDICATE",
        "machine_checks": ["not-read-by-validator", "not-in-predicate-hash", "authorizes-none"],
        "authorizes": [],
    } for relative in sorted(plan_files - members, key=str.casefold)]
    types = {}
    for artifact_type in sorted({item["artifact_type"] for item in records}):
        verdicts = {dimension: {"status": "PASS"} for dimension in sorted(DIMENSIONS)}
        if artifact_type in {"external-trust-anchor", "static-normative"}:
            verdicts["source_of_truth_derivation"] = {
                "status": "N/A",
                "reason_code": "EXTERNAL_ROOT_AUTHORITY" if artifact_type == "external-trust-anchor" else "NORMATIVE_OWNER",
                "reason": "The artifact is a normative authority owner rather than a derived projection.",
            }
        types[artifact_type] = {
            "dimension_verdicts": verdicts,
            "dimension_rules": DIMENSION_RULES,
            "validator_path": TYPE_VALIDATOR_PATH,
            "validator_callable": TYPE_VALIDATOR_CALLABLE,
        }
    member_paths = [item["path"] for item in records]
    excluded_paths = [item["path"] for item in excluded]
    return {
        "schema_version": "rmap.predicate-artifact-closure.v1",
        "plan_id": "repository-maintenance-tdd-adapter",
        "baseline_commit": baseline_commit,
        "type_contracts": types,
        "artifacts": records,
        "predicates": {
            predicate: {"members": member_paths, "excluded": excluded_paths}
            for predicate in PREDICATES
        },
        "excluded": excluded,
        "candidate_hash_scope": {"root": "repository", "members": member_paths},
    }


def validate_predicate_artifact_closure(
    repository_root: Path, closure: dict[str, Any]
) -> list[dict[str, str]]:
    plan_root = repository_root / "execution-plans" / "2026-07-15-repository-maintenance-tdd-adapter"
    try:
        import json
        manifest = json.loads((plan_root / "schemas" / "authority-manifest.v1.json").read_text(encoding="utf-8"))
        baseline = str(closure["baseline_commit"])
        members = independently_discover_predicate_consumers(repository_root, plan_root, manifest)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        return [_finding("RMAP-ARTIFACT-PROOF-CLOSURE", "predicate-artifact-closure", str(exc))]
    member_paths = sorted(members, key=str.casefold)
    actual_members = [item.get("path") for item in closure.get("artifacts", [])]
    if actual_members != member_paths:
        return [_finding("RMAP-ARTIFACT-PROOF-CLOSURE", "predicate-artifact-closure", "closure differs from independent consumer derivation")]
    if closure.get("candidate_hash_scope") != {"root": "repository", "members": member_paths}:
        return [_finding("RMAP-ARTIFACT-PROOF-IDENTITY", "predicate-artifact-closure", "candidate identity does not cover the complete closure")]
    if any(item.get("members") != member_paths for item in closure.get("predicates", {}).values()):
        return [_finding("RMAP-ARTIFACT-PROOF-CLOSURE", "predicate-artifact-closure", "predicate member projection is incomplete")]
    categories = {
        item["path"]: category for category, entries in manifest["categories"].items() for item in entries
    }
    by_path = {item["path"]: item for item in closure["artifacts"]}
    for relative, item in by_path.items():
        contract_id = item.get("type_contract_id")
        contract = closure["type_contracts"].get(contract_id, {})
        verdicts = contract.get("dimension_verdicts", {})
        if (
            contract_id != item.get("artifact_type")
            or set(verdicts) != DIMENSIONS
            or contract.get("dimension_rules") != DIMENSION_RULES
            or contract.get("validator_path") != TYPE_VALIDATOR_PATH
            or contract.get("validator_callable") != TYPE_VALIDATOR_CALLABLE
            or any(value.get("status") not in {"PASS", "N/A"} for value in verdicts.values())
        ):
            return [_finding("RMAP-ARTIFACT-PROOF-APPLICABILITY", relative, "typed seven-dimension verdict is incomplete")]
        expected_category = categories.get(relative, "derived-machine-owner")
        if item.get("producer_category") != expected_category:
            return [_finding("RMAP-ARTIFACT-PROOF-PRODUCER", relative, "producer category differs from independent authority inventory")]
        normative_owner = item.get("artifact_type") in {"external-trust-anchor", "static-normative"}
        expected_source = None if normative_owner else (
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/authority-manifest.v1.json"
            if relative in categories else
            "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/rmap_checks.py"
        )
        if item.get("source_path") != expected_source or (expected_source and not (repository_root / expected_source).is_file()):
            return [_finding("RMAP-ARTIFACT-PROOF-DERIVATION", relative, "source derivation is not bound to the independent inventory")]
        if normative_owner and item.get("source_reason_code") not in {"EXTERNAL_ROOT_AUTHORITY", "NORMATIVE_OWNER"}:
            return [_finding("RMAP-ARTIFACT-PROOF-DERIVATION", relative, "N/A reason is not authorized by the type contract")]
        if item["source_path"] == relative:
            return [_finding("RMAP-ARTIFACT-PROOF-DERIVATION", relative, "authorization closure member cannot derive from itself")]
        predecessor = item["predecessor_sha256"]
        current = "sha256:" + hashlib.sha256((repository_root / relative).read_bytes()).hexdigest()
        baseline_hash = _git_hash(repository_root, baseline, relative)
        expected_lifecycle = "new" if baseline_hash is None else ("unchanged" if baseline_hash == current else "supersedes")
        valid_lineage = (
            (item["lifecycle_status"] == "new" and predecessor is None)
            or (item["lifecycle_status"] == "unchanged" and predecessor == current)
            or (item["lifecycle_status"] == "supersedes" and predecessor not in {None, current})
        )
        if not valid_lineage or item.get("lifecycle_status") != expected_lifecycle or predecessor != (None if expected_lifecycle == "new" else baseline_hash):
            return [_finding("RMAP-ARTIFACT-PROOF-LINEAGE", relative, "baseline-bound lifecycle is invalid")]
        if item.get("invalidates") != PREDICATES:
            return [_finding("RMAP-ARTIFACT-PROOF-STALENESS", relative, "staleness does not invalidate every authorizing predicate")]
        if item.get("authorizes") != [] or item.get("does_not_authorize") != DOES_NOT_AUTHORIZE:
            return [_finding("RMAP-ARTIFACT-PROOF-CONSUMER", relative, "static closure member gained runtime authority")]
    return []


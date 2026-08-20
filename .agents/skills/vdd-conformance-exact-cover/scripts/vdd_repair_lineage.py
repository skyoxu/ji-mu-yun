"""Create a deterministic successor for an already accepted VDD repair chain.

This producer deliberately separates a reviewed semantic decision from the
validator and custody envelope that proves it is current.  It never calls a
model and never changes lifecycle state.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.toolchain.canonical_evidence import canonical_bytes, domain_hash


SCHEMA = "vdd-repair-lineage-successor.v1"
DOMAIN = "jimuyun.vdd-repair-lineage-successor.v1"
SUPPORTED_PREDECESSOR_REPAIR_INPUT_SCHEMAS = {"vdd-repair-input.v1"}
LINEAGE_REQUIRED_FIELDS = {
    "schema_version", "predecessor_repair_input", "predecessor_conformance", "predecessor_semantic_decision_hash",
    "semantic_decision_hash", "predecessor_validator_identity", "current_validator_identity",
    "predecessor_source_freeze", "current_predecessor_freeze", "predecessor_obligation_set_hash",
    "current_obligation_set_hash", "predecessor_semantic_fingerprint_root",
    "current_semantic_fingerprint_root", "selection_unchanged", "authority_unchanged",
    "semantic_inputs_unchanged", "mapping_decision_unchanged", "migration_reason",
    "current_reviewed_mapping", "current_repair_input", "validation_envelope_hash",
    "validation_envelope", "authorizes", "canonical_hash",
}


class LineageError(ValueError):
    """Typed deterministic repair-lineage failure."""


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise LineageError(f"module unavailable: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise LineageError("artifact escapes repository root") from exc


def artifact_ref(root: Path, path: Path) -> dict[str, str]:
    if not path.is_file():
        raise LineageError(f"artifact is missing: {path}")
    return {"path": _relative(root, path), "sha256": file_hash(path)}


def read_artifact(root: Path, ref: object, label: str) -> tuple[Path, dict[str, Any]]:
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise LineageError(f"{label}_invalid")
    raw_path, expected = ref.get("path"), ref.get("sha256")
    if not isinstance(raw_path, str) or not isinstance(expected, str):
        raise LineageError(f"{label}_invalid")
    path = (root / raw_path).resolve()
    if not path.is_file() or file_hash(path) != expected:
        raise LineageError(f"{label}_stale")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LineageError(f"{label}_unreadable") from exc
    if not isinstance(value, dict):
        raise LineageError(f"{label}_invalid")
    return path, value


def semantic_fingerprint(obligation: dict[str, Any]) -> str:
    """Hash semantic obligation content, intentionally excluding byte custody."""
    anchor = obligation.get("anchor")
    if not isinstance(anchor, dict):
        raise LineageError("obligation_drift")
    projection = {
        "obligation_id": obligation.get("obligation_id"),
        "source_path": obligation.get("source_path"),
        "role": obligation.get("role"),
        "kind": obligation.get("kind"),
        "quote": anchor.get("quote"),
        "acceptance_ids": obligation.get("acceptance_ids"),
    }
    if any(value is None for value in projection.values()):
        raise LineageError("obligation_drift")
    return domain_hash(f"{DOMAIN}.obligation-semantic.v1", projection)


def semantic_fingerprint_root(obligations: list[dict[str, Any]], identifiers: set[str]) -> str:
    values = [
        {"obligation_id": item["obligation_id"], "fingerprint": semantic_fingerprint(item)}
        for item in obligations if item.get("obligation_id") in identifiers
    ]
    values.sort(key=lambda item: item["obligation_id"])
    if {item["obligation_id"] for item in values} != identifiers:
        raise LineageError("obligation_drift")
    return domain_hash(f"{DOMAIN}.semantic-fingerprint-root.v1", values)


def requirements_semantic_identity(mapping: dict[str, Any]) -> str:
    requirements = mapping.get("requirements")
    if not isinstance(requirements, list):
        raise LineageError("source_semantic_drift")
    projection = []
    for item in requirements:
        if not isinstance(item, dict):
            raise LineageError("source_semantic_drift")
        projection.append({
            "id": item.get("id"),
            "acceptance_ids": item.get("acceptance_ids"),
            "obligation_ids": item.get("obligation_ids"),
            "slice": item.get("slice"),
        })
    projection.sort(key=lambda item: str(item["id"]))
    return domain_hash(f"{DOMAIN}.requirements-semantic.v1", projection)


def handoff_semantic_projection(handoff: object) -> dict[str, Any]:
    if not isinstance(handoff, dict):
        raise LineageError("predecessor_chain_invalid")
    return {
        "schema_version": handoff.get("schema_version"),
        "profile": handoff.get("profile"),
        "affected_obligation_ids": handoff.get("affected_obligation_ids"),
        "affected_requirement_ids": handoff.get("affected_requirement_ids"),
        "ambiguity_reason": handoff.get("ambiguity_reason"),
        "ambiguity_scope": handoff.get("ambiguity_scope"),
        "review_run_required": handoff.get("review_run_required"),
    }


def _role_graph(manifest: dict[str, Any]) -> list[dict[str, str]]:
    rows = manifest.get("sources")
    if not isinstance(rows, list):
        raise LineageError("authority_drift")
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise LineageError("authority_drift")
        result.append({key: row.get(key) for key in ("path", "role", "relationship", "sha256")})
    return result


def _approved_ids(mapping: dict[str, Any]) -> set[str]:
    records = mapping.get("approved_semantic_dispositions")
    if not isinstance(records, list) or not records:
        raise LineageError("predecessor_chain_invalid")
    identifiers: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or record.get("decision") != "not_applicable":
            raise LineageError("predecessor_chain_invalid")
        values = record.get("obligation_ids")
        if not isinstance(values, list) or not values or any(not isinstance(item, str) for item in values):
            raise LineageError("predecessor_chain_invalid")
        if identifiers.intersection(values):
            raise LineageError("predecessor_chain_invalid")
        identifiers.update(values)
    return identifiers


def _mapping_obligation_index(mapping: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = mapping.get("obligations")
    if not isinstance(items, list):
        raise LineageError("predecessor_chain_invalid")
    index = {item.get("obligation_id"): item for item in items if isinstance(item, dict)}
    if len(index) != len(items) or None in index:
        raise LineageError("predecessor_chain_invalid")
    return index


def _historic_chain(root: Path, predecessor_freeze: Path, predecessor_mapping: Path,
                    predecessor_review: Path, predecessor_repair: Path,
                    predecessor_conformance: Path) -> dict[str, Any]:
    """Validate immutable predecessor references without requiring old code bytes."""
    if any(not path.is_file() for path in (
        predecessor_freeze, predecessor_mapping, predecessor_review, predecessor_repair, predecessor_conformance,
    )):
        raise LineageError("predecessor_chain_invalid")
    freeze = json.loads(predecessor_freeze.read_text(encoding="utf-8"))
    mapping = json.loads(predecessor_mapping.read_text(encoding="utf-8"))
    repair = json.loads(predecessor_repair.read_text(encoding="utf-8"))
    review = json.loads(predecessor_review.read_text(encoding="utf-8"))
    conformance = json.loads(predecessor_conformance.read_text(encoding="utf-8"))
    if (
        freeze.get("schema_version") != "vdd-source-freeze-manifest.v1"
        or repair.get("schema_version") not in SUPPORTED_PREDECESSOR_REPAIR_INPUT_SCHEMAS
        or review.get("schema_version") != "vdd-review-run.v1"
        or repair.get("authorizes") != []
        or review.get("status") != "accepted"
    ):
        raise LineageError("predecessor_chain_invalid")
    frozen = repair.get("frozen_authority")
    if not isinstance(frozen, dict) or frozen.get("source_manifest") != artifact_ref(root, predecessor_freeze):
        raise LineageError("predecessor_chain_invalid")
    if repair.get("review_run") != artifact_ref(root, predecessor_review):
        raise LineageError("predecessor_chain_invalid")
    predecessor_validator = repair.get("validator")
    if not isinstance(predecessor_validator, dict) or set(predecessor_validator) != {"path", "sha256"}:
        raise LineageError("predecessor_chain_invalid")
    try:
        predecessor_validator_path = (root / predecessor_validator["path"]).resolve()
        predecessor_validator_path.relative_to(root.resolve())
    except (TypeError, ValueError) as exc:
        raise LineageError("predecessor_validator_unavailable") from exc
    # The old validator's content hash is intentionally not required to match:
    # a validator update is exactly the envelope change this successor repairs.
    if not predecessor_validator_path.is_file():
        raise LineageError("predecessor_validator_unavailable")
    if (
        conformance.get("schema_version") != "vdd-conformance-result.v1"
        or conformance.get("status") != "conformant"
        or conformance.get("errors") != []
        or conformance.get("authorizes") != []
        or conformance.get("requirements_manifest_hash") != artifact_ref(root, predecessor_mapping)["sha256"]
        or conformance.get("validator_identity") != predecessor_validator["sha256"]
    ):
        raise LineageError("predecessor_chain_invalid")
    handoff = repair.get("semantic_handoff")
    prior_path, _ = read_artifact(root, repair.get("prior_requirements_manifest"), "predecessor_requirements")
    predecessor_freeze_ref = artifact_ref(root, predecessor_freeze)
    if (
        not isinstance(handoff, dict)
        or review.get("semantic_handoff_hash") != repair.get("semantic_handoff_hash")
        or review.get("source_manifest_hash") != predecessor_freeze_ref["sha256"]
        or review.get("requirements_manifest_hash") != file_hash(prior_path)
        or handoff.get("frozen_authority", {}).get("source_manifest_hash") != predecessor_freeze_ref["sha256"]
        or handoff.get("requirements_manifest_hash") != file_hash(prior_path)
        or review.get("ambiguity_ids") != handoff.get("affected_obligation_ids")
        or review.get("affected_requirement_ids") != handoff.get("affected_requirement_ids")
    ):
        raise LineageError("predecessor_chain_invalid")
    if review.get("decision") != "accepted" or review.get("authorizes") != []:
        raise LineageError("predecessor_chain_invalid")
    return {"freeze": freeze, "mapping": mapping, "repair": repair, "review": review, "handoff": handoff,
            "conformance": conformance}


def _write_once(path: Path, value: dict[str, Any]) -> None:
    encoded = canonical_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != encoded:
            raise LineageError("generation_conflict")
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _current_handoff(conformance: Any, current_predecessor: Path, current_freeze: dict[str, Any],
                     prior_mapping: Path, predecessor_handoff: dict[str, Any]) -> dict[str, Any]:
    handoff = {
        **handoff_semantic_projection(predecessor_handoff),
        "frozen_authority": {
            "source_manifest_hash": file_hash(current_predecessor),
            "source_manifest_canonical_hash": current_freeze["canonical_hash"],
            "role_graph_hash": conformance.domain_hash("frozen_role_graph", current_freeze["sources"]),
        },
        "requirements_manifest_hash": file_hash(prior_mapping),
        "authorizes": [],
    }
    if set(handoff) != {
        "schema_version", "profile", "affected_obligation_ids", "affected_requirement_ids",
        "ambiguity_reason", "ambiguity_scope", "review_run_required", "frozen_authority",
        "requirements_manifest_hash", "authorizes",
    }:
        raise LineageError("predecessor_chain_invalid")
    return handoff


def successor(args: argparse.Namespace) -> dict[str, Any]:
    root = args.repository_root.resolve()
    conformance = _load_module("repair_lineage_conformance", root / ".agents/skills/vdd-conformance-exact-cover/scripts/conformance.py")
    source_freeze = _load_module("repair_lineage_source_freeze", root / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py")
    predecessor_freeze = args.predecessor_freeze.resolve()
    predecessor_mapping = args.predecessor_mapping.resolve()
    predecessor_review = args.predecessor_review.resolve()
    predecessor_repair = args.predecessor_repair_input.resolve()
    predecessor_conformance = args.predecessor_conformance.resolve()
    for path in (predecessor_freeze, predecessor_mapping, predecessor_review, predecessor_repair, predecessor_conformance, args.policy.resolve()):
        _relative(root, path)
    historic = _historic_chain(root, predecessor_freeze, predecessor_mapping, predecessor_review, predecessor_repair, predecessor_conformance)
    repair = historic["repair"]
    prior_path, prior_mapping = read_artifact(root, repair["prior_requirements_manifest"], "prior_requirements")
    if repair.get("repaired_requirements_manifest") != artifact_ref(root, predecessor_mapping):
        raise LineageError("predecessor_chain_invalid")
    if repair.get("policy") != artifact_ref(root, args.policy.resolve()):
        raise LineageError("review_policy_drift")
    current_validator = root / ".agents/skills/vdd-conformance-exact-cover/scripts/conformance.py"
    canonical_evidence = root / "scripts/toolchain/canonical_evidence/core.py"
    terminal_validator = root / "execution-plans/2026-08-13-vdd-conformance-exact-cover/tools/terminal_validation.py"
    preflight_validator = root / ".agents/skills/authorization/scripts/conformance_preflight.py"
    for path in (current_validator, canonical_evidence, terminal_validator, preflight_validator):
        if not path.is_file():
            raise LineageError("predecessor_validator_unavailable")
    output_root = args.out_dir.resolve()
    _relative(root, output_root)
    generation_seed = {
        "predecessor_repair": artifact_ref(root, predecessor_repair),
        "predecessor_mapping": artifact_ref(root, predecessor_mapping),
        "predecessor_conformance": artifact_ref(root, predecessor_conformance),
        "current_validator": artifact_ref(root, current_validator),
        "canonical_evidence": artifact_ref(root, canonical_evidence),
    }
    generation_id = domain_hash(f"{DOMAIN}.generation.v1", generation_seed).removeprefix("sha256:")[:24]
    generation = output_root / "generations" / generation_id
    current_predecessor = generation / "source-freeze-predecessor.v1.json"
    current_freeze = source_freeze.build_manifest(
        root, args.spec.resolve(), args.target_root, f"repair-lineage-{generation_id}-predecessor",
        None, artifact_ref(root, prior_path), None,
    )
    source_freeze.validate_manifest(root, current_freeze)
    _write_once(current_predecessor, current_freeze)
    old_freeze = historic["freeze"]
    if old_freeze.get("selection_hash") != current_freeze.get("selection_hash"):
        raise LineageError("authority_drift")
    if _role_graph(old_freeze) != _role_graph(current_freeze):
        raise LineageError("authority_drift")
    inventory = conformance.build_obligation_inventory(root, current_freeze)
    current_deferred = {item["obligation_id"] for item in inventory if item.get("status") == "deferred"}
    approved_ids = _approved_ids(historic["mapping"])
    if approved_ids != current_deferred:
        raise LineageError("obligation_drift")
    predecessor_index = _mapping_obligation_index(historic["mapping"])
    predecessor_semantic = [
        {**item, "status": "deferred"}
        for identifier, item in predecessor_index.items() if identifier in approved_ids
    ]
    predecessor_root = semantic_fingerprint_root(predecessor_semantic, approved_ids)
    current_root = semantic_fingerprint_root(inventory, approved_ids)
    if predecessor_root != current_root:
        raise LineageError("source_semantic_drift")
    for identifier in approved_ids:
        item = predecessor_index.get(identifier)
        if not isinstance(item, dict) or item.get("status") != "not_applicable" or item.get("mapping_kind") != "disposition":
            raise LineageError("semantic_rereview_required")
    prior_identity = requirements_semantic_identity(prior_mapping)
    semantic_decision = {
        "obligation_ids": sorted(approved_ids),
        "obligation_semantic_fingerprint_root": current_root,
        "prior_requirements_semantic_identity": prior_identity,
        "semantic_handoff": handoff_semantic_projection(historic["handoff"]),
        "review_decision": historic["review"].get("decision"),
        "policy_semantic_identity": artifact_ref(root, args.policy.resolve()),
    }
    semantic_decision_hash = domain_hash(f"{DOMAIN}.semantic-decision.v1", semantic_decision)
    current_handoff = _current_handoff(conformance, current_predecessor, current_freeze, prior_path, historic["handoff"])
    review_path = generation / "semantic-review-rebound.v1.json"
    review_value = {
        "schema_version": "vdd-review-run.v1", "status": "accepted",
        "semantic_handoff_hash": conformance.semantic_handoff_hash(current_handoff),
        "source_manifest_hash": file_hash(current_predecessor),
        "requirements_manifest_hash": file_hash(prior_path),
        "profile": current_handoff["profile"],
        "ambiguity_ids": current_handoff["affected_obligation_ids"],
        "affected_requirement_ids": current_handoff["affected_requirement_ids"],
        "decision": "accepted", "authorizes": [],
    }
    _write_once(review_path, review_value)
    reviewed_mapping = json.loads(json.dumps(historic["mapping"]))
    reviewed_mapping["approved_semantic_dispositions"] = [{
        "obligation_ids": record["obligation_ids"], "decision": "not_applicable",
        "review_run": artifact_ref(root, review_path),
        "prior_requirements_manifest": artifact_ref(root, prior_path),
        "semantic_handoff": current_handoff,
        "semantic_handoff_hash": conformance.semantic_handoff_hash(current_handoff),
    } for record in reviewed_mapping["approved_semantic_dispositions"]]
    reviewed_mapping["semantic_decision_hash"] = semantic_decision_hash
    reviewed_path = generation / "requirements-acceptance-reviewed.v3.json"
    _write_once(reviewed_path, reviewed_mapping)
    result = {
        "status": "requirement_semantic_review_required", "authorizes": [],
        "semantic_handoff": current_handoff,
        "source_manifest_hash": file_hash(current_predecessor),
        "requirements_manifest_hash": file_hash(prior_path),
    }
    repair_value = conformance.build_repair_input(
        root, result, current_predecessor, prior_path, review_path, reviewed_path,
        args.policy.resolve(), f"repair-lineage-{generation_id}", ["semantic-disposition-only"],
    )
    repair_path = generation / "vdd-repair-input.v3.json"
    _write_once(repair_path, repair_value)
    validation_envelope = {
        "validator": artifact_ref(root, current_validator),
        "canonical_evidence": artifact_ref(root, canonical_evidence),
        "current_predecessor_freeze": artifact_ref(root, current_predecessor),
        "current_reviewed_mapping": artifact_ref(root, reviewed_path),
        "current_repair_input": artifact_ref(root, repair_path),
        "policy": artifact_ref(root, args.policy.resolve()),
        "terminal_validator": artifact_ref(root, terminal_validator),
        "preflight_validator": artifact_ref(root, preflight_validator),
    }
    lineage_body = {
        "schema_version": SCHEMA,
        "predecessor_repair_input": artifact_ref(root, predecessor_repair),
        "predecessor_conformance": artifact_ref(root, predecessor_conformance),
        "predecessor_semantic_decision_hash": domain_hash(f"{DOMAIN}.semantic-decision.v1", {
            **semantic_decision, "obligation_semantic_fingerprint_root": predecessor_root,
        }),
        "semantic_decision_hash": semantic_decision_hash,
        "predecessor_validator_identity": repair["validator"],
        "current_validator_identity": artifact_ref(root, current_validator),
        "predecessor_source_freeze": artifact_ref(root, predecessor_freeze),
        "current_predecessor_freeze": artifact_ref(root, current_predecessor),
        "predecessor_obligation_set_hash": domain_hash(f"{DOMAIN}.obligation-set.v1", sorted(approved_ids)),
        "current_obligation_set_hash": domain_hash(f"{DOMAIN}.obligation-set.v1", sorted(current_deferred)),
        "predecessor_semantic_fingerprint_root": predecessor_root,
        "current_semantic_fingerprint_root": current_root,
        "selection_unchanged": True, "authority_unchanged": True,
        "semantic_inputs_unchanged": True, "mapping_decision_unchanged": True,
        "migration_reason": "validator-and-canonical-evidence-validation-envelope-refresh",
        "current_reviewed_mapping": artifact_ref(root, reviewed_path),
        "current_repair_input": artifact_ref(root, repair_path),
        "validation_envelope_hash": domain_hash(f"{DOMAIN}.validation-envelope.v1", validation_envelope),
        "validation_envelope": validation_envelope,
        "authorizes": [],
    }
    lineage = {
        **lineage_body,
        "canonical_hash": domain_hash(f"{DOMAIN}.artifact.v1", lineage_body),
    }
    if set(lineage) != LINEAGE_REQUIRED_FIELDS:
        raise LineageError("predecessor_chain_invalid")
    lineage_path = generation / "repair-lineage-successor.v1.json"
    _write_once(lineage_path, lineage)
    successor_freeze = source_freeze.build_manifest(
        root, args.spec.resolve(), args.target_root, f"repair-lineage-{generation_id}-successor",
        artifact_ref(root, repair_path), artifact_ref(root, reviewed_path), artifact_ref(root, lineage_path),
    )
    source_freeze.validate_manifest(root, successor_freeze)
    successor_freeze_path = generation / "source-freeze-successor.v3.json"
    _write_once(successor_freeze_path, successor_freeze)
    conformance_result = conformance.validate_conformance(root, successor_freeze_path, reviewed_path)
    if conformance_result.get("status") != "conformant" or conformance_result.get("authorizes") != []:
        raise LineageError("semantic_rereview_required")
    conformance_path = generation / "conformance-result.v3.json"
    _write_once(conformance_path, conformance_result)
    preflight_path = generation / "authorization-preflight.v3.json"
    command = [
        sys.executable, str(root / ".agents/skills/authorization/scripts/conformance_preflight.py"),
        "--receipt", str(conformance_path), "--manifest", str(successor_freeze_path),
        "--mapping", str(reviewed_path), "--validator", str(current_validator),
    ]
    completed = subprocess.run(command, cwd=root, check=False, capture_output=True, text=True, encoding="utf-8")
    preflight = {"status": "preflight_passed" if completed.returncode == 0 else "blocked", "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip(), "authorizes": []}
    if completed.returncode:
        raise LineageError("preflight_blocked")
    _write_once(preflight_path, preflight)
    pointer = {
        "schema_version": "vdd-repair-lineage-current.v1", "generation_id": generation_id,
        "repair_lineage_successor": artifact_ref(root, lineage_path),
        "reviewed_mapping": artifact_ref(root, reviewed_path),
        "repair_input": artifact_ref(root, repair_path),
        "source_freeze": artifact_ref(root, successor_freeze_path),
        "conformance_result": artifact_ref(root, conformance_path),
        "authorization_preflight": artifact_ref(root, preflight_path), "authorizes": [],
    }
    _write_once(output_root / "repair-lineage-current.v1.json", pointer)
    return {"status": "conformant", "generation_id": generation_id, "pointer": artifact_ref(root, output_root / "repair-lineage-current.v1.json"), "authorizes": []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("successor")
    create.add_argument("--repository-root", type=Path, required=True)
    create.add_argument("--spec", type=Path, required=True)
    create.add_argument("--target-root", required=True)
    create.add_argument("--predecessor-freeze", type=Path, required=True)
    create.add_argument("--predecessor-mapping", type=Path, required=True)
    create.add_argument("--predecessor-review", type=Path, required=True)
    create.add_argument("--predecessor-repair-input", type=Path, required=True)
    create.add_argument("--predecessor-conformance", type=Path, required=True)
    create.add_argument("--policy", type=Path, required=True)
    create.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = successor(args)
    except (OSError, TypeError, KeyError, json.JSONDecodeError, LineageError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc), "authorizes": []}, separators=(",", ":")))
        return 2
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

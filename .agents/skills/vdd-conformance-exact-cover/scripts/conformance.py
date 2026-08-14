"""Read-only deterministic exact-cover and recovery primitives."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Iterable


DOMAIN = "jimuyun.vdd-exact-cover"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def domain_hash(name: str, value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes({"domain": f"{DOMAIN}.{name}.v1", "payload": value})).hexdigest()


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def exact_cover(requirements: Iterable[dict[str, Any]], acceptance_ids: Iterable[str], reverse_mapping: dict[str, list[str]]) -> dict[str, Any]:
    rows = list(requirements)
    raw_acceptance = list(acceptance_ids)
    acceptance = sorted(set(raw_acceptance))
    requirement_ids = {row.get("id") for row in rows}
    errors: list[dict[str, str]] = []
    if len(raw_acceptance) != len(acceptance):
        errors.append({"family": "deterministic_coverage_gap", "code": "duplicate_acceptance"})
    if len(requirement_ids) != len(rows) or None in requirement_ids:
        errors.append({"family": "deterministic_coverage_gap", "code": "duplicate_requirement"})
    if set(reverse_mapping) != set(acceptance):
        errors.append({"family": "deterministic_coverage_gap", "code": "acceptance_universe_mismatch"})
    for row in rows:
        rid = row.get("id")
        bound = row.get("acceptance_ids")
        if not isinstance(rid, str) or not isinstance(bound, list) or not bound:
            errors.append({"family": "deterministic_coverage_gap", "code": "requirement_binding_invalid"})
            continue
        for aid in bound:
            if aid not in acceptance or rid not in reverse_mapping.get(aid, []):
                errors.append({"family": "deterministic_coverage_gap", "code": "wrong_binding"})
    for aid in acceptance:
        if not reverse_mapping.get(aid):
            errors.append({"family": "deterministic_coverage_gap", "code": "orphan_acceptance"})
    return {"schema_version": "vdd-conformance-result.v1", "status": "blocked" if errors else "conformant", "errors": errors, "authorizes": []}


def shard_id(manifest_path: str, source_sha256: str, start_byte: int, end_byte: int) -> str:
    raw_hash = source_sha256.removeprefix("sha256:")
    payload = f"vcec-shard-v1\n{manifest_path}\n{raw_hash}\n{start_byte}\n{end_byte}\n".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def aggregate_fingerprint(payload: dict[str, Any]) -> str:
    required = {"source_manifest_hash", "requirements_manifest_hash", "validator_identity", "prompt_identity", "policy_identity", "authoritative_companions"}
    if set(payload) != required:
        raise ValueError("aggregate fingerprint payload is incomplete")
    return domain_hash("run_aggregate_fingerprint", payload)


def shard_reuse_fingerprint(payload: dict[str, Any]) -> str:
    required = {"shard_identity", "source_segments", "roles", "relationships", "requirements_manifest_hash", "validator_identity", "prompt_identity", "policy_identity"}
    if set(payload) != required:
        raise ValueError("shard reuse fingerprint payload is incomplete")
    return domain_hash("shard_reuse_fingerprint", payload)


def bounded_summary(value: dict[str, Any]) -> dict[str, Any]:
    result = {**value, "serialized_utf8_bytes": 0, "estimated_tokens_v1": 0, "measurement_mode": "estimated", "measurement_method": "utf8-bytes-ceil-div-4-v1", "truncated": False, "authorizes": []}
    for _ in range(4):
        size = len((json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
        result["serialized_utf8_bytes"] = size
        result["estimated_tokens_v1"] = (size + 3) // 4
    final_size = len((json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
    if final_size != result["serialized_utf8_bytes"]:
        raise ValueError("model-visible output size did not converge")
    if final_size > 12000:
        raise ValueError("model-visible output exceeds 12000 UTF-8 bytes")
    return result


def append_checkpoint(path: Path, checkpoint: dict[str, Any]) -> None:
    required = {"schema_version", "run_id", "branch_id", "sequence", "stage", "state", "validator_identity", "policy_identity", "artifact_refs", "attempt_binding", "shard_states", "live_blocker", "next_legal_actions", "authorizes"}
    if set(checkpoint) != required or checkpoint.get("schema_version") != "recovery-checkpoint.v1" or checkpoint.get("authorizes") != []:
        raise ValueError("checkpoint schema or authority is invalid")
    if not isinstance(checkpoint["run_id"], str) or not checkpoint["run_id"] or not isinstance(checkpoint["branch_id"], str) or not checkpoint["branch_id"]:
        raise ValueError("checkpoint run or branch identity is invalid")
    if not isinstance(checkpoint["sequence"], int) or isinstance(checkpoint["sequence"], bool) or checkpoint["sequence"] < 0:
        raise ValueError("checkpoint sequence is invalid")
    artifacts = checkpoint["artifact_refs"]
    if not isinstance(artifacts, list) or artifacts != sorted(artifacts, key=lambda item: (item.get("role", ""), item.get("path", ""))):
        raise ValueError("checkpoint artifact references are incomplete or unsorted")
    if path.exists():
        raise ValueError("checkpoint publication is create-new only")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def resolve_runtime_policy(registry_path: Path, policy_id: str | None = None) -> dict[str, Any]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if registry.get("schema_version") != "vdd-conformance-runtime-policy-registry.v1" or registry.get("authorizes") != []:
        raise ValueError("runtime policy registry is invalid")
    selected_id = policy_id or registry.get("current_policy_id")
    policy = next((item for item in registry.get("policies", []) if item.get("policy_id") == selected_id), None)
    if not isinstance(policy, dict) or policy.get("status") != "approved" or policy.get("authorizes") != []:
        raise ValueError("runtime policy is not approved")
    maxima, actions = policy.get("retry_maximums"), policy.get("exhaustion_actions")
    expected = {"timeout", "transport_failure", "obligation_extraction_invalid", "obligation_extraction_unstable"}
    if not isinstance(maxima, dict) or not isinstance(actions, dict) or set(maxima) != expected or set(actions) != expected:
        raise ValueError("runtime policy retry contract is incomplete")
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in maxima.values()):
        raise ValueError("runtime policy retry maximum is invalid")
    if any(not isinstance(value, str) or not value for value in actions.values()):
        raise ValueError("runtime policy exhaustion action is invalid")
    return policy


def retry_decision(family: str, attempt: int, maximum: int, operation_id: str, exhaustion_action: str | None = None) -> dict[str, Any]:
    retryable = {"timeout", "transport_failure", "obligation_extraction_invalid", "obligation_extraction_unstable"}
    if family not in retryable or maximum <= 0 or attempt < 1 or not operation_id:
        return {"status": "blocked", "family": "schema_error", "action": "repair_manifest", "authorizes": []}
    identity = domain_hash("attempt", {"family": family, "attempt": attempt, "operation_id": operation_id})
    if attempt < maximum:
        action = "rerun_changed_shards" if family.startswith("obligation_extraction") else "retry_transport"
        return {"status": "retry", "family": family, "action": action, "attempt_identity": identity, "authorizes": []}
    action = exhaustion_action or ("inspect_extraction" if family.startswith("obligation_extraction") else "inspect_transport")
    return {"status": "blocked", "family": family, "action": action, "attempt_identity": identity, "authorizes": []}


def _load_vdd_source_freeze(root: Path):
    path = root / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py"
    spec = importlib.util.spec_from_file_location("exact_cover_vdd_source_freeze", path)
    if spec is None or spec.loader is None:
        raise ValueError("VDD source-freeze validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ACTIVE_OBLIGATION_ROLES = {"canonical", "normative_companion", "adopted_companion", "repository_authority"}


def _obligation_id(source: dict[str, Any], number: int, line: str) -> str:
    if line.startswith("| `VCEC-"):
        identifier = line.split("`", 2)[1]
        if identifier.startswith("VCEC-") and identifier[5:].isdigit():
            return identifier
    identity = domain_hash("source_obligation", {
        "path": source["path"], "sha256": source["sha256"], "line": number, "quote": line,
    }).removeprefix("sha256:")
    return f"OBL-{identity}"


def build_obligation_inventory(root: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a complete deterministic active universe from the frozen role graph.

    Every non-blank line from an active authority source is retained. This is
    deliberately conservative: an unclassified source line cannot disappear
    merely because an extractor did not recognize its prose as normative.
    """
    rows: list[dict[str, Any]] = []
    for source in manifest["sources"]:
        if source["role"] not in ACTIVE_OBLIGATION_ROLES:
            continue
        path = root / source["path"]
        for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.rstrip()
            if not line:
                continue
            rows.append({
                "obligation_id": _obligation_id(source, number, line),
                "source_path": source["path"],
                "source_sha256": source["sha256"],
                "role": source["role"],
                "anchor": {"line_start": number, "line_end": number, "quote": line},
                "kind": "constraint",
                "status": "active",
                "disposition": None,
            })
    rows.sort(key=lambda item: (item["source_path"], item["anchor"]["line_start"], item["obligation_id"]))
    identifiers = [item["obligation_id"] for item in rows]
    if not rows or len(identifiers) != len(set(identifiers)):
        raise ValueError("frozen obligation inventory is empty or duplicated")
    return rows


def acceptance_obligations(root: Path, manifest: dict[str, Any]) -> set[str]:
    source = next(
        (item for item in manifest["sources"] if item["path"].endswith("/acceptance-contract.md") and item["role"] in {"normative_companion", "adopted_companion"}),
        None,
    )
    if source is None:
        raise ValueError("frozen authority lacks acceptance-contract companion")
    values: set[str] = set()
    for line in (root / source["path"]).read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `VCEC-A"):
            continue
        identifier = line.split("`", 2)[1]
        if not identifier.startswith("VCEC-A") or not identifier[6:].isdigit():
            raise ValueError("frozen acceptance identifier is invalid")
        if identifier in values:
            raise ValueError("frozen acceptance identifier is duplicated")
        values.add(identifier)
    if not values:
        raise ValueError("frozen acceptance obligations are missing")
    return values


def _mapping_obligation_errors(mapping: dict[str, Any], inventory: list[dict[str, Any]]) -> list[dict[str, str]]:
    provided = mapping.get("obligations")
    requirements = mapping.get("requirements")
    if not isinstance(provided, list) or not isinstance(requirements, list):
        return [{"family": "deterministic_coverage_gap", "code": "frozen_obligation_universe_mismatch"}]
    expected = {item["obligation_id"]: item for item in inventory}
    actual: dict[str, dict[str, Any]] = {}
    for item in provided:
        if not isinstance(item, dict) or not isinstance(item.get("obligation_id"), str):
            return [{"family": "deterministic_coverage_gap", "code": "obligation_record_invalid"}]
        identifier = item["obligation_id"]
        if identifier in actual:
            return [{"family": "deterministic_coverage_gap", "code": "duplicate_obligation"}]
        actual[identifier] = item
    if set(actual) != set(expected):
        return [{"family": "deterministic_coverage_gap", "code": "frozen_obligation_universe_mismatch"}]
    requirement_index = {item.get("id"): item for item in requirements if isinstance(item, dict)}
    claims: dict[str, set[str]] = {identifier: set() for identifier in expected}
    errors: list[dict[str, str]] = []
    for identifier, expected_item in expected.items():
        item = actual[identifier]
        projection = {key: value for key, value in item.items() if key != "requirement_ids"}
        if projection != expected_item:
            errors.append({"family": "deterministic_coverage_gap", "code": "obligation_source_binding_mismatch"})
            continue
        requirement_ids = item.get("requirement_ids")
        if not isinstance(requirement_ids, list) or not requirement_ids or len(requirement_ids) != len(set(requirement_ids)):
            errors.append({"family": "deterministic_coverage_gap", "code": "obligation_requirement_binding_invalid"})
            continue
        for requirement_id in requirement_ids:
            requirement = requirement_index.get(requirement_id)
            if not isinstance(requirement, dict) or identifier not in requirement.get("obligation_ids", []):
                errors.append({"family": "deterministic_coverage_gap", "code": "wrong_obligation_requirement_binding"})
                continue
            claims[identifier].add(requirement_id)
    for requirement in requirement_index.values():
        obligation_ids = requirement.get("obligation_ids")
        if not isinstance(obligation_ids, list) or len(obligation_ids) != len(set(obligation_ids)) or any(item not in expected for item in obligation_ids):
            errors.append({"family": "deterministic_coverage_gap", "code": "requirement_obligation_binding_invalid"})
            continue
        for identifier in obligation_ids:
            if requirement["id"] not in actual[identifier].get("requirement_ids", []):
                errors.append({"family": "deterministic_coverage_gap", "code": "wrong_obligation_requirement_binding"})
    if any(not values for values in claims.values()):
        errors.append({"family": "deterministic_coverage_gap", "code": "uncovered_obligation"})
    return errors


def _semantic_handoff(mapping: dict[str, Any], inventory: list[dict[str, Any]]) -> dict[str, Any] | None:
    review = mapping.get("semantic_review", [])
    if review is None:
        review = []
    if not isinstance(review, list):
        raise ValueError("semantic review handoff is invalid")
    if not review:
        return None
    valid = {item["obligation_id"] for item in inventory}
    affected: set[str] = set()
    for item in review:
        if not isinstance(item, dict) or set(item) != {"obligation_ids", "reason", "profile", "target_plan"}:
            raise ValueError("semantic review handoff is invalid")
        identifiers = item["obligation_ids"]
        if not isinstance(identifiers, list) or not identifiers or any(not isinstance(value, str) or value not in valid for value in identifiers):
            raise ValueError("semantic review obligations are invalid")
        if item["profile"] != "bootstrap-upstream-plan" or any(not isinstance(item[key], str) or not item[key] for key in ("reason", "target_plan")):
            raise ValueError("semantic review routing is invalid")
        affected.update(identifiers)
    return {"profile": "bootstrap-upstream-plan", "obligation_ids": sorted(affected), "authorizes": []}


def validate_conformance(root: Path, manifest_path: Path, mapping_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _load_vdd_source_freeze(root).validate_manifest(root, manifest)
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    result = exact_cover(mapping["requirements"], mapping["acceptance_ids"], mapping["reverse_mapping"])
    obligations = build_obligation_inventory(root, manifest)
    expected_ids = {
        item["obligation_id"] for item in obligations
        if item["obligation_id"].startswith("VCEC-")
    }
    actual_ids = {item.get("id") for item in mapping["requirements"]}
    expected_acceptance_ids = acceptance_obligations(root, manifest)
    actual_acceptance_ids = set(mapping["acceptance_ids"])
    if expected_ids != actual_ids:
        result = {
            **result,
            "status": "blocked",
            "errors": [*result["errors"], {"family": "deterministic_coverage_gap", "code": "frozen_obligation_universe_mismatch"}],
        }
    if expected_acceptance_ids != actual_acceptance_ids:
        result = {
            **result,
            "status": "blocked",
            "errors": [*result["errors"], {"family": "deterministic_coverage_gap", "code": "frozen_acceptance_universe_mismatch"}],
        }
    mapping_errors = _mapping_obligation_errors(mapping, obligations)
    if mapping_errors:
        result = {**result, "status": "blocked", "errors": [*result["errors"], *mapping_errors]}
    handoff = _semantic_handoff(mapping, obligations)
    if result["status"] == "conformant" and handoff is not None:
        result = {**result, "status": "requirement_semantic_review_required", "semantic_handoff": handoff}
    return bounded_summary({
        **result,
        "source_manifest_hash": file_hash(manifest_path),
        "source_manifest_canonical_hash": manifest["canonical_hash"],
        "requirements_manifest_hash": file_hash(mapping_path),
        "validator_identity": file_hash(Path(__file__)),
        "obligation_count": len(obligations),
        "obligation_inventory_hash": domain_hash("obligation_inventory", obligations),
        "acceptance_count": len(expected_acceptance_ids),
        "acceptance_inventory_hash": domain_hash("acceptance_inventory", sorted(expected_acceptance_ids)),
    })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--repository-root", type=Path)
    args = parser.parse_args()
    try:
        if args.manifest is None or args.repository_root is None:
            data = json.loads(args.mapping.read_text(encoding="utf-8"))
            result = exact_cover(data["requirements"], data["acceptance_ids"], data["reverse_mapping"])
        else:
            result = validate_conformance(args.repository_root.resolve(), args.manifest.resolve(), args.mapping.resolve())
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "family": "schema_error", "detail": str(exc), "authorizes": []}))
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["status"] == "conformant" else 2


if __name__ == "__main__":
    raise SystemExit(main())

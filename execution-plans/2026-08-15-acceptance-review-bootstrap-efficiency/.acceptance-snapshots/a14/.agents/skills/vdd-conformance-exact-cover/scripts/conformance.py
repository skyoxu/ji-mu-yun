"""Read-only deterministic exact-cover and recovery primitives."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Iterable

from scripts.toolchain.canonical_evidence import canonical_bytes, domain_hash as _domain_hash


DOMAIN = "jimuyun.vdd-exact-cover"


def domain_hash(name: str, value: Any) -> str:
    return _domain_hash(f"{DOMAIN}.{name}.v1", value)


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
    result = {**value, "serialized_utf8_bytes": 0, "estimated_tokens_v1": 0, "measurement_mode": "estimated", "measurement_method": "utf8-bytes-ceil-div-4-v1", "truncated": bool(value.get("truncated", False)), "authorizes": []}
    for _ in range(8):
        size = len((json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
        result["serialized_utf8_bytes"] = size
        result["estimated_tokens_v1"] = (size + 3) // 4
    final_size = len((json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
    if final_size > 12000 and not result["truncated"]:
        errors = result.get("errors")
        if isinstance(errors, list) and len(errors) > 20:
            result["errors"] = errors[:20]
            result["omitted_items"] = len(errors) - 20
            result["truncated"] = True
        handoff = result.get("semantic_handoff")
        if isinstance(handoff, dict) and len(handoff.get("affected_obligation_ids", [])) > 100:
            original_count = len(handoff["affected_obligation_ids"])
            handoff["affected_obligation_ids"] = handoff["affected_obligation_ids"][:100]
            handoff["omitted_affected_obligation_ids"] = original_count - 100
            result["truncated"] = True
        for _ in range(8):
            final_size = len((json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
            result["serialized_utf8_bytes"] = final_size
            result["estimated_tokens_v1"] = (final_size + 3) // 4
    if final_size != result["serialized_utf8_bytes"]:
        result["serialized_utf8_bytes"] = final_size
        result["estimated_tokens_v1"] = (final_size + 3) // 4
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
_REQUIREMENT_ID = re.compile(r"`(VCEC-\d{3})`")
_ACCEPTANCE_ID = re.compile(r"`(VCEC-A\d{2})`")
_NORMATIVE_MARKER = re.compile(r"\b(must|must not|never|only|required|requires|shall)\b|必须|不得|只能|禁止|需要")


def _obligation_id(source: dict[str, Any], number: int, line: str) -> str:
    if line.startswith("| `VCEC-"):
        identifier = line.split("`", 2)[1]
        if identifier.startswith("VCEC-") and identifier[5:].isdigit():
            return identifier
    identity = domain_hash("source_obligation", {
        "path": source["path"], "sha256": source["sha256"], "line": number, "quote": line,
    }).removeprefix("sha256:")
    return f"OBL-{identity}"


def _disposition(source: dict[str, Any], line_number: int, reason: str, target_root: str) -> dict[str, str]:
    return {
        "reason": reason,
        "authority_reference": f"{source['path']}:{line_number}",
        "target_plan": target_root,
    }


def semantic_handoff_hash(handoff: dict[str, Any]) -> str:
    payload = {"domain": "jimuyun.vdd-semantic-handoff.v1", "payload": handoff}
    return "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _validate_review_envelope(handoff: dict[str, Any], review: object) -> None:
    if not isinstance(review, dict) or set(review) != {
        "schema_version", "status", "semantic_handoff_hash", "source_manifest_hash",
        "requirements_manifest_hash", "profile", "ambiguity_ids",
        "affected_requirement_ids", "decision", "authorizes",
    }:
        raise ValueError("review run envelope is incomplete")
    if (
        review["schema_version"] != "vdd-review-run.v1"
        or review["status"] != "accepted"
        or review["decision"] != "accepted"
        or review["profile"] != handoff["profile"]
        or review["authorizes"] != []
        or review["semantic_handoff_hash"] != semantic_handoff_hash(handoff)
        or review["source_manifest_hash"] != handoff["frozen_authority"]["source_manifest_hash"]
        or review["requirements_manifest_hash"] != handoff["requirements_manifest_hash"]
        or sorted(review["ambiguity_ids"]) != sorted(handoff["affected_obligation_ids"])
        or sorted(review["affected_requirement_ids"]) != sorted(handoff["affected_requirement_ids"])
    ):
        raise ValueError("review run is not bound to the current semantic handoff")


def _approved_semantic_dispositions(
    root: Path, mapping: dict[str, Any], inventory: list[dict[str, Any]], manifest: dict[str, Any], manifest_path: Path
) -> set[str]:
    records = mapping.get("approved_semantic_dispositions", [])
    if records is None:
        records = []
    if not isinstance(records, list):
        raise ValueError("approved semantic dispositions are invalid")
    valid = {item["obligation_id"]: item for item in inventory}
    approved: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {
            "obligation_ids", "decision", "review_run", "prior_requirements_manifest",
            "semantic_handoff", "semantic_handoff_hash",
        }:
            raise ValueError("approved semantic disposition record is invalid")
        identifiers = record["obligation_ids"]
        if (
            not isinstance(identifiers, list) or not identifiers
            or any(not isinstance(value, str) or value not in valid for value in identifiers)
            or record["decision"] != "not_applicable"
            or approved.intersection(identifiers)
            or any(valid[value]["status"] != "deferred" for value in identifiers)
        ):
            raise ValueError("approved semantic disposition binding is invalid")
        handoff = record["semantic_handoff"]
        if not isinstance(handoff, dict) or handoff.get("schema_version") != "vdd-requirement-semantic-handoff.v1":
            raise ValueError("approved semantic disposition handoff is invalid")
        repair_binding = manifest.get("repair_input")
        if not isinstance(repair_binding, dict) or set(repair_binding) != {"path", "sha256"}:
            raise ValueError("approved semantic disposition requires an explicit VDD repair manifest")
        repair_value = json.loads((root / repair_binding["path"]).read_text(encoding="utf-8"))
        source_ref = repair_value.get("frozen_authority", {}).get("source_manifest")
        if not isinstance(source_ref, dict):
            raise ValueError("approved semantic disposition repair source authority is invalid")
        source_ref = _contained_artifact(root, Path(source_ref["path"]), "source manifest")
        prior_ref = _contained_artifact(root, Path(record["prior_requirements_manifest"]["path"]), "prior requirements manifest")
        if sorted(handoff.get("affected_obligation_ids", [])) != sorted(identifiers):
            raise ValueError("approved semantic disposition obligations are incomplete")
        if handoff.get("requirements_manifest_hash") != prior_ref["sha256"]:
            raise ValueError("approved semantic disposition prior requirements are stale")
        if handoff.get("frozen_authority", {}).get("source_manifest_hash") != source_ref["sha256"]:
            raise ValueError("approved semantic disposition source authority is stale")
        if record["semantic_handoff_hash"] != semantic_handoff_hash(handoff):
            raise ValueError("approved semantic disposition handoff hash is stale")
        review_path = Path(record["review_run"]["path"])
        review = json.loads((root / review_path).read_text(encoding="utf-8"))
        _validate_review_envelope(handoff, review)
        approved.update(identifiers)
    return approved


def _classify_obligation(source: dict[str, Any], line_number: int, line: str, target_root: str) -> dict[str, Any]:
    """Classify source text without promoting document structure to requirements.

    Canonical IDs are authoritative identity bindings. Other imperative prose
    is retained as a typed deferred boundary; it cannot be silently promoted to
    a generic requirement and needs explicit VDD review before activation.
    """
    acceptance_ids = sorted(set(_ACCEPTANCE_ID.findall(line)))
    direct_requirements = sorted(set(_REQUIREMENT_ID.findall(line)))
    if line.startswith("#"):
        return {"kind": "workflow", "status": "not_applicable", "disposition": _disposition(source, line_number, "Markdown heading is structural context, not a standalone obligation.", target_root), "acceptance_ids": []}
    if line.startswith("|") and ("---" in line or line.startswith("| ID |") or line.startswith("| Role |") or line.startswith("| Field |")):
        return {"kind": "constraint", "status": "not_applicable", "disposition": _disposition(source, line_number, "Markdown table header or separator is structural context.", target_root), "acceptance_ids": []}
    if acceptance_ids and not direct_requirements:
        return {"kind": "constraint", "status": "not_applicable", "disposition": _disposition(source, line_number, "Acceptance definition is consumed as an acceptance record, not a separate requirement obligation.", target_root), "acceptance_ids": []}
    if "`VCEC-NG" in line:
        return {"kind": "non_goal", "status": "deferred", "disposition": _disposition(source, line_number, "Non-goal prose is retained as a typed deferred boundary and is not a deliverable obligation.", target_root), "acceptance_ids": []}
    if direct_requirements:
        return {"kind": "workflow" if "workflow" in line.casefold() or "流程" in line else "behavior", "status": "active", "disposition": None, "acceptance_ids": acceptance_ids}
    if _NORMATIVE_MARKER.search(line):
        return {"kind": "workflow" if "workflow" in line.casefold() or "流程" in line else "constraint", "status": "deferred", "disposition": _disposition(source, line_number, "Imperative prose lacks a stable canonical requirement ID; activation requires an explicit VDD semantic review and repair.", target_root), "acceptance_ids": []}
    return {"kind": "constraint", "status": "not_applicable", "disposition": _disposition(source, line_number, "Explanatory source text has no standalone normative operator or canonical requirement identifier.", target_root), "acceptance_ids": []}


def build_obligation_inventory(root: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a complete deterministic active universe from the frozen role graph.

    Every non-blank line is retained with a typed classification. Structural and
    explanatory lines receive a complete named disposition; imperative prose
    without a canonical requirement reference is deferred, never silently
    mapped to a generic requirement.
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
            classification = _classify_obligation(source, number, line, manifest["target_root"])
            rows.append({
                "obligation_id": _obligation_id(source, number, line),
                "source_path": source["path"],
                "source_sha256": source["sha256"],
                "role": source["role"],
                "anchor": {"line_start": number, "line_end": number, "quote": line},
                **classification,
            })
    requirement_acceptance: dict[str, set[str]] = {}
    for row in rows:
        if row["status"] != "active":
            continue
        for requirement_id in _REQUIREMENT_ID.findall(row["anchor"]["quote"]):
            requirement_acceptance.setdefault(requirement_id, set()).update(row["acceptance_ids"])
    for row in rows:
        if row["status"] != "active":
            continue
        requirement_ids = _REQUIREMENT_ID.findall(row["anchor"]["quote"])
        if requirement_ids:
            row["acceptance_ids"] = sorted({acceptance_id for requirement_id in requirement_ids for acceptance_id in requirement_acceptance.get(requirement_id, set())})
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


def _mapping_obligation_errors(
    root: Path, mapping: dict[str, Any], inventory: list[dict[str, Any]], manifest: dict[str, Any], manifest_path: Path
) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]], set[str]]:
    provided = mapping.get("obligations")
    requirements = mapping.get("requirements")
    if not isinstance(provided, list) or not isinstance(requirements, list):
        return [{"family": "deterministic_coverage_gap", "code": "frozen_obligation_universe_mismatch"}], {}, set()
    expected = {item["obligation_id"]: item for item in inventory}
    actual: dict[str, dict[str, Any]] = {}
    for item in provided:
        if not isinstance(item, dict) or not isinstance(item.get("obligation_id"), str):
            return [{"family": "deterministic_coverage_gap", "code": "obligation_record_invalid"}], {}, set()
        identifier = item["obligation_id"]
        if identifier in actual:
            return [{"family": "deterministic_coverage_gap", "code": "duplicate_obligation"}], {}, set()
        actual[identifier] = item
    if set(actual) != set(expected):
        return [{"family": "deterministic_coverage_gap", "code": "frozen_obligation_universe_mismatch"}], {}, set()
    requirement_index = {item.get("id"): item for item in requirements if isinstance(item, dict)}
    claims: dict[str, set[str]] = {
        identifier: set() for identifier, item in expected.items() if item["status"] == "active"
    }
    errors: list[dict[str, str]] = []
    try:
        approved = _approved_semantic_dispositions(root, mapping, inventory, manifest, manifest_path)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return [{"family": "deterministic_coverage_gap", "code": "semantic_disposition_invalid"}], actual, set()
    for identifier, expected_item in expected.items():
        item = actual[identifier]
        projection = {key: value for key, value in item.items() if key not in {"requirement_ids", "mapping_kind", "merge_reason"}}
        expected_projection = {**expected_item, "status": "not_applicable"} if identifier in approved else expected_item
        if projection != expected_projection:
            errors.append({"family": "deterministic_coverage_gap", "code": "obligation_source_binding_mismatch"})
            continue
        requirement_ids = item.get("requirement_ids")
        acceptance_ids = item.get("acceptance_ids")
        mapping_kind = item.get("mapping_kind")
        merge_reason = item.get("merge_reason")
        if expected_item["status"] != "active":
            if expected_item["status"] == "deferred" and identifier in approved and item.get("status") != "not_applicable":
                errors.append({"family": "deterministic_coverage_gap", "code": "approved_disposition_not_applied"})
                continue
            if requirement_ids != [] or acceptance_ids != [] or mapping_kind != "disposition" or not isinstance(merge_reason, str) or not merge_reason:
                errors.append({"family": "deterministic_coverage_gap", "code": "disposition_mapping_invalid"})
            continue
        if not isinstance(requirement_ids, list) or not requirement_ids or len(requirement_ids) != len(set(requirement_ids)):
            errors.append({"family": "deterministic_coverage_gap", "code": "obligation_requirement_binding_invalid"})
            continue
        if mapping_kind not in {"identity", "semantic_equivalence"} or not isinstance(merge_reason, str) or not merge_reason:
            errors.append({"family": "deterministic_coverage_gap", "code": "obligation_mapping_kind_invalid"})
            continue
        expected_acceptance = sorted({acceptance_id for requirement_id in requirement_ids for acceptance_id in requirement_index.get(requirement_id, {}).get("acceptance_ids", [])})
        if not isinstance(acceptance_ids, list) or acceptance_ids != expected_acceptance or not acceptance_ids:
            errors.append({"family": "deterministic_coverage_gap", "code": "obligation_acceptance_binding_invalid"})
            continue
        direct_ids = sorted(set(_REQUIREMENT_ID.findall(expected_item["anchor"]["quote"])))
        if direct_ids and (mapping_kind != "identity" or sorted(requirement_ids) != direct_ids):
            errors.append({"family": "deterministic_coverage_gap", "code": "deterministically_provable_weakening"})
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
    return errors, actual, approved


def _semantic_handoff(
    mapping: dict[str, Any], inventory: list[dict[str, Any]], manifest_path: Path,
    manifest: dict[str, Any], mapping_path: Path, approved: set[str]
) -> dict[str, Any] | None:
    review = mapping.get("semantic_review", [])
    if review is None:
        review = []
    if not isinstance(review, list):
        raise ValueError("semantic review handoff is invalid")
    valid = {item["obligation_id"] for item in inventory}
    mapping_index = {item.get("obligation_id"): item for item in mapping.get("obligations", []) if isinstance(item, dict)}
    required = {
        identifier for identifier, item in mapping_index.items()
        if identifier in valid and item.get("status") == "active" and item.get("mapping_kind") == "semantic_equivalence"
    }
    required.update(
        item["obligation_id"] for item in inventory
        if item["status"] == "deferred" and item["obligation_id"] not in approved
    )
    if not required and not review:
        return None
    affected: set[str] = set()
    requirements: set[str] = set()
    reasons: list[str] = []
    scopes: list[str] = []
    for item in review:
        if not isinstance(item, dict) or set(item) != {"obligation_ids", "requirement_ids", "reason", "scope", "profile", "target_plan"}:
            raise ValueError("semantic review handoff is invalid")
        identifiers = item["obligation_ids"]
        if not isinstance(identifiers, list) or not identifiers or any(not isinstance(value, str) or value not in valid for value in identifiers):
            raise ValueError("semantic review obligations are invalid")
        if item["profile"] != "bootstrap-upstream-plan" or any(not isinstance(item[key], str) or not item[key] for key in ("reason", "scope", "target_plan")):
            raise ValueError("semantic review routing is invalid")
        if not isinstance(item["requirement_ids"], list) or not item["requirement_ids"] or any(not isinstance(value, str) for value in item["requirement_ids"]):
            raise ValueError("semantic review requirements are invalid")
        for identifier in identifiers:
            mapped = mapping_index.get(identifier, {})
            if mapped.get("status") == "active" and mapped.get("mapping_kind") != "semantic_equivalence":
                raise ValueError("semantic review cannot override a deterministic identity binding")
            if mapped.get("status") not in {"deferred", "conflict", "active"}:
                raise ValueError("semantic review obligation is not eligible")
        affected.update(identifiers)
        requirements.update(item["requirement_ids"])
        reasons.append(item["reason"])
        scopes.append(item["scope"])
    uncovered = sorted(required - affected)
    if uncovered:
        reasons.append("Frozen normative prose lacks a stable canonical requirement ID and has no approved disposition.")
        scopes.append("Bootstrap upstream VDD semantic review must decide applicability or repair the requirements manifest.")
        affected.update(uncovered)
    if not required.issubset(affected):
        raise ValueError("semantic review must cover every semantic-equivalence obligation")
    return {
        "schema_version": "vdd-requirement-semantic-handoff.v1",
        "profile": "bootstrap-upstream-plan",
        "frozen_authority": {
            "source_manifest_hash": file_hash(manifest_path),
            "source_manifest_canonical_hash": manifest["canonical_hash"],
            "role_graph_hash": domain_hash("frozen_role_graph", manifest["sources"]),
        },
        "affected_obligation_ids": sorted(affected),
        "affected_requirement_ids": sorted(requirements),
        "ambiguity_reason": " | ".join(sorted(set(reasons))),
        "ambiguity_scope": " | ".join(sorted(set(scopes))),
        "review_run_required": True,
        "requirements_manifest_hash": file_hash(mapping_path),
        "authorizes": [],
    }


def _contained_artifact(root: Path, path: Path, label: str) -> dict[str, str]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the repository") from exc
    if not resolved.is_file():
        raise ValueError(f"{label} is missing")
    return {"path": relative, "sha256": file_hash(resolved)}


def build_repair_input(
    root: Path,
    result: dict[str, Any],
    manifest_path: Path,
    mapping_path: Path,
    review_run_path: Path,
    repaired_requirements_path: Path,
    policy_path: Path,
    repair_id: str,
    allowed_repair_scope: list[str],
) -> dict[str, Any]:
    """Create the exact-cover-owned, non-mutating VDD repair handoff."""
    if result.get("status") != "requirement_semantic_review_required" or result.get("authorizes") != []:
        raise ValueError("repair input requires a current semantic-review conformance result")
    if not isinstance(repair_id, str) or not repair_id or not isinstance(allowed_repair_scope, list) or not allowed_repair_scope or any(not isinstance(item, str) or not item for item in allowed_repair_scope):
        raise ValueError("repair input identity or scope is invalid")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _load_vdd_source_freeze(root).validate_manifest(root, manifest)
    source_manifest = _contained_artifact(root, manifest_path, "source manifest")
    prior_requirements = _contained_artifact(root, mapping_path, "prior requirements manifest")
    review_run = _contained_artifact(root, review_run_path, "review run")
    review = json.loads(review_run_path.read_text(encoding="utf-8"))
    handoff = result.get("semantic_handoff")
    if not isinstance(handoff, dict) or result.get("truncated") or handoff.get("omitted_affected_obligation_ids"):
        raise ValueError("repair input requires a complete semantic handoff")
    _validate_review_envelope(handoff, review)
    repaired = _contained_artifact(root, repaired_requirements_path, "repaired requirements manifest")
    if repaired == prior_requirements:
        raise ValueError("repair input must bind a new requirements identity")
    validator = _contained_artifact(root, Path(__file__), "validator")
    policy = _contained_artifact(root, policy_path, "policy")
    ambiguity_ids: list[str] = []
    affected_requirement_ids: list[str] = []
    ambiguity: list[dict[str, Any]] = []
    ambiguity_ids = list(handoff.get("affected_obligation_ids", []))
    affected_requirement_ids = list(handoff.get("affected_requirement_ids", []))
    ambiguity = [{
        "obligation_ids": ambiguity_ids,
        "requirement_ids": affected_requirement_ids,
        "reason": handoff.get("ambiguity_reason"),
        "scope": handoff.get("ambiguity_scope"),
    }]
    if result.get("source_manifest_hash") != source_manifest["sha256"] or result.get("requirements_manifest_hash") != prior_requirements["sha256"]:
        raise ValueError("repair input conformance result is stale")
    return {
        "schema_version": "vdd-repair-input.v1",
        "repair_id": repair_id,
        "target_root": manifest["target_root"],
        "frozen_authority": {
            "source_manifest": source_manifest,
            "source_manifest_canonical_hash": manifest["canonical_hash"],
            "role_graph_hash": domain_hash("frozen_role_graph", manifest["sources"]),
        },
        "semantic_handoff": handoff,
        "semantic_handoff_hash": semantic_handoff_hash(handoff),
        "review_run": review_run,
        "prior_requirements_manifest": prior_requirements,
        "repaired_requirements_manifest": repaired,
        "validator": validator,
        "policy": policy,
        "ambiguity_ids": ambiguity_ids,
        "affected_requirement_ids": affected_requirement_ids,
        "ambiguity": ambiguity,
        "allowed_repair_scope": allowed_repair_scope,
        "authorizes": [],
    }


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
    requirements_identity = manifest.get("requirements_manifest")
    if requirements_identity is not None and (
        not isinstance(requirements_identity, dict)
        or requirements_identity.get("path") != mapping_path.resolve().relative_to(root.resolve()).as_posix()
        or requirements_identity.get("sha256") != file_hash(mapping_path)
    ):
        result = {**result, "status": "blocked", "errors": [*result["errors"], {"family": "deterministic_coverage_gap", "code": "requirements_identity_mismatch"}]}
    mapping_errors, _mapping_index, approved = _mapping_obligation_errors(root, mapping, obligations, manifest, manifest_path)
    if mapping_errors:
        result = {**result, "status": "blocked", "errors": [*result["errors"], *mapping_errors]}
    handoff = _semantic_handoff(mapping, obligations, manifest_path, manifest, mapping_path, approved)
    if result["status"] == "conformant" and handoff is not None:
        result = {**result, "status": "requirement_semantic_review_required", "semantic_handoff": handoff}
    try:
        full_artifact_path = mapping_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        full_artifact_path = mapping_path.resolve().as_posix()
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
        "full_artifact": {"path": full_artifact_path, "sha256": file_hash(mapping_path)},
    })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--repair-input-out", type=Path)
    parser.add_argument("--repair-id")
    parser.add_argument("--review-run", type=Path)
    parser.add_argument("--repaired-requirements-manifest", type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--allowed-repair-scope", action="append", default=[])
    args = parser.parse_args()
    try:
        if args.manifest is None or args.repository_root is None:
            data = json.loads(args.mapping.read_text(encoding="utf-8"))
            result = exact_cover(data["requirements"], data["acceptance_ids"], data["reverse_mapping"])
        else:
            result = validate_conformance(args.repository_root.resolve(), args.manifest.resolve(), args.mapping.resolve())
        if args.repair_input_out:
            if not all((args.repository_root, args.manifest, args.repair_id, args.review_run, args.repaired_requirements_manifest, args.policy)):
                raise ValueError("repair input publication requires the complete explicit handoff contract")
            repair_input = build_repair_input(
                args.repository_root.resolve(), result, args.manifest.resolve(), args.mapping.resolve(),
                args.review_run.resolve(), args.repaired_requirements_manifest.resolve(), args.policy.resolve(),
                args.repair_id, args.allowed_repair_scope,
            )
            if args.repair_input_out.exists():
                raise ValueError("repair input output is append-only")
            args.repair_input_out.parent.mkdir(parents=True, exist_ok=True)
            args.repair_input_out.write_bytes(canonical_bytes(repair_input) + b"\n")
            print(json.dumps({"status": "repair_input_created", "repair_input_hash": file_hash(args.repair_input_out), "authorizes": []}, ensure_ascii=False, separators=(",", ":")))
            return 0
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "family": "schema_error", "detail": str(exc), "authorizes": []}))
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["status"] == "conformant" else 2


if __name__ == "__main__":
    raise SystemExit(main())

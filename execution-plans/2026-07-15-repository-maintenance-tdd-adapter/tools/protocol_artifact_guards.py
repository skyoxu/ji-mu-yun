from __future__ import annotations

import fnmatch
import hashlib
import json
from pathlib import PurePosixPath
from typing import Any


PATH_TYPES = {"repo_path", "plan_path", "run_path"}


def finding(rule_id: str, target: str, message: str) -> dict[str, str]:
    return {"rule_id": rule_id, "target": target, "message": message}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def bytes_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def value_hash(value: Any) -> str:
    return bytes_hash(canonical_bytes(value))


def safe_relative(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and not any(":" in part for part in path.parts)


def ref_key(ref: dict[str, Any]) -> tuple[str, str, str]:
    return str(ref.get("role", "")), str(ref.get("path_type", "")), str(ref.get("path", ""))


def store_key(ref: dict[str, Any]) -> tuple[str, str]:
    return str(ref.get("path_type", "")), str(ref.get("path", ""))


def validate_ref(
    ref: Any,
    store: dict[tuple[str, str], bytes],
    target: str,
    *,
    role_required: bool = True,
) -> list[dict[str, str]]:
    if not isinstance(ref, dict):
        return [finding("RMAP-PROTOCOL-ARTIFACT", target, "artifact reference is not an object")]
    required = {"path_type", "path", "sha256"} | ({"role"} if role_required else set())
    if set(ref) != required or ref.get("path_type") not in PATH_TYPES or not safe_relative(ref.get("path")):
        return [finding("RMAP-PROTOCOL-PATH", target, "artifact reference has an ambiguous or escaping typed root")]
    payload = store.get(store_key(ref))
    if payload is None or bytes_hash(payload) != ref.get("sha256"):
        return [finding("RMAP-PROTOCOL-ARTIFACT", target, "artifact reference is missing or stale against actual bytes")]
    return []


def capsule_artifact_refs(capsule: dict[str, Any]) -> list[dict[str, Any]]:
    refs = [
        *capsule.get("authority_refs", []),
        capsule.get("implementation_contract"),
        capsule.get("baseline_ref"),
        *capsule.get("stage_evidence_refs", []),
    ]
    blocker = capsule.get("latest_blocker_ref")
    if blocker is not None:
        refs.append(blocker)
    return [ref for ref in refs if isinstance(ref, dict)]


def validate_context_artifacts(
    context: dict[str, Any],
    capsule: dict[str, Any],
    store: dict[tuple[str, str], bytes],
) -> list[dict[str, str]]:
    capsule_ref = context.get("capsule_ref")
    findings = validate_ref(capsule_ref, store, "context.capsule_ref")
    expected = capsule_artifact_refs(capsule)
    actual = context.get("artifact_refs")
    if not isinstance(actual, list):
        return findings + [finding("RMAP-CAPSULE-ARTIFACT-CLOSURE", "context.artifact_refs", "artifact_refs is not a list")]
    expected_keys = [ref_key(ref) for ref in expected]
    actual_keys = [ref_key(ref) for ref in actual if isinstance(ref, dict)]
    if len(actual_keys) != len(set(actual_keys)):
        findings.append(finding("RMAP-CAPSULE-ARTIFACT-CLOSURE", "context.artifact_refs", "artifact references contain duplicate role/path identities"))
    if sorted(actual_keys) != sorted(expected_keys) or any(
        next((candidate for candidate in expected if ref_key(candidate) == ref_key(ref)), None) != ref
        for ref in actual
        if isinstance(ref, dict)
    ):
        findings.append(finding("RMAP-CAPSULE-ARTIFACT-CLOSURE", "context.artifact_refs", "context manifest is not the exact deduplicated union of Capsule references"))
    for index, ref in enumerate(actual):
        findings.extend(validate_ref(ref, store, f"context.artifact_refs[{index}]"))
    capsule_hash = bytes_hash(store.get(store_key(capsule_ref), b"")) if isinstance(capsule_ref, dict) else ""
    if context.get("context_hash") != value_hash({"capsule_hash": capsule_hash, "artifact_refs": actual}):
        findings.append(finding("RMAP-CAPSULE-CONTEXT", "context.context_hash", "context hash does not bind the exact byte-verified closure"))
    return findings


def matches_any(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/").casefold()
    return any(fnmatch.fnmatchcase(normalized, pattern.replace("\\", "/").casefold()) for pattern in patterns)


def classify_scope(path: str, boundaries: dict[str, Any]) -> str:
    if matches_any(path, boundaries.get("forbidden_write_set", [])):
        return "forbidden"
    if matches_any(path, boundaries.get("allowed_write_set", [])):
        return "allowed"
    return "unrelated"

"""Immutable authority projections and segment descriptors for Bootstrap review."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any

from scripts.toolchain.canonical_evidence import domain_hash


class ProjectionError(ValueError):
    pass


_PROJECTION_DOMAIN = "bootstrap.range-projection.v1"
_SEGMENT_DOMAIN = "jimuyun.bootstrap.segment-descriptor.v1"
_HASH_PREFIX = "sha256:"


def _sha(payload: bytes) -> str:
    return _HASH_PREFIX + hashlib.sha256(payload).hexdigest()


def _identity_payload(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "identity"}


def _hash_identity(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.startswith(_HASH_PREFIX) or len(value) != 71:
        raise ProjectionError(f"{field} is invalid")
    return value


def _validate_utf8_boundaries(source: bytes, start_byte: int, end_byte: int) -> bytes:
    try:
        source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProjectionError("projection source must be UTF-8") from exc
    if not source:
        raise ProjectionError("projection source must not be empty")
    if (
        not isinstance(start_byte, int)
        or isinstance(start_byte, bool)
        or not isinstance(end_byte, int)
        or isinstance(end_byte, bool)
        or start_byte < 0
        or end_byte < start_byte
        or end_byte >= len(source)
    ):
        raise ProjectionError("inclusive projection range is invalid")
    if source[start_byte] & 0xC0 == 0x80:
        raise ProjectionError("projection start is not a UTF-8 character boundary")
    if end_byte + 1 < len(source) and source[end_byte + 1] & 0xC0 == 0x80:
        raise ProjectionError("projection end is not a UTF-8 character boundary")
    return source[start_byte:end_byte + 1]


def build_range_projection(
    *,
    path: str,
    source: bytes,
    start_byte: int,
    end_byte: int,
    inclusion_reason: str,
    changed_set_id: str,
    requirement_ids: list[str],
    acceptance_ids: list[str],
    policy_identity: str,
) -> dict[str, Any]:
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path or ".." in Path(path).parts:
        raise ProjectionError("projection path is invalid")
    if not isinstance(inclusion_reason, str) or not inclusion_reason.strip():
        raise ProjectionError("projection inclusion reason is invalid")
    if not all(isinstance(value, list) and value and all(isinstance(item, str) and item for item in value) for value in (requirement_ids, acceptance_ids)):
        raise ProjectionError("projection requirement or acceptance references are invalid")
    extracted = _validate_utf8_boundaries(source, start_byte, end_byte)
    document: dict[str, Any] = {
        "schema_version": "bootstrap.range-projection.v1",
        "path": path,
        "full_source_hash": _sha(source),
        "encoding": "utf-8",
        "newline_policy": "source-preserved",
        "start_byte": start_byte,
        "end_byte": end_byte,
        "extracted_bytes_base64": base64.b64encode(extracted).decode("ascii"),
        "extracted_bytes_hash": _sha(extracted),
        "inclusion_reason": inclusion_reason,
        "changed_set_identity": _hash_identity(changed_set_id, "changed set identity"),
        "requirement_ids": sorted(set(requirement_ids)),
        "acceptance_ids": sorted(set(acceptance_ids)),
        "policy_identity": _hash_identity(policy_identity, "policy identity"),
    }
    document["identity"] = domain_hash(_PROJECTION_DOMAIN, document)
    return document


def validate_range_projection(projection: Any, source: bytes) -> dict[str, Any]:
    required = {
        "schema_version", "path", "full_source_hash", "encoding", "newline_policy", "start_byte", "end_byte",
        "extracted_bytes_base64", "extracted_bytes_hash", "inclusion_reason", "changed_set_identity",
        "requirement_ids", "acceptance_ids", "policy_identity", "identity",
    }
    if not isinstance(projection, dict) or set(projection) != required or projection.get("schema_version") != "bootstrap.range-projection.v1":
        raise ProjectionError("projection schema is invalid")
    rebuilt = build_range_projection(
        path=projection["path"], source=source, start_byte=projection["start_byte"], end_byte=projection["end_byte"],
        inclusion_reason=projection["inclusion_reason"], changed_set_id=projection["changed_set_identity"],
        requirement_ids=projection["requirement_ids"], acceptance_ids=projection["acceptance_ids"], policy_identity=projection["policy_identity"],
    )
    if rebuilt != projection:
        raise ProjectionError("projection content identity is stale or mutated")
    return projection


def build_segment_descriptor(
    *,
    projection: dict[str, Any],
    review_identity: str,
    candidate_identity: str,
    closure_identity: str,
    role: str,
    ordinal: int,
    total: int,
    model_identity: str | None,
) -> dict[str, Any]:
    if not isinstance(role, str) or not role or not isinstance(ordinal, int) or not isinstance(total, int) or ordinal < 1 or total < ordinal:
        raise ProjectionError("segment role or ordinal is invalid")
    _hash_identity(review_identity, "review identity")
    _hash_identity(candidate_identity, "candidate identity")
    _hash_identity(closure_identity, "closure identity")
    _hash_identity(projection.get("identity"), "projection identity")
    document: dict[str, Any] = {
        "schema_version": "bootstrap.segment-descriptor.v1",
        "review_identity": review_identity,
        "candidate_identity": candidate_identity,
        "closure_identity": closure_identity,
        "role": role,
        "path": projection["path"],
        "artifact_hash": projection["full_source_hash"],
        "start_byte": projection["start_byte"],
        "end_byte": projection["end_byte"],
        "ordinal": ordinal,
        "total": total,
        "segment_bytes_hash": projection["extracted_bytes_hash"],
        "projection_identity": projection["identity"],
        "projection_schema_version": projection["schema_version"],
        "model_identity": model_identity,
    }
    document["identity"] = domain_hash(_SEGMENT_DOMAIN, document)
    return document


def validate_segment_snapshot(snapshot_path: str, expected_bytes: bytes) -> None:
    path = Path(snapshot_path)
    if not path.is_absolute():
        raise ProjectionError("segment snapshot path must be absolute")
    try:
        actual = path.read_bytes()
    except OSError as exc:
        raise ProjectionError("segment snapshot is unavailable") from exc
    if actual != expected_bytes:
        raise ProjectionError("segment snapshot bytes are stale")

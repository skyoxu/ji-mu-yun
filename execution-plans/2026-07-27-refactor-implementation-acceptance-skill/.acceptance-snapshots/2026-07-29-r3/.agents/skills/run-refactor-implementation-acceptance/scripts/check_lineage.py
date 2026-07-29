"""Stable check identifiers and lineage validation for acceptance matrices."""

from __future__ import annotations

import hashlib
from typing import Any

from acceptance_core import InputError


_EVENTS = {"split", "merge", "supersede", "retire"}


def stable_check_id(namespace: str, source_path: str, source_key: str, semantic_key: str) -> str:
    if not all(isinstance(value, str) and value.strip() for value in (namespace, source_path, source_key, semantic_key)):
        raise InputError("check identity inputs are invalid")
    identity = "\0".join((namespace, source_path.replace("\\", "/"), source_key, semantic_key))
    return namespace + "-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:18].upper()


def validate_check_id_lineage(value: Any) -> None:
    if not isinstance(value, dict) or value.get("schemaVersion") != "check-id-lineage.v1" or value.get("authorizes") != []:
        raise InputError("check lineage schema or authority boundary is invalid")
    checks, events = value.get("checks"), value.get("events")
    if not isinstance(checks, list) or not isinstance(events, list):
        raise InputError("check lineage collections are invalid")
    ids: set[str] = set()
    retired: set[str] = set()
    for check in checks:
        if not isinstance(check, dict) or set(check) != {"checkId", "sourcePath", "sourceKey", "semanticKey", "state"}:
            raise InputError("check lineage check record is invalid")
        check_id = check.get("checkId")
        if not isinstance(check_id, str) or check_id in ids or check_id != stable_check_id(
            check_id.rsplit("-", 1)[0], check.get("sourcePath"), check.get("sourceKey"), check.get("semanticKey")
        ):
            raise InputError("check lineage check id is invalid or unstable")
        if check.get("state") not in {"active", "retired"}:
            raise InputError("check lineage check state is invalid")
        ids.add(check_id)
        if check["state"] == "retired":
            retired.add(check_id)
    referenced: set[str] = set()
    for event in events:
        if not isinstance(event, dict) or set(event) != {"eventId", "kind", "fromCheckIds", "toCheckIds", "reason"}:
            raise InputError("check lineage event is invalid")
        if event.get("kind") not in _EVENTS or not isinstance(event.get("eventId"), str) or not event["eventId"] or not isinstance(event.get("reason"), str) or not event["reason"].strip():
            raise InputError("check lineage event identity is invalid")
        before, after = event.get("fromCheckIds"), event.get("toCheckIds")
        if not isinstance(before, list) or not isinstance(after, list) or not before or (event["kind"] != "retire" and not after):
            raise InputError("check lineage event relationship is invalid")
        if any(not isinstance(item, str) or item not in ids for item in [*before, *after]) or len(before) != len(set(before)) or len(after) != len(set(after)):
            raise InputError("check lineage event references are invalid")
        if event["kind"] == "split" and len(before) != 1 or event["kind"] == "merge" and len(after) != 1:
            raise InputError("check lineage split or merge cardinality is invalid")
        if any(item not in retired for item in before):
            raise InputError("check lineage predecessor must be tombstoned")
        referenced.update(before)
    if retired - referenced:
        raise InputError("retired check has no lineage tombstone event")


def active_check_ids(value: Any) -> set[str]:
    validate_check_id_lineage(value)
    return {item["checkId"] for item in value["checks"] if item["state"] == "active"}

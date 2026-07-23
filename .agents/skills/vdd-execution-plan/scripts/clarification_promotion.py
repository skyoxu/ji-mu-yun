#!/usr/bin/env python3
"""Fail-closed clarification promotion preflight.

This module intentionally performs no authority writes. Transactional promotion
is enabled only after a trusted approval and owner-specific write plan exist.
"""
from __future__ import annotations

import argparse
import hmac
import hashlib
import importlib.util
import json
import sys
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


HASH_PREFIX = "sha256:"
PROMOTION_STATES = {
    "prepared": {"reserved", "blocked", "aborted"},
    "reserved": {"committing", "blocked", "aborted"},
    "committing": {"committed", "recovery_required"},
    "recovery_required": {"committed", "aborted", "manual_recovery"},
    "blocked": {"aborted"},
    "committed": set(),
    "aborted": set(),
    "manual_recovery": set(),
}

# This is deliberately independent of a promotion request.  A request may only
# bind this inventory; it cannot declare a smaller set of readers for itself.
REGISTERED_MACHINE_AUTHORITY_READERS = {
    "schema_version": "vdd.clarification-authority-consumers.v1",
    "consumers": [{
        "id": "clarification_authority_resolver",
        "module": "scripts/clarification_authority_resolver.py",
        "access": "hash-bound-committed-generation",
        "migration_status": "migrated",
    }],
}


def canonical_hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def registered_machine_reader_manifest() -> dict:
    """Return the versioned, repository-owned authority-reader inventory."""
    manifest = dict(REGISTERED_MACHINE_AUTHORITY_READERS)
    manifest["consumers"] = [dict(item) for item in REGISTERED_MACHINE_AUTHORITY_READERS["consumers"]]
    manifest["inventory_hash"] = canonical_hash(REGISTERED_MACHINE_AUTHORITY_READERS)
    return manifest


def classify_three_way_item(
    baseline: object, current: object, delta: object, predicates: object
) -> tuple[str, str]:
    """Classify an owner-bound item without using text overlap as merge evidence."""
    if not all(isinstance(value, dict) for value in (baseline, current, delta)):
        return "missing-owner", "baseline/current/delta item is missing"
    required = {"id", "owner", "value_hash", "consumers"}
    if any(not required <= set(value) for value in (baseline, current, delta)):
        return "missing-owner", "item lacks stable owner binding"
    if len({value["id"] for value in (baseline, current, delta)}) != 1 or len({value["owner"] for value in (baseline, current, delta)}) != 1:
        return "conflicting", "stable identity or owner changed"
    if any(not isinstance(value["consumers"], list) for value in (baseline, current, delta)):
        return "conflicting", "consumer closure is invalid"
    if current["value_hash"] == baseline["value_hash"]:
        return "unchanged", "current authority matches frozen baseline"
    if not isinstance(predicates, list):
        return "conflicting", "no registered deterministic compatible predicate"
    for predicate in predicates:
        if not isinstance(predicate, dict):
            continue
        if (
            predicate.get("schema_version") == "vdd.clarification-compatible-predicate.v1"
            and predicate.get("id") == delta["id"]
            and predicate.get("owner") == delta["owner"]
            and predicate.get("baseline_hash") == baseline["value_hash"]
            and predicate.get("current_hash") == current["value_hash"]
            and predicate.get("delta_hash") == delta["value_hash"]
            and predicate.get("consumer_hash") == canonical_hash(sorted(delta["consumers"]))
            and predicate.get("result") == "compatible"
            and isinstance(predicate.get("rule_version"), str)
            and predicate.get("counterexample_rejected") is True
        ):
            return "compatible", "registered owner-specific predicate accepted the exact inputs"
    return "conflicting", "current authority changed without a deterministic compatible predicate"


def validate_promotion_transition(current: str, next_state: str) -> tuple[bool, str]:
    if current not in PROMOTION_STATES or next_state not in PROMOTION_STATES:
        return False, "unknown promotion state"
    if next_state not in PROMOTION_STATES[current]:
        return False, f"illegal promotion transition {current}->{next_state}"
    return True, ""


def load_state_module():
    path = Path(__file__).with_name("clarification_state.py")
    spec = importlib.util.spec_from_file_location("vdd_clarification_state_for_promotion", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("VDD-CLARIFICATION-PROMOTION-STATE-LOADER")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blocked(rule_id: str, message: str) -> dict:
    return {
        "schema_version": "vdd.clarification-promotion-result.v1",
        "promotion_id": None,
        "status": "blocked",
        "state": "blocked",
        "rule_id": rule_id,
        "message": message,
        "authorizes": [],
        "does_not_authorize": [
            "plan-ready", "phase-authorized", "implementation-accepted", "release-ready",
        ],
    }


def validate_baseline(state_path: Path, state: dict) -> tuple[bool, str]:
    path = state_path.parent / "baseline-authority.json"
    if not path.is_file():
        return False, "baseline authority manifest is missing"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "baseline authority manifest is unreadable"
    if not isinstance(manifest, dict):
        return False, "baseline authority manifest is invalid"
    stored_hash = manifest.get("manifest_hash")
    unhashed = {key: value for key, value in manifest.items() if key != "manifest_hash"}
    if (
        manifest.get("schema_version") != "vdd.clarification-baseline-authority.v1"
        or stored_hash != canonical_hash(unhashed)
        or manifest.get("run_id") != state.get("run_id")
        or manifest.get("target") != state.get("target")
        or manifest.get("authority_hash") != state.get("authority_hash")
        or manifest.get("target_hash") != state.get("target_hash")
    ):
        return False, "baseline authority manifest does not bind the run initialization identity"
    authority = manifest.get("authority_manifest")
    if authority is not None:
        if not isinstance(authority, dict) or authority.get("schema_version") != "vdd.clarification-authority-manifest.v1":
            return False, "baseline authority source manifest is invalid"
        sources = authority.get("sources")
        if not isinstance(sources, list):
            return False, "baseline authority source closure is invalid"
        identities = set()
        for source in sources:
            if not isinstance(source, dict) or not {"path", "owner", "consumers", "identity"} <= set(source):
                return False, "baseline authority source member is incomplete"
            if not isinstance(source["consumers"], list) or not isinstance(source["identity"], str):
                return False, "baseline authority source member identity is invalid"
            key = (str(source["path"]).casefold(), source["identity"])
            if key in identities:
                return False, "baseline authority source closure has duplicate identities"
            identities.add(key)
    return True, ""


def validate_approval_capability(
    path: Path, promotion_id: str, candidate_hash: str, before_manifest_hash: str | None = None
) -> tuple[bool, str]:
    try:
        capability = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "approval capability is unreadable"
    required = {
        "issuer", "promotion_id", "candidate_hash", "before_manifest_hash", "canonical_paths",
        "issued_at", "expires_at", "nonce", "scope", "actor", "session_id", "turn_id",
        "identity_level", "revocation_state", "signature",
    }
    if not isinstance(capability, dict) or not required <= set(capability):
        return False, "approval capability is structurally incomplete"
    if capability.get("promotion_id") != promotion_id or capability.get("candidate_hash") != candidate_hash:
        return False, "approval capability is not bound to this promotion candidate"
    if capability.get("scope") != "clarification-promotion":
        return False, "approval capability scope is invalid"
    if (
        not isinstance(capability.get("canonical_paths"), list)
        or not capability["canonical_paths"]
        or any(not isinstance(value, str) or not value or ":" in value or ".." in Path(value).parts for value in capability["canonical_paths"])
        or len({value.casefold() for value in capability["canonical_paths"]}) != len(capability["canonical_paths"])
        or not all(isinstance(capability.get(name), str) and capability[name] for name in ("actor", "session_id", "turn_id", "identity_level"))
        or capability.get("revocation_state") != "active"
    ):
        return False, "approval capability binding fields are invalid"
    if before_manifest_hash is not None and capability.get("before_manifest_hash") != before_manifest_hash:
        return False, "approval capability is not bound to the frozen baseline manifest"
    try:
        issued_at = datetime.fromisoformat(str(capability["issued_at"]).replace("Z", "+00:00"))
        expires_at = datetime.fromisoformat(str(capability["expires_at"]).replace("Z", "+00:00"))
    except ValueError:
        return False, "approval capability expiry is invalid"
    if issued_at.tzinfo is None or expires_at.tzinfo is None or issued_at >= expires_at or expires_at <= datetime.now(timezone.utc):
        return False, "approval capability has expired"
    roots_path = Path(__file__).with_name("clarification-approval-roots.v1.json")
    try:
        roots_document = json.loads(roots_path.read_text(encoding="utf-8"))
        root = roots_document.get("roots", {}).get(capability["issuer"])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        root = None
    if (
        not isinstance(root, dict)
        or root.get("algorithm") != "hmac-sha256-v1"
        or capability["scope"] not in root.get("allowed_scopes", [])
        or not isinstance(root.get("environment_key"), str)
        or not isinstance(root.get("verifier_id"), str)
        or capability["identity_level"] not in root.get("allowed_identity_levels", [])
    ):
        return False, "approval issuer is not trusted for this scope"
    signing_key = os.environ.get(root["environment_key"])
    signed = {key: value for key, value in capability.items() if key != "signature"}
    expected = hmac.new(
        signing_key.encode("utf-8"), canonical_hash(signed).encode("ascii"), hashlib.sha256
    ).hexdigest() if signing_key else None
    if expected is None or not isinstance(capability.get("signature"), str) or not hmac.compare_digest(capability["signature"], expected):
        return False, "approval capability signature is invalid"
    return True, ""


def reserve_approval_nonce(run_dir: Path, approval_path: Path, promotion_id: str, candidate_hash: str) -> tuple[bool, str]:
    capability = json.loads(approval_path.read_text(encoding="utf-8"))
    journal_path = run_dir / "promotion-approvals.jsonl"
    existing = journal_path.read_text(encoding="utf-8") if journal_path.exists() else ""
    for line_number, line in enumerate(existing.splitlines(), start=1):
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            return False, f"approval journal is invalid at line {line_number}: {exc}"
        if not isinstance(item, dict):
            return False, "approval journal contains an invalid record"
        if item.get("issuer") == capability["issuer"] and item.get("nonce") == capability["nonce"]:
            if item.get("promotion_id") == promotion_id and item.get("candidate_hash") == candidate_hash:
                return True, "idempotent"
            return False, "approval nonce has already been reserved by another promotion"
    record = {
        "schema_version": "vdd.clarification-approval-reservation.v1",
        "issuer": capability["issuer"],
        "nonce": capability["nonce"],
        "promotion_id": promotion_id,
        "candidate_hash": candidate_hash,
        "capability_hash": canonical_hash(capability),
        "state": "reserved",
    }
    with journal_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return True, "reserved"


def consume_approval_nonce(
    run_dir: Path, promotion_id: str, candidate_hash: str, capability_hash: str
) -> tuple[bool, str]:
    """Consume exactly the nonce reservation owned by this promotion transaction."""
    journal_ok, journal_error = validate_approval_journal(run_dir)
    if not journal_ok:
        return False, journal_error
    journal_path = run_dir / "promotion-approvals.jsonl"
    records = [json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()] if journal_path.exists() else []
    matches = [record for record in records if record.get("capability_hash") == capability_hash]
    if not matches:
        return False, "approval nonce was not reserved by this promotion"
    latest = matches[-1]
    if latest.get("promotion_id") != promotion_id or latest.get("candidate_hash") != candidate_hash:
        return False, "approval nonce was not reserved by this promotion"
    if latest.get("state") == "consumed":
        return True, "idempotent"
    if latest.get("state") != "reserved":
        return False, "approval nonce is not consumable"
    record = {
        "schema_version": "vdd.clarification-approval-reservation.v1",
        "issuer": latest["issuer"],
        "nonce": latest["nonce"],
        "promotion_id": promotion_id,
        "candidate_hash": candidate_hash,
        "capability_hash": capability_hash,
        "state": "consumed",
    }
    with journal_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return True, "consumed"


@contextmanager
def promotion_target_lock(state_path: Path, state: dict):
    """Share the clarification target lock before taking any promotion reservation."""
    state_module = load_state_module()
    root = state_module._repository_root_for_state(state_path, state)
    registry_root = state_module._canonical_registry_target_root(root, state["target_slug"])
    with state_module._target_lock(registry_root):
        yield


def append_attempt_evidence(run_dir: Path, payload: dict) -> None:
    """Append immutable preflight evidence without touching a promoted authority."""
    journal_path = run_dir / "promotion-attempts.jsonl"
    record = {
        "schema_version": "vdd.clarification-promotion-attempt.v1",
        "record_hash": None,
        **payload,
    }
    record["record_hash"] = canonical_hash({key: value for key, value in record.items() if key != "record_hash"})
    with journal_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def validate_approval_journal(run_dir: Path) -> tuple[bool, str]:
    journal_path = run_dir / "promotion-approvals.jsonl"
    if not journal_path.exists():
        return True, ""
    try:
        lines = journal_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return False, str(exc)
    for line_number, line in enumerate(lines, start=1):
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            return False, f"approval journal is invalid at line {line_number}: {exc}"
        if not isinstance(item, dict) or item.get("schema_version") != "vdd.clarification-approval-reservation.v1":
            return False, f"approval journal contains an invalid record at line {line_number}"
        required = {"issuer", "nonce", "promotion_id", "candidate_hash", "capability_hash", "state"}
        if not required <= set(item) or item["state"] not in {"reserved", "consumed"}:
            return False, f"approval journal contains an incomplete record at line {line_number}"
    return True, ""


def _atomic_write(path: Path, content: bytes) -> None:
    """Write a control-plane object atomically; never replace an authority source directly."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.pending-{os.getpid()}")
    try:
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def _normalized_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or ":" in value:
        raise ValueError("VDD-CLARIFICATION-PROMOTION-PATH")
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("VDD-CLARIFICATION-PROMOTION-PATH")
    return path.as_posix()


def file_object_identity(path: Path) -> dict:
    """Capture the local object facts needed to reject alias/reparse write sets."""
    stat = path.stat()
    lstat = path.lstat()
    attributes = getattr(lstat, "st_file_attributes", 0)
    raw = path.read_bytes()
    is_text = False
    canonical = None
    try:
        decoded = raw.decode("utf-8")
        is_text = True
        canonical = "sha256:" + hashlib.sha256(decoded.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")).hexdigest()
    except UnicodeDecodeError:
        pass
    return {
        "resolved_path": str(path.resolve()),
        "device": stat.st_dev,
        "inode": stat.st_ino,
        "mode": stat.st_mode,
        "link_count": stat.st_nlink,
        "reparse": bool(attributes & 0x400),
        "raw_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "byte_length": len(raw),
        "canonical_text_sha256": canonical if is_text else None,
    }


def validate_generation_write_set(repository_root: Path, write_set: object) -> tuple[bool, str, list[dict]]:
    """Validate a resolver-only generation write set and freeze source identities."""
    if not isinstance(write_set, dict) or write_set.get("schema_version") != "vdd.clarification-generation-write-set.v1":
        return False, "write set schema is invalid", []
    entries = write_set.get("entries")
    readers = write_set.get("resolver_readers")
    consumer_manifest = write_set.get("consumer_manifest")
    if not isinstance(entries, list) or not entries or not isinstance(readers, list) or not readers:
        return False, "write set requires entries and resolver readers", []
    if consumer_manifest != registered_machine_reader_manifest():
        return False, "write set consumer manifest does not match the registered machine reader inventory", []
    normalized: list[dict] = []
    seen: set[str] = set()
    seen_objects: set[tuple[int, int]] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "owner", "candidate_path", "before_sha256"}:
            return False, "write set entry is invalid", []
        try:
            path = _normalized_relative_path(entry["path"])
            candidate_path = _normalized_relative_path(entry["candidate_path"])
        except ValueError:
            return False, "write set contains an unsafe path", []
        key = path.casefold()
        if key in seen or not isinstance(entry["owner"], str) or not entry["owner"]:
            return False, "write set has duplicate paths or no owner", []
        seen.add(key)
        source = (repository_root / path).resolve()
        candidate = (repository_root / candidate_path).resolve()
        try:
            source.relative_to(repository_root.resolve())
            candidate.relative_to(repository_root.resolve())
        except ValueError:
            return False, "write set path escapes repository", []
        if not source.is_file() or not candidate.is_file() or source.is_symlink() or candidate.is_symlink():
            return False, "write set source or candidate is not a regular file", []
        source_identity = file_object_identity(source)
        candidate_identity = file_object_identity(candidate)
        if (
            source_identity["reparse"] or candidate_identity["reparse"]
            or source_identity["link_count"] > 1 or candidate_identity["link_count"] > 1
        ):
            return False, "write set contains a reparse point or hardlink alias", []
        object_key = (int(source_identity["device"]), int(source_identity["inode"]))
        if object_key in seen_objects:
            return False, "write set contains overlapping file objects", []
        seen_objects.add(object_key)
        before = source_identity["raw_sha256"]
        if before != entry["before_sha256"]:
            return False, "write set source identity is stale", []
        normalized.append({
            "path": path,
            "owner": entry["owner"],
            "before_sha256": before,
            "source_identity": source_identity,
            "candidate_identity": candidate_identity,
            "candidate_sha256": candidate_identity["raw_sha256"],
            "candidate_bytes": candidate.read_bytes(),
        })
    if (
        any(not isinstance(reader, str) or not reader for reader in readers)
        or len(set(readers)) != len(readers)
        or "clarification_authority_resolver" not in readers
        or any(not reader.startswith("clarification_authority_resolver") for reader in readers)
    ):
        return False, "resolver reader declaration is invalid", []
    expected_reader_ids = sorted(item["id"] for item in REGISTERED_MACHINE_AUTHORITY_READERS["consumers"])
    if sorted(readers) != expected_reader_ids:
        return False, "resolver reader declaration does not close over the registered machine reader inventory", []
    return True, "", normalized


def prepare_generation(run_dir: Path, repository_root: Path, promotion_id: str, write_set: object) -> tuple[bool, str, Path | None]:
    """Stage a complete generation. Original authority files remain untouched."""
    valid, message, entries = validate_generation_write_set(repository_root, write_set)
    if not valid:
        return False, message, None
    generation = run_dir / "generations" / promotion_id
    manifest_path = generation / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False, "existing generation manifest is unreadable", None
        if manifest.get("write_set_hash") == canonical_hash(write_set):
            return True, "idempotent", generation
        return False, "promotion ID already has a different generation", None
    material = []
    for entry in entries:
        staged = generation / "files" / entry["path"]
        _atomic_write(staged, entry.pop("candidate_bytes"))
        material.append(entry)
    manifest = {
        "schema_version": "vdd.clarification-generation.v1",
        "promotion_id": promotion_id,
        "write_set_hash": canonical_hash(write_set),
        "entries": material,
        "resolver_readers": sorted(write_set["resolver_readers"]),
        "state": "prepared",
    }
    manifest["manifest_hash"] = canonical_hash(manifest)
    _atomic_write(manifest_path, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return True, "prepared", generation


def commit_generation(run_dir: Path, promotion_id: str) -> tuple[bool, str, dict | None]:
    """Atomically publish one immutable generation through the sole committed pointer."""
    manifest_path = run_dir / "generations" / promotion_id / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "prepared generation manifest is unavailable", None
    expected = canonical_hash({key: value for key, value in manifest.items() if key != "manifest_hash"})
    if manifest.get("schema_version") != "vdd.clarification-generation.v1" or manifest.get("manifest_hash") != expected:
        return False, "prepared generation manifest integrity failed", None
    pointer = {
        "schema_version": "vdd.clarification-committed-generation-pointer.v1",
        "promotion_id": promotion_id,
        "manifest_hash": manifest["manifest_hash"],
        "state": "committed",
    }
    pointer["pointer_hash"] = canonical_hash(pointer)
    pointer_path = run_dir / "committed-generation.json"
    if pointer_path.exists():
        existing = json.loads(pointer_path.read_text(encoding="utf-8"))
        if existing == pointer:
            return True, "idempotent", pointer
        return False, "another committed generation already exists", None
    _atomic_write(pointer_path, (json.dumps(pointer, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return True, "committed", pointer


def resolve_committed_generation(run_dir: Path) -> tuple[bool, str, dict | None]:
    """Read only a fully verified committed generation; no direct source fallback exists."""
    pointer_path = run_dir / "committed-generation.json"
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        manifest_path = run_dir / "generations" / pointer["promotion_id"] / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError):
        return False, "committed generation is unavailable", None
    pointer_expected = canonical_hash({key: value for key, value in pointer.items() if key != "pointer_hash"})
    manifest_expected = canonical_hash({key: value for key, value in manifest.items() if key != "manifest_hash"})
    readers = manifest.get("resolver_readers")
    if (
        pointer.get("schema_version") != "vdd.clarification-committed-generation-pointer.v1"
        or pointer.get("state") != "committed"
        or pointer.get("pointer_hash") != pointer_expected
        or manifest.get("manifest_hash") != manifest_expected
        or pointer.get("manifest_hash") != manifest.get("manifest_hash")
        or pointer.get("promotion_id") != manifest.get("promotion_id")
        or not isinstance(readers, list)
        or "clarification_authority_resolver" not in readers
        or any(not isinstance(reader, str) or not reader.startswith("clarification_authority_resolver") for reader in readers)
    ):
        return False, "committed generation binding failed", None
    return True, "", manifest


def _transaction_manifest_path(run_dir: Path, promotion_id: str) -> Path:
    return run_dir / "promotion-transactions" / f"{promotion_id}.json"


def _write_transaction_event(run_dir: Path, promotion_id: str, event: dict) -> None:
    path = run_dir / "promotion-transactions" / f"{promotion_id}.events.jsonl"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    record = {
        "schema_version": "vdd.clarification-promotion-transaction-event.v1",
        "sequence": len(existing.splitlines()) + 1,
        "predecessor_hash": None,
        **event,
    }
    if existing:
        prior = json.loads(existing.splitlines()[-1])
        record["predecessor_hash"] = prior.get("event_hash")
    record["event_hash"] = canonical_hash(record)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def create_promotion_transaction(run_dir: Path, promotion_id: str, inputs: dict) -> tuple[bool, str, dict | None]:
    """Create one immutable, idempotent transaction identity before any generation work."""
    if not isinstance(inputs, dict) or not inputs:
        return False, "transaction inputs are required", None
    path = _transaction_manifest_path(run_dir, promotion_id)
    request_hash = canonical_hash(inputs)
    if path.is_file():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("request_hash") == request_hash:
            return True, "idempotent", manifest
        return False, "promotion ID was replayed with different transaction inputs", None
    manifest = {
        "schema_version": "vdd.clarification-promotion-transaction.v1",
        "promotion_id": promotion_id,
        "state": "prepared",
        "request_hash": request_hash,
        "inputs": inputs,
    }
    manifest["manifest_hash"] = canonical_hash(manifest)
    _atomic_write(path, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    _write_transaction_event(run_dir, promotion_id, {"from": None, "to": "prepared", "manifest_hash": manifest["manifest_hash"]})
    return True, "prepared", manifest


def transition_promotion_transaction(run_dir: Path, promotion_id: str, next_state: str) -> tuple[bool, str, dict | None]:
    path = _transaction_manifest_path(run_dir, promotion_id)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "transaction manifest is unavailable", None
    expected = canonical_hash({key: value for key, value in manifest.items() if key != "manifest_hash"})
    if manifest.get("schema_version") != "vdd.clarification-promotion-transaction.v1" or manifest.get("manifest_hash") != expected:
        return False, "transaction manifest integrity failed", None
    current = manifest.get("state")
    if current == next_state:
        return True, "idempotent", manifest
    valid, message = validate_promotion_transition(current, next_state)
    if not valid:
        return False, message, None
    manifest["state"] = next_state
    manifest["manifest_hash"] = canonical_hash({key: value for key, value in manifest.items() if key != "manifest_hash"})
    _atomic_write(path, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    _write_transaction_event(run_dir, promotion_id, {"from": current, "to": next_state, "manifest_hash": manifest["manifest_hash"]})
    return True, next_state, manifest


def recover_promotion_transaction(run_dir: Path, promotion_id: str) -> tuple[bool, str, dict | None]:
    """Fail closed unless the sole pointer proves a completed transaction."""
    path = _transaction_manifest_path(run_dir, promotion_id)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "transaction manifest is unavailable", None
    if manifest.get("state") == "committed":
        resolved, message, generation = resolve_committed_generation(run_dir)
        if resolved and generation and generation.get("promotion_id") == promotion_id:
            return True, "committed", manifest
        return False, "committed transaction pointer is inconsistent", None
    if manifest.get("state") == "committing":
        resolved, _, generation = resolve_committed_generation(run_dir)
        if resolved and generation and generation.get("promotion_id") == promotion_id:
            return transition_promotion_transaction(run_dir, promotion_id, "committed")
        return transition_promotion_transaction(run_dir, promotion_id, "recovery_required")
    return False, f"transaction requires explicit next action from {manifest.get('state')}", manifest


def validate_transaction_freeze(transaction: object, generation: object) -> tuple[bool, str]:
    """Require the commit request to bind the closed clarification snapshot to one generation."""
    if not isinstance(transaction, dict) or not isinstance(generation, dict):
        return False, "frozen clarification inputs are unavailable"
    inputs = transaction.get("inputs")
    freeze = inputs.get("clarification_freeze") if isinstance(inputs, dict) else None
    required = {
        "event_head",
        "run_status",
        "exit_attestation_hash",
        "baseline_manifest_hash",
        "current_authority_manifest_hash",
        "write_set_hash",
        "generation_manifest_hash",
        "candidate_hash",
        "approval_capability_hash",
    }
    if not isinstance(freeze, dict) or set(freeze) != required:
        return False, "frozen clarification inputs are incomplete"
    if freeze.get("run_status") != "closed":
        return False, "frozen clarification inputs do not bind a closed run"
    hash_fields = required - {"run_status"}
    if any(not isinstance(freeze.get(field), str) or not freeze[field].startswith(HASH_PREFIX) for field in hash_fields):
        return False, "frozen clarification inputs contain an invalid identity"
    if (
        freeze["write_set_hash"] != generation.get("write_set_hash")
        or freeze["generation_manifest_hash"] != generation.get("manifest_hash")
    ):
        return False, "frozen clarification inputs do not match the prepared generation"
    return True, ""


def commit_transaction_generation(run_dir: Path, promotion_id: str) -> tuple[bool, str, dict | None]:
    """Publish only from the reserved transaction state and record recovery-safe completion."""
    path = _transaction_manifest_path(run_dir, promotion_id)
    try:
        transaction = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "transaction manifest is unavailable", None
    if transaction.get("state") == "committed":
        return recover_promotion_transaction(run_dir, promotion_id)
    if transaction.get("state") != "reserved":
        return False, f"transaction must be reserved before commit, got {transaction.get('state')}", None
    resolved, message, generation = resolve_committed_generation(run_dir)
    if resolved:
        return False, "another committed generation already exists", None
    try:
        generation = json.loads((run_dir / "generations" / promotion_id / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "prepared generation manifest is unavailable", None
    valid, message = validate_transaction_freeze(transaction, generation)
    if not valid:
        return False, message, None
    freeze = transaction["inputs"]["clarification_freeze"]
    consumed, message = consume_approval_nonce(
        run_dir, promotion_id, freeze["candidate_hash"], freeze["approval_capability_hash"]
    )
    if not consumed:
        return False, message, None
    transitioned, message, _ = transition_promotion_transaction(run_dir, promotion_id, "committing")
    if not transitioned:
        return False, message, None
    committed, message, pointer = commit_generation(run_dir, promotion_id)
    if not committed:
        transition_promotion_transaction(run_dir, promotion_id, "recovery_required")
        return False, message, None
    transitioned, message, transaction = transition_promotion_transaction(run_dir, promotion_id, "committed")
    if not transitioned:
        return False, message, None
    return True, "committed", {"transaction": transaction, "pointer": pointer}


def evaluate_preflight(args: argparse.Namespace) -> dict:
    state_module = load_state_module()
    state_path = Path(args.state).resolve()
    state = state_module._load_state(state_path)
    result = blocked("VDD-CLARIFICATION-PROMOTION-APPROVAL-REQUIRED", "trusted approval capability is required")
    result["promotion_id"] = args.promotion_id
    if state.get("status") != "closed":
        result.update({"rule_id": "VDD-CLARIFICATION-PROMOTION-RUN-STATE", "message": "only a closed clarification run may enter promotion preflight"})
        append_attempt_evidence(state_path.parent, {
            "promotion_id": args.promotion_id,
            "candidate_hash": args.candidate_hash,
            "status": result["status"],
            "state": result["state"],
            "rule_id": result["rule_id"],
            "authority_write_count": 0,
        })
        return result
    with promotion_target_lock(state_path, state):
        baseline_ok, baseline_error = validate_baseline(state_path, state)
        if not baseline_ok:
            result.update({"rule_id": "VDD-CLARIFICATION-PROMOTION-BASELINE", "message": baseline_error})
        else:
            exit_attestation = state.get("exit_attestation")
            if (
                not isinstance(exit_attestation, dict)
                or state.get("interaction_mode") != "interactive"
                or exit_attestation.get("actor") != "user"
                or exit_attestation.get("explicit_no_more_clarification") is not True
                or exit_attestation.get("explicit_write_permission") is not True
                or exit_attestation.get("draft_only") is not False
                or state.get("write_disposition") != "normal"
            ):
                result.update({"rule_id": "VDD-CLARIFICATION-PROMOTION-EXIT", "message": "valid interactive dual exit and normal write disposition are required"})
            elif (
                args.current_authority_hash != state.get("current_authority_hash")
                or args.current_target_hash != state.get("current_target_hash")
                or not args.candidate_hash.startswith(HASH_PREFIX)
            ):
                result.update({"rule_id": "VDD-CLARIFICATION-PROMOTION-FRESHNESS", "message": "candidate or current authority/target identity is stale"})
            elif args.approval is not None:
                journal_ok, journal_error = validate_approval_journal(state_path.parent)
                if not journal_ok:
                    result.update({"rule_id": "VDD-CLARIFICATION-PROMOTION-NONCE", "message": journal_error})
                else:
                    approval_path = Path(args.approval).resolve()
                    baseline_manifest = json.loads((state_path.parent / "baseline-authority.json").read_text(encoding="utf-8"))
                    approval_ok, approval_error = validate_approval_capability(
                        approval_path, args.promotion_id, args.candidate_hash, baseline_manifest.get("manifest_hash")
                    )
                    if not approval_ok:
                        result.update({"rule_id": "VDD-CLARIFICATION-PROMOTION-APPROVAL", "message": approval_error})
                    else:
                        reserved, reservation_message = reserve_approval_nonce(state_path.parent, approval_path, args.promotion_id, args.candidate_hash)
                        if not reserved:
                            result.update({"rule_id": "VDD-CLARIFICATION-PROMOTION-NONCE", "message": reservation_message})
                        else:
                            result.update({
                                "rule_id": "VDD-CLARIFICATION-PROMOTION-CONSUMPTION",
                                "message": "approval nonce is reserved; a bound authority write plan must create the promotion transaction before consumption",
                            })
        append_attempt_evidence(state_path.parent, {
            "promotion_id": args.promotion_id,
            "candidate_hash": args.candidate_hash,
            "status": result["status"],
            "state": result["state"],
            "rule_id": result["rule_id"],
            "authority_write_count": 0,
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--promotion-id", required=True)
    parser.add_argument("--candidate-hash", required=True)
    parser.add_argument("--current-authority-hash", required=True)
    parser.add_argument("--current-target-hash", required=True)
    parser.add_argument("--approval", type=Path)
    args = parser.parse_args()
    try:
        result = evaluate_preflight(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        result = blocked("VDD-CLARIFICATION-PROMOTION-PARSE", str(exc))
        result["promotion_id"] = args.promotion_id
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    sys.exit(main())

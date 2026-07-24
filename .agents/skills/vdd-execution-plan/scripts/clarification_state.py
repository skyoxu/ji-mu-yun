#!/usr/bin/env python3
"""Optional, atomic single-writer resume state for material VDD clarification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "vdd.clarification-resume.v3"
QUARANTINE_SCHEMA_VERSION = "vdd.clarification-quarantine.v1"
LEGACY_SCHEMA_VERSIONS = {"vdd.clarification-state.v1", "vdd.clarification-resume.v2"}
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
DECISION_ID_PATTERN = re.compile(r"^CQ-[0-9]{3,}$")
DECISION_KINDS = {"fact_gap", "user_decision", "authority_conflict"}
SAFE_TOKEN_METADATA_KEYS = {"token_count", "token_counts", "token_budget", "token_usage", "max_tokens", "min_tokens"}
SENSITIVE_KEY_PATTERN = re.compile(
    r"^(?:token|secret|password|credential|authorization|api_key|private_key|raw_user|conversation|email|phone"
    r"|(?:access|refresh|api|auth|bearer|session)_token|(?:client|signing)_secret|.+_(?:secret|password|credential|email|phone|api_key|private_key|token))$"
)
SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{16,}\b", re.I),
    re.compile(r"\bbasic\s+[A-Za-z0-9+/]{8,}={0,2}\b", re.I),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b", re.I),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{12,}\b", re.I),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b", re.I),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{12,}\b", re.I),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"BEGIN\s+[^\r\n]*PRIVATE\s+KEY", re.I),
)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fail(rule_id: str, detail: str, **safe_metadata: str) -> ValueError:
    error = ValueError(detail)
    error.rule_id = rule_id  # type: ignore[attr-defined]
    error.safe_metadata = safe_metadata  # type: ignore[attr-defined]
    return error


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def decode_json_object(raw: bytes) -> tuple[dict[str, Any], bool, bool]:
    duplicate_key = False
    sensitive = False

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        nonlocal duplicate_key, sensitive
        value: dict[str, Any] = {}
        seen: set[str] = set()
        for key, child in pairs:
            if key in seen:
                duplicate_key = True
            seen.add(key)
            if is_sensitive_key(key) or contains_sensitive(child):
                sensitive = True
            value[key] = child
        return value

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs)
    if not isinstance(value, dict):
        raise fail("VDD-CLARIFICATION-SCHEMA", "JSON root must be an object")
    return value, duplicate_key, sensitive or contains_sensitive(value)


def load_json_bytes(path: Path) -> tuple[bytes, dict[str, Any], bool, bool]:
    raw = path.read_bytes()
    value, duplicate_key, sensitive = decode_json_object(raw)
    return raw, value, duplicate_key, sensitive


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=True, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def target_slug(target: str) -> str:
    target_digest = hashlib.sha256(target.casefold().encode("utf-8")).hexdigest()[:12]
    stem = re.sub(r"[^a-z0-9]+", "-", target.casefold()).strip("-")[-48:] or "plan"
    return f"{stem}-{target_digest}"


def ensure_inside(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise fail("VDD-CLARIFICATION-PATH", "path escapes project root") from exc
    return resolved


def normalize_key(value: str) -> str:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).replace("-", "_")
    return re.sub(r"_+", "_", separated).strip("_").casefold()


def is_sensitive_key(value: str) -> bool:
    normalized = normalize_key(value)
    return normalized not in SAFE_TOKEN_METADATA_KEYS and SENSITIVE_KEY_PATTERN.fullmatch(normalized) is not None


def is_sensitive_value(value: str) -> bool:
    return any(pattern.search(value) is not None for pattern in SENSITIVE_VALUE_PATTERNS)


def contains_sensitive(value: Any) -> bool:
    if isinstance(value, dict):
        return any(is_sensitive_key(str(key)) or contains_sensitive(child) for key, child in value.items())
    if isinstance(value, list):
        return any(contains_sensitive(child) for child in value)
    return isinstance(value, str) and is_sensitive_value(value)


def validate_hash(value: Any, field: str) -> None:
    if not isinstance(value, str) or not HASH_PATTERN.fullmatch(value):
        raise fail("VDD-CLARIFICATION-SCHEMA", f"invalid {field}")


def validate_decisions(decisions: Any) -> list[dict[str, str]]:
    if not isinstance(decisions, list):
        return [{"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": "decisions must be a list"}]
    findings: list[dict[str, str]] = []
    by_id: dict[str, dict[str, Any]] = {}
    fields = {"id", "summary", "material", "status", "kind", "depends_on"}
    for item in decisions:
        if not isinstance(item, dict) or set(item) != fields:
            findings.append({"rule_id": "VDD-CLARIFICATION-DECISION", "detail": "decision has invalid fields"})
            continue
        decision_id = item["id"]
        if not isinstance(decision_id, str) or not DECISION_ID_PATTERN.fullmatch(decision_id) or decision_id in by_id:
            findings.append({"rule_id": "VDD-CLARIFICATION-DECISION", "detail": "decision ID is invalid or duplicated"})
            continue
        by_id[decision_id] = item
        if (
            not isinstance(item["summary"], str)
            or not item["summary"].strip()
            or not isinstance(item["material"], bool)
            or not isinstance(item["status"], str)
            or item["status"] not in {"open", "resolved", "deferred"}
            or not isinstance(item["kind"], str)
            or item["kind"] not in DECISION_KINDS
        ):
            findings.append({"rule_id": "VDD-CLARIFICATION-DECISION", "detail": "decision value is invalid"})
        dependencies = item["depends_on"]
        if (
            not isinstance(dependencies, list)
            or any(not isinstance(value, str) or not DECISION_ID_PATTERN.fullmatch(value) for value in dependencies)
            or len(set(dependencies)) != len(dependencies)
            or decision_id in dependencies
        ):
            findings.append({"rule_id": "VDD-CLARIFICATION-DEPENDENCY", "detail": "decision dependencies are invalid"})
    if findings:
        return findings
    for decision_id, item in by_id.items():
        missing = [value for value in item["depends_on"] if value not in by_id]
        if missing:
            findings.append({"rule_id": "VDD-CLARIFICATION-DEPENDENCY", "detail": f"missing dependencies for {decision_id}"})
        if item["status"] == "resolved" and any(by_id[value]["status"] != "resolved" for value in item["depends_on"] if value in by_id):
            findings.append({"rule_id": "VDD-CLARIFICATION-DEPENDENCY", "detail": f"unresolved dependency for {decision_id}"})
    dependency_counts = {decision_id: len(item["depends_on"]) for decision_id, item in by_id.items()}
    dependents: dict[str, list[str]] = {decision_id: [] for decision_id in by_id}
    for decision_id, item in by_id.items():
        for dependency in item["depends_on"]:
            if dependency in dependents:
                dependents[dependency].append(decision_id)
    ready = [decision_id for decision_id, count in dependency_counts.items() if count == 0]
    visited_count = 0
    while ready:
        decision_id = ready.pop()
        visited_count += 1
        for dependent in dependents[decision_id]:
            dependency_counts[dependent] -= 1
            if dependency_counts[dependent] == 0:
                ready.append(dependent)
    if visited_count != len(by_id):
        findings.append({"rule_id": "VDD-CLARIFICATION-DEPENDENCY", "detail": "decision dependency graph contains a cycle"})
    return findings


def validate_state(data: dict[str, Any]) -> list[dict[str, str]]:
    required = {
        "schema_version",
        "project_root",
        "evidence_root",
        "run_id",
        "target",
        "mode",
        "authority_hash",
        "target_hash",
        "status",
        "decisions",
        "updated_at",
    }
    if set(data) != required:
        return [{"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": "state fields do not match the current schema"}]
    findings: list[dict[str, str]] = []
    if (
        data["schema_version"] != SCHEMA_VERSION
        or not isinstance(data["mode"], str)
        or data["mode"] not in {"create", "repair"}
        or not isinstance(data["status"], str)
        or data["status"] not in {"active", "closed", "invalidated"}
    ):
        findings.append({"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": "invalid state vocabulary"})
    if not isinstance(data["run_id"], str) or not RUN_ID_PATTERN.fullmatch(data["run_id"]):
        findings.append({"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": "invalid run_id"})
    for field in ("project_root", "evidence_root", "target", "updated_at"):
        if not isinstance(data[field], str) or not data[field]:
            findings.append({"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": f"invalid {field}"})
    for field in ("authority_hash", "target_hash"):
        if not isinstance(data[field], str) or not HASH_PATTERN.fullmatch(data[field]):
            findings.append({"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": f"invalid {field}"})
    findings.extend(validate_decisions(data["decisions"]))
    return findings


def validate_current_identity(data: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if data.get("schema_version") != SCHEMA_VERSION:
        findings.append({"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": "invalid current schema"})
    if not isinstance(data.get("run_id"), str) or not RUN_ID_PATTERN.fullmatch(data["run_id"]):
        findings.append({"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": "invalid run_id"})
    mode = data.get("mode")
    status = data.get("status")
    if not isinstance(mode, str) or mode not in {"create", "repair"} or not isinstance(status, str) or status not in {"active", "closed", "invalidated"}:
        findings.append({"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": "invalid state vocabulary"})
    for field in ("target", "project_root", "evidence_root"):
        if not isinstance(data.get(field), str) or not data[field]:
            findings.append({"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": f"invalid {field}"})
    target = data.get("target")
    if isinstance(target, str) and not is_valid_target(target):
        findings.append({"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": "invalid target"})
    for field in ("authority_hash", "target_hash"):
        if not isinstance(data.get(field), str) or not HASH_PATTERN.fullmatch(data[field]):
            findings.append({"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": f"invalid {field}"})
    return findings


def validate_quarantine(data: dict[str, Any]) -> bool:
    return (
        set(data) == {"schema_version", "status", "rule_id", "payload_sha256", "quarantined_at"}
        and data.get("schema_version") == QUARANTINE_SCHEMA_VERSION
        and data.get("status") == "quarantined"
        and data.get("rule_id") == "VDD-CLARIFICATION-SENSITIVE"
        and isinstance(data.get("payload_sha256"), str)
        and HASH_PATTERN.fullmatch(data["payload_sha256"]) is not None
        and isinstance(data.get("quarantined_at"), str)
        and bool(data["quarantined_at"])
        and not contains_sensitive(data)
    )


def is_valid_target(value: str) -> bool:
    normalized = value.replace("\\", "/")
    target_path = Path(normalized)
    return bool(normalized) and normalized == value and not target_path.is_absolute() and ".." not in target_path.parts


def resolve_state_argument(project_root: Path, value: str) -> Path:
    root = project_root.resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    return ensure_inside(root, candidate)


def validate_declared_location(path: Path, project_root: Path, state: dict[str, Any]) -> Path:
    root = project_root.resolve()
    if state.get("project_root") != str(root):
        raise fail("VDD-CLARIFICATION-PATH", "state project root does not match caller")
    evidence_value = state.get("evidence_root")
    if not isinstance(evidence_value, str) or not evidence_value:
        raise fail("VDD-CLARIFICATION-PATH", "state evidence root is invalid")
    evidence = ensure_inside(root, root / evidence_value)
    ensure_inside(evidence, path)
    return evidence


def validate_state_location(path: Path, project_root: Path, state: dict[str, Any]) -> None:
    evidence = validate_declared_location(path, project_root, state)
    target = state.get("target")
    run_id = state.get("run_id")
    if not isinstance(target, str) or not isinstance(run_id, str):
        raise fail("VDD-CLARIFICATION-PATH", "state identity is invalid")
    expected = ensure_inside(evidence, evidence / target_slug(target) / run_id / "state.json")
    if path.resolve() != expected:
        raise fail("VDD-CLARIFICATION-PATH", "state path does not match target and run identity")


def quarantine(path: Path, payload: bytes) -> str:
    payload_digest = digest(payload)
    atomic_write(
        path,
        {
            "schema_version": QUARANTINE_SCHEMA_VERSION,
            "status": "quarantined",
            "rule_id": "VDD-CLARIFICATION-SENSITIVE",
            "payload_sha256": payload_digest,
            "quarantined_at": now(),
        },
    )
    return payload_digest


def read_current_state(path: Path, project_root: Path) -> tuple[dict[str, Any], bytes]:
    root = project_root.resolve()
    resolved = ensure_inside(root, path)
    raw, data, duplicate_key, sensitive = load_json_bytes(resolved)
    schema_version = data.get("schema_version")
    if schema_version == QUARANTINE_SCHEMA_VERSION:
        if duplicate_key or sensitive or not validate_quarantine(data):
            raise fail("VDD-CLARIFICATION-SCHEMA", "invalid quarantine envelope")
        raise fail("VDD-CLARIFICATION-QUARANTINED", "clarification run is quarantined", payload_sha256=str(data.get("payload_sha256", "")))
    if not isinstance(schema_version, str):
        raise fail("VDD-CLARIFICATION-SCHEMA", "unknown clarification schema")
    if schema_version in LEGACY_SCHEMA_VERSIONS:
        raise fail("VDD-CLARIFICATION-LEGACY-READ-ONLY", "legacy state requires inspect-legacy")
    if schema_version != SCHEMA_VERSION:
        raise fail("VDD-CLARIFICATION-SCHEMA", "unknown clarification schema")
    identity_findings = validate_current_identity(data)
    if identity_findings:
        raise fail(identity_findings[0]["rule_id"], identity_findings[0]["detail"])
    validate_state_location(resolved, root, data)
    if sensitive:
        payload_digest = quarantine(resolved, raw)
        raise fail("VDD-CLARIFICATION-QUARANTINED", "clarification run is quarantined", payload_sha256=payload_digest)
    if duplicate_key:
        raise fail("VDD-CLARIFICATION-SCHEMA", "duplicate JSON fields are not allowed")
    findings = validate_state(data)
    if findings:
        raise fail(findings[0]["rule_id"], findings[0]["detail"])
    return data, raw


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    validate_hash(args.authority_hash, "authority_hash")
    validate_hash(args.target_hash, "target_hash")
    root = Path(args.project_root).resolve()
    target = str(args.target).replace("\\", "/")
    if not is_valid_target(target):
        raise fail("VDD-CLARIFICATION-PATH", "target must be a project-relative path")
    if not RUN_ID_PATTERN.fullmatch(args.run_id):
        raise fail("VDD-CLARIFICATION-SCHEMA", "invalid run_id")
    evidence = Path(args.evidence_root) if args.evidence_root else Path("logs") / "vdd-resume"
    evidence_root = ensure_inside(root, root / evidence)
    state_path = ensure_inside(evidence_root, evidence_root / target_slug(target) / args.run_id / "state.json")
    if state_path.exists():
        existing, _ = read_current_state(state_path, root)
        immutable_identity = {
            "project_root": str(root),
            "evidence_root": str(evidence_root.relative_to(root)),
            "target": target,
            "mode": args.mode,
        }
        if any(existing.get(key) != value for key, value in immutable_identity.items()):
            raise fail("VDD-CLARIFICATION-IDENTITY", "existing run identity does not match init request")
        if existing["authority_hash"] != args.authority_hash or existing["target_hash"] != args.target_hash:
            return {"status": "stale", "state": str(state_path)}
        if existing["status"] == "invalidated":
            return {"status": "invalidated", "state": str(state_path)}
        return {"status": "resume", "state": str(state_path)}
    data = {
        "schema_version": SCHEMA_VERSION,
        "project_root": str(root),
        "evidence_root": str(evidence_root.relative_to(root)),
        "run_id": args.run_id,
        "target": target,
        "mode": args.mode,
        "authority_hash": args.authority_hash,
        "target_hash": args.target_hash,
        "status": "active",
        "decisions": [],
        "updated_at": now(),
    }
    findings = validate_state(data)
    if findings:
        raise fail(findings[0]["rule_id"], findings[0]["detail"])
    atomic_write(state_path, data)
    return {"status": "initialized", "state": str(state_path)}


def command_record(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.project_root)
    path = resolve_state_argument(root, args.state)
    state, _ = read_current_state(path, root)
    if state["status"] != "active":
        raise fail("VDD-CLARIFICATION-STATE", "only active resume state may change")
    payload_raw, payload, duplicate_key, sensitive = load_json_bytes(Path(args.decisions_file).resolve())
    if sensitive:
        payload_digest = quarantine(path, payload_raw)
        raise fail("VDD-CLARIFICATION-QUARANTINED", "clarification run is quarantined", payload_sha256=payload_digest)
    if duplicate_key:
        raise fail("VDD-CLARIFICATION-SCHEMA", "duplicate JSON fields are not allowed")
    decisions = payload.get("decisions")
    candidate = dict(state)
    candidate["decisions"] = decisions
    candidate["updated_at"] = now()
    findings = validate_state(candidate)
    if findings:
        raise fail(findings[0]["rule_id"], findings[0]["detail"])
    atomic_write(path, candidate)
    return {
        "status": "recorded",
        "state": str(path),
        "open_material": sum(item["material"] and item["status"] != "resolved" for item in decisions),
    }


def command_close(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.project_root)
    path = resolve_state_argument(root, args.state)
    state, _ = read_current_state(path, root)
    if state["status"] != "active":
        raise fail("VDD-CLARIFICATION-STATE", "only active resume state may close")
    open_material = [item["id"] for item in state["decisions"] if item["material"] and item["status"] != "resolved"]
    if open_material:
        raise fail("VDD-CLARIFICATION-BLOCKER", f"material decisions remain open: {open_material}")
    state["status"] = "closed"
    state["updated_at"] = now()
    atomic_write(path, state)
    return {"status": "closed", "state": str(path)}


def command_invalidate(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.project_root)
    path = resolve_state_argument(root, args.state)
    state, _ = read_current_state(path, root)
    if state["status"] == "invalidated":
        return {"status": "invalidated", "state": str(path)}
    if state["status"] not in {"active", "closed"}:
        raise fail("VDD-CLARIFICATION-STATE", "only active or closed state may invalidate")
    state["status"] = "invalidated"
    state["updated_at"] = now()
    atomic_write(path, state)
    return {"status": "invalidated", "state": str(path)}


def command_reopen(args: argparse.Namespace) -> dict[str, Any]:
    validate_hash(args.authority_hash, "authority_hash")
    validate_hash(args.target_hash, "target_hash")
    root = Path(args.project_root)
    path = resolve_state_argument(root, args.state)
    state, _ = read_current_state(path, root)
    if state["status"] != "invalidated":
        raise fail("VDD-CLARIFICATION-STATE", "only invalidated state may reopen")
    state["authority_hash"] = args.authority_hash
    state["target_hash"] = args.target_hash
    state["decisions"] = []
    state["status"] = "active"
    state["updated_at"] = now()
    atomic_write(path, state)
    return {"status": "active", "state": str(path)}


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.project_root)
    state, _ = read_current_state(resolve_state_argument(root, args.state), root)
    return state


def validate_legacy_state(data: dict[str, Any], project_root: Path, path: Path) -> tuple[str, str, str]:
    schema_version = data.get("schema_version")
    run_id = data.get("run_id")
    target = data.get("target")
    mode = data.get("mode")
    status = data.get("status")
    if (
        schema_version not in LEGACY_SCHEMA_VERSIONS
        or not isinstance(run_id, str)
        or not RUN_ID_PATTERN.fullmatch(run_id)
        or not isinstance(target, str)
        or not is_valid_target(target)
        or not isinstance(mode, str)
        or mode not in {"create", "repair"}
        or not isinstance(status, str)
        or status not in {"active", "closed", "invalidated"}
    ):
        raise fail("VDD-CLARIFICATION-LEGACY-SCHEMA", "legacy identity is invalid")
    if schema_version == "vdd.clarification-resume.v2":
        required = {
            "project_root",
            "evidence_root",
            "authority_hash",
            "target_hash",
            "decisions",
            "updated_at",
        }
        if (
            any(field not in data for field in required)
            or not isinstance(data.get("decisions"), list)
            or not isinstance(data.get("updated_at"), str)
            or not data["updated_at"]
        ):
            raise fail("VDD-CLARIFICATION-LEGACY-SCHEMA", "legacy v2 state is incomplete")
        try:
            validate_hash(data.get("authority_hash"), "authority_hash")
            validate_hash(data.get("target_hash"), "target_hash")
            validate_declared_location(path, project_root, data)
        except ValueError as exc:
            raise fail("VDD-CLARIFICATION-LEGACY-SCHEMA", "legacy v2 identity is invalid") from exc
    return run_id, target, status


def command_inspect_legacy(args: argparse.Namespace) -> dict[str, Any]:
    validate_hash(args.expected_sha256, "expected_sha256")
    root = Path(args.project_root).resolve()
    path = resolve_state_argument(root, args.state)
    raw = path.read_bytes()
    actual = digest(raw)
    if actual != args.expected_sha256:
        raise fail("VDD-CLARIFICATION-LEGACY-HASH", "legacy state hash does not match", payload_sha256=actual)
    data, duplicate_key, sensitive = decode_json_object(raw)
    schema_version = data.get("schema_version")
    if not isinstance(schema_version, str) or schema_version not in LEGACY_SCHEMA_VERSIONS:
        raise fail("VDD-CLARIFICATION-LEGACY-SCHEMA", "state is not a supported legacy schema", payload_sha256=actual)
    if sensitive:
        raise fail("VDD-CLARIFICATION-LEGACY-SENSITIVE", "legacy state contains sensitive content", payload_sha256=actual)
    if duplicate_key:
        raise fail("VDD-CLARIFICATION-LEGACY-SCHEMA", "duplicate JSON fields are not allowed", payload_sha256=actual)
    try:
        run_id, target, status = validate_legacy_state(data, root, path)
    except ValueError as exc:
        if not getattr(exc, "safe_metadata", None):
            exc.safe_metadata = {"payload_sha256": actual}  # type: ignore[attr-defined]
        raise
    return {
        "status": "legacy-inspected",
        "schema_version": data["schema_version"],
        "run_id": run_id,
        "target": target,
        "state_status": status,
        "payload_sha256": actual,
        "read_only": True,
    }


def add_state_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--state", required=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Persist optional material clarification resume state.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init")
    init.add_argument("--project-root", required=True)
    init.add_argument("--target", required=True)
    init.add_argument("--mode", choices=("create", "repair"), required=True)
    init.add_argument("--authority-hash", required=True)
    init.add_argument("--target-hash", required=True)
    init.add_argument("--run-id", required=True)
    init.add_argument("--evidence-root")
    init.set_defaults(handler=command_init)
    record = subparsers.add_parser("record")
    add_state_arguments(record)
    record.add_argument("--decisions-file", required=True)
    record.set_defaults(handler=command_record)
    close = subparsers.add_parser("close")
    add_state_arguments(close)
    close.set_defaults(handler=command_close)
    invalidate = subparsers.add_parser("invalidate")
    add_state_arguments(invalidate)
    invalidate.set_defaults(handler=command_invalidate)
    reopen = subparsers.add_parser("reopen")
    add_state_arguments(reopen)
    reopen.add_argument("--authority-hash", required=True)
    reopen.add_argument("--target-hash", required=True)
    reopen.set_defaults(handler=command_reopen)
    status = subparsers.add_parser("status")
    add_state_arguments(status)
    status.set_defaults(handler=command_status)
    legacy = subparsers.add_parser("inspect-legacy")
    add_state_arguments(legacy)
    legacy.add_argument("--expected-sha256", required=True)
    legacy.set_defaults(handler=command_inspect_legacy)
    args = parser.parse_args(argv)
    try:
        payload = args.handler(args)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        payload = {
            "status": "error",
            "rule_id": getattr(exc, "rule_id", "VDD-CLARIFICATION-IO"),
            "detail": str(exc),
        }
        payload.update(getattr(exc, "safe_metadata", {}))
        print(json.dumps(payload, ensure_ascii=True))
        return 1
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Optional, single-writer resume state for material VDD clarification only."""

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


SCHEMA_VERSION = "vdd.clarification-resume.v2"
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
DECISION_ID_PATTERN = re.compile(r"^CQ-[0-9]{3,}$")
SENSITIVE_KEY_PATTERN = re.compile(r"(token|secret|password|credential|raw_user|conversation|email|phone)", re.I)
SENSITIVE_VALUE_PATTERN = re.compile(r"(bearer\s+\S+|sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|AKIA[0-9A-Z]{16})", re.I)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fail(rule_id: str, detail: str) -> ValueError:
    error = ValueError(detail)
    error.rule_id = rule_id  # type: ignore[attr-defined]
    return error


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise fail("VDD-CLARIFICATION-SCHEMA", "JSON root must be an object")
    return value


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=True, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def target_slug(target: str) -> str:
    digest = hashlib.sha256(target.casefold().encode("utf-8")).hexdigest()[:12]
    stem = re.sub(r"[^a-z0-9]+", "-", target.casefold()).strip("-")[-48:] or "plan"
    return f"{stem}-{digest}"


def ensure_inside(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise fail("VDD-CLARIFICATION-PATH", "path escapes project root") from exc
    return resolved


def validate_state(data: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    required = {"schema_version", "project_root", "evidence_root", "run_id", "target", "mode", "authority_hash", "target_hash", "status", "decisions", "updated_at"}
    missing = sorted(required - set(data))
    if missing:
        findings.append({"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": f"missing fields: {missing}"})
        return findings
    if data["schema_version"] != SCHEMA_VERSION or data["mode"] not in {"create", "repair"} or data["status"] not in {"active", "closed", "invalidated"}:
        findings.append({"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": "invalid state vocabulary"})
    if not isinstance(data["run_id"], str) or not RUN_ID_PATTERN.fullmatch(data["run_id"]):
        findings.append({"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": "invalid run_id"})
    for field in ("authority_hash", "target_hash"):
        if not isinstance(data[field], str) or not HASH_PATTERN.fullmatch(data[field]):
            findings.append({"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": f"invalid {field}"})
    if not isinstance(data["decisions"], list):
        findings.append({"rule_id": "VDD-CLARIFICATION-SCHEMA", "detail": "decisions must be a list"})
        return findings
    seen: set[str] = set()
    for decision in data["decisions"]:
        if not isinstance(decision, dict) or set(decision) != {"id", "summary", "material", "status"}:
            findings.append({"rule_id": "VDD-CLARIFICATION-DECISION", "detail": "decision has invalid fields"})
            continue
        if not isinstance(decision["id"], str) or not DECISION_ID_PATTERN.fullmatch(decision["id"]) or decision["id"] in seen:
            findings.append({"rule_id": "VDD-CLARIFICATION-DECISION", "detail": "decision ID is invalid or duplicated"})
        seen.add(decision["id"])
        if not isinstance(decision["summary"], str) or not decision["summary"].strip() or not isinstance(decision["material"], bool) or decision["status"] not in {"open", "resolved", "deferred"}:
            findings.append({"rule_id": "VDD-CLARIFICATION-DECISION", "detail": "decision value is invalid"})
    return findings


def assert_no_sensitive(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if SENSITIVE_KEY_PATTERN.search(str(key)):
                raise fail("VDD-CLARIFICATION-MINIMIZATION", f"sensitive field: {path}.{key}")
            assert_no_sensitive(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_sensitive(child, f"{path}[{index}]")
    elif isinstance(value, str) and SENSITIVE_VALUE_PATTERN.search(value):
        raise fail("VDD-CLARIFICATION-MINIMIZATION", f"sensitive value: {path}")


def read_state(path: Path) -> dict[str, Any]:
    data = load_json(path)
    findings = validate_state(data)
    if findings:
        raise fail(findings[0]["rule_id"], findings[0]["detail"])
    return data


def validate_state_location(path: Path, project_root: Path, state: dict[str, Any]) -> None:
    root = project_root.resolve()
    if state.get("project_root") != str(root):
        raise fail("VDD-CLARIFICATION-PATH", "state project root does not match caller")
    evidence = ensure_inside(root, root / str(state.get("evidence_root", "")))
    ensure_inside(evidence, path)


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.project_root).resolve()
    target = str(args.target).replace("\\", "/")
    if Path(target).is_absolute() or ".." in Path(target).parts:
        raise fail("VDD-CLARIFICATION-PATH", "target must be a project-relative path")
    if not RUN_ID_PATTERN.fullmatch(args.run_id):
        raise fail("VDD-CLARIFICATION-SCHEMA", "invalid run_id")
    evidence = Path(args.evidence_root) if args.evidence_root else Path("logs") / "vdd-resume"
    evidence_root = ensure_inside(root, root / evidence)
    state_path = evidence_root / target_slug(target) / args.run_id / "state.json"
    if state_path.exists():
        existing = read_state(state_path)
        if any(existing.get(key) != value for key, value in {"project_root": str(root), "evidence_root": str(evidence_root.relative_to(root)), "target": target, "mode": args.mode, "authority_hash": args.authority_hash, "target_hash": args.target_hash}.items()):
            return {"status": "stale", "state": str(state_path)}
        return {"status": "resume", "state": str(state_path)}
    data = {"schema_version": SCHEMA_VERSION, "project_root": str(root), "evidence_root": str(evidence_root.relative_to(root)), "run_id": args.run_id, "target": target, "mode": args.mode, "authority_hash": args.authority_hash, "target_hash": args.target_hash, "status": "active", "decisions": [], "updated_at": now()}
    findings = validate_state(data)
    if findings:
        raise fail(findings[0]["rule_id"], findings[0]["detail"])
    atomic_write(state_path, data)
    return {"status": "initialized", "state": str(state_path)}


def command_record(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.state).resolve()
    state = read_state(path)
    validate_state_location(path, Path(args.project_root), state)
    if state["status"] != "active":
        raise fail("VDD-CLARIFICATION-STATE", "only active resume state may change")
    payload = load_json(Path(args.decisions_file).resolve())
    assert_no_sensitive(payload)
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise fail("VDD-CLARIFICATION-DECISION", "decisions must be a list")
    state["decisions"] = decisions
    state["updated_at"] = now()
    findings = validate_state(state)
    if findings:
        raise fail(findings[0]["rule_id"], findings[0]["detail"])
    atomic_write(path, state)
    return {"status": "recorded", "state": str(path), "open_material": sum(item["material"] and item["status"] != "resolved" for item in decisions)}


def command_close(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.state).resolve()
    state = read_state(path)
    validate_state_location(path, Path(args.project_root), state)
    open_material = [item["id"] for item in state["decisions"] if item["material"] and item["status"] != "resolved"]
    if open_material:
        raise fail("VDD-CLARIFICATION-BLOCKER", f"material decisions remain open: {open_material}")
    state["status"] = "closed"
    state["updated_at"] = now()
    atomic_write(path, state)
    return {"status": "closed", "state": str(path)}


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.state).resolve()
    state = read_state(path)
    validate_state_location(path, Path(args.project_root), state)
    return state


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
    record.add_argument("--project-root", required=True)
    record.add_argument("--state", required=True)
    record.add_argument("--decisions-file", required=True)
    record.set_defaults(handler=command_record)
    close = subparsers.add_parser("close")
    close.add_argument("--project-root", required=True)
    close.add_argument("--state", required=True)
    close.set_defaults(handler=command_close)
    status = subparsers.add_parser("status")
    status.add_argument("--project-root", required=True)
    status.add_argument("--state", required=True)
    status.set_defaults(handler=command_status)
    args = parser.parse_args(argv)
    try:
        payload = args.handler(args)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "error", "rule_id": getattr(exc, "rule_id", "VDD-CLARIFICATION-IO"), "detail": str(exc)}))
        return 1
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

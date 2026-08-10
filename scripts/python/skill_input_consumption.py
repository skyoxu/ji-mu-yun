#!/usr/bin/env python
"""Shared helpers for Skill input snapshots and consumption receipts."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "scripts" / "sc" / "schemas"
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SECRET_PATTERN = re.compile(
    r"(?i)(token|secret|password|api[_-]?key|authorization)\s*[\"']?\s*[:=]\s*[\"']?(\"[^\"\r\n]*\"|'[^'\r\n]*'|[^,\r\n;]+)"
)
BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")
API_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")


class SkillInputError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SkillInputError(f"invalid JSON: {path}: {exc}") from exc


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(path.name + ".staging")
    staged.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    staged.replace(path)


def contained_path(repository_root: Path, raw_path: str, *, must_exist: bool = True) -> tuple[Path, str]:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise SkillInputError("absolute source paths are not allowed")
    root = repository_root.resolve()
    resolved = (root / candidate).resolve()
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise SkillInputError("source path escapes repository root") from exc
    if must_exist and not resolved.exists():
        raise SkillInputError(f"source does not exist: {relative}")
    if resolved.is_symlink():
        raise SkillInputError(f"symlink source is not allowed: {relative}")
    return resolved, relative


def _git(repository_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository_root), *args],
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        raise SkillInputError(f"git command failed: {' '.join(args)}")
    return result.stdout.strip()


def repository_identity(repository_root: Path, scoped_paths: Iterable[str]) -> dict[str, str]:
    head = _git(repository_root, "rev-parse", "HEAD")
    index = subprocess.run(
        ["git", "-C", str(repository_root), "diff", "--cached", "--binary"],
        capture_output=True,
        check=False,
    ).stdout
    worktree = subprocess.run(
        ["git", "-C", str(repository_root), "diff", "--binary", "--", *sorted(set(scoped_paths))],
        capture_output=True,
        check=False,
    ).stdout
    return {
        "head": head,
        "index_hash": sha256_bytes(index),
        "scoped_worktree_hash": sha256_bytes(worktree),
    }


def contract_hash(contract_path: Path) -> str:
    try:
        return sha256_bytes(contract_path.read_bytes())
    except OSError as exc:
        raise SkillInputError(f"contract cannot be read: {contract_path}") from exc


def validate_contract(contract: dict[str, Any], repository_root: Path) -> None:
    required = {
        "schema_version", "consumer", "mode", "trigger", "source_roles", "operations",
        "reference_policy", "max_reference_depth", "max_sources", "max_context_bytes",
        "budget_basis", "sensitivity_policy", "redaction_profile", "forbidden_sources",
        "semantic_acceptance",
    }
    missing = required - set(contract)
    if missing:
        raise SkillInputError(f"contract missing required fields: {sorted(missing)}")
    if contract["schema_version"] != "skill-input-contract.v1" or contract["mode"] != "strict":
        raise SkillInputError("contract schema_version or mode is invalid")
    if contract["reference_policy"] != "declared-in-root-and-contained":
        raise SkillInputError("contract reference_policy is invalid")
    if contract["sensitivity_policy"] != "deny-credential-values" or contract["redaction_profile"] != "credential-values-v1":
        raise SkillInputError("contract sensitivity policy is invalid")
    if "logs-as-recovery-source" not in contract.get("forbidden_sources", []):
        raise SkillInputError("contract must forbid logs as recovery source")
    if not isinstance(contract["max_sources"], int) or not 0 < contract["max_sources"] <= 5000:
        raise SkillInputError("contract max_sources is invalid")
    if not isinstance(contract["max_context_bytes"], int) or not 512 <= contract["max_context_bytes"] <= 12000:
        raise SkillInputError("contract max_context_bytes is invalid")
    basis = contract["budget_basis"]
    if not isinstance(basis, dict) or not isinstance(basis.get("path"), str) or not SHA256_PATTERN.fullmatch(str(basis.get("sha256", ""))):
        raise SkillInputError("contract budget_basis is invalid")
    basis_path, _ = contained_path(repository_root, basis["path"])
    if sha256_bytes(basis_path.read_bytes()) != basis["sha256"]:
        raise SkillInputError("contract budget_basis hash mismatch")
    if not isinstance(contract["source_roles"], dict) or not isinstance(contract["operations"], dict):
        raise SkillInputError("contract source_roles or operations is invalid")


def redact_bytes(raw: bytes) -> tuple[bytes, str, str]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SkillInputError(f"source is not UTF-8: byte {exc.start}") from exc
    sensitivity = "credential-bearing" if (SECRET_PATTERN.search(text) or BEARER_PATTERN.search(text) or API_KEY_PATTERN.search(text)) else "normal"
    # Redact complete bearer/API credentials before generic key/value masking.
    redacted = BEARER_PATTERN.sub("Bearer <redacted>", text)
    redacted = API_KEY_PATTERN.sub("<redacted-api-key>", redacted)
    redacted = SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=<redacted>", redacted)
    status = "complete" if sensitivity == "credential-bearing" else "not-required"
    return redacted.encode("utf-8"), sensitivity, status


def expand_sources(repository_root: Path, raw_paths: list[str], max_sources: int) -> list[tuple[Path, str]]:
    expanded: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for raw in raw_paths:
        path, relative = contained_path(repository_root, raw)
        candidates = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
        for candidate in candidates:
            if candidate.is_symlink():
                raise SkillInputError(f"symlink source is not allowed: {candidate}")
            rel = candidate.relative_to(repository_root.resolve()).as_posix()
            if rel.startswith(".git/") or rel.startswith("logs/"):
                raise SkillInputError(f"forbidden source path: {rel}")
            if rel in seen:
                continue
            seen.add(rel)
            expanded.append((candidate, rel))
            if len(expanded) > max_sources:
                raise SkillInputError("source count exceeds contract max_sources")
    if not expanded:
        raise SkillInputError("no source files were discovered")
    return expanded


def line_ranges(raw: bytes) -> tuple[int, list[dict[str, int | str]]]:
    text = raw.decode("utf-8")
    lines = text.splitlines()
    if not lines:
        return 0, []
    return len(lines), [{"unit": "line", "start": 1, "end": len(lines)}]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

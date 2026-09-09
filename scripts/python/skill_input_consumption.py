#!/usr/bin/env python
"""Shared helpers for Skill input snapshots and consumption receipts."""

from __future__ import annotations

import hashlib
import fnmatch
import json
import os
import re
import stat
import subprocess
import uuid
from pathlib import Path, PureWindowsPath
from urllib.parse import unquote, urlsplit
from datetime import datetime, timezone
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "scripts" / "sc" / "schemas"
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
CONSUMER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
SELECTOR_PATTERN = re.compile(r"^[a-z0-9_]{3,80}$")
SECRET_PATTERN = re.compile(
    r"(?i)(token|secret|password|api[_-]?key|authorization)\s*[\"']?\s*[:=]\s*[\"']?(\"[^\"\r\n]*\"|'[^'\r\n]*'|[^,\r\n;]+)"
)
BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")
API_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z0-9 ]*PRIVATE KEY-----"
)
COMMON_TOKEN_PATTERN = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16})\b"
)
REDACTION_PROFILE_ID = "credential-values-v1"
DEFAULT_MAX_SNAPSHOT_BYTES = 262144


def is_reparse_point(path: Path) -> bool:
    """Return whether a path component is a link/reparse point without following it."""
    try:
        attributes = os.stat(path, follow_symlinks=False).st_file_attributes
    except (AttributeError, OSError):
        attributes = 0
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag) or path.is_symlink()


class SkillInputError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def artifact_identity_hash(path: Path) -> str:
    """Hash JSON artifacts by semantic content, other artifacts by bytes."""
    raw = path.read_bytes()
    if path.suffix.casefold() == ".json":
        try:
            return canonical_hash(json.loads(raw.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    return sha256_bytes(raw)


def redaction_profile_hash() -> str:
    """Bind semantic decisions to the exact v1 redaction rules."""
    return canonical_hash({
        "profile": REDACTION_PROFILE_ID,
        "secret_pattern": SECRET_PATTERN.pattern,
        "bearer_pattern": BEARER_PATTERN.pattern,
        "api_key_pattern": API_KEY_PATTERN.pattern,
        "private_key_pattern": PRIVATE_KEY_PATTERN.pattern,
        "common_token_pattern": COMMON_TOKEN_PATTERN.pattern,
        "replacement": {
            "secret": "<redacted>",
            "bearer": "Bearer <redacted>",
            "api_key": "<redacted-api-key>",
        },
    })


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SkillInputError(f"invalid JSON: {path}: {exc}") from exc


def write_json_atomic(path: Path, payload: Any, *, expected_bytes: bytes | None = None) -> None:
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    write_bytes_atomic(path, data, expected_bytes=expected_bytes)


def write_bytes_atomic(path: Path, data: bytes, *, expected_bytes: bytes | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.staging")
    with staged.open("wb") as handle:
        handle.write(data)
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except (AttributeError, OSError):
            pass
    if path.exists():
        try:
            current = path.read_bytes()
            if current == data:
                staged.unlink()
                return
            if expected_bytes is not None and current == expected_bytes:
                staged.replace(path)
                return
        except OSError:
            pass
        try:
            staged.unlink()
        except OSError:
            pass
        raise SkillInputError(f"atomic destination is not absent or byte-identical: {path}")
    staged.replace(path)


def forbidden_repository_path(relative: str) -> bool:
    normalized = relative.replace("\\", "/").casefold()
    return normalized == ".git" or normalized.startswith(".git/") or normalized == "logs" or normalized.startswith("logs/")


_SENSITIVE_REQUEST_KEYS = {
    "authorization", "credential", "credentials", "password", "secret",
    "token", "access_token", "refresh_token", "api_key", "apikey",
}


def validate_request_payload(value: Any, *, path: str = "request") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or not key:
                raise SkillInputError(f"{path} contains an invalid object key")
            normalized_key = key.casefold().replace("-", "_")
            if normalized_key in _SENSITIVE_REQUEST_KEYS and child not in (None, "", [], {}):
                raise SkillInputError(f"{path}.{key} may not persist credential material")
            validate_request_payload(child, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            validate_request_payload(child, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        if "\x00" in value:
            raise SkillInputError(f"{path} contains a NUL byte")
        if Path(value).is_absolute() or PureWindowsPath(value).is_absolute() or value.startswith(("/", "\\\\")):
            raise SkillInputError(f"{path} contains an absolute machine path")
        if _credential_like_text(value):
            raise SkillInputError(f"{path} may not persist credential material")
        return
    if value is not None and not isinstance(value, (bool, int, float)):
        raise SkillInputError(f"{path} contains a non-JSON value")


def contained_path(repository_root: Path, raw_path: str, *, must_exist: bool = True) -> tuple[Path, str]:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise SkillInputError("absolute source paths are not allowed")
    root = repository_root.resolve()
    joined = root / candidate
    current = joined
    while current != root and current != current.parent:
        if is_reparse_point(current):
            raise SkillInputError("symlink source is not allowed")
        current = current.parent
    resolved = joined.resolve()
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise SkillInputError("source path escapes repository root") from exc
    if must_exist and not resolved.exists():
        raise SkillInputError(f"source does not exist: {relative}")
    if is_reparse_point(joined) or is_reparse_point(resolved):
        raise SkillInputError(f"symlink source is not allowed: {relative}")
    return resolved, relative


def declared_missing_plan_files(repository_root: Path, target: Path) -> frozenset[str]:
    """Return missing bridge-created test paths explicitly declared by the target plan."""
    contract_path = target / "implementation-contract.v1.json" if target.is_dir() else target
    if contract_path.name != "implementation-contract.v1.json" or not contract_path.is_file():
        return frozenset()
    contract = read_json(contract_path)
    if not isinstance(contract, dict) or not isinstance(contract.get("slices"), list):
        return frozenset()
    allowed: set[str] = set()
    for slice_item in contract["slices"]:
        if not isinstance(slice_item, dict):
            continue
        planned = slice_item.get("planned_new_files", [])
        if not isinstance(planned, list):
            raise SkillInputError("planned_new_files must be an array")
        for raw_path in planned:
            if not isinstance(raw_path, str) or not raw_path:
                raise SkillInputError("planned_new_files contains an invalid path")
            resolved, relative = contained_path(repository_root, raw_path, must_exist=False)
            if resolved.exists():
                continue
            # Future planned files are intentionally absent before their
            # slice starts; they are not current Skill-input sources.
            allowed.add(relative)
    return frozenset(allowed)


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
    normalized_paths = sorted(set(scoped_paths))
    head = _git(repository_root, "rev-parse", "HEAD")
    index = subprocess.run(
        ["git", "-C", str(repository_root), "diff", "--cached", "--binary", "--", *normalized_paths],
        capture_output=True,
        check=False,
    ).stdout
    worktree = subprocess.run(
        ["git", "-C", str(repository_root), "diff", "--binary", "--", *normalized_paths],
        capture_output=True,
        check=False,
    ).stdout
    return {
        "head": head,
        "index_hash": sha256_bytes(index),
        "scoped_worktree_hash": sha256_bytes(worktree),
    }


def source_selection_hash(request_binding: dict[str, Any]) -> str:
    """Return the semantic identity of the declared source selection.

    This deliberately excludes execution provenance.  A clean commit after a
    frozen dirty worktree must not create a new input generation when the
    selected authority and its content are unchanged.
    """
    def normalize_selection(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: normalize_selection(value[key]) for key in sorted(value)}
        if isinstance(value, list):
            normalized = [normalize_selection(item) for item in value]
            return sorted(normalized, key=lambda item: canonical_bytes(item))
        return value

    return canonical_hash({
        "algorithm": "skill-input-source-selection.v1",
        "consumer": request_binding["consumer"],
        "operation": request_binding["operation"],
        "target": request_binding["target"],
        "source_roles": normalize_selection(request_binding["source_roles"]),
    })


def build_typed_source_selection_v2(
    sources: Iterable[dict[str, Any]],
    *,
    consumer: str = "quick-dev-tdd-adapter",
    policy_revision: str = "v2",
) -> dict[str, str]:
    """Compatibility facade for the strict ADR-0060 typed selector."""
    try:
        from .skill_input_selection import selection_identity
    except ImportError:
        from skill_input_selection import selection_identity
    try:
        return selection_identity(sources, consumer=consumer, policy_revision=policy_revision)
    except ValueError as exc:
        raise SkillInputError(str(exc)) from exc


def selected_source_content_root(sources: Iterable[tuple[Path, str]]) -> str:
    """Return a stable content root for the exact selected source set."""
    entries = [
        {"path": relative, "sha256": sha256_bytes(path.read_bytes())}
        for path, relative in sources
    ]
    return canonical_hash({
        "algorithm": "skill-input-selected-source-content.v1",
        "sources": sorted(entries, key=lambda entry: entry["path"]),
    })


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
    optional = {"max_snapshot_bytes", "semantic_input_mode", "max_snapshot_chunk_bytes"}
    unknown = set(contract) - required - optional
    if unknown:
        raise SkillInputError(f"contract contains unknown fields: {sorted(unknown)}")
    if contract["schema_version"] != "skill-input-contract.v1" or contract["mode"] != "strict":
        raise SkillInputError("contract schema_version or mode is invalid")
    if not isinstance(contract["consumer"], str) or not CONSUMER_PATTERN.fullmatch(contract["consumer"]):
        raise SkillInputError("contract consumer is invalid")
    if not isinstance(contract["trigger"], str) or not contract["trigger"]:
        raise SkillInputError("contract trigger is invalid")
    if contract["reference_policy"] != "declared-in-root-and-contained":
        raise SkillInputError("contract reference_policy is invalid")
    if contract["sensitivity_policy"] != "deny-credential-values" or contract["redaction_profile"] != "credential-values-v1":
        raise SkillInputError("contract sensitivity policy is invalid")
    if contract["semantic_acceptance"] != "all-required-inputs-are-sufficient":
        raise SkillInputError("contract semantic acceptance rule is invalid")
    forbidden_sources = contract.get("forbidden_sources")
    if (
        not isinstance(forbidden_sources, list)
        or any(not isinstance(item, str) or not item for item in forbidden_sources)
        or len(set(forbidden_sources)) != len(forbidden_sources)
        or "logs-as-recovery-source" not in forbidden_sources
    ):
        raise SkillInputError("contract must forbid logs as recovery source")
    if not isinstance(contract["max_reference_depth"], int) or not 1 <= contract["max_reference_depth"] <= 64:
        raise SkillInputError("contract max_reference_depth is invalid")
    if not isinstance(contract["max_sources"], int) or not 0 < contract["max_sources"] <= 5000:
        raise SkillInputError("contract max_sources is invalid")
    if not isinstance(contract["max_context_bytes"], int) or not 512 <= contract["max_context_bytes"] <= 12000:
        raise SkillInputError("contract max_context_bytes is invalid")
    max_snapshot_bytes = contract.get("max_snapshot_bytes", DEFAULT_MAX_SNAPSHOT_BYTES)
    if not isinstance(max_snapshot_bytes, int) or isinstance(max_snapshot_bytes, bool) or not 65536 <= max_snapshot_bytes <= 4194304:
        raise SkillInputError("contract max_snapshot_bytes is invalid")
    input_mode = contract.get("semantic_input_mode", "serialized-snapshot-stdin")
    if input_mode not in {"serialized-snapshot-stdin", "paged-frozen-snapshot-stdin"}:
        raise SkillInputError("contract semantic_input_mode is invalid")
    chunk_bytes = contract.get("max_snapshot_chunk_bytes")
    if input_mode == "paged-frozen-snapshot-stdin":
        if (
            not isinstance(chunk_bytes, int)
            or isinstance(chunk_bytes, bool)
            or not 4096 <= chunk_bytes <= 65536
            or chunk_bytes > max_snapshot_bytes
        ):
            raise SkillInputError("contract max_snapshot_chunk_bytes is invalid")
    elif chunk_bytes is not None:
        raise SkillInputError("serialized contract may not declare max_snapshot_chunk_bytes")
    basis = contract["budget_basis"]
    if not isinstance(basis, dict) or set(basis) != {"path", "sha256"} or not isinstance(basis.get("path"), str) or not SHA256_PATTERN.fullmatch(str(basis.get("sha256", ""))):
        raise SkillInputError("contract budget_basis is invalid")
    basis_path, _ = contained_path(repository_root, basis["path"])
    if not basis_path.is_file() or sha256_bytes(basis_path.read_bytes()) != basis["sha256"]:
        raise SkillInputError("contract budget_basis hash mismatch")
    try:
        budget = read_json(basis_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SkillInputError("contract budget_basis is not valid JSON") from exc
    if not isinstance(budget, dict) or budget.get("schema_version") != "skill-input-budget.v1":
        raise SkillInputError("contract budget_basis schema is invalid")
    budget_bindings = [
        ("max_context_bytes", contract["max_context_bytes"]),
        ("max_snapshot_bytes", max_snapshot_bytes),
        ("max_sources", contract["max_sources"]),
        ("max_reference_depth", contract["max_reference_depth"]),
    ]
    paging_fields = {"semantic_input_mode", "max_snapshot_chunk_bytes"}
    present_paging_fields = paging_fields & set(budget)
    if present_paging_fields and present_paging_fields != paging_fields:
        raise SkillInputError("contract budget_basis paging fields are incomplete")
    if present_paging_fields:
        budget_bindings.extend([
            ("semantic_input_mode", input_mode),
            ("max_snapshot_chunk_bytes", chunk_bytes),
        ])
    for field, effective in budget_bindings:
        if budget.get(field) != effective:
            raise SkillInputError(f"contract budget_basis does not bind {field}")
    source_roles = contract["source_roles"]
    operations = contract["operations"]
    if not isinstance(source_roles, dict) or not source_roles or not isinstance(operations, dict) or not operations:
        raise SkillInputError("contract source_roles or operations is invalid")
    for role_name, role in source_roles.items():
        if not isinstance(role_name, str) or not role_name or not isinstance(role, dict):
            raise SkillInputError("contract source role is invalid")
        allowed_role_fields = {"selector", "required", "root", "allowed_kinds", "reference_kinds", "opaque_reference_paths", "payload"}
        if not set(role).issubset(allowed_role_fields) or not {"selector", "required", "root", "allowed_kinds", "reference_kinds"}.issubset(role):
            raise SkillInputError(f"contract source role fields are invalid: {role_name}")
        if not isinstance(role["selector"], str) or not SELECTOR_PATTERN.fullmatch(role["selector"]):
            raise SkillInputError(f"contract source role selector is invalid: {role_name}")
        if type(role["required"]) is not bool or not isinstance(role["root"], str) or not role["root"]:
            raise SkillInputError(f"contract source role metadata is invalid: {role_name}")
        if "payload" in role and type(role["payload"]) is not bool:
            raise SkillInputError(f"contract source role payload is invalid: {role_name}")
        for field, allowed in (("allowed_kinds", {"file", "directory"}), ("reference_kinds", {"markdown-link", "json-path-field"})):
            values = role[field]
            if not isinstance(values, list) or any(not isinstance(item, str) for item in values) or len(set(values)) != len(values) or not values or any(item not in allowed for item in values):
                if field == "reference_kinds" and values == []:
                    continue
                raise SkillInputError(f"contract source role {field} is invalid: {role_name}")
        opaque = role.get("opaque_reference_paths", [])
        if (
            not isinstance(opaque, list)
            or any(not isinstance(item, str) or not item or Path(item).is_absolute() or ".." in Path(item).parts for item in opaque)
            or len(set(opaque)) != len(opaque)
        ):
            raise SkillInputError(f"contract source role opaque_reference_paths is invalid: {role_name}")
    for operation_name, operation in operations.items():
        if operation_name not in {"create", "repair", "review", "execute", "acceptance"} or not isinstance(operation, dict) or set(operation) != {"required_inputs"}:
            raise SkillInputError(f"contract operation is invalid: {operation_name}")
        required_inputs = operation["required_inputs"]
        if not isinstance(required_inputs, list) or not required_inputs or any(not isinstance(item, str) or not item or item not in source_roles for item in required_inputs) or len(set(required_inputs)) != len(required_inputs):
            raise SkillInputError(f"contract operation required_inputs are invalid: {operation_name}")


_MARKDOWN_INLINE_START = re.compile(r"!?\[[^\]\r\n]*\]\(\s*")
_MARKDOWN_REFERENCE_DEFINITION = re.compile(
    r"(?m)^[ \t]{0,3}\[([^\]\r\n]+)\]:[ \t]*(?:<([^>\r\n]+)>|([^\s\r\n]+))(?:[ \t]+[^\r\n]*)?[ \t]*\r?$"
)
_MARKDOWN_REFERENCE_USE = re.compile(r"!?\[([^\]\r\n]+)\]\[([^\]\r\n]*)\]")
_MARKDOWN_SHORTCUT_USE = re.compile(r"!?\[([^\]\r\n]+)\]")
_MARKDOWN_AUTOLINK = re.compile(r"<((?:[A-Za-z][A-Za-z0-9+.-]*:|//)[^>\s]+)>")
_JSON_REFERENCE_SUFFIXES = {
    "path", "paths", "file", "files", "filepath", "filepaths", "filename", "filenames",
    "directory", "directories",
}


def _is_json_reference_field(key: str) -> bool:
    # Diagnostic inventories bind names for audit, not semantic dependencies.
    # Treating them as source edges recursively imports every historical path.
    # Planned/future file declarations are also metadata: they describe files
    # that a later lifecycle slice may create, not sources consumed by the
    # current Skill-input operation. Following them makes a repair fail on
    # intentionally absent runtime artifacts (for example predecessor freezes).
    if key.casefold() in {"affected_paths", "planned_files", "planned_new_files"}:
        return False
    if key.casefold() == "$ref":
        return True
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    tokens = re.findall(r"[a-z0-9]+", separated.casefold())
    return bool(tokens) and tokens[-1] in _JSON_REFERENCE_SUFFIXES


def _markdown_label(value: str) -> str:
    return " ".join(value.split()).casefold()


def _markdown_semantic_text(text: str) -> str:
    """Mask Markdown regions whose link-looking text is literal content."""
    masked = list(text)

    def mask(start: int, end: int) -> None:
        for index in range(start, end):
            if masked[index] not in "\r\n":
                masked[index] = " "

    for match in re.finditer(r"(?s)<!--.*?(?:-->|\Z)", text):
        mask(*match.span())

    fence = re.compile(r"(?m)^[ \t]{0,3}(`{3,}|~{3,})[^\r\n]*(?:\r?\n|\Z)")
    position = 0
    while True:
        opening = fence.search(text, position)
        if opening is None:
            break
        marker = opening.group(1)
        closing = re.compile(
            rf"(?m)^[ \t]{{0,3}}{re.escape(marker[0])}{{{len(marker)},}}[ \t]*(?:\r?$)"
        ).search(text, opening.end())
        end = closing.end() if closing is not None else len(text)
        mask(opening.start(), end)
        position = end

    index = 0
    while index < len(text):
        if text[index] != "`" or (index > 0 and text[index - 1] == "\\"):
            index += 1
            continue
        end_marker = index
        while end_marker < len(text) and text[end_marker] == "`":
            end_marker += 1
        marker = text[index:end_marker]
        closing = text.find(marker, end_marker)
        if closing < 0:
            index = end_marker
            continue
        mask(index, closing + len(marker))
        index = closing + len(marker)
    return "".join(masked)


def _markdown_match_is_escaped(text: str, start: int) -> bool:
    backslashes = 0
    index = start - 1
    while index >= 0 and text[index] == "\\":
        backslashes += 1
        index -= 1
    return backslashes % 2 == 1


def _markdown_inline_close(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t":
        index += 1
    if index < len(text) and text[index] in {'"', "'", "("}:
        opening = text[index]
        closing = ")" if opening == "(" else opening
        index += 1
        escaped = False
        while index < len(text):
            if escaped:
                escaped = False
            elif text[index] == "\\":
                escaped = True
            elif text[index] == closing:
                index += 1
                break
            elif text[index] in "\r\n":
                raise SkillInputError("Markdown inline reference title is incomplete")
            index += 1
        else:
            raise SkillInputError("Markdown inline reference title is incomplete")
        while index < len(text) and text[index] in " \t":
            index += 1
    if index >= len(text) or text[index] != ")":
        raise SkillInputError("Markdown inline reference is incomplete")
    return index


def _markdown_inline_targets(text: str) -> list[str]:
    """Parse inline Markdown destinations with balanced parentheses."""
    targets: list[str] = []
    for match in _MARKDOWN_INLINE_START.finditer(text):
        if _markdown_match_is_escaped(text, match.start()):
            continue
        index = match.end()
        if index >= len(text):
            raise SkillInputError("Markdown inline reference is incomplete")
        if text[index] == "<":
            end = text.find(">", index + 1)
            if end < 0:
                raise SkillInputError("Markdown angle-bracket destination is incomplete")
            target = text[index + 1:end]
            _markdown_inline_close(text, end + 1)
            targets.append(target)
            continue
        start = index
        depth = 0
        escaped = False
        while index < len(text):
            character = text[index]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "(":
                depth += 1
            elif character == ")":
                if depth == 0:
                    break
                depth -= 1
            elif character.isspace() and depth == 0:
                break
            index += 1
        if index == start or index >= len(text):
            raise SkillInputError("Markdown inline reference is incomplete")
        target = text[start:index]
        _markdown_inline_close(text, index)
        targets.append(target.replace("\\(", "(").replace("\\)", ")"))
    return targets


def _markdown_reference_targets(text: str) -> list[str]:
    definitions: dict[str, str] = {}
    occupied: list[tuple[int, int]] = []
    for match in _MARKDOWN_REFERENCE_DEFINITION.finditer(text):
        if _markdown_match_is_escaped(text, match.start()):
            continue
        label = _markdown_label(match.group(1))
        target = match.group(2) or match.group(3)
        if label in definitions and definitions[label] != target:
            raise SkillInputError(f"ambiguous Markdown reference definition: {match.group(1)}")
        definitions[label] = target
        occupied.append(match.span())
    targets: list[str] = []
    for match in _MARKDOWN_REFERENCE_USE.finditer(text):
        if _markdown_match_is_escaped(text, match.start()):
            continue
        raw_label = match.group(2) or match.group(1)
        label = _markdown_label(raw_label)
        if label not in definitions:
            raise SkillInputError(f"unresolved Markdown reference label: {raw_label}")
        targets.append(definitions[label])
        occupied.append(match.span())
    for match in _MARKDOWN_INLINE_START.finditer(text):
        occupied.append(match.span())
    for match in _MARKDOWN_SHORTCUT_USE.finditer(text):
        if _markdown_match_is_escaped(text, match.start()):
            continue
        if any(start <= match.start() < end for start, end in occupied):
            continue
        label = _markdown_label(match.group(1))
        if label in definitions:
            targets.append(definitions[label])
    return targets


def _reference_values(path: Path, reference_kinds: set[str]) -> list[str]:
    raw = path.read_bytes()
    values: list[str] = []
    if "markdown-link" in reference_kinds and path.suffix.lower() in {".md", ".markdown", ".mdx"}:
        text = _markdown_semantic_text(raw.decode("utf-8"))
        values.extend(_markdown_inline_targets(text))
        values.extend(_markdown_reference_targets(text))
        values.extend(match.group(1) for match in _MARKDOWN_AUTOLINK.finditer(text))
    if "json-path-field" in reference_kinds and path.suffix.lower() == ".json":
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SkillInputError(f"JSON reference source is invalid: {path}") from exc

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    # Hash-bound artifact references are custody metadata, not
                    # semantic source dependencies. Following their path field
                    # recursively makes closure/receipt graphs self-referential.
                    if key == "path" and isinstance(value.get("sha256"), str):
                        visit(child)
                        continue
                    if isinstance(key, str) and _is_json_reference_field(key):
                        if isinstance(child, str):
                            values.append(child)
                        elif isinstance(child, list):
                            values.extend(item for item in child if isinstance(item, str))
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(payload)
    return list(dict.fromkeys(values))


def _resolve_reference(
    repository_root: Path,
    source: Path,
    raw_reference: str,
    reference_root: Path,
    allowed_missing_references: frozenset[str] = frozenset(),
) -> tuple[Path, str] | None:
    reference = raw_reference.strip().strip("<>")
    if not reference or reference.startswith("#"):
        return None
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc or reference.startswith("//"):
        raise SkillInputError(f"external reference is forbidden: {raw_reference}")
    if any(character in reference for character in "*?[]"):
        return None
    target_text = unquote(parsed.path)
    if not target_text:
        return None
    try:
        repository_resolved = repository_root.resolve()
        source.resolve().relative_to(repository_resolved)
        root_relative = reference_root.resolve().relative_to(repository_resolved)
        ancestor_candidates: list[str] = []
        ancestor = source.resolve().parent
        while True:
            ancestor_relative = ancestor.relative_to(repository_resolved)
            ancestor_candidates.append((ancestor_relative / target_text).as_posix())
            if ancestor == repository_resolved:
                break
            ancestor = ancestor.parent
        candidates = ancestor_candidates + [(root_relative / target_text).as_posix(), target_text]
    except ValueError as exc:
        raise SkillInputError("reference source escapes repository") from exc
    for candidate in dict.fromkeys(candidates):
        try:
            resolved, relative = contained_path(repository_root, candidate)
        except SkillInputError:
            continue
        if forbidden_repository_path(relative):
            raise SkillInputError(f"forbidden reference path: {relative}")
        return resolved, relative
    for candidate in dict.fromkeys(candidates):
        try:
            _resolved, relative = contained_path(repository_root, candidate, must_exist=False)
        except SkillInputError:
            continue
        if relative in allowed_missing_references:
            return None
    if not (
        target_text.startswith(".")
        or "/" in target_text
        or "\\" in target_text
        or bool(Path(target_text).suffix)
    ):
        return None
    raise SkillInputError(f"referenced source does not exist: {raw_reference}")


def generated_artifact_exclusions(repository_root: Path, target: Path) -> frozenset[str]:
    """Exclude generated lifecycle/evidence artifacts from their own source graph.

    The exclusion is intentionally type-based rather than tied to one receipt
    filename. Authoritative requirements, contracts, and repair findings remain
    selectable; mutable projections and derived evidence do not become their
    own Skill-input authority.
    """
    root = repository_root.resolve()
    target = target.resolve()
    if not target.is_dir():
        return frozenset()
    exact_names = {
        "plan-state.v1.json",
        "resume-state.v1.json",
        "implementation-authorization-receipt.v1.json",
        "repair-closure.json",
    }
    directory_names = {
        "__pycache__",
        "acceptance-inputs",
        "repair",
        "skill-input",
        "terminal-results",
        "attempts",
        "pages",
        "sidecars",
        "knowledge-context.history",
        "knowledge-context.freeze.history",
    }
    file_patterns = (
        "skill-input*",
        "semantic-input*",
        "knowledge-context*",
        "95-*.md",
        "*terminal-result*.json",
        "*implementation-complete*.json",
        "implementation-authorization-receipt*.json",
        "*acceptance-result*.json",
        "changed-set*.json",
        "root-cause*.json",
        "sibling-disposition*.json",
        "composition*.json",
        "*retry*.json",
        "*page*.json",
        "*sidecar*.json",
        "*.pyc",
    )
    excluded: set[str] = set()
    for item in target.rglob("*"):
        relative = item.relative_to(root).as_posix()
        if item.is_dir() and (item.name in directory_names or item.name.startswith("skill-input-output")):
            excluded.add(relative)
            continue
        if item.is_file() and (item.name in exact_names or any(fnmatch.fnmatchcase(item.name, pattern) for pattern in file_patterns)):
            excluded.add(relative)
    return frozenset(excluded)


def expand_source_graph(
    repository_root: Path,
    contract: dict[str, Any],
    operation: str,
    role_values: dict[str, list[str]],
    allowed_missing_references: frozenset[str] = frozenset(),
    excluded_paths: frozenset[str] = frozenset(),
) -> list[tuple[Path, str]]:
    """Expand explicit role roots and their declared in-boundary references."""
    validate_contract(contract, repository_root)
    if operation not in contract["operations"]:
        raise SkillInputError("operation is not declared by contract")
    required_roles = contract["operations"][operation]["required_inputs"]
    if any(role not in role_values for role in required_roles):
        missing = sorted(set(required_roles) - set(role_values))
        raise SkillInputError(f"required source role is missing: {missing}")
    queue: list[tuple[Path, int, frozenset[str], set[str], Path, str | None, frozenset[str], bool]] = []
    for role_name, raw_paths in role_values.items():
        role = contract["source_roles"].get(role_name)
        if not isinstance(role, dict) or not isinstance(raw_paths, list) or not raw_paths:
            raise SkillInputError(f"source role values are invalid: {role_name}")
        for raw_path in raw_paths:
            root_path, relative_root = contained_path(repository_root, raw_path)
            declared_root = role["root"].rstrip("/")
            if declared_root != "repository" and relative_root != declared_root and not relative_root.startswith(declared_root + "/"):
                raise SkillInputError(f"source does not satisfy role root: {raw_path}")
            kind = "directory" if root_path.is_dir() else "file"
            if kind not in role["allowed_kinds"]:
                raise SkillInputError(f"source kind is not allowed for role: {role_name}")
            reference_root = root_path if root_path.is_dir() else root_path.parent
            opaque_paths: set[str] = set()
            for raw_path in role.get("opaque_reference_paths", []):
                opaque_path = (reference_root / raw_path).resolve()
                try:
                    opaque_relative = opaque_path.relative_to(repository_root.resolve()).as_posix()
                    opaque_path.relative_to(reference_root.resolve())
                except ValueError as exc:
                    raise SkillInputError("opaque reference path escapes its source root") from exc
                opaque_paths.add(opaque_relative)
            # Explicit target selection is still subject to the contract's
            # opaque boundary. A caller must not smuggle lifecycle/evidence
            # artifacts back into the Skill input by naming them directly.
            if role_name == "target_files":
                for raw_path in raw_paths:
                    _selected_path, selected_relative = contained_path(repository_root, raw_path)
                    if selected_relative in opaque_paths or any(
                        selected_relative.startswith(prefix + "/") for prefix in opaque_paths
                    ):
                        raise SkillInputError(
                            f"target_files selects opaque lifecycle path: {selected_relative}"
                        )
            queue.append((root_path, 0, frozenset(), set(role["reference_kinds"]), reference_root, None, frozenset(opaque_paths), role.get("payload", True)))
    expanded: list[tuple[Path, str]] = []
    seen: set[str] = set()
    while queue:
        candidate_root, depth, ancestors, reference_kinds, reference_root, referrer, opaque_paths, payload = queue.pop(0)
        candidates = ([candidate_root] if candidate_root.is_file() else sorted(item for item in candidate_root.rglob("*") if item.is_file())) if payload else []
        for candidate in candidates:
            if is_reparse_point(candidate):
                raise SkillInputError(f"symlink source is not allowed: {candidate}")
            relative = candidate.resolve().relative_to(repository_root.resolve()).as_posix()
            if "__pycache__" in Path(relative).parts or relative.endswith(".pyc"):
                continue
            if relative in excluded_paths or any(
                relative.startswith(prefix + "/") for prefix in excluded_paths
            ):
                continue
            if forbidden_repository_path(relative):
                raise SkillInputError(f"forbidden source path: {relative}")
            if any(relative.startswith(prefix + "/") for prefix in opaque_paths):
                continue
            if relative in ancestors:
                if relative == referrer:
                    # A contract may hash-bind itself in its dependency closure.
                    # This direct self-reference adds no source; multi-file
                    # cycles continue to fail closed.
                    continue
                raise SkillInputError(f"reference cycle detected: {relative}")
            if relative not in seen:
                seen.add(relative)
                expanded.append((candidate.resolve(), relative))
                if len(expanded) > contract["max_sources"]:
                    raise SkillInputError("source count exceeds contract max_sources")
            if relative in opaque_paths:
                continue
            if not reference_kinds:
                continue
            if depth >= contract["max_reference_depth"]:
                references = _reference_values(candidate, reference_kinds)
                if references:
                    raise SkillInputError("reference depth exceeds contract max_reference_depth")
                continue
            for raw_reference in _reference_values(candidate, reference_kinds):
                raw_parts = Path(raw_reference.replace("\\", "/")).parts
                if "__pycache__" in raw_parts or raw_reference.replace("\\", "/").endswith(".pyc"):
                    continue
                resolved, _ = _resolve_reference(
                    repository_root,
                    candidate,
                    raw_reference,
                    reference_root,
                    allowed_missing_references,
                ) or (None, None)
                if resolved is None:
                    continue
                next_ancestors = frozenset(set(ancestors) | {relative})
                resolved_path = resolved.resolve()
                try:
                    resolved_relative = resolved_path.relative_to(repository_root.resolve()).as_posix()
                except ValueError as exc:
                    raise SkillInputError("reference escapes repository") from exc
                if resolved_relative in excluded_paths or any(
                    resolved_relative.startswith(prefix + "/") for prefix in excluded_paths
                ):
                    # Generated evidence and interpreter caches are excluded from
                    # the source graph even when an older manifest still names
                    # them explicitly.
                    continue
                inside_reference_root = resolved_path == reference_root or reference_root in resolved_path.parents
                next_reference_kinds = set(reference_kinds) if inside_reference_root else set()
                # External directory references are boundary metadata, not an
                # instruction to ingest an entire dependency package. Keep
                # direct file references, while expanding directories only
                # when they remain inside the declared reference root.
                expand_directory = resolved_path.is_file() or inside_reference_root
                queue.append((resolved_path, depth + 1, next_ancestors, next_reference_kinds, reference_root, relative, opaque_paths, expand_directory))
    if not expanded:
        raise SkillInputError("no source files were discovered")
    return sorted(expanded, key=lambda item: item[1])


def redact_bytes(raw: bytes) -> tuple[bytes, str, str]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SkillInputError(f"source is not UTF-8: byte {exc.start}") from exc
    sensitivity = "credential-bearing" if _credential_like_text(text) else "normal"
    # Preserve JSON structure when a sensitive key contains an object. The
    # legacy text regex can otherwise replace the value together with braces,
    # producing an invalid model snapshot.
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, (dict, list)):
        def redact_json(value: Any) -> Any:
            if isinstance(value, dict):
                result: dict[str, Any] = {}
                for key, child in value.items():
                    if (
                        isinstance(key, str)
                        and "/" not in key
                        and "\\" not in key
                        and re.search(r"(?i)(token|secret|password|api[_-]?key|authorization)", key)
                    ):
                        result[key] = "<redacted>"
                    elif isinstance(key, str) and key.casefold() in {"affected_paths", "changed_paths"} and isinstance(child, list):
                        result[key] = {
                            "omitted_count": len(child),
                            "canonical_sha256": sha256_bytes(canonical_bytes(child)),
                        }
                    else:
                        result[key] = redact_json(child)
                return result
            if isinstance(value, list):
                return [redact_json(child) for child in value]
            if isinstance(value, str):
                masked = BEARER_PATTERN.sub("Bearer <redacted>", value)
                masked = API_KEY_PATTERN.sub("<redacted-api-key>", masked)
                masked = PRIVATE_KEY_PATTERN.sub("<redacted-private-key>", masked)
                return COMMON_TOKEN_PATTERN.sub("<redacted-token>", masked)
            return value

        return (
            (json.dumps(redact_json(parsed), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"),
            sensitivity,
            "complete" if sensitivity == "credential-bearing" else "not-required",
        )
    # Redact complete bearer/API credentials before generic key/value masking.
    redacted = BEARER_PATTERN.sub("Bearer <redacted>", text)
    redacted = API_KEY_PATTERN.sub("<redacted-api-key>", redacted)
    redacted = PRIVATE_KEY_PATTERN.sub("<redacted-private-key>", redacted)
    redacted = COMMON_TOKEN_PATTERN.sub("<redacted-token>", redacted)
    redacted = SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=<redacted>", redacted)
    status = "complete" if sensitivity == "credential-bearing" else "not-required"
    return redacted.encode("utf-8"), sensitivity, status


def _credential_like_text(value: str) -> bool:
    return bool(
        SECRET_PATTERN.search(value)
        or BEARER_PATTERN.search(value)
        or API_KEY_PATTERN.search(value)
        or PRIVATE_KEY_PATTERN.search(value)
        or COMMON_TOKEN_PATTERN.search(value)
    )


def line_ranges(raw: bytes) -> tuple[int, list[dict[str, int | str]]]:
    text = raw.decode("utf-8")
    lines = text.splitlines()
    if not lines:
        return 0, []
    return len(lines), [{"unit": "line", "start": 1, "end": len(lines)}]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


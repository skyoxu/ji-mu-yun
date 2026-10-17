from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from _util import repo_root


# ADR-0049 keeps reuse decisions controller-owned. This identity makes that
# decision depend on the reviewed bytes instead of Git path-state alone.
GIT_FINGERPRINT_SCHEMA = "sc-review-git-fingerprint.v2"
CONTENT_IDENTITY_SCHEMA = "sc-review-worktree-content.v1"
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONTENT_IDENTITY_KEYS = {
    "schema_version",
    "head",
    "status_short",
    "tracked_worktree_diff_sha256",
    "tracked_worktree_manifest_sha256",
    "tracked_worktree_file_count",
    "index_diff_sha256",
    "untracked_manifest_sha256",
    "untracked_file_count",
    "complete",
    "snapshot_sha256",
    "error_codes",
}
_RESULT_DETERMINING_INPUT_CATEGORIES = {
    "git_baseline",
    "skill_input_v2_selection",
    "skill_input_v2_content",
    "code",
    "fixtures",
    "contracts",
    "consumers",
    "tests",
    "targets",
    "validators",
    "dependencies",
    "sources",
    "evidence",
    "normalization_policy",
}


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256(encoded)


def _run_git_bytes(args: list[str], *, root: Path, timeout_sec: int = 60) -> tuple[int, bytes]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout_sec,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return 1, b""
    return int(proc.returncode or 0), bytes(proc.stdout or b"")


def _decode_lines(raw: bytes) -> list[str]:
    return sorted(
        line.rstrip()
        for line in raw.decode("utf-8", errors="replace").splitlines()
        if line.strip()
    )


def _worktree_content_manifest(
    root: Path,
    raw_paths: bytes,
    *,
    error_prefix: str,
) -> tuple[list[dict[str, str]], list[str]]:
    entries: list[dict[str, str]] = []
    errors: list[str] = []
    for raw_path in sorted(item for item in raw_paths.split(b"\0") if item):
        try:
            relative = raw_path.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            errors.append(f"{error_prefix}_path_not_utf8")
            continue
        path = root / Path(relative)
        try:
            if path.is_symlink():
                payload = os.readlink(path).encode("utf-8")
                kind = "symlink"
            elif path.is_file():
                payload = path.read_bytes()
                kind = "file"
            elif not path.exists():
                entries.append({"path": relative.replace("\\", "/"), "kind": "absent", "sha256": ""})
                continue
            else:
                errors.append(f"{error_prefix}_path_not_file")
                continue
        except OSError:
            errors.append(f"{error_prefix}_file_read_failed")
            continue
        entries.append({"path": relative.replace("\\", "/"), "kind": kind, "sha256": _sha256(payload)})
    return entries, sorted(set(errors))


def current_git_fingerprint(*, root: Path | None = None) -> dict[str, Any]:
    resolved_root = (root or repo_root()).resolve()
    rc_head, raw_head = _run_git_bytes(["rev-parse", "HEAD"], root=resolved_root, timeout_sec=30)
    rc_status, raw_status = _run_git_bytes(
        ["status", "--short", "--untracked-files=all"],
        root=resolved_root,
        timeout_sec=30,
    )
    diff_options = ["--binary", "--full-index", "--no-ext-diff", "--no-textconv", "--no-color", "--no-renames"]
    rc_worktree, raw_worktree = _run_git_bytes(["diff", *diff_options, "--"], root=resolved_root)
    rc_index, raw_index = _run_git_bytes(["diff", "--cached", *diff_options, "--"], root=resolved_root)
    rc_tracked_paths, raw_tracked_paths = _run_git_bytes(
        ["diff", "--name-only", "-z", "--no-ext-diff", "--no-renames", "--"],
        root=resolved_root,
    )
    rc_untracked, raw_untracked = _run_git_bytes(
        ["ls-files", "--others", "--exclude-standard", "-z"],
        root=resolved_root,
    )
    rc_index_flags, raw_index_flags = _run_git_bytes(["ls-files", "-v", "-z"], root=resolved_root)

    tracked_entries: list[dict[str, str]] = []
    untracked_entries: list[dict[str, str]] = []
    tracked_errors: list[str] = []
    untracked_errors: list[str] = []
    errors: list[str] = []
    if rc_tracked_paths == 0:
        tracked_entries, tracked_errors = _worktree_content_manifest(
            resolved_root,
            raw_tracked_paths,
            error_prefix="tracked_worktree",
        )
        errors.extend(tracked_errors)
    else:
        errors.append("git_tracked_worktree_list_failed")
    if rc_untracked == 0:
        untracked_entries, untracked_errors = _worktree_content_manifest(
            resolved_root,
            raw_untracked,
            error_prefix="untracked",
        )
        errors.extend(untracked_errors)
    else:
        errors.append("git_untracked_list_failed")
    for rc, code in (
        (rc_head, "git_head_failed"),
        (rc_status, "git_status_failed"),
        (rc_worktree, "git_worktree_diff_failed"),
        (rc_index, "git_index_diff_failed"),
        (rc_index_flags, "git_index_flags_failed"),
    ):
        if rc != 0:
            errors.append(code)
    if rc_index_flags == 0:
        special_index_flags = []
        for row in (item for item in raw_index_flags.split(b"\0") if item):
            tag = chr(row[0])
            if tag == "S" or tag.islower():
                special_index_flags.append(tag)
        if special_index_flags:
            errors.append("git_special_index_flags_present")

    head = raw_head.decode("utf-8", errors="replace").strip() if rc_head == 0 else ""
    status_short = _decode_lines(raw_status) if rc_status == 0 else []
    identity_inputs = {
        "schema_version": CONTENT_IDENTITY_SCHEMA,
        "head": head,
        "status_short": status_short,
        "tracked_worktree_diff_sha256": _sha256(raw_worktree) if rc_worktree == 0 else "",
        "tracked_worktree_manifest_sha256": _canonical_hash(tracked_entries) if rc_tracked_paths == 0 and not tracked_errors else "",
        "tracked_worktree_file_count": len(tracked_entries),
        "index_diff_sha256": _sha256(raw_index) if rc_index == 0 else "",
        "untracked_manifest_sha256": _canonical_hash(untracked_entries) if rc_untracked == 0 and not untracked_errors else "",
        "untracked_file_count": len(untracked_entries),
    }
    result_determining_inputs = {
        category: {
            "immutable_identity": _canonical_hash(
                {"category": category, "snapshot_inputs": identity_inputs}
            )
        }
        for category in sorted(_RESULT_DETERMINING_INPUT_CATEGORIES)
    }
    complete = not errors
    snapshot_inputs = {
        **identity_inputs,
        "result_determining_inputs": result_determining_inputs,
    }
    return {
        "schema_version": GIT_FINGERPRINT_SCHEMA,
        "head": head,
        "status_short": status_short,
        "result_determining_inputs": result_determining_inputs,
        "content_identity": {
            **identity_inputs,
            "complete": complete,
            "snapshot_sha256": _canonical_hash(snapshot_inputs) if complete else "",
            "error_codes": sorted(set(errors)),
        },
    }


def has_complete_content_identity(value: dict[str, Any] | None) -> bool:
    payload = value if isinstance(value, dict) else {}
    identity = payload.get("content_identity") if isinstance(payload.get("content_identity"), dict) else {}
    if set(payload) != {
        "schema_version",
        "head",
        "status_short",
        "result_determining_inputs",
        "content_identity",
    }:
        return False
    if set(identity) != _CONTENT_IDENTITY_KEYS:
        return False
    if payload.get("schema_version") != GIT_FINGERPRINT_SCHEMA or identity.get("schema_version") != CONTENT_IDENTITY_SCHEMA:
        return False
    head = payload.get("head")
    status_short = payload.get("status_short")
    if not isinstance(head, str) or re.fullmatch(r"[0-9a-f]{40,64}", head) is None:
        return False
    if not isinstance(status_short, list) or not all(isinstance(item, str) and item.strip() for item in status_short):
        return False
    if identity.get("head") != head or identity.get("status_short") != status_short:
        return False
    result_inputs = payload.get("result_determining_inputs")
    if not isinstance(result_inputs, dict) or set(result_inputs) != _RESULT_DETERMINING_INPUT_CATEGORIES:
        return False
    if any(
        not isinstance(entry, dict)
        or set(entry) != {"immutable_identity"}
        or not isinstance(entry.get("immutable_identity"), str)
        or _SHA256_RE.fullmatch(entry["immutable_identity"]) is None
        for entry in result_inputs.values()
    ):
        return False
    for key in (
        "tracked_worktree_diff_sha256",
        "tracked_worktree_manifest_sha256",
        "index_diff_sha256",
        "untracked_manifest_sha256",
        "snapshot_sha256",
    ):
        if not isinstance(identity.get(key), str) or _SHA256_RE.fullmatch(identity[key]) is None:
            return False
    for key in ("tracked_worktree_file_count", "untracked_file_count"):
        if not isinstance(identity.get(key), int) or isinstance(identity.get(key), bool) or identity[key] < 0:
            return False
    if identity.get("complete") is not True or identity.get("error_codes") != []:
        return False
    identity_inputs = {key: identity[key] for key in _CONTENT_IDENTITY_KEYS - {"complete", "snapshot_sha256", "error_codes"}}
    if any(
        entry["immutable_identity"]
        != _canonical_hash({"category": category, "snapshot_inputs": identity_inputs})
        for category, entry in result_inputs.items()
    ):
        return False
    snapshot_inputs = {**identity_inputs, "result_determining_inputs": result_inputs}
    return identity.get("snapshot_sha256") == _canonical_hash(snapshot_inputs)


def uses_versioned_content_identity(value: dict[str, Any] | None) -> bool:
    payload = value if isinstance(value, dict) else {}
    return (
        "schema_version" in payload
        or "content_identity" in payload
        or "result_determining_inputs" in payload
    )


def same_head_and_status(previous: dict[str, Any] | None, current: dict[str, Any] | None) -> bool:
    left = previous if isinstance(previous, dict) else {}
    right = current if isinstance(current, dict) else {}
    left_status = sorted(str(line).rstrip() for line in (left.get("status_short") or []) if str(line).strip())
    right_status = sorted(str(line).rstrip() for line in (right.get("status_short") or []) if str(line).strip())
    return str(left.get("head") or "").strip() == str(right.get("head") or "").strip() and left_status == right_status


def git_snapshots_match(previous: dict[str, Any] | None, current: dict[str, Any] | None) -> bool:
    left = previous if isinstance(previous, dict) else {}
    right = current if isinstance(current, dict) else {}
    if uses_versioned_content_identity(left) or uses_versioned_content_identity(right):
        if not has_complete_content_identity(left) or not has_complete_content_identity(right):
            return False
        left_identity = left["content_identity"]
        right_identity = right["content_identity"]
        return (
            str(left.get("head") or "").strip() == str(right.get("head") or "").strip()
            and left_identity.get("snapshot_sha256") == right_identity.get("snapshot_sha256")
        )
    return same_head_and_status(left, right)

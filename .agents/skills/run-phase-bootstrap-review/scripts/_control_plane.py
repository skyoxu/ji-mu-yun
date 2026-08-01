"""Deterministic execution and evidence primitives for Bootstrap Review."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import secrets
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HASH_PREFIX = "sha256:"
ENVIRONMENT_ALLOWLIST = (
    "APPDATA", "CODEX_HOME", "COMSPEC", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA",
    "CURL_CA_BUNDLE", "HOME", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
    "NODE_EXTRA_CA_CERTS", "OPENAI_API_KEY", "PATH", "PATHEXT", "PROGRAMDATA",
    "SSL_CERT_FILE", "SYSTEMDRIVE", "SYSTEMROOT", "TEMP", "TMP", "USERDOMAIN",
    "USERNAME", "USERPROFILE", "WINDIR", "http_proxy", "https_proxy", "no_proxy",
)
TYPED_PLACEHOLDERS = {
    "codex_command": "executable_path",
    "model": "model_id",
    "reasoning_effort": "enum:medium|high|max",
    "sandbox": "enum:read-only|workspace-write",
    "output_path": "absolute_path",
    "workspace_root": "absolute_attempt_path",
}
TERMINAL_EVENT_TYPES = {
    "attempt-completed",
    "attempt-failed",
    "attempt-rejected",
    "attempt-stale",
}


class ControlPlaneError(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return HASH_PREFIX + hashlib.sha256(payload).hexdigest()


def bytes_hash(value: bytes) -> str:
    return HASH_PREFIX + hashlib.sha256(value).hexdigest()


def atomic_write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".t{os.getpid():x}{time.time_ns() & 0xFFFFFF:x}")
    try:
        with temp.open("xb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_bytes(
        path,
        (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"),
    )


def git_index_hash(repository_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--git-path", "index"],
        cwd=repository_root,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        shell=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise ControlPlaneError("Git index path is not readable")
    index_path = Path(result.stdout.strip())
    if not index_path.is_absolute():
        index_path = repository_root / index_path
    return bytes_hash(index_path.read_bytes() if index_path.is_file() else b"")


def is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return bool(attributes & 0x400)


def reject_reparse_escape(repository_root: Path, source: Path) -> None:
    current = source
    while current != repository_root:
        if is_reparse_point(current):
            raise ControlPlaneError(f"Artifact path contains a reparse point: {source}")
        current = current.parent


def create_artifact_view(
    repository_root: Path,
    run_dir: Path,
    artifacts: list[dict[str, Any]],
    context_classes: dict[str, list[str]],
    authority_revision: str,
    deleted_artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    view_root = run_dir / "artifact-view"
    tree_root = view_root / "tree"
    case_identities: dict[str, str] = {}
    entries: list[dict[str, Any]] = []
    memberships = {
        artifact: sorted(name for name, names in context_classes.items() if artifact in names)
        for artifact in (item["artifact"] for item in artifacts)
    }
    for artifact in artifacts:
        relative = artifact["artifact"]
        case_identity = relative.replace("\\", "/").casefold()
        previous = case_identities.get(case_identity)
        if previous is not None and previous != relative:
            raise ControlPlaneError(f"Windows case-normalized artifact collision: {previous} vs {relative}")
        case_identities[case_identity] = relative
        source = repository_root / relative
        reject_reparse_escape(repository_root, source)
        raw = source.read_bytes()
        if bytes_hash(raw) != artifact["sha256"]:
            raise ControlPlaneError(f"Artifact changed while creating view: {relative}")
        snapshot = tree_root / Path(relative)
        if view_root == snapshot or view_root in snapshot.parents:
            atomic_write_bytes(snapshot, raw)
        else:
            raise ControlPlaneError(f"Artifact snapshot escapes view: {relative}")
        entry = {
            "originalPath": relative,
            "snapshotPath": snapshot.relative_to(run_dir).as_posix(),
            "originalSha256": artifact["sha256"],
            "snapshotSha256": bytes_hash(raw),
            "sizeBytes": len(raw),
            "encoding": artifact.get("textEncoding"),
            "lineCount": artifact.get("lineCount"),
            "fileType": source.suffix.casefold() or "none",
            "contentKind": "text" if artifact.get("textEncoding") else "binary",
            "reparsePoint": False,
            "windowsCaseIdentity": case_identity,
            "contextClasses": memberships[relative],
            "sourceScopes": [
                scope for scope in artifact.get("sourceScopes", []) if isinstance(scope, str)
            ],
        }
        entries.append(entry)
    for artifact in deleted_artifacts or []:
        relative = artifact["artifact"]
        case_identity = relative.replace("\\", "/").casefold()
        previous = case_identities.get(case_identity)
        if previous is not None:
            raise ControlPlaneError(
                f"Deleted artifact collides with a current Artifact View entry: {relative}"
            )
        case_identities[case_identity] = relative
        source = Path(artifact["sourcePath"]).resolve()
        raw = source.read_bytes()
        if bytes_hash(raw) != artifact["sha256"]:
            raise ControlPlaneError(f"Deleted predecessor artifact drifted: {relative}")
        snapshot = view_root / "deleted-tree" / Path(relative)
        if view_root == snapshot or view_root in snapshot.parents:
            atomic_write_bytes(snapshot, raw)
        else:
            raise ControlPlaneError(f"Deleted artifact snapshot escapes view: {relative}")
        entries.append(
            {
                "originalPath": relative,
                "snapshotPath": snapshot.relative_to(run_dir).as_posix(),
                "originalSha256": artifact["sha256"],
                "snapshotSha256": bytes_hash(raw),
                "sizeBytes": len(raw),
                "encoding": artifact.get("textEncoding"),
                "lineCount": artifact.get("lineCount"),
                "fileType": Path(relative).suffix.casefold() or "none",
                "contentKind": "text" if artifact.get("textEncoding") else "binary",
                "reparsePoint": False,
                "windowsCaseIdentity": case_identity,
                "contextClasses": [],
                "sourceScopes": [],
                "sourceState": "deleted",
                "predecessorRun": artifact["predecessorRun"],
            }
        )
    manifest = {
        "schemaVersion": "artifact-view.v1",
        "authorityRevision": authority_revision,
        "createdAt": utc_now(),
        "entries": entries,
    }
    manifest["creationHash"] = canonical_hash(
        {"authorityRevision": authority_revision, "entries": entries}
    )
    atomic_write_json(view_root / "manifest.json", manifest)
    return manifest


def validate_artifact_view(
    run_dir: Path,
    repository_root: Path,
    manifest: dict[str, Any],
    *,
    require_live_originals: bool = True,
) -> str:
    if manifest.get("schemaVersion") != "artifact-view.v1":
        raise ControlPlaneError("Artifact View has an unsupported schemaVersion")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ControlPlaneError("Artifact View contains no entries")
    expected_creation = canonical_hash(
        {"authorityRevision": manifest.get("authorityRevision"), "entries": entries}
    )
    if manifest.get("creationHash") != expected_creation:
        raise ControlPlaneError("Artifact View creationHash is invalid")
    for entry in entries:
        original = repository_root / entry["originalPath"]
        snapshot = run_dir / entry["snapshotPath"]
        if require_live_originals:
            if entry.get("sourceState") == "deleted":
                if original.exists():
                    raise ControlPlaneError(
                        f"Deleted artifact reappeared: {entry['originalPath']}"
                    )
            elif not original.is_file() or bytes_hash(original.read_bytes()) != entry["originalSha256"]:
                raise ControlPlaneError(f"Live artifact drifted: {entry['originalPath']}")
        if not snapshot.is_file() or bytes_hash(snapshot.read_bytes()) != entry["snapshotSha256"]:
            raise ControlPlaneError(f"Artifact View drifted: {entry['snapshotPath']}")
        if entry["originalSha256"] != entry["snapshotSha256"]:
            raise ControlPlaneError(f"Artifact View bytes differ: {entry['originalPath']}")
    return bytes_hash((run_dir / "artifact-view" / "manifest.json").read_bytes())


def _process_creation_identity(pid: int) -> str | None:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    if os.name == "nt":
        process_query_limited_information = 0x1000
        still_active = 259

        class FileTime(ctypes.Structure):
            _fields_ = [("low", ctypes.c_ulong), ("high", ctypes.c_ulong)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel32.GetExitCodeProcess.restype = ctypes.c_int
        kernel32.GetProcessTimes.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(FileTime),
            ctypes.POINTER(FileTime),
            ctypes.POINTER(FileTime),
            ctypes.POINTER(FileTime),
        ]
        kernel32.GetProcessTimes.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return None
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return None
            if exit_code.value != still_active:
                return None
            creation = FileTime()
            exit_time = FileTime()
            kernel = FileTime()
            user = FileTime()
            if not kernel32.GetProcessTimes(
                handle,
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel),
                ctypes.byref(user),
            ):
                return None
            return f"windows-filetime:{(creation.high << 32) | creation.low}"
        finally:
            kernel32.CloseHandle(handle)
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.is_file():
        try:
            stat = proc_stat.read_text(encoding="ascii")
            fields_after_comm = stat[stat.rfind(")") + 2:].split()
            return f"linux-starttime:{fields_after_comm[19]}"
        except (OSError, UnicodeError, IndexError, ValueError):
            return None
    return None


def _event_lock_is_stale(lock: Path) -> bool:
    try:
        age_seconds = time.time() - lock.stat().st_mtime
    except OSError:
        return False
    try:
        owner = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return age_seconds > 1
    pid = owner.get("pid") if isinstance(owner, dict) else None
    identity = owner.get("processIdentity") if isinstance(owner, dict) else None
    if isinstance(owner, dict) and owner.get("phase") == "committed":
        return True
    if not isinstance(pid, int) or not isinstance(identity, str):
        return age_seconds > 1
    return _process_creation_identity(pid) != identity


def _write_event_lock_owner(descriptor: int, owner: dict[str, Any]) -> None:
    payload = json.dumps(
        owner, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    os.lseek(descriptor, 0, os.SEEK_SET)
    os.ftruncate(descriptor, 0)
    os.write(descriptor, payload)
    os.fsync(descriptor)


def append_process_event(run_dir: Path, event: dict[str, Any]) -> None:
    path = run_dir / "process-events.jsonl"
    lock = run_dir / ".process-events.lock"
    deadline = time.monotonic() + 15
    descriptor: int | None = None
    token = secrets.token_hex(16)
    while descriptor is None:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                owner = {
                    "pid": os.getpid(),
                    "processIdentity": _process_creation_identity(os.getpid()),
                    "token": token,
                    "createdAt": utc_now(),
                    "phase": "acquired",
                }
                _write_event_lock_owner(descriptor, owner)
            except Exception:
                os.close(descriptor)
                descriptor = None
                lock.unlink(missing_ok=True)
                raise
        except FileExistsError:
            if _event_lock_is_stale(lock):
                try:
                    lock.unlink()
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise ControlPlaneError("Timed out waiting for process event lock")
            time.sleep(0.05)
    try:
        event = {"schemaVersion": "bootstrap-process-event.v1", **event}
        line = json.dumps(event, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())
        owner["phase"] = "committed"
        _write_event_lock_owner(descriptor, owner)
    finally:
        os.close(descriptor)
        for _attempt in range(40):
            try:
                current_owner = json.loads(lock.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError):
                break
            if current_owner.get("token") != token:
                break
            try:
                lock.unlink(missing_ok=True)
                break
            except PermissionError:
                time.sleep(0.05)


def read_process_events(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "process-events.jsonl"
    if not path.is_file():
        return []
    events = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            value = json.loads(line)
        except ValueError as exc:
            raise ControlPlaneError(f"Invalid process event at line {number}: {exc}") from exc
        if value.get("schemaVersion") != "bootstrap-process-event.v1":
            raise ControlPlaneError(f"Invalid process event schema at line {number}")
        events.append(value)
    return events


def active_attempts(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    active: dict[str, dict[str, Any]] = {}
    for event in events:
        attempt_id = event.get("attemptId")
        if not isinstance(attempt_id, str):
            continue
        if event.get("eventType") in {"attempt-reserved", "attempt-started"}:
            active[attempt_id] = event
        elif event.get("eventType") in TERMINAL_EVENT_TYPES:
            active.pop(attempt_id, None)
    return active


def child_environment() -> tuple[dict[str, str], dict[str, str]]:
    child: dict[str, str] = {}
    evidence: dict[str, str] = {}
    for name in ENVIRONMENT_ALLOWLIST:
        value = os.environ.get(name)
        if value is None:
            continue
        child[name] = value
        evidence[name] = bytes_hash(value.encode("utf-8")) if name.endswith("KEY") else value
    return child, evidence


def render_codex_command(
    codex_command: str,
    model: str,
    reasoning_effort: str,
    sandbox: str,
    output_path: Path,
) -> list[str]:
    if reasoning_effort not in {"medium", "high", "max"}:
        raise ControlPlaneError("reasoning_effort violates its typed placeholder")
    if sandbox not in {"read-only", "workspace-write"}:
        raise ControlPlaneError("sandbox violates its typed placeholder")
    if not model or re.fullmatch(r"[A-Za-z0-9._-]+", model) is None:
        raise ControlPlaneError("model violates its typed placeholder")
    if not Path(codex_command).name:
        raise ControlPlaneError("codex_command violates its typed placeholder")
    if not output_path.is_absolute():
        raise ControlPlaneError("output_path violates its typed placeholder")
    command = [
        codex_command, "exec", "-C", str(output_path.parent), "--skip-git-repo-check",
        "--sandbox", sandbox, "-m", model,
        "-c", f"model_reasoning_effort={reasoning_effort}",
    ]
    command.extend(["--json", "--output-last-message", str(output_path), "-"])
    return command

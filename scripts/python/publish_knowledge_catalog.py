"""Build, evaluate, and atomically publish the repository knowledge generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from _knowledge_catalog_builder import build_layers, canonical_bytes, compatibility_catalog, prefixed_sha256
from _knowledge_locator_core import verify_current_publication
from evaluate_knowledge_queries import evaluate


LAYER_PATHS = {
    "snapshot": Path("knowledge/snapshots/repository-source-snapshot.v1.json"),
    "catalog_v2": Path("knowledge/catalogs/repository-knowledge-catalog.v2.json"),
    "projections": Path("knowledge/projections/consumer-projections.v1.json"),
    "catalog_v1": Path("knowledge/catalogs/repository-knowledge-catalog.v1.json"),
}
INPUT_PATHS = {
    "policy": Path("knowledge/policies/consumer-policies.v2.json"),
    "exclusions": Path("knowledge/policies/source-exclusions.v1.json"),
    "query_suite": Path("knowledge/evaluation/repository-knowledge-query-suite.v1.json"),
}
CONTROL_PATHS = (
    Path("scripts/python/publish_knowledge_catalog.py"),
    Path("scripts/python/_knowledge_catalog_builder.py"),
    Path("scripts/python/evaluate_knowledge_queries.py"),
    Path("scripts/python/knowledge_locator.py"),
    Path("scripts/python/_knowledge_locator_core.py"),
    Path("scripts/python/knowledge_context_validation.py"),
)
SCHEMA_VERSION = "jimuyun.knowledge-publication-generation.v1"
POINTER_SCHEMA_VERSION = "jimuyun.knowledge-index-pointer.v2"
REPORT_SCHEMA_VERSION = "jimuyun.knowledge-publication-report.v1"
PUBLICATION_REQUEST_SCHEMA_VERSION = "jimuyun.knowledge-publication-request.v1"
MALFORMED_LOCK_GRACE_SECONDS = 60
REQUIRED_ARTIFACTS = {*LAYER_PATHS, *INPUT_PATHS, "query_report"}
EXPECTED_BUNDLE_PATHS = {
    **{name: Path("layers") / path.name for name, path in LAYER_PATHS.items()},
    **{name: Path("inputs") / path.name for name, path in INPUT_PATHS.items()},
    "query_report": Path("evaluation/query-report.v1.json"),
}
EXPECTED_REPOSITORY_PATHS = {
    **LAYER_PATHS,
    **INPUT_PATHS,
    "query_report": Path("logs/knowledge-context"),
}


@dataclass(frozen=True)
class _PublicationAuthorization:
    summary: dict[str, Any]


def _render(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _load_json_bytes(payload: bytes, label: str) -> dict[str, Any]:
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label}_schema_invalid")
    return value


def _validate_publication_request(
    request: dict[str, Any],
    *,
    expected_main: str,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    required = {
        "schema_version", "request_id", "caller", "trigger", "target_plan", "main_commit",
        "automatic", "maintainer_confirmation", "recorded_at", "authorizes", "source_route",
    }
    if set(request) != required or request.get("schema_version") != PUBLICATION_REQUEST_SCHEMA_VERSION:
        raise ValueError("knowledge_publication_request_schema_invalid")
    if not isinstance(request.get("request_id"), str) or not request["request_id"]:
        raise ValueError("knowledge_publication_request_schema_invalid")
    if request.get("caller") != "maintain-knowledge-base":
        raise ValueError("knowledge_publication_request_caller_invalid")
    if request.get("trigger") not in {"operator-requested", "catalog-stale-maintenance"}:
        raise ValueError("knowledge_publication_request_trigger_invalid")
    target = request.get("target_plan")
    target_name = target.removeprefix("execution-plans/") if isinstance(target, str) else ""
    if (
        not isinstance(target, str)
        or "\\" in target
        or target.count("/") != 1
        or not target.startswith("execution-plans/")
        or not target_name
        or target_name in {".", ".."}
    ):
        raise ValueError("knowledge_publication_request_target_invalid")
    if request.get("main_commit") != expected_main:
        raise ValueError("knowledge_publication_request_main_mismatch")
    if request.get("automatic") is not False or request.get("maintainer_confirmation") is not True:
        raise ValueError("knowledge_publication_request_confirmation_required")
    if request.get("authorizes") != ["knowledge-publication"]:
        raise ValueError("knowledge_publication_request_authority_invalid")
    source_route = request.get("source_route")
    if request["trigger"] == "catalog-stale-maintenance":
        route_path = source_route.get("path") if isinstance(source_route, dict) else None
        expected_prefix = f"{target}/knowledge-context-routes/"
        if (
            not isinstance(source_route, dict)
            or set(source_route) != {"path", "sha256"}
            or not isinstance(route_path, str)
            or not route_path.startswith(expected_prefix)
            or len(Path(route_path).stem) != 64
            or Path(route_path).suffix != ".json"
            or any(character not in "0123456789abcdef" for character in Path(route_path).stem)
            or not _is_sha256(source_route.get("sha256"))
        ):
            raise ValueError("knowledge_publication_request_route_invalid")
    elif source_route is not None:
        raise ValueError("knowledge_publication_request_route_invalid")
    recorded_at = request.get("recorded_at")
    if not isinstance(recorded_at, str):
        raise ValueError("knowledge_publication_request_recorded_at_invalid")
    try:
        parsed = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("knowledge_publication_request_recorded_at_invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("knowledge_publication_request_recorded_at_invalid")
    if repository_root is not None:
        try:
            _main_blob(repository_root, expected_main, Path(target) / "00-index.md")
        except ValueError as exc:
            raise ValueError("knowledge_publication_request_target_invalid") from exc
        if source_route is not None:
            _validate_source_route(repository_root, target, source_route)
    return {
        "request_id": request["request_id"],
        "caller": request["caller"],
        "trigger": request["trigger"],
        "target_plan": target,
        "request_sha256": _sha(_render(request)),
        "source_route": source_route,
    }


def _validate_source_route(repository_root: Path, target_plan: str, summary: dict[str, str]) -> None:
    raw = Path(summary["path"])
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError("knowledge_publication_request_route_invalid")
    route_path = (repository_root / raw).resolve()
    allowed = (repository_root / target_plan / "knowledge-context-routes").resolve()
    try:
        route_path.relative_to(allowed)
        route = _load_json_bytes(route_path.read_bytes(), "publication_route")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("knowledge_publication_request_route_invalid") from exc
    route_without_hash = {key: value for key, value in route.items() if key != "route_sha256"}
    expected = {
        "schema_version": "jimuyun.acceptance-knowledge-maintenance-route.v1",
        "status": "blocked",
        "failure_code": "catalog_stale",
        "next_action": "knowledge-maintenance-required",
        "target_plan": target_plan,
        "automatic_publication_allowed": False,
        "requires_explicit_maintainer_confirmation": True,
        "authorizes": [],
        "route_output": raw.as_posix(),
    }
    route_hash = prefixed_sha256(canonical_bytes(route_without_hash))
    if (
        any(route.get(key) != value for key, value in expected.items())
        or route.get("route_sha256") != route_hash
        or summary["sha256"] != route_hash
    ):
        raise ValueError("knowledge_publication_request_route_invalid")


def _load_publication_request(repository_root: Path, raw: Path, *, expected_main: str) -> _PublicationAuthorization:
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError("knowledge_publication_request_path_invalid")
    path = (repository_root / raw).resolve()
    allowed = (repository_root / "logs" / "knowledge-context" / "publication-requests").resolve()
    try:
        path.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("knowledge_publication_request_path_invalid") from exc
    if not path.is_file():
        raise ValueError("knowledge_publication_request_unavailable")
    request = _load_json_bytes(path.read_bytes(), "publication_request")
    return _PublicationAuthorization(
        _validate_publication_request(request, expected_main=expected_main, repository_root=repository_root)
    )


def _git(repository_root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(repository_root), *arguments], capture_output=True, check=False)


def _main_commit(repository_root: Path) -> str:
    completed = _git(repository_root, "rev-parse", "refs/heads/main")
    value = completed.stdout.decode("ascii", errors="replace").strip()
    if completed.returncode or len(value) != 40:
        raise ValueError("main_commit_unavailable")
    return value


def _main_blob(repository_root: Path, commit: str, relative_path: Path) -> bytes:
    completed = _git(repository_root, "show", f"{commit}:{relative_path.as_posix()}")
    if completed.returncode:
        raise ValueError(f"main_input_unavailable:{relative_path.as_posix()}")
    return completed.stdout


def _require_main_controls(repository_root: Path, commit: str) -> None:
    for relative_path in CONTROL_PATHS:
        main_bytes = _main_blob(repository_root, commit, relative_path)
        formal_path = repository_root / relative_path
        if not formal_path.is_file() or formal_path.read_bytes() != main_bytes:
            raise ValueError(f"dirty_or_stale_publication_control:{relative_path.as_posix()}")


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _pid_alive(pid: object) -> bool | None:
    if not isinstance(pid, int) or pid <= 0:
        return None
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel32.GetExitCodeProcess.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error == 87:  # ERROR_INVALID_PARAMETER: no such PID
                return False
            if error == 5:  # Access denied still proves that the PID exists.
                return True
            return None
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return None
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as error:
        if getattr(error, "winerror", None) == 87:
            return False
        return None
    return True


def _process_identity(pid: object) -> str | None:
    if not isinstance(pid, int) or pid <= 0:
        return None
    if os.name == "nt":
        import ctypes

        class FileTime(ctypes.Structure):
            _fields_ = [("low", ctypes.c_ulong), ("high", ctypes.c_ulong)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel32.OpenProcess.restype = ctypes.c_void_p
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
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
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
    try:
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="ascii").split()
    except (OSError, UnicodeError):
        return None
    return f"proc-start:{fields[21]}" if len(fields) > 21 else None


def _lock_owner_alive(lock: dict[str, Any]) -> bool | None:
    alive = _pid_alive(lock.get("pid"))
    if alive is not True:
        return alive
    recorded = lock.get("process_identity")
    if recorded is None:
        return True
    current = _process_identity(lock.get("pid"))
    if current is None:
        return None
    return current == recorded


@contextmanager
def _acquisition_guard(index_root: Path) -> Iterator[None]:
    path = index_root / ".publication-acquire.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR)
    try:
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"\0")
            os.fsync(descriptor)
        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _recover_stale_lock(index_root: Path, lock_path: Path) -> bool:
    payload: bytes
    lock: dict[str, Any]
    try:
        payload = lock_path.read_bytes()
        lock = _load_json_bytes(payload, "publication_lock")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        try:
            age = time.time() - lock_path.stat().st_mtime
        except OSError:
            return False
        if age < MALFORMED_LOCK_GRACE_SECONDS:
            return False
        payload = lock_path.read_bytes()
        lock = {"malformed": True}
    if not lock.get("malformed") and _lock_owner_alive(lock) is not False:
        return False
    if lock_path.read_bytes() != payload:
        return False
    repository_root = index_root.parents[1]
    now = datetime.now(timezone.utc)
    evidence = repository_root / "logs" / "knowledge-context" / now.date().isoformat() / "stale-locks" / f"{now.strftime('%H%M%S%f')}-{uuid.uuid4().hex}.json"
    quarantine = index_root / f".publication-lock-stale-{uuid.uuid4().hex}"
    try:
        if lock_path.read_bytes() != payload:
            return False
        os.replace(lock_path, quarantine)
    except OSError:
        return False
    try:
        _atomic_bytes(evidence, _render({
            "schema_version": "jimuyun.knowledge-publication-stale-lock.v1",
            "status": "recovered",
            "recorded_at": now.isoformat(),
            "lock_sha256": _sha(payload),
            "lock": lock,
        }))
        quarantine.unlink()
    except OSError:
        if not lock_path.exists() and quarantine.exists():
            os.replace(quarantine, lock_path)
        return False
    return True


@contextmanager
def _single_writer(index_root: Path) -> Iterator[None]:
    index_root.mkdir(parents=True, exist_ok=True)
    lock_path = index_root / "publication.lock"
    token = uuid.uuid4().hex
    descriptor: int | None = None
    try:
        with _acquisition_guard(index_root):
            for attempt in range(2):
                try:
                    descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    break
                except FileExistsError as exc:
                    if attempt or not _recover_stale_lock(index_root, lock_path):
                        raise ValueError("knowledge_publication_lock_conflict") from exc
    except OSError as exc:
        raise ValueError("knowledge_publication_lock_conflict") from exc
    assert descriptor is not None
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({
                "pid": os.getpid(),
                "process_identity": _process_identity(os.getpid()),
                "token": token,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        yield
    finally:
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            if lock.get("token") == token:
                lock_path.unlink()
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass


def _validate_layers(
    snapshot: dict[str, Any],
    catalog: dict[str, Any],
    projections: dict[str, Any],
    legacy: dict[str, Any],
    policies: dict[str, Any],
    exclusions: dict[str, Any],
) -> None:
    if snapshot.get("schema_version") != "jimuyun.repository-source-snapshot.v1":
        raise ValueError("snapshot_schema_invalid")
    identity = {key: snapshot.get(key) for key in ("ref", "commit", "exclusion_policy_revision", "sources")}
    if snapshot.get("snapshot_id") != prefixed_sha256(canonical_bytes(identity)):
        raise ValueError("snapshot_hash_invalid")
    sources = snapshot.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("snapshot_schema_invalid")
    source_hashes: dict[str, str] = {}
    for item in sources:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "source_role"}:
            raise ValueError("snapshot_schema_invalid")
        path, digest = item.get("path"), item.get("sha256")
        if not isinstance(path, str) or not isinstance(digest, str) or path.startswith("docs/migration/"):
            raise ValueError("snapshot_contamination_detected")
        source_hashes[path] = digest
    if (
        catalog.get("schema_version") != "jimuyun.repository-knowledge-catalog.v2"
        or catalog.get("authority_class") != "derived_cache"
        or catalog.get("instruction_authority") is not False
        or catalog.get("may_override_source") is not False
        or catalog.get("source_snapshot") != snapshot
    ):
        raise ValueError("catalog_schema_invalid")
    modules = catalog.get("modules")
    if not isinstance(modules, list) or not modules:
        raise ValueError("catalog_schema_invalid")
    for module in modules:
        if not isinstance(module, dict):
            raise ValueError("catalog_schema_invalid")
        path = module.get("source_path")
        if (
            not isinstance(path, str)
            or path.startswith("docs/migration/")
            or source_hashes.get(path) != module.get("source_sha256")
            or module.get("lifecycle") != "repository-source"
            or module.get("enforcement_level") != "E1"
        ):
            raise ValueError("catalog_composition_invalid")
        for resource in module.get("resources", []):
            resource_path = resource.get("path") if isinstance(resource, dict) else None
            if not isinstance(resource_path, str) or source_hashes.get(resource_path) != resource.get("source_sha256"):
                raise ValueError("catalog_resource_hash_invalid")
    if (
        projections.get("schema_version") != "jimuyun.knowledge-consumer-projections.v1"
        or projections.get("source_snapshot_id") != snapshot.get("snapshot_id")
        or projections.get("catalog_sha256") != prefixed_sha256(canonical_bytes(catalog))
        or projections.get("policy_revision") != policies.get("policy_revision")
        or projections.get("policy_sha256") != prefixed_sha256(canonical_bytes(policies))
    ):
        raise ValueError("projection_binding_invalid")
    projection_values = {
        item.get("consumer"): item
        for item in projections.get("projections", [])
        if isinstance(item, dict)
    }
    if set(projection_values) != {"vdd", "quick-dev", "bootstrap", "refactor-acceptance"}:
        raise ValueError("projection_schema_invalid")
    if projection_values["quick-dev"].get("eligible_module_ids") != []:
        raise ValueError("quick_dev_projection_must_be_empty")
    if legacy != compatibility_catalog(catalog):
        raise ValueError("compatibility_catalog_invalid")
    if exclusions.get("policy_revision") != snapshot.get("exclusion_policy_revision"):
        raise ValueError("exclusion_policy_binding_invalid")


def _validate_evaluation(report: dict[str, Any], suite: dict[str, Any]) -> None:
    cases = suite.get("cases")
    results = report.get("results")
    summary = report.get("summary")
    if (
        report.get("schema_version") != "jimuyun.repository-knowledge-query-report.v1"
        or not isinstance(cases, list)
        or not isinstance(results, list)
        or not isinstance(summary, dict)
        or summary.get("status") != "passed"
        or summary.get("total") != len(cases)
        or summary.get("passed") != len(cases)
        or summary.get("failed") != 0
        or summary.get("protocol_total") != 4
        or summary.get("protocol_passed") != 4
    ):
        raise ValueError("query_evaluation_gate_failed")
    for category in ("adr", "execution-plan", "architecture", "toolchain"):
        value = report.get("categories", {}).get(category, {})
        if value.get("matched_cases", 0) < 25 or value.get("failed") != 0:
            raise ValueError(f"query_category_gate_failed:{category}")
    for result in results:
        if result.get("status") != "passed" or result.get("candidate_count") != len(result.get("consumption_decisions", [])):
            raise ValueError("adapter_consumption_decision_gate_failed")
        if result.get("expected_result_status") == "matched":
            accepted = [item for item in result["consumption_decisions"] if item.get("decision") == "accepted"]
            if len(accepted) != 1:
                raise ValueError("adapter_consumption_decision_gate_failed")


def _artifact(repository_path: Path, bundle_path: Path, payload: bytes) -> dict[str, str]:
    return {
        "repository_path": repository_path.as_posix(),
        "bundle_path": bundle_path.as_posix(),
        "sha256": _sha(payload),
    }


def _load_pointer(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    payload = path.read_bytes()
    pointer = _load_json_bytes(payload, label)
    generation_id = pointer.get("generation_id")
    if (
        pointer.get("schema_version") != POINTER_SCHEMA_VERSION
        or not isinstance(generation_id, str)
        or len(generation_id) != 64
        or any(character not in "0123456789abcdef" for character in generation_id)
        or not _is_sha256(pointer.get("generation_sha256"))
        or not isinstance(pointer.get("main_commit"), str)
        or len(pointer["main_commit"]) != 40
        or any(character not in "0123456789abcdef" for character in pointer["main_commit"])
        or not _is_sha256(pointer.get("source_snapshot_id"))
    ):
        raise ValueError(f"{label}_schema_invalid")
    return pointer, payload


def _generation_payloads(
    repository_root: Path,
    pointer: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, bytes]]:
    generation_id = pointer["generation_id"]
    generation_root = (repository_root / "knowledge" / "indexes" / "generations" / generation_id).resolve()
    expected_root = (repository_root / "knowledge" / "indexes" / "generations").resolve()
    generation_root.relative_to(expected_root)
    manifest_path = generation_root / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    if pointer["generation_sha256"] != _sha(manifest_bytes):
        raise ValueError("lkg_manifest_hash_invalid")
    manifest = _load_json_bytes(manifest_bytes, "lkg_manifest")
    body = {key: value for key, value in manifest.items() if key != "generation_id"}
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("generation_id") != generation_id
        or hashlib.sha256(canonical_bytes(body)).hexdigest() != generation_id
        or manifest.get("main_commit") != pointer.get("main_commit")
        or manifest.get("source_snapshot_id") != pointer.get("source_snapshot_id")
    ):
        raise ValueError("lkg_manifest_invalid")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != REQUIRED_ARTIFACTS:
        raise ValueError("lkg_artifact_set_invalid")
    payloads: dict[str, bytes] = {}
    for name, artifact in artifacts.items():
        if not isinstance(artifact, dict):
            raise ValueError(f"lkg_artifact_invalid:{name}")
        bundle_path = artifact.get("bundle_path")
        repository_path = artifact.get("repository_path")
        if (
            not isinstance(bundle_path, str)
            or bundle_path != EXPECTED_BUNDLE_PATHS[name].as_posix()
            or repository_path != EXPECTED_REPOSITORY_PATHS[name].as_posix()
        ):
            raise ValueError(f"lkg_artifact_invalid:{name}")
        artifact_path = (generation_root / bundle_path).resolve()
        artifact_path.relative_to(generation_root)
        payload = artifact_path.read_bytes()
        if artifact.get("sha256") != _sha(payload):
            raise ValueError(f"lkg_artifact_hash_invalid:{name}")
        payloads[name] = payload
    return manifest, payloads


def _validate_generation_payloads(
    manifest: dict[str, Any],
    payloads: dict[str, bytes],
) -> tuple[dict[str, Any], dict[str, Any]]:
    layers = {name: _load_json_bytes(payloads[name], name) for name in LAYER_PATHS}
    inputs = {name: _load_json_bytes(payloads[name], name) for name in INPUT_PATHS}
    report = _load_json_bytes(payloads["query_report"], "query_report")
    _validate_layers(
        layers["snapshot"],
        layers["catalog_v2"],
        layers["projections"],
        layers["catalog_v1"],
        inputs["policy"],
        inputs["exclusions"],
    )
    _validate_evaluation(report, inputs["query_suite"])
    if (
        layers["snapshot"].get("commit") != manifest.get("main_commit")
        or layers["snapshot"].get("snapshot_id") != manifest.get("source_snapshot_id")
        or inputs["policy"].get("policy_revision") != manifest.get("policy_revision")
        or report.get("summary") != manifest.get("evaluation_summary")
    ):
        raise ValueError("lkg_snapshot_binding_invalid")
    return layers, inputs


def _require_generation_compatible_with_main(
    repository_root: Path,
    *,
    generation_main: str,
    current_main: str,
    snapshot: dict[str, Any],
    payloads: dict[str, bytes],
) -> None:
    ancestry = _git(repository_root, "merge-base", "--is-ancestor", generation_main, current_main)
    if ancestry.returncode:
        raise ValueError("lkg_main_commit_stale")
    for item in snapshot.get("sources", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("lkg_snapshot_binding_invalid")
        blob = _main_blob(repository_root, current_main, Path(item["path"]))
        if hashlib.sha256(blob).hexdigest() != item.get("sha256"):
            raise ValueError(f"lkg_source_drift:{item['path']}")
    for name, path in INPUT_PATHS.items():
        if _main_blob(repository_root, current_main, path) != payloads[name]:
            raise ValueError(f"lkg_input_drift:{path.as_posix()}")
    _require_main_controls(repository_root, current_main)


def _locator_smoke(repository_root: Path, snapshot: dict[str, Any], policy_revision: str) -> None:
    # ADR-0050 keeps the restored generation's source snapshot as Locator
    # provenance after a publication-only commit advances main.
    request = {
        "schema_version": "jimuyun.knowledge-locator-request.v1",
        "request_id": "knowledge-lkg-restore-smoke",
        "consumer": "vdd",
        "query": "repository knowledge authority",
        "snapshot": {"ref": snapshot["ref"], "commit": snapshot["commit"]},
        "policy_revision": policy_revision,
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(repository_root / "scripts" / "python" / "knowledge_locator.py"),
            "--repository-root",
            str(repository_root),
        ],
        cwd=repository_root,
        input=json.dumps(request, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        capture_output=True,
        check=False,
    )
    try:
        result = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("lkg_locator_smoke_invalid_json") from error
    candidates = result.get("candidates")
    if (
        completed.returncode != 0
        or result.get("schema_version") != "jimuyun.knowledge-locator-result.v1"
        or result.get("request_id") != request["request_id"]
        or result.get("snapshot") != request["snapshot"]
        or result.get("source_snapshot_id") != snapshot.get("snapshot_id")
        or result.get("policy_revision") != policy_revision
        or result.get("status") != "matched"
        or not isinstance(candidates, list)
        or not candidates
        or any(
            not isinstance(candidate, dict)
            or not isinstance(candidate.get("path"), str)
            or not _is_sha256("sha256:" + str(candidate.get("source_sha256", "")))
            for candidate in candidates
        )
    ):
        raise ValueError("lkg_locator_smoke_failed")


def _restore_bytes(path: Path, payload: bytes | None) -> None:
    if payload is None:
        if path.exists():
            path.unlink()
    else:
        _atomic_bytes(path, payload)


def _rollback_and_verify(backups: dict[Path, bytes | None]) -> None:
    errors: list[str] = []
    for path, payload in backups.items():
        try:
            _restore_bytes(path, payload)
        except Exception as error:  # every target must still be attempted
            errors.append(f"restore:{path.as_posix()}:{error}")
    for path, payload in backups.items():
        try:
            current = path.read_bytes() if path.is_file() else None
            if current != payload:
                errors.append(f"verify:{path.as_posix()}")
        except Exception as error:
            errors.append(f"verify:{path.as_posix()}:{error}")
    if errors:
        raise RuntimeError("activation_rollback_failed:" + "|".join(errors))


def _activate_lkg(
    repository_root: Path,
    *,
    pointer: dict[str, Any],
    pointer_bytes: bytes,
    manifest: dict[str, Any],
    payloads: dict[str, bytes],
    layers: dict[str, Any],
    inputs: dict[str, Any],
    repeat: int,
    expected_main: str,
    evidence_path: Path | None = None,
) -> dict[str, Any]:
    index_root = repository_root / "knowledge" / "indexes"
    targets = [repository_root / path for path in LAYER_PATHS.values()]
    current_pointer_path = index_root / "current.json"
    backups = {
        target: target.read_bytes() if target.is_file() else None
        for target in [*targets, *([evidence_path] if evidence_path is not None else []), current_pointer_path]
    }
    try:
        if _main_commit(repository_root) != expected_main:
            raise ValueError("main_advanced_during_lkg_restore")
        for name, path in LAYER_PATHS.items():
            _atomic_bytes(repository_root / path, payloads[name])
        _atomic_bytes(current_pointer_path, pointer_bytes)
        if not verify_current_publication(
            repository_root,
            catalog_path=repository_root / LAYER_PATHS["catalog_v2"],
            policy_path=repository_root / INPUT_PATHS["policy"],
            projections_path=repository_root / LAYER_PATHS["projections"],
        ):
            raise ValueError("restored_publication_verification_failed")
        report = evaluate(
            repository_root,
            repository_root / INPUT_PATHS["query_suite"],
            repository_root / LAYER_PATHS["catalog_v2"],
            repository_root / INPUT_PATHS["policy"],
            repository_root / LAYER_PATHS["projections"],
            repeat,
            allow_ancestor_snapshot=True,
        )
        _validate_evaluation(report, inputs["query_suite"])
        _locator_smoke(repository_root, layers["snapshot"], manifest["policy_revision"])
        if _main_commit(repository_root) != expected_main:
            raise ValueError("main_advanced_during_lkg_restore")
        if evidence_path is not None:
            _atomic_bytes(evidence_path, _render(report))
        return report
    except Exception as error:
        try:
            _rollback_and_verify(backups)
        except Exception as rollback_error:
            raise RuntimeError(f"{error}; {rollback_error}") from error
        raise


def restore_last_known_good(repository_root: Path, *, repeat: int) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    index_root = repository_root / "knowledge" / "indexes"
    phase = "restore-lock"
    pinned_main: str | None = None
    report: dict[str, Any] | None = None
    try:
        with _single_writer(index_root):
            phase = "restore-load-lkg"
            pinned_main = _main_commit(repository_root)
            pointer, pointer_bytes = _load_pointer(index_root / "last-known-good.json", "lkg_pointer")
            manifest, payloads = _generation_payloads(repository_root, pointer)
            layers, inputs = _validate_generation_payloads(manifest, payloads)
            _require_generation_compatible_with_main(
                repository_root,
                generation_main=pointer["main_commit"],
                current_main=pinned_main,
                snapshot=layers["snapshot"],
                payloads=payloads,
            )
            for name, path in INPUT_PATHS.items():
                formal_path = repository_root / path
                if not formal_path.is_file() or formal_path.read_bytes() != payloads[name]:
                    raise ValueError(f"lkg_input_drift:{path.as_posix()}")
            phase = "restore-four-layers"
            evidence = (
                repository_root
                / "logs"
                / "knowledge-context"
                / datetime.now(timezone.utc).date().isoformat()
                / "restores"
                / pointer["generation_id"]
                / f"{uuid.uuid4().hex}.query-report.v1.json"
            )
            report = _activate_lkg(
                repository_root,
                pointer=pointer,
                pointer_bytes=pointer_bytes,
                manifest=manifest,
                payloads=payloads,
                layers=layers,
                inputs=inputs,
                repeat=repeat,
                expected_main=pinned_main,
                evidence_path=evidence,
            )
            phase = "restore-verify-locator-suite"
            return {
                "status": "restored",
                "main_commit": pinned_main,
                "snapshot_id": pointer["source_snapshot_id"],
                "generation_id": pointer["generation_id"],
                "generation_sha256": pointer["generation_sha256"],
                "evaluation": report["summary"],
                "evidence": evidence.relative_to(repository_root).as_posix(),
            }
    except (OSError, UnicodeError, ValueError, RuntimeError, KeyError, TypeError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        evidence = _write_failure(
            repository_root,
            phase=phase,
            error=str(error),
            main_commit=pinned_main,
            evaluation_report=report,
        )
        return {"status": "blocked", "phase": phase, "error": str(error), "evidence": evidence.as_posix()}


def _write_failure(
    repository_root: Path,
    *,
    phase: str,
    error: str,
    main_commit: str | None,
    evaluation_report: dict[str, Any] | None = None,
    publication_request: dict[str, Any] | None = None,
) -> Path:
    now = datetime.now(timezone.utc)
    relative = Path("logs/knowledge-context") / now.date().isoformat() / "publication-failures" / f"{now.strftime('%H%M%S%f')}-{uuid.uuid4().hex}.json"
    report_path: Path | None = None
    report_hash: str | None = None
    if evaluation_report is not None:
        report_path = relative.with_name(relative.stem + ".query-report.json")
        report_bytes = _render(evaluation_report)
        report_hash = _sha(report_bytes)
        _atomic_bytes(repository_root / report_path, report_bytes)
    payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "failed",
        "phase": phase,
        "error": error,
        "main_commit": main_commit,
        "recorded_at": now.isoformat(),
        "evaluation_report_path": report_path.as_posix() if report_path is not None else None,
        "evaluation_report_sha256": report_hash,
        "publication_request": publication_request,
    }
    _atomic_bytes(repository_root / relative, _render(payload))
    return relative


def _publish_bundle(
    repository_root: Path,
    *,
    main_commit: str,
    layer_bytes: dict[str, bytes],
    input_bytes: dict[str, bytes],
    report_bytes: bytes,
    report: dict[str, Any],
    publication_authorization: _PublicationAuthorization | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(publication_authorization, _PublicationAuthorization):
        raise ValueError("knowledge_publication_request_required")
    publication_request = publication_authorization.summary
    index_root = repository_root / "knowledge" / "indexes"
    artifacts: dict[str, dict[str, str]] = {}
    bundle_payloads: dict[Path, bytes] = {}
    for name, payload in layer_bytes.items():
        bundle_path = Path("layers") / LAYER_PATHS[name].name
        artifacts[name] = _artifact(LAYER_PATHS[name], bundle_path, payload)
        bundle_payloads[bundle_path] = payload
    for name, payload in input_bytes.items():
        bundle_path = Path("inputs") / INPUT_PATHS[name].name
        artifacts[name] = _artifact(INPUT_PATHS[name], bundle_path, payload)
        bundle_payloads[bundle_path] = payload
    report_bundle_path = Path("evaluation/query-report.v1.json")
    artifacts["query_report"] = _artifact(Path("logs/knowledge-context"), report_bundle_path, report_bytes)
    bundle_payloads[report_bundle_path] = report_bytes
    body = {
        "schema_version": SCHEMA_VERSION,
        "main_commit": main_commit,
        "source_snapshot_id": report["snapshot"]["snapshot_id"],
        "policy_revision": report["policy_revision"],
        "artifacts": artifacts,
        "evaluation_summary": report["summary"],
    }
    if publication_request is not None:
        body["publication_request"] = publication_request
    generation_id = hashlib.sha256(canonical_bytes(body)).hexdigest()
    manifest = {**body, "generation_id": generation_id}
    generation_root = index_root / "generations" / generation_id
    manifest_bytes = _render(manifest)
    if generation_root.exists():
        if (generation_root / "manifest.json").read_bytes() != manifest_bytes:
            raise ValueError("generation_identity_conflict")
        for path, payload in bundle_payloads.items():
            if (generation_root / path).read_bytes() != payload:
                raise ValueError("generation_identity_conflict")
    else:
        generation_root.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{generation_id}.", dir=generation_root.parent))
        try:
            for path, payload in bundle_payloads.items():
                target = temporary / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
            (temporary / "manifest.json").write_bytes(manifest_bytes)
            os.replace(temporary, generation_root)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    pointer = {
        "schema_version": POINTER_SCHEMA_VERSION,
        "generation_id": generation_id,
        "generation_sha256": _sha(manifest_bytes),
        "main_commit": main_commit,
        "source_snapshot_id": report["snapshot"]["snapshot_id"],
    }
    success_path = repository_root / "logs" / "knowledge-context" / datetime.now(timezone.utc).date().isoformat() / "publications" / generation_id / "query-report.v1.json"
    current_path = index_root / "current.json"
    lkg_path = index_root / "last-known-good.json"
    targets = [*(repository_root / path for path in LAYER_PATHS.values()), lkg_path, success_path, current_path]
    backups = {path: path.read_bytes() if path.is_file() else None for path in targets}
    try:
        if _main_commit(repository_root) != main_commit:
            raise ValueError("main_advanced_during_publication")
        for name, payload in layer_bytes.items():
            _atomic_bytes(repository_root / LAYER_PATHS[name], payload)
        pointer_bytes = _render(pointer)
        _atomic_bytes(lkg_path, pointer_bytes)
        if success_path.is_file() and success_path.read_bytes() != report_bytes:
            raise ValueError("publication_success_evidence_conflict")
        if not success_path.is_file():
            _atomic_bytes(success_path, report_bytes)
        _atomic_bytes(current_path, pointer_bytes)
        if not verify_current_publication(
            repository_root,
            catalog_path=repository_root / LAYER_PATHS["catalog_v2"],
            policy_path=repository_root / INPUT_PATHS["policy"],
            projections_path=repository_root / LAYER_PATHS["projections"],
        ):
            raise ValueError("published_publication_verification_failed")
        _locator_smoke(repository_root, _load_json_bytes(layer_bytes["snapshot"], "snapshot"), report["policy_revision"])
        if _main_commit(repository_root) != main_commit:
            raise ValueError("main_advanced_during_publication")
    except Exception as error:
        try:
            _rollback_and_verify(backups)
        except Exception as rollback_error:
            raise RuntimeError(f"{error}; {rollback_error}") from error
        raise
    return manifest, pointer


def run(repository_root: Path, *, publish: bool, repeat: int, publication_request: Path | None = None) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    index_root = repository_root / "knowledge" / "indexes"
    phase = "lock"
    pinned_main: str | None = None
    report: dict[str, Any] | None = None
    request_summary: dict[str, Any] | None = None
    request_authorization: _PublicationAuthorization | None = None
    try:
        if publish and publication_request is None:
            phase = "authorize-publication"
            raise ValueError("knowledge_publication_request_required")
        with _single_writer(index_root):
            phase = "pin-main"
            pinned_main = _main_commit(repository_root)
            if publish:
                phase = "authorize-publication"
                request_authorization = _load_publication_request(repository_root, publication_request, expected_main=pinned_main)
                request_summary = request_authorization.summary
            phase = "bind-publication-controls"
            _require_main_controls(repository_root, pinned_main)
            phase = "load-main-inputs"
            input_bytes = {name: _main_blob(repository_root, pinned_main, path) for name, path in INPUT_PATHS.items()}
            inputs = {name: _load_json_bytes(payload, name) for name, payload in input_bytes.items()}
            for name, payload in input_bytes.items():
                formal_path = repository_root / INPUT_PATHS[name]
                if not formal_path.is_file() or formal_path.read_bytes() != payload:
                    raise ValueError(f"dirty_or_stale_publication_input:{INPUT_PATHS[name].as_posix()}")
            phase = "build-staging"
            snapshot, catalog, projections, legacy = build_layers(
                repository_root,
                policy=inputs["policy"],
                exclusions=inputs["exclusions"],
                authority_ref="refs/heads/main",
            )
            layer_values = {
                "snapshot": snapshot,
                "catalog_v2": catalog,
                "projections": projections,
                "catalog_v1": legacy,
            }
            _validate_layers(snapshot, catalog, projections, legacy, inputs["policy"], inputs["exclusions"])
            layer_bytes = {name: _render(value) for name, value in layer_values.items()}
            with tempfile.TemporaryDirectory(prefix=".publication-", dir=index_root) as staging_name:
                staging = Path(staging_name)
                staged_paths: dict[str, Path] = {}
                for name, payload in {**layer_bytes, **input_bytes}.items():
                    target = staging / f"{name}.json"
                    target.write_bytes(payload)
                    staged_paths[name] = target
                phase = "evaluate-staging"
                report = evaluate(
                    repository_root,
                    staged_paths["query_suite"],
                    staged_paths["catalog_v2"],
                    staged_paths["policy"],
                    staged_paths["projections"],
                    repeat,
                )
                _validate_evaluation(report, inputs["query_suite"])
                report_bytes = _render(report)
            phase = "repin-main"
            if _main_commit(repository_root) != pinned_main:
                raise ValueError("main_advanced_during_publication")
            if not publish:
                return {
                    "status": "publishable",
                    "main_commit": pinned_main,
                    "snapshot_id": snapshot["snapshot_id"],
                    "evaluation": report["summary"],
                }
            phase = "publish"
            manifest, pointer = _publish_bundle(
                repository_root,
                main_commit=pinned_main,
                layer_bytes=layer_bytes,
                input_bytes=input_bytes,
                report_bytes=report_bytes,
                report=report,
                publication_authorization=request_authorization,
            )
            return {
                "status": "published",
                "main_commit": pinned_main,
                "snapshot_id": snapshot["snapshot_id"],
                "generation_id": manifest["generation_id"],
                "generation_sha256": pointer["generation_sha256"],
                "evaluation": report["summary"],
            }
    except (OSError, UnicodeError, ValueError, RuntimeError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        evidence = _write_failure(
            repository_root,
            phase=phase,
            error=str(error),
            main_commit=pinned_main,
            evaluation_report=report,
            publication_request=request_summary,
        )
        return {"status": "blocked", "phase": phase, "error": str(error), "evidence": evidence.as_posix()}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Build and evaluate staging without publication (default).")
    mode.add_argument("--publish", action="store_true", help="Publish a validated immutable generation.")
    mode.add_argument("--restore-lkg", action="store_true", help="Restore the four formal layers from the immutable last-known-good generation.")
    parser.add_argument("--publication-request", type=Path, help="Repository-relative maintainer authorization under logs/knowledge-context/publication-requests/ (required with --publish).")
    parser.add_argument("--repeat", type=int, default=2)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    if args.publication_request is not None and not args.publish:
        parser.error("--publication-request is valid only with --publish")
    result = (
        restore_last_known_good(args.repository_root, repeat=args.repeat)
        if args.restore_lkg
        else run(args.repository_root, publish=args.publish, repeat=args.repeat, publication_request=args.publication_request)
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] in {"publishable", "published", "restored"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

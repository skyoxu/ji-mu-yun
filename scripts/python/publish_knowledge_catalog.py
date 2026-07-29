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
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from _knowledge_catalog_builder import build_layers, canonical_bytes, compatibility_catalog, prefixed_sha256
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
SCHEMA_VERSION = "jimuyun.knowledge-publication-generation.v1"
POINTER_SCHEMA_VERSION = "jimuyun.knowledge-index-pointer.v2"
REPORT_SCHEMA_VERSION = "jimuyun.knowledge-publication-report.v1"


def _render(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _load_json_bytes(payload: bytes, label: str) -> dict[str, Any]:
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label}_schema_invalid")
    return value


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


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


@contextmanager
def _single_writer(index_root: Path) -> Iterator[None]:
    index_root.mkdir(parents=True, exist_ok=True)
    lock_path = index_root / "publication.lock"
    token = uuid.uuid4().hex
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError("knowledge_publication_lock_conflict") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"pid": os.getpid(), "token": token}, handle, sort_keys=True)
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


def _write_failure(
    repository_root: Path,
    *,
    phase: str,
    error: str,
    main_commit: str | None,
    evaluation_report: dict[str, Any] | None = None,
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
) -> tuple[dict[str, Any], dict[str, Any]]:
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
    for name, payload in layer_bytes.items():
        _atomic_bytes(repository_root / LAYER_PATHS[name], payload)
    pointer = {
        "schema_version": POINTER_SCHEMA_VERSION,
        "generation_id": generation_id,
        "generation_sha256": _sha(manifest_bytes),
        "main_commit": main_commit,
        "source_snapshot_id": report["snapshot"]["snapshot_id"],
    }
    _atomic_bytes(index_root / "current.json", _render(pointer))
    _atomic_bytes(index_root / "last-known-good.json", _render(pointer))
    success_path = repository_root / "logs" / "knowledge-context" / datetime.now(timezone.utc).date().isoformat() / "publications" / generation_id / "query-report.v1.json"
    _atomic_bytes(success_path, report_bytes)
    return manifest, pointer


def run(repository_root: Path, *, publish: bool, repeat: int) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    index_root = repository_root / "knowledge" / "indexes"
    phase = "lock"
    pinned_main: str | None = None
    report: dict[str, Any] | None = None
    try:
        with _single_writer(index_root):
            phase = "pin-main"
            pinned_main = _main_commit(repository_root)
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
            )
            return {
                "status": "published",
                "main_commit": pinned_main,
                "snapshot_id": snapshot["snapshot_id"],
                "generation_id": manifest["generation_id"],
                "generation_sha256": pointer["generation_sha256"],
                "evaluation": report["summary"],
            }
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        evidence = _write_failure(
            repository_root,
            phase=phase,
            error=str(error),
            main_commit=pinned_main,
            evaluation_report=report,
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
    parser.add_argument("--repeat", type=int, default=2)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    result = run(args.repository_root, publish=args.publish, repeat=args.repeat)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] in {"publishable", "published"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

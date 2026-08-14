"""Produce a VDD-owned, content-bound source-freeze manifest."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
from typing import Any


SCHEMA_VERSION = "vdd-source-freeze-manifest.v1"
HASH_DOMAIN = "jimuyun.vdd-source-freeze-manifest.v1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def domain_hash(value: Any) -> str:
    payload = {"domain": HASH_DOMAIN, "payload": value}
    return "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def contained_path(root: Path, raw_path: object, label: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path or "\\" in raw_path or ":" in raw_path:
        raise ValueError(f"{label} must be a contained repository-relative POSIX path")
    parsed = PurePosixPath(raw_path)
    if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
        raise ValueError(f"{label} must be a contained repository-relative POSIX path")
    resolved = (root / Path(*parsed.parts)).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} escapes the repository root") from exc
    return resolved


def _canonical_package_module(root: Path):
    path = root / ".agents/skills/bmad-spec/scripts/canonical_package.py"
    spec = importlib.util.spec_from_file_location("vdd_canonical_package", path)
    if spec is None or spec.loader is None:
        raise ValueError("canonical package validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _safe_target(value: str) -> str:
    candidate = PurePosixPath(value.replace("\\", "/"))
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError("target root must be a contained repository-relative POSIX path")
    return candidate.as_posix()


def build_manifest(root: Path, spec_path: Path, target_root: str, run_id: str) -> dict[str, Any]:
    root, spec_path = root.resolve(), spec_path.resolve()
    try:
        spec_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("canonical spec escapes the repository root") from exc
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("source-freeze run ID is invalid")
    module = _canonical_package_module(root)
    descriptor, selection, selection_hash = module.build_contract(root, spec_path)
    pointer = root / "_bmad-output/specs/canonical-spec-package-selections/current" / f"{descriptor['id']}.json"
    module.validate_selection(root, spec_path, pointer)
    sources = []
    for entry in selection["role_graph"]:
        path = (root / entry["path"]).resolve()
        sources.append({"path": relative(root, path), "role": entry["role"], "sha256": file_hash(path)})
    body = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "target_root": _safe_target(target_root),
        "package_root": relative(root, spec_path.parent),
        "selection_hash": selection_hash,
        "selection_record_path": relative(root, pointer.parent.parent / f"{selection_hash.replace(':', '-')}.json"),
        "selection_pointer_path": relative(root, pointer),
        "sources": sources,
        "authorizes": [],
    }
    return {**body, "canonical_hash": domain_hash(body)}


def validate_manifest(root: Path, manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("authorizes") != []:
        raise ValueError("source-freeze manifest schema or authority is invalid")
    supplied_hash = manifest.get("canonical_hash")
    body = {key: value for key, value in manifest.items() if key != "canonical_hash"}
    if supplied_hash != domain_hash(body):
        raise ValueError("source-freeze canonical hash is stale")
    if not isinstance(manifest.get("sources"), list) or not manifest["sources"]:
        raise ValueError("source-freeze sources are invalid")
    package_root = manifest.get("package_root")
    if not isinstance(package_root, str):
        raise ValueError("source-freeze package root is invalid")
    spec_path = contained_path(root, package_root, "source-freeze package root") / "SPEC.md"
    if not spec_path.is_file():
        raise ValueError("source-freeze canonical package is missing")
    module = _canonical_package_module(root)
    descriptor, selection, selection_hash = module.build_contract(root, spec_path)
    pointer = root / "_bmad-output/specs/canonical-spec-package-selections/current" / f"{descriptor['id']}.json"
    module.validate_selection(root, spec_path, pointer)
    if manifest.get("selection_hash") != selection_hash:
        raise ValueError("source-freeze selection binding is stale")
    record = pointer.parent.parent / f"{selection_hash.replace(':', '-')}.json"
    if manifest.get("selection_pointer_path") != relative(root, pointer) or manifest.get("selection_record_path") != relative(root, record):
        raise ValueError("source-freeze selection paths are stale")
    expected_roles = [(item["path"], item["role"]) for item in selection["role_graph"]]
    actual_roles = [(item.get("path"), item.get("role")) for item in manifest["sources"]]
    if actual_roles != expected_roles:
        raise ValueError("source-freeze role graph is incomplete or drifted")
    seen: set[str] = set()
    for entry in manifest["sources"]:
        if not isinstance(entry, dict) or set(entry) != {"path", "role", "sha256"}:
            raise ValueError("source-freeze source entry is invalid")
        path = contained_path(root, entry["path"], "source-freeze source path")
        key = entry["path"].casefold()
        if key in seen or not path.is_file() or file_hash(path) != entry["sha256"]:
            raise ValueError("source-freeze source binding is stale")
        seen.add(key)


def _write_new(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError("source-freeze output is append-only")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical_bytes(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_manifest(args.repository_root, args.spec, args.target_root, args.run_id)
        validate_manifest(args.repository_root.resolve(), result)
        _write_new(args.out, result)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "family": "manifest_invalid", "detail": str(exc), "authorizes": []}))
        return 2
    print(json.dumps({"status": "source_frozen", "manifest_hash": result["canonical_hash"], "authorizes": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

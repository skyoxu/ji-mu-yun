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
ROLE_RELATIONSHIPS = {
    "canonical": "canonical_package_root",
    "normative_companion": "package_normative_companion",
    "adopted_companion": "package_adopted_companion",
    "provenance": "package_provenance",
    "repository_authority": "applicable_repository_rule",
}


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


def _repository_rules(root: Path, target_root: str) -> list[dict[str, str]]:
    target = contained_path(root, _safe_target(target_root), "target root")
    candidates: list[Path] = []
    current = target
    while True:
        candidate = current / "AGENTS.md"
        if candidate.is_file():
            candidates.append(candidate)
        if current == root:
            break
        current = current.parent
    return [
        {"path": relative(root, path), "sha256": file_hash(path), "relationship": "applicable_repository_rule"}
        for path in sorted(set(candidates), key=lambda item: relative(root, item))
    ]


def _knowledge_bindings(root: Path, target_root: str) -> list[dict[str, str]]:
    target = contained_path(root, _safe_target(target_root), "target root")
    bindings: list[dict[str, str]] = []
    for name, relationship in (
        ("knowledge-context.v1.json", "vdd_knowledge_context"),
        ("knowledge-context.freeze.v1.json", "vdd_knowledge_freeze"),
    ):
        path = target / name
        if path.is_file():
            bindings.append({"path": relative(root, path), "sha256": file_hash(path), "relationship": relationship})
    return bindings


def _artifact_ref(root: Path, value: object, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise ValueError(f"{label} reference is invalid")
    path = contained_path(root, value["path"], label)
    if not path.is_file() or value["sha256"] != file_hash(path):
        raise ValueError(f"{label} binding is stale")
    return {"path": value["path"], "sha256": value["sha256"]}


def validate_repair_input(root: Path, path: Path, target_root: str) -> dict[str, str]:
    try:
        relative_path = relative(root, path)
    except ValueError as exc:
        raise ValueError("VDD repair input must stay inside the repository") from exc
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version", "repair_id", "target_root", "frozen_authority", "review_run",
        "prior_requirements_manifest", "repaired_requirements_manifest", "validator", "policy",
        "ambiguity_ids", "affected_requirement_ids", "ambiguity", "allowed_repair_scope", "authorizes",
    }
    if set(value) != required or value.get("schema_version") != "vdd-repair-input.v1" or value.get("authorizes") != []:
        raise ValueError("VDD repair input schema or authority is invalid")
    if value.get("target_root") != _safe_target(target_root) or not isinstance(value.get("repair_id"), str) or not value["repair_id"]:
        raise ValueError("VDD repair input target or identity is invalid")
    frozen = value.get("frozen_authority")
    if not isinstance(frozen, dict) or set(frozen) != {"source_manifest", "source_manifest_canonical_hash", "role_graph_hash"}:
        raise ValueError("VDD repair input frozen authority is invalid")
    source_manifest = _artifact_ref(root, frozen["source_manifest"], "VDD repair input source manifest")
    source_manifest_value = json.loads((root / source_manifest["path"]).read_text(encoding="utf-8"))
    if not all(isinstance(frozen.get(key), str) and frozen[key].startswith("sha256:") and len(frozen[key]) == 71 for key in ("source_manifest_canonical_hash", "role_graph_hash")):
        raise ValueError("VDD repair input frozen authority hash is invalid")
    if source_manifest_value.get("canonical_hash") != frozen["source_manifest_canonical_hash"]:
        raise ValueError("VDD repair input frozen authority canonical hash is stale")
    for label in ("review_run", "prior_requirements_manifest", "repaired_requirements_manifest", "validator", "policy"):
        _artifact_ref(root, value.get(label), f"VDD repair input {label}")
    review_value = json.loads((root / value["review_run"]["path"]).read_text(encoding="utf-8"))
    if not isinstance(review_value, dict) or review_value.get("authorizes") != [] or not isinstance(review_value.get("status"), str) or not review_value["status"]:
        raise ValueError("VDD repair input review run is invalid")
    prior = value["prior_requirements_manifest"]
    repaired = value["repaired_requirements_manifest"]
    if prior["path"] == repaired["path"] and prior["sha256"] == repaired["sha256"]:
        raise ValueError("VDD repair input must bind a new requirements identity")
    if not isinstance(value["ambiguity_ids"], list) or any(not isinstance(item, str) or not item for item in value["ambiguity_ids"]):
        raise ValueError("VDD repair input ambiguity IDs are invalid")
    if not isinstance(value["affected_requirement_ids"], list) or any(not isinstance(item, str) or not item for item in value["affected_requirement_ids"]):
        raise ValueError("VDD repair input affected requirement IDs are invalid")
    ambiguity = value["ambiguity"]
    if not isinstance(ambiguity, list) or any(
        not isinstance(item, dict)
        or set(item) != {"obligation_ids", "requirement_ids", "reason", "scope"}
        or not isinstance(item["obligation_ids"], list)
        or not isinstance(item["requirement_ids"], list)
        or any(not isinstance(identifier, str) or not identifier for identifier in [*item["obligation_ids"], *item["requirement_ids"]])
        or any(not isinstance(item[key], str) or not item[key] for key in ("reason", "scope"))
        for item in ambiguity
    ):
        raise ValueError("VDD repair input ambiguity contract is invalid")
    if sorted({identifier for item in ambiguity for identifier in item["obligation_ids"]}) != sorted(value["ambiguity_ids"]) or sorted({identifier for item in ambiguity for identifier in item["requirement_ids"]}) != sorted(value["affected_requirement_ids"]):
        raise ValueError("VDD repair input ambiguity bindings are incomplete")
    scope = value["allowed_repair_scope"]
    if not isinstance(scope, list) or not scope or any(not isinstance(item, str) or not item for item in scope):
        raise ValueError("VDD repair input allowed repair scope is invalid")
    return {"path": relative_path, "sha256": file_hash(path)}


def build_manifest(
    root: Path,
    spec_path: Path,
    target_root: str,
    run_id: str,
    repair_input: dict[str, str] | None = None,
    requirements_manifest: dict[str, str] | None = None,
) -> dict[str, Any]:
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
        sources.append({
            "path": relative(root, path),
            "role": entry["role"],
            "sha256": file_hash(path),
            "relationship": ROLE_RELATIONSHIPS[entry["role"]],
        })
    repository_rules = _repository_rules(root, target_root)
    sources.extend({**rule, "role": "repository_authority"} for rule in repository_rules)
    body = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "target_root": _safe_target(target_root),
        "package_root": relative(root, spec_path.parent),
        "selection_hash": selection_hash,
        "selection_record_path": relative(root, pointer.parent.parent / f"{selection_hash.replace(':', '-')}.json"),
        "selection_pointer_path": relative(root, pointer),
        "sources": sources,
        "repository_rules": repository_rules,
        "knowledge_bindings": _knowledge_bindings(root, target_root),
        "unresolved_inputs": [],
        "repair_input": repair_input,
        "requirements_manifest": requirements_manifest,
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
    required = {
        "schema_version", "run_id", "target_root", "package_root", "selection_hash",
        "selection_record_path", "selection_pointer_path", "sources", "repository_rules",
        "knowledge_bindings", "unresolved_inputs", "repair_input", "requirements_manifest", "authorizes", "canonical_hash",
    }
    if set(manifest) != required:
        raise ValueError("source-freeze manifest fields are incomplete")
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
    expected_rules = _repository_rules(root, manifest["target_root"])
    expected_roles = [
        (item["path"], item["role"], ROLE_RELATIONSHIPS[item["role"]])
        for item in selection["role_graph"]
    ] + [
        (item["path"], "repository_authority", item["relationship"])
        for item in expected_rules
    ]
    actual_roles = [(item.get("path"), item.get("role"), item.get("relationship")) for item in manifest["sources"]]
    if actual_roles != expected_roles:
        raise ValueError("source-freeze role graph is incomplete or drifted")
    seen: set[str] = set()
    for entry in manifest["sources"]:
        if not isinstance(entry, dict) or set(entry) != {"path", "role", "sha256", "relationship"}:
            raise ValueError("source-freeze source entry is invalid")
        if entry["role"] not in ROLE_RELATIONSHIPS or entry["relationship"] != ROLE_RELATIONSHIPS[entry["role"]]:
            raise ValueError("source-freeze source relationship is invalid")
        path = contained_path(root, entry["path"], "source-freeze source path")
        key = entry["path"].casefold()
        if key in seen or not path.is_file() or file_hash(path) != entry["sha256"]:
            raise ValueError("source-freeze source binding is stale")
        seen.add(key)
    if manifest["repository_rules"] != expected_rules:
        raise ValueError("source-freeze repository rules are stale")
    expected_knowledge = _knowledge_bindings(root, manifest["target_root"])
    if manifest["knowledge_bindings"] != expected_knowledge:
        raise ValueError("source-freeze knowledge bindings are stale")
    if not isinstance(manifest["unresolved_inputs"], list) or any(
        not isinstance(item, dict) or set(item) != {"id", "reason", "target_plan"}
        or not all(isinstance(item[key], str) and item[key] for key in ("id", "reason", "target_plan"))
        for item in manifest["unresolved_inputs"]
    ):
        raise ValueError("source-freeze unresolved inputs are invalid")
    repair_input = manifest["repair_input"]
    if repair_input is not None:
        if not isinstance(repair_input, dict) or set(repair_input) != {"path", "sha256"}:
            raise ValueError("source-freeze repair input binding is invalid")
        repair_path = contained_path(root, repair_input["path"], "source-freeze repair input")
        if not repair_path.is_file() or repair_input["sha256"] != file_hash(repair_path):
            raise ValueError("source-freeze repair input is stale")
        if validate_repair_input(root, repair_path, manifest["target_root"]) != repair_input:
            raise ValueError("source-freeze repair input binding is invalid")
    requirements_manifest = manifest["requirements_manifest"]
    if requirements_manifest is not None and _artifact_ref(root, requirements_manifest, "source-freeze requirements manifest") != requirements_manifest:
        raise ValueError("source-freeze requirements identity is invalid")


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
    parser.add_argument("--repair-input", type=Path)
    parser.add_argument("--requirements-manifest", type=Path)
    args = parser.parse_args()
    try:
        root = args.repository_root.resolve()
        repair_input = validate_repair_input(root, args.repair_input.resolve(), args.target_root) if args.repair_input else None
        requirements_manifest = None
        if args.requirements_manifest:
            requirements_path = args.requirements_manifest.resolve()
            requirements_manifest = {"path": relative(root, requirements_path), "sha256": file_hash(requirements_path)}
        if repair_input is not None:
            if requirements_manifest is None:
                raise ValueError("explicit VDD repair requires a repaired requirements manifest")
            repair_value = json.loads(args.repair_input.read_text(encoding="utf-8"))
            if repair_value["repaired_requirements_manifest"] != requirements_manifest:
                raise ValueError("VDD repair requirements identity does not match repair input")
        result = build_manifest(root, args.spec, args.target_root, args.run_id, repair_input, requirements_manifest)
        validate_manifest(args.repository_root.resolve(), result)
        _write_new(args.out, result)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "family": "manifest_invalid", "detail": str(exc), "authorizes": []}))
        return 2
    print(json.dumps({"status": "source_frozen", "manifest_hash": result["canonical_hash"], "authorizes": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

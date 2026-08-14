#!/usr/bin/env python3
"""Validate a canonical SPEC descriptor and publish its selection record."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
from typing import Any


PACKAGE_SCHEMA = "canonical-spec-package.v1"
SELECTION_SCHEMA = "canonical-spec-package-selection.v1"
CURRENT_SCHEMA = "canonical-spec-package-selection-current.v1"
COMPANION_ROLES = {"normative_companion", "adopted_companion"}
DESCRIPTOR_DOMAIN = "jimuyun.canonical-spec-package.descriptor.v1"
SELECTION_DOMAIN = "jimuyun.canonical-spec-package.selection.v1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def domain_hash(domain: str, payload: Any) -> str:
    envelope = {
        "domain": domain,
        "payload": payload,
    }
    return "sha256:" + hashlib.sha256(canonical_bytes(envelope)).hexdigest()


def read_frontmatter(spec_path: Path) -> dict[str, Any]:
    text = spec_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("SPEC.md must start with YAML frontmatter")
    try:
        raw = text.split("---\n", 2)[1]
    except IndexError as exc:
        raise ValueError("SPEC.md frontmatter is not closed") from exc
    lines = raw.splitlines()
    data: dict[str, Any] = {}
    section: str | None = None
    entries: list[dict[str, str]] | None = None
    pending: dict[str, str] | None = None
    for line in lines:
        if not line.strip():
            continue
        if line.startswith("id: "):
            if "id" in data:
                raise ValueError("duplicate id field")
            data["id"] = line[4:].strip()
        elif line.startswith("package_schema: "):
            if "package_schema" in data:
                raise ValueError("duplicate package_schema field")
            data["package_schema"] = line[len("package_schema: ") :].strip()
        elif line.startswith("companions: []"):
            if "companions" in data:
                raise ValueError("duplicate companions field")
            data["companions"] = []
            section = "companions"
            entries = data["companions"]
        elif line.startswith("sources: []"):
            if "sources" in data:
                raise ValueError("duplicate sources field")
            data["sources"] = []
            section = "sources"
            entries = data["sources"]
        elif line == "companions:":
            if "companions" in data:
                raise ValueError("duplicate companions field")
            section = "companions"
            entries = []
            data[section] = entries
        elif line == "sources:":
            if "sources" in data:
                raise ValueError("duplicate sources field")
            section = "sources"
            entries = []
            data[section] = entries
        elif line.startswith("  - path: ") and entries is not None:
            pending = {"path": line[len("  - path: ") :].strip()}
            entries.append(pending)
        elif line.startswith("    role: ") and pending is not None:
            if "role" in pending:
                raise ValueError("duplicate role field")
            pending["role"] = line[len("    role: ") :].strip()
        elif line.startswith("  - "):
            raise ValueError("descriptor entries must be typed path/role objects")
        else:
            raise ValueError(f"unsupported frontmatter line: {line}")
    return data


def validate_path(repo_root: Path, raw_path: Any) -> str:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("descriptor paths must be non-empty strings")
    if "\\" in raw_path or ":" in raw_path:
        raise ValueError(f"path is not repository-relative POSIX: {raw_path}")
    path = PurePosixPath(raw_path)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"path is not contained: {raw_path}")
    resolved = (repo_root / Path(*path.parts)).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {raw_path}") from exc
    if not resolved.is_file():
        raise ValueError(f"descriptor path does not exist: {raw_path}")
    return path.as_posix()


def typed_entries(
    repo_root: Path,
    value: Any,
    field: str,
    allowed_roles: set[str],
) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    entries: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"path", "role"}:
            raise ValueError(f"{field} entries must be typed path/role objects")
        role = item["role"]
        if role not in allowed_roles:
            raise ValueError(f"unknown {field} role: {role}")
        entries.append({"path": validate_path(repo_root, item["path"]), "role": role})
    return entries


def build_contract(repo_root: Path, spec_path: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    frontmatter = read_frontmatter(spec_path)
    if frontmatter.get("package_schema") != PACKAGE_SCHEMA:
        raise ValueError(f"package_schema must be {PACKAGE_SCHEMA}")
    package_id = frontmatter.get("id")
    if not isinstance(package_id, str) or not package_id:
        raise ValueError("id must be a non-empty string")

    companions = typed_entries(repo_root, frontmatter.get("companions"), "companions", COMPANION_ROLES)
    sources = typed_entries(repo_root, frontmatter.get("sources"), "sources", {"provenance"})
    paths = [entry["path"].casefold() for entry in companions + sources]
    if len(paths) != len(set(paths)):
        raise ValueError("descriptor paths must be unique without case collisions")

    spec_relative = spec_path.resolve().relative_to(repo_root.resolve()).as_posix()
    descriptor = {
        "id": package_id,
        "package_schema": PACKAGE_SCHEMA,
        "companions": companions,
        "sources": sources,
    }
    descriptor_hash = domain_hash(DESCRIPTOR_DOMAIN, descriptor)
    role_graph = [{"path": spec_relative, "role": "canonical"}, *companions, *sources]
    selection = {
        "schema": SELECTION_SCHEMA,
        "package_id": package_id,
        "descriptor_hash": descriptor_hash,
        "role_graph": role_graph,
    }
    return descriptor, selection, domain_hash(SELECTION_DOMAIN, selection)


def validate_selection(repo_root: Path, spec_path: Path, pointer_path: Path) -> dict[str, Any]:
    """Verify the maintainer-scoped pointer and its content-addressed record."""
    descriptor, expected, selection_hash = build_contract(repo_root, spec_path)
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if pointer != {
        "package_id": descriptor["id"],
        "schema": CURRENT_SCHEMA,
        "selection_hash": selection_hash,
    }:
        raise ValueError("current selection pointer is stale or malformed")
    registry = pointer_path.parent.parent
    record_path = registry / (selection_hash.replace(":", "-") + ".json")
    if not record_path.is_file():
        raise ValueError("content-addressed selection record is missing")
    actual = json.loads(record_path.read_text(encoding="utf-8"))
    if actual != expected:
        raise ValueError("selection record does not match the current typed package")
    return {"package_id": descriptor["id"], "selection_hash": selection_hash}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(canonical_bytes(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    spec_path = args.spec.resolve()
    descriptor, selection, selection_hash = build_contract(repo_root, spec_path)

    written: list[str] = []
    if args.publish:
        registry = repo_root / "_bmad-output/specs/canonical-spec-package-selections"
        record_path = registry / f"{selection_hash.replace(':', '-')}.json"
        pointer_path = registry / "current" / f"{selection['package_id']}.json"
        write_json(record_path, selection)
        write_json(
            pointer_path,
            {
                "package_id": selection["package_id"],
                "schema": CURRENT_SCHEMA,
                "selection_hash": selection_hash,
            },
        )
        written = [record_path.relative_to(repo_root).as_posix(), pointer_path.relative_to(repo_root).as_posix()]

    print(
        json.dumps(
            {
                "ok": True,
                "descriptor_hash": selection["descriptor_hash"],
                "selection_hash": selection_hash,
                "role_graph_entries": len(selection["role_graph"]),
                "written": written,
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

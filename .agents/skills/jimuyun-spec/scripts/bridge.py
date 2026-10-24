"""ADR-0041/ADR-0062: isolate native rendering from typed package publication."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from scripts.toolchain.bmad_native import NativeError, contained, digest, invocation, new_workspace, verify
from canonical_package import build_contract, validate_selection, write_json


def package_path(root, spec):
    path = contained(root, spec)
    if not spec.startswith("_bmad-output/specs/") or path.name != "SPEC.md" or "canonical-spec-package-selections" in path.parts:
        raise ValueError("INVALID_PACKAGE_TARGET")
    return path


def package_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"SPEC-[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise ValueError("INVALID_PACKAGE_ID")
    return value


def pointer(root, identity):
    return contained(root, f"_bmad-output/specs/canonical-spec-package-selections/current/{package_id(identity)}.json")


def current_selection(root, spec, identity):
    current = pointer(root, identity)
    _, _, selection_hash = build_contract(root, spec)
    contained(root, "_bmad-output/specs/canonical-spec-package-selections/" + selection_hash.replace(":", "-") + ".json")
    return validate_selection(root, spec, current)


def split_spec(text):
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError("INVALID_NATIVE_FRONTMATTER")
    header, body = text[4:].split("\n---\n", 1)
    return header, body


def native_descriptor(text):
    """Parse native v6.12.4's small string-array frontmatter, never YAML code."""
    header, body = split_spec(text)
    data = {}
    field = None
    def scalar(raw):
        raw = raw.strip()
        if raw.startswith('"'):
            value = json.loads(raw)
        elif raw.startswith("'") and raw.endswith("'"):
            value = raw[1:-1].replace("''", "'")
        else:
            value = raw
            if any(c in raw for c in "{}[]#!&*"):
                raise ValueError("INVALID_NATIVE_SCALAR")
        if not isinstance(value, str) or not value:
            raise ValueError("INVALID_NATIVE_SCALAR")
        return value
    for line in header.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") and field in {"companions", "sources"}:
            data[field].append(scalar(line[4:]))
            continue
        key, sep, raw = line.partition(":")
        if not sep or key not in {"id", "companions", "sources"} or key in data:
            raise ValueError("INVALID_NATIVE_FRONTMATTER")
        field = key
        if key == "id":
            data[key] = scalar(raw)
        elif not raw.strip():
            data[key] = []
        else:
            data[key] = json.loads(raw.partition("#")[0].strip())
            if not isinstance(data[key], list) or not all(isinstance(p, str) for p in data[key]):
                raise ValueError("NATIVE_ARRAY_REQUIRED")
    if set(data) != {"id", "companions", "sources"}:
        raise ValueError("INVALID_NATIVE_FRONTMATTER")
    return data, body


def roles_checked(root, spec, entries):
    result = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "role"}:
            raise ValueError("INVALID_ROLE_MAP")
        path, role = entry["path"], entry["role"]
        target = contained(root, path)
        if role not in {"normative_companion", "adopted_companion", "provenance"} or path == spec:
            raise ValueError("INVALID_ROLE_MAP")
        if role == "normative_companion":
            target.relative_to(package_path(root, spec).parent)
        if target.name in {"SPEC.md", ".memlog.md"}:
            raise ValueError("INVALID_ROLE_MAP")
        if path.casefold() in {p.casefold() for p in result}:
            raise ValueError("DUPLICATE_ROLE_PATH")
        result[path] = role
    return result


def prepare(root, spec, run, identity=None, roles=()):
    root = Path(root).absolute()
    verify(root)
    target = package_path(root, spec)
    original = target.exists()
    if original:
        descriptor, selection, _ = build_contract(root, target)
        identity = package_id(descriptor["id"])
        current_selection(root, target, identity)
        entries = descriptor["companions"] + descriptor["sources"]
        if roles:
            raise ValueError("USE_PUBLISH_ROLES_FOR_CHANGES")
    else:
        identity = package_id(identity)
        entries = list(roles)
        if pointer(root, identity).exists():
            raise ValueError("PACKAGE_ID_ALREADY_SELECTED")
    role_map = roles_checked(root, spec, entries)
    snapshots = {}
    selected = list(role_map)
    if original:
        selected += [spec, str(PurePosixPath(spec).parent / ".memlog.md")]
    for relative in selected:
        path = contained(root, relative)
        if not path.is_file():
            raise ValueError("PACKAGE_INPUT_MISSING")
        snapshots[relative] = digest(path)
    folder, native = new_workspace(root, run)
    for relative in selected:
        target_copy = contained(native, relative)
        target_copy.parent.mkdir(parents=True, exist_ok=True)
        target_copy.write_bytes(contained(root, relative).read_bytes())
    native_spec = contained(native, spec)
    native_spec.parent.mkdir(parents=True, exist_ok=True)
    if original:
        _, body = split_spec(target.read_text(encoding="utf-8"))
        lines = ["---", "id: " + identity]
        for field in ("companions", "sources"):
            paths = [posixpath.relpath(e["path"], str(PurePosixPath(spec).parent)) for e in descriptor[field]]
            lines.append(field + ": " + json.dumps(paths, ensure_ascii=False))
        native_spec.write_text("\n".join(lines) + "\n---\n" + body, encoding="utf-8", newline="\n")
    custom = native / "_bmad/custom/bmad-spec.toml"
    custom.parent.mkdir(parents=True, exist_ok=True)
    custom.write_text("[workflow]\nspec_output_path = " + json.dumps(native_spec.parent.parent.as_posix(), ensure_ascii=False)
                      + "\nrun_folder_pattern = " + json.dumps(native_spec.parent.name, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    state = {"schema": "jimuyun-spec-work.v1", "spec": spec, "id": identity, "original": original,
             "roles": role_map, "role_order": list(role_map), "snapshots": snapshots}
    write_json(folder / "state.json", state)
    policy = ("Use headless bmad-spec to create or update the package at " + native_spec.parent.as_posix() + ".\n"
              "Canonical package id: " + identity + ". Write only in the isolated native project.\n"
              "The native Skill owns SPEC.md, spec-authored companions and append-only .memlog.md here.\n"
              "Use native string path arrays relative to SPEC.md, never typed frontmatter in this staging view.\n"
              "Preserve every existing CAP id and all existing companion/source entries unless the caller explicitly changes scope.\n"
              "Adopted companions and provenance files are read-only. Only the outer wrapper publishes the repository typed package.\n"
              "Read the input role map and snapshots in ../state.json relative to this project; use those paths as input.\n"
              "Do not publish selection records or invoke VDD, Quick Dev or Acceptance. Return the native headless result.\n")
    policy += "Follow native headless behavior: skip the interactive Story Breakdown; no stories feature is added by this wrapper.\n"
    from scripts.toolchain.knowledge_query import adapter
    provenance = [path for path, role in role_map.items() if role == "provenance"]
    memory = contained(root, str(PurePosixPath(spec).parent / ".memlog.md"))
    prior = memory.read_text(encoding="utf-8") if memory.is_file() else ""
    # Existing source-bound decisions are inherited, not promoted into new roles.
    inherited = bool(provenance) and all(any(path in line and snapshots[path] in line
        for line in prior.splitlines()) for path in provenance)
    if inherited:
        policy += "\nReuse inherited source decisions: current provenance bytes match recorded path/hash; no factual input change, so no supplemental query. Preserve open questions and exclusions.\n"
        # ADR-0048 / AD-5: forward the verified identity, not a new adoption claim.
        policy += "Verified inherited provenance: " + json.dumps(
            [{"path": path, "sha256": snapshots[path]} for path in provenance],
            ensure_ascii=False, sort_keys=True) + "\n"
    elif selected:
        prepared_query = adapter.prepare_consumption({
            "stage": "spec", "operation": "update" if original else "create",
            "task_id": identity, "inputs": list(role_map) or [spec],
            "scope": list(role_map) or [spec], "query": "current basis " + identity,
            "supplement_reason": "missing_or_changed_source_basis",
            "record_path": run + "/execution-record.md"}, root)
        if prepared_query["status"] == "blocked":
            raise ValueError("PLANNING_QUERY_BLOCKED:" + prepared_query["query_result"]["reason_code"])
        policy += adapter.consumption_instructions(prepared_query)
    else:
        policy += "\nNo repository source input is available: retain necessary factual questions before decisions.\n"
    prompt = invocation(root, folder, native, "bmad-spec", policy)
    return {"ok": True, "invocation": prompt.relative_to(root).as_posix(), "native_spec": native_spec.relative_to(root).as_posix(), "authorizes": []}


def publish(root, run, roles=(), removed=()):
    root = Path(root).absolute()
    if not run.startswith("logs/bmad-wrappers/"):
        raise ValueError("RUN_OUTSIDE_LOGS")
    folder = contained(root, run)
    native = folder / "native"
    verify(root)
    verify(native)
    state = json.loads(contained(folder, "state.json").read_text(encoding="utf-8"))
    spec = state["spec"]
    target = package_path(root, spec)
    if (folder / "published.json").exists():
        raise ValueError("RUN_ALREADY_PUBLISHED")
    for relative, expected in state["snapshots"].items():
        if digest(contained(root, relative)) != expected:
            raise ValueError("SOURCE_CHANGED_DURING_RENDER")
    if state["original"]:
        current_selection(root, target, state["id"])
    elif target.exists() or pointer(root, state["id"]).exists():
        raise ValueError("PACKAGE_CREATED_DURING_RENDER")
    role_map = roles_checked(root, spec, [{"path": p, "role": r} for p, r in state["roles"].items()])
    additions = roles_checked(root, spec, roles)
    for path, role in additions.items():
        if path in role_map and role_map[path] != role:
            raise ValueError("EXISTING_ROLE_CHANGE_REQUIRES_NEW_CONTRACT")
        role_map[path] = role
    if not set(removed) <= set(state["roles"]):
        raise ValueError("UNKNOWN_REMOVAL")
    native_spec = contained(native, spec)
    descriptor, body = native_descriptor(native_spec.read_text(encoding="utf-8"))
    if descriptor["id"] != state["id"]:
        raise ValueError("PACKAGE_ID_CHANGED")
    typed = {"id": state["id"], "package_schema": "canonical-spec-package.v1", "companions": [], "sources": []}
    seen = set()
    writes = {}
    for field in ("companions", "sources"):
        for raw in descriptor[field]:
            if not raw or "\\" in raw or ":" in raw or raw.startswith("/"):
                raise ValueError("UNSAFE_NATIVE_PATH")
            relative = posixpath.normpath(posixpath.join(str(PurePosixPath(spec).parent), raw))
            source = contained(native, relative)
            destination = contained(root, relative)
            if relative.casefold() in seen:
                raise ValueError("DUPLICATE_NATIVE_PATH")
            seen.add(relative.casefold())
            role = role_map.get(relative)
            if role is None or relative in removed or (role == "provenance") != (field == "sources"):
                raise ValueError("EXPLICIT_ROLE_REQUIRED")
            typed[field].append({"path": relative, "role": role})
            if role == "normative_companion":
                writes[destination] = source.read_bytes()
            elif not destination.is_file() or digest(source) != digest(destination):
                raise ValueError("READ_ONLY_INPUT_CHANGED")
    expected = set(role_map) - set(removed)
    if seen != {p.casefold() for p in expected}:
        raise ValueError("ROLE_LOSS_REJECTED")
    order = list(state.get("role_order", state["roles"]))
    order.extend(path for path in additions if path not in order)
    for field in ("companions", "sources"):
        typed[field].sort(key=lambda entry: order.index(entry["path"]))
    memlog_relative = str(PurePosixPath(spec).parent / ".memlog.md")
    memlog = contained(native, memlog_relative).read_text(encoding="utf-8")
    if state["original"]:
        old_header, old_body = split_spec(contained(root, memlog_relative).read_text(encoding="utf-8"))
        new_header, new_body = split_spec(memlog)
        # The official memlog writer refreshes its `updated` metadata on append.
        # History is the ordered body, not that mutable clock field.
        metadata = lambda value: [line for line in value.splitlines() if not line.startswith("updated:")]
        old_lines = old_body.strip("\n").splitlines()
        new_lines = new_body.strip("\n").splitlines()
        if metadata(old_header) != metadata(new_header) or new_lines[:len(old_lines)] != old_lines:
            raise ValueError("MEMLOG_HISTORY_CHANGED")
    lines = ["---", "id: " + typed["id"], "package_schema: canonical-spec-package.v1"]
    for field in ("companions", "sources"):
        entries = typed[field]
        lines.append(field + (":" if entries else ": []"))
        for entry in entries:
            lines += ["  - path: " + entry["path"], "    role: " + entry["role"]]
    writes[target] = ("\n".join(lines) + "\n---\n" + body).encode("utf-8")
    writes[contained(root, memlog_relative)] = memlog.encode("utf-8")
    # Validate the complete candidate using the unchanged canonical producer.
    # Its relative paths are identical to the final repository package.
    candidate = contained(folder, "candidate")
    for relative in [spec, *expected]:
        destination = contained(root, relative)
        staged = contained(candidate, relative)
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(writes[destination] if destination in writes else destination.read_bytes())
    _, selection, selection_hash = build_contract(candidate, contained(candidate, spec))
    selected = pointer(root, typed["id"])
    record = contained(root, "_bmad-output/specs/canonical-spec-package-selections/" + selection_hash.replace(":", "-") + ".json")
    if record.exists() and json.loads(record.read_text(encoding="utf-8")) != selection:
        raise ValueError("IMMUTABLE_SELECTION_CONFLICT")
    # Selection binds membership, not file content. Multi-file publication is
    # not a crash transaction; retain pre-publication bytes for explicit recovery.
    for destination in writes:
        if destination.exists():
            backup = contained(folder, "before-publish/" + destination.relative_to(root).as_posix())
            if backup.exists():
                raise ValueError("PUBLICATION_RECOVERY_REQUIRED")
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(destination.read_bytes())
    for destination, content in writes.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    if not record.exists():
        write_json(record, selection)
    write_json(selected, {"package_id": typed["id"], "schema": "canonical-spec-package-selection-current.v1", "selection_hash": selection_hash})
    validate_selection(root, target, selected)
    verify(root)
    verify(native)
    result = {"ok": True, "selection_hash": selection_hash, "spec": spec, "authorizes": []}
    write_json(folder / "published.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "publish"])
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--spec")
    parser.add_argument("--package-id")
    parser.add_argument("--roles", help="Contained JSON array of explicitly assigned path/role entries")
    parser.add_argument("--remove", action="append", default=[])
    args = parser.parse_args()
    try:
        roles = json.loads(contained(args.repo_root, args.roles).read_text(encoding="utf-8")) if args.roles else []
        result = prepare(args.repo_root, args.spec, args.run, args.package_id, roles) if args.action == "prepare" else publish(args.repo_root, args.run, roles, args.remove)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except NativeError as exc:
        print(json.dumps(exc.result()))
        return 2
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc) if isinstance(exc, ValueError) and re.fullmatch(r"[A-Z_]+", str(exc)) else "PACKAGE_INVALID", "authorizes": []}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

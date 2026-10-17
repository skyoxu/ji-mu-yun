"""Read-only Quick Dev raw-evidence archive preflight (Accepted ADR-0058).

This checks archival membership and reference integrity. It cannot mint a Q7,
Q8, Acceptance result, or replace any missing local native bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def canonical(value) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def contained(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    path.relative_to(root.resolve())
    return path


def inspect(root: Path, result_path: str) -> dict:
    terminal_path = contained(root, result_path)
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    if terminal.get("schema") != "quick-dev.implementation-complete-result.v2" or terminal.get("authorizes") != []:
        raise ValueError("native non-authorizing v2 terminal result required")
    missing, mismatches, roots, archive = set(), [], set(), {result_path}

    def binding(name: str, expected: str | None = None, json_canonical=False):
        path = contained(root, name)
        archive.add(name)
        if not path.is_file():
            missing.add(name)
            return None
        raw = path.read_bytes()
        value = json.loads(raw) if path.suffix == ".json" else None
        actual = canonical(value) if json_canonical else "sha256:" + hashlib.sha256(raw).hexdigest()
        if expected is not None and actual != expected:
            mismatches.append({"path": name, "expected": expected, "observed": actual, "encoding": "canonical-json" if json_canonical else "raw-bytes"})
        return value

    input_ref = terminal.get("terminal_input_ref")
    if isinstance(input_ref, str):
        inputs = binding(input_ref, terminal.get("terminal_input_sha256"), True)
    else:
        raise ValueError("terminal input reference is missing")
    predecessors = terminal.get("predecessors")
    if not isinstance(predecessors, list) or not predecessors:
        raise ValueError("terminal predecessors are missing")
    reports = []
    for predecessor in predecessors:
        report = binding(predecessor["result_ref"], predecessor["result_sha256"], True)
        if not isinstance(report, dict):
            continue
        if report.get("slice_id") != predecessor["slice_id"] or report.get("authorizes") != []:
            raise ValueError("predecessor identity or authority mismatch")
        run_root = predecessor.get("run_root")
        if not isinstance(run_root, str):
            raise ValueError("predecessor native run root is missing")
        roots.add(run_root)
        reports.append((report, run_root))
    # Snapshot descriptor/plan-state roots contain the actual native commands,
    # observations and stage descriptors, not just the terminal projection.
    for document in [inputs, *(report for report, _ in reports)]:
        if not isinstance(document, dict):
            continue
        manifest = document.get("snapshot_manifest", {})
        for row in manifest.get("roots", []):
            if row.get("root_kind") in {"descriptor", "plan_state_transition"}:
                name = row.get("repository_relative_posix_path")
                if isinstance(name, str):
                    roots.add(name)
    for name in sorted(roots):
        directory = contained(root, name)
        if not directory.exists():
            missing.add(name)
            continue
        candidates = directory.rglob("*") if directory.is_dir() else [directory]
        for path in candidates:
            if path.is_symlink():
                raise ValueError("native archive cannot follow symlinks")
            if path.is_file() and ".compiler-cache" not in path.parts and ".compiler-work" not in path.parts and "__pycache__" not in path.parts:
                archive.add(path.relative_to(root).as_posix())
    # Runtime edges use raw file references, independently of canonical Q7
    # result hashing. Retain every stage's stdout/stderr and descriptor too.
    for document, run_root in reports:
        coverage = document.get("assertion_coverage", {})
        for assertions in coverage.values():
            if not isinstance(assertions, dict):
                continue
            for references in assertions.values():
                for reference in references:
                    if not isinstance(reference, dict) or not isinstance(reference.get("path"), str):
                        raise ValueError("runtime edge reference is invalid")
                    name = (Path(run_root) / reference["path"]).as_posix()
                    binding(name, reference.get("sha256"))
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, timeout=30, check=True).stdout.decode("utf-8").split("\0")
    untracked = sorted(archive - set(tracked) - missing)
    return {"schema": "tc-d1-native-archive-audit.v1", "status": "archive-ready" if not missing and not mismatches else "archive-incomplete", "terminal_result": result_path, "predecessor_count": len(predecessors), "referenced_native_roots": sorted(roots), "missing_paths": sorted(missing), "identity_mismatches": mismatches, "archive_paths": sorted(archive - missing), "untracked_archive_paths": untracked, "does_not_validate_current_candidate": True, "authorizes": []}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = inspect(ROOT, args.result)
    output = contained(ROOT, args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    pathspec = output.with_suffix(".paths.nul")
    with pathspec.open("xb") as stream:
        for name in result["untracked_archive_paths"]:
            stream.write(name.encode("utf-8") + b"\0")
    print(json.dumps({"status": result["status"], "output": args.output, "pathspec": pathspec.relative_to(ROOT).as_posix(), "missing_count": len(result["missing_paths"]), "mismatch_count": len(result["identity_mismatches"]), "authorizes": []}, sort_keys=True))
    return 0 if result["status"] == "archive-ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())

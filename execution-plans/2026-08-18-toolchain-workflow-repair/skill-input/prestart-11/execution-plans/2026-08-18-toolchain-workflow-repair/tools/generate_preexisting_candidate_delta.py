from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def git_bytes(root: Path, revision: str, relative: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(f"path is not present at {revision}: {relative}")
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--path", action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    paths = sorted(set(args.path))
    if any(Path(path).is_absolute() or ".." in Path(path).parts for path in paths):
        raise ValueError("paths must be repository-relative and contained")
    entries = []
    for relative in paths:
        before = git_bytes(root, args.baseline, relative)
        after = git_bytes(root, args.candidate, relative)
        entries.append(
            {
                "path": relative.replace("\\", "/"),
                "baseline_sha256": sha256(before),
                "candidate_sha256": sha256(after),
                "disposition": "pre-existing-regression-or-repair-input",
            }
        )
    payload = {
        "schema_version": "toolchain-workflow-repair.pre-existing-delta.v1",
        "baseline_commit": args.baseline,
        "candidate_commit": args.candidate,
        "paths": entries,
        "generator": "tools/generate_preexisting_candidate_delta.py",
        "authorizes": [],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": "pass", "out": args.out.as_posix(), "count": len(entries)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

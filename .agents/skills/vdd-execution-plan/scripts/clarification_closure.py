#!/usr/bin/env python3
"""Build and verify the S0 clarification control-asset closure."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


# This set belongs to the S0 verifier, not to the VCR registry.  A registry
# edit cannot silently remove a control-plane consumer or owner from review.
INDEPENDENT_CONTROL_MEMBERS = frozenset({
    "references/clarification-gate.md",
    "scripts/clarification_state.py",
    "scripts/clarification_promotion.py",
    "scripts/clarification_authority_resolver.py",
    "scripts/clarification_baseline.py",
    "scripts/clarification_closure.py",
    "scripts/validate_skill_contract.py",
    "scripts/vdd-clarification-requirements.v1.json",
})


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def producer(registry: dict) -> dict:
    members = sorted({item["owner"] for item in registry["requirements"]})
    return {"schema_version": "vdd.clarification-closure-producer.v1", "members": members}


def _git_identity(repository_root: Path, path: Path) -> dict:
    relative = path.resolve().relative_to(repository_root.resolve()).as_posix()
    try:
        index = subprocess.check_output(
            ["git", "ls-files", "-s", "--", relative], cwd=repository_root, text=True, encoding="utf-8"
        ).split()
        tree = subprocess.check_output(
            ["git", "ls-tree", "HEAD", "--", relative], cwd=repository_root, text=True, encoding="utf-8"
        ).split()
    except (OSError, subprocess.CalledProcessError):
        index, tree = [], []
    return {
        "repository_path": relative,
        "head": {"mode": tree[0], "blob": tree[2]} if len(tree) >= 3 else None,
        "index": {"mode": index[0], "blob": index[1], "stage": index[2]} if len(index) >= 3 else None,
        "working_tree": {
            "raw_sha256": digest(path),
            "byte_length": path.stat().st_size,
            "mode": oct(path.stat().st_mode & 0o777),
        },
    }


def verifier(repository_root: Path, skill_root: Path, registry: dict) -> dict:
    # Deliberately do not derive verifier membership from the supplied registry.
    members = sorted(INDEPENDENT_CONTROL_MEMBERS)
    observations = []
    for member in members:
        path = skill_root / member
        observations.append({
            "path": member,
            "exists": path.is_file(),
            "sha256": digest(path) if path.is_file() else None,
            "identity": _git_identity(repository_root, path) if path.is_file() else None,
        })
    return {"schema_version": "vdd.clarification-closure-verifier.v1", "members": members, "observations": observations}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--skill-root", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--producer-out")
    parser.add_argument("--verifier-out")
    args = parser.parse_args()
    root = Path(args.repository_root).resolve()
    skill_root = Path(args.skill_root).resolve()
    try:
        skill_root.relative_to(root)
    except ValueError:
        raise SystemExit("VDD-CLARIFICATION-CLOSURE-SKILL-ROOT")
    registry = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    produced = producer(registry)
    verified = verifier(root, skill_root, registry)
    if args.producer_out:
        Path(args.producer_out).write_text(json.dumps(produced, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.verifier_out:
        Path(args.verifier_out).write_text(json.dumps(verified, indent=2) + "\n", encoding="utf-8", newline="\n")
    missing = [item["path"] for item in verified["observations"] if not item["exists"]]
    status = "PASS" if produced["members"] == verified["members"] and not missing else "FAIL"
    print(json.dumps({
        "status": status,
        "producer": produced,
        "verifier": verified,
        "findings": ["VDD-CLARIFICATION-CLOSURE"] if status == "FAIL" else [],
    }))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

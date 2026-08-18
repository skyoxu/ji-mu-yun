from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=False, capture_output=True, text=True
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git identity command failed")
    return result.stdout.strip()


def _candidate_binding(root: Path) -> str:
    head = _git(root, "rev-parse", "HEAD")
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if diff.returncode:
        raise RuntimeError("candidate diff command failed")
    return _sha256((head + "\n").encode("utf-8") + diff.stdout)


def _test_command(root: Path, selector: str) -> list[str]:
    return [sys.executable, "-B", "-m", "pytest", selector, "-q"]


def _selectors(slice_id: str | None) -> tuple[list[str], list[str]]:
    tests = {
        "R0": [".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator_trust.py"],
        "R1": [".agents/skills/quick-dev-tdd-adapter/tools/tests/test_successor_crash_recovery.py"],
        "R2": [".agents/skills/quick-dev-tdd-adapter/tools/tests/test_authorization_refresh_chain.py"],
        "R3": [".agents/skills/quick-dev-tdd-adapter/tools/tests/test_legacy_red_compatibility.py"],
        "R4": [".agents/skills/run-refactor-implementation-acceptance/tests/test_8_17_dogfood.py"],
    }
    selected = tests.get(slice_id, []) if slice_id else [
        ".agents/skills/quick-dev-tdd-adapter/tools/tests",
        ".agents/skills/run-refactor-implementation-acceptance/tests",
    ]
    command_ids = [f"{slice_id.lower()}-targeted" if slice_id else "quick-dev-suite", "acceptance-suite"]
    return selected, command_ids


def _final_bindings(plan: Path) -> tuple[dict[str, str], list[str]]:
    required = (
        "implementation-contract.v1.json",
        "command-registry.v1.json",
        "authority-manifest.v1.json",
        "knowledge-context.v1.json",
        "knowledge-context.freeze.v1.json",
    )
    hashes: dict[str, str] = {}
    missing: list[str] = []
    for name in required:
        path = plan / name
        if not path.is_file():
            missing.append(name)
        else:
            hashes[name] = _sha256(path.read_bytes())
    successor = plan / "skill-input-receipt.successor.v1.json"
    base = plan / "skill-input-receipt.v1.json"
    receipt = successor if successor.is_file() else base
    if not receipt.is_file():
        missing.append("skill-input-receipt(.successor).v1.json")
    else:
        hashes[receipt.name] = _sha256(receipt.read_bytes())
    return hashes, missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--slice")
    args = parser.parse_args()

    root = args.repository_root.resolve()
    plan = args.plan_dir.resolve()
    contract_bytes = (plan / "implementation-contract.v1.json").read_bytes()
    registry_bytes = (plan / "command-registry.v1.json").read_bytes()
    contract = json.loads(contract_bytes.decode("utf-8"))
    selectors, command_ids = _selectors(args.slice)
    failures: list[str] = []
    binding_hashes: dict[str, str] = {}
    if not args.slice:
        binding_hashes, missing = _final_bindings(plan)
        failures.extend(f"missing-binding:{name}" for name in missing)
    for selector in selectors:
        completed = subprocess.run(
            _test_command(root, selector), cwd=root, check=False
        )
        if completed.returncode:
            failures.append(selector)

    passed = not failures
    predicate = "slice-ready" if args.slice else "implementation-complete"
    terminal_command_id = (
        f"{args.slice.lower()}-terminal" if args.slice else "terminal-full"
    )
    result = {
        "schema_version": "quick-dev-tdd-adapter.terminal-result.v1",
        "plan_id": contract["plan_id"],
        "predicate": predicate,
        "status": "pass" if passed else "fail",
        "terminal_command_id": terminal_command_id,
        "contract_hash": _sha256(contract_bytes),
        "command_registry_hash": _sha256(registry_bytes),
        "candidate_binding_hash": _candidate_binding(root),
        "validated_command_ids": command_ids,
        "validated_selectors": selectors,
        "failures": failures,
        "binding_hashes": binding_hashes,
        "authorizes": ["implementation-complete"] if passed and not args.slice else [],
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8", newline="\n")
    print(encoded, end="")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

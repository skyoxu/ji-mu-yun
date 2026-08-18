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
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if untracked.returncode:
        raise RuntimeError("candidate untracked-file command failed")
    payload = bytearray((head + "\n").encode("utf-8"))
    payload.extend(diff.stdout)
    for raw_path in sorted(filter(None, untracked.stdout.split(b"\0"))):
        path = root / raw_path.decode("utf-8")
        if path.is_file():
            payload.extend(b"\0untracked\0" + raw_path + b"\0")
            payload.extend(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
    return _sha256(bytes(payload))


def _test_command(root: Path, selector: str) -> list[str]:
    return [sys.executable, "-B", "-m", "pytest", selector, "-q"]


_SLICE_TESTS = {
    "R0": [".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator_trust.py"],
    "R1": [".agents/skills/quick-dev-tdd-adapter/tools/tests/test_successor_crash_recovery.py"],
    "R2": [
        ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_authorization_refresh_chain.py",
        ".agents/skills/run-refactor-implementation-acceptance/tests/test_knowledge_degraded_execution.py",
    ],
    "R3": [".agents/skills/quick-dev-tdd-adapter/tools/tests/test_legacy_red_compatibility.py"],
    "R4": [".agents/skills/run-refactor-implementation-acceptance/tests/test_8_17_dogfood.py"],
}


def _selectors(slice_id: str | None) -> tuple[list[str], list[str]]:
    if slice_id is not None and slice_id not in _SLICE_TESTS:
        raise ValueError(f"unknown slice: {slice_id}")
    if slice_id:
        return list(_SLICE_TESTS[slice_id]), [f"{slice_id.lower()}-green"]
    selected = [selector for slice_tests in _SLICE_TESTS.values() for selector in slice_tests]
    return selected, [f"{slice_id.lower()}-green" for slice_id in _SLICE_TESTS]


def _final_bindings(root: Path, plan: Path) -> tuple[dict[str, str], list[str]]:
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
    receipt_candidates = (
        plan / "skill-input-r18" / "receipt.json",
        plan / "skill-input-receipt.successor.v1.json",
        plan / "skill-input-receipt.v1.json",
    )
    receipt = next((candidate for candidate in receipt_candidates if candidate.is_file()), None)
    if receipt is None:
        missing.append("skill-input-receipt(.successor).v1.json")
    else:
        hashes[str(receipt.relative_to(plan)).replace("\\", "/")] = _sha256(receipt.read_bytes())
        try:
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            if payload.get("ready") is not True or payload.get("authorizes") != []:
                missing.append("skill-input-receipt-not-ready-or-authorizing")
            expected_target = str(plan.relative_to(root)).replace("\\", "/")
            if payload.get("target") != expected_target:
                missing.append("skill-input-receipt-target-mismatch")
        except (OSError, ValueError):
            missing.append("skill-input-receipt-invalid-json")
    return hashes, missing


def _authority_failures(plan: Path) -> list[str]:
    failures: list[str] = []
    state_path = plan / "plan-state.v1.json"
    if not state_path.is_file():
        return ["missing-plan-state"]
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["invalid-plan-state"]
    if state.get("status") != "implementation-authorized":
        failures.append("maintainer-implementation-authorization-required")
    if "implementation-authorized" not in state.get("authorizes", []):
        failures.append("implementation-authorization-not-published")
    freeze_path = plan / "knowledge-context.freeze.v1.json"
    context_path = plan / "knowledge-context.v1.json"
    if not freeze_path.is_file() or not context_path.is_file():
        failures.append("knowledge-freeze-or-context-missing")
    else:
        try:
            freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
            expected = freeze.get("context_sha256", "")
            actual = _sha256(context_path.read_bytes())
            if expected != actual:
                failures.append("knowledge-freeze-context-mismatch")
        except (OSError, ValueError):
            failures.append("knowledge-freeze-invalid-json")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--slice")
    args = parser.parse_args()

    root = args.repository_root.resolve()
    plan = args.plan_dir.resolve()
    if not root.is_dir() or not plan.is_dir():
        print(json.dumps({"status": "fail", "failures": ["repository-or-plan-directory-missing"]}))
        return 1
    contract_bytes = (plan / "implementation-contract.v1.json").read_bytes()
    registry_bytes = (plan / "command-registry.v1.json").read_bytes()
    contract = json.loads(contract_bytes.decode("utf-8"))
    try:
        selectors, command_ids = _selectors(args.slice)
    except ValueError as exc:
        print(json.dumps({"status": "fail", "failures": [str(exc)]}))
        return 1
    failures: list[str] = []
    binding_hashes: dict[str, str] = {}
    failures.extend(_authority_failures(plan))
    if not args.slice:
        binding_hashes, missing = _final_bindings(root, plan)
        failures.extend(f"missing-binding:{name}" for name in missing)
    for selector in selectors:
        if not (root / selector).exists():
            failures.append(f"missing-selector:{selector}")
            continue
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
        "authorizes": [],
        "lifecycle_transition": "none",
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8", newline="\n")
    print(encoded, end="")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

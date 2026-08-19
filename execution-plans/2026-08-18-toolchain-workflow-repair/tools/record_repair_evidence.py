"""Produce non-authorizing repair evidence from actual local checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def command_receipt(root: Path, name: str, argv: list[str]) -> dict:
    result = subprocess.run(argv, cwd=root, capture_output=True, text=True, check=False)
    return {
        "schema_version": "toolchain-workflow-repair.command-receipt.v1",
        "command_id": name,
        "argv": argv,
        "shell": False,
        "exit_code": result.returncode,
        "stdout_sha256": sha(result.stdout.encode("utf-8")),
        "stderr_sha256": sha(result.stderr.encode("utf-8")),
        "status": "pass" if result.returncode == 0 else "fail",
        "authorizes": [],
    }


def directory_manifest(root: Path, relative: str) -> dict:
    worktree = root / relative
    tracked = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD", "--", relative], cwd=root, capture_output=True, text=True, check=False)
    paths = set(tracked.stdout.splitlines())
    if worktree.is_dir():
        paths.update(path.relative_to(root).as_posix() for path in worktree.rglob("*") if path.is_file())
    entries = []
    for path in sorted(paths):
        head = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=root, capture_output=True, check=False)
        current = root / path
        entries.append({"path": path, "head_sha256": sha(head.stdout) if head.returncode == 0 else None, "worktree_sha256": sha(current.read_bytes()) if current.is_file() else None})
    return {"schema_version": "toolchain-workflow-repair.read-only-manifest.v1", "path": relative, "entries": entries, "unchanged": all(item["head_sha256"] == item["worktree_sha256"] for item in entries), "authorizes": []}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    args = parser.parse_args()
    root, plan = args.repository_root.resolve(), args.plan_dir.resolve()
    round_dir = plan / "repair" / "round-1"
    checks = {
        "plan-tool-tests": ["python", "-m", "pytest", "-q", "execution-plans/2026-08-18-toolchain-workflow-repair/repair/round-1/tests"],
        "quick-dev-regression": ["python", "-m", "pytest", "-q", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_plan_directory_loop.py"],
        "skill-input-suite": ["python", "-m", "pytest", "-q", "scripts/python/tests/test_skill_input_consumption.py"],
    }
    receipts = {name: command_receipt(root, name, argv) for name, argv in checks.items()}
    for name, receipt in receipts.items():
        write(round_dir / "test-receipts" / f"{name}.v1.json", receipt)
    source_files = [
        "tools/validate_all.py", "tools/validate_plan_ready.py", "tools/terminal_full.py",
        "tools/migration_bridge.py", "tools/publish_implementation_authorization.py",
    ]
    inventory = []
    for relative in source_files:
        path = plan / relative
        if path.is_file():
            lines = path.read_text(encoding="utf-8").splitlines()
            inventory.append({"path": f"execution-plans/2026-08-18-toolchain-workflow-repair/{relative}", "sha256": sha(path.read_bytes()), "callsite_lines": [index for index, line in enumerate(lines, start=1) if "authorization" in line or "skill_input" in line or "repair" in line]})
    write(round_dir / "root-cause-callsite-inventory.v1.json", {"schema_version": "toolchain-workflow-repair.callsite-inventory.v1", "entries": inventory, "authorizes": []})
    composition_paths = ["implementation-contract.v1.json", "command-registry.v1.json", "authority-manifest.v1.json", "tools/validate_all.py", "tools/validate_plan_ready.py", "tools/terminal_full.py", "tools/migration_bridge.py"]
    write(round_dir / "producer-consumer-composition-receipt.v1.json", {"schema_version": "toolchain-workflow-repair.composition-receipt.v1", "bindings": [{"path": path, "sha256": sha((plan / path).read_bytes())} for path in composition_paths], "status": "pass" if all(receipt["status"] == "pass" for receipt in receipts.values()) else "fail", "authorizes": []})
    for relative, output in (("execution-plans/2026-08-17-acceptance-coordinator-efficiency", "sibling-8-17-manifest.v1.json"), ("execution-plans/2026-08-18-acceptance-coordinator-trust-recovery", "sibling-original-8-18-manifest.v1.json")):
        write(round_dir / output, directory_manifest(root, relative))
    print(json.dumps({"status": "pass" if all(value["status"] == "pass" for value in receipts.values()) else "fail", "authorizes": []}))
    return 0 if all(value["status"] == "pass" for value in receipts.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

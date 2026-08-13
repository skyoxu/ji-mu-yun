"""Execution-proof command gate for future Exact-cover implementation receipts."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"
EVIDENCE = PLAN / "implementation-evidence.v1.json"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate(command: str, item: dict) -> None:
    if not isinstance(item, dict):
        raise RuntimeError("command evidence is not an object")
    program = item.get("validation_program")
    receipt_name = item.get("validation_receipt")
    arguments = item.get("validation_arguments", [])
    acceptance_ids = item.get("acceptance_ids")
    if not isinstance(program, str) or not isinstance(receipt_name, str) or not isinstance(arguments, list) or not isinstance(acceptance_ids, list) or not acceptance_ids:
        raise RuntimeError("controlled validation binding is incomplete")
    program_path = (ROOT / program).resolve()
    receipt_path = (ROOT / receipt_name).resolve()
    for path in (program_path, receipt_path):
        try:
            path.relative_to(ROOT.resolve())
        except ValueError as exc:
            raise RuntimeError("controlled validation path escapes repository") from exc
    if not program_path.is_file() or not receipt_path.is_file() or program_path.name in {"terminal-full.py", "implementation-command.py"}:
        raise RuntimeError("controlled validation files are missing or recursive")
    if item.get("validation_program_sha256") != sha(program_path):
        raise RuntimeError("controlled validation program hash is stale")
    result = subprocess.run([sys.executable, str(program_path), *arguments], cwd=ROOT, capture_output=True, text=True, check=False, timeout=300)
    if result.returncode != 0:
        raise RuntimeError("controlled validation command failed")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != "vdd-exact-cover-validation-receipt.v1" or receipt.get("command_id") != command or receipt.get("status") != "passed":
        raise RuntimeError("controlled receipt does not prove command success")
    if receipt.get("acceptance_ids") != acceptance_ids or receipt.get("validation_program_sha256") != item["validation_program_sha256"]:
        raise RuntimeError("controlled receipt binding is stale")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise RuntimeError("controlled receipt has no artifacts")
    for artifact in artifacts:
        path = (ROOT / artifact.get("path", "")).resolve()
        if not path.is_file() or artifact.get("sha256") != sha(path):
            raise RuntimeError("controlled receipt artifact hash is stale")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    args = parser.parse_args()
    try:
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        if evidence.get("schema_version") != "vdd-exact-cover-implementation-evidence.v1" or evidence.get("status") != "implementation-ready":
            raise RuntimeError("implementation evidence is not ready")
        validate(args.command, evidence.get("commands", {}).get(args.command))
    except (OSError, json.JSONDecodeError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"implementation-command=blocked command={args.command} reason={exc}")
        return 2
    print(f"implementation-command=passed command={args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

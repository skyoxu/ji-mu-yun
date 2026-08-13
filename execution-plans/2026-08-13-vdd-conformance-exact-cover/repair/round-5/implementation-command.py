"""Fail-closed implementation evidence verifier with registry-owned bindings."""
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
REGISTRY = PLAN / "command-registry.v1.json"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def inside(path: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(ROOT.resolve())
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    args = parser.parse_args()
    try:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        record = next(item for item in registry["commands"] if item["id"] == args.command)
        acceptance = record.get("acceptance_ids")
        validator_ref = record.get("validator")
        if not isinstance(acceptance, list) or not acceptance or not isinstance(validator_ref, dict):
            raise RuntimeError("registry command lacks acceptance and validator binding")
        validator = inside(ROOT / validator_ref["path"])
        if not validator.is_file() or validator_ref.get("sha256") != sha(validator):
            raise RuntimeError("registered validator is missing or stale")
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        item = evidence.get("commands", {}).get(args.command)
        if not isinstance(item, dict) or item.get("acceptance_ids") != acceptance or item.get("validation_program") != validator_ref["path"] or item.get("validation_program_sha256") != validator_ref["sha256"]:
            raise RuntimeError("implementation evidence does not match registry binding")
        receipt = inside(ROOT / item["validation_receipt"])
        arguments = item.get("validation_arguments")
        if arguments != ["--command", args.command, "--receipt", item["validation_receipt"], "--acceptance-json", json.dumps(acceptance, separators=(",", ":"))]:
            raise RuntimeError("implementation evidence validator arguments do not match registry binding")
        result = subprocess.run([sys.executable, str(validator), *arguments], cwd=ROOT, capture_output=True, text=True, check=False, timeout=300)
        if result.returncode:
            raise RuntimeError("registered validator failed")
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        if payload.get("command_id") != args.command or payload.get("acceptance_ids") != acceptance or payload.get("status") != "passed" or payload.get("authorizes") != []:
            raise RuntimeError("validation receipt binding is invalid")
        for artifact in payload.get("artifacts", []):
            path = inside(ROOT / artifact["path"])
            if not path.is_file() or artifact.get("sha256") != sha(path):
                raise RuntimeError("validation artifact hash is stale")
    except (OSError, KeyError, TypeError, ValueError, StopIteration, json.JSONDecodeError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"implementation-command=blocked command={args.command} reason={exc}")
        return 2
    print(f"implementation-command=passed command={args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

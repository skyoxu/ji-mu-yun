"""Controlled validator for one implementation command's hash-bound receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def inside(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--acceptance-json", required=True)
    args = parser.parse_args()
    try:
        expected = json.loads(args.acceptance_json)
        receipt = json.loads(inside(args.receipt).read_text(encoding="utf-8"))
        if receipt.get("schema_version") != "vdd-exact-cover-validation-receipt.v1" or receipt.get("command_id") != args.command or receipt.get("acceptance_ids") != expected or receipt.get("status") != "passed" or receipt.get("authorizes") != []:
            raise RuntimeError("receipt does not satisfy registered command binding")
        artifacts = receipt.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise RuntimeError("receipt has no bound artifacts")
        for artifact in artifacts:
            path = inside(artifact["path"])
            if not path.is_file() or artifact.get("sha256") != sha(path):
                raise RuntimeError("receipt artifact is missing or stale")
    except (OSError, KeyError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"implementation-receipt-validator=blocked command={args.command} reason={exc}")
        return 2
    print(f"implementation-receipt-validator=passed command={args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Quick Dev-owned terminal wrapper for the legacy exact-cover plan."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def publish_receipt(plan: Path, result: dict[str, object]) -> Path:
    repair = plan / "repair" / "round-1"
    repair.mkdir(parents=True, exist_ok=True)
    base = repair / "quick-dev-implementation-complete.v1.json"
    encoded = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if base.is_file() and base.read_text(encoding="utf-8") != encoded:
        base = repair / f"quick-dev-implementation-complete.{str(result['contract_hash']).split(':', 1)[-1][:16]}.v1.json"
    if not base.is_file():
        base.write_text(encoded, encoding="utf-8", newline="\n")
    elif base.read_text(encoding="utf-8") != encoded:
        raise RuntimeError("implementation-complete successor conflicts")
    return base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root, plan = args.repository_root.resolve(), args.plan_dir.resolve()
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    registry = json.loads((plan / contract["command_registry"]).read_text(encoding="utf-8"))
    completed = subprocess.run(
        [sys.executable, str(plan / "tools" / "terminal_validation.py")],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    command_ids = [
        command_id
        for slice_ in contract["slices"]
        for key in ("red_command_ids", "green_command_ids")
        for command_id in slice_[key]
    ]
    known = {item["id"] for item in registry["commands"]}
    failures = []
    if completed.returncode != 0:
        failures.append("terminal-validation-failed")
    if any(command_id not in known for command_id in command_ids):
        failures.append("terminal-command-registry-drift")
    result: dict[str, object] = {
        "schema_version": "quick-dev-implementation-complete.v1",
        "plan_id": contract["plan_id"],
        "predicate": "implementation-complete",
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "contract_hash": digest(plan / "implementation-contract.v1.json"),
        "command_registry_hash": digest(plan / contract["command_registry"]),
        "terminal_command_id": contract["terminal"]["command_id"],
        "validated_command_ids": command_ids,
        "authorizes": ["implementation-complete"] if not failures else [],
        "lifecycle_transition": "none",
        "terminal_stdout_sha256": "sha256:" + hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
    }
    if not failures:
        result["canonical_receipt_path"] = publish_receipt(plan, result).relative_to(plan).as_posix()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--plan-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root = Path(args.repository_root)
    plan = Path(args.plan_dir)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    if status:
        return 2
    command = [sys.executable, str(plan / "tools" / "validate_all.py")]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return completed.returncode
    try:
        validation = json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return 1
    if validation.get("status") != "pass" or validation.get("validated_state") != "implementation-complete":
        return 1
    candidate_revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    tracked = subprocess.run(["git", "ls-files", "PhaseA.Platform", "PhaseA.Platform.Tests", "tests/phase_b_c_identity_isolation"], cwd=root, capture_output=True, text=True, check=True).stdout.splitlines()
    candidate_manifest = {path: "sha256:" + hashlib.sha256((root / path).read_bytes()).hexdigest() for path in tracked if (root / path).is_file()}
    manifest_hash = "sha256:" + hashlib.sha256(json.dumps(candidate_manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    bound_paths = [plan / "implementation-contract.v1.json", plan / "command-registry.v1.json", plan / "tools" / "terminal_full.py"]
    producer_hash = "sha256:" + hashlib.sha256(json.dumps({str(p.relative_to(root)): "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest() for p in bound_paths if p.exists()}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    result = {
        "schema_version": "quick-dev-implementation-complete.v2",
        "plan_id": "2026-08-24-phase-b-c-identity-isolation-workspace-recovery",
        "status": "pass",
        "predicate": "implementation-complete",
        "terminal_command_id": "implementation-complete",
        "validated_command_ids": ["s0-green", "s1-green", "s2-green", "s3-green", "s4-green", "s4-terminal"],
        "authorizes": ["implementation-complete"],
        "candidate": {"revision": candidate_revision, "manifest_sha256": manifest_hash, "manifest": candidate_manifest},
        "bindings": {"contract": str((plan / "implementation-contract.v1.json")), "registry": str((plan / "command-registry.v1.json")), "terminal_runner": str(Path(__file__).relative_to(root)), "producer_hash": producer_hash},
        "published_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract_hash": "sha256:" + hashlib.sha256((plan / "implementation-contract.v1.json").read_bytes()).hexdigest(),
        "command_registry_hash": "sha256:" + hashlib.sha256((plan / "command-registry.v1.json").read_bytes()).hexdigest(),
        "validation": validation,
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    handoff = output.parent / "acceptance-handoff.v2.json"
    handoff.write_text(json.dumps({"schema_version": "acceptance-handoff.v2", "status": "ready", "candidate_revision": candidate_revision, "candidate_manifest_sha256": manifest_hash, "implementation_receipt": str(output.relative_to(root)), "terminal_result": "pass"}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

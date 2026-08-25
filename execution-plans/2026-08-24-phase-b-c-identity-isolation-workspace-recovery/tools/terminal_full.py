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
    status_lines = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True).stdout.splitlines()
    status = "\n".join(line for line in status_lines if "execution-plans/2026-08-24-phase-b-c-identity-isolation-workspace-recovery/terminal/" not in line)
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
    def git_bytes(path: Path) -> bytes:
        relative = path.relative_to(root).as_posix()
        return subprocess.run(["git", "show", f"{candidate_revision}:{relative}"], cwd=root, capture_output=True, check=True).stdout
    tracked = subprocess.run(["git", "ls-files", "PhaseA.Platform", "PhaseA.Platform.Tests", "tests/phase_b_c_identity_isolation"], cwd=root, capture_output=True, text=True, check=True).stdout.splitlines()
    entries = []
    for path in tracked:
        source = root / path
        if source.is_file():
            entries.append({"path": path.replace("\\", "/"), "role": "production" if path.startswith("PhaseA.Platform/") else "test", "slice_ids": ["S0", "S1", "S2", "S3", "S4"], "sha256": "sha256:" + hashlib.sha256(git_bytes(source)).hexdigest()})
    entries.sort(key=lambda item: (item["path"], item["role"], item["slice_ids"]))
    source_root = "sha256:" + hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest = {"schema_version": "jimuyun.candidate-source-manifest.v1", "entries": entries, "candidate_source_root": source_root}
    manifest_path = plan / "terminal" / "candidate-source-manifest.v1.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    manifest_hash = "sha256:" + hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    terminal_path = plan / "terminal" / "terminal-result.json"
    terminal_document = {"schema_version": "acceptance-coordinator-efficiency.terminal-result.v2", "predicate": "implementation-complete", "status": "pass", "terminal_command_id": "terminal-full", "authorizes": []}
    terminal_path.write_text(json.dumps(terminal_document, indent=2) + "\n", encoding="utf-8")
    contract_path = plan / "implementation-contract.v1.json"
    registry_path = plan / "command-registry.v1.json"
    runner_path = plan / "tools" / "terminal_full.py"
    bound_paths = [plan / "implementation-contract.v1.json", plan / "command-registry.v1.json", plan / "tools" / "terminal_full.py"]
    producer_hash = "sha256:" + hashlib.sha256(json.dumps({p.relative_to(root).as_posix(): "sha256:" + hashlib.sha256(git_bytes(p)).hexdigest() for p in bound_paths if p.exists()}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    result = {
        "schema_version": "quick-dev-implementation-complete.v2",
        "plan_id": "2026-08-24-phase-b-c-identity-isolation-workspace-recovery",
        "status": "pass",
        "predicate": "implementation-complete",
        "terminal_command_id": "terminal-full",
        "validated_command_ids": ["s0-green", "s1-green", "s2-green", "s3-green", "s4-green", "s4-terminal"],
        "authorizes": ["acceptance-handoff"],
        "implementation_contract": {"path": "implementation-contract.v1.json", "sha256": "sha256:" + hashlib.sha256(git_bytes(contract_path)).hexdigest()},
        "command_registry": {"path": "command-registry.v1.json", "sha256": "sha256:" + hashlib.sha256(git_bytes(registry_path)).hexdigest()},
        "terminal_runner": {"path": "tools/terminal_full.py", "sha256": "sha256:" + hashlib.sha256(git_bytes(runner_path)).hexdigest()},
        "terminal_result": {"path": "terminal/terminal-result.json", "sha256": "sha256:" + hashlib.sha256(terminal_path.read_bytes()).hexdigest(), "command_id": "terminal-full"},
        "candidate_custody": {"mode": "commit", "candidate_revision": candidate_revision},
        "candidate_source_manifest": {"path": "terminal/candidate-source-manifest.v1.json", "sha256": manifest_hash, "candidate_source_root": source_root},
        "validated_command_ids": validation.get("results", [{}])[0].get("type") and ["implementation-complete"] or [],
        "bindings": {"producer_hash": producer_hash},
        "published_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract_hash": "sha256:" + hashlib.sha256((plan / "implementation-contract.v1.json").read_bytes()).hexdigest(),
        "command_registry_hash": "sha256:" + hashlib.sha256((plan / "command-registry.v1.json").read_bytes()).hexdigest(),
        "validation": validation,
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    handoff = output.parent / "acceptance-handoff.v2.json"
    handoff.write_text(json.dumps({"schema_version": "acceptance-handoff.v2", "status": "ready", "candidate_revision": candidate_revision, "candidate_manifest_sha256": manifest_hash, "implementation_receipt": output.relative_to(root).as_posix(), "terminal_result": "pass", "authorizes": ["acceptance-handoff"]}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

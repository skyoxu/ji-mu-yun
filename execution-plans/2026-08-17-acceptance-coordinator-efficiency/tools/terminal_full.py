"""Run terminal checks and publish hash-bound Quick Dev completion evidence."""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1]
ROOT = PLAN.parents[1]

def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()

def _fh(path: Path) -> str:
    return _sha(path.read_bytes())

def _run(suites):
    done = []
    for directory, pattern in suites:
        command = ([sys.executable, "-B", "-m", "pytest", pattern, "-q"] if directory == "pytest" else [sys.executable, "-B", "-m", "unittest", "discover", "-s", directory, "-p", pattern])
        env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(ROOT / ".agents/skills/quick-dev-tdd-adapter/tools"), os.environ.get("PYTHONPATH", "")]))}
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, check=False)
        if result.returncode:
            return False, done
        done.append(f"pytest:{pattern}" if directory == "pytest" else f"unittest:{directory}:{pattern}")
    return True, done

def _entries():
    return [
        {"path": ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py", "role": "production", "slice_ids": ["S3"]},
        {"path": ".agents/skills/run-refactor-implementation-acceptance/scripts/execution_control.py", "role": "production", "slice_ids": ["S0", "S2", "S3"]},
        {"path": ".agents/skills/run-refactor-implementation-acceptance/scripts/compact_vdd_projection.py", "role": "contract-consumer", "slice_ids": ["S0"]},
        {"path": ".agents/skills/run-refactor-implementation-acceptance/scripts/deterministic_finalization.py", "role": "contract-consumer", "slice_ids": ["S0", "S3"]},
        {"path": ".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator.py", "role": "test", "slice_ids": ["S3"]},
        {"path": ".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator_trust.py", "role": "test", "slice_ids": ["S0", "S2"]},
        {"path": ".agents/skills/run-refactor-implementation-acceptance/tests/test_compact_vdd_projection.py", "role": "test", "slice_ids": ["S0"]},
        {"path": ".agents/skills/run-refactor-implementation-acceptance/tests/test_deterministic_finalization.py", "role": "test", "slice_ids": ["S0", "S3"]},
        {"path": "execution-plans/2026-08-17-acceptance-coordinator-efficiency/tools/terminal_full.py", "role": "validator", "slice_ids": ["S0", "S1", "S2", "S3"]},
        {"path": "execution-plans/2026-08-17-acceptance-coordinator-efficiency/implementation-contract.v1.json", "role": "contract", "slice_ids": ["S0", "S1", "S2", "S3"]},
        {"path": "execution-plans/2026-08-17-acceptance-coordinator-efficiency/command-registry.v1.json", "role": "contract", "slice_ids": ["S0", "S1", "S2", "S3"]},
    ]

def build_candidate_source_manifest(root: Path):
    entries = []
    for item in _entries():
        path = root / item["path"]
        if not path.is_file():
            raise RuntimeError("candidate source is missing: " + item["path"])
        entries.append({**item, "slice_ids": sorted(item["slice_ids"]), "sha256": _fh(path)})
    entries.sort(key=lambda x: (x["path"], x["role"], tuple(x["slice_ids"])))
    return {"schema_version": "jimuyun.candidate-source-manifest.v1", "entries": entries, "candidate_source_root": _sha(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode())}

def terminal_result(predicate, command_id, suites):
    passed, done = _run(suites)
    return {"schema_version": "acceptance-coordinator-efficiency.terminal-result.v2", "status": "pass" if passed else "fail", "predicate": predicate, "plan_id": "acceptance-coordinator-efficiency", "terminal_command_id": command_id, "implementation_contract": {"path": "implementation-contract.v1.json", "sha256": _fh(PLAN / "implementation-contract.v1.json")}, "command_registry": {"path": "command-registry.v1.json", "sha256": _fh(PLAN / "command-registry.v1.json")}, "terminal_runner": {"path": "tools/terminal_full.py", "sha256": _fh(Path(__file__))}, "validated_command_ids": done, "authorizes": []}

def publish_completion_handoff(root: Path, plan: Path, terminal_path: Path):
    terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
    if terminal.get("schema_version") != "acceptance-coordinator-efficiency.terminal-result.v2" or terminal.get("status") != "pass" or terminal.get("predicate") != "implementation-complete" or terminal.get("terminal_command_id") != "terminal-full" or terminal.get("authorizes") != []:
        raise RuntimeError("terminal result does not prove implementation-complete")
    manifest = build_candidate_source_manifest(root)
    binding = manifest["candidate_source_root"].split(":", 1)[1][:16]
    out = plan / "completion-handoffs"; out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / f"candidate-source-manifest.{binding}.v1.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    receipt = {"schema_version": "quick-dev-implementation-complete.v2", "plan_id": "acceptance-coordinator-efficiency", "predicate": "implementation-complete", "status": "pass", "implementation_contract": {"path": "implementation-contract.v1.json", "sha256": _fh(plan / "implementation-contract.v1.json")}, "command_registry": {"path": "command-registry.v1.json", "sha256": _fh(plan / "command-registry.v1.json")}, "terminal_runner": {"path": "tools/terminal_full.py", "sha256": _fh(plan / "tools/terminal_full.py")}, "candidate_custody": {"mode": "commit", "candidate_revision": head}, "candidate_source_manifest": {"path": manifest_path.relative_to(plan).as_posix(), "sha256": _fh(manifest_path), "candidate_source_root": manifest["candidate_source_root"]}, "terminal_result": {"path": terminal_path.relative_to(plan).as_posix(), "sha256": _fh(terminal_path), "command_id": "terminal-full"}, "validated_command_ids": terminal["validated_command_ids"], "authorizes": ["acceptance-handoff"]}
    receipt_path = out / f"quick-dev-implementation-complete.{binding}.v2.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return receipt_path

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--slice", choices=("S0", "S1", "S2", "S3")); parser.add_argument("--quick-dev-regression", action="store_true"); parser.add_argument("--repository-root", type=Path, default=ROOT); parser.add_argument("--plan-dir", type=Path, default=PLAN); parser.add_argument("--out", type=Path); parser.add_argument("--publish-completion", action="store_true"); parser.add_argument("--terminal-result", type=Path)
    args = parser.parse_args()
    suites = {"S0": (("pytest", ".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator_s0.py"),), "S1": (("pytest", ".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator_s1.py"),), "S2": (("pytest", ".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator_s2.py"),), "S3": (("pytest", ".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator.py"),)}
    regression = ((".agents/skills/quick-dev-tdd-adapter/tools/tests", "test_candidate_identity.py"), (".agents/skills/quick-dev-tdd-adapter/tools/tests", "test_plan_directory_loop.py"), (".agents/skills/quick-dev-tdd-adapter/tools/tests", "test_adapter.py"))
    if args.publish_completion:
        if args.terminal_result is None: parser.error("--publish-completion requires --terminal-result")
        result = {"status": "pass", "receipt": publish_completion_handoff(args.repository_root.resolve(), args.plan_dir.resolve(), args.terminal_result.resolve()).relative_to(args.repository_root.resolve()).as_posix()}
    elif args.slice: result = terminal_result("slice-ready", f"s{args.slice[1]}-terminal", suites[args.slice])
    elif args.quick_dev_regression: result = terminal_result("slice-ready", "quick-dev-suite", regression)
    else:
        result = terminal_result("implementation-complete", "terminal-full", (*regression, ("pytest", ".agents/skills/run-refactor-implementation-acceptance/tests")))
        if args.out is not None: args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, separators=(",", ":"))); return 0 if result["status"] == "pass" else 1

if __name__ == "__main__": raise SystemExit(main())

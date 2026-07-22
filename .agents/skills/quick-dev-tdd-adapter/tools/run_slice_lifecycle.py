from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess


TOOLS = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"missing shared tool: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--run-context", type=Path, required=True)
    parser.add_argument("--snapshot-path", action="append", required=True)
    parser.add_argument("--command", action="append", required=True,
                        help="stage=path-to-shell-false-command-json")
    parser.add_argument("--terminal-command", type=Path, required=True)
    args = parser.parse_args()
    workspace, run_dir = args.workspace.resolve(), args.run_dir.resolve()
    if run_dir.exists():
        raise ValueError("run directory already exists")
    context = json.loads(args.run_context.read_text(encoding="utf-8"))
    commands = {}
    for item in args.command:
        stage, separator, path = item.partition("=")
        if separator != "=" or stage not in {"red", "green", "refactor"}:
            raise ValueError("commands must be stage=path")
        command = json.loads(Path(path).read_text(encoding="utf-8"))
        if command.get("shell") is not False:
            raise ValueError("shell commands are forbidden")
        commands[stage] = command
    if set(commands) != {"red", "green", "refactor"}:
        raise ValueError("all TDD stages require a command")
    lifecycle = _load("stage_lifecycle_runner").LifecycleRunner(workspace, run_dir, args.snapshot_path)
    for stage in ("red", "green", "refactor"):
        lifecycle.observe(stage, commands[stage], f"Recorded {stage} command observation.")
    bundle = lifecycle.close(context, {})
    plan_tools = workspace / "execution-plans" / "2026-07-15-repository-maintenance-tdd-adapter" / "tools"
    projection_spec = importlib.util.spec_from_file_location("stage_projection_builder", plan_tools / "stage_projection_builder.py")
    if projection_spec is None or projection_spec.loader is None:
        raise RuntimeError("plan-local stage projection builder is unavailable")
    projection = importlib.util.module_from_spec(projection_spec)
    projection_spec.loader.exec_module(projection)
    output = run_dir / "stage-evidence-projection.v1.json"
    output.write_text(json.dumps(projection.build(workspace, run_dir, args.slice_id, args.snapshot_path), indent=2) + "\n", encoding="utf-8")
    terminal = json.loads(args.terminal_command.read_text(encoding="utf-8"))
    if terminal.get("shell") is not False:
        raise ValueError("terminal command must be shell-free")
    completed = subprocess.run([terminal["executable"], *terminal["argv"]], cwd=workspace, shell=False, check=False, capture_output=True, timeout=terminal["timeout_seconds"])
    if completed.returncode:
        raise RuntimeError("plan-local terminal predicate failed")
    state = run_dir.parents[2] / "run-state.v1.json"
    state.write_text(json.dumps({"schema_version": "jimuyun.tdd-adapter-run-state.v1", "last_slice_id": args.slice_id, "last_observed_predicate": "slice-ready", "next_action": "route", "failure_fingerprint": None, "repeat_count": 0, "authorizes": [], "does_not_authorize": ["implementation-accepted", "commit", "release"]}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_dir.name, "stages": ["red", "green", "refactor"], "bundle_schema": bundle["schema_version"], "terminal_exit": completed.returncode, "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

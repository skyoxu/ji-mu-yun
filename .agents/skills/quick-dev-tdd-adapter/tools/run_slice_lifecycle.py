from __future__ import annotations

import argparse
import base64
import importlib.util
import json
from pathlib import Path
import subprocess
from typing import Any


TOOLS = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"missing shared tool: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _command(path: str) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"id", "executable", "argv", "cwd", "timeout_seconds", "shell"}
    if not isinstance(document, dict) or set(document) != required or document.get("shell") is not False:
        raise ValueError("command must be a structured shell-free descriptor")
    if document.get("cwd") != "." or not isinstance(document.get("argv"), list) or any(not isinstance(item, str) for item in document["argv"]):
        raise ValueError("command descriptor has an unsafe working directory or arguments")
    return document


def _run(workspace: Path, command: dict[str, Any]) -> int:
    completed = subprocess.run([command["executable"], *command["argv"]], cwd=workspace / command["cwd"], shell=False, check=False, capture_output=True, timeout=command["timeout_seconds"])
    return completed.returncode


def _run_terminal(workspace: Path, command: dict[str, Any]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run([command["executable"], *command["argv"]], cwd=workspace / command["cwd"], shell=False, check=False, capture_output=True, timeout=command["timeout_seconds"])


def _projection(plan_dir: Path):
    spec = importlib.util.spec_from_file_location("plan_stage_projection_builder", plan_dir / "tools" / "stage_projection_builder.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("plan-local stage projection builder is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--run-context", type=Path, required=True)
    parser.add_argument("--snapshot-path", action="append", required=True)
    parser.add_argument("--command", action="append", required=True, help="stage=path-to-shell-false-command-json")
    parser.add_argument("--terminal-command", type=Path, required=True)
    parser.add_argument("--prepare-command", type=Path, action="append", default=[])
    args = parser.parse_args()
    workspace, plan_dir, run_dir = args.workspace.resolve(), args.plan_dir.resolve(), args.run_dir.resolve()
    try:
        plan_dir.relative_to((workspace / "execution-plans").resolve())
    except ValueError as exc:
        raise ValueError("plan directory must stay under workspace execution-plans") from exc
    if run_dir.exists():
        raise ValueError("run directory already exists")
    context = json.loads(args.run_context.read_text(encoding="utf-8"))
    if context.get("slice_id") != args.slice_id or not isinstance(context.get("plan_id"), str):
        raise ValueError("run context identity does not match invocation")
    for item in [*context["authority_refs"], context["implementation_contract"]]:
        item["payload"] = base64.b64decode(item.pop("payload_base64"), validate=True)

    commands: dict[str, list[dict[str, Any]]] = {"red": [], "green": [], "refactor": []}
    for item in args.command:
        stage, separator, path = item.partition("=")
        if separator != "=" or stage not in commands:
            raise ValueError("commands must be red=path, green=path, or refactor=path")
        commands[stage].append(_command(path))
    if len(commands["red"]) != 1 or len(commands["green"]) != 1 or not commands["refactor"]:
        raise ValueError("RED and GREEN require one command; REFACTOR requires at least one")

    lifecycle = _load("stage_lifecycle_runner").LifecycleRunner(workspace, run_dir, args.snapshot_path)
    red = lifecycle.observe("red", commands["red"][0], "Recorded RED command observation.")
    if red["exit_code"] == 0:
        raise RuntimeError("RED command unexpectedly passed")
    green = lifecycle.observe("green", commands["green"][0], "Recorded GREEN command observation.")
    if green["exit_code"] != 0:
        raise RuntimeError("GREEN command failed")
    for command in commands["refactor"][:-1]:
        if _run(workspace, command) != 0:
            raise RuntimeError("REFACTOR pre-observation command failed")
    refactor = lifecycle.observe("refactor", commands["refactor"][-1], "Recorded REFACTOR command observation.")
    if refactor["exit_code"] != 0:
        raise RuntimeError("REFACTOR command failed")

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "recovery-state.json").write_text(json.dumps({
        "schema_version": "rmap.recovery-state.v1", "run_id": run_dir.name,
        "state": "active", "contract_hash": context["stage_results"]["red"]["contract_hash"],
        "validator_hash": context["stage_results"]["red"]["validator_hash"],
        "predecessor_run_id": None, "supersedes_run_id": None,
    }, indent=2) + "\n", encoding="utf-8", newline="\n")

    # The composer supplies protocol bindings; only observed values are injected here.
    for stage, observation in (("red", red), ("green", green), ("refactor", refactor)):
        core = context["stage_results"][stage]
        core["exit_code"] = observation["exit_code"]
        core["observed_at"] = observation["observed_at"]
        if stage == "refactor":
            core["command_ids"] = [item["id"] for item in commands["refactor"]]
            core["command_id"] = commands["refactor"][0]["id"]
    bundle = lifecycle.close(context, {})

    projection = _projection(plan_dir)
    output = run_dir / "stage-evidence-projection.v1.json"
    output.write_text(json.dumps(projection.build(workspace, run_dir, args.slice_id, args.snapshot_path), indent=2) + "\n", encoding="utf-8", newline="\n")
    for path in args.prepare_command:
        preparation = _command(str(path))
        if _run(workspace, preparation) != 0:
            raise RuntimeError("plan-local candidate preparation failed")
    terminal = _command(str(args.terminal_command))
    terminal_result = _run_terminal(workspace, terminal)
    if terminal_result.returncode != 0:
        raise RuntimeError("plan-local terminal predicate failed")
    try:
        predicate_result = json.loads(terminal_result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("terminal predicate did not emit a JSON result") from exc
    if predicate_result.get("status") != "pass" or not isinstance(predicate_result.get("predicate"), str):
        raise RuntimeError("terminal predicate output is not a passing result")
    (run_dir / f"{predicate_result['predicate']}-result.json").write_text(
        json.dumps(predicate_result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    state = run_dir.parents[1] / "run-state.v1.json"
    state.write_text(json.dumps({"schema_version": "jimuyun.tdd-adapter-run-state.v1", "last_slice_id": args.slice_id, "last_observed_predicate": "slice-ready", "next_action": "route", "failure_fingerprint": None, "repeat_count": 0, "authorizes": [], "does_not_authorize": ["implementation-accepted", "commit", "release"]}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"run_id": run_dir.name, "stages": ["red", "green", "refactor"], "bundle_schema": bundle["schema_version"], "terminal_exit": 0, "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

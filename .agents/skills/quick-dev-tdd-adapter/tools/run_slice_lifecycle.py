from __future__ import annotations

import argparse
import base64
import hashlib
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
    print(json.dumps({"event": "command-start", "command_id": command["id"]}), flush=True)
    completed = subprocess.run([command["executable"], *command["argv"]], cwd=workspace / command["cwd"], shell=False, check=False, timeout=command["timeout_seconds"])
    print(json.dumps({"event": "command-finished", "command_id": command["id"], "exit_code": completed.returncode}), flush=True)
    return completed.returncode


def _run_terminal(workspace: Path, command: dict[str, Any]) -> subprocess.CompletedProcess[bytes]:
    print(json.dumps({"event": "terminal-start", "command_id": command["id"]}), flush=True)
    completed = subprocess.run([command["executable"], *command["argv"]], cwd=workspace / command["cwd"], shell=False, check=False, capture_output=True, timeout=command["timeout_seconds"])
    print(json.dumps({"event": "terminal-finished", "command_id": command["id"], "exit_code": completed.returncode}), flush=True)
    return completed


def _projection(plan_dir: Path):
    spec = importlib.util.spec_from_file_location("plan_stage_projection_builder", plan_dir / "tools" / "stage_projection_builder.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("plan-local stage projection builder is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_red_exit(mode: str, exit_code: int) -> None:
    if mode == "legacy-regression":
        if exit_code != 0:
            raise RuntimeError("legacy regression command failed")
        return
    if mode != "red":
        raise RuntimeError("RED mode is invalid")
    if exit_code == 0:
        raise RuntimeError("RED command unexpectedly passed")


def _prior_red_successor(workspace: Path, prior_red: Any, command_id: str) -> dict[str, str]:
    """Validate immutable predecessor RED without importing its snapshots or observation."""
    if not isinstance(prior_red, dict) or set(prior_red) != {"path", "sha256"}:
        raise RuntimeError("prior RED successor reference is missing")
    path, expected_hash = prior_red["path"], prior_red["sha256"]
    if not isinstance(path, str) or not isinstance(expected_hash, str) or not expected_hash.startswith("sha256:"):
        raise RuntimeError("prior RED successor reference is invalid")
    root = workspace.resolve()
    evidence = (root / path).resolve()
    try:
        evidence.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("prior RED successor reference escapes workspace") from exc
    raw = evidence.read_bytes()
    if "sha256:" + hashlib.sha256(raw).hexdigest() != expected_hash:
        raise RuntimeError("prior RED evidence hash is stale")
    try:
        observation = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("prior RED evidence is invalid") from exc
    if (
        not isinstance(observation, dict)
        or observation.get("stage") != "red"
        or not isinstance(observation.get("exit_code"), int)
        or observation["exit_code"] == 0
        or not isinstance(observation.get("commands_attempted"), list)
        or command_id not in observation.get("commands_attempted", [])
    ):
        raise RuntimeError("prior RED evidence is not a matching failed RED")
    return {"path": path, "sha256": expected_hash}


def _prior_red_basis(workspace: Path, prior_red: dict[str, str]) -> tuple[dict[str, str], str] | None:
    """Resolve the predecessor basis that accompanies a prior RED observation."""
    observation = (workspace.resolve() / prior_red["path"]).resolve()
    try:
        observation.relative_to(workspace.resolve())
    except ValueError:
        return None
    basis = observation.parent.parent / "red-basis.v1.json"
    if not basis.is_file():
        return None
    try:
        json.loads(basis.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return (
        {"path": basis.relative_to(workspace.resolve()).as_posix(), "sha256": "sha256:" + hashlib.sha256(basis.read_bytes()).hexdigest()},
        basis.parent.name,
    )


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
    parser.add_argument("--stage", choices=("all", "red", "green", "refactor"), default="all")
    args = parser.parse_args()
    workspace, plan_dir, run_dir = args.workspace.resolve(), args.plan_dir.resolve(), args.run_dir.resolve()
    try:
        plan_dir.relative_to((workspace / "execution-plans").resolve())
    except ValueError as exc:
        raise ValueError("plan directory must stay under workspace execution-plans") from exc
    if run_dir.exists() and args.stage in {"all", "red"}:
        raise ValueError("run directory already exists")
    if args.stage in {"green", "refactor"} and not run_dir.is_dir():
        raise ValueError("stage successor run directory is missing")
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

    stage_runner = _load("stage_lifecycle_runner")
    lifecycle = stage_runner.LifecycleRunner(workspace, run_dir, args.snapshot_path)
    red_core = context["stage_results"]["red"]
    red_mode = red_core.get("mode", "red")
    predecessor = red_core.get("legacy_predecessor")
    if red_mode == "legacy-regression" and (
        not isinstance(predecessor, dict) or set(predecessor) != {"path", "sha256"}
    ):
        raise RuntimeError("legacy regression predecessor is missing")
    prior_red = red_core.get("prior_red")
    if args.stage == "red":
        run_dir.mkdir(parents=True, exist_ok=True)
        red = lifecycle.observe(
            "red", commands["red"][0],
            "Recorded declared legacy regression observation." if red_mode == "legacy-regression" else "Recorded RED command observation.",
        )
        _validate_red_exit(red_mode, red["exit_code"])
        red_core = context["stage_results"]["red"]
        (run_dir / "red-basis.v1.json").write_text(json.dumps({
            "schema_version": "quick-dev-tdd-adapter.red-basis.v1",
            "failure_intent": {"command_id": red_core["command_id"], "test_selector": red_core["test_selector"], "expected_failure_ids": red_core["expected_failure_ids"]},
            "test_selector": red_core["test_selector"],
            "test_sha256": red_core["test_sha256"],
            "contract_hash": red_core["contract_hash"],
            "validator_hash": red_core["validator_hash"],
            "execution_fingerprint": red_core["execution_fingerprint"],
            "pre_implementation_candidate": red_core["pre_implementation_candidate"],
            "authorizes": [],
        }, indent=2) + "\n", encoding="utf-8", newline="\n")
        (run_dir / "stage-state.json").write_text(json.dumps({"stage": "red", "next_stage": "implement", "authorizes": []}, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"run_id": run_dir.name, "stage": "red", "next_stage": "implement", "authorizes": []}, sort_keys=True))
        return 0

    if args.stage in {"green", "refactor"}:
        if args.stage == "green" and not stage_runner.validate_implementation_successor(run_dir):
            raise RuntimeError("GREEN requires a valid RED-bound implementation successor")
        lifecycle.resume_observations(run_dir, ["red"] if args.stage == "green" else ["red", "green"])
    else:
        if red_mode == "prior-red-successor":
            prior_red = _prior_red_successor(workspace, prior_red, commands["red"][0]["id"])
            lifecycle.begin_after_prior_red()
            red = {"exit_code": None, "observed_at": None}
        else:
            red = lifecycle.observe(
                "red", commands["red"][0],
                "Recorded declared legacy regression observation." if red_mode == "legacy-regression" else "Recorded RED command observation.",
            )
            _validate_red_exit(red_mode, red["exit_code"])

    if args.stage == "refactor":
        green = json.loads((run_dir / "observations" / "green-observed.json").read_text(encoding="utf-8"))
    else:
        green = lifecycle.observe("green", commands["green"][0], "Recorded GREEN command observation.")
    if green["exit_code"] != 0:
        raise RuntimeError("GREEN command failed")
    if args.stage == "green":
        if green["exit_code"] != 0:
            raise RuntimeError("GREEN command failed")
        (run_dir / "stage-state.json").write_text(json.dumps({"stage": "green", "next_stage": "refactor", "authorizes": []}, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"run_id": run_dir.name, "stage": "green", "next_stage": "refactor", "authorizes": []}, sort_keys=True))
        return 0

    existing_refactor = run_dir / "observations" / "refactor-observed.json"
    if args.stage == "refactor" and existing_refactor.is_file():
        refactor = json.loads(existing_refactor.read_text(encoding="utf-8"))
        if refactor.get("stage") != "refactor" or refactor.get("exit_code") != 0:
            raise RuntimeError("existing REFACTOR observation is not reusable")
    else:
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
    for stage, observation in (("green", green), ("refactor", refactor)):
        core = context["stage_results"][stage]
        core["exit_code"] = observation["exit_code"]
        core["observed_at"] = observation["observed_at"]
        if stage == "refactor":
            core["command_ids"] = [item["id"] for item in commands["refactor"]]
            core["command_id"] = commands["refactor"][0]["id"]
    bundle = None
    if red_mode == "legacy-regression":
        (run_dir / "legacy-regression-evidence.json").write_text(json.dumps({
            "schema_version": "quick-dev-tdd-adapter.legacy-regression-evidence.v1",
            "plan_id": context["plan_id"], "slice_id": args.slice_id, "run_id": run_dir.name,
            "prior_red_evidence": predecessor,
            "red_exit_code": red["exit_code"], "green_exit_code": green["exit_code"],
            "refactor_exit_code": refactor["exit_code"], "authorizes": [],
        }, indent=2) + "\n", encoding="utf-8", newline="\n")
    elif red_mode == "prior-red-successor":
        prior_basis = _prior_red_basis(workspace, prior_red)
        if prior_basis is None:
            raise RuntimeError("prior RED successor requires a readable predecessor basis")
        red_basis, predecessor_run = prior_basis
        (run_dir / "prior-red-handoff.v2.json").write_text(json.dumps({
            "schema_version": "quick-dev-tdd-adapter.prior-red-handoff.v2",
            "plan_id": context["plan_id"], "slice_id": args.slice_id, "run_id": run_dir.name,
            "red_observation": prior_red,
            "red_basis": red_basis,
            "execution_fingerprint": context["stage_results"]["red"]["execution_fingerprint"],
            "test_selector": context["stage_results"]["red"]["test_selector"],
            "test_sha256": context["stage_results"]["red"]["test_sha256"],
            "expected_failure_ids": context["stage_results"]["red"]["expected_failure_ids"],
            "validator_hash": context["stage_results"]["red"]["validator_hash"],
            "pre_implementation_candidate": context["stage_results"]["red"]["pre_implementation_candidate"],
            "predecessor_run": predecessor_run,
            "red_command_id": commands["red"][0]["id"],
            "green_command_id": commands["green"][0]["id"],
            "refactor_command_ids": [item["id"] for item in commands["refactor"]],
            "current_contract_hash": context["stage_results"]["red"]["contract_hash"],
            "green_exit_code": green["exit_code"], "refactor_exit_code": refactor["exit_code"],
            "authorizes": [],
        }, indent=2) + "\n", encoding="utf-8", newline="\n")
    elif args.stage == "all":
        bundle = lifecycle.close(context, {})

    if args.stage == "refactor":
        (run_dir / "stage-state.json").write_text(json.dumps({"stage": "refactor", "next_stage": "slice-terminal", "authorizes": []}, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"run_id": run_dir.name, "stage": "refactor", "next_stage": "slice-terminal", "authorizes": []}, sort_keys=True))
        return 0

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
    predicate_result["execution_fingerprint"] = context["stage_results"]["red"]["execution_fingerprint"]
    (run_dir / f"{predicate_result['predicate']}-result.json").write_text(
        json.dumps(predicate_result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    if predicate_result["predicate"] == "implementation-candidate":
        (run_dir / "candidate-result.json").write_text(
            json.dumps(predicate_result, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    state = run_dir.parents[1] / "run-state.v1.json"
    state.write_text(json.dumps({"schema_version": "jimuyun.tdd-adapter-run-state.v1", "last_slice_id": args.slice_id, "last_observed_predicate": "slice-ready", "next_action": "route", "failure_fingerprint": None, "repeat_count": 0, "authorizes": [], "does_not_authorize": ["implementation-accepted", "commit", "release"]}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"run_id": run_dir.name, "stages": ["red", "green", "refactor"], "bundle_schema": bundle["schema_version"] if bundle else None, "evidence_mode": red_mode, "terminal_exit": 0, "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

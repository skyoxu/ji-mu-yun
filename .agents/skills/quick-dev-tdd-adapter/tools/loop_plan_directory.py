from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from route_plan_directory import route


TOOLS = Path(__file__).resolve().parent
HELPER_TIMEOUT_SECONDS = 900
LIFECYCLE_TIMEOUT_OVERHEAD_SECONDS = 60


def _terminal_contract(plan: Path) -> dict[str, str]:
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    value = contract.get("terminal")
    if (
        not isinstance(value, dict)
        or set(value) != {"command_id", "runner", "predicate"}
        or value.get("predicate") != "implementation-complete"
        or not isinstance(value.get("runner"), str)
        or not value["runner"]
        or Path(value["runner"]).is_absolute()
        or ".." in Path(value["runner"]).parts
    ):
        raise ValueError("terminal contract is missing or invalid")
    runner = (plan / value["runner"]).resolve()
    try:
        runner.relative_to(plan.resolve())
    except ValueError as exc:
        raise ValueError("terminal contract runner escapes plan") from exc
    if not runner.is_file():
        raise ValueError("terminal contract runner is missing")
    return value


def _run_terminal(root: Path, plan: Path) -> None:
    terminal = _terminal_contract(plan)
    run_id = datetime.now(timezone.utc).strftime("RUN-%Y%m%dT%H%M%S-%fZ")
    output = root / "logs" / "tdd-adapter" / json.loads(
        (plan / "implementation-contract.v1.json").read_text(encoding="utf-8")
    )["plan_id"] / "terminal" / run_id / "implementation-complete-result.json"
    output.parent.mkdir(parents=True, exist_ok=False)
    runner = (plan / terminal["runner"]).resolve()
    _run([
        str(runner), "--repository-root", str(root), "--plan-dir", str(plan),
        "--out", str(output),
    ], timeout_seconds=7200)


def _run(arguments: list[str], *, timeout_seconds: int = HELPER_TIMEOUT_SECONDS) -> None:
    print(json.dumps({"event": "helper-start", "helper": Path(arguments[0]).name}), flush=True)
    completed = subprocess.run([sys.executable, *arguments], shell=False, check=False, timeout=timeout_seconds)
    print(json.dumps({"event": "helper-finished", "helper": Path(arguments[0]).name, "exit_code": completed.returncode}), flush=True)
    if completed.returncode:
        raise RuntimeError(f"lifecycle helper failed with exit code {completed.returncode}")


def run_red_only(workspace: Path, command: dict[str, object]) -> subprocess.CompletedProcess[str]:
    """Observe one shell-free RED command without advancing to GREEN or REFACTOR."""
    required = {"id", "executable", "argv", "cwd", "timeout_seconds", "shell"}
    if (
        set(command) != required
        or command.get("shell") is not False
        or command.get("cwd") != "."
        or not isinstance(command.get("executable"), str)
        or not isinstance(command.get("argv"), list)
        or any(not isinstance(item, str) for item in command["argv"])
        or not isinstance(command.get("timeout_seconds"), int)
        or command["timeout_seconds"] <= 0
    ):
        raise ValueError("RED command must be a structured shell-free descriptor")
    completed = subprocess.run(
        [command["executable"], *command["argv"]],
        cwd=workspace,
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=command["timeout_seconds"],
    )
    if completed.returncode == 0:
        raise RuntimeError("RED command unexpectedly passed")
    return completed


def build_red_basis(
    command: dict[str, object],
    failure_intent: dict[str, object],
    pre_implementation_candidate: dict[str, object],
    validator_hash: str,
    contract_hash: str,
) -> dict[str, object]:
    """Build the non-authorizing identity that a RED observation must bind."""
    required = {"id", "executable", "argv", "cwd", "timeout_seconds", "shell"}
    if not isinstance(command, dict) or set(command) != required or command.get("shell") is not False:
        raise ValueError("RED command is not a structured shell-free descriptor")
    selector = failure_intent.get("test_selector")
    expected = failure_intent.get("expected_failure_ids")
    if not isinstance(selector, str) or not selector or not isinstance(expected, list) or not expected or not all(isinstance(item, str) and item for item in expected):
        raise ValueError("RED failure intent is invalid")
    if not isinstance(pre_implementation_candidate, dict) or not pre_implementation_candidate:
        raise ValueError("pre-implementation candidate identity is missing")
    if not isinstance(validator_hash, str) or not validator_hash or not isinstance(contract_hash, str) or not contract_hash:
        raise ValueError("RED identity hashes are invalid")
    return {
        "failure_intent": {"command_id": command["id"], "test_selector": selector, "expected_failure_ids": list(expected)},
        "test_selector": selector,
        "contract_hash": contract_hash,
        "validator_hash": validator_hash,
        "pre_implementation_candidate": dict(pre_implementation_candidate),
    }


def staged_cutover_guard(repository_root: Path, plan_dir: Path) -> bool:
    """Read-only predicate for the staged adapter cutover boundary."""
    tools = Path(__file__).resolve().parent
    required = (tools / "stage_lifecycle_runner.py", tools / "run_slice_lifecycle.py")
    root = repository_root.resolve()
    target = (root / plan_dir).resolve() if not plan_dir.is_absolute() else plan_dir.resolve()
    try:
        target.relative_to(root / "execution-plans")
    except ValueError:
        return False
    return all(path.is_file() for path in required) and (target / "implementation-contract.v1.json").is_file()


def _lifecycle_timeout_seconds(invocation: Path) -> int:
    descriptors: list[dict[str, object]] = []
    for name in ("preparation-commands.json", "refactor-commands.json"):
        document = json.loads((invocation / name).read_text(encoding="utf-8"))
        if not isinstance(document, list):
            raise ValueError(f"{name} must contain a command list")
        descriptors.extend(document)
    for name in ("red-command.json", "green-command.json", "terminal-command.json"):
        document = json.loads((invocation / name).read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError(f"{name} must contain one command descriptor")
        descriptors.append(document)
    timeouts = [item.get("timeout_seconds") for item in descriptors]
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in timeouts):
        raise ValueError("every lifecycle command must declare a positive integer timeout")
    return sum(timeouts) + LIFECYCLE_TIMEOUT_OVERHEAD_SECONDS


def _workspace_snapshot_paths(root: Path, plan: Path, snapshots: list[str]) -> list[str]:
    """Resolve declared plan-local snapshots without widening the caller's set."""
    plan_relative = plan.relative_to(root).as_posix()
    resolved: list[str] = []
    for raw in snapshots:
        if not isinstance(raw, str) or not raw:
            raise ValueError("snapshot path is invalid")
        if (root / raw).is_file():
            resolved.append(raw.replace("\\", "/"))
        elif (plan / raw).is_file():
            resolved.append(f"{plan_relative}/{raw.replace('\\', '/')}")
        else:
            raise ValueError(f"declared snapshot path is missing: {raw}")
    return resolved


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _current_bridge_handoff(root: Path, plan: Path, contract: dict[str, object], slice_id: str) -> dict[str, str] | None:
    """Return one current bridge RED handoff or reject stale bridge evidence."""
    selected = next((item for item in contract.get("slices", []) if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict) or not isinstance(selected.get("tdd"), dict):
        raise ValueError("bridge slice declaration is invalid")
    red = selected["tdd"].get("red")
    if not isinstance(red, dict):
        raise ValueError("bridge RED declaration is invalid")
    evidence_root = root / "logs" / "tdd-adapter" / str(contract["plan_id"]) / slice_id
    artifacts = sorted(evidence_root.glob("*/implementation-needed-result.json")) if evidence_root.is_dir() else []
    if not artifacts:
        return None
    contract_hash = _sha(plan / "implementation-contract.v1.json")
    valid: list[Path] = []
    stale = False
    for artifact in artifacts:
        try:
            handoff = json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("migration RED handoff is unreadable") from exc
        selector = handoff.get("test_selector")
        test_path = (root / selector).resolve() if isinstance(selector, str) else None
        expected = {
            "schema_version": "quick-dev-tdd-adapter.red-handoff.v1",
            "plan_id": contract["plan_id"],
            "slice_id": slice_id,
            "predicate": "implementation-needed",
            "status": "pass",
            "contract_hash": contract_hash,
            "test_selector": red.get("test_selector"),
            "expected_failure_ids": red.get("expected_failure_ids"),
            "stage": "red",
            "commands_attempted": [f"quick-dev-generated-red-{slice_id}"],
        }
        if (
            any(handoff.get(key) != value for key, value in expected.items())
            or not isinstance(handoff.get("exit_code"), int)
            or handoff["exit_code"] == 0
            or test_path is None
            or not test_path.is_file()
            or handoff.get("test_hash") != _sha(test_path)
        ):
            stale = True
            continue
        valid.append(artifact)
    if len(valid) != 1:
        if valid:
            raise ValueError("migration RED handoff is ambiguous")
        if stale:
            return None
        raise ValueError("migration RED handoff is invalid")
    artifact = valid[0]
    return {"path": artifact.relative_to(root).as_posix(), "sha256": _sha(artifact)}


def _active_slice_run(root: Path, plan_id: str, slice_id: str) -> tuple[Path, str] | None:
    evidence_root = root / "logs" / "tdd-adapter" / plan_id / slice_id
    candidates = sorted((path for path in evidence_root.glob("RUN-*") if path.is_dir()), key=lambda path: path.name, reverse=True)
    for run_dir in candidates:
        if not (run_dir / "stage-state.json").is_file():
            continue
        try:
            state = json.loads((run_dir / "stage-state.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if state.get("stage") == "refactor" and (run_dir / "slice-ready-result.json").is_file():
            continue
        if state.get("stage") == "refactor" and (run_dir / "observations" / "refactor-observed.json").is_file():
            return run_dir, "slice-terminal"
        if (run_dir / "observations" / "green-observed.json").is_file():
            return run_dir, "refactor"
        if (run_dir / "observations" / "red-observed.json").is_file() and (run_dir / "red-basis.v1.json").is_file():
            return run_dir, "green"
    return None


def _run_slice(root: Path, plan: Path, slice_id: str, snapshots: list[str]) -> None:
    snapshots = _workspace_snapshot_paths(root, plan, snapshots)
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    bridge = contract.get("adapter_bridge")
    active = _active_slice_run(root, str(contract["plan_id"]), slice_id)
    stage = active[1] if active else "red"
    if stage == "slice-terminal":
        raise RuntimeError("slice terminal must be routed as validate-slice")
    handoff = _current_bridge_handoff(root, plan, contract, slice_id) if stage == "red" and contract.get("plan_id") != "quick-dev-tdd-stage-recovery" else None
    if stage == "red" and isinstance(bridge, dict) and isinstance(bridge.get("runner"), str) and handoff is None:
        runner = plan / bridge["runner"]
        if not runner.is_file():
            raise ValueError("declared plan-local adapter bridge is missing")
        _run([str(runner), "--repository-root", str(root), "--plan-dir", str(plan), "--slice-id", slice_id, "--snapshot-path", *snapshots, "--materialize-only"])
    run_id = active[0].name if active else datetime.now(timezone.utc).strftime("RUN-%Y%m%dT%H%M%S-%fZ")
    invocation_id = datetime.now(timezone.utc).strftime("RUN-%Y%m%dT%H%M%S-%fZ")
    evidence = root / "logs" / "tdd-adapter" / contract["plan_id"]
    run_dir = evidence / slice_id / run_id
    invocation = evidence / "_invocations" / invocation_id
    _run([str(TOOLS / "build_slice_invocation.py"), "--repository-root", str(root), "--plan-dir", str(plan), "--slice-id", slice_id, "--run-id", invocation_id, "--out-dir", str(invocation)])
    if handoff is not None:
        context_path = invocation / "run-context.json"
        context = json.loads(context_path.read_text(encoding="utf-8"))
        red = context["stage_results"]["red"]
        red["mode"] = "prior-red-successor"
        red["prior_red"] = handoff
        red["legacy_predecessor"] = None
        context_path.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8", newline="\n")
    commands = [
        "--command", f"red={invocation / 'red-command.json'}",
        "--command", f"green={invocation / 'green-command.json'}",
    ]
    for index in range(len(json.loads((invocation / "refactor-commands.json").read_text(encoding="utf-8")))):
        # Materialize each descriptor separately to keep the lifecycle interface typed.
        command_path = invocation / f"refactor-command-{index}.json"
        commands_document = json.loads((invocation / "refactor-commands.json").read_text(encoding="utf-8"))
        command_path.write_text(json.dumps(commands_document[index], indent=2) + "\n", encoding="utf-8", newline="\n")
        commands.extend(["--command", f"refactor={command_path}"])
    invocation_args = [str(TOOLS / "run_slice_lifecycle.py"), "--workspace", str(root), "--plan-dir", str(plan), "--run-dir", str(run_dir), "--slice-id", slice_id, "--run-context", str(invocation / "run-context.json"), "--terminal-command", str(invocation / "terminal-command.json")]
    if handoff is None:
        invocation_args.extend(["--stage", stage])
    for index, command in enumerate(json.loads((invocation / "preparation-commands.json").read_text(encoding="utf-8"))):
        command_path = invocation / f"preparation-command-{index}.json"
        command_path.write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8", newline="\n")
        invocation_args.extend(["--prepare-command", str(command_path)])
    for snapshot in snapshots:
        invocation_args.extend(["--snapshot-path", snapshot])
    _run([*invocation_args, *commands], timeout_seconds=_lifecycle_timeout_seconds(invocation))


def _run_slice_terminal(root: Path, plan: Path, slice_id: str, snapshots: list[str]) -> None:
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    active = _active_slice_run(root, str(contract["plan_id"]), slice_id)
    if active is None or active[1] != "slice-terminal":
        raise RuntimeError("slice terminal requires a completed refactor observation")
    run_dir = active[0]
    run_id = datetime.now(timezone.utc).strftime("RUN-%Y%m%dT%H%M%S-%fZ")
    invocation = root / "logs" / "tdd-adapter" / str(contract["plan_id"]) / "_invocations" / run_id
    _run([str(TOOLS / "build_slice_invocation.py"), "--repository-root", str(root), "--plan-dir", str(plan), "--slice-id", slice_id, "--run-id", run_id, "--out-dir", str(invocation)])
    command = json.loads((invocation / "terminal-command.json").read_text(encoding="utf-8"))
    completed = subprocess.run([command["executable"], *command["argv"]], cwd=root, shell=False, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=command["timeout_seconds"])
    if completed.returncode != 0:
        raise RuntimeError("slice terminal predicate failed")
    result = json.loads(completed.stdout)
    if result.get("status") != "pass" or result.get("predicate") != "slice-ready":
        raise RuntimeError("slice terminal predicate did not pass")
    (run_dir / "slice-ready-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--snapshot-path", action="append", required=True)
    parser.add_argument("--max-actions", type=int, default=1)
    args = parser.parse_args()
    root, plan = args.repository_root.resolve(), args.plan_dir.resolve()
    if args.max_actions < 1:
        raise ValueError("max actions must be positive")
    actions: list[dict[str, object]] = []
    for _ in range(args.max_actions):
        result = route(root, plan)
        result["authorizes"] = []
        actions.append(result)
        if result["next_action"] == "validate-terminal":
            _run_terminal(root, plan)
            continue
        if result["next_action"] == "validate-slice":
            _run_slice_terminal(root, plan, str(result["slice_id"]), args.snapshot_path)
            continue
        if result["next_action"] != "run-slice":
            break
        _run_slice(root, plan, str(result["slice_id"]), args.snapshot_path)
    print(json.dumps({"actions": actions, "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

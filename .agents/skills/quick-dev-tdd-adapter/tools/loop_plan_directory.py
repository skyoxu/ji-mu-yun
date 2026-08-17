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


def staged_cutover_guard(repository_root: Path, plan_dir: Path) -> bool:
    """Read-only predicate for the staged adapter cutover boundary."""
    tools = Path(__file__).resolve().parent
    required = (tools / "stage_lifecycle_runner.py", tools / "run_slice_lifecycle.py")
    return all(path.is_file() for path in required) and (plan_dir / "implementation-contract.v1.json").is_file()


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


def _run_slice(root: Path, plan: Path, slice_id: str, snapshots: list[str]) -> None:
    snapshots = _workspace_snapshot_paths(root, plan, snapshots)
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    bridge = contract.get("adapter_bridge")
    handoff = None
    if isinstance(bridge, dict) and isinstance(bridge.get("runner"), str):
        handoff = _current_bridge_handoff(root, plan, contract, slice_id)
        if handoff is None:
            runner = plan / bridge["runner"]
            if not runner.is_file():
                raise ValueError("declared plan-local adapter bridge is missing")
            _run([str(runner), "--repository-root", str(root), "--plan-dir", str(plan), "--slice-id", slice_id, "--snapshot-path", *snapshots])
            return
    run_id = datetime.now(timezone.utc).strftime("RUN-%Y%m%dT%H%M%S-%fZ")
    evidence = root / "logs" / "tdd-adapter" / contract["plan_id"]
    run_dir = evidence / slice_id / run_id
    invocation = evidence / "_invocations" / run_id
    _run([str(TOOLS / "build_slice_invocation.py"), "--repository-root", str(root), "--plan-dir", str(plan), "--slice-id", slice_id, "--run-id", run_id, "--out-dir", str(invocation)])
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
    for index, command in enumerate(json.loads((invocation / "preparation-commands.json").read_text(encoding="utf-8"))):
        command_path = invocation / f"preparation-command-{index}.json"
        command_path.write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8", newline="\n")
        invocation_args.extend(["--prepare-command", str(command_path)])
    for snapshot in snapshots:
        invocation_args.extend(["--snapshot-path", snapshot])
    _run([*invocation_args, *commands], timeout_seconds=_lifecycle_timeout_seconds(invocation))


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
        if result["next_action"] != "run-slice":
            break
        _run_slice(root, plan, str(result["slice_id"]), args.snapshot_path)
    print(json.dumps({"actions": actions, "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

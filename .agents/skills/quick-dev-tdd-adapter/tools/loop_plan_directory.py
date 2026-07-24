from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from route_plan_directory import route


TOOLS = Path(__file__).resolve().parent


def _run(arguments: list[str]) -> None:
    print(json.dumps({"event": "helper-start", "helper": Path(arguments[0]).name}), flush=True)
    completed = subprocess.run([sys.executable, *arguments], shell=False, check=False, timeout=900)
    print(json.dumps({"event": "helper-finished", "helper": Path(arguments[0]).name, "exit_code": completed.returncode}), flush=True)
    if completed.returncode:
        raise RuntimeError(f"lifecycle helper failed with exit code {completed.returncode}")


def _run_slice(root: Path, plan: Path, slice_id: str, snapshots: list[str]) -> None:
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    run_id = datetime.now(timezone.utc).strftime("RUN-%Y%m%dT%H%M%S-%fZ")
    evidence = root / "logs" / "tdd-adapter" / contract["plan_id"]
    run_dir = evidence / slice_id / run_id
    invocation = evidence / "_invocations" / run_id
    _run([str(TOOLS / "build_slice_invocation.py"), "--repository-root", str(root), "--plan-dir", str(plan), "--slice-id", slice_id, "--run-id", run_id, "--out-dir", str(invocation)])
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
    _run([*invocation_args, *commands])


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
        if result["next_action"] != "run-slice":
            break
        _run_slice(root, plan, str(result["slice_id"]), args.snapshot_path)
    print(json.dumps({"actions": actions, "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

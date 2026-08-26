from __future__ import annotations
import argparse, json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

TOOLS = Path(__file__).parent

def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")

def _snapshot_paths(plan: Path, slice_id: str) -> list[str]:
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    item = next((value for value in contract["slices"] if value.get("slice_id") == slice_id), None)
    if not isinstance(item, dict): raise ValueError("routed slice is absent from contract")
    paths = item.get("execution_snapshot_paths")
    if not isinstance(paths, list) or not paths or not all(isinstance(path, str) for path in paths):
        raise ValueError("slice has no declared execution snapshot path")
    normalized = [path.replace("\\", "/") for path in paths]
    if any(any(token in path for token in ("*", "?", "[", "]")) for path in normalized):
        raise ValueError("execution snapshot path cannot contain a wildcard")
    return normalized


def _snapshot(plan: Path, slice_id: str) -> str:
    """Legacy single-snapshot view retained for v1 callers."""
    values = _snapshot_paths(plan, slice_id)
    if len(values) != 1:
        raise ValueError("legacy snapshot view cannot represent multiple paths")
    return values[0]

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--poll-seconds", type=int, default=15)
    args = parser.parse_args(); root, plan = args.repository_root.resolve(), args.plan_dir.resolve()
    while True:
        routed = json.loads(subprocess.check_output([
            sys.executable, str(TOOLS / "route_plan_directory.py"),
            "--repository-root", str(root), "--plan-dir", str(plan),
            "--caller", "quick-dev-tdd-adapter",
        ], text=True))
        action = routed["next_action"]
        _write(args.state_file, {"observed_at": datetime.now(timezone.utc).isoformat(), "action": action, "slice_id": routed.get("slice_id"), "authorizes": []})
        if action in {"awaiting-implementation-authorization", "external-repair-required", "implement", "stop", "implementation-complete"}:
            return 0
        if action in {"run-slice", "validate-slice", "validate-terminal", "refresh-knowledge-context"}:
            snapshots = _snapshot_paths(plan, str(routed["slice_id"])) if routed.get("slice_id") else []
            command = [sys.executable, str(TOOLS / "loop_plan_directory.py"), "--repository-root", str(root), "--plan-dir", str(plan), "--max-actions", "1"]
            for snapshot in snapshots:
                command.extend(["--snapshot-path", snapshot])
            completed = subprocess.run(command, cwd=root)
        else:
            return 0
        if completed.returncode: return completed.returncode
        time.sleep(args.poll_seconds)

if __name__ == "__main__": raise SystemExit(main())

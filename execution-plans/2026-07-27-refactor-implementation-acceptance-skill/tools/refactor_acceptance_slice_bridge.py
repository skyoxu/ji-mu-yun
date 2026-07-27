"""Run one 7-27 slice in separate RED and completion phases."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]
PLAN_ID = "refactor-implementation-acceptance-skill"
ADAPTER_TOOLS = REPOSITORY_ROOT / ".agents/skills/quick-dev-tdd-adapter/tools"
sys.path.insert(0, str(ADAPTER_TOOLS))
from stage_observation_runner import record_observation, run  # noqa: E402


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, PLAN_ROOT / "tools" / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("plan helper is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _contract() -> dict:
    return json.loads((PLAN_ROOT / "implementation-contract.v1.json").read_text(encoding="utf-8"))


def _slice(slice_id: str) -> dict:
    for item in _contract()["slices"]:
        if item.get("slice_id") == slice_id:
            return item
    raise ValueError("unknown slice")


def _commands() -> dict[str, dict]:
    values = json.loads((PLAN_ROOT / "command-registry.v1.json").read_text(encoding="utf-8"))
    return {item["id"]: {"id": item["id"], "executable": item["executable"], "argv": item["argv"], "cwd": ".", "timeout_seconds": item["timeout_seconds"], "shell": False} for item in values["commands"]}


def _command_ids(slice_id: str) -> tuple[str, str, str]:
    if slice_id == "RMAP-S0":
        return "s0-companion-red", "s0-companion-suite", "bootstrap-regression-suite"
    if slice_id == "RMAP-S1":
        return "s1-core-red", "s1-core-suite", "s1-core-suite"
    if slice_id == "RMAP-S2":
        return "s2-matrix-red", "s2-matrix-suite", "s2-matrix-suite"
    if slice_id == "RMAP-S3":
        return "s3-control-red", "s3-control-suite", "s3-control-suite"
    if slice_id == "RMAP-S4":
        return "s4-bootstrap-red", "s4-bootstrap-suite", "s4-bootstrap-suite"
    if slice_id == "RMAP-S5":
        return "s5-package-red", "s5-package-suite", "s5-package-suite"
    return "plan-validator", "plan-validator", "plan-validator"


def _run_dir(slice_id: str, run_id: str) -> Path:
    return REPOSITORY_ROOT / "logs/tdd-adapter" / PLAN_ID / slice_id / run_id


def _session(run_id: str) -> Path:
    return REPOSITORY_ROOT / "logs/tdd-adapter" / PLAN_ID / "_bridge-sessions" / f"{run_id}.json"


def _write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError("append-only evidence already exists")
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def _result(slice_id: str, run_id: str) -> dict:
    snapshot = _load("validate_all").slice_validation_snapshot(slice_id)
    return {"schema_version": "ria.slice-result.v1", "plan_id": PLAN_ID, "slice_id": slice_id, "run_id": run_id, "predicate": "slice-ready", "status": "pass", "contract_hash": _sha(PLAN_ROOT / "implementation-contract.v1.json"), **snapshot, "authorizes": []}


def start_red(slice_id: str, snapshots: list[str]) -> int:
    selected = _slice(slice_id)
    if snapshots != selected["execution_snapshot_paths"]:
        raise ValueError("snapshot paths must exactly match the slice contract")
    run_id = "RUN-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-%fZ")
    commands = _commands()
    red_id, _, _ = _command_ids(slice_id)
    observation = run(REPOSITORY_ROOT, "red", commands[red_id], snapshots, "Recorded declared RED observation.")
    if observation["exit_code"] == 0:
        raise RuntimeError("RED command unexpectedly passed")
    run_dir = _run_dir(slice_id, run_id)
    record_observation(run_dir, observation)
    _write_new(_session(run_id), {"schema_version": "ria.tdd-bridge-session.v1", "plan_id": PLAN_ID, "slice_id": slice_id, "run_id": run_id, "snapshot_paths": snapshots, "contract_hash": _sha(PLAN_ROOT / "implementation-contract.v1.json"), "authorizes": []})
    print(json.dumps({"run_id": run_id, "next_action": "perform-green-write", "authorizes": []}))
    return 0


def complete(slice_id: str, run_id: str) -> int:
    session = json.loads(_session(run_id).read_text(encoding="utf-8"))
    if session.get("slice_id") != slice_id or session.get("contract_hash") != _sha(PLAN_ROOT / "implementation-contract.v1.json"):
        raise RuntimeError("session is stale or has the wrong slice")
    selected = _slice(slice_id)
    if session["snapshot_paths"] != selected["execution_snapshot_paths"]:
        raise RuntimeError("snapshot paths are stale")
    run_dir = _run_dir(slice_id, run_id)
    red_path = run_dir / "observations/red-observed.json"
    if not red_path.is_file():
        raise RuntimeError("RED observation is missing")
    red = json.loads(red_path.read_text(encoding="utf-8"))
    commands = _commands()
    _, green_id, refactor_id = _command_ids(slice_id)
    green_path = run_dir / "observations/green-observed.json"
    if green_path.is_file():
        green = json.loads(green_path.read_text(encoding="utf-8"))
    else:
        before = {entry["path"]: entry["after_bytes_base64"] for entry in red["changed_files"]}
        green = run(REPOSITORY_ROOT, "green", commands[green_id], session["snapshot_paths"], "Recorded GREEN command observation.", before_snapshots=before)
        if green["exit_code"] != 0:
            raise RuntimeError("GREEN command failed")
        record_observation(run_dir, green)
    if green["exit_code"] != 0:
        raise RuntimeError("saved GREEN command failed")
    before = {entry["path"]: entry["after_bytes_base64"] for entry in green["changed_files"]}
    refactor_path = run_dir / "observations/refactor-observed.json"
    if refactor_path.is_file():
        refactor = json.loads(refactor_path.read_text(encoding="utf-8"))
    else:
        refactor = run(REPOSITORY_ROOT, "refactor", commands[refactor_id], session["snapshot_paths"], "Recorded REFACTOR command observation.", before_snapshots=before)
        if refactor["exit_code"] != 0:
            raise RuntimeError("REFACTOR command failed")
        record_observation(run_dir, refactor)
    if refactor["exit_code"] != 0:
        raise RuntimeError("saved REFACTOR command failed")
    predicate_check = subprocess.run(
        [sys.executable, "-B", str(PLAN_ROOT / "tools" / "validate_slice.py"), "--slice-id", slice_id],
        cwd=REPOSITORY_ROOT, shell=False, check=False, capture_output=True, timeout=120,
    )
    if predicate_check.returncode != 0:
        raise RuntimeError("plan-local slice predicate failed")
    predicate = _result(slice_id, run_id)
    _write_new(run_dir / "slice-ready-result.json", predicate)
    _write_new(run_dir / "recovery-state.json", {"schema_version": "ria.recovery-state.v1", "run_id": run_id, "slice_id": slice_id, "state": "completed", "contract_hash": predicate["contract_hash"], "validator_hash": predicate["validator_root"], "authorizes": []})
    print(json.dumps(predicate, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--snapshot-path", action="append", required=True)
    parser.add_argument("--stage", choices=("red", "complete"), default="red")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.repository_root.resolve() != REPOSITORY_ROOT or args.plan_dir.resolve() != PLAN_ROOT:
        raise ValueError("bridge must use its owning repository and plan directory")
    if args.stage == "red":
        if args.run_id:
            raise ValueError("RED creates its own run id")
        return start_red(args.slice_id, args.snapshot_path)
    if not args.run_id:
        raise ValueError("complete requires --run-id")
    return complete(args.slice_id, args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())

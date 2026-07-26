"""Run one Knowledge Locator workflow slice in explicit RED and completion phases."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]
ADAPTER_TOOLS = REPOSITORY_ROOT / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools"
PLAN_ID = "knowledge-locator-workflow-integration"

if str(ADAPTER_TOOLS) not in sys.path:
    sys.path.insert(0, str(ADAPTER_TOOLS))

from stage_artifact_composer import compose  # noqa: E402
from stage_observation_runner import record_observation, run  # noqa: E402
from adapter import persist_protocol_bundle  # noqa: E402


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _paths_for_slice(slice_id: str) -> list[str]:
    contract = json.loads((PLAN_ROOT / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = next((item for item in contract["slices"] if item["slice_id"] == slice_id), None)
    if not isinstance(selected, dict):
        raise ValueError("unknown slice")
    paths = selected.get("execution_snapshot_paths")
    if not isinstance(paths, list) or not paths or any(not isinstance(item, str) for item in paths):
        raise ValueError("slice snapshots are invalid")
    return paths


def _build(slice_id: str, run_id: str) -> dict[str, Any]:
    builder = _load(ADAPTER_TOOLS / "build_slice_invocation.py", "knowledge_workflow_invocation")
    return builder.build(REPOSITORY_ROOT, PLAN_ROOT, slice_id, run_id)


def _run_directory(slice_id: str, run_id: str) -> Path:
    return REPOSITORY_ROOT / "logs" / "tdd-adapter" / PLAN_ID / slice_id / run_id


def _session_path(run_id: str) -> Path:
    return REPOSITORY_ROOT / "logs" / "tdd-adapter" / PLAN_ID / "_bridge-sessions" / f"{run_id}.json"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError(f"append-only evidence already exists: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _decode_context(value: dict[str, Any]) -> dict[str, Any]:
    context = json.loads(json.dumps(value))
    for item in [*context["authority_refs"], context["implementation_contract"]]:
        item["payload"] = base64.b64decode(item.pop("payload_base64"), validate=True)
    return context


def _after_snapshots(observation: dict[str, Any]) -> dict[str, str | None]:
    return {
        item["path"]: item["after_bytes_base64"]
        for item in observation["changed_files"]
    }


def _run_plain(command: dict[str, Any]) -> int:
    completed = subprocess.run(
        [command["executable"], *command["argv"]],
        cwd=REPOSITORY_ROOT / command["cwd"],
        shell=False,
        check=False,
        timeout=command["timeout_seconds"],
    )
    return completed.returncode


def _snapshot(slice_id: str) -> dict[str, str]:
    validator = _load(PLAN_ROOT / "tools" / "validate_all.py", "knowledge_workflow_validator")
    snapshot = validator.slice_validation_snapshot(slice_id)
    if not isinstance(snapshot, dict) or not all(isinstance(value, str) for value in snapshot.values()):
        raise ValueError("slice validation snapshot is invalid")
    return snapshot


def _result(slice_id: str, run_id: str, predicate: str) -> dict[str, Any]:
    return {
        "schema_version": "kwi.slice-result.v1",
        "plan_id": PLAN_ID,
        "slice_id": slice_id,
        "run_id": run_id,
        "predicate": predicate,
        "status": "pass",
        "contract_hash": _sha((PLAN_ROOT / "implementation-contract.v1.json").read_bytes()),
        **_snapshot(slice_id),
        "authorizes": [],
    }


def _existing_observation(run_dir: Path, stage: str) -> dict[str, Any] | None:
    path = run_dir / "observations" / f"{stage}-observed.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _start_red(slice_id: str, snapshots: list[str]) -> int:
    run_id = "RUN-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-%fZ")
    built = _build(slice_id, run_id)
    run_dir = _run_directory(slice_id, run_id)
    if run_dir.exists():
        raise ValueError("new run directory unexpectedly exists")
    contract = json.loads((PLAN_ROOT / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = next(item for item in contract["slices"] if item["slice_id"] == slice_id)
    legacy_regression = selected["tdd"]["red"].get("mode") == "legacy-regression"
    red = run(
        REPOSITORY_ROOT,
        "red",
        built["red"],
        snapshots,
        "Recorded declared legacy regression observation." if legacy_regression else "Recorded explicit RED command observation.",
    )
    if legacy_regression:
        if red["exit_code"] != 0:
            raise RuntimeError("legacy regression command failed")
    elif red["exit_code"] == 0:
        raise RuntimeError("RED command unexpectedly passed")
    record_observation(run_dir, red)
    session = {
        "schema_version": "kwi.tdd-bridge-session.v1",
        "plan_id": PLAN_ID,
        "slice_id": slice_id,
        "run_id": run_id,
        "snapshot_paths": snapshots,
        "run_context": built["run_context"],
        "red_observation": red,
        "contract_hash": _sha((PLAN_ROOT / "implementation-contract.v1.json").read_bytes()),
        "authorizes": [],
    }
    _write_json(_session_path(run_id), session)
    next_action = "complete-legacy-regression" if legacy_regression else "perform-green-write"
    print(json.dumps({"run_id": run_id, "next_action": next_action, "authorizes": []}))
    return 0


def _complete(slice_id: str, run_id: str) -> int:
    session = json.loads(_session_path(run_id).read_text(encoding="utf-8"))
    if session.get("plan_id") != PLAN_ID or session.get("slice_id") != slice_id:
        raise ValueError("session identity does not match requested slice")
    current_contract = _sha((PLAN_ROOT / "implementation-contract.v1.json").read_bytes())
    if session.get("contract_hash") != current_contract:
        raise RuntimeError("bridge session is stale after contract drift")
    snapshots = session.get("snapshot_paths")
    if snapshots != _paths_for_slice(slice_id):
        raise RuntimeError("bridge session snapshot declaration is stale")
    built = _build(slice_id, run_id)
    run_dir = _run_directory(slice_id, run_id)
    red = session["red_observation"]
    if not (run_dir / "observations" / "red-observed.json").is_file():
        raise RuntimeError("RED observation is missing")

    green = _existing_observation(run_dir, "green")
    if green is None:
        green = run(
            REPOSITORY_ROOT,
            "green",
            built["green"],
            snapshots,
            "Recorded GREEN command observation after explicit RED.",
            before_snapshots=_after_snapshots(red),
        )
        if green["exit_code"] != 0:
            raise RuntimeError("GREEN command failed")
        record_observation(run_dir, green)
    elif green["exit_code"] != 0:
        raise RuntimeError("saved GREEN command failed")

    refactor = _existing_observation(run_dir, "refactor")
    if refactor is None:
        refactors = built["refactor"]
        for command in refactors[:-1]:
            if _run_plain(command) != 0:
                raise RuntimeError("REFACTOR pre-observation command failed")
        refactor = run(
            REPOSITORY_ROOT,
            "refactor",
            refactors[-1],
            snapshots,
            "Recorded REFACTOR command observation.",
            before_snapshots=_after_snapshots(green),
        )
        if refactor["exit_code"] != 0:
            raise RuntimeError("REFACTOR command failed")
        record_observation(run_dir, refactor)
    elif refactor["exit_code"] != 0:
        raise RuntimeError("saved REFACTOR command failed")

    context = _decode_context(session["run_context"])
    contract = json.loads((PLAN_ROOT / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = next(item for item in contract["slices"] if item["slice_id"] == slice_id)
    legacy_regression = selected["tdd"]["red"].get("mode") == "legacy-regression"
    if legacy_regression:
        _write_json(
            run_dir / "legacy-regression-evidence.json",
            {
                "schema_version": "kwi.legacy-regression-evidence.v1",
                "plan_id": PLAN_ID,
                "slice_id": slice_id,
                "run_id": run_id,
                "red_exit_code": red["exit_code"],
                "green_exit_code": green["exit_code"],
                "refactor_exit_code": refactor["exit_code"],
                "authorizes": [],
            },
        )
    else:
        bundle, store, _ = compose(context, [red, green, refactor], {})
        persist_protocol_bundle(run_dir, bundle, store)

    terminal = built["terminal"]
    completed = subprocess.run(
        [terminal["executable"], *terminal["argv"]],
        cwd=REPOSITORY_ROOT / terminal["cwd"],
        shell=False,
        check=False,
        capture_output=True,
        timeout=terminal["timeout_seconds"],
    )
    if completed.returncode != 0:
        raise RuntimeError("plan-local terminal command failed")

    predicate = selected["exit_predicate"]
    result = _result(slice_id, run_id, predicate)
    if legacy_regression:
        result["evidence_mode"] = "legacy-regression"
    _write_json(run_dir / f"{predicate}-result.json", result)
    if predicate == "implementation-candidate":
        _write_json(run_dir / "candidate-evidence.json", result)
    _write_json(
        run_dir / "recovery-state.json",
        {
            "schema_version": "rmap.recovery-state.v1",
            "run_id": run_id,
            "state": "completed",
            "slice_id": slice_id,
            "contract_hash": result["contract_hash"],
            "validator_hash": result["validator_root"],
            "predecessor_run_id": None,
            "supersedes_run_id": None,
            "authorizes": [],
        },
    )
    print(json.dumps({"run_id": run_id, "predicate": predicate, "status": "pass", "authorizes": []}))
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
    snapshots = args.snapshot_path
    if snapshots != _paths_for_slice(args.slice_id):
        raise ValueError("snapshot paths must exactly match the selected slice contract")
    if args.stage == "red":
        if args.run_id is not None:
            raise ValueError("RED creates its own run id")
        return _start_red(args.slice_id, snapshots)
    if not args.run_id:
        raise ValueError("complete requires --run-id")
    return _complete(args.slice_id, args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())

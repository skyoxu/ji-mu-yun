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


PLAN_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_DIR.parents[1]
ADAPTER_TOOLS = REPOSITORY_ROOT / ".agents/skills/quick-dev-tdd-adapter/tools"
if str(ADAPTER_TOOLS) not in sys.path:
    sys.path.insert(0, str(ADAPTER_TOOLS))
if str(PLAN_DIR / "tools") not in sys.path:
    sys.path.insert(0, str(PLAN_DIR / "tools"))

import adapter
import build_slice_invocation
import stage_artifact_composer
import stage_observation_runner

_PROJECTION_SPEC = importlib.util.spec_from_file_location(
    "broh_stage_projection_builder",
    PLAN_DIR / "tools" / "stage_projection_builder.py",
)
if _PROJECTION_SPEC is None or _PROJECTION_SPEC.loader is None:
    raise RuntimeError("plan-local stage projection builder is unavailable")
stage_projection_builder = importlib.util.module_from_spec(_PROJECTION_SPEC)
_PROJECTION_SPEC.loader.exec_module(stage_projection_builder)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def _hash_file(path: Path) -> str:
    if not path.is_file():
        return "sha256:" + hashlib.sha256(b"<missing>").hexdigest()
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _plan_test_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted((PLAN_DIR / "tools" / "tests").glob("test_*.py"), key=lambda item: item.name.casefold()):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _acceptance_test_hash() -> str:
    digest = hashlib.sha256()
    root = REPOSITORY_ROOT / ".agents/skills/run-refactor-implementation-acceptance/tests"
    for path in sorted(root.glob("test_*.py"), key=lambda item: item.name.casefold()):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _protocol_identity() -> dict[str, str]:
    return {
        "contract_hash": _hash_file(PLAN_DIR / "implementation-contract.v1.json"),
        "command_registry_hash": _hash_file(PLAN_DIR / "command-registry.v1.json"),
        "bridge_hash": _hash_file(Path(__file__).resolve()),
        "plan_test_hash": _hash_file(PLAN_DIR / "implementation-contract.v1.json"),
    }


def _persist_protocol_bundle_with_short_drive(run_dir: Path, bundle: dict[str, Any], store: dict[tuple[str, str], bytes]) -> None:
    """Use a temporary subst drive for deep Windows protocol snapshot paths."""
    if sys.platform != "win32":
        adapter.persist_protocol_bundle(run_dir, bundle, store)
        return
    original_run_path = adapter._run_path

    def windows_safe_run_path(root: Path, relative: str) -> Path | None:
        candidate = original_run_path(root, relative)
        if candidate is None:
            return None
        if len(str(candidate)) >= 240:
            return Path("\\\\?\\" + str(candidate))
        return candidate

    adapter._run_path = windows_safe_run_path
    try:
        adapter.persist_protocol_bundle(run_dir, bundle, store)
    finally:
        adapter._run_path = original_run_path


def _validation_module():
    path = PLAN_DIR / "tools" / "validate_all.py"
    spec = importlib.util.spec_from_file_location("broh_bridge_validate_all", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("plan-local validation helper is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _result_is_current(result: dict[str, Any], selected: dict[str, Any], slice_id: str) -> bool:
    validation = _validation_module()
    snapshot = (
        validation.slice_validation_snapshot(slice_id)
        if selected["exit_predicate"] == "slice-ready"
        else validation.validation_snapshot()
    )
    return not (
        result.get("status") != "pass"
        or result.get("predicate") != selected["exit_predicate"]
        or result.get("slice_id") != slice_id
        or result.get("contract_hash") != _hash_file(PLAN_DIR / "implementation-contract.v1.json")
        or any(result.get(key) != value for key, value in snapshot.items())
        or (
            selected["exit_predicate"] == "slice-ready"
            and result.get("predecessor_result_hashes") != validation.predecessor_result_hashes(slice_id)
        )
    )


def _worktree_manifest(root: Path) -> dict[str, str]:
    commands = (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    )
    paths: set[str] = set()
    for command in commands:
        completed = subprocess.run(command, cwd=root, capture_output=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError("git worktree manifest is unavailable")
        paths.update(
            line.replace("\\", "/")
            for line in completed.stdout.decode("utf-8", errors="surrogateescape").splitlines()
            if line
        )
    return {path: _hash_file(root / path) for path in sorted(paths, key=str.casefold)}


def _changed_since(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {path for path in set(before) | set(after) if before.get(path) != after.get(path)}


def _assert_manifest_delta(
    before: dict[str, str],
    after: dict[str, str],
    allowed: set[str],
    label: str,
) -> set[str]:
    """Reject command-side effects outside the stage's exact write class."""
    changed = _changed_since(before, after)
    if not changed.issubset(allowed):
        escaped = ", ".join(sorted(changed - allowed, key=str.casefold))
        raise RuntimeError(f"{label} changed undeclared worktree paths: {escaped}")
    return changed


def _validate_red_changes(changed: set[str], write_set: dict[str, set[str]]) -> None:
    if not changed or not changed.issubset(write_set["tests"]):
        raise RuntimeError("RED preparation must change only declared tests")


def _validate_green_changes(changed: set[str], write_set: dict[str, set[str]]) -> None:
    if not changed or not changed.issubset(write_set["production"]) or not changed.intersection(write_set["production"]):
        raise RuntimeError("GREEN must change at least one declared production path and no other path")


def _validate_refactor_changes(changed: set[str], write_set: dict[str, set[str]]) -> None:
    if not changed.issubset(set().union(*write_set.values())):
        raise RuntimeError("REFACTOR changes escaped the declared write set")


def _selected(contract: dict[str, Any], slice_id: str) -> dict[str, Any]:
    selected = next((item for item in contract.get("slices", []) if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict):
        raise ValueError(f"unknown slice: {slice_id}")
    return selected


def _write_set(selected: dict[str, Any]) -> dict[str, set[str]]:
    groups = selected.get("allowed_changes")
    if not isinstance(groups, dict):
        raise ValueError("slice write set is invalid")
    result: dict[str, set[str]] = {}
    for name in ("production", "tests", "documentation"):
        values = groups.get(name)
        if not isinstance(values, list) or any(not isinstance(value, str) or any(token in value for token in "*?[]") for value in values):
            raise ValueError("single-maintainer bridge requires exact write paths")
        result[name] = {value.replace("\\", "/") for value in values}
    return result


def _planned_new_files(selected: dict[str, Any], write_set: dict[str, set[str]]) -> set[str]:
    values = selected.get("planned_new_files")
    allowed = set().union(*write_set.values())
    if (
        not isinstance(values, list)
        or any(not isinstance(value, str) or any(token in value for token in "*?[]") for value in values)
        or len(values) != len(set(values))
        or not set(values).issubset(allowed)
    ):
        raise ValueError("planned new file declaration is invalid")
    return {value.replace("\\", "/") for value in values}


def _require_materialized(paths: set[str], stage: str) -> None:
    missing = sorted(path for path in paths if not (REPOSITORY_ROOT / path).is_file())
    if missing:
        raise RuntimeError(f"{stage} requires planned new files to be materialized: {', '.join(missing)}")


def _snapshot_paths(selected: dict[str, Any], write_set: dict[str, set[str]]) -> list[str]:
    declared = selected.get("execution_snapshot_paths")
    expected = set().union(*write_set.values())
    planned = _planned_new_files(selected, write_set)
    missing = {path for path in expected if not (REPOSITORY_ROOT / path).is_file()}
    if not missing.issubset(planned):
        raise ValueError("only explicitly planned new files may be absent from execution snapshots")
    if not isinstance(declared, list) or {value.replace("\\", "/") for value in declared if isinstance(value, str)} != expected:
        raise ValueError("execution snapshots must exactly cover the single-maintainer write set")
    return sorted(expected, key=str.casefold)


def _changed_observation_paths(observation: dict[str, Any]) -> set[str]:
    return {
        item["path"]
        for item in observation["changed_files"]
        if item["before_bytes_base64"] != item["after_bytes_base64"]
    }


def _run_command(root: Path, command: dict[str, Any], *, capture: bool = False) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [command["executable"], *command["argv"]],
        cwd=root / command["cwd"],
        shell=False,
        check=False,
        capture_output=capture,
        timeout=command["timeout_seconds"],
    )


def _run_command_with_manifest(
    root: Path,
    command: dict[str, Any],
    allowed: set[str],
    label: str,
    *,
    capture: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    before = _worktree_manifest(root)
    try:
        completed = _run_command(root, command, capture=capture)
    finally:
        after = _worktree_manifest(root)
        _assert_manifest_delta(before, after, allowed, label)
    return completed


def _stable_terminal_guard(
    run_dir: Path,
    predicate: dict[str, Any],
    slice_id: str,
    expected_predicate: str,
) -> None:
    """Check terminal evidence using the bridge-side validator root.

    BROH-S7 can change validate_implementation.py, so this guard deliberately
    uses the stable validate_all.py identity and does not call the terminal
    validator's implementation logic.
    """
    validation = _validation_module()
    expected_contract = _hash_file(PLAN_DIR / "implementation-contract.v1.json")
    expected_snapshot = (
        validation.validation_snapshot()
        if expected_predicate == "implementation-complete"
        else validation.slice_validation_snapshot(slice_id)
    )
    expected_validator = validation._validator_hash()
    projection = _json(run_dir / "stage-evidence-projection.v1.json")
    projection_core = dict(projection)
    root_hash = projection_core.pop("root_hash", None)
    if root_hash != "sha256:" + hashlib.sha256(
        json.dumps(projection_core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest():
        raise RuntimeError("stable terminal guard rejected projection integrity")
    expected_stage_hashes = {
        stage: _hash_file(run_dir / f"{stage}-result.json")
        for stage in ("red", "green", "refactor")
    }
    if projection.get("stage_result_hashes") != expected_stage_hashes:
        raise RuntimeError("stable terminal guard rejected stage evidence linkage")
    candidate = projection.get("candidate_identity")
    legacy_validator = _json(run_dir / "red-result.json").get("validator_hash")
    known_legacy_validators = {
        value.get("validator_hash")
        for path in (REPOSITORY_ROOT / "logs/tdd-adapter" / _json(PLAN_DIR / "implementation-contract.v1.json")["plan_id"] / "BROH-S6").glob("*/red-result.json")
        for value in [_json(path)]
        if isinstance(value.get("validator_hash"), str)
    }
    allowed_validators = {expected_validator}
    if isinstance(legacy_validator, str) and legacy_validator in known_legacy_validators:
        allowed_validators.add(legacy_validator)
    if (
        projection.get("plan_id") != _json(PLAN_DIR / "implementation-contract.v1.json").get("plan_id")
        or projection.get("slice_id") != slice_id
        or projection.get("run_id") != run_dir.name
        or not isinstance(candidate, dict)
        or candidate.get("contract_hash") != expected_contract
        or candidate.get("validator_hash") not in allowed_validators
    ):
        raise RuntimeError("stable terminal guard rejected candidate verifier identity")
    for stage in ("red", "green", "refactor"):
        stage_result = _json(run_dir / f"{stage}-result.json")
        if stage_result.get("contract_hash") != expected_contract or stage_result.get("validator_hash") not in allowed_validators:
            raise RuntimeError(f"stable terminal guard rejected {stage} verifier identity")
    if (
        predicate.get("status") != "pass"
        or predicate.get("predicate") != expected_predicate
        or predicate.get("slice_id") != slice_id
        or predicate.get("contract_hash") != expected_contract
        or predicate.get("validation_snapshot") != expected_snapshot
        or any(predicate.get(key) != value for key, value in expected_snapshot.items())
        or predicate.get("authorizes") != []
    ):
        raise RuntimeError("stable terminal guard rejected terminal predicate")


def _decode_context(context: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(context))
    for item in [*result["authority_refs"], result["implementation_contract"]]:
        item["payload"] = base64.b64decode(item.pop("payload_base64"), validate=True)
    return result


def _state_paths(plan_id: str, slice_id: str) -> tuple[Path, Path]:
    evidence_root = REPOSITORY_ROOT / "logs/tdd-adapter" / plan_id
    return evidence_root, evidence_root / "controller" / f"{slice_id}-single-maintainer-state.v1.json"


def _prepare(
    contract: dict[str, Any],
    selected: dict[str, Any],
    state_path: Path,
    evidence_root: Path,
    *,
    predecessor_run_id: str | None = None,
) -> dict[str, Any]:
    run_id = datetime.now(timezone.utc).strftime("RUN-%Y%m%dT%H%M%S-%fZ")
    invocation = build_slice_invocation.build(REPOSITORY_ROOT, PLAN_DIR, selected["slice_id"], run_id)
    run_dir = evidence_root / selected["slice_id"] / run_id
    write_set = _write_set(selected)
    paths = _snapshot_paths(selected, write_set)
    planned_new = _planned_new_files(selected, write_set)
    state = {
        "schema_version": "jimuyun.single-maintainer-tdd-bridge-state.v1",
        "plan_id": contract["plan_id"],
        "slice_id": selected["slice_id"],
        "run_id": run_id,
        "phase": "awaiting-red-test",
        "run_dir": run_dir.relative_to(REPOSITORY_ROOT).as_posix(),
        "snapshot_paths": paths,
        "write_set": {key: sorted(value) for key, value in write_set.items()},
        "planned_new_files": sorted(planned_new),
        "baseline_snapshots": stage_observation_runner.freeze(REPOSITORY_ROOT, paths),
        "baseline_worktree_manifest": _worktree_manifest(REPOSITORY_ROOT),
        "invocation": invocation,
        "protocol_identity": _protocol_identity(),
        "predecessor_run_id": predecessor_run_id,
        "authorizes": [],
    }
    _write(state_path, state)
    return {
        "status": "paused",
        "next_action": "add-or-update-the-declared-red-test-in-the-current-ai-session",
        "slice_id": selected["slice_id"],
        "run_id": run_id,
        "authorizes": [],
    }


def _observe_red(state: dict[str, Any], state_path: Path) -> dict[str, Any]:
    write_set = {key: set(value) for key, value in state["write_set"].items()}
    current_manifest = _worktree_manifest(REPOSITORY_ROOT)
    changed = _changed_since(state["baseline_worktree_manifest"], current_manifest)
    _validate_red_changes(changed, write_set)
    command = state["invocation"]["red"]
    _require_materialized(
        {path for path in state.get("planned_new_files", []) if path in write_set["tests"]},
        "RED",
    )
    command_before = _worktree_manifest(REPOSITORY_ROOT)
    observation = stage_observation_runner.run(
        REPOSITORY_ROOT,
        "red",
        command,
        state["snapshot_paths"],
        "Observed the maintainer-authored target RED test.",
        before_snapshots=state["baseline_snapshots"],
    )
    command_after = _worktree_manifest(REPOSITORY_ROOT)
    _assert_manifest_delta(command_before, command_after, write_set["tests"], "RED command")
    if observation["exit_code"] == 0:
        raise RuntimeError("declared target RED test unexpectedly passed")
    observed_changes = _changed_observation_paths(observation)
    _validate_red_changes(observed_changes, write_set)
    run_dir = REPOSITORY_ROOT / state["run_dir"]
    stage_observation_runner.record_observation(run_dir, observation)
    state["phase"] = "awaiting-implementation"
    state["red_after_snapshots"] = {item["path"]: item["after_bytes_base64"] for item in observation["changed_files"]}
    state["red_worktree_manifest"] = command_after
    _write(state_path, state)
    return {
        "status": "paused",
        "next_action": "implement-minimal-green-in-the-current-ai-session",
        "slice_id": state["slice_id"],
        "run_id": state["run_id"],
        "authorizes": [],
    }


def _observe_green(state: dict[str, Any], state_path: Path) -> dict[str, Any]:
    write_set = {key: set(value) for key, value in state["write_set"].items()}
    current_manifest = _worktree_manifest(REPOSITORY_ROOT)
    changed = _changed_since(state["red_worktree_manifest"], current_manifest)
    _validate_green_changes(changed, write_set)

    run_dir = REPOSITORY_ROOT / state["run_dir"]
    _require_materialized(
        {path for path in state.get("planned_new_files", []) if path in write_set["production"]},
        "GREEN",
    )
    command_before = _worktree_manifest(REPOSITORY_ROOT)
    green = stage_observation_runner.run(
        REPOSITORY_ROOT,
        "green",
        state["invocation"]["green"],
        state["snapshot_paths"],
        "Observed the target GREEN test after the current-session implementation.",
        before_snapshots=state["red_after_snapshots"],
    )
    command_after = _worktree_manifest(REPOSITORY_ROOT)
    _assert_manifest_delta(command_before, command_after, write_set["production"], "GREEN command")
    if green["exit_code"] != 0:
        raise RuntimeError("target GREEN test failed")
    _validate_green_changes(_changed_observation_paths(green), write_set)
    stage_observation_runner.record_observation(run_dir, green)
    state["phase"] = "awaiting-refactor"
    state["green_after_snapshots"] = {item["path"]: item["after_bytes_base64"] for item in green["changed_files"]}
    state["green_worktree_manifest"] = command_after
    _write(state_path, state)
    return {
        "status": "paused",
        "next_action": "apply-declared-documentation-or-refactor-edits-in-the-current-ai-session",
        "slice_id": state["slice_id"],
        "run_id": state["run_id"],
        "authorizes": [],
    }


def _complete(state: dict[str, Any], state_path: Path, selected: dict[str, Any]) -> dict[str, Any]:
    write_set = {key: set(value) for key, value in state["write_set"].items()}
    current_manifest = _worktree_manifest(REPOSITORY_ROOT)
    _validate_refactor_changes(_changed_since(state["green_worktree_manifest"], current_manifest), write_set)
    run_dir = REPOSITORY_ROOT / state["run_dir"]
    _require_materialized(set(state.get("planned_new_files", [])), "REFACTOR")

    for command in state["invocation"]["refactor"][:-1]:
        if _run_command_with_manifest(REPOSITORY_ROOT, command, set(), f"REFACTOR pre-observation command {command['id']}").returncode != 0:
            raise RuntimeError("REFACTOR pre-observation command failed")
    command_before = _worktree_manifest(REPOSITORY_ROOT)
    refactor = stage_observation_runner.run(
        REPOSITORY_ROOT,
        "refactor",
        state["invocation"]["refactor"][-1],
        state["snapshot_paths"],
        "Observed the declared regression checks after refactor.",
        before_snapshots=state["green_after_snapshots"],
    )
    command_after = _worktree_manifest(REPOSITORY_ROOT)
    _assert_manifest_delta(command_before, command_after, set().union(*write_set.values()), "REFACTOR command")
    if refactor["exit_code"] != 0:
        raise RuntimeError("REFACTOR command failed")
    _validate_refactor_changes(_changed_observation_paths(refactor), write_set)
    stage_observation_runner.record_observation(run_dir, refactor)

    context = _decode_context(state["invocation"]["run_context"])
    for stage, observation in (
        ("red", _json(run_dir / "observations/red-observed.json")),
        ("green", _json(run_dir / "observations/green-observed.json")),
        ("refactor", refactor),
    ):
        core = context["stage_results"][stage]
        core["exit_code"] = observation["exit_code"]
        core["observed_at"] = observation["observed_at"]
        if stage == "refactor":
            core["command_ids"] = [item["id"] for item in state["invocation"]["refactor"]]
            core["command_id"] = state["invocation"]["refactor"][0]["id"]
    _write(run_dir / "recovery-state.json", {
        "schema_version": "rmap.recovery-state.v1",
        "run_id": state["run_id"],
        "state": "active",
        "contract_hash": context["stage_results"]["red"]["contract_hash"],
        "validator_hash": context["stage_results"]["red"]["validator_hash"],
        "predecessor_run_id": state.get("predecessor_run_id"),
        "supersedes_run_id": None,
    })
    observations = [_json(run_dir / f"observations/{stage}-observed.json") for stage in ("red", "green", "refactor")]
    for observation in observations:
        observation["changed_files"] = [
            item for item in observation.get("changed_files", [])
            if item.get("before_bytes_base64") is not None or item.get("after_bytes_base64") is not None
        ]
    bundle, store, _ = stage_artifact_composer.compose(context, observations, {})
    _persist_protocol_bundle_with_short_drive(run_dir, bundle, store)
    _write(run_dir / "stage-evidence-projection.v1.json", stage_projection_builder.build(
        REPOSITORY_ROOT, run_dir, state["slice_id"], state["snapshot_paths"]
    ))

    terminal_command = json.loads(json.dumps(state["invocation"]["terminal"]))
    if selected["exit_predicate"] == "implementation-complete":
        terminal_command["argv"].extend(["--current-run-dir", run_dir.relative_to(REPOSITORY_ROOT).as_posix()])
    terminal = _run_command_with_manifest(REPOSITORY_ROOT, terminal_command, set(), "terminal command", capture=True)
    if terminal.returncode != 0:
        raise RuntimeError("plan-local terminal predicate failed")
    try:
        predicate = json.loads(terminal.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("plan-local terminal predicate returned invalid JSON") from exc
    _stable_terminal_guard(run_dir, predicate, state["slice_id"], selected["exit_predicate"])
    _write(run_dir / f"{selected['exit_predicate']}-result.json", predicate)
    _write(run_dir.parents[1] / "run-state.v1.json", {
        "schema_version": "jimuyun.tdd-adapter-run-state.v1",
        "last_slice_id": state["slice_id"],
        "last_observed_predicate": selected["exit_predicate"],
        "next_action": "route",
        "failure_fingerprint": None,
        "repeat_count": 0,
        "authorizes": [],
        "does_not_authorize": ["acceptance-passed", "commit", "release"],
    })
    state["phase"] = "completed"
    state["completion_identity"] = _protocol_identity()
    _write(state_path, state)
    return {
        "status": "pass",
        "predicate": selected["exit_predicate"],
        "slice_id": state["slice_id"],
        "run_id": state["run_id"],
        "authorizes": [],
    }


def _complete_terminal_only(state: dict[str, Any], state_path: Path, selected: dict[str, Any]) -> dict[str, Any]:
    """Recover a failed terminal invocation without rewriting immutable stage observations."""
    run_dir = REPOSITORY_ROOT / state["run_dir"]
    result_path = run_dir / f"{selected['exit_predicate']}-result.json"
    if result_path.exists():
        raise RuntimeError("terminal result already exists; recovery would overwrite evidence")
    terminal_command = json.loads(json.dumps(state["invocation"]["terminal"]))
    if selected["exit_predicate"] == "implementation-complete":
        terminal_command["argv"].extend(["--current-run-dir", run_dir.relative_to(REPOSITORY_ROOT).as_posix()])
    terminal = _run_command_with_manifest(REPOSITORY_ROOT, terminal_command, set(), "terminal recovery command", capture=True)
    if terminal.returncode != 0:
        raise RuntimeError("terminal recovery predicate failed")
    try:
        predicate = json.loads(terminal.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("terminal recovery predicate returned invalid JSON") from exc
    _stable_terminal_guard(run_dir, predicate, state["slice_id"], selected["exit_predicate"])
    _write(run_dir / f"{selected['exit_predicate']}-result.json", predicate)
    _write(run_dir.parents[1] / "run-state.v1.json", {
        "schema_version": "jimuyun.tdd-adapter-run-state.v1",
        "last_slice_id": state["slice_id"],
        "last_observed_predicate": selected["exit_predicate"],
        "next_action": "route",
        "failure_fingerprint": None,
        "repeat_count": 0,
        "authorizes": [],
        "does_not_authorize": ["acceptance-passed", "commit", "release"],
    })
    state["phase"] = "completed"
    state["completion_identity"] = _protocol_identity()
    _write(state_path, state)
    return {
        "status": "pass",
        "predicate": selected["exit_predicate"],
        "slice_id": state["slice_id"],
        "run_id": state["run_id"],
        "authorizes": [],
    }


def run(slice_id: str, supplied_snapshots: list[str]) -> dict[str, Any]:
    contract = _json(PLAN_DIR / "implementation-contract.v1.json")
    selected = _selected(contract, slice_id)
    write_set = _write_set(selected)
    declared = _snapshot_paths(selected, write_set)
    supplied = sorted({path.replace("\\", "/") for path in supplied_snapshots}, key=str.casefold)
    if supplied != declared:
        raise ValueError("caller snapshot paths must exactly match the complete declared write set")
    evidence_root, state_path = _state_paths(contract["plan_id"], slice_id)
    if not state_path.is_file():
        return _prepare(contract, selected, state_path, evidence_root)
    state = _json(state_path)
    if state.get("plan_id") != contract["plan_id"] or state.get("slice_id") != slice_id:
        raise ValueError("single-maintainer bridge state identity mismatch")
    run_dir = REPOSITORY_ROOT / state["run_dir"]
    if (
        state.get("phase") == "awaiting-refactor"
        and (run_dir / "observations" / "refactor-observed.json").is_file()
        and not (run_dir / f"{selected['exit_predicate']}-result.json").is_file()
    ):
        return _complete_terminal_only(state, state_path, selected)
    if state.get("protocol_identity") != _protocol_identity():
        return _prepare(
            contract,
            selected,
            state_path,
            evidence_root,
            predecessor_run_id=state.get("run_id") if isinstance(state.get("run_id"), str) else None,
        )
    if state.get("phase") == "awaiting-red-test":
        return _observe_red(state, state_path)
    if state.get("phase") == "awaiting-implementation":
        return _observe_green(state, state_path)
    if state.get("phase") == "awaiting-refactor":
        return _complete(state, state_path, selected)
    if state.get("phase") == "completed":
        run_dir = REPOSITORY_ROOT / state["run_dir"]
        result_path = run_dir / f"{selected['exit_predicate']}-result.json"
        if state.get("completion_identity") != _protocol_identity() or not result_path.is_file():
            return _prepare(
                contract,
                selected,
                state_path,
                evidence_root,
                predecessor_run_id=state["run_id"],
            )
        result = _json(result_path)
        if not _result_is_current(result, selected, slice_id):
            return _prepare(
                contract,
                selected,
                state_path,
                evidence_root,
                predecessor_run_id=state["run_id"],
            )
        return {"status": "pass", "predicate": selected["exit_predicate"], "slice_id": slice_id, "run_id": state["run_id"], "authorizes": []}
    raise ValueError("single-maintainer bridge state phase is invalid")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--snapshot-path", action="append", nargs="+", default=[])
    args = parser.parse_args()
    if args.repository_root.resolve() != REPOSITORY_ROOT or args.plan_dir.resolve() != PLAN_DIR:
        raise ValueError("single-maintainer bridge is bound to this repository and plan")
    snapshots = [path for group in args.snapshot_path for path in group]
    print(json.dumps(run(args.slice_id, snapshots), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

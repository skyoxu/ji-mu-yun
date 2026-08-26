from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from route_plan_directory import route, _validation_snapshot
from stage_lifecycle_runner import (
    LifecycleRunner,
    derive_run_state,
    prior_red_observation_path,
    rebuild_stage_state,
    validate_implementation_successor,
)


HELPER_TIMEOUT_SECONDS = 900
LIFECYCLE_TIMEOUT_OVERHEAD_SECONDS = 60


def _refresh_successor_context(root: Path, plan: Path) -> dict[str, object]:
    """Load the adapter-owned Knowledge boundary without a shared module name."""
    module_path = TOOLS / "knowledge_context.py"
    spec = importlib.util.spec_from_file_location("quick_dev_loop_knowledge_context", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Quick Dev knowledge refresh boundary is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.refresh_successor_context(root, plan)
    if not isinstance(result, dict):
        raise RuntimeError("Quick Dev knowledge refresh result is invalid")
    return result


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


def _has_complete_protocol_bundle(run_dir: Path) -> bool:
    required = (
        "attempt-ledger-manifest.v1.json",
        "baseline-file-manifest.v1.json",
        "red-result.json",
        "green-result.json",
        "refactor-result.json",
    )
    return all((run_dir / name).is_file() for name in required)


def _slice_terminal_predicate(plan: Path, slice_id: str) -> str:
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = next((item for item in contract.get("slices", []) if item.get("slice_id") == slice_id), None)
    predicate = selected.get("exit_predicate") if isinstance(selected, dict) else None
    if not isinstance(predicate, str) or not predicate:
        raise ValueError("slice terminal predicate is missing or invalid")
    return predicate


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
        cwd=workspace / command["cwd"],
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
    plan_binding: dict[str, object] | None = None,
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
    basis = {
        "failure_intent": {"command_id": command["id"], "test_selector": selector, "expected_failure_ids": list(expected)},
        "test_selector": selector,
        "contract_hash": contract_hash,
        "validator_hash": validator_hash,
        "pre_implementation_candidate": dict(pre_implementation_candidate),
    }
    if plan_binding is not None:
        basis["plan_binding"] = dict(plan_binding)
    return basis


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


def _legacy_current_bridge_handoff(root: Path, plan: Path, contract: dict[str, object], slice_id: str) -> dict[str, str] | None:
    """Historical reader retained only for older evidence inspection."""
    selected = next((item for item in contract.get("slices", []) if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict):
        raise ValueError("bridge slice declaration is invalid")
    if selected.get("execution_mode", "tdd") != "tdd":
        return None
    if not isinstance(selected.get("tdd"), dict):
        raise ValueError("bridge slice declaration is invalid")
    red = selected["tdd"].get("red")
    if not isinstance(red, dict):
        raise ValueError("bridge RED declaration is invalid")
    evidence_root = root / "logs" / "tdd-adapter" / str(contract["plan_id"]) / slice_id
    artifacts = sorted(evidence_root.glob("*/implementation-needed-result.json")) if evidence_root.is_dir() else []
    if not artifacts:
        artifacts = []
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
        # Legacy staged runs may only have red-result plus the immutable
        # nonzero observation. Accept the newest matching observation as a
        # prior-red successor; it is never treated as a fresh RED pass.
        legacy: list[Path] = []
        for result_path in sorted(evidence_root.glob("*/red-result.json")) if evidence_root.is_dir() else []:
            observation = result_path.parent / "observations" / "red-observed.json"
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
                observed = json.loads(observation.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if (result.get("stage") == "red" and result.get("slice_id") == slice_id
                    and isinstance(result.get("test_selector"), str)
                    and result.get("test_selector", "").startswith(".agents/")
                    and isinstance(result.get("expected_failure_ids"), list)
                    and result.get("expected_failure_ids")
                    and observed.get("stage") == "red" and isinstance(observed.get("exit_code"), int)
                    and observed.get("exit_code") != 0):
                legacy.append(observation)
        if not legacy:
            for run_path in sorted(evidence_root.glob("RUN-*")) if evidence_root.is_dir() else []:
                basis_path = run_path / "red-basis.v1.json"
                observation = run_path / "observations" / "red-observed.json"
                try:
                    basis = json.loads(basis_path.read_text(encoding="utf-8"))
                    observed = json.loads(observation.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    continue
                intent = basis.get("failure_intent", {})
                if (intent.get("expected_failure_ids") == red.get("expected_failure_ids")
                        and observed.get("stage") == "red"
                        and isinstance(observed.get("exit_code"), int)
                        and observed.get("exit_code") != 0):
                    legacy.append(observation)
        if legacy:
            artifact = sorted(legacy, key=lambda path: path.parent.parent.name)[-1]
            return {"path": artifact.relative_to(root).as_posix(), "sha256": _sha(artifact)}
        if valid:
            raise ValueError("migration RED handoff is ambiguous")
        if stale:
            return None
        raise ValueError("migration RED handoff is invalid")
    artifact = valid[0]
    return {"path": artifact.relative_to(root).as_posix(), "sha256": _sha(artifact)}


def _current_bridge_handoff(root: Path, plan: Path, contract: dict[str, object], slice_id: str) -> dict[str, str] | None:
    """Use the router's single strict handoff validator for all continuations."""
    from route_plan_directory import current_red_handoff
    return current_red_handoff(root, plan, slice_id)


def _active_slice_run(root: Path, plan_id: str, slice_id: str) -> tuple[Path, str] | None:
    evidence_root = root / "logs" / "tdd-adapter" / plan_id / slice_id
    candidates = sorted((path for path in evidence_root.glob("RUN-*") if path.is_dir()), key=lambda path: path.name, reverse=True)
    # A recovery retry may leave a newer GREEN-only successor beside an older
    # successor that already has a complete REFACTOR. Prefer the furthest
    # verified lifecycle evidence so retries do not regress the route.
    ranked: list[tuple[Path, str]] = []
    for run_dir in candidates:
        action = route_staged_run(run_dir)
        if action is None and (run_dir / "slice-ready-result.json").is_file() and validate_implementation_successor(run_dir):
            action = "slice-terminal"
        if action is not None:
            ranked.append((run_dir, action))
    if ranked:
        priority = {"slice-terminal": 0, "refactor": 1, "green": 2, "implement": 3}
        return sorted(ranked, key=lambda item: (priority.get(item[1], 9), item[0].name))[0]
    return None


def reserve_successor_run(predecessor: Path, lineage: dict[str, object]) -> Path:
    """Reserve one replayable successor before materializing any stage evidence.

    The lineage bytes are the reservation identity.  Repeating the same request
    returns the original reservation; a competing lineage cannot overwrite it.
    """
    if not predecessor.is_dir() or not isinstance(lineage, dict):
        raise ValueError("successor reservation input is invalid")
    if lineage.get("authorizes") != [] or not isinstance(lineage.get("predecessor_run"), str) or not lineage["predecessor_run"]:
        raise ValueError("successor lineage is invalid")
    successor = predecessor.parent / f"{predecessor.name}-SUCCESSOR"
    lineage_path = successor / "successor-lineage.v1.json"
    encoded = json.dumps(lineage, indent=2, sort_keys=True) + "\n"
    if successor.exists():
        if successor.is_dir() and not successor.is_symlink() and lineage_path.is_file() and lineage_path.read_text(encoding="utf-8") == encoded:
            # A matching reservation is reusable only after a complete
            # protocol bundle exists. Incomplete historical reservations are
            # immutable evidence and must receive a fresh successor.
            if (successor / "protocol-bundle.v1.json").is_file():
                return successor
        # Keep an incomplete/conflicting historical successor immutable and
        # reserve the next deterministic append-only identity.
        index = 1
        while True:
            candidate = predecessor.parent / f"{predecessor.name}-SUCCESSOR-{index:03d}"
            if not candidate.exists():
                successor = candidate
                lineage_path = successor / "successor-lineage.v1.json"
                break
            index += 1
    successor.mkdir(parents=True)
    try:
        with lineage_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
    except FileExistsError as exc:
        raise RuntimeError("successor reservation identity conflicts") from exc
    return successor


def _active_prior_red_handoff(run_dir: Path) -> dict[str, str] | None:
    path = run_dir / "prior-red-handoff.v2.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        reference = value.get("red_observation")
        if isinstance(reference, dict) and set(reference) == {"path", "sha256"} and all(isinstance(reference[key], str) for key in reference):
            return {"path": reference["path"], "sha256": reference["sha256"]}
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        pass
    return None


def _has_execution_fingerprint(run_dir: Path) -> bool:
    try:
        basis = json.loads((run_dir / "red-basis.v1.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(basis.get("execution_fingerprint"), str) and bool(basis["execution_fingerprint"])


def route_staged_run(run_dir: Path) -> str | None:
    """Return the next action derived from append-only observations.

    The stage-state sidecar is refreshed only as a cache.  It never controls
    whether a RED, GREEN, or REFACTOR observation is repeated.
    """
    return rebuild_stage_state(run_dir)


def _run_slice(root: Path, plan: Path, slice_id: str, snapshots: list[str]) -> None:
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    bridge = contract.get("adapter_bridge")
    active = _active_slice_run(root, str(contract["plan_id"]), slice_id)
    stage = active[1] if active else "red"
    reusable_handoff = _current_bridge_handoff(root, plan, contract, slice_id)
    if active is not None and reusable_handoff is not None and not _has_execution_fingerprint(active[0]):
        # An interrupted implementation stage is recoverable from the one
        # validated prior RED observation. Legacy runs cannot prove their
        # executable semantics against the current contract, so they resume in
        # a successor rather than writing another observation into that run.
        active = None
        stage = "red"
    if stage == "implement":
        raise RuntimeError("implementation handoff must publish a RED-bound successor before run-slice")
    if stage == "slice-terminal":
        raise RuntimeError("slice terminal must be routed as validate-slice")
    handoff = reusable_handoff if stage == "red" else _active_prior_red_handoff(active[0]) if active is not None else None
    if stage == "red" and isinstance(bridge, dict) and isinstance(bridge.get("runner"), str) and handoff is None:
        runner = plan / bridge["runner"]
        if not runner.is_file():
            raise ValueError("declared plan-local adapter bridge is missing")
        _run([str(runner), "--repository-root", str(root), "--plan-dir", str(plan), "--slice-id", slice_id, "--snapshot-path", *snapshots, "--materialize-only"])
    snapshots = _workspace_snapshot_paths(root, plan, snapshots)
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
    if handoff is not None and stage == "red":
        run_dir.mkdir(parents=True, exist_ok=False)
        invocation_args.extend(["--stage", "green"])
    else:
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
    selected = next((item for item in contract.get("slices", []) if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict):
        raise RuntimeError("slice terminal is not declared")
    if selected.get("execution_mode") in {"regression", "dogfood-replay"}:
        # Read-only verification slices deliberately have no new RED/GREEN/
        # REFACTOR lifecycle. Their registered terminal is the full evidence.
        runner = plan / contract["terminal"]["runner"]
        output = plan / "terminal-results" / f"{slice_id}.json"
        _run([
            str(runner), "--repository-root", str(root), "--plan-dir", str(plan),
            "--slice", slice_id, "--out", str(output),
        ], timeout_seconds=7200)
        return
    active = _active_slice_run(root, str(contract["plan_id"]), slice_id)
    if active is None or active[1] != "slice-terminal":
        raise RuntimeError("slice terminal requires a completed refactor observation")
    run_dir = active[0]
    run_id = datetime.now(timezone.utc).strftime("RUN-%Y%m%dT%H%M%S-%fZ")
    invocation = root / "logs" / "tdd-adapter" / str(contract["plan_id"]) / "_invocations" / run_id
    _run([str(TOOLS / "build_slice_invocation.py"), "--repository-root", str(root), "--plan-dir", str(plan), "--slice-id", slice_id, "--run-id", run_id, "--out-dir", str(invocation)])
    context = json.loads((invocation / "run-context.json").read_text(encoding="utf-8"))
    for item in [*context["authority_refs"], context["implementation_contract"]]:
        item["payload"] = base64.b64decode(item.pop("payload_base64"), validate=True)
    prior_red = prior_red_observation_path(run_dir)
    observation_sources = {"red": prior_red.parent.parent if prior_red is not None else run_dir, "green": run_dir, "refactor": run_dir}
    observations = {
        stage: json.loads((observation_sources[stage] / "observations" / f"{stage}-observed.json").read_text(encoding="utf-8"))
        for stage in ("red", "green", "refactor")
    }
    for stage in ("green", "refactor"):
        core = context["stage_results"][stage]
        core["exit_code"] = observations[stage]["exit_code"]
        core["observed_at"] = observations[stage]["observed_at"]
        if stage == "refactor":
            refactor_commands = json.loads((invocation / "refactor-commands.json").read_text(encoding="utf-8"))
            core["command_ids"] = [item["id"] for item in refactor_commands]
            core["command_id"] = refactor_commands[0]["id"]
    snapshots = _workspace_snapshot_paths(root, plan, snapshots)
    observation_refs = []
    for stage in ("red", "green", "refactor"):
        source = observation_sources[stage] / "observations" / f"{stage}-observed.json"
        if not source.is_file():
            raise RuntimeError("terminal successor requires complete lifecycle observations")
        observation_refs.append({"stage": stage, "path": source.relative_to(root).as_posix(), "sha256": _sha(source)})
    lineage = {
        "schema_version": "quick-dev-tdd-adapter.successor-lineage.v1",
        "predecessor_run": run_dir.relative_to(root).as_posix(),
        "predecessor_observations": observation_refs,
        "next_transition": "slice-terminal",
        "authorizes": [],
    }
    # Always close a fresh terminal successor. Historical runs may contain
    # immutable protocol artifacts from an older contract or partial retry.
    run_dir = reserve_successor_run(run_dir, lineage)
    context["run_id"] = run_dir.name
    for core in context["stage_results"].values():
        core["run_id"] = run_dir.name
    lifecycle = LifecycleRunner(root, run_dir, snapshots)
    lifecycle.resume_observations(run_dir, ["red", "green", "refactor"], observation_sources=observation_sources)
    try:
        try:
            lifecycle.close(context, {}, observation_sources=observation_sources)
        except ValueError as exc:
            if "existing protocol artifact conflicts" not in str(exc) or not _has_complete_protocol_bundle(run_dir):
                raise
    except (ValueError, FileNotFoundError) as exc:
        # A partially closed run is immutable. Reconcile it by creating an
        # append-only successor carrying only stage observations, never by
        # overwriting protocol attempts from the predecessor.
        if "protocol artifact conflicts" not in str(exc):
            raise
        observation_refs = []
        for stage in ("red", "green", "refactor"):
            source = observation_sources[stage] / "observations" / f"{stage}-observed.json"
            if not source.is_file():
                raise RuntimeError("terminal successor requires complete lifecycle observations")
            observation_refs.append({"stage": stage, "path": source.relative_to(root).as_posix(), "sha256": _sha(source)})
        lineage = {
            "schema_version": "quick-dev-tdd-adapter.successor-lineage.v1",
            "predecessor_run": run_dir.relative_to(root).as_posix(),
            "predecessor_observations": observation_refs,
            "next_transition": "slice-terminal",
            "authorizes": [],
        }
        # Reservation is the single identity gate for real terminal recovery.
        # It is reused on retry before successor observations are materialized.
        run_dir = reserve_successor_run(run_dir, lineage)
        context["run_id"] = run_dir.name
        for core in context["stage_results"].values():
            core["run_id"] = run_dir.name
        lifecycle = LifecycleRunner(root, run_dir, snapshots)
        lifecycle.resume_observations(
            run_dir.parent / run_dir.name.removesuffix("-SUCCESSOR"),
            ["red", "green", "refactor"],
            observation_sources=observation_sources,
        )
        try:
            lifecycle.close(context, {}, observation_sources=observation_sources)
        except ValueError as exc:
            if "existing protocol artifact conflicts" not in str(exc) or not _has_complete_protocol_bundle(run_dir):
                raise
    expected_predicate = _slice_terminal_predicate(plan, slice_id)
    command = json.loads((invocation / "terminal-command.json").read_text(encoding="utf-8"))
    completed = subprocess.run([command["executable"], *command["argv"]], cwd=root / command["cwd"], shell=False, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=command["timeout_seconds"])
    if completed.returncode != 0:
        raise RuntimeError("slice terminal predicate failed")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        # Registered test commands are allowed to be ordinary deterministic
        # runners (for example pytest -q). Their zero exit is the predicate;
        # JSON output is optional and must not be fabricated by the test.
        if completed.stdout.strip():
            result = {"status": "pass", "predicate": "slice-ready", "stdout_sha256": "sha256:" + hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest()}
        else:
            result = {"status": "pass", "predicate": "slice-ready"}
    if result.get("status") != "pass" or result.get("predicate") != expected_predicate:
        raise RuntimeError("slice terminal predicate did not pass")
    if expected_predicate == "implementation-complete":
        contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
        selected = next(item for item in contract["slices"] if item.get("slice_id") == slice_id)
        result.update({
            "schema_version": "quick-dev-implementation-complete.v1",
            "plan_id": contract["plan_id"],
            "contract_hash": _sha(plan / "implementation-contract.v1.json"),
            "terminal_command_id": selected["post_refactor_command_id"],
            "validated_command_ids": [selected["post_refactor_command_id"]],
            "authorizes": ["implementation-complete"],
        })
    result["execution_fingerprint"] = context["stage_results"]["red"]["execution_fingerprint"]
    # Terminal slice evidence must carry the complete current candidate
    # identity so route validation cannot accept an old successor after a
    # contract, authority, or validator change.
    identity = _validation_snapshot(plan, slice_id)
    if identity is None:
        raise RuntimeError("slice terminal candidate identity is unavailable")
    result.update(identity)
    exit_predicate = selected.get("exit_predicate", "slice-ready")
    if exit_predicate == "implementation-candidate":
        result["predicate"] = "implementation-candidate"
        result["status"] = "pass"
        candidate = {
            "schema_version": "quick-dev-tdd-adapter.candidate-evidence.v1",
            "plan_id": contract["plan_id"],
            "slice_id": slice_id,
            "status": "pass",
            "candidate": identity,
            "lifecycle": {"red": True, "green": True, "refactor": True},
            "authorizes": [],
        }
        (run_dir / "candidate-evidence.json").write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8", newline="\n")
    (run_dir / f"{exit_predicate}-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--snapshot-path", action="append", default=[])
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
        if result["next_action"] == "refresh-knowledge-context":
            refreshed = _refresh_successor_context(root, plan)
            if refreshed.get("status") != "refreshed":
                raise RuntimeError(str(refreshed.get("failure_code", "knowledge successor refresh failed")))
            continue
        if result["next_action"] == "validate-slice":
            if not args.snapshot_path:
                raise ValueError("validate-slice requires a snapshot path")
            _run_slice_terminal(root, plan, str(result["slice_id"]), args.snapshot_path)
            continue
        if result["next_action"] != "run-slice":
            break
        _run_slice(root, plan, str(result["slice_id"]), args.snapshot_path)
    print(json.dumps({"actions": actions, "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any

PLAN_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_DIR.parents[1]
SLICE_ORDER = [f"BROH-S{index}" for index in range(8)]
TERMINAL_COMMAND_IDS = [
    "skill-tests",
    "acceptance-review-requirement-tests",
    "acceptance-bootstrap-integration-tests",
    "plan-validator-tests",
]
REQUIRED_TERMINAL_CONSUMERS = frozenset(TERMINAL_COMMAND_IDS)
FRESHNESS_ROOTS = (
    "candidate_hash", "predicate_input_root", "authority_root", "validator_root",
    "validator_version", "closure_definition_hash",
)


def _validation_module():
    path = PLAN_DIR / "tools" / "validate_all.py"
    spec = importlib.util.spec_from_file_location("broh_implementation_validate_all", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("plan-local validation snapshot helper is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validation_snapshot() -> dict[str, str]:
    return _validation_module().validation_snapshot()


def _contract() -> dict[str, Any]:
    return json.loads((PLAN_DIR / "implementation-contract.v1.json").read_text(encoding="utf-8"))


def _contract_hash() -> str:
    return "sha256:" + hashlib.sha256((PLAN_DIR / "implementation-contract.v1.json").read_bytes()).hexdigest()


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _value_hash(value: Any) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def check_lifecycle_entry(plan_dir: Path = PLAN_DIR) -> list[str]:
    try:
        state = json.loads((plan_dir / "plan-state.v1.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ["implementation-state-invalid"]
    lifecycle_state = state.get("state")
    owner = state.get("state_owner")
    if lifecycle_state not in {"implementation-authorized", "implementation-complete"}:
        return [f"implementation-authorization-required:{lifecycle_state}"]
    expected_owner = "maintainer" if lifecycle_state == "implementation-authorized" else "quick-dev-tdd-adapter"
    if owner != expected_owner:
        return [f"implementation-state-owner-invalid:{lifecycle_state}"]
    return []


def _validate_run(
    run_dir: Path,
    slice_id: str,
    contract_hash: str,
    *,
    result_predicate: str = "slice-ready",
    require_result: bool = True,
) -> list[str]:
    errors: list[str] = []
    required = [
        "red-result.json", "green-result.json", "refactor-result.json",
        "stage-evidence-projection.v1.json", "recovery-state.json",
        "attempt-ledger-manifest.v1.json", "run-events.jsonl", "baseline-file-manifest.v1.json",
    ]
    if require_result:
        required.append(f"{result_predicate}-result.json")
    errors.extend(f"slice-artifact-missing:{slice_id}:{name}" for name in required if not (run_dir / name).is_file())
    if errors:
        return errors
    contract = _contract()
    selected = next(item for item in contract["slices"] if item["slice_id"] == slice_id)
    expected_commands = {
        "red": [selected["tdd"]["red"]["command_id"]],
        "green": [selected["tdd"]["green"]["command_id"]],
        "refactor": [item["command_id"] for item in selected["tdd"]["refactor"]["invocations"]],
    }
    expected_status = {"red": "red-observed", "green": "green-observed", "refactor": "refactor-verified"}
    stage_values: dict[str, dict[str, Any]] = {}
    for stage in ("red", "green", "refactor"):
        try:
            value = json.loads((run_dir / f"{stage}-result.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            errors.append(f"slice-stage-invalid:{slice_id}:{stage}")
            continue
        stage_values[stage] = value
        commands = value.get("command_ids", [value.get("command_id")]) if stage == "refactor" else [value.get("command_id")]
        binding_fields = ("attempt_id", "decision_hash", "capsule_hash", "context_hash", "validator_hash")
        if (
            value.get("slice_id") != slice_id
            or value.get("run_id") != run_dir.name
            or value.get("contract_hash") != contract_hash
            or value.get("status") != expected_status[stage]
            or commands != expected_commands[stage]
            or any(not isinstance(value.get(field), str) or not value[field] for field in binding_fields)
            or (stage == "red" and value.get("exit_code") == 0)
            or (stage != "red" and value.get("exit_code") != 0)
        ):
            errors.append(f"slice-stage-binding-invalid:{slice_id}:{stage}")
    if len(stage_values) == 3:
        stage_hashes = {stage: _sha((run_dir / f"{stage}-result.json").read_bytes()) for stage in stage_values}
        expected_predecessors = {"red": None, "green": stage_hashes["red"], "refactor": stage_hashes["green"]}
        if any(stage_values[stage].get("predecessor_stage_hash") != expected_predecessors[stage] for stage in stage_values):
            errors.append(f"slice-stage-chain-invalid:{slice_id}")
        if len({stage_values[stage].get("validator_hash") for stage in stage_values}) != 1:
            errors.append(f"slice-stage-validator-invalid:{slice_id}")
    try:
        projection = json.loads((run_dir / "stage-evidence-projection.v1.json").read_text(encoding="utf-8"))
        projection_core = dict(projection)
        root_hash = projection_core.pop("root_hash", None)
        expected_hashes = {stage: _sha((run_dir / f"{stage}-result.json").read_bytes()) for stage in ("red", "green", "refactor")}
        if (
            projection.get("plan_id") != contract["plan_id"]
            or projection.get("slice_id") != slice_id
            or projection.get("run_id") != run_dir.name
            or projection.get("stage_result_hashes") != expected_hashes
            or root_hash != _value_hash(projection_core)
        ):
            errors.append(f"slice-projection-invalid:{slice_id}")
    except (OSError, UnicodeError, json.JSONDecodeError):
        errors.append(f"slice-projection-invalid:{slice_id}")
    if require_result:
        try:
            result = json.loads((run_dir / f"{result_predicate}-result.json").read_text(encoding="utf-8"))
            validation = _validation_module()
            expected_snapshot = validation.slice_validation_snapshot(slice_id)
            expected_predecessors = validation.predecessor_result_hashes(slice_id)
            if (
                result.get("predicate") != result_predicate
                or result.get("status") != "pass"
                or result.get("slice_id") != slice_id
                or result.get("contract_hash") != contract_hash
                or result.get("predecessor_result_hashes") != expected_predecessors
                or any(result.get(key) != expected_snapshot[key] for key in FRESHNESS_ROOTS)
                or result.get("validation_snapshot") != expected_snapshot
            ):
                errors.append(f"slice-result-invalid:{slice_id}")
        except (OSError, UnicodeError, json.JSONDecodeError):
            errors.append(f"slice-result-invalid:{slice_id}")
    try:
        ledger_path = run_dir / "attempt-ledger-manifest.v1.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ledger_core = dict(ledger)
        root_hash = ledger_core.pop("root_hash", None)
        attempts = ledger.get("attempts")
        event_payload = (run_dir / "run-events.jsonl").read_bytes()
        events = [json.loads(line) for line in event_payload.decode("utf-8").splitlines() if line]
        expected_attempts = [stage_values.get(stage, {}).get("attempt_id") for stage in ("red", "green", "refactor")]
        if (
            not isinstance(attempts, list)
            or [item.get("stage") for item in attempts] != ["red", "green", "refactor"]
            or [item.get("attempt_id") for item in attempts] != expected_attempts
            or any(
                item.get("stage_result_hash") != _sha((run_dir / f"{item.get('stage')}-result.json").read_bytes())
                for item in attempts
            )
            or ledger.get("run_events_hash") != _sha(event_payload)
            or root_hash != _value_hash(ledger_core)
            or not events
            or [item.get("sequence") for item in events] != list(range(1, len(events) + 1))
            or any(
                item.get("previous_event_hash") != (None if index == 0 else _value_hash(events[index - 1]))
                for index, item in enumerate(events)
            )
            or ledger.get("final_event_hash") != _value_hash(events[-1])
        ):
            errors.append(f"slice-attempt-ledger-invalid:{slice_id}")
    except (OSError, UnicodeError, json.JSONDecodeError):
        errors.append(f"slice-attempt-ledger-invalid:{slice_id}")
    try:
        recovery = json.loads((run_dir / "recovery-state.json").read_text(encoding="utf-8"))
        if (
            recovery.get("schema_version") != "rmap.recovery-state.v1"
            or recovery.get("run_id") != run_dir.name
            or recovery.get("contract_hash") != contract_hash
            or recovery.get("validator_hash") != stage_values.get("red", {}).get("validator_hash")
        ):
            errors.append(f"slice-recovery-state-invalid:{slice_id}")
    except (OSError, UnicodeError, json.JSONDecodeError):
        errors.append(f"slice-recovery-state-invalid:{slice_id}")
    if len(stage_values) == 3:
        for index, stage in enumerate(("red", "green", "refactor"), start=1):
            attempt_id = stage_values[stage].get("attempt_id")
            if not isinstance(attempt_id, str) or not attempt_id:
                errors.append(f"slice-protocol-binding-invalid:{slice_id}:{stage}")
                continue
            capsule_id = f"CAP-{index:03d}"
            try:
                decision = json.loads((run_dir / "attempts" / attempt_id / "adapter-decision.v1.json").read_text(encoding="utf-8"))
                context = json.loads((run_dir / "context" / capsule_id / "context-manifest.v1.json").read_text(encoding="utf-8"))
                capsule_path = run_dir / "context" / capsule_id / "slice-capsule.v1.json"
                if (
                    _value_hash(decision) != stage_values[stage]["decision_hash"]
                    or context.get("context_hash") != stage_values[stage]["context_hash"]
                    or context.get("capsule_ref", {}).get("sha256") != stage_values[stage]["capsule_hash"]
                    or _sha(capsule_path.read_bytes()) != stage_values[stage]["capsule_hash"]
                ):
                    errors.append(f"slice-protocol-binding-invalid:{slice_id}:{stage}")
            except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError):
                errors.append(f"slice-protocol-binding-invalid:{slice_id}:{stage}")
    return errors


def _latest_slice_result(slice_id: str, contract_hash: str) -> Path | None:
    root = REPOSITORY_ROOT / "logs" / "tdd-adapter" / _contract()["plan_id"] / slice_id
    candidates = sorted(root.glob("*/slice-ready-result.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if value.get("predicate") == "slice-ready" and value.get("status") == "pass" and value.get("contract_hash") == contract_hash:
            return path.parent
    return None


def check_slice_evidence() -> list[str]:
    contract_hash = _contract_hash()
    errors: list[str] = []
    for slice_id in SLICE_ORDER[:-1]:
        run_dir = _latest_slice_result(slice_id, contract_hash)
        if run_dir is None:
            errors.append(f"slice-evidence-missing:{slice_id}")
        else:
            errors.extend(_validate_run(run_dir, slice_id, contract_hash))
    return errors


def _latest_terminal_run() -> Path | None:
    root = REPOSITORY_ROOT / "logs" / "tdd-adapter" / _contract()["plan_id"] / "BROH-S7"
    candidates = sorted(root.glob("*/implementation-complete-result.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0].parent if candidates else None


def check_terminal_slice_evidence(run_dir: Path | None) -> list[str]:
    if run_dir is None:
        return ["terminal-slice-evidence-missing:BROH-S7"]
    candidate = run_dir.resolve()
    expected_root = (
        REPOSITORY_ROOT / "logs" / "tdd-adapter" / _contract()["plan_id"] / "BROH-S7"
    ).resolve()
    try:
        relative = candidate.relative_to(expected_root)
    except ValueError:
        return ["terminal-slice-run-outside-evidence-root:BROH-S7"]
    if len(relative.parts) != 1 or not candidate.is_dir():
        return ["terminal-slice-run-invalid:BROH-S7"]
    return _validate_run(candidate, "BROH-S7", _contract_hash(), require_result=False)


def check_contract_consistency() -> list[str]:
    contract = _contract()
    registry = json.loads((PLAN_DIR / contract["command_registry"]).read_text(encoding="utf-8"))
    commands = {item.get("id"): item for item in registry.get("commands", []) if isinstance(item, dict)}
    errors: list[str] = []
    for item in contract.get("slices", []):
        slice_id = item.get("slice_id")
        tdd = item.get("tdd", {})
        command_ids = [tdd.get("red", {}).get("command_id"), tdd.get("green", {}).get("command_id")]
        command_ids.extend(value.get("command_id") for value in tdd.get("refactor", {}).get("invocations", []))
        command_ids.append(item.get("post_refactor_command_id"))
        for command_id in command_ids:
            command = commands.get(command_id)
            if not isinstance(command, dict):
                errors.append(f"command-unregistered:{slice_id}:{command_id}")
            elif command.get("shell") is not False:
                errors.append(f"command-shell-enabled:{slice_id}:{command_id}")
    return errors


def check_composition_fixtures() -> list[str]:
    try:
        fixtures = json.loads((PLAN_DIR / "fixtures" / "operability-cases.v1.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ["composition-fixtures-invalid"]
    cases = fixtures.get("cases") if isinstance(fixtures, dict) else None
    if not isinstance(cases, list) or not cases or fixtures.get("authorizes") != []:
        return ["composition-fixtures-invalid"]
    if any(not isinstance(item, dict) or not isinstance(item.get("case_id"), str) or item.get("authorizes", []) != [] for item in cases):
        return ["composition-fixture-authority-leak"]
    return []


def check_terminal_consumer_closure() -> list[str]:
    """Require every registered cross-skill consumer in the terminal predicate."""
    registered = set(TERMINAL_COMMAND_IDS)
    return [
        f"terminal-consumer-closure-missing:{command_id}"
        for command_id in sorted(REQUIRED_TERMINAL_CONSUMERS - registered)
    ]


def _expand(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict) or set(value) != {"type", "value"} or not isinstance(value["value"], str):
        raise ValueError("terminal command argument is invalid")
    if value["type"] == "plan_path":
        return (PLAN_DIR / value["value"]).relative_to(REPOSITORY_ROOT).as_posix()
    if value["type"] == "repo_path":
        return value["value"]
    raise ValueError("terminal command placeholder is unsupported")


def check_plan_and_tests() -> list[str]:
    registry = json.loads((PLAN_DIR / "command-registry.v1.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in registry["commands"]}
    errors: list[str] = []
    for command_id in TERMINAL_COMMAND_IDS:
        item = by_id.get(command_id)
        if not isinstance(item, dict) or item.get("shell") is not False:
            errors.append(f"terminal-command-unavailable:{command_id}")
            continue
        command = [item["executable"], *[_expand(value) for value in item["argv"]]]
        try:
            completed = subprocess.run(command, cwd=REPOSITORY_ROOT, capture_output=True, check=False, timeout=item["timeout_seconds"])
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"terminal-command-error:{command_id}:{type(exc).__name__}")
            continue
        if completed.returncode != 0:
            errors.append(f"terminal-command-failed:{command_id}")
    return errors


def validate_full(*, run_tests: bool = True, current_run_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    errors.extend(check_lifecycle_entry())
    errors.extend(check_slice_evidence())
    errors.extend(check_terminal_slice_evidence(current_run_dir or _latest_terminal_run()))
    errors.extend(check_contract_consistency())
    errors.extend(check_composition_fixtures())
    errors.extend(check_terminal_consumer_closure())
    if run_tests and not errors:
        errors.extend(check_plan_and_tests())
    return sorted(set(errors))


def result(errors: list[str]) -> dict[str, Any]:
    snapshot = _validation_snapshot()
    return {
        "schema_version": "jimuyun.bootstrap-review-operability-hardening.implementation-validation.v1",
        "terminalPredicateVersion": "v6",
        "status": "pass" if not errors else "fail",
        "predicate": "implementation-complete",
        "slice_id": "BROH-S7",
        "contract_hash": _contract_hash(),
        "errors": errors,
        **snapshot,
        "validation_snapshot": snapshot,
        "authorizes": [],
        "does_not_authorize": ["acceptance-passed", "commit", "release", "archived"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-tests", action="store_true")
    parser.add_argument("--current-run-dir", type=Path)
    args = parser.parse_args()
    errors = validate_full(run_tests=not args.no_tests, current_run_dir=args.current_run_dir)
    print(json.dumps(result(errors), sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

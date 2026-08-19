from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

try:
    from stage_lifecycle_runner import derive_run_state, validate_implementation_successor
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from stage_lifecycle_runner import derive_run_state, validate_implementation_successor


_IMPLEMENTATION_CANDIDATE_ROOTS = (
    "candidate_hash",
    "predicate_input_root",
    "authority_root",
    "validator_root",
    "validator_version",
    "closure_definition_hash",
)


def _verify_plan_context(repository_root: Path, plan_dir: Path) -> dict[str, object]:
    path = Path(__file__).with_name("knowledge_context.py")
    spec = importlib.util.spec_from_file_location("quick_dev_bound_knowledge_context", path)
    if spec is None or spec.loader is None:
        return {"status": "vdd-repair", "failure_code": "KWI-QUICK-FROZEN-CONTEXT-STALE"}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_plan_context(repository_root, plan_dir)


def _validation_snapshot(plan_dir: Path, slice_id: str | None = None) -> dict[str, str] | None:
    """Load the explicit plan's optional, read-only current-state projection.

    An implementation-candidate result is intentionally not contract-hash
    bound.  Plans that declare this predicate must instead expose the complete
    current root set through ``tools/validate_all.py::validation_snapshot``.
    Missing or malformed projections fail closed so a generic router never
    promotes an old candidate after a control-plane authority change.
    """
    validator = plan_dir / "tools" / "validate_all.py"
    if not validator.is_file():
        return None
    module_name = f"_tdd_adapter_plan_snapshot_{hashlib.sha256(str(plan_dir).encode('utf-8')).hexdigest()}"
    spec = importlib.util.spec_from_file_location(module_name, validator)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    previous_path = list(sys.path)
    try:
        sys.path.insert(0, str(validator.parent))
        spec.loader.exec_module(module)
        snapshot = module.slice_validation_snapshot(slice_id) if slice_id else module.validation_snapshot()
    except (AttributeError, ImportError, OSError, ValueError):
        return None
    finally:
        sys.path[:] = previous_path
        sys.modules.pop(module_name, None)
    if not isinstance(snapshot, dict):
        return None
    values = {key: snapshot.get(key) for key in _IMPLEMENTATION_CANDIDATE_ROOTS}
    return values if all(isinstance(value, str) and value for value in values.values()) else None


def _implementation_candidate_current(result: dict[str, object], current: dict[str, str] | None) -> bool:
    if current is None:
        return False
    return all(result.get(key) == current[key] for key in _IMPLEMENTATION_CANDIDATE_ROOTS)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _current_execution_fingerprint(repository_root: Path, plan_dir: Path, slice_id: str) -> str | None:
    """Build the current RED semantic identity without creating a run."""
    try:
        from build_slice_invocation import build

        context = build(repository_root, plan_dir, slice_id, "RECOVERY-PROBE")["run_context"]
        value = context["stage_results"]["red"]["execution_fingerprint"]
        return value if isinstance(value, str) and value else None
    except (ImportError, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def current_red_handoff(repository_root: Path, plan_dir: Path, slice_id: str) -> dict[str, str] | None:
    """Return the single current Quick Dev RED handoff for a slice.

    The handoff is continuity evidence only: its contract, selector, expected
    failures, and test bytes must still match the plan before it can seed a
    GREEN continuation.
    """
    root, plan = repository_root.resolve(), plan_dir.resolve()
    contract_path = plan / "implementation-contract.v1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    selected = next((item for item in contract.get("slices", []) if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict):
        return None
    if selected.get("execution_mode", "tdd") != "tdd":
        return None
    red = selected.get("tdd", {}).get("red") if isinstance(selected.get("tdd"), dict) else None
    if not isinstance(red, dict):
        return None
    selector = red.get("test_selector")
    if not isinstance(selector, str):
        return None
    evidence_root = root / "logs" / "tdd-adapter" / str(contract.get("plan_id")) / slice_id
    current_fingerprint = _current_execution_fingerprint(root, plan, slice_id)
    for handoff_path in sorted(evidence_root.glob("*/prior-red-handoff.v2.json"), reverse=True) if evidence_root.is_dir() else []:
        try:
            handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
            reference = handoff.get("red_observation")
            if (
                handoff.get("plan_id") == contract.get("plan_id")
                and handoff.get("slice_id") == slice_id
                and handoff.get("execution_fingerprint") == current_fingerprint
                and handoff.get("test_selector") == selector
                and handoff.get("expected_failure_ids") == red.get("expected_failure_ids")
                and isinstance(reference, dict)
                and set(reference) == {"path", "sha256"}
            ):
                return {"path": reference["path"], "sha256": reference["sha256"]}
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
            continue
    artifacts = sorted(evidence_root.glob("*/implementation-needed-result.json")) if evidence_root.is_dir() else []
    expected_contract = _sha(contract_path.read_bytes())
    expected_test_hash = _sha((root / selector).read_bytes()) if (root / selector).is_file() else None

    def valid_basis(path: Path) -> bool:
        try:
            basis = json.loads(path.read_text(encoding="utf-8"))
            intent = basis.get("failure_intent", {})
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
            return False
        return (
            basis.get("test_selector") == selector
            and basis.get("test_sha256") == expected_test_hash
            and basis.get("execution_fingerprint") == current_fingerprint
            and intent.get("expected_failure_ids") == red.get("expected_failure_ids")
        )
    valid: list[Path] = []
    for artifact in artifacts:
        try:
            value = json.loads(artifact.read_text(encoding="utf-8"))
            test_path = (root / selector).resolve()
            test_path.relative_to(root)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            continue
        contract_matches = value.get("contract_hash") == expected_contract
        if not contract_matches:
            historical = _historical_contract_and_registry(repository_root, plan_dir, value.get("contract_hash"))
            if historical is not None:
                try:
                    old_contract = json.loads(historical[0].decode("utf-8"))
                    old_registry = json.loads(historical[1].decode("utf-8"))
                    contract_matches = _slice_projection(old_contract, old_registry, slice_id) == _slice_projection(
                        json.loads(contract_path.read_text(encoding="utf-8")),
                        json.loads((plan_dir / "command-registry.v1.json").read_text(encoding="utf-8")),
                        slice_id,
                    )
                except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
                    contract_matches = False
        if (
            value.get("predicate") != "implementation-needed"
            or value.get("status") != "pass"
            or value.get("stage") != "red"
            or not contract_matches
            or value.get("test_selector") != selector
            or value.get("expected_failure_ids") != red.get("expected_failure_ids")
            or not isinstance(value.get("exit_code"), int)
            or value["exit_code"] == 0
            or not test_path.is_file()
            or value.get("test_hash") != _sha(test_path.read_bytes())
        ):
            continue
        valid.append(artifact)
    if len(valid) != 1:
        # Compatibility bridge for staged runs that recorded the RED result
        # before the implementation-needed sidecar was introduced. The
        # observation remains the authoritative nonzero execution proof; the
        # red-result binds selector/failure intent and contract projection.
        legacy: list[tuple[Path, Path]] = []
        for result_path in sorted(evidence_root.glob("*/red-result.json")):
            observation_path = result_path.parent / "observations" / "red-observed.json"
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
                observation = json.loads(observation_path.read_text(encoding="utf-8"))
                test_path = (root / selector).resolve()
                test_path.relative_to(root)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                continue
            if (
                result.get("stage") != "red"
                or result.get("slice_id") != slice_id
                or result.get("test_selector") != selector
                or result.get("expected_failure_ids") != red.get("expected_failure_ids")
                or observation.get("stage") != "red"
                or not isinstance(observation.get("exit_code"), int)
                or observation.get("exit_code") == 0
                or not test_path.is_file()
                or not valid_basis(result_path.parent / "red-basis.v1.json")
            ):
                continue
            legacy.append((result_path, observation_path))
        if not legacy:
            # The oldest staged shape contains only the canonical RED basis and
            # its immutable failed observation.  It is safe only when both
            # current executable identity and current test bytes still match.
            for basis_path in sorted(evidence_root.glob("*/red-basis.v1.json")):
                observation_path = basis_path.parent / "observations" / "red-observed.json"
                try:
                    observation = json.loads(observation_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    continue
                if (
                    valid_basis(basis_path)
                    and observation.get("stage") == "red"
                    and isinstance(observation.get("exit_code"), int)
                    and observation["exit_code"] != 0
                ):
                    legacy.append((basis_path, observation_path))
        if not legacy:
            return None
        # Multiple interrupted attempts may exist; the newest matching RED is
        # the recoverable predecessor when all candidates describe the same
        # selector/failure intent.
        observation_path = sorted(legacy, key=lambda item: item[0].parent.name)[-1][1]
        return {"path": observation_path.relative_to(root).as_posix(), "sha256": _sha(observation_path.read_bytes())}
    artifact = valid[0]
    return {"path": artifact.relative_to(root).as_posix(), "sha256": _sha(artifact.read_bytes())}


def _head_artifact_bytes(repository_root: Path, relative: Path) -> bytes | None:
    """Read an immutable HEAD artifact for independent-slice freshness checks."""
    completed = subprocess.run(
        ["git", "-C", str(repository_root), "show", f"HEAD:{relative.as_posix()}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout if completed.returncode == 0 else None


def _historical_contract_and_registry(
    repository_root: Path,
    plan_dir: Path,
    contract_hash: str,
) -> tuple[bytes, bytes] | None:
    """Resolve immutable producer inputs for a legacy slice receipt."""
    root = repository_root.resolve()
    contract_path = plan_dir.resolve().relative_to(root).as_posix()
    registry_path = (plan_dir / "command-registry.v1.json").resolve().relative_to(root).as_posix()
    commits = subprocess.run(
        ["git", "-C", str(root), "log", "--all", "--format=%H", "--", contract_path],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    for commit in commits.stdout.splitlines():
        contract = subprocess.run(
            ["git", "-C", str(root), "show", f"{commit}:{contract_path}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if contract.returncode != 0 or _sha(contract.stdout) != contract_hash:
            continue
        registry = subprocess.run(
            ["git", "-C", str(root), "show", f"{commit}:{registry_path}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return contract.stdout, registry.stdout if registry.returncode == 0 else b'{"commands":[]}'
    return None


def _slice_projection(contract: dict[str, object], registry: dict[str, object], slice_id: str) -> str | None:
    """Hash the slice and recursive dependencies, plus their command descriptors."""
    declared = contract.get("slices")
    commands = registry.get("commands")
    if not isinstance(declared, list) or not isinstance(commands, list):
        return None
    by_id = {item.get("slice_id"): item for item in declared if isinstance(item, dict)}
    if slice_id not in by_id or len(by_id) != len(declared):
        return None
    ordered: list[str] = []
    visiting: set[str] = set()

    def visit(current: str) -> bool:
        if current in visiting:
            return False
        if current in ordered:
            return True
        item = by_id.get(current)
        if not isinstance(item, dict):
            return False
        visiting.add(current)
        dependencies = item.get("depends_on", [])
        if not isinstance(dependencies, list) or any(not isinstance(value, str) for value in dependencies):
            return False
        if not all(visit(value) for value in dependencies):
            return False
        visiting.remove(current)
        ordered.append(current)
        return True

    if not visit(slice_id):
        return None
    command_ids: set[str] = set()
    for current in ordered:
        item = by_id[current]
        tdd = item.get("tdd", {})
        if isinstance(tdd, dict):
            for stage in ("red", "green"):
                value = tdd.get(stage, {})
                if isinstance(value, dict) and isinstance(value.get("command_id"), str):
                    command_ids.add(value["command_id"])
            refactor = tdd.get("refactor", {})
            if isinstance(refactor, dict) and isinstance(refactor.get("invocations"), list):
                for invocation in refactor["invocations"]:
                    if isinstance(invocation, dict) and isinstance(invocation.get("command_id"), str):
                        command_ids.add(invocation["command_id"])
        if isinstance(item.get("post_refactor_command_id"), str):
            command_ids.add(item["post_refactor_command_id"])
    command_by_id = {item.get("id"): item for item in commands if isinstance(item, dict)}
    if any(command_id not in command_by_id for command_id in command_ids):
        return None
    payload = {
        "plan_id": contract.get("plan_id"),
        "slices": [by_id[current] for current in ordered],
        "commands": [command_by_id[current] for current in sorted(command_ids)],
    }
    return _sha(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _unaffected_slice_current(
    repository_root: Path,
    plan_dir: Path,
    contract: dict[str, object],
    registry: dict[str, object],
    result: dict[str, object],
    slice_id: str,
) -> bool:
    """Reuse a predecessor result only when its exact slice projection is unchanged."""
    current_fingerprint = _current_execution_fingerprint(repository_root.resolve(), plan_dir, slice_id)
    if isinstance(result.get("execution_fingerprint"), str):
        return result["execution_fingerprint"] == current_fingerprint
    root = repository_root.resolve()
    contract_path = plan_dir / "implementation-contract.v1.json"
    current_bytes = _head_artifact_bytes(root, contract_path.resolve().relative_to(root))
    if current_bytes is None:
        return False
    if result.get("contract_hash") == _sha(current_bytes):
        baseline_bytes = current_bytes
        registry_path = plan_dir / "command-registry.v1.json"
        baseline_registry_bytes = _head_artifact_bytes(root, registry_path.resolve().relative_to(root)) or b'{"commands":[]}'
    else:
        historical = _historical_contract_and_registry(root, plan_dir, str(result.get("contract_hash")))
        if historical is None:
            return False
        baseline_bytes, baseline_registry_bytes = historical
    try:
        baseline_contract = json.loads(baseline_bytes.decode("utf-8"))
        baseline_registry = json.loads(baseline_registry_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return False
    current_projection = _slice_projection(contract, registry, slice_id)
    baseline_projection = _slice_projection(baseline_contract, baseline_registry, slice_id)
    return current_projection is not None and current_projection == baseline_projection


def _terminal_completion_current(repository_root: Path, plan_dir: Path, contract_hash: str) -> bool:
    contract = json.loads((plan_dir / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    terminal = contract.get("terminal")
    if not isinstance(terminal, dict) or terminal.get("predicate") != "implementation-complete":
        return False
    evidence = repository_root / "logs" / "tdd-adapter" / contract["plan_id"] / "terminal"
    for path in sorted(evidence.glob("*/implementation-complete-result.json"), reverse=True):
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (
            result.get("predicate") == "implementation-complete"
            and result.get("status") == "pass"
            and (contract.get("plan_id") != "quick-dev-tdd-stage-recovery" or result.get("orchestration_version") == "stage-actions.v2")
            and result.get("plan_id") == contract["plan_id"]
            and result.get("contract_hash") == contract_hash
            and result.get("terminal_command_id") == terminal.get("command_id")
            and isinstance(result.get("validated_command_ids"), list)
            and result.get("authorizes") == ["implementation-complete"]
        ):
            return True
    return False


def _active_slice_action(repository_root: Path, plan_id: str, slice_id: str) -> str | None:
    evidence_root = repository_root / "logs" / "tdd-adapter" / plan_id / slice_id
    candidates = sorted((path for path in evidence_root.glob("RUN-*") if path.is_dir()), key=lambda path: path.name, reverse=True)
    for run_dir in candidates:
        action = derive_run_state(run_dir)
        if action == "slice-terminal":
            return "validate-slice"
        if action == "implement":
            return "implement"
        if action in {"green", "refactor"}:
            return "run-slice"
    return None


def next_stage_action(stages: list[str]) -> str:
    """Return the only legal successor for an observed stage prefix."""
    transitions = {(): "red", ("red",): "implement", ("red", "implement"): "green", ("red", "implement", "green"): "refactor", ("red", "implement", "green", "refactor"): "slice-terminal"}
    key = tuple(stages)
    if key not in transitions:
        raise ValueError("stage observations are not an ordered lifecycle prefix")
    return transitions[key]


def _staged_refactor_complete(result_path: Path) -> bool:
    try:
        state = json.loads(result_path.with_name("stage-state.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return state.get("stage") == "refactor"


def _slice_authorization_gate(plan_dir: Path, plan_id: str) -> dict[str, object] | None:
    state_path = plan_dir / "plan-state.v1.json"
    if not state_path.is_file():
        return None
    try:
        document = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {
            "next_action": "external-repair-required",
            "reason": "invalid-plan-state",
            "authorizes": [],
        }
    if not isinstance(document, dict):
        return {
            "next_action": "external-repair-required",
            "reason": "invalid-plan-state",
            "authorizes": [],
        }
    current_state = document.get("status")
    legacy_state = document.get("state")
    if (
        isinstance(current_state, str)
        and isinstance(legacy_state, str)
        and current_state != legacy_state
    ):
        return {
            "next_action": "external-repair-required",
            "reason": "invalid-plan-state",
            "authorizes": [],
        }
    lifecycle_state = current_state if isinstance(current_state, str) else legacy_state
    if (
        document.get("plan_id") != plan_id
        or not isinstance(lifecycle_state, str)
        or not isinstance(document.get("authorizes"), list)
    ):
        return {
            "next_action": "external-repair-required",
            "reason": "invalid-plan-state",
            "authorizes": [],
        }
    if lifecycle_state == "implementation-authorized":
        if document["authorizes"] == ["plan-ready", "implementation-authorized"]:
            repair_state_path = plan_dir / "repair" / "round-1" / "repair-state.v1.json"
            try:
                repair_state = json.loads(repair_state_path.read_text(encoding="utf-8"))
                if (
                    repair_state.get("status") != "closed"
                    or repair_state.get("blocks_execution") is not False
                    or repair_state.get("authorizes") != []
                ):
                    return {
                        "next_action": "external-repair-required",
                        "reason": "repair-state-not-closed",
                        "authorizes": [],
                    }
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
                return {
                    "next_action": "external-repair-required",
                    "reason": "repair-state-invalid",
                    "authorizes": [],
                }
            receipt_path = plan_dir / "implementation-authorization-receipt.successor.v1.json"
            if not receipt_path.is_file():
                return {
                    "next_action": "awaiting-implementation-authorization",
                    "reason": "implementation-authorization-receipt-missing",
                    "authorizes": [],
                }
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if (
                    receipt.get("plan_id") != plan_id
                    or receipt.get("decision", {}).get("owner") != "maintainer"
                    or receipt.get("decision", {}).get("transition") != "implementation-authorized"
                    or receipt.get("authorizes") != ["implementation-authorized"]
                ):
                    raise ValueError("receipt metadata mismatch")
                bindings = (
                    "implementation_contract",
                    "command_registry",
                    "authority_manifest",
                    "knowledge_context",
                    "knowledge_context_freeze",
                    "skill_input_receipt",
                    "skill_input_request",
                    "plan_validation",
                    "repair_closure",
                    "bootstrap_preexisting_delta",
                    "candidate_manifest",
                    "validate_all",
                    "terminal_validator",
                    "immutable_predecessor",
                )
                root = plan_dir.resolve().parents[1]
                for field in bindings:
                    binding = receipt.get(field)
                    if not isinstance(binding, dict) or not isinstance(binding.get("path"), str) or not isinstance(binding.get("sha256"), str):
                        raise ValueError("receipt binding missing")
                    path = (root / binding["path"]).resolve()
                    path.relative_to(root)
                    if not path.is_file() or _sha(path.read_bytes()) != binding["sha256"]:
                        raise ValueError("receipt binding stale")
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
                return {
                    "next_action": "awaiting-implementation-authorization",
                    "reason": "implementation-authorization-stale",
                    "authorizes": [],
                }
            return None
        return {
            "next_action": "external-repair-required",
            "reason": "invalid-plan-state",
            "authorizes": [],
        }
    if lifecycle_state in {"draft", "plan-ready"}:
        expected = [] if lifecycle_state == "draft" else ["plan-ready"]
        if document["authorizes"] != expected:
            return {
                "next_action": "external-repair-required",
                "reason": "invalid-plan-state",
                "authorizes": [],
            }
        return {
            "next_action": "awaiting-implementation-authorization",
            "reason": "implementation-authorization-required",
            "authorizes": [],
        }
    return {
        "next_action": "external-repair-required",
        "reason": "plan-state-precludes-slice-execution",
        "authorizes": [],
    }


def route(repository_root: Path, plan_dir: Path) -> dict[str, object]:
    execution_root = (repository_root / "execution-plans").resolve()
    target = plan_dir.resolve()
    try:
        target.relative_to(execution_root)
    except ValueError as exc:
        raise ValueError("plan directory must stay under execution-plans") from exc
    knowledge = _verify_plan_context(repository_root, target)
    if knowledge["status"] == "successor-required":
        return {"next_action": "refresh-knowledge-context", "reason": knowledge["failure_code"], "authorizes": []}
    if knowledge["status"] == "vdd-repair":
        return {"next_action": "external-repair-required", "reason": knowledge["failure_code"], "authorizes": []}
    contract_path = target / "implementation-contract.v1.json"
    contract_bytes = contract_path.read_bytes()
    contract = json.loads(contract_bytes.decode("utf-8"))
    try:
        registry = json.loads((target / "command-registry.v1.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        registry = {}
    contract_hash = "sha256:" + hashlib.sha256(contract_bytes).hexdigest()
    if not isinstance(contract.get("plan_id"), str) or not isinstance(contract.get("slices"), list):
        raise ValueError("implementation contract is invalid")
    reports = sorted(target.glob("95-*.md"), key=lambda item: item.name.casefold())
    if len(reports) > 1:
        return {"next_action": "external-repair-required", "reason": "ambiguous-plan-report", "authorizes": []}
    evidence_root = repository_root / "logs" / "tdd-adapter" / contract["plan_id"]
    state = evidence_root / "run-state.v1.json"
    if state.is_file():
        value = json.loads(state.read_text(encoding="utf-8"))
        if value.get("failure_fingerprint") and value.get("repeat_count", 0) >= 2:
            return {"next_action": "stop", "reason": "repeated-failure-fingerprint", "authorizes": []}
    completed: set[str] = set()
    for slice_item in contract["slices"]:
        slice_id = slice_item.get("slice_id")
        if not isinstance(slice_id, str):
            raise ValueError("slice id is invalid")
        execution_mode = slice_item.get("execution_mode", "tdd")
        exit_predicate = slice_item.get("exit_predicate", "slice-ready")
        if not isinstance(exit_predicate, str) or not exit_predicate:
            raise ValueError("slice exit predicate is invalid")
        for result_path in (evidence_root / slice_id).glob(f"*/{exit_predicate}-result.json"):
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            contract_current = result.get("contract_hash") == contract_hash
            required_artifact = result_path.with_name("candidate-evidence.json") if exit_predicate == "implementation-candidate" else None
            current = contract_current
            if exit_predicate == "implementation-candidate":
                current = _implementation_candidate_current(
                    result, _validation_snapshot(target, slice_id)
                )
            elif all(key in result for key in _IMPLEMENTATION_CANDIDATE_ROOTS):
                # RMAP validation envelopes (including slice-ready) own
                # freshness through current roots rather than contract_hash.
                # Compare every root, not only the candidate hash, so a
                # control-plane authority update cannot be skipped.
                current = _implementation_candidate_current(
                    result,
                    _validation_snapshot(
                        target,
                        None if exit_predicate == "implementation-complete" else slice_id,
                    ),
                )
            elif not contract_current and isinstance(registry, dict):
                current = _unaffected_slice_current(
                    repository_root, target, contract, registry, result, slice_id
                )
            if result.get("predicate") == exit_predicate and result.get("status") == "pass" and (contract.get("plan_id") != "quick-dev-tdd-stage-recovery" or (result.get("orchestration_version") == "stage-actions.v2" and _staged_refactor_complete(result_path))) and current and (required_artifact is None or required_artifact.is_file()):
                completed.add(slice_id)
                break
    for slice_item in contract["slices"]:
        slice_id = slice_item["slice_id"]
        execution_mode = slice_item.get("execution_mode", "tdd")
        if slice_id in completed:
            continue
        if not set(slice_item.get("depends_on", [])).issubset(completed):
            continue
        authorization_gate = _slice_authorization_gate(target, contract["plan_id"])
        if authorization_gate is not None:
            return authorization_gate
        active_action = _active_slice_action(repository_root, contract["plan_id"], slice_id)
        if active_action == "validate-slice":
            return {"next_action": "validate-slice", "slice_id": slice_id, "authorizes": []}
        if active_action == "implement":
            return {"next_action": "implement", "slice_id": slice_id, "authorizes": []}
        if execution_mode in {"regression", "dogfood-replay"}:
            return {"next_action": "validate-slice", "slice_id": slice_id, "execution_mode": execution_mode, "authorizes": []}
        return {"next_action": "run-slice", "slice_id": slice_id, "authorizes": []}
    if _terminal_completion_current(repository_root, target, contract_hash):
        return {"next_action": "implementation-complete", "authorizes": []}
    return {"next_action": "validate-terminal", "authorizes": []}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--caller", required=True)
    args = parser.parse_args()
    if args.caller != "quick-dev-tdd-adapter":
        parser.error("--caller must be quick-dev-tdd-adapter")
    print(json.dumps(route(args.repository_root.resolve(), args.plan_dir.resolve()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


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


def route(repository_root: Path, plan_dir: Path) -> dict[str, object]:
    execution_root = (repository_root / "execution-plans").resolve()
    target = plan_dir.resolve()
    try:
        target.relative_to(execution_root)
    except ValueError as exc:
        raise ValueError("plan directory must stay under execution-plans") from exc
    knowledge = _verify_plan_context(repository_root, target)
    if knowledge["status"] == "vdd-repair":
        return {"next_action": "external-repair-required", "reason": knowledge["failure_code"], "authorizes": []}
    contract_path = target / "implementation-contract.v1.json"
    contract_bytes = contract_path.read_bytes()
    contract = json.loads(contract_bytes.decode("utf-8"))
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
        exit_predicate = slice_item.get("exit_predicate", "slice-ready")
        if not isinstance(exit_predicate, str) or not exit_predicate:
            raise ValueError("slice exit predicate is invalid")
        for result_path in (evidence_root / slice_id).glob(f"*/{exit_predicate}-result.json"):
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if (result_path.parent / "targeted-validation.v1.json").is_file():
                continue
            contract_current = result.get("contract_hash") == contract_hash
            required_artifact = result_path.with_name("candidate-evidence.json") if exit_predicate == "implementation-candidate" else None
            current = contract_current
            if all(key in result for key in _IMPLEMENTATION_CANDIDATE_ROOTS):
                # RMAP validation envelopes (including slice-ready) own
                # freshness through current roots rather than contract_hash.
                # Compare every root, not only the candidate hash, so a
                # control-plane authority update cannot be skipped.
                current = _implementation_candidate_current(result, _validation_snapshot(target, slice_id))
            if result.get("predicate") == exit_predicate and result.get("status") == "pass" and current and (required_artifact is None or required_artifact.is_file()):
                completed.add(slice_id)
                break
    for slice_item in contract["slices"]:
        slice_id = slice_item["slice_id"]
        if slice_id in completed:
            continue
        if not set(slice_item.get("depends_on", [])).issubset(completed):
            continue
        return {"next_action": "run-slice", "slice_id": slice_id, "authorizes": []}
    return {"next_action": "validate-terminal", "authorizes": []}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(route(args.repository_root.resolve(), args.plan_dir.resolve()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

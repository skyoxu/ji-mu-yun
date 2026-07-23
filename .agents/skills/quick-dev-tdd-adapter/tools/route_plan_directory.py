from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def route(repository_root: Path, plan_dir: Path) -> dict[str, object]:
    execution_root = (repository_root / "execution-plans").resolve()
    target = plan_dir.resolve()
    try:
        target.relative_to(execution_root)
    except ValueError as exc:
        raise ValueError("plan directory must stay under execution-plans") from exc
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
            contract_current = result.get("contract_hash") == contract_hash
            candidate_hash = result.get("candidate_hash")
            candidate_current = (
                isinstance(candidate_hash, str)
                and candidate_hash == result.get("current_candidate_hash")
                and candidate_hash == result.get("predicate_input_root")
            )
            required_artifact = result_path.with_name("candidate-result.json") if exit_predicate == "implementation-candidate" else None
            if result.get("predicate") == exit_predicate and result.get("status") == "pass" and (contract_current or candidate_current) and (required_artifact is None or required_artifact.is_file()):
                completed.add(slice_id)
                break
    for slice_item in contract["slices"]:
        slice_id = slice_item["slice_id"]
        if slice_id in completed:
            continue
        if not set(slice_item.get("depends_on", [])).issubset(completed):
            continue
        if slice_id == "RMAP-S7":
            return {"next_action": "await-external-envelope", "slice_id": slice_id, "authorizes": []}
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

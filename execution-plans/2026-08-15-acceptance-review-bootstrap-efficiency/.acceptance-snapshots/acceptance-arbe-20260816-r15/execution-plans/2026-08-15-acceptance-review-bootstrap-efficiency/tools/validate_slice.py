from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PLAN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLAN_ROOT.parents[1]
PLAN_ID = "acceptance-review-bootstrap-efficiency"


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _observation(path: Path, stage: str) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("stage") != stage or not isinstance(value.get("exit_code"), int):
        raise ValueError(f"{stage} observation is invalid")
    return value


def _validate_prior_red_successor(run: Path, selected: dict[str, object], contract_hash: str) -> None:
    red = selected["tdd"]["red"]
    prior = red.get("prior_red")
    if not isinstance(prior, dict) or set(prior) != {"path", "sha256"}:
        raise ValueError("prior RED successor contract is invalid")
    path, expected_hash = prior["path"], prior["sha256"]
    if not isinstance(path, str) or not isinstance(expected_hash, str):
        raise ValueError("prior RED successor reference is invalid")
    root = REPOSITORY_ROOT.resolve()
    predecessor = (root / path).resolve()
    try:
        predecessor.relative_to(root)
    except ValueError as exc:
        raise ValueError("prior RED successor reference escapes repository") from exc
    raw = predecessor.read_bytes()
    if _sha(raw) != expected_hash:
        raise ValueError("prior RED successor hash is stale")
    prior_observation = _observation(predecessor, "red")
    if (
        prior_observation["exit_code"] == 0
        or not isinstance(prior_observation.get("commands_attempted"), list)
        or red.get("command_id") not in prior_observation.get("commands_attempted", [])
    ):
        raise ValueError("prior RED successor does not bind a matching failed RED")
    evidence_path = run / "prior-red-successor-evidence.v1.json"
    if (run / "observations" / "red-observed.json").exists() or not evidence_path.is_file():
        raise ValueError("prior RED successor evidence shape is invalid")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": "quick-dev-tdd-adapter.prior-red-successor-evidence.v1",
        "plan_id": PLAN_ID,
        "slice_id": selected["slice_id"],
        "run_id": run.name,
        "prior_red": prior,
        "red_command_id": red.get("command_id"),
        "green_command_id": selected["tdd"]["green"].get("command_id"),
        "refactor_command_ids": [item.get("command_id") for item in selected["tdd"]["refactor"].get("invocations", [])],
        "current_contract_hash": contract_hash,
        "green_exit_code": 0,
        "refactor_exit_code": 0,
        "authorizes": [],
    }
    if evidence != expected:
        raise ValueError("prior RED successor evidence is invalid")


def validate(run_dir: Path, slice_id: str) -> dict[str, object]:
    contract_path = PLAN_ROOT / "implementation-contract.v1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    selected = next((item for item in contract.get("slices", []) if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict):
        raise ValueError("slice is not declared")
    expected_root = REPOSITORY_ROOT / "logs" / "tdd-adapter" / PLAN_ID / slice_id
    run = run_dir.resolve()
    try:
        run.relative_to(expected_root.resolve())
    except ValueError as exc:
        raise ValueError("run directory escapes plan evidence root") from exc
    red_mode = selected["tdd"]["red"].get("mode", "red")
    successor = red_mode == "prior-red-successor"
    stages = ("green", "refactor") if successor else ("red", "green", "refactor")
    observations = {stage: _observation(run / "observations" / f"{stage}-observed.json", stage) for stage in stages}
    legacy = red_mode == "legacy-regression"
    if legacy:
        if observations["red"]["exit_code"] != 0 or not (run / "legacy-regression-evidence.json").is_file():
            raise ValueError("legacy regression evidence is invalid")
    elif successor:
        _validate_prior_red_successor(run, selected, _sha(contract_path.read_bytes()))
    elif observations["red"]["exit_code"] == 0:
        raise ValueError("RED observation unexpectedly passed")
    if observations["green"]["exit_code"] != 0 or observations["refactor"]["exit_code"] != 0:
        raise ValueError("GREEN or REFACTOR observation failed")
    projection = run / "stage-evidence-projection.v1.json"
    if not projection.is_file():
        raise ValueError("stage evidence projection is missing")
    return {
        "schema_version": "acceptance-review-bootstrap-efficiency.slice-validation.v1",
        "status": "pass",
        "predicate": "slice-ready",
        "plan_id": PLAN_ID,
        "slice_id": slice_id,
        "run_id": run.name,
        "contract_hash": _sha(contract_path.read_bytes()),
        "evidence_mode": "legacy-regression" if legacy else "prior-red-successor" if successor else "red-green-refactor",
        "authorizes": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.run_dir, args.slice_id), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

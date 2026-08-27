"""Build a hash-bound, run-local input manifest from formal predecessor runs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


FIXTURE_RED_SELECTORS = (
    "red_s1_semantic_artifact.py", "red_s2_descriptor_producer.py", "red_s3_judge_producer.py",
    "red_s4_coverage_producer.py", "red_s5_promotion_producer.py", "red_s6_terminal_producer.py",
    "red_s1_semantic_artifact.py", "red_s2_descriptor_producer.py", "red_s3_judge_producer.py",
)


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _repository_root(run_root: Path) -> Path:
    logs = next((parent for parent in run_root.resolve().parents if parent.name == "logs"), None)
    if logs is None:
        raise ValueError("run root is outside formal logs")
    return logs.parent


def _formal_artifact(root: Path, run_root: Path, slice_id: str, name: str) -> dict[str, str]:
    """Resolve only the explicit predecessor ref supplied by the lifecycle."""
    pointer = run_root / "predecessor-slice-ready-ref.v1.json"
    try:
        pointer_value = json.loads(pointer.read_text(encoding="utf-8"))
        result_ref = pointer_value["result"]
        result = (root / result_ref["path"]).resolve()
        result.relative_to(root / "logs" / "tdd-adapter")
        if not result.is_file() or _sha(result) != result_ref["sha256"]:
            raise ValueError("predecessor result is stale")
        result_value = json.loads(result.read_text(encoding="utf-8"))
        if result_value.get("slice_id") != slice_id or result_value.get("run_id") != result.parent.name:
            raise ValueError("predecessor result identity is invalid")
        candidates = [ref for ref in result_value.get("produced_artifact_refs", []) if isinstance(ref, dict) and ref.get("path", "").endswith("/" + name)]
        if len(candidates) != 1:
            raise ValueError("predecessor artifact ref is missing or ambiguous")
        artifact = (root / candidates[0]["path"]).resolve()
        artifact.relative_to(result.parent)
        if not artifact.is_file() or _sha(artifact) != candidates[0]["sha256"]:
            raise ValueError("predecessor artifact is stale")
        value = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("formal predecessor artifact is invalid") from exc
    if value.get("slice_id") != slice_id or value.get("run_id") != artifact.parent.name:
        raise ValueError("formal predecessor artifact identity is invalid")
    return {
        "path": artifact.relative_to(root).as_posix(), "sha256": _sha(artifact),
        "producer": str(value.get("producer", "")), "slice_id": slice_id, "run_id": artifact.parent.name,
    }


def build(plan_dir: Path, run_root: Path, slice_id: str) -> dict[str, object]:
    plan = plan_dir.resolve()
    root = _repository_root(run_root)
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    plan_id = contract.get("plan_id")
    if not isinstance(plan_id, str) or run_root.parent.name != slice_id or not run_root.name.startswith("RUN-"):
        raise ValueError("run input identity is invalid")
    refs = lambda predecessor, artifact: {"artifact_ref": _formal_artifact(root, run_root, predecessor, artifact)}
    inputs: dict[str, dict[str, object]]
    if slice_id == "S1":
        inputs = {"semantic-intent-input.v1.json": {
            "acceptance_ids": ["A-SEMANTIC"], "producer": "vdd", "coverage": "exact-cover",
            "covers_acceptance_ids": ["A-SEMANTIC"], "fixture_class": "positive",
            "taxonomy": ["outcome", "failure_family", "failure_id"], "rollback": "deferred",
            "oracle_id": "semantic-oracle", "oracle_class": "contract", "test_selector": "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/red_s1_semantic_artifact.py",
            "subject_role": "sut", "required_case_roles": ["positive", "negative", "mutation"], "red_failure_family": "semantic-contract-gap",
            "expected_failure_ids": ["VDD-SEMANTIC-MINIMUM-CASES"], "green_expected_observations": ["semantic-artifacts.v1.json"],
            "minimum_executed_cases": 3, "independent_judge_required": True, "case_source_refs": ["SPEC:FR-1", "SPEC:FR-2", "SPEC:FR-10"],
            "case_producer_ref": "vdd-semantic-fixture-owner", "complexity_class": "complex", "verification_lane": "self-hosted",
            "context_lookup_required": False, "context_lookup_reason": "repository-owned", "minimum_red_scope": "semantic", "upgrade_conditions": [],
        }}
    elif slice_id == "S2":
        inputs = {
            "descriptor-input.v1.json": {"descriptor": {"target": "semantic-oracle", "argv": [sys.executable, "-m", "pytest", "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/test_semantic_negative.py", "-q"], "cwd": ".", "timeout_seconds": 30, "shell": False, "case_source_refs": ["active-acceptance-manifest"], "case_producer_ref": "vdd"}},
            "semantic-artifacts.v1.json": refs("S1", "semantic-artifacts.v1.json"),
        }
    elif slice_id == "S3":
        inputs = {
            "execution-input.v1.json": {"argv": [sys.executable, "-m", "pytest", "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/test_s2_descriptor_negative.py", "-q"], "executor_id": "sut-executor", "observation_id": "OBS-S3", "candidate_hash": _sha(plan / "implementation-contract.v1.json")},
            "execution-descriptor.v1.json": refs("S2", "execution-descriptor.v1.json"),
        }
    elif slice_id == "S4":
        inputs = {
            "coverage-input.v1.json": {"acceptance_ids": ["A-COVER"], "observation_ids": ["OBS-S3"], "edges": [{"acceptance_id": "A-COVER", "case_id": "CASE-S4", "observation_id": "OBS-S3"}]},
            "process-receipt.v1.json": refs("S3", "process-receipt.v1.json"),
        }
    elif slice_id == "S5":
        inputs = {
            "false-green-fixture-input.v1.json": {"fixtures": [{"fixture_id": f"FG-{index:02d}", "blocked_argv": [sys.executable, "-m", "pytest", f"execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/{selector}", "-q"], "corrected_argv": [sys.executable, "-m", "pytest", "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/test_semantic_negative.py", "-q"]} for index, selector in enumerate(FIXTURE_RED_SELECTORS, start=1)]},
            "acceptance-coverage.v1.json": refs("S4", "acceptance-coverage.v1.json"),
        }
    else:
        raise ValueError("slice does not consume run inputs")
    payload: dict[str, object] = {
        "schema_version": "quick-dev-tdd-adapter.run-inputs.v1", "plan_id": plan_id,
        "slice_id": slice_id, "run_id": run_root.name, "inputs": inputs,
    }
    payload["manifest_sha256"] = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--slice", required=True)
    args = parser.parse_args()
    value = build(args.plan_dir, args.run_root, args.slice)
    output = args.run_root / "run-inputs.v1.json"
    output.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

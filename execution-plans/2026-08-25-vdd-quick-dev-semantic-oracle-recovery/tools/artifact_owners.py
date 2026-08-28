"""Run-local evidence producers for the self-hosted verification plan."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from semantic_oracle import compile_run_local_semantic_artifacts, validate_descriptor, validate_judge, validate_many_to_many_cover, validate_promotion
from terminal_validator import publish_terminal_evidence


def _digest(value: dict) -> str:
    body = {key: item for key, item in value.items() if key != "evidence_sha256"}
    return "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _write(path: Path, value: dict) -> dict:
    value["evidence_sha256"] = _digest(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    return value


def _input(run_root: Path, name: str) -> dict:
    path = run_root / name
    if not path.is_file():
        raise FileNotFoundError(name)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid object: {name}")
    return value


def _bound(value: dict, producer: str, slice_id: str, run_id: str) -> bool:
    return value.get("producer") == producer and value.get("status") == "pass" and value.get("slice_id") == slice_id and value.get("run_id") == run_id and value.get("evidence_sha256") == _digest(value)


def _artifact(run_root: Path, name: str, producer: str, slice_id: str) -> dict:
    value = _input(run_root, name)
    reference = value.get("artifact_ref") if isinstance(value, dict) else None
    if not isinstance(reference, dict):
        return value
    required = {"path", "sha256", "producer", "slice_id", "run_id"}
    if set(reference) != required or reference["producer"] != producer or reference["slice_id"] != slice_id:
        raise ValueError("artifact reference is invalid")
    logs = next((parent for parent in run_root.resolve().parents if parent.name == "logs"), None)
    if logs is None or not isinstance(reference["path"], str) or not isinstance(reference["sha256"], str):
        raise ValueError("artifact reference is invalid")
    target = (logs.parent / reference["path"]).resolve()
    try:
        target.relative_to(logs.parent)
    except ValueError as exc:
        raise ValueError("artifact reference escapes repository") from exc
    if not target.is_file() or "DIAGNOSTIC" in target.as_posix().upper() or "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest() != reference["sha256"]:
        raise ValueError("artifact reference is stale")
    artifact = json.loads(target.read_text(encoding="utf-8"))
    if not _bound(artifact, producer, slice_id, reference["run_id"]):
        raise ValueError("artifact reference is unbound")
    return artifact


def produce_descriptor(run_root: Path) -> dict:
    source, semantic = _input(run_root, "descriptor-input.v1.json"), _input(run_root, "semantic-artifacts.v1.json")
    descriptor = source.get("descriptor")
    valid, failure = validate_descriptor(descriptor)
    semantic = _artifact(run_root, "semantic-artifacts.v1.json", "vdd", "S1")
    if not valid or not _bound(semantic, "vdd", "S1", semantic["run_id"]):
        raise ValueError(failure or "semantic-artifacts-unbound")
    result = _write(run_root / "execution-descriptor.v1.json", {"schema_version":"execution-descriptor.v1", "producer":"quick-dev", "status":"pass", "slice_id":"S2", "run_id":run_root.name, "descriptor":descriptor, "semantic_artifact_hash":semantic["evidence_sha256"]})
    return result


def produce_receipt(run_root: Path) -> dict:
    source, descriptor = _input(run_root, "execution-input.v1.json"), _artifact(run_root, "execution-descriptor.v1.json", "quick-dev", "S2")
    argv = descriptor.get("descriptor", {}).get("argv") if isinstance(descriptor.get("descriptor"), dict) else None
    if not _bound(descriptor, "quick-dev", "S2", descriptor["run_id"]) or not isinstance(argv, list) or not argv or any(not isinstance(x, str) for x in argv):
        raise ValueError("execution-input-invalid")
    descriptor_value = descriptor["descriptor"]
    cwd_value = descriptor_value.get("cwd", ".")
    repo_root = next((parent for parent in run_root.resolve().parents if parent.name == "logs"), None)
    cwd = (repo_root.parent / cwd_value).resolve() if repo_root else run_root
    if repo_root is None:
        # Unit-level owner tests use an isolated temporary run root; formal
        # lifecycle runs always resolve through the repository logs root.
        cwd = run_root.parent.resolve()
    else:
        cwd.relative_to(repo_root.parent)
    completed = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=descriptor_value.get("timeout_seconds", 30), check=False)
    candidate_hash = source.get("candidate_hash")
    if not isinstance(candidate_hash, str) or not candidate_hash.startswith("sha256:") or candidate_hash == "sha256:fixture":
        raise ValueError("JUDGE-CANDIDATE-BINDING-INCOMPLETE")
    expected_exit = source.get("expected_exit", "zero")
    if expected_exit not in {"zero", "nonzero"}:
        raise ValueError("JUDGE-EXPECTATION-INCOMPLETE")
    receipt = {"executor_id":source.get("executor_id", "sut-executor"), "judge_id":"independent-judge", "descriptor_hash":descriptor["evidence_sha256"], "candidate_hash":candidate_hash, "run_id":run_root.name, "exit_code":completed.returncode}
    assertions = source.get("acceptance_assertions", {})
    if not isinstance(assertions, dict) or not assertions or any(not isinstance(key, str) or not isinstance(value, str) or not value for key, value in assertions.items()):
        raise ValueError("JUDGE-INDEPENDENCE-UNPROVEN")
    observation = {"run_id":run_root.name, "stdout":completed.stdout, "stderr":completed.stderr, "observation_id":source.get("observation_id", "OBS-S3"), "descriptor_argv":argv, "expected_exit":expected_exit, "executions":1, "acceptance_assertions":assertions}
    receipt["actual_argv"] = argv
    valid, failure = validate_judge(receipt, observation)
    if not valid:
        raise ValueError(failure)
    result = _write(run_root / "process-receipt.v1.json", {"schema_version":"process-receipt.v1", "producer":"independent-judge", "status":"pass", "slice_id":"S3", "run_id":run_root.name, "receipt":receipt, "observation":observation, "descriptor_evidence_sha256":descriptor["evidence_sha256"]})
    return result


def produce_coverage(run_root: Path) -> dict:
    source, receipt = _input(run_root, "coverage-input.v1.json"), _artifact(run_root, "process-receipt.v1.json", "independent-judge", "S3")
    acceptance_ids, observation_ids, edges = source.get("acceptance_ids"), source.get("observation_ids"), source.get("edges")
    valid, failure = validate_many_to_many_cover(edges, set(acceptance_ids or []), set(observation_ids or []))
    observed_assertions = receipt.get("observation", {}).get("acceptance_assertions") if isinstance(receipt.get("observation"), dict) else None
    expected_acceptance = {"A-SEMANTIC", "A-DESCRIPTOR", "A-JUDGE", "A-COVER", "A-PROMOTION", "A-TERMINAL", "A-BOUNDARY"}
    if set(acceptance_ids or []) != expected_acceptance or not isinstance(observed_assertions, dict):
        raise ValueError("COVERAGE-EVIDENCE-LINEAGE-UNBOUND")
    if any(edge.get("assertion") != observed_assertions.get(edge.get("acceptance_id")) for edge in edges if isinstance(edge, dict)):
        raise ValueError("COVERAGE-EVIDENCE-LINEAGE-UNBOUND")
    observed = receipt.get("observation", {}).get("observation_id") if isinstance(receipt.get("observation"), dict) else None
    if not isinstance(observed, str) or observed not in set(observation_ids or []):
        raise ValueError("COVERAGE-EVIDENCE-LINEAGE-UNBOUND")
    if any(edge.get("observation_id") != observed for edge in edges if isinstance(edge, dict)):
        raise ValueError("COVERAGE-EVIDENCE-LINEAGE-UNBOUND")
    if not _bound(receipt, "independent-judge", "S3", receipt["run_id"]) or not isinstance(acceptance_ids, list) or not isinstance(observation_ids, list) or not isinstance(edges, list) or not valid:
        raise ValueError(failure or "receipt-unbound")
    result = _write(run_root / "acceptance-coverage.v1.json", {"schema_version":"acceptance-coverage.v1", "producer":"coverage-gate", "status":"pass", "slice_id":"S4", "run_id":run_root.name, "acceptance_ids":acceptance_ids, "observation_ids":observation_ids, "edges":edges, "receipt_evidence_sha256":receipt["evidence_sha256"]})
    return result


def produce_false_green_fixtures(run_root: Path) -> dict:
    source, coverage = _input(run_root, "false-green-fixture-input.v1.json"), _artifact(run_root, "acceptance-coverage.v1.json", "coverage-gate", "S4")
    fixtures = source.get("fixtures")
    if not _bound(coverage, "coverage-gate", "S4", coverage["run_id"]) or not isinstance(fixtures, list):
        raise ValueError("fixture-input-invalid")
    if len(fixtures) != 9 or {item.get("fixture_id") for item in fixtures if isinstance(item, dict)} != {f"FG-{i:02d}" for i in range(1, 10)}:
        raise ValueError("fixture-input-invalid")
    predecessor_hash = source.get("predecessor_judge_hash")
    if not isinstance(predecessor_hash, str) or not predecessor_hash.startswith("sha256:") or "coverage" in predecessor_hash:
        raise ValueError("PROMOTION-PREDECESSOR-JUDGE-UNBOUND")
    freeze = run_root.parents[4] / "execution-plans" / "2026-08-25-vdd-quick-dev-semantic-oracle-recovery" / "predecessor-judge-freeze.v1.json"
    if "logs" in run_root.parts:
        if not freeze.is_file() or "independent" not in freeze.read_text(encoding="utf-8").lower():
            raise ValueError("PROMOTION-PREDECESSOR-JUDGE-UNBOUND")
    results = []
    for fixture in fixtures:
        if not isinstance(fixture, dict) or not isinstance(fixture.get("blocked_argv"), list) or not isinstance(fixture.get("corrected_argv"), list) or fixture.get("blocked_argv") == fixture.get("corrected_argv"):
            raise ValueError("fixture-input-invalid")
        blocked = subprocess.run(fixture["blocked_argv"], cwd=run_root, capture_output=True, text=True, timeout=30, check=False)
        corrected = subprocess.run(fixture["corrected_argv"], cwd=run_root, capture_output=True, text=True, timeout=30, check=False)
        try:
            blocked_doc = json.loads(blocked.stdout.strip().splitlines()[-1])
            corrected_doc = json.loads(corrected.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            raise ValueError("fixture-observation-invalid")
        if blocked_doc.get("fixture_id") != fixture.get("fixture_id") or corrected_doc.get("fixture_id") != fixture.get("fixture_id") or blocked_doc.get("baseline_hash") != corrected_doc.get("baseline_hash") or blocked_doc.get("mutation_hash") != corrected_doc.get("mutation_hash"):
            raise ValueError("fixture-lineage-unbound")
        results.append({"fixture_id":fixture.get("fixture_id"), "category":blocked_doc.get("category"), "baseline_hash":blocked_doc.get("baseline_hash"), "mutation_hash":blocked_doc.get("mutation_hash"), "blocked":blocked.returncode != 0, "blocked_exit_code":blocked.returncode, "blocked_failure_id":blocked_doc.get("failure_id"), "corrected_pair_pass":corrected.returncode == 0 and corrected_doc.get("status") == "corrected" and corrected_doc.get("failure_id") is None, "corrected_exit_code":corrected.returncode})
    valid, failure = validate_promotion(results, predecessor_hash, "coverage-gate")
    if not valid:
        raise ValueError(failure)
    ids = [f"FG-{index:02d}" for index in range(1, 10)]
    result = _write(run_root / "false-green-fixtures.v1.json", {"schema_version":"false-green-fixtures.v1", "producer":"coverage-gate", "status":"pass", "slice_id":"S5", "run_id":run_root.name, "fixtures":results, "fixture_ids":ids, "blocked_ids":ids, "corrected_pair_ids":ids, "corrected_pairs_executed":True, "predecessor_judge_hash":predecessor_hash})
    return result


def produce_terminal(run_root: Path, plan: Path) -> dict:
    publish_terminal_evidence(plan, run_root)
    result = _input(run_root, "terminal-replay-report.json")
    if result.get("status") != "pass" or result.get("run_id") != run_root.name:
        raise ValueError("TERMINAL-LINEAGE-NOT-CLOSED")
    return result


def run(plan: Path, slice_id: str, stage: str, run_root: Path | None = None) -> int:
    if run_root is None:
        return 2
    try:
        if slice_id == "S6":
            if stage != "terminal": return 2
            result = produce_terminal(run_root, plan)
        else:
            if stage not in {"green", "refactor"}: return 2
            result = {"S1":compile_run_local_semantic_artifacts, "S2":produce_descriptor, "S3":produce_receipt, "S4":produce_coverage, "S5":produce_false_green_fixtures}[slice_id](run_root)
        producer = {"S1":"vdd", "S2":"quick-dev", "S3":"independent-judge", "S4":"coverage-gate", "S5":"coverage-gate", "S6":"terminal-validator"}[slice_id]
        return 0 if _bound(result, producer, slice_id, run_root.name) else 2
    except (KeyError, OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError):
        return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-dir", required=True); parser.add_argument("--slice", required=True); parser.add_argument("--stage", required=True); parser.add_argument("--run-root")
    args = parser.parse_args()
    raise SystemExit(run(Path(args.plan_dir), args.slice, args.stage, Path(args.run_root) if args.run_root else None))

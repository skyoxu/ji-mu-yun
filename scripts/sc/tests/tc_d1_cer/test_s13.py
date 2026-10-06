"""S13 replay and evaluator behavior checks (ADR-0058, ADR-0041)."""
from __future__ import annotations

import json
import copy
import subprocess
import sys
from pathlib import Path

import pytest

_CER_ASSERTION_BINDINGS = [pytest.mark.cer_assertion("SM2-EFFECTIVE-IDENTITY-REUSE")]


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts/sc/skill_package_replay.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"


def _run(*arguments: str) -> tuple[int, dict]:
    process = subprocess.run(
        [sys.executable, "-B", str(ENTRY), *arguments],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        # This integrates parent routes and a fresh child; native child and
        # Matrix budgets remain 60 seconds in the production adapter.
        errors="replace", timeout=180 if arguments[0] == "replay-package" else 60, check=False,
    )
    try:
        receipt = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Replay entry did not return JSON: {exc}; stderr={process.stderr[:500]}")
    if not isinstance(receipt, dict):
        pytest.fail("Replay entry did not return an object")
    return process.returncode, receipt


@pytest.fixture(scope="module")
def replay() -> dict:
    code, receipt = _run(
        "replay-package", "--target", TARGET, "--capability", CAPABILITY,
        "--probe-mode", "fresh",
    )
    if code != 0 or not isinstance(receipt.get("current_wrapper_replay"), dict):
        pytest.fail(f"Positive replay fixture could not execute: exit={code}; receipt={receipt}")
    return receipt


def _matrix(*cases: dict, native_matrix=None) -> tuple[int, dict]:
    matrix = native_matrix if native_matrix is not None else {"schema_version": "jimuyun.stable-candidate-replay-matrix.v2", "cases": cases, "authorizes": []}
    child = (
        "import json, runpy, sys\n"
        "from pathlib import Path\n"
        "payload = sys.stdin.read()\n"
        "original_text, original_bytes = Path.read_text, Path.read_bytes\n"
        "def fixture_text(path, *args, **kwargs):\n"
        "    return payload if path.name == 's13-matrix.json' else original_text(path, *args, **kwargs)\n"
        "def fixture_bytes(path, *args, **kwargs):\n"
        "    return payload.encode('utf-8') if path.name == 's13-matrix.json' else original_bytes(path, *args, **kwargs)\n"
        "Path.read_text, Path.read_bytes = fixture_text, fixture_bytes\n"
        "sys.path.insert(0, str(Path(sys.argv[1]).parent))\n"
        "sys.argv = [sys.argv[1], 'replay-matrix', '--matrix', 's13-matrix.json']\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )
    process = subprocess.run(
        [sys.executable, "-B", "-c", child, str(ENTRY)], cwd=ROOT,
        input=json.dumps(matrix), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=60, check=False,
    )
    try:
        receipt = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Matrix entry did not return JSON: {exc}; stderr={process.stderr[:500]}")
    if not isinstance(receipt, dict):
        pytest.fail("Matrix entry did not return an object")
    return process.returncode, receipt


def _case(case_id: str, **facts: object) -> dict:
    return {"case_id": case_id, "target": TARGET, "capability": CAPABILITY, "expected_exit": 0, **facts}


def _assert_behavior(condition: bool, failure_id: str, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, detail


def _rejected(code: int, receipt: dict, fragment: str) -> bool:
    rows = receipt.get("case_results")
    row = rows[0] if isinstance(rows, list) and len(rows) == 1 else {}
    return (
        code != 0 and receipt.get("status") != "pass"
        and row.get("status") != "pass"
        and fragment in str(row.get("rejection_reason", "")).lower()
    )


@pytest.mark.cer_assertion("assert-identity-execution-facts-gate")
def test_unverifiable_identity_and_execution_facts_reject_success(native_skill_replay_matrix, native_matrix_rejection) -> None:
    matrix, control = native_skill_replay_matrix
    missing = copy.deepcopy(matrix)
    missing["cases"][0].pop("fixture")
    missing_code, missing_receipt = native_matrix_rejection(missing)
    wrong = copy.deepcopy(matrix)
    wrong["candidate"]["target"] = "scripts"
    wrong_code, wrong_receipt = native_matrix_rejection(wrong)
    _assert_behavior(
        control.get("status") == "pass"
        and all(row.get("executed") is True for row in control["case_results"])
        and missing_code != 0 and missing_receipt.get("aggregate_valid") is False
        and "fixture binding" in str(missing_receipt.get("invalid_reasons", []))
        and wrong_code != 0 and wrong_receipt.get("aggregate_valid") is False
        and "targets must match" in str(wrong_receipt.get("invalid_reasons", []))
        and all(row.get("executed") is False for row in missing_receipt["case_results"] + wrong_receipt["case_results"]),
        "IDENTITY-FACTS-UNVERIFIABLE",
        {"missing": missing_receipt, "wrong_target": wrong_receipt},
    )


@pytest.mark.cer_assertion("NFR-1.identity-execution-ambiguity-blocks-success")
def test_ambiguous_identity_rejects_success() -> None:
    code, receipt = _matrix(_case("ambiguous-identity", identity_status="ambiguous"))
    _assert_behavior(_rejected(code, receipt, "ambiguous"),
                     "FI-7D1CF486-AMBIGUOUS-IDENTITY-ACCEPTED", receipt)


@pytest.mark.cer_assertion("A-96518A7BEA24-1")
@pytest.mark.parametrize("facts,reason,failure_id", [
    ({"identity_status": "stale"}, "identity", "F-96518A7BEA24-1"),
    ({"execution_freshness": None}, "freshness", "F-96518A7BEA24-2"),
])
def test_stale_or_unverifiable_execution_rejects_success(facts: dict, reason: str, failure_id: str) -> None:
    code, receipt = _matrix(_case("stale-execution", **facts))
    _assert_behavior(_rejected(code, receipt, reason), failure_id, receipt)


@pytest.mark.cer_assertion("SM-2.skipped-consumer-rejects-success")
def test_skipped_consumer_rejects_success() -> None:
    code, receipt = _matrix(_case("skipped-consumer", consumer_status="skipped"))
    _assert_behavior(_rejected(code, receipt, "consumer"),
                     "FI-82C942DEA6B9-SKIPPED-CONSUMER-ACCEPTED", receipt)


@pytest.mark.cer_assertion("assert-reused-evidence-rejects-success")
def test_reused_evidence_rejects_success() -> None:
    code, receipt = _matrix(_case("reused-evidence", evidence_origin="copied"))
    _assert_behavior(_rejected(code, receipt, "copied"), "REUSED-EVIDENCE-ACCEPTED", receipt)


@pytest.mark.cer_assertion("A-CCC2E767570E-1")
def test_substituted_target_is_denied_before_processing() -> None:
    process = subprocess.run(
        [sys.executable, "-B", str(ENTRY), "validate-package", "--target", "scripts",
         "--capability", CAPABILITY], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", timeout=30, check=False,
    )
    refusal = json.loads(process.stdout)
    _assert_behavior(process.returncode != 0 and "target does not match" in process.stderr
                     and refusal.get("status") == "execution-failed" and refusal.get("authorizes") == []
                     and "successful_evidence" not in refusal, "F-CCC2E767570E-1", refusal)


@pytest.mark.cer_assertion("SM-5-A1")
def test_successful_replay_has_independent_target_outcome(replay: dict) -> None:
    record = replay["current_wrapper_replay"]
    verification = record.get("target_verification", {})
    _assert_behavior(
        replay.get("status") == "pass" and verification.get("independent") is True
        and verification.get("target") == TARGET and verification.get("status") == "passed"
        and verification.get("identity_match") is True,
        "FI-41624F84A890-MISSING-TARGET-VERIFICATION", verification,
    )


@pytest.mark.cer_assertion("A-25E-1")
def test_successful_replay_has_independent_snapshot_outcome(replay: dict) -> None:
    record = replay["current_wrapper_replay"]
    verification = record.get("snapshot_verification", {})
    snapshot = record.get("current_snapshot", {})
    _assert_behavior(
        verification.get("independent") is True and verification.get("status") == "passed"
        and verification.get("snapshot_sha256") == snapshot.get("sha256"),
        "F-25E-SNAPSHOT-CHECK-MISSING", verification,
    )


@pytest.mark.cer_assertion("A-6C67-1")
def test_successful_replay_has_separate_probe_verification(replay: dict) -> None:
    record = replay["current_wrapper_replay"]
    verification = record.get("probe_verification", {})
    probes = record.get("probes", [])
    _assert_behavior(
        verification.get("independent") is True and verification.get("status") == "passed"
        and any(isinstance(probe, dict) and probe.get("process", {}).get("pid")
                for probe in probes),
        "F-6C67-MISSING-PROBE-VERIFICATION", verification,
    )


@pytest.mark.cer_assertion("A-C4A5591E2D9E-1")
def test_successful_replay_has_bound_validator_capability_verification(replay: dict) -> None:
    record = replay["current_wrapper_replay"]
    verification = record.get("validator_capability", {})
    _assert_behavior(
        verification.get("independent") is True and verification.get("status") == "passed"
        and verification.get("replay_identity") == record.get("replay_identity"),
        "CER-A-D5DE0A6A3875-BEHAVIOR", verification,
    )


@pytest.mark.cer_assertion("A-SM6-FRESH-SEMANTIC-REPLAY")
def test_fresh_replay_reconstructs_pinned_verdict_and_bindings(replay: dict) -> None:
    record = replay["current_wrapper_replay"]
    snapshot = record.get("current_snapshot", {})
    roots = snapshot.get("roots", [])
    _assert_behavior(
        record.get("fresh_process") is True and record.get("fresh_checkout") is True
        and record.get("pinned_semantic_verdict") == record.get("fresh_semantic_verdict")
        and record.get("reconstructed_identity") == record.get("replay_identity")
        and len(roots) == 8 and all(row.get("sha256", "").startswith("sha256:") for row in roots),
        "CER-A-78FD23DDD4A1-BEHAVIOR", record,
    )


@pytest.mark.cer_assertion("A-236-1")
def test_prose_only_verdict_cannot_validate() -> None:
    code, receipt = _matrix(_case("prose-only-verdict", narrative="I verified this", source_identity=None, execution_evidence=None))
    _assert_behavior(_rejected(code, receipt, "evidence") or _rejected(code, receipt, "source"),
                     "F-236-PROSE-ONLY-VERDICT", receipt)


@pytest.mark.cer_assertion("O-D4C0A15CD173-A1")
def test_manifest_transitions_cover_every_consumer(replay: dict) -> None:
    record = replay["current_wrapper_replay"]
    entries = record.get("consumer_manifest", {}).get("entries", [])
    transitions = record.get("route_transitions", [])
    _assert_behavior(
        bool(entries) and all(any(t.get("consumer") == entry.get("consumer") and t.get("status") == "completed"
                                  for t in transitions) for entry in entries)
        and record.get("transition_completion_percent") == 100,
        "CER-A-CA2FDAF6C599-BEHAVIOR", record.get("route_transitions"),
    )


@pytest.mark.cer_assertion("O-D4C0A15CD173-A2")
def test_manifest_transitions_have_post_rollback_baselines(replay: dict) -> None:
    record = replay["current_wrapper_replay"]
    entries = record.get("consumer_manifest", {}).get("entries", [])
    transitions = record.get("route_transitions", [])
    _assert_behavior(
        bool(entries) and all(any(t.get("consumer") == entry.get("consumer")
                                  and t.get("post_rollback_prior_behavior_baseline", {}).get("observed") is True
                                  for t in transitions) for entry in entries),
        "O-D4C0A15CD173-F2", transitions,
    )


@pytest.mark.cer_assertion("A-D4C8E08364E2-1")
def test_aggregate_records_deterministic_terminal_state() -> None:
    case = _case("bounded-aggregate", aggregate_time_bound_ms=2000, aggregate_output_bound_bytes=4096)
    first_code, first = _matrix(case)
    second_code, second = _matrix(case)
    left = (first.get("case_results") or [{}])[0]
    right = (second.get("case_results") or [{}])[0]
    _assert_behavior(
        first_code == second_code and bool(left.get("terminal_state"))
        and left.get("terminal_state") == right.get("terminal_state")
        and isinstance(left.get("elapsed_ms"), (int, float)),
        "CER-A-CD67894167F3-BEHAVIOR", (left, right),
    )


@pytest.mark.cer_assertion("NFR-7.aggregate-completes-within-bound")
def test_over_budget_aggregate_terminates_unsuccessfully(native_skill_replay_matrix) -> None:
    matrix, _ = native_skill_replay_matrix
    bounded = json.loads(json.dumps(matrix))
    bounded["cases"][0].update(aggregate_time_bound_ms=0, aggregate_output_bound_bytes=1)
    code, receipt = _matrix(native_matrix=bounded)
    row = (receipt.get("case_results") or [{}])[0]
    _assert_behavior(
        code != 0 and row.get("terminal_state") in {"timeout", "budget-exhausted"}
        and isinstance(row.get("elapsed_ms"), (int, float))
        and row.get("status") != "pass",
        "FI-89B4F7D1B20D-AGGREGATE-TIME-BOUND", row,
    )

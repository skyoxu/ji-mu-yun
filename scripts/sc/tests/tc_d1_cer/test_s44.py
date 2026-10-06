"""S44 CER checks for verdict source identity and real execution traceability."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"


def _run_matrix(case: dict, *, matrix_fields: dict | None = None, cases: list[dict] | None = None) -> tuple[int, dict]:
    matrix = {"schema_version": "jimuyun.stable-candidate-replay-matrix.v2", "authorizes": [], "cases": cases or [case]}
    if matrix_fields:
        matrix.update(matrix_fields)
    child = (
        "import runpy,sys\n"
        "from pathlib import Path\n"
        "payload=sys.stdin.read(); old=Path.read_text; oldb=Path.read_bytes\n"
        "Path.read_text=lambda p,*a,**k: payload if p.name=='s44-matrix.json' else old(p,*a,**k)\n"
        "Path.read_bytes=lambda p,*a,**k: payload.encode('utf-8') if p.name=='s44-matrix.json' else oldb(p,*a,**k)\n"
        f"sys.argv=['{ENTRY.as_posix()}','replay-matrix','--matrix','s44-matrix.json']\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", child],
        cwd=ROOT,
        input=json.dumps(matrix),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Matrix entry did not return JSON: {exc}; stderr={result.stderr[:500]}")
    if not isinstance(payload, dict):
        pytest.fail("Matrix entry did not return an object")
    return result.returncode, payload


def _run_replay(probe_mode: str = "source-identity") -> tuple[int, dict]:
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(ENTRY),
            "replay-package",
            "--target",
            TARGET,
            "--capability",
            CAPABILITY,
            "--probe-mode",
            probe_mode,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Replay entry did not return JSON: {exc}; stderr={result.stderr[:500]}")
    if not isinstance(payload, dict):
        pytest.fail("Replay entry did not return an object")
    return result.returncode, payload


def _assert_behavior(condition: bool, failure_id: str, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, detail


@pytest.mark.cer_assertion("O-12738417684F")
def test_verdict_binds_current_source_identity_to_real_execution_command() -> None:
    code, receipt = _run_replay()
    replay = receipt.get("current_wrapper_replay") or {}
    snapshot = replay.get("current_snapshot") or {}
    roots = snapshot.get("roots") if isinstance(snapshot, dict) else None
    source_root = next((item for item in roots or [] if isinstance(item, dict) and item.get("root_kind") == "source"), None)
    command = replay.get("command")
    condition = (
        code == 0
        and receipt.get("status") == "pass"
        and isinstance(source_root, dict)
        and source_root.get("path") == "scripts/sc/skill_package_replay.py"
        and isinstance(source_root.get("sha256"), str)
        and source_root["sha256"].startswith("sha256:")
        and isinstance(command, list)
        and "scripts/sc/skill_package_replay.py" in command
        and replay.get("fresh_process") is True
    )
    _assert_behavior(condition, "F-VERDICT-MISSING-SOURCE-IDENTITY", receipt)


@pytest.mark.cer_assertion("O-12738417684F")
def test_verdict_with_missing_source_identity_is_rejected() -> None:
    case = {
        "case_id": "missing-source-identity",
        "target": TARGET,
        "capability": CAPABILITY,
        "expected_exit": 0,
        "source_identity": None,
        "execution_evidence": None,
    }
    code, receipt = _run_matrix(case)
    row = (receipt.get("case_results") or [{}])[0]
    _assert_behavior(
        code != 0
        and receipt.get("aggregate_valid") is False
        and row.get("status") != "pass"
        and any(word in str(row.get("rejection_reason", "")).lower() for word in ("source", "evidence", "identity")),
        "F-VERDICT-MISSING-SOURCE-IDENTITY",
        receipt,
    )


@pytest.mark.cer_assertion("A-8AD58EB8B159-1")
def test_stale_matrix_evidence_is_invalid() -> None:
    code, receipt = _run_matrix({"case_id": "stale", "target": TARGET, "capability": CAPABILITY,
                                 "expected_exit": 0, "identity_status": "stale"})
    row = receipt["case_results"][0]
    _assert_behavior(code != 0 and receipt["aggregate_valid"] is False and row["status"] == "fail" and "stale" in row["rejection_reason"], "F-S44-STALE-MATRIX", receipt)


@pytest.mark.cer_assertion("A-B572-1")
def test_stable_and_candidate_fixture_assignments_must_differ() -> None:
    assignments = {"Stable": {"fixture_id": "same", "state_id": "stable"}, "Candidate": {"fixture_id": "same", "state_id": "stable"}}
    code, receipt = _run_matrix({"case_id": "same-fixtures", "target": TARGET, "capability": CAPABILITY,
                                 "expected_exit": 0, "fixture_state_assignments": assignments})
    row = receipt["case_results"][0]
    _assert_behavior(code != 0 and row["status"] == "fail" and "distinct" in row["rejection_reason"], "F-S44-SAME-FIXTURES", receipt)


@pytest.mark.cer_assertion("A-B572-2")
def test_nonexecuted_matrix_evidence_is_rejected() -> None:
    code, receipt = _run_matrix({"case_id": "nonexecuted", "target": TARGET, "capability": CAPABILITY,
                                 "expected_exit": 0, "matrix_evidence": [{"executed": False}]})
    row = receipt["case_results"][0]
    _assert_behavior(code != 0 and row["status"] == "fail" and "non-executed" in row["rejection_reason"], "F-S44-NONEXECUTED", receipt)


@pytest.mark.cer_assertion("A-B5F-1")
def test_required_matrix_case_missing_is_invalid() -> None:
    case = {"case_id": "only-one", "target": TARGET, "capability": CAPABILITY, "expected_exit": 0}
    code, receipt = _run_matrix(case, matrix_fields={"required_matrix_cases": ["only-one", "missing-case"]})
    _assert_behavior(code != 0 and receipt["aggregate_valid"] is False and receipt["missing_cases"] == ["missing-case"], "F-S44-MISSING-CASE", receipt)


@pytest.mark.cer_assertion("A-B5F-2")
def test_duplicate_evidence_identity_is_rejected() -> None:
    case = {"target": TARGET, "capability": CAPABILITY, "expected_exit": 0, "effective_evidence_identity": "evidence-1"}
    code, receipt = _run_matrix(case, cases=[dict(case, case_id="duplicate-a"), dict(case, case_id="duplicate-b")])
    _assert_behavior(code != 0 and receipt["aggregate_valid"] is False and all(row["status"] == "fail" for row in receipt["case_results"]), "F-S44-DUPLICATE-EVIDENCE", receipt)


@pytest.mark.cer_assertion("A-EEB6-stale-invalid")
def test_bound_and_evidence_input_identity_mismatch_is_invalid() -> None:
    code, receipt = _run_matrix({"case_id": "stale-input", "target": TARGET, "capability": CAPABILITY,
                                 "expected_exit": 0, "bound_input_identity": "a", "evidence_input_identity": "b"})
    row = receipt["case_results"][0]
    _assert_behavior(code != 0 and row["status"] == "fail" and "stale" in row["rejection_reason"], "F-S44-STALE-INPUT", receipt)


@pytest.mark.cer_assertion("FR-10-A1")
def test_fresh_checkout_replay_records_reproducible_result() -> None:
    code, receipt = _run_replay("fresh")
    replay = receipt.get("current_wrapper_replay") or {}
    _assert_behavior(code == 0 and receipt.get("status") == "pass" and replay.get("fresh_checkout") is True and replay.get("fresh_semantic_verdict") == replay.get("pinned_semantic_verdict") and replay.get("fresh_coverage") == replay.get("pinned_coverage"), "F-S44-FRESH-REPLAY", receipt)


@pytest.mark.cer_assertion("O-0C8536BAA793")
def test_unverifiable_identity_is_rejected() -> None:
    code, receipt = _run_matrix({"case_id": "unverifiable", "target": TARGET, "capability": CAPABILITY,
                                 "expected_exit": 0, "identity_status": "unverifiable"})
    row = receipt["case_results"][0]
    _assert_behavior(code != 0 and row["status"] == "fail" and "unverifiable" in row["rejection_reason"], "F-S44-UNVERIFIABLE", receipt)


@pytest.mark.cer_assertion("fresh-checkout-coverage-reproducibility")
def test_fresh_checkout_contains_coverage_and_identity() -> None:
    code, receipt = _run_replay("fresh")
    replay = receipt.get("current_wrapper_replay") or {}
    _assert_behavior(code == 0 and isinstance(replay.get("coverage_result"), dict) and replay.get("fresh_checkout") is True and replay.get("coverage_result") == replay.get("pinned_coverage"), "F-S44-COVERAGE-REPRO", receipt)


@pytest.mark.cer_assertion("fresh-checkout-coverage-reproducibility")
def test_fresh_checkout_contains_the_replay_entry_used_for_execution() -> None:
    code, receipt = _run_replay("fresh")
    replay = receipt.get("current_wrapper_replay") or {}
    checkout = replay.get("checkout_path")
    entry = Path(checkout) / "scripts" / "sc" / "skill_package_replay.py" if isinstance(checkout, str) else None
    _assert_behavior(
        code == 0
        and replay.get("fresh_checkout") is True
        and entry is not None
        and entry.is_file(),
        "F-S44-FRESH-ENTRY-MISSING",
        {"checkout": checkout, "entry": str(entry) if entry else None},
    )


@pytest.mark.cer_assertion("consumer-call-surface-is-real")
def test_consumer_verification_records_real_commands_not_file_reads() -> None:
    code, receipt = _run_replay("source-identity")
    replay = receipt.get("current_wrapper_replay") or {}
    verification = replay.get("consumer_verification") or {}
    calls = verification.get("calls") or []
    required = {
        "vdd-execution-plan",
        "run-refactor-implementation-acceptance",
        "workflow-model-routing",
    }
    _assert_behavior(
        code == 0
        and {call.get("consumer") for call in calls} == required
        and all(
            call.get("executed") is True
            and call.get("exit_code") == 0
            and isinstance(call.get("command"), list)
            and call.get("command")
            and not ("read_text" in " ".join(map(str, call.get("command"))))
            for call in calls
        ),
        "F-CONSUMER-FILE-READ-NOT-CALL",
        verification,
    )


@pytest.mark.cer_assertion("matrix-case-binds-real-input")
def test_independent_matrix_requires_real_distinct_input_bindings() -> None:
    case = {
        "case_id": "same-package-different-label",
        "target": TARGET,
        "stable_target": TARGET,
        "candidate_target": TARGET,
        "capability": CAPABILITY,
        "expected_exit": 0,
    }
    code, receipt = _run_matrix(
        case,
        matrix_fields={"subject_contract": "independent-stable-candidate-v1"},
    )
    row = receipt["case_results"][0]
    _assert_behavior(
        code != 0
        and row.get("status") == "fail"
        and "input" in str(row.get("rejection_reason", "")).lower(),
        "F-MATRIX-LABEL-ONLY",
        receipt,
    )

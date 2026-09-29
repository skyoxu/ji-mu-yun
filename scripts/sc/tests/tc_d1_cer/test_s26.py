"""S26 bounded CER checks against the repository replay entrypoints."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_CER_ASSERTION_BINDINGS = [pytest.mark.cer_assertion("A-AF55FF781031-1")]


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts/sc/skill_package_replay.py"
PROBE = ROOT / "scripts/vdd/probe_real_worker.py"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
MATRIX = ROOT / "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/stable-candidate-replay-matrix.v1.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-B", str(ENTRY), *args], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", check=False)


def _replay(mode: str = "fresh") -> tuple[subprocess.CompletedProcess[str], dict]:
    result = _run("replay-package", "--target", TARGET, "--capability", CAPABILITY, "--probe-mode", mode)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    return result, payload if isinstance(payload, dict) else {}


def _body(payload: dict) -> dict:
    value = payload.get("current_wrapper_replay")
    return value if isinstance(value, dict) else {}


def _probe(payload: dict, probe_id: str) -> dict:
    rows = _body(payload).get("probes", [])
    return next((row for row in rows if isinstance(row, dict) and row.get("probe_id") == probe_id), {})


def _assert_behavior(condition: bool, failure_id: str, message: str) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, message


def _matrix(*cases: dict) -> tuple[subprocess.CompletedProcess[str], dict]:
    matrix = {"schema_version": "jimuyun.stable-candidate-replay-matrix.v2", "authorizes": [], "cases": list(cases)}
    child = (
        "import json,runpy,sys\n"
        "from pathlib import Path\n"
        "data=sys.stdin.read(); old=Path.read_text; oldb=Path.read_bytes\n"
        "Path.read_text=lambda p,*a,**k: data if p.name=='s26-matrix.json' else old(p,*a,**k)\n"
        "Path.read_bytes=lambda p,*a,**k: data.encode() if p.name=='s26-matrix.json' else oldb(p,*a,**k)\n"
        "sys.path.insert(0,str(Path(sys.argv[1]).parent))\n"
        "sys.argv=[sys.argv[1],'replay-matrix','--matrix','s26-matrix.json']; runpy.run_path(sys.argv[0],run_name='__main__')\n"
    )
    result = subprocess.run([sys.executable, "-B", "-c", child, str(ENTRY)], cwd=ROOT,
                            input=json.dumps(matrix), capture_output=True, text=True,
                            encoding="utf-8", check=False)
    stdout = result.stdout
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = {}
    return result, payload if isinstance(payload, dict) else {}


@pytest.mark.cer_assertion("A-AF55FF781031-1")
@pytest.mark.cer_assertion("assert-fr4-positive-probe-must-pass")
def test_positive_probe_requires_real_success() -> None:
    result, payload = _replay()
    probe = _probe(payload, "detached-positive")
    _assert_behavior(result.returncode == 0 and probe.get("exit_code") == 0 and probe.get("status") == "pass",
                     "POSITIVE-PROBE-FAILURE-ACCEPTED", "successful replay requires a successful positive Probe")


@pytest.mark.cer_assertion("assert-fr4-negative-probe-declared-defect-category")
def test_negative_probe_is_nonzero_and_independent() -> None:
    result, payload = _replay("detached-positive-negative")
    probe = _probe(payload, "detached-negative")
    process = probe.get("process", {})
    _assert_behavior(result.returncode == 0 and probe.get("exit_code", 0) != 0
                     and process.get("pid") != process.get("parent_pid"),
                     "NEGATIVE-PROBE-WRONG-DEFECT-ACCEPTED", "negative Probe must be a nonzero child process")


@pytest.mark.cer_assertion("RMAP-R6-S1")
def test_detached_negative_receipt_has_process_boundary() -> None:
    result, payload = _replay("detached-positive-negative")
    probe = _probe(payload, "detached-negative")
    process = probe.get("process", {})
    _assert_behavior(result.returncode == 0 and isinstance(process.get("pid"), int)
                     and isinstance(process.get("parent_pid"), int)
                     and process["pid"] != process["parent_pid"] and probe.get("exit_code", 0) != 0,
                     "RMAP-R6-S1-DETACHED-NEGATIVE-NOT-INDEPENDENT", "detached negative evidence is incomplete")


@pytest.mark.cer_assertion("SM-5-non-authority-binding-independent-verification")
def test_successful_replay_has_independent_non_authority_binding() -> None:
    result, payload = _replay()
    value = _body(payload).get("candidate_external_trust_verification", {})
    _assert_behavior(result.returncode == 0 and value.get("independent") is True
                     and value.get("complete") is True and value.get("candidate_controlled") is False,
                     "MISSING-INDEPENDENT-NON-AUTHORITY-BINDING", "non-authority binding is not independently verified")


@pytest.mark.cer_assertion("A-E89D613529C4-1")
def test_successful_replay_has_dependency_verification() -> None:
    result, payload = _replay()
    value = _body(payload).get("dependency_verification", {})
    _assert_behavior(result.returncode == 0 and value.get("independent") is True
                     and isinstance(value.get("validator"), str) and isinstance(value.get("capability"), str),
                     "FI-E89D613529C4-1", "dependency verification evidence is missing")


@pytest.mark.cer_assertion("A-D191B8A1BFB4-1")
@pytest.mark.cer_assertion("A-D191B8A1BFB4-2")
def test_successful_replay_has_distinct_command_verification() -> None:
    result, payload = _replay()
    replay = _body(payload)
    command = replay.get("command_verification", {})
    _assert_behavior(result.returncode == 0 and command.get("status") == "pass"
                     and command.get("independent") is True and command.get("command") == replay.get("command"),
                     "CER-A-CDC101075496-BEHAVIOR", "command verification is not independently bound")


@pytest.mark.cer_assertion("A-43C7-windows-support-1")
def test_windows_support_is_explicit() -> None:
    result, payload = _replay()
    value = _body(payload).get("platform_behavior", {})
    _assert_behavior(result.returncode == 0 and value.get("platform") == "win32" and bool(value.get("behavior")),
                     "CER-A-DF30AF5D2EDB-BEHAVIOR", "Windows support branch is not explicit")


@pytest.mark.cer_assertion("FR-8-wrong-target-evidence-invalidates-aggregate")
def test_wrong_target_evidence_invalidates_aggregate() -> None:
    result, payload = _matrix({"case_id": "wrong-target", "target": TARGET, "capability": CAPABILITY,
                               "expected_exit": 0, "bound_target": TARGET,
                               "evidence_target": ".agents/skills/vdd-execution-plan"})
    _assert_behavior(result.returncode != 0 and payload.get("aggregate_valid") is False,
                     "WRONG-TARGET-MATRIX-EVIDENCE-INVALIDATES-AGGREGATE", "wrong target was accepted")


@pytest.mark.cer_assertion("SM-2-adversarial-dependency-success-rejection")
def test_adversarial_dependency_rejects_success() -> None:
    result, payload = _matrix({"case_id": "adversarial", "target": TARGET, "capability": CAPABILITY,
                               "expected_exit": 0, "adversarial_dependency": True})
    _assert_behavior(result.returncode != 0 and payload.get("aggregate_valid") is False,
                     "ADVERSARIAL-DEPENDENCY-MUST-NOT-SUCCEED", "adversarial dependency was accepted")


@pytest.mark.cer_assertion("SM-2-stale-input-success-rejection")
def test_stale_input_rejects_success() -> None:
    result, payload = _matrix({"case_id": "stale", "target": TARGET, "capability": CAPABILITY,
                               "expected_exit": 0, "bound_input_identity": "sha256:old",
                               "evidence_input_identity": "sha256:new"})
    _assert_behavior(result.returncode != 0 and payload.get("aggregate_valid") is False,
                     "STALE-INPUT-MUST-NOT-SUCCEED", "stale input was accepted")


@pytest.mark.cer_assertion("A-O-36747B1BB805-six-cases-two-subjects-complete-coverage")
def test_six_cases_record_both_subjects() -> None:
    result = _run("replay-matrix", "--matrix", MATRIX.relative_to(ROOT).as_posix())
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    rows = payload.get("case_results", [])
    ok = len(rows) == 6 and all(isinstance(row.get("subject_executions"), list)
                                 and len(row["subject_executions"]) == 2 for row in rows)
    _assert_behavior(result.returncode == 0 and ok, "F-O-36747B1BB805-MISSING-SUBJECT-EXECUTION",
                     "matrix does not record both subject executions")


@pytest.mark.cer_assertion("A-O-31D7DE0B840F-stable-subject-immutable-six-cases")
def test_six_cases_attest_stable_immutability() -> None:
    result = _run("replay-matrix", "--matrix", MATRIX.relative_to(ROOT).as_posix())
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    rows = payload.get("case_results", [])
    ok = len(rows) == 6 and all(isinstance(row.get("stable_subject"), dict)
                                 and row["stable_subject"].get("executed") is True
                                 and row["stable_subject"].get("pre_identity") == row["stable_subject"].get("post_identity")
                                 for row in rows)
    _assert_behavior(result.returncode == 0 and ok, "F-O-31D7DE0B840F-STABLE-SUBJECT-MUTATION-OR-OMISSION",
                     "stable subject immutability evidence is missing")


@pytest.mark.cer_assertion("A-O-370AAFBB0DAC-budget-exhaustion-unsuccessful")
def test_budget_exhaustion_is_terminally_unsuccessful() -> None:
    time_result, time_payload = _matrix({"case_id": "over-time-budget", "target": TARGET,
                                         "capability": CAPABILITY, "expected_exit": 0,
                                         "aggregate_time_bound_ms": 0})
    output_result, output_payload = _matrix({"case_id": "over-output-budget", "target": TARGET,
                                             "capability": CAPABILITY, "expected_exit": 0,
                                             "aggregate_output_bound_bytes": 1})
    time_row = (time_payload.get("case_results") or [{}])[0]
    output_row = (output_payload.get("case_results") or [{}])[0]
    time_ok = (time_result.returncode != 0 and time_row.get("terminal_state") in {"timeout", "budget-exhausted"}
               and time_row.get("status") != "pass")
    output_ok = (output_result.returncode != 0 and output_row.get("terminal_state") in {"timeout", "budget-exhausted"}
                 and output_row.get("status") != "pass")
    if not time_ok:
        print("FAILURE_ID:F-O-370AAFBB0DAC-TIME-BUDGET-EXHAUSTION")
    if not output_ok:
        print("FAILURE_ID:F-O-370AAFBB0DAC-OUTPUT-BUDGET-EXHAUSTION")
    assert time_ok and output_ok, "budget exhaustion did not produce unsuccessful terminal results"


@pytest.mark.cer_assertion("A-O-2B2BDE7F47B2-infrastructure-false-negative-fails")
def test_infrastructure_false_negative_is_terminal_failure() -> None:
    result = subprocess.run([sys.executable, "-B", str(PROBE), "--backend", "unavailable-infrastructure-backend"],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    _assert_behavior(result.returncode != 0 and payload.get("status") in {"environment-blocked", "worker-failed"}
                     and payload.get("execution_succeeded") is not True,
                     "F-O-2B2BDE7F47B2-INFRASTRUCTURE-FALSE-NEGATIVE", "infrastructure failure was accepted")

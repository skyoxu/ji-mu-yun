"""CER checks for detached Probe execution through the replay entrypoint."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.sc import skill_replay_runtime as runtime


_CER_ASSERTION_BINDINGS = [
    pytest.mark.cer_assertion("assert-fr4-positive-probe-must-pass"),
    pytest.mark.cer_assertion("assert-fr4-negative-probe-declared-defect-category"),
]


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"


def _assert_behavior(condition: bool, failure_id: str, message: str) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, message


def _positive_replay() -> tuple[int, int, dict[str, object] | None]:
    process = runtime.capture_process(
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
            "fresh",
        ],
        ROOT,
        timeout=runtime.PROCESS_TRANSPORT_SECONDS,
    )
    try:
        receipt = json.loads(process.stdout)
    except json.JSONDecodeError:
        receipt = None
    return process.pid, process.returncode, receipt if isinstance(receipt, dict) else None


@pytest.fixture(scope="module")
def positive_replay() -> tuple[int, int, dict[str, object] | None]:
    # ADR-0058: share one current native scenario within this pytest process.
    # Every Quick Dev stage launches a new process and performs a fresh replay.
    return _positive_replay()


def _positive_probe(receipt: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(receipt, dict):
        return None
    replay = receipt.get("current_wrapper_replay")
    if not isinstance(replay, dict):
        return None
    probes = replay.get("probes")
    if not isinstance(probes, list):
        return None
    for probe in probes:
        if isinstance(probe, dict) and probe.get("probe_id") == "detached-positive":
            return probe
    return None


@pytest.mark.cer_assertion("ASSERT-O-2B7C47734A05-PROBE-PROCESS")
def test_detached_positive_probe_records_a_distinct_child_process(positive_replay) -> None:
    replay_pid, returncode, receipt = positive_replay
    probe = _positive_probe(receipt)
    process = probe.get("process") if isinstance(probe, dict) else None
    condition = (
        returncode == 0
        and isinstance(process, dict)
        and isinstance(process.get("pid"), int)
        and process["pid"] != replay_pid
        and process.get("parent_pid") == replay_pid
    )
    _assert_behavior(
        condition,
        "DETACHED_POSITIVE_PROBE_UNBOUND",
        "The detached positive Probe must record a distinct child process bound to the replay process",
    )


@pytest.mark.cer_assertion("ASSERT-O-2B7C47734A05-PROBE-BINDINGS")
def test_detached_positive_probe_binds_input_target_outcome_and_output(positive_replay) -> None:
    _, returncode, receipt = positive_replay
    probe = _positive_probe(receipt)
    input_value = probe.get("input") if isinstance(probe, dict) else None
    command_outcome = probe.get("command_outcome") if isinstance(probe, dict) else None
    output = probe.get("output") if isinstance(probe, dict) else None
    condition = (
        returncode == 0
        and isinstance(input_value, dict)
        and input_value.get("target") == TARGET
        and isinstance(probe, dict)
        and Path(str(probe.get("actual_target"))).is_absolute()
        and probe.get("actual_target") == probe.get("read_witness", {}).get("target")
        and isinstance(command_outcome, dict)
        and command_outcome.get("exit_code") == 0
        and isinstance(output, dict)
        and bool(output)
    )
    _assert_behavior(
        condition,
        "DETACHED_POSITIVE_PROBE_UNBOUND",
        "The detached positive Probe must bind its input, actual target, command outcome, and output",
    )


@pytest.mark.cer_assertion("ASSERT-O-833C8FA8A239-ALWAYS-SUCCESS-FALSE-NEGATIVE")
def test_always_success_validator_is_reported_as_a_failed_probe_outcome() -> None:
    sys.path.insert(0, str(ROOT / "scripts/sc/tests"))
    import test_skill_replay_review_regressions as support
    fixture = support.NativeRuntimeTests(methodName="runTest")
    fixture.setUp()
    try:
        code = "import json,sys\nfrom pathlib import Path\n(Path(sys.argv[-1])/'fixture.json').read_text(encoding='utf-8')\nprint(json.dumps({'findings':[]}))\nraise SystemExit(0)\n"
        fixture.write("validator/check.py", code)
        fixture.write("authority/source.py", code)
        fixture.cap.update(validator_sha256=support.replay.digest(fixture.root / "validator/check.py"), validator_source_sha256=support.replay.digest(fixture.root / "authority/source.py"))
        fixture.write("capability.json", json.dumps(fixture.cap))
        fixture.git("add", ".")
        fixture.git("commit", "-qm", "Freeze always-success fault fixture")
        fixture.pin_fixture_authority(fixture.git("rev-parse", "HEAD").strip())
        result = runtime.capture_process([sys.executable, "-B", str(fixture.root / "scripts/sc/skill_package_replay.py"),
                                 "validate-package", "--target", "candidate", "--capability", "capability.json"],
                                fixture.root, timeout=60)
    finally:
        fixture.tearDown()
    _assert_behavior(
        result.returncode != 0 and "negative compatibility probe unexpectedly passed" in result.stderr,
        "ALWAYS_SUCCESS_FALSE_NEGATIVE_PASSED",
        "An always-success validator must produce a failed detached Probe outcome",
    )


@pytest.mark.cer_assertion("A-431D-fresh-replay-1")
def test_fresh_replay_reproduces_recorded_verdict_and_coverage(positive_replay) -> None:
    _, returncode, receipt = positive_replay
    replay = receipt.get("current_wrapper_replay") if isinstance(receipt, dict) else None
    condition = (
        returncode == 0
        and isinstance(replay, dict)
        and replay.get("fresh_checkout") is True
        and replay.get("fresh_semantic_verdict") == replay.get("pinned_semantic_verdict")
        and replay.get("fresh_coverage") == replay.get("pinned_coverage")
    )
    _assert_behavior(
        condition,
        "CER-A-92898EBFD70B-BEHAVIOR",
        "Fresh-checkout replay must reproduce the pinned verdict and coverage",
    )


@pytest.mark.cer_assertion("A-REPLAY-CURRENT-SNAPSHOT-COMPLETE")
@pytest.mark.cer_assertion("A-REPLAY-SNAPSHOT-BINDING")
def test_replay_result_contains_complete_current_snapshot_binding(positive_replay) -> None:
    _, returncode, receipt = positive_replay
    replay = receipt.get("current_wrapper_replay") if isinstance(receipt, dict) else None
    snapshot = replay.get("current_snapshot") if isinstance(replay, dict) else None
    condition = returncode == 0 and isinstance(snapshot, dict) and snapshot.get("sha256") and snapshot.get("roots")
    _assert_behavior(
        bool(condition),
        "F-REPLAY-INCOMPLETE-SNAPSHOT",
        "Replay results must bind a complete Current Snapshot",
    )


def test_replay_target_is_observed_by_validator_and_fresh_checkout_is_real(positive_replay) -> None:
    _, returncode, receipt = positive_replay
    replay = receipt["current_wrapper_replay"]
    verification = replay["target_verification"]
    assert returncode == 0
    assert verification["validator_observed_target"] is True
    assert verification["mutation_rejected"] is True
    assert Path(replay["fresh_replay"]["checkout_path"]).resolve() != ROOT.resolve()


@pytest.mark.cer_assertion("A-FCD3611EEC73-1")
def test_supported_replay_route_binds_effective_inspected_content(positive_replay) -> None:
    _, returncode, receipt = positive_replay
    replay = receipt.get("current_wrapper_replay") if isinstance(receipt, dict) else None
    inspected = replay.get("effective_inspected_content") if isinstance(replay, dict) else None
    condition = (
        returncode == 0
        and isinstance(inspected, dict)
        and inspected.get("path") == TARGET
        and isinstance(inspected.get("identity"), str)
        and inspected["identity"].startswith("sha256:")
    )
    _assert_behavior(
        condition,
        "F-FCD3611EEC73-1",
        "Supported replay routes must bind the effective inspected content",
    )

"""CER checks for detached Probe execution through the replay entrypoint."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"


def _assert_behavior(condition: bool, failure_id: str, message: str) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, message


def _positive_replay() -> tuple[int, int, dict[str, object] | None]:
    process = subprocess.Popen(
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
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    stdout, _ = process.communicate(timeout=60)
    try:
        receipt = json.loads(stdout)
    except json.JSONDecodeError:
        receipt = None
    return process.pid, process.returncode, receipt if isinstance(receipt, dict) else None


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
def test_detached_positive_probe_records_a_distinct_child_process() -> None:
    replay_pid, returncode, receipt = _positive_replay()
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
def test_detached_positive_probe_binds_input_target_outcome_and_output() -> None:
    _, returncode, receipt = _positive_replay()
    probe = _positive_probe(receipt)
    input_value = probe.get("input") if isinstance(probe, dict) else None
    command_outcome = probe.get("command_outcome") if isinstance(probe, dict) else None
    output = probe.get("output") if isinstance(probe, dict) else None
    condition = (
        returncode == 0
        and isinstance(input_value, dict)
        and input_value.get("target") == TARGET
        and isinstance(probe, dict)
        and probe.get("actual_target") == TARGET
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
    child_script = "\n".join(
        [
            "import sys",
            f"sys.path.insert(0, {str(ENTRY.parent)!r})",
            "import skill_package_replay as replay",
            "replay.validator_command = lambda validator, value, target: [sys.executable, '-c', 'raise SystemExit(0)']",
            f"sys.argv = ['skill_package_replay.py', 'replay-package', '--target', {TARGET!r}, '--capability', {CAPABILITY!r}, '--probe-mode', 'fresh']",
            "raise SystemExit(replay.main())",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", child_script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    _assert_behavior(
        result.returncode != 0 and "negative compatibility probe unexpectedly passed" in result.stderr,
        "ALWAYS_SUCCESS_FALSE_NEGATIVE_PASSED",
        "An always-success validator must produce a failed detached Probe outcome",
    )

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as element_tree


TEST_PROJECT = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"
TEST_CLASS = "PhaseA.Platform.Tests.PhaseB.Repair.S32BoundaryTests"
TRX_NAMESPACE = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
OBSERVATION_FIELDS = {
    "fixture",
    "sample",
    "fixtureSizeBytes",
    "restoreStatus",
    "contentValidated",
    "routeValidated",
    "cleanupValidated",
    "timingSampleRecorded",
    "approvalTicks",
    "wallTicks",
    "measuredTicks",
}


class BoundaryHarnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class BoundaryCaseResult:
    fully_qualified_name: str
    outcome: str
    observation: dict[str, str]
    error_message: str


def run_boundary_case(repository_root: Path, method_name: str) -> BoundaryCaseResult:
    fully_qualified_name = f"{TEST_CLASS}.{method_name}"
    with tempfile.TemporaryDirectory(prefix="s32-trx-", ignore_cleanup_errors=True) as results_directory:
        argv = [
            "dotnet",
            "test",
            TEST_PROJECT,
            "--no-restore",
            "--no-build",
            "--filter",
            f"FullyQualifiedName={fully_qualified_name}",
            "--logger",
            "trx",
            "--results-directory",
            results_directory,
        ]
        try:
            completed = subprocess.run(
                argv,
                cwd=repository_root,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            raise BoundaryHarnessError(f"S32 harness could not run {fully_qualified_name}") from error

        trx_files = list(Path(results_directory).glob("*.trx"))
        if len(trx_files) != 1:
            diagnostics = (completed.stdout + completed.stderr).strip()[-2000:]
            raise BoundaryHarnessError(
                f"S32 harness did not produce one fresh TRX for {fully_qualified_name}: "
                f"exit={completed.returncode}, trx_count={len(trx_files)}, diagnostics={diagnostics!r}"
            )
        if completed.returncode not in {0, 1}:
            raise BoundaryHarnessError(
                f"S32 harness invocation failed for {fully_qualified_name}: exit={completed.returncode}"
            )
        return _read_case_result(trx_files[0], fully_qualified_name, completed.returncode)


def assert_boundary_observation(
    result: BoundaryCaseResult, method_name: str, failure_id: str
) -> None:
    if result.outcome == "Passed":
        if not _proves_required_observation(result.observation, method_name):
            raise BoundaryHarnessError(
                f"S32 boundary passed without its required real observation: {result.fully_qualified_name}"
            )
        return
    if result.outcome != "Failed":
        raise BoundaryHarnessError(
            f"S32 boundary result was not executable for {result.fully_qualified_name}: {result.outcome!r}"
        )
    if failure_id not in result.error_message:
        raise BoundaryHarnessError(
            f"S32 boundary failed before its bound behavior assertion: {result.fully_qualified_name}"
        )
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {result.fully_qualified_name} did not prove its production boundary")


def _read_case_result(trx_path: Path, fully_qualified_name: str, return_code: int) -> BoundaryCaseResult:
    try:
        root = element_tree.parse(trx_path).getroot()
    except element_tree.ParseError as error:
        raise BoundaryHarnessError(f"S32 harness produced an unreadable TRX for {fully_qualified_name}") from error
    test_ids = {
        unit_test.attrib["id"]
        for unit_test in root.findall(".//trx:UnitTest", TRX_NAMESPACE)
        if unit_test.attrib.get("name") == fully_qualified_name
    }
    if len(test_ids) != 1:
        raise BoundaryHarnessError(f"S32 TRX did not contain exactly one expected test identity: {fully_qualified_name}")
    results = [
        result
        for result in root.findall(".//trx:UnitTestResult", TRX_NAMESPACE)
        if result.attrib.get("testId") in test_ids
    ]
    if len(results) != 1:
        raise BoundaryHarnessError(f"S32 TRX did not contain exactly one result for {fully_qualified_name}")
    result = results[0]
    outcome = result.attrib.get("outcome", "")
    if outcome not in {"Passed", "Failed"}:
        raise BoundaryHarnessError(f"S32 boundary result was not executable for {fully_qualified_name}: {outcome!r}")
    if (outcome == "Passed") != (return_code == 0):
        raise BoundaryHarnessError(f"S32 harness exit did not match the target boundary result: {fully_qualified_name}")
    stdout = "\n".join(node.text or "" for node in result.findall(".//trx:StdOut", TRX_NAMESPACE))
    observation_prefix = f"S32-OBSERVATION {fully_qualified_name.rsplit('.', 1)[1]};"
    observations = [line.removeprefix(observation_prefix) for line in stdout.splitlines() if line.startswith(observation_prefix)]
    if outcome == "Passed" and len(observations) != 1:
        raise BoundaryHarnessError(f"S32 boundary did not emit exactly one observation: {fully_qualified_name}")
    observation = _parse_observation(observations[0], fully_qualified_name) if observations else {}
    return BoundaryCaseResult(
        fully_qualified_name,
        outcome,
        observation,
        result.findtext("trx:Output/trx:ErrorInfo/trx:Message", default="", namespaces=TRX_NAMESPACE),
    )


def _parse_observation(raw: str, fully_qualified_name: str) -> dict[str, str]:
    observation = dict(part.split("=", 1) for part in raw.split(";") if "=" in part)
    if set(observation) != OBSERVATION_FIELDS:
        raise BoundaryHarnessError(f"S32 observation was incomplete for {fully_qualified_name}")
    return observation


def _proves_required_observation(observation: dict[str, str], method_name: str) -> bool:
    try:
        fixture_size = int(observation["fixtureSizeBytes"])
        approval_ticks = int(observation["approvalTicks"])
        wall_ticks = int(observation["wallTicks"])
        measured_ticks = int(observation["measuredTicks"])
    except (KeyError, ValueError) as error:
        raise BoundaryHarnessError("S32 observation did not contain parseable drill measurements") from error
    common_sample_binding = (
        observation["fixture"].startswith("s32-fixture-")
        and observation["sample"].startswith("s32-sample-")
        and 0 < fixture_size <= 100 * 1024 * 1024
        and observation["restoreStatus"] == "Published"
    )
    checks = {
        "O_24C61509CBFA": (
            observation["contentValidated"] == "true"
            and observation["routeValidated"] == "true"
            and observation["cleanupValidated"] == "true"
            and observation["timingSampleRecorded"] == "true"
        ),
        "O_3180CF499B2D": observation["contentValidated"] == "true",
        "O_51B1E0927330": (
            observation["contentValidated"] == "true" and observation["routeValidated"] == "true"
        ),
        "O_54814D965C36": (
            observation["routeValidated"] == "true" and observation["cleanupValidated"] == "true"
        ),
        "O_9F7DA3182063": observation["contentValidated"] == "true",
        "O_A1983E093799": (
            observation["routeValidated"] == "true"
            and observation["timingSampleRecorded"] == "true"
            and approval_ticks > 0
            and measured_ticks >= 0
            and measured_ticks == wall_ticks - approval_ticks
        ),
    }
    if method_name not in checks:
        raise BoundaryHarnessError(f"S32 wrapper has no observation predicate for {method_name}")
    return common_sample_binding and checks[method_name]

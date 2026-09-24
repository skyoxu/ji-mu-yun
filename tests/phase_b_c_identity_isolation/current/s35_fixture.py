from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ElementTree


ASSERTION_ID = "A-OBF44FB067530"
FAILURE_ID = "FAILURE-O-BF44FB067530"
CASE_NAME = "PhaseA.Platform.Tests.PhaseB.Repair.S35BoundaryTests.O_BF44FB067530"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIRECTORY = Path(__file__).resolve().parent


class DotnetBoundaryHarnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class DotnetBoundaryResult:
    outcome: str
    operation_id: str
    snapshot_inventory_count: int


def run_s35_boundary() -> DotnetBoundaryResult:
    existing_trx_files = set(RESULTS_DIRECTORY.glob("*.trx"))
    environment = os.environ.copy()
    environment["S35_TEST_ROOT"] = str(RESULTS_DIRECTORY)
    try:
        completed = subprocess.run(
            [
                "dotnet",
                "test",
                "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj",
                "--filter",
                "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S35BoundaryTests.O_BF44FB067530",
                "--logger",
                "trx",
                "--results-directory",
                str(RESULTS_DIRECTORY),
            ],
            cwd=REPOSITORY_ROOT,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
            env=environment,
        )
    except FileNotFoundError as error:
        raise DotnetBoundaryHarnessError("dotnet is unavailable for the S35 boundary test") from error
    except subprocess.TimeoutExpired as error:
        raise DotnetBoundaryHarnessError("S35 boundary test timed out") from error

    fresh_trx_files = set(RESULTS_DIRECTORY.glob("*.trx")) - existing_trx_files
    if len(fresh_trx_files) != 1:
        raise DotnetBoundaryHarnessError(
            f"S35 boundary test produced {len(fresh_trx_files)} fresh TRX files instead of one result; "
            f"exit={completed.returncode}; stdout={completed.stdout}; stderr={completed.stderr}"
        )

    trx_path = fresh_trx_files.pop()
    try:
        return _parse_s35_result(trx_path, completed)
    finally:
        trx_path.unlink(missing_ok=True)


def _parse_s35_result(trx_path: Path, completed: subprocess.CompletedProcess[str]) -> DotnetBoundaryResult:
    try:
        root = ElementTree.parse(trx_path).getroot()
    except ElementTree.ParseError as error:
        raise DotnetBoundaryHarnessError("S35 boundary test produced an unreadable TRX result") from error

    namespace = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
    expected_test_ids = {
        unit.attrib["id"]
        for unit in root.findall(".//trx:UnitTest", namespace)
        if (method := unit.find(".//trx:TestMethod", namespace)) is not None
        and method.attrib.get("className") == "PhaseA.Platform.Tests.PhaseB.Repair.S35BoundaryTests"
        and method.attrib.get("name") == "O_BF44FB067530"
    }
    if len(expected_test_ids) != 1:
        raise DotnetBoundaryHarnessError("S35 TRX did not identify the exact required C# case")

    results = [
        result
        for result in root.findall(".//trx:UnitTestResult", namespace)
        if result.attrib.get("testId") in expected_test_ids
    ]
    if len(results) != 1:
        raise DotnetBoundaryHarnessError("S35 TRX did not contain exactly one required case result")

    result = results[0]
    outcome = result.attrib.get("outcome")
    if outcome not in {"Passed", "Failed"}:
        raise DotnetBoundaryHarnessError(f"S35 C# case has non-behavioral outcome: {outcome!r}")

    error_message = "\n".join(
        message.text or "" for message in result.findall(".//trx:ErrorInfo/trx:Message", namespace)
    )
    standard_output = "\n".join(
        output.text or "" for output in result.findall(".//trx:StdOut", namespace)
    )
    if outcome == "Failed" and FAILURE_ID not in error_message:
        raise DotnetBoundaryHarnessError(
            "S35 C# case failed before its bound Snapshot behavior assertion.\n"
            f"dotnet stdout:\n{completed.stdout}\n"
            f"dotnet stderr:\n{completed.stderr}"
        )
    observation = re.search(
        r"migration-status=(?P<status>[^\s]+) operation-id=(?P<operation_id>[^\s]+) "
        r"snapshot-inventory-count=(?P<count>\d+)",
        standard_output,
    )
    if outcome == "Passed":
        if completed.returncode != 0:
            raise DotnetBoundaryHarnessError("S35 passed in TRX but dotnet test exited nonzero")
        if observation is None or observation.group("status") != "completed":
            raise DotnetBoundaryHarnessError("S35 passed without its required migration inventory observation")
    elif completed.returncode == 0:
        raise DotnetBoundaryHarnessError("S35 failed in TRX but dotnet test exited zero")

    return DotnetBoundaryResult(
        outcome=outcome,
        operation_id=observation.group("operation_id") if observation is not None else "",
        snapshot_inventory_count=int(observation.group("count")) if observation is not None else -1,
    )

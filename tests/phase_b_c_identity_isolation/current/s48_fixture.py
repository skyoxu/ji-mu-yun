from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as element_tree
from uuid import uuid4


TEST_PROJECT = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"
FULLY_QUALIFIED_NAME = "PhaseA.Platform.Tests.PhaseB.Repair.S48BoundaryTests.O_92963141AC9F"
TRX_NAMESPACE = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}


@dataclass(frozen=True)
class BoundaryCaseResult:
    fully_qualified_name: str
    outcome: str
    details: str


def run_boundary_case(repository_root: Path) -> BoundaryCaseResult:
    temporary_directory = Path(tempfile.gettempdir()) / f"s48-trx-{uuid4().hex}"
    temporary_directory.mkdir()
    try:
        results_directory = temporary_directory / "results"
        argv = [
            "dotnet",
            "test",
            "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj",
            "--filter",
            "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S48BoundaryTests.O_92963141AC9F",
            "--logger",
            "trx",
            "--results-directory",
            str(results_directory),
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
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"S48 harness timeout for {FULLY_QUALIFIED_NAME}") from error

        trx_files = list(results_directory.glob("*.trx"))
        if len(trx_files) != 1:
            diagnostics = (completed.stdout + completed.stderr).strip()[-2000:]
            raise RuntimeError(
                f"S48 harness did not produce one fresh TRX for {FULLY_QUALIFIED_NAME}: "
                f"exit={completed.returncode}, trx_count={len(trx_files)}, diagnostics={diagnostics!r}"
            )
        if completed.returncode not in (0, 1):
            raise RuntimeError(
                f"S48 harness invocation failed for {FULLY_QUALIFIED_NAME}: exit={completed.returncode}"
            )

        result = _read_case_result(trx_files[0])
        if result.outcome not in {"Passed", "Failed"}:
            raise RuntimeError(f"S48 boundary result was not executable for {FULLY_QUALIFIED_NAME}: {result.outcome!r}")
        if completed.returncode != 0 and result.outcome != "Failed":
            raise RuntimeError(f"S48 harness failed outside the target boundary for {FULLY_QUALIFIED_NAME}")
        return result
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


def assert_boundary_observation(result: BoundaryCaseResult) -> None:
    expected_observation = (
        "S48-OBSERVATION O-92963141AC9F "
        "stale-publication-rejected-current-fenced-publication-remains-authoritative"
    )
    failure_id = "FAILURE-O-92963141AC9F"
    if result.outcome == "Passed":
        if expected_observation not in result.details:
            raise RuntimeError(f"S48 boundary passed without its product observation: {result.fully_qualified_name}")
        return
    if failure_id not in result.details:
        raise RuntimeError(
            f"S48 boundary failed without its bound product failure id: {result.fully_qualified_name}; "
            f"TRX={result.details}"
        )
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {result.fully_qualified_name} did not prove {expected_observation}")


def _read_case_result(trx_path: Path) -> BoundaryCaseResult:
    try:
        root = element_tree.parse(trx_path).getroot()
    except element_tree.ParseError as error:
        raise RuntimeError(f"S48 harness produced an unreadable TRX for {FULLY_QUALIFIED_NAME}") from error

    test_ids = {
        unit_test.attrib["id"]
        for unit_test in root.findall(".//trx:UnitTest", TRX_NAMESPACE)
        if unit_test.attrib.get("name") == FULLY_QUALIFIED_NAME
    }
    if len(test_ids) != 1:
        raise RuntimeError(f"S48 TRX did not contain exactly one expected test identity for {FULLY_QUALIFIED_NAME}")

    matches = [
        result
        for result in root.findall(".//trx:UnitTestResult", TRX_NAMESPACE)
        if result.attrib.get("testId") in test_ids
    ]
    if len(matches) != 1:
        raise RuntimeError(f"S48 TRX did not contain exactly one result for {FULLY_QUALIFIED_NAME}")
    result = matches[0]
    return BoundaryCaseResult(
        FULLY_QUALIFIED_NAME,
        result.attrib.get("outcome", ""),
        element_tree.tostring(result, encoding="unicode"),
    )

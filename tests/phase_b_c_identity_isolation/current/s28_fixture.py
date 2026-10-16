from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as element_tree


TEST_PROJECT = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"
TEST_CLASS = "PhaseA.Platform.Tests.PhaseB.Repair.S28BoundaryTests"


@dataclass(frozen=True)
class BoundaryCaseResult:
    fully_qualified_name: str
    outcome: str
    details: str


def run_boundary_case(repository_root: Path, method_name: str) -> BoundaryCaseResult:
    fully_qualified_name = f"{TEST_CLASS}.{method_name}"
    # ADR-0041: isolate each TRX, not build artifacts, so the bounded probe remains observable.
    results_directory = repository_root / f"s28-trx-{uuid.uuid4().hex}"
    results_directory.mkdir()
    try:
        try:
            completed = subprocess.run(
                [
                    "dotnet",
                    "test",
                    TEST_PROJECT,
                    "--filter",
                    f"FullyQualifiedName={fully_qualified_name}",
                    "--logger",
                    "trx",
                    "--results-directory",
                    str(results_directory),
                ],
                cwd=repository_root,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=240,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"S28 harness timeout for {fully_qualified_name}") from error

        trx_files = list(results_directory.glob("*.trx"))
        if len(trx_files) != 1:
            raise RuntimeError(
                f"S28 harness did not produce one fresh TRX for {fully_qualified_name}: "
                f"exit={completed.returncode}; stdout={completed.stdout}; stderr={completed.stderr}"
            )

        result = _read_case_result(trx_files[0], fully_qualified_name)
        if completed.returncode not in (0, 1):
            raise RuntimeError(
                f"S28 harness invocation failed for {fully_qualified_name}: "
                f"exit={completed.returncode}; stdout={completed.stdout}; stderr={completed.stderr}"
            )
        if result.outcome not in {"Passed", "Failed"}:
            raise RuntimeError(f"S28 boundary result was not executable for {fully_qualified_name}: {result.outcome!r}")
        return result
    finally:
        shutil.rmtree(results_directory, ignore_errors=True)


def assert_boundary_passes(result: BoundaryCaseResult, failure_id: str) -> None:
    if result.outcome == "Passed":
        return
    if failure_id not in result.details:
        raise RuntimeError(
            f"S28 boundary failed without its bound product failure id for {result.fully_qualified_name}"
        )
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {result.details}")


def _read_case_result(trx_path: Path, fully_qualified_name: str) -> BoundaryCaseResult:
    namespace = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
    root = element_tree.parse(trx_path).getroot()
    test_ids = {
        unit_test.attrib["id"]
        for unit_test in root.findall(".//trx:UnitTest", namespace)
        if unit_test.attrib.get("name") == fully_qualified_name
    }
    if len(test_ids) != 1:
        raise RuntimeError(f"S28 TRX did not contain the expected test identity: {fully_qualified_name}")

    matching_results = [
        result
        for result in root.findall(".//trx:UnitTestResult", namespace)
        if result.attrib.get("testId") in test_ids
    ]
    if len(matching_results) != 1:
        raise RuntimeError(f"S28 TRX did not contain exactly one result for: {fully_qualified_name}")

    result = matching_results[0]
    return BoundaryCaseResult(
        fully_qualified_name=fully_qualified_name,
        outcome=result.attrib.get("outcome", ""),
        details=element_tree.tostring(result, encoding="unicode"),
    )

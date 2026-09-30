from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as element_tree


TEST_PROJECT = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"
TEST_CLASS = "PhaseA.Platform.Tests.PhaseB.Repair.S60BoundaryTests"


@dataclass(frozen=True)
class BoundaryCaseResult:
    fully_qualified_name: str
    outcome: str
    details: str


def run_boundary_case(repository_root: Path, method_name: str) -> BoundaryCaseResult:
    with tempfile.TemporaryDirectory(prefix="s60-trx-", ignore_cleanup_errors=True) as results_directory:
        if method_name == "O_1E49B9F4CF89":
            fully_qualified_name = f"{TEST_CLASS}.O_1E49B9F4CF89"
            command = [
                "dotnet",
                "test",
                "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj",
                "--filter",
                "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S60BoundaryTests.O_1E49B9F4CF89",
                "--logger",
                "trx",
                "--results-directory",
                results_directory,
            ]
        elif method_name == "O_3B86525DF394":
            fully_qualified_name = f"{TEST_CLASS}.O_3B86525DF394"
            command = [
                "dotnet",
                "test",
                "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj",
                "--filter",
                "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S60BoundaryTests.O_3B86525DF394",
                "--logger",
                "trx",
                "--results-directory",
                results_directory,
            ]
        else:
            raise ValueError(f"unknown S60 boundary method: {method_name}")

        try:
            completed = subprocess.run(
                command,
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
            raise RuntimeError(f"S60 harness timeout for {fully_qualified_name}") from error

        trx_files = list(Path(results_directory).glob("*.trx"))
        if len(trx_files) != 1:
            raise RuntimeError(
                f"S60 harness did not produce one fresh TRX for {fully_qualified_name}: "
                f"exit={completed.returncode}; stdout={completed.stdout}; stderr={completed.stderr}"
            )
        if completed.returncode not in (0, 1):
            raise RuntimeError(
                f"S60 harness invocation failed for {fully_qualified_name}: "
                f"exit={completed.returncode}; stdout={completed.stdout}; stderr={completed.stderr}"
            )

        result = _read_case_result(trx_files[0], fully_qualified_name)
        if result.outcome not in {"Passed", "Failed"}:
            raise RuntimeError(f"S60 boundary result was not executable for {fully_qualified_name}: {result.outcome!r}")
        if completed.returncode != 0 and result.outcome != "Failed":
            raise RuntimeError(f"S60 harness failed outside the target boundary for {fully_qualified_name}")
        return result


def assert_boundary_observation(
    result: BoundaryCaseResult, expected_observation: str, failure_id: str
) -> None:
    if result.outcome == "Passed":
        if expected_observation not in result.details:
            raise RuntimeError(f"S60 boundary passed without its product observation: {result.fully_qualified_name}")
        return
    if failure_id not in result.details:
        raise RuntimeError(
            f"S60 boundary failed without its bound product failure id: {result.fully_qualified_name}; "
            f"TRX={result.details}"
        )
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {result.fully_qualified_name} did not prove {expected_observation}")


def _read_case_result(trx_path: Path, fully_qualified_name: str) -> BoundaryCaseResult:
    namespace = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
    root = element_tree.parse(trx_path).getroot()
    test_ids = {
        unit_test.attrib["id"]
        for unit_test in root.findall(".//trx:UnitTest", namespace)
        if unit_test.attrib.get("name") == fully_qualified_name
    }
    if len(test_ids) != 1:
        raise RuntimeError(f"S60 TRX did not contain the expected test identity: {fully_qualified_name}")

    matching_results = [
        result
        for result in root.findall(".//trx:UnitTestResult", namespace)
        if result.attrib.get("testId") in test_ids
    ]
    if len(matching_results) != 1:
        raise RuntimeError(f"S60 TRX did not contain exactly one result for: {fully_qualified_name}")

    result = matching_results[0]
    return BoundaryCaseResult(
        fully_qualified_name,
        result.attrib.get("outcome", ""),
        element_tree.tostring(result, encoding="unicode"),
    )

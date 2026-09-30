from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as element_tree


TEST_PROJECT = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"
TEST_CLASS = "PhaseA.Platform.Tests.PhaseB.Repair.S34BoundaryTests"


class BoundaryHarnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class BoundaryResult:
    outcome: str
    details: str


def run_boundary_case(repository_root: Path, method_name: str) -> BoundaryResult:
    fully_qualified_name = f"{TEST_CLASS}.{method_name}"
    with tempfile.TemporaryDirectory(prefix="s34-trx-", ignore_cleanup_errors=True) as results_directory:
        command = [
            "dotnet", "test", TEST_PROJECT,
            "--filter", f"FullyQualifiedName={fully_qualified_name}",
            "--logger", "trx", "--results-directory", results_directory,
        ]
        try:
            completed = subprocess.run(
                command, cwd=repository_root, shell=False, check=False,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            raise BoundaryHarnessError(f"S34 harness could not run {fully_qualified_name}") from error

        trx_files = list(Path(results_directory).glob("*.trx"))
        if len(trx_files) != 1:
            raise BoundaryHarnessError(f"S34 harness did not produce one fresh TRX for {fully_qualified_name}")
        root = element_tree.parse(trx_files[0]).getroot()
        namespace = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
        test_ids = {
            unit.attrib["id"] for unit in root.findall(".//trx:UnitTest", namespace)
            if unit.attrib.get("name") == fully_qualified_name
        }
        results = [
            result for result in root.findall(".//trx:UnitTestResult", namespace)
            if result.attrib.get("testId") in test_ids
        ]
        if len(test_ids) != 1 or len(results) != 1:
            raise BoundaryHarnessError(f"S34 TRX did not contain exactly the requested case: {fully_qualified_name}")
        result = results[0]
        outcome = result.attrib.get("outcome", "")
        if outcome not in {"Passed", "Failed"} or (completed.returncode not in {0, 1}):
            raise BoundaryHarnessError(f"S34 harness could not execute {fully_qualified_name}: exit={completed.returncode}")
        if outcome == "Passed" and completed.returncode != 0:
            raise BoundaryHarnessError(f"S34 passed TRX case but dotnet exited nonzero: {fully_qualified_name}")
        if outcome == "Failed" and completed.returncode == 0:
            raise BoundaryHarnessError(f"S34 failed TRX case but dotnet exited zero: {fully_qualified_name}")
        return BoundaryResult(outcome, element_tree.tostring(result, encoding="unicode"))


def assert_boundary(result: BoundaryResult, method_name: str, failure_id: str) -> None:
    if result.outcome == "Passed" and f"S34-OBSERVATION {method_name}" in result.details:
        return
    if result.outcome != "Failed":
        raise BoundaryHarnessError(f"S34 case did not provide its required observation: {method_name}")
    if failure_id not in result.details:
        raise BoundaryHarnessError(f"S34 case failed before its bound behavior assertion: {method_name}")
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {method_name} did not prove its production-boundary behavior")

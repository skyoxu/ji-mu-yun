from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as element_tree


TEST_PROJECT = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"
TEST_CLASS = "PhaseA.Platform.Tests.PhaseB.Repair.S46BoundaryTests"
TRX_NAMESPACE = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}


@dataclass(frozen=True)
class BoundaryResult:
    case_name: str
    outcome: str
    details: str


def invoke_boundary_test(repository_root: Path, method_name: str) -> BoundaryResult:
    case_name = f"{TEST_CLASS}.{method_name}"
    with tempfile.TemporaryDirectory(prefix="s46-trx-", dir=repository_root, ignore_cleanup_errors=True) as results_directory:
        argv = [
            "dotnet",
            "test",
            TEST_PROJECT,
            "--filter",
            f"FullyQualifiedName={case_name}",
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
                timeout=240,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            raise RuntimeError(f"S46 harness could not run {case_name}") from error

        trx_files = list(Path(results_directory).glob("*.trx"))
        if len(trx_files) != 1:
            diagnostics = (completed.stdout + completed.stderr).strip()[-3000:]
            raise RuntimeError(
                f"S46 harness did not produce one fresh TRX for {case_name}: "
                f"exit={completed.returncode}, trx_count={len(trx_files)}, diagnostics={diagnostics!r}"
            )
        try:
            root = element_tree.parse(trx_files[0]).getroot()
        except element_tree.ParseError as error:
            raise RuntimeError(f"S46 harness produced unreadable TRX for {case_name}") from error
        test_ids = {
            item.attrib["id"]
            for item in root.findall(".//trx:UnitTest", TRX_NAMESPACE)
            if item.attrib.get("name") == case_name
        }
        if len(test_ids) != 1:
            raise RuntimeError(f"S46 TRX did not contain exactly one test identity: {case_name}")
        results = [
            item
            for item in root.findall(".//trx:UnitTestResult", TRX_NAMESPACE)
            if item.attrib.get("testId") in test_ids
        ]
        if len(results) != 1:
            raise RuntimeError(f"S46 TRX did not contain exactly one result: {case_name}")
        result = results[0]
        outcome = result.attrib.get("outcome", "")
        if outcome not in {"Passed", "Failed"}:
            raise RuntimeError(f"S46 boundary was not executable for {case_name}: {outcome!r}")
        if (completed.returncode == 0) != (outcome == "Passed"):
            raise RuntimeError(f"S46 harness failed outside the target boundary for {case_name}")
        return BoundaryResult(case_name, outcome, element_tree.tostring(result, encoding="unicode"))


def assert_boundary_observation(result: BoundaryResult, expected_observation: str, failure_id: str) -> None:
    if result.outcome == "Passed":
        if expected_observation not in result.details:
            raise RuntimeError(f"S46 boundary passed without its product observation: {result.case_name}")
        return
    if failure_id not in result.details:
        raise RuntimeError(f"S46 boundary failed before its bound behavior assertion: {result.case_name}")
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {result.case_name} did not prove the declared boundary")

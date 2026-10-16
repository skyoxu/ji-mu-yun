from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as element_tree


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
TEST_PROJECT = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"
CASE_NAMES = {
    "O_CEEBD932678A": "PhaseA.Platform.Tests.PhaseB.Repair.S56BoundaryTests.O_CEEBD932678A",
}


@dataclass(frozen=True)
class BoundaryCaseResult:
    fully_qualified_name: str
    outcome: str
    error_message: str


def invoke_s56_boundary(case_name: str) -> BoundaryCaseResult:
    fully_qualified_name = CASE_NAMES[case_name]
    with tempfile.TemporaryDirectory(prefix="s56-trx-", dir=r"C:\tmp") as temporary_directory:
        results_directory = Path(temporary_directory)
        try:
            completed = subprocess.run(
                [
                    "dotnet",
                    "test",
                    "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj",
                    "--filter",
                    f"FullyQualifiedName={fully_qualified_name}",
                    "--logger",
                    "trx",
                    "--results-directory",
                    str(results_directory),
                ],
                cwd=REPOSITORY_ROOT,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"S56 harness timeout for {fully_qualified_name}") from error

        trx_files = list(results_directory.glob("*.trx"))
        if len(trx_files) != 1:
            diagnostics = (completed.stdout + completed.stderr).strip()[-2000:]
            raise RuntimeError(
                f"S56 harness did not produce one fresh TRX for {fully_qualified_name}: "
                f"exit={completed.returncode}, trx_count={len(trx_files)}, diagnostics={diagnostics!r}"
            )
        if completed.returncode not in {0, 1}:
            raise RuntimeError(f"S56 harness failed outside the target boundary for {fully_qualified_name}")

        return _read_case_result(trx_files[0], fully_qualified_name)


def assert_behavior(result: BoundaryCaseResult, failure_id: str) -> None:
    if result.outcome == "Passed":
        return
    if result.outcome != "Failed" or failure_id not in result.error_message:
        raise RuntimeError(
            f"S56 boundary did not report a behavioral assertion failure for {result.fully_qualified_name}"
        )
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {result.error_message}")


def _read_case_result(trx_path: Path, fully_qualified_name: str) -> BoundaryCaseResult:
    namespace = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
    root = element_tree.parse(trx_path).getroot()
    test_ids = {
        unit_test.attrib["id"]
        for unit_test in root.findall(".//trx:UnitTest", namespace)
        if unit_test.attrib.get("name") == fully_qualified_name
    }
    if len(test_ids) != 1:
        raise RuntimeError(f"S56 TRX did not contain the expected test identity: {fully_qualified_name}")
    matching_results = [
        result
        for result in root.findall(".//trx:UnitTestResult", namespace)
        if result.attrib.get("testId") in test_ids
    ]
    if len(matching_results) != 1:
        raise RuntimeError(f"S56 TRX did not contain exactly one result for: {fully_qualified_name}")

    result = matching_results[0]
    error_message = result.findtext(
        "trx:Output/trx:ErrorInfo/trx:Message", default="", namespaces=namespace
    )
    return BoundaryCaseResult(fully_qualified_name, result.attrib.get("outcome", ""), error_message)

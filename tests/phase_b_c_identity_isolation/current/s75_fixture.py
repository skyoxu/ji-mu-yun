from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import xml.etree.ElementTree as element_tree


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class BoundaryCaseResult:
    fully_qualified_name: str
    outcome: str
    error_message: str


def invoke_s75_boundary(tmp_path: Path, case_name: str) -> BoundaryCaseResult:
    results_directory = tmp_path / case_name
    results_directory.mkdir()

    if case_name == "O_AB9213E2F95A":
        fully_qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S75BoundaryTests.O_AB9213E2F95A"
        command = [
            "dotnet",
            "test",
            "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj",
            "--filter",
            "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S75BoundaryTests.O_AB9213E2F95A",
            "--logger",
            "trx",
            "--results-directory",
            str(results_directory),
        ]
    elif case_name == "O_1C96420A7A74":
        fully_qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S75BoundaryTests.O_1C96420A7A74"
        command = [
            "dotnet",
            "test",
            "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj",
            "--filter",
            "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S75BoundaryTests.O_1C96420A7A74",
            "--logger",
            "trx",
            "--results-directory",
            str(results_directory),
        ]
    else:
        raise ValueError(f"unknown S75 boundary method: {case_name}")

    try:
        completed = subprocess.run(
            command,
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
        raise RuntimeError(f"S75 harness timeout for {fully_qualified_name}") from error

    trx_files = list(results_directory.glob("*.trx"))
    if len(trx_files) != 1:
        diagnostics = (completed.stdout + completed.stderr).strip()[-2000:]
        raise RuntimeError(
            f"S75 harness did not produce one fresh TRX for {fully_qualified_name}: "
            f"exit={completed.returncode}, trx_count={len(trx_files)}, diagnostics={diagnostics!r}"
        )
    if completed.returncode not in {0, 1}:
        raise RuntimeError(f"S75 harness failed outside the target boundary for {fully_qualified_name}")

    result = _read_case_result(trx_files[0], fully_qualified_name)
    if result.outcome not in {"Passed", "Failed"}:
        raise RuntimeError(f"S75 boundary result was not executable for {fully_qualified_name}: {result.outcome!r}")
    if completed.returncode != 0 and result.outcome != "Failed":
        raise RuntimeError(f"S75 harness failed outside the target boundary for {fully_qualified_name}")
    return result


def assert_behavior(result: BoundaryCaseResult, failure_id: str) -> None:
    if result.outcome == "Passed":
        return
    if result.outcome != "Failed" or failure_id not in result.error_message:
        raise RuntimeError(
            f"S75 boundary did not report its behavioral assertion failure for {result.fully_qualified_name}"
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
        raise RuntimeError(f"S75 TRX did not contain the expected test identity: {fully_qualified_name}")

    matching_results = [
        result
        for result in root.findall(".//trx:UnitTestResult", namespace)
        if result.attrib.get("testId") in test_ids
    ]
    if len(matching_results) != 1:
        raise RuntimeError(f"S75 TRX did not contain exactly one result for: {fully_qualified_name}")

    result = matching_results[0]
    error_message = result.findtext(
        "trx:Output/trx:ErrorInfo/trx:Message", default="", namespaces=namespace
    )
    return BoundaryCaseResult(fully_qualified_name, result.attrib.get("outcome", ""), error_message)

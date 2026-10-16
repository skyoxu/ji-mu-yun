from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as element_tree


TEST_CASE = "PhaseA.Platform.Tests.PhaseB.Repair.S30BoundaryTests.O_13F33C30B03B"


@dataclass(frozen=True)
class BoundaryResult:
    outcome: str
    details: str


@contextmanager
def _fresh_results_directory(repository_root: Path):
    results_directory = repository_root / f"s30-trx-{uuid.uuid4().hex}"
    results_directory.mkdir()
    try:
        yield str(results_directory)
    finally:
        shutil.rmtree(results_directory, ignore_errors=True)


def run_boundary_case(repository_root: Path) -> BoundaryResult:
    with _fresh_results_directory(repository_root) as results_directory:
        try:
            completed = subprocess.run(
                [
                    "dotnet",
                    "test",
                    "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj",
                    "--filter",
                    "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S30BoundaryTests.O_13F33C30B03B",
                    "--logger",
                    "trx",
                    "--results-directory",
                    results_directory,
                    "--artifacts-path",
                    results_directory,
                ],
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
            raise RuntimeError(f"S30 harness timeout for {TEST_CASE}") from error

        trx_files = list(Path(results_directory).glob("*.trx"))
        if len(trx_files) != 1:
            raise RuntimeError(
                f"S30 harness did not produce one fresh TRX for {TEST_CASE}: "
                f"exit={completed.returncode}; stdout={completed.stdout}; stderr={completed.stderr}"
            )

        result = _read_case_result(trx_files[0])
        if completed.returncode not in (0, 1):
            raise RuntimeError(
                f"S30 harness invocation failed for {TEST_CASE}: "
                f"exit={completed.returncode}; stdout={completed.stdout}; stderr={completed.stderr}"
            )
        if result.outcome not in {"Passed", "Failed"}:
            raise RuntimeError(f"S30 boundary result was not executable for {TEST_CASE}: {result.outcome!r}")
        if completed.returncode != 0 and result.outcome != "Failed":
            raise RuntimeError(f"S30 harness failed outside the target boundary for {TEST_CASE}")
        return result


def assert_boundary_observation(result: BoundaryResult) -> None:
    observation = (
        "S30-OBSERVATION O-13F33C30B03B "
        "prohibited-extension-absent-from-manifest-export-and-retained-payload-"
        "while-policy-metadata-and-description-remain"
    )
    failure_id = "FAILURE-O-13F33C30B03B"
    if result.outcome == "Passed" and observation in result.details:
        return
    if result.outcome != "Failed":
        raise RuntimeError(f"S30 boundary did not prove its expected observation: {TEST_CASE}")
    if failure_id not in result.details:
        raise RuntimeError(f"S30 boundary failed without its bound product failure id: {TEST_CASE}")
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {TEST_CASE} did not prove the required Snapshot boundary behavior")


def _read_case_result(trx_path: Path) -> BoundaryResult:
    namespace = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
    root = element_tree.parse(trx_path).getroot()
    test_ids = {
        unit_test.attrib["id"]
        for unit_test in root.findall(".//trx:UnitTest", namespace)
        if unit_test.attrib.get("name") == TEST_CASE
    }
    if len(test_ids) != 1:
        raise RuntimeError(f"S30 TRX did not contain the expected test identity: {TEST_CASE}")

    matching_results = [
        result
        for result in root.findall(".//trx:UnitTestResult", namespace)
        if result.attrib.get("testId") in test_ids
    ]
    if len(matching_results) != 1:
        raise RuntimeError(f"S30 TRX did not contain exactly one result for: {TEST_CASE}")

    result = matching_results[0]
    return BoundaryResult(
        outcome=result.attrib.get("outcome", ""),
        details=element_tree.tostring(result, encoding="unicode"),
    )

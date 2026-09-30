from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as element_tree


TEST_PROJECT = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"
TEST_CASE = "PhaseA.Platform.Tests.PhaseB.Repair.S44BoundaryTests.O_6C4973EE3FE2"


@dataclass(frozen=True)
class BoundaryResult:
    outcome: str
    details: str


# ADR-0041: one .NET execution covers the full matrix; each pytest case checks its own row.
@lru_cache(maxsize=1)
def invoke_boundary_test(repository_root: Path) -> BoundaryResult:
    with tempfile.TemporaryDirectory(prefix="s44-trx-", ignore_cleanup_errors=True) as results_directory:
        argv = [
            "dotnet",
            "test",
            TEST_PROJECT,
            "--filter",
            "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S44BoundaryTests.O_6C4973EE3FE2",
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
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"S44 harness timeout for {TEST_CASE}") from error

        trx_files = list(Path(results_directory).glob("*.trx"))
        if len(trx_files) != 1:
            diagnostics = (completed.stdout + completed.stderr).strip()[-2000:]
            raise RuntimeError(
                f"S44 harness did not produce one fresh TRX for {TEST_CASE}: "
                f"exit={completed.returncode}, trx_count={len(trx_files)}, diagnostics={diagnostics!r}"
            )
        result = _read_result(trx_files[0])
        if result.outcome not in {"Passed", "Failed"}:
            raise RuntimeError(f"S44 boundary was not executable for {TEST_CASE}: {result.outcome!r}")
        if completed.returncode != 0 and result.outcome != "Failed":
            raise RuntimeError(f"S44 harness failed outside the target boundary for {TEST_CASE}")
        return result


def assert_matrix_case(result: BoundaryResult, category: str, condition: str, failure_id: str) -> None:
    expected_case = (
        f"S44-CASE category={category} condition={condition} "
        f"placement_reference={'null' if condition == 'null' else f'{category}-{condition}'} "
        "authority=server-records restore=content"
    )
    if result.outcome == "Passed":
        if expected_case not in result.details:
            raise RuntimeError(f"S44 boundary passed without matrix case: {expected_case}")
        return
    if failure_id not in result.details:
        raise RuntimeError(f"S44 boundary failed without its bound product failure id: {TEST_CASE}")
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {TEST_CASE} did not prove {expected_case}")


def _read_result(trx_path: Path) -> BoundaryResult:
    namespace = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
    root = element_tree.parse(trx_path).getroot()
    test_ids = {
        unit_test.attrib["id"]
        for unit_test in root.findall(".//trx:UnitTest", namespace)
        if unit_test.attrib.get("name") == TEST_CASE
    }
    if len(test_ids) != 1:
        raise RuntimeError(f"S44 TRX did not contain the expected test identity: {TEST_CASE}")
    results = [
        item
        for item in root.findall(".//trx:UnitTestResult", namespace)
        if item.attrib.get("testId") in test_ids
    ]
    if len(results) != 1:
        raise RuntimeError(f"S44 TRX did not contain exactly one result for: {TEST_CASE}")
    result = results[0]
    return BoundaryResult(result.attrib.get("outcome", ""), element_tree.tostring(result, encoding="unicode"))

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as element_tree


TEST_PROJECT = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"
TEST_CLASS = "PhaseA.Platform.Tests.PhaseB.Repair.S37BoundaryTests"
TRX_NAMESPACE = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
TEMP_ROOT = Path("C:/tmp")


@dataclass(frozen=True)
class BoundaryCaseResult:
    fully_qualified_name: str
    outcome: str
    details: str


def run_boundary_case(repository_root: Path, method_name: str) -> BoundaryCaseResult:
    fully_qualified_name = f"{TEST_CLASS}.{method_name}"
    with tempfile.TemporaryDirectory(
        prefix="s37-trx-", dir=TEMP_ROOT, ignore_cleanup_errors=True
    ) as results_directory:
        artifacts_directory = Path(results_directory) / "artifacts"
        environment = os.environ.copy()
        environment["PHASEA_TEST_REPOSITORY_ROOT"] = str(repository_root)
        argv = [
            "dotnet",
            "test",
            TEST_PROJECT,
            "--artifacts-path",
            str(artifacts_directory),
            "--filter",
            f"FullyQualifiedName={fully_qualified_name}",
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
                env=environment,
                timeout=180,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"S37 harness timeout for {fully_qualified_name}") from error

        trx_files = list(Path(results_directory).glob("*.trx"))
        if len(trx_files) != 1:
            diagnostics = (completed.stdout + completed.stderr).strip()[-2000:]
            raise RuntimeError(
                f"S37 harness did not produce one fresh TRX for {fully_qualified_name}: "
                f"exit={completed.returncode}, trx_count={len(trx_files)}, diagnostics={diagnostics!r}"
            )
        if completed.returncode not in (0, 1):
            raise RuntimeError(
                f"S37 harness invocation failed for {fully_qualified_name}: "
                f"exit={completed.returncode}; stdout={completed.stdout}; stderr={completed.stderr}"
            )
        return _read_case_result(trx_files[0], fully_qualified_name)


def assert_boundary_passes(result: BoundaryCaseResult, failure_id: str) -> None:
    if result.outcome == "Passed":
        return
    if result.outcome != "Failed":
        raise RuntimeError(
            f"S37 boundary result was not executable for {result.fully_qualified_name}: {result.outcome!r}"
        )
    if failure_id not in result.details:
        raise RuntimeError(
            f"S37 boundary failed without its bound product failure id for {result.fully_qualified_name}"
        )
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {result.fully_qualified_name} did not prove its production boundary")


def _read_case_result(trx_path: Path, fully_qualified_name: str) -> BoundaryCaseResult:
    try:
        root = element_tree.parse(trx_path).getroot()
    except element_tree.ParseError as error:
        raise RuntimeError(f"S37 harness produced an unreadable TRX for {fully_qualified_name}") from error
    test_ids = {
        unit_test.attrib["id"]
        for unit_test in root.findall(".//trx:UnitTest", TRX_NAMESPACE)
        if unit_test.attrib.get("name") == fully_qualified_name
    }
    if len(test_ids) != 1:
        raise RuntimeError(f"S37 TRX did not contain exactly one expected test identity for {fully_qualified_name}")
    results = [
        result
        for result in root.findall(".//trx:UnitTestResult", TRX_NAMESPACE)
        if result.attrib.get("testId") in test_ids
    ]
    if len(results) != 1:
        raise RuntimeError(f"S37 TRX did not contain exactly one result for {fully_qualified_name}")
    result = results[0]
    return BoundaryCaseResult(
        fully_qualified_name,
        result.attrib.get("outcome", ""),
        element_tree.tostring(result, encoding="unicode"),
    )

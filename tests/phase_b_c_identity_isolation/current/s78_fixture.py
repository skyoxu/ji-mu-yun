from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as element_tree


TEST_PROJECT = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"
TEST_CLASS = "PhaseA.Platform.Tests.PhaseB.Repair.S78BoundaryTests"
TRX_NAMESPACE = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}


@dataclass(frozen=True)
class BoundaryCaseResult:
    fully_qualified_name: str
    outcome: str
    details: str


def run_boundary_case(repository_root: Path, method_name: str) -> BoundaryCaseResult:
    fully_qualified_name = f"{TEST_CLASS}.{method_name}"
    invocation_root = Path(tempfile.gettempdir()) / f"s78-dotnet-{uuid.uuid4().hex}"
    results_directory = invocation_root / "results"
    argv = [
        "dotnet",
        "test",
        TEST_PROJECT,
        "--no-restore",
        "--no-build",
        "--filter",
        f"FullyQualifiedName={fully_qualified_name}",
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
        raise RuntimeError(f"S78 harness timeout for {fully_qualified_name}") from error

    trx_files = list(results_directory.glob("*.trx"))
    if len(trx_files) != 1:
        diagnostics = (completed.stdout + completed.stderr).strip()[-2000:]
        raise RuntimeError(
            f"S78 harness did not produce one fresh TRX for {fully_qualified_name}: "
            f"exit={completed.returncode}, trx_count={len(trx_files)}, diagnostics={diagnostics!r}"
        )
    if completed.returncode not in (0, 1):
        raise RuntimeError(
            f"S78 harness invocation failed for {fully_qualified_name}: "
            f"exit={completed.returncode}; stdout={completed.stdout}; stderr={completed.stderr}"
        )
    return _read_case_result(trx_files[0], fully_qualified_name)


def assert_boundary_passes(result: BoundaryCaseResult, expected_observation: str, failure_id: str) -> None:
    if result.outcome == "Passed" and expected_observation in result.details:
        return
    if result.outcome != "Failed":
        raise RuntimeError(f"S78 boundary result was not executable for {result.fully_qualified_name}: {result.outcome!r}")
    if failure_id not in result.details:
        raise RuntimeError(f"S78 boundary failed without its bound product failure id for {result.fully_qualified_name}")
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {result.fully_qualified_name} did not prove {expected_observation}")


def _read_case_result(trx_path: Path, fully_qualified_name: str) -> BoundaryCaseResult:
    try:
        root = element_tree.parse(trx_path).getroot()
    except element_tree.ParseError as error:
        raise RuntimeError(f"S78 harness produced an unreadable TRX for {fully_qualified_name}") from error
    test_ids = {
        unit_test.attrib["id"]
        for unit_test in root.findall(".//trx:UnitTest", TRX_NAMESPACE)
        if unit_test.attrib.get("name") == fully_qualified_name
    }
    if len(test_ids) != 1:
        raise RuntimeError(f"S78 TRX did not contain exactly one expected test identity for {fully_qualified_name}")
    matches = [
        result
        for result in root.findall(".//trx:UnitTestResult", TRX_NAMESPACE)
        if result.attrib.get("testId") in test_ids
    ]
    if len(matches) != 1:
        raise RuntimeError(f"S78 TRX did not contain exactly one result for {fully_qualified_name}")
    result = matches[0]
    return BoundaryCaseResult(
        fully_qualified_name,
        result.attrib.get("outcome", ""),
        element_tree.tostring(result, encoding="unicode"),
    )

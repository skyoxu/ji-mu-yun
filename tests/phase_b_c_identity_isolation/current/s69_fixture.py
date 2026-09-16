from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as element_tree


TEST_PROJECT = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"
TEST_CLASS = "PhaseA.Platform.Tests.PhaseB.Repair.S69BoundaryTests"
TEMP_ROOT = Path("C:/tmp")


@dataclass(frozen=True)
class BoundaryCaseResult:
    fully_qualified_name: str
    outcome: str
    error_message: str


def assert_boundary_passes(result: BoundaryCaseResult, failure_id: str) -> None:
    if result.outcome == "Passed":
        return
    if failure_id not in result.error_message:
        raise RuntimeError(
            f"S69 boundary failed without its bound product failure id for {result.fully_qualified_name}"
        )
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {result.error_message}")


def run_boundary_case(repository_root: Path, method_name: str) -> BoundaryCaseResult:
    fully_qualified_name = f"{TEST_CLASS}.{method_name}"
    results_directory = Path(tempfile.mkdtemp(prefix=f"s69-trx-{uuid.uuid4().hex}-", dir=TEMP_ROOT))
    command = [
        "dotnet",
        "test",
        TEST_PROJECT,
        "--filter",
        f"FullyQualifiedName={fully_qualified_name}",
        "--logger",
        "trx",
        "--results-directory",
        str(results_directory),
        "--artifacts-path",
        str(results_directory),
    ]
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
    trx_files = list(results_directory.glob("*.trx"))
    if len(trx_files) != 1:
        raise RuntimeError(
            f"S69 harness did not produce one fresh TRX for {fully_qualified_name}: "
            f"exit={completed.returncode}; stdout={completed.stdout}; stderr={completed.stderr}"
        )

    result = _read_case_result(trx_files[0], fully_qualified_name)
    if completed.returncode not in (0, 1):
        raise RuntimeError(
            f"S69 harness invocation failed for {fully_qualified_name}: "
            f"exit={completed.returncode}; stdout={completed.stdout}; stderr={completed.stderr}"
        )
    return result


def _read_case_result(trx_path: Path, fully_qualified_name: str) -> BoundaryCaseResult:
    namespace = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
    root = element_tree.parse(trx_path).getroot()
    test_ids = {
        unit_test.attrib["id"]
        for unit_test in root.findall(".//trx:UnitTest", namespace)
        if unit_test.attrib.get("name") == fully_qualified_name
    }
    if len(test_ids) != 1:
        raise RuntimeError(f"S69 TRX did not contain the expected test identity: {fully_qualified_name}")

    matching_results = [
        result
        for result in root.findall(".//trx:UnitTestResult", namespace)
        if result.attrib.get("testId") in test_ids
    ]
    if len(matching_results) != 1:
        raise RuntimeError(f"S69 TRX did not contain exactly one result for: {fully_qualified_name}")

    result = matching_results[0]
    error_message = result.findtext("trx:Output/trx:ErrorInfo/trx:Message", default="", namespaces=namespace)
    return BoundaryCaseResult(fully_qualified_name, result.attrib.get("outcome", ""), error_message)

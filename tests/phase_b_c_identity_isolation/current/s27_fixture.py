from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as element_tree


TEST_PROJECT = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"
TEST_CLASS = "PhaseA.Platform.Tests.PhaseB.Repair.S27BoundaryTests"
METHOD_NAME = "O_EF3B026F4525"
TRX_NAMESPACE = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}


@dataclass(frozen=True)
class BoundaryCaseResult:
    fully_qualified_name: str
    outcome: str
    details: str


def run_boundary_case(repository_root: Path, method_name: str) -> BoundaryCaseResult:
    if method_name != METHOD_NAME:
        raise ValueError(f"unknown S27 boundary method: {method_name}")
    fully_qualified_name = f"{TEST_CLASS}.{method_name}"
    with tempfile.TemporaryDirectory(
        prefix="s27-trx-", dir=repository_root, ignore_cleanup_errors=True
    ) as results_directory:
        argv = [
            "dotnet",
            "test",
            TEST_PROJECT,
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
                timeout=180,
            )
        except FileNotFoundError as error:
            raise RuntimeError(f"S27 harness could not start dotnet for {fully_qualified_name}") from error
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"S27 harness timeout for {fully_qualified_name}") from error

        trx_files = list(Path(results_directory).glob("*.trx"))
        if len(trx_files) != 1:
            diagnostics = (completed.stdout + completed.stderr).strip()[-2000:]
            raise RuntimeError(
                f"S27 harness did not produce one fresh TRX for {fully_qualified_name}: "
                f"exit={completed.returncode}, trx_count={len(trx_files)}, diagnostics={diagnostics!r}"
            )
        if completed.returncode not in (0, 1):
            raise RuntimeError(
                f"S27 harness invocation failed for {fully_qualified_name}: exit={completed.returncode}"
            )

        result = _read_case_result(trx_files[0], fully_qualified_name)
        if result.outcome not in {"Passed", "Failed"}:
            raise RuntimeError(
                f"S27 boundary result was not executable for {fully_qualified_name}: {result.outcome!r}"
            )
        if (completed.returncode == 0) != (result.outcome == "Passed"):
            raise RuntimeError(f"S27 TRX outcome conflicts with the test exit code for {fully_qualified_name}")
        return result


def assert_boundary_observation(
    result: BoundaryCaseResult, expected_observation: str, failure_id: str
) -> None:
    if result.outcome == "Passed":
        if expected_observation not in result.details:
            raise RuntimeError(
                f"S27 boundary passed without its product observation: {result.fully_qualified_name}"
            )
        return
    if failure_id not in result.details:
        raise RuntimeError(
            f"S27 boundary failed before its bound behavior assertion: {result.fully_qualified_name}"
        )
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {result.fully_qualified_name} did not prove {expected_observation}")


def _read_case_result(trx_path: Path, fully_qualified_name: str) -> BoundaryCaseResult:
    try:
        root = element_tree.parse(trx_path).getroot()
    except element_tree.ParseError as error:
        raise RuntimeError(f"S27 harness produced unreadable TRX for {fully_qualified_name}") from error
    test_ids = {
        item.attrib["id"]
        for item in root.findall(".//trx:UnitTest", TRX_NAMESPACE)
        if item.attrib.get("name") == fully_qualified_name
    }
    if len(test_ids) != 1:
        raise RuntimeError(f"S27 TRX did not contain exactly one test identity: {fully_qualified_name}")
    results = [
        item
        for item in root.findall(".//trx:UnitTestResult", TRX_NAMESPACE)
        if item.attrib.get("testId") in test_ids
    ]
    if len(results) != 1:
        raise RuntimeError(f"S27 TRX did not contain exactly one result: {fully_qualified_name}")
    result = results[0]
    output = "\n".join(
        node.text or "" for node in result.findall(".//trx:StdOut", TRX_NAMESPACE)
    )
    error_message = result.findtext(
        "trx:Output/trx:ErrorInfo/trx:Message", default="", namespaces=TRX_NAMESPACE
    )
    return BoundaryCaseResult(
        fully_qualified_name,
        result.attrib.get("outcome", ""),
        f"{output}\n{error_message}",
    )

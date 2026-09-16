from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ElementTree


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROJECT_PATH = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"
TRX_NAMESPACE = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}


@dataclass(frozen=True)
class BoundaryResult:
    case_name: str
    outcome: str
    details: str


def invoke_boundary_test(case_name: str) -> BoundaryResult:
    with tempfile.TemporaryDirectory(prefix="s11-trx-", ignore_cleanup_errors=True) as results_directory:
        argv = [
            "dotnet",
            "test",
            PROJECT_PATH,
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
            raise RuntimeError(f"S11 harness timeout for {case_name}") from error

        trx_files = list(Path(results_directory).glob("*.trx"))
        if len(trx_files) != 1:
            diagnostics = (completed.stdout + completed.stderr).strip()[-2000:]
            raise RuntimeError(
                f"S11 harness did not produce one fresh TRX for {case_name}: "
                f"exit={completed.returncode}, trx_count={len(trx_files)}, diagnostics={diagnostics!r}"
            )

        try:
            root = ElementTree.parse(trx_files[0]).getroot()
        except ElementTree.ParseError as error:
            raise RuntimeError(f"S11 harness produced an unreadable TRX for {case_name}") from error

        test_ids = {
            test.attrib["id"]
            for test in root.findall(".//trx:UnitTest", TRX_NAMESPACE)
            if test.attrib.get("name") == case_name
        }
        if len(test_ids) != 1:
            raise RuntimeError(f"S11 TRX did not contain exactly one expected test identity for {case_name}")

        matching = [
            result
            for result in root.findall(".//trx:UnitTestResult", TRX_NAMESPACE)
            if result.attrib.get("testId") in test_ids
        ]
        if len(matching) != 1:
            raise RuntimeError(f"S11 TRX did not contain exactly one result for {case_name}")

        if completed.returncode not in (0, 1):
            raise RuntimeError(
                f"S11 harness invocation failed for {case_name}: "
                f"exit={completed.returncode}; stdout={completed.stdout}; stderr={completed.stderr}"
            )

        result = matching[0]
        outcome = result.attrib.get("outcome", "")
        if outcome not in {"Passed", "Failed"}:
            raise RuntimeError(f"S11 boundary result was not executable for {case_name}: {outcome!r}")
        return BoundaryResult(
            case_name=case_name,
            outcome=outcome,
            details=ElementTree.tostring(result, encoding="unicode"),
        )


def assert_behavior(result: BoundaryResult, expected_observation: str, failure_id: str) -> None:
    if result.outcome == "Passed" and expected_observation in result.details:
        return
    if result.outcome == "Failed" and failure_id not in result.details:
        raise RuntimeError(
            f"S11 boundary failed without its bound product failure id for {result.case_name}"
        )
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {result.case_name} did not prove {expected_observation}")

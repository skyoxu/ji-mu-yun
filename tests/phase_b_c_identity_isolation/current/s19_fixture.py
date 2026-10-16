from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as element_tree


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
TEST_PROJECT = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"


@dataclass(frozen=True)
class BoundaryResult:
    case_name: str
    outcome: str
    details: str


def invoke_boundary_test(case_name: str) -> BoundaryResult:
    with tempfile.TemporaryDirectory(prefix="s19-trx-", ignore_cleanup_errors=True) as results_directory:
        try:
            completed = subprocess.run(
                [
                    "dotnet",
                    "test",
                    TEST_PROJECT,
                    "--filter",
                    f"FullyQualifiedName={case_name}",
                    "--logger",
                    "trx",
                    "--results-directory",
                    results_directory,
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
            raise RuntimeError(f"S19 harness timeout for {case_name}") from error

        trx_files = list(Path(results_directory).glob("*.trx"))
        if len(trx_files) != 1:
            diagnostics = (completed.stdout + completed.stderr).strip()[-2000:]
            raise RuntimeError(
                f"S19 harness did not produce one fresh TRX for {case_name}: "
                f"exit={completed.returncode}, trx_count={len(trx_files)}, diagnostics={diagnostics!r}"
            )
        try:
            document = element_tree.parse(trx_files[0])
        except element_tree.ParseError as error:
            raise RuntimeError(f"S19 harness produced an unreadable TRX for {case_name}") from error

        matching = [
            result
            for result in document.getroot().iter()
            if result.tag.endswith("UnitTestResult") and result.attrib.get("testName") == case_name
        ]
        if len(matching) != 1:
            raise RuntimeError(f"S19 harness did not discover exactly one result for {case_name}: {len(matching)}")
        result = matching[0]
        outcome = result.attrib.get("outcome")
        if outcome not in {"Passed", "Failed"}:
            raise RuntimeError(f"S19 boundary result was not executable for {case_name}: {outcome!r}")
        if completed.returncode != 0 and outcome != "Failed":
            raise RuntimeError(f"S19 harness failed outside the target boundary for {case_name}")
        return BoundaryResult(case_name, outcome, element_tree.tostring(result, encoding="unicode"))


def assert_behavior(result: BoundaryResult, expected_observation: str, failure_id: str) -> None:
    if result.outcome == "Passed":
        if expected_observation not in result.details:
            raise RuntimeError(f"S19 boundary passed without its product observation: {result.case_name}")
        return
    if failure_id not in result.details:
        raise RuntimeError(f"S19 boundary failed without its bound product failure id: {result.case_name}")
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {result.case_name} did not prove {expected_observation}")

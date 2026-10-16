from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import xml.etree.ElementTree as element_tree


CASE = "PhaseA.Platform.Tests.PhaseB.Repair.S22BoundaryTests.O_D6DA22255508"
FAILURE_ID = "FAILURE-O-D6DA22255508"
TRX_NAMESPACE = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}


@dataclass(frozen=True)
class BoundaryResult:
    outcome: str
    observation: dict[str, str]
    error_message: str


def invoke_s22_boundary(tmp_path: Path) -> BoundaryResult:
    repository_root = Path(__file__).resolve().parents[3]
    results_directory = tmp_path / "s22-trx"
    results_directory.mkdir()
    try:
        completed = subprocess.run(
            [
                "dotnet",
                "test",
                "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj",
                "--filter",
                f"FullyQualifiedName={CASE}",
                "--logger",
                "trx",
                "--results-directory",
                str(results_directory),
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
        raise RuntimeError(f"S22 harness timeout for {CASE}") from error

    trx_files = list(results_directory.glob("*.trx"))
    if len(trx_files) != 1 or completed.returncode not in (0, 1):
        raise RuntimeError(
            f"S22 harness invocation failed: exit={completed.returncode}, trx_count={len(trx_files)}, "
            f"stdout={completed.stdout}, stderr={completed.stderr}"
        )
    return _read_boundary_result(trx_files[0])


def _read_boundary_result(trx_path: Path) -> BoundaryResult:
    try:
        root = element_tree.parse(trx_path).getroot()
    except element_tree.ParseError as error:
        raise RuntimeError(f"S22 harness produced an unreadable TRX for {CASE}") from error

    test_ids = {
        test.attrib["id"]
        for test in root.findall(".//trx:UnitTest", TRX_NAMESPACE)
        if test.attrib.get("name") == CASE
    }
    if len(test_ids) != 1:
        raise RuntimeError(f"S22 TRX did not contain exactly one expected test identity for {CASE}")
    results = [
        result
        for result in root.findall(".//trx:UnitTestResult", TRX_NAMESPACE)
        if result.attrib.get("testId") in test_ids
    ]
    if len(results) != 1:
        raise RuntimeError(f"S22 TRX did not contain exactly one result for {CASE}")

    result = results[0]
    outcome = result.attrib.get("outcome", "")
    if outcome not in {"Passed", "Failed"}:
        raise RuntimeError(f"S22 boundary result was not executable for {CASE}: {outcome!r}")
    stdout = "\n".join(node.text or "" for node in result.findall(".//trx:StdOut", TRX_NAMESPACE))
    observations = [line.removeprefix("S22_OBSERVATION:") for line in stdout.splitlines() if line.startswith("S22_OBSERVATION:")]
    if len(observations) != 1:
        raise RuntimeError(f"S22 boundary did not emit exactly one real observation for {CASE}")
    fields = dict(part.split("=", 1) for part in observations[0].split(";") if "=" in part)
    if set(fields) != {"keyReference", "mechanism", "protectedPayload", "recovered"}:
        raise RuntimeError(f"S22 boundary emitted an incomplete observation for {CASE}")
    return BoundaryResult(
        outcome=outcome,
        observation=fields,
        error_message=result.findtext("trx:Output/trx:ErrorInfo/trx:Message", default="", namespaces=TRX_NAMESPACE),
    )

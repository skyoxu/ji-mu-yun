from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import xml.etree.ElementTree as element_tree


PROJECT_PATH = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"
CASE_PREFIX = "PhaseA.Platform.Tests.PhaseB.Repair.S24BoundaryTests"
TRX_NAMESPACE = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}


@dataclass(frozen=True)
class BoundaryResult:
    outcome: str
    observation: dict[str, str]
    error_message: str


def invoke_s24_boundary(tmp_path: Path, case: str, observation_prefix: str, fields: set[str]) -> BoundaryResult:
    repository_root = Path(__file__).resolve().parents[3]
    case_name = f"{CASE_PREFIX}.{case}"
    results_directory = tmp_path / f"s24-{case.lower()}-trx"
    results_directory.mkdir()
    try:
        completed = subprocess.run(
            [
                "dotnet",
                "test",
                PROJECT_PATH,
                "--filter",
                f"FullyQualifiedName={case_name}",
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
        raise RuntimeError(f"S24 harness timeout for {case_name}") from error

    trx_files = list(results_directory.glob("*.trx"))
    if len(trx_files) != 1 or completed.returncode not in {0, 1}:
        raise RuntimeError(
            f"S24 harness invocation failed for {case_name}: exit={completed.returncode}, trx_count={len(trx_files)}, "
            f"stdout={completed.stdout}, stderr={completed.stderr}"
        )
    return _read_boundary_result(trx_files[0], case_name, observation_prefix, fields)


def _read_boundary_result(trx_path: Path, case_name: str, observation_prefix: str, fields: set[str]) -> BoundaryResult:
    try:
        root = element_tree.parse(trx_path).getroot()
    except element_tree.ParseError as error:
        raise RuntimeError(f"S24 harness produced an unreadable TRX for {case_name}") from error

    test_ids = {
        test.attrib["id"]
        for test in root.findall(".//trx:UnitTest", TRX_NAMESPACE)
        if test.attrib.get("name") == case_name
    }
    if len(test_ids) != 1:
        raise RuntimeError(f"S24 TRX did not contain exactly one expected test identity for {case_name}")
    results = [
        result
        for result in root.findall(".//trx:UnitTestResult", TRX_NAMESPACE)
        if result.attrib.get("testId") in test_ids
    ]
    if len(results) != 1:
        raise RuntimeError(f"S24 TRX did not contain exactly one result for {case_name}")

    result = results[0]
    outcome = result.attrib.get("outcome", "")
    if outcome not in {"Passed", "Failed"}:
        raise RuntimeError(f"S24 boundary result was not executable for {case_name}: {outcome!r}")
    stdout = "\n".join(node.text or "" for node in result.findall(".//trx:StdOut", TRX_NAMESPACE))
    observations = [line.removeprefix(observation_prefix) for line in stdout.splitlines() if line.startswith(observation_prefix)]
    if outcome == "Passed" and len(observations) != 1:
        raise RuntimeError(f"S24 boundary did not emit exactly one real observation for {case_name}")
    observation = _parse_observation(observations[0], fields, case_name) if observations else {}
    return BoundaryResult(
        outcome=outcome,
        observation=observation,
        error_message=result.findtext("trx:Output/trx:ErrorInfo/trx:Message", default="", namespaces=TRX_NAMESPACE),
    )


def _parse_observation(raw: str, fields: set[str], case_name: str) -> dict[str, str]:
    observation = dict(part.split("=", 1) for part in raw.split(";") if "=" in part)
    if set(observation) != fields:
        raise RuntimeError(f"S24 boundary emitted an incomplete observation for {case_name}")
    return observation

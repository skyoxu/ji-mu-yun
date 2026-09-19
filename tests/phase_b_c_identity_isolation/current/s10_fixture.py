import json
import subprocess
import xml.etree.ElementTree as element_tree
from pathlib import Path


CASE_NAME = "PhaseA.Platform.Tests.PhaseB.Repair.S10BoundaryTests.O_3E7CE839D9C3"
OBSERVATION_PREFIX = "S10_OBSERVATION:"
OBSERVATION_FIELDS = {
    "queuedBeforeDisable",
    "reauthorizationDenied",
    "queueDrainedAfterDispatch",
    "writeLeaseGranted",
}


class BoundaryHarnessError(RuntimeError):
    pass


def invoke_s10_boundary(tmp_path: Path) -> dict[str, bool]:
    repository_root = Path(__file__).resolve().parents[3]
    results_directory = tmp_path / "s10-trx"
    results_directory.mkdir()

    try:
        completed = subprocess.run(
            [
                "dotnet",
                "test",
                "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj",
                "--filter",
                f"FullyQualifiedName={CASE_NAME}",
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
        raise BoundaryHarnessError("S10 boundary invocation timed out.") from error

    trx_files = list(results_directory.glob("*.trx"))
    if len(trx_files) != 1:
        raise BoundaryHarnessError("S10 boundary invocation did not produce exactly one fresh TRX file.")

    observation = _read_observation(trx_files[0])
    if completed.returncode != 0:
        raise BoundaryHarnessError("S10 boundary invocation failed outside the product observation.")
    return observation


def _read_observation(trx_path: Path) -> dict[str, bool]:
    try:
        root = element_tree.parse(trx_path).getroot()
    except element_tree.ParseError as error:
        raise BoundaryHarnessError("S10 boundary TRX is not valid XML.") from error

    results = [
        result
        for result in root.iter()
        if _local_name(result.tag) == "UnitTestResult" and result.attrib.get("testName") == CASE_NAME
    ]
    if len(results) != 1:
        raise BoundaryHarnessError("S10 boundary TRX did not identify the exact requested test case.")

    result = results[0]
    if result.attrib.get("outcome") != "Passed":
        raise BoundaryHarnessError("S10 boundary test did not complete successfully.")

    stdout = "\n".join(
        node.text or ""
        for node in result.iter()
        if _local_name(node.tag) == "StdOut"
    )
    observation_lines = [
        line[len(OBSERVATION_PREFIX):]
        for line in stdout.splitlines()
        if line.startswith(OBSERVATION_PREFIX)
    ]
    if len(observation_lines) != 1:
        raise BoundaryHarnessError("S10 boundary TRX did not contain one product observation.")

    try:
        observation = json.loads(observation_lines[0])
    except json.JSONDecodeError as error:
        raise BoundaryHarnessError("S10 boundary observation is not valid JSON.") from error

    if set(observation) != OBSERVATION_FIELDS or not all(
        isinstance(observation[field], bool) for field in OBSERVATION_FIELDS
    ):
        raise BoundaryHarnessError("S10 boundary observation has an invalid shape.")
    return observation


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]

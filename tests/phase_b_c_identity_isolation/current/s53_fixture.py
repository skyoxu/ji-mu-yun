from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as element_tree


TEST_PROJECT = "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj"
TEST_CLASS = "PhaseA.Platform.Tests.PhaseB.Repair.S53BoundaryTests"
TRX_NAMESPACE = {"trx": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}


class BoundaryHarnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class BoundaryResult:
    fully_qualified_name: str
    outcome: str
    observation: dict[str, str]
    error_message: str


def invoke_boundary_test(repository_root: Path, method_name: str) -> BoundaryResult:
    fully_qualified_name = f"{TEST_CLASS}.{method_name}"
    with tempfile.TemporaryDirectory(prefix="s53-trx-", dir=repository_root, ignore_cleanup_errors=True) as results_directory:
        argv = ["dotnet", "test", TEST_PROJECT, "--no-restore", "--no-build", "--filter", f"FullyQualifiedName={fully_qualified_name}", "--logger", "trx", "--results-directory", results_directory]
        try:
            completed = subprocess.run(argv, cwd=repository_root, shell=False, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            raise BoundaryHarnessError(f"S53 harness could not run {fully_qualified_name}") from error
        trx_files = list(Path(results_directory).glob("*.trx"))
        if len(trx_files) != 1:
            raise BoundaryHarnessError(f"S53 harness did not produce one fresh TRX for {fully_qualified_name}: exit={completed.returncode}; diagnostics={(completed.stdout + completed.stderr)[-2000:]!r}")
        result = _read_result(trx_files[0], fully_qualified_name)
        if completed.returncode not in {0, 1} or (result.outcome == "Passed") != (completed.returncode == 0):
            raise BoundaryHarnessError(f"S53 harness failed outside the target boundary for {fully_qualified_name}")
        return result


def assert_behavior(result: BoundaryResult, method_name: str, expected_accepted: bool, expected_reason: str, required_artifact: str | None, failure_id: str) -> None:
    if result.outcome == "Passed":
        if (result.observation.get("accepted") != str(expected_accepted).lower() or result.observation.get("reason") != expected_reason or not result.observation.get("processId", "").isdigit() or (required_artifact is not None and required_artifact not in result.observation.get("artifacts", "").split(","))):
            raise BoundaryHarnessError(f"S53 boundary passed without its required independent observation: {result.fully_qualified_name}")
        return
    if result.outcome != "Failed" or failure_id not in result.error_message:
        raise BoundaryHarnessError(f"S53 boundary failed before its bound behavior assertion: {result.fully_qualified_name}")
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {result.fully_qualified_name} did not prove independent evidence validation")


def _read_result(trx_path: Path, fully_qualified_name: str) -> BoundaryResult:
    try:
        root = element_tree.parse(trx_path).getroot()
    except element_tree.ParseError as error:
        raise BoundaryHarnessError(f"S53 harness produced unreadable TRX for {fully_qualified_name}") from error
    test_ids = {item.attrib["id"] for item in root.findall(".//trx:UnitTest", TRX_NAMESPACE) if item.attrib.get("name") == fully_qualified_name}
    if len(test_ids) != 1:
        raise BoundaryHarnessError(f"S53 TRX did not contain exactly one test identity: {fully_qualified_name}")
    results = [item for item in root.findall(".//trx:UnitTestResult", TRX_NAMESPACE) if item.attrib.get("testId") in test_ids]
    if len(results) != 1:
        raise BoundaryHarnessError(f"S53 TRX did not contain exactly one result: {fully_qualified_name}")
    result = results[0]
    lines = "\n".join(node.text or "" for node in result.findall(".//trx:StdOut", TRX_NAMESPACE)).splitlines()
    prefix = f"S53-OBSERVATION {fully_qualified_name.rsplit('.', 1)[1]};"
    observations = [line.removeprefix(prefix) for line in lines if line.startswith(prefix)]
    if result.attrib.get("outcome") == "Passed" and len(observations) != 1:
        raise BoundaryHarnessError(f"S53 boundary did not emit exactly one observation: {fully_qualified_name}")
    observation = dict(piece.split("=", 1) for piece in observations[0].split(";") if "=" in piece) if observations else {}
    return BoundaryResult(fully_qualified_name, result.attrib.get("outcome", ""), observation, result.findtext("trx:Output/trx:ErrorInfo/trx:Message", default="", namespaces=TRX_NAMESPACE))

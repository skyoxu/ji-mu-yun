import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def invoke_s54_boundary(tmp_path: Path, method: str) -> bool:
    root = Path(__file__).resolve().parents[3]
    results = tmp_path / method
    results.mkdir()
    qualified_name = f"PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.{method}"
    completed = subprocess.run(
        ["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter",
         f"FullyQualifiedName={qualified_name}", "--logger", "trx", "--results-directory", str(results)],
        cwd=root, shell=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    trx_files = list(results.glob("*.trx"))
    if len(trx_files) != 1:
        raise RuntimeError("S54 did not produce exactly one invocation-specific TRX")
    document = ET.parse(trx_files[0]).getroot()
    rows = [item for item in document.iter() if item.tag.endswith("UnitTestResult") and item.attrib.get("testName") == qualified_name]
    if len(rows) != 1:
        raise RuntimeError("S54 exact boundary case is missing or ambiguous")
    outcome = rows[0].attrib.get("outcome")
    if outcome not in {"Passed", "Failed"}:
        raise RuntimeError(f"S54 boundary case has non-admissible outcome: {outcome}")
    if completed.returncode == 0 and outcome != "Passed":
        raise RuntimeError("S54 TRX outcome conflicts with dotnet test exit status")
    if completed.returncode != 0 and outcome != "Failed":
        raise RuntimeError("S54 dotnet test failed before the bound boundary assertion")
    return outcome == "Passed"

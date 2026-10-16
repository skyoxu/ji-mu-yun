import json
import subprocess
import xml.etree.ElementTree as element_tree
from pathlib import Path


PREFIX = "S23_OBSERVATION:"


def invoke_s23_boundary(tmp_path: Path, method: str) -> dict:
    root = Path(__file__).resolve().parents[3]
    case = f"PhaseA.Platform.Tests.PhaseB.Repair.S23BoundaryTests.{method}"
    result_dir = tmp_path / f"s23-{method}"
    result_dir.mkdir()
    completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", f"FullyQualifiedName={case}", "--logger", "trx", "--results-directory", str(result_dir)], cwd=root, shell=False, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    files = list(result_dir.glob("*.trx"))
    if completed.returncode != 0 or len(files) != 1:
        raise RuntimeError(f"S23 boundary invocation failed for {case}")
    document = element_tree.parse(files[0]).getroot()
    results = [x for x in document.iter() if x.tag.endswith("UnitTestResult") and x.attrib.get("testName") == case]
    if len(results) != 1 or results[0].attrib.get("outcome") != "Passed":
        raise RuntimeError(f"S23 boundary result was not executable for {case}")
    lines = [node.text[len(PREFIX):] for node in results[0].iter() if node.tag.endswith("StdOut") and node.text and PREFIX in node.text]
    if len(lines) != 1:
        raise RuntimeError(f"S23 boundary observation missing for {case}")
    return json.loads(lines[0])

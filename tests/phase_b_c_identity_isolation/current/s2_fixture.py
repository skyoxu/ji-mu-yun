import subprocess
import xml.etree.ElementTree as element_tree
from pathlib import Path


CASE = "PhaseA.Platform.Tests.PhaseB.Repair.S2BoundaryTests.O_26DE8E588B36"


def invoke_s2_boundary(tmp_path: Path) -> dict:
    root = Path(__file__).resolve().parents[3]
    result_dir = tmp_path / "s2-trx"
    result_dir.mkdir()
    completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", f"FullyQualifiedName={CASE}", "--logger", "trx", "--results-directory", str(result_dir)], cwd=root, shell=False, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    files = list(result_dir.glob("*.trx"))
    if len(files) != 1:
        raise RuntimeError(f"S2 boundary did not produce one fresh TRX: exit={completed.returncode}")
    document = element_tree.parse(files[0]).getroot()
    result = [x for x in document.iter() if x.tag.endswith("UnitTestResult") and x.attrib.get("testName") == CASE]
    if len(result) != 1:
        raise RuntimeError("S2 boundary did not discover exactly one target result")
    outcome = result[0].attrib.get("outcome")
    details = element_tree.tostring(result[0], encoding="unicode")
    if outcome == "Failed" and "FAILURE-O-26DE8E588B36" in details:
        raise AssertionError("FAILURE-O-26DE8E588B36: isolated file operation did not complete")
    if outcome != "Passed" or completed.returncode != 0:
        raise RuntimeError(f"S2 boundary failed outside the product assertion: outcome={outcome}, exit={completed.returncode}")
    stdout = "\n".join(node.text or "" for node in result[0].iter() if node.tag.endswith("StdOut"))
    lines = [line[len("S2_OBSERVATION:"):].split(",") for line in stdout.splitlines() if line.startswith("S2_OBSERVATION:")]
    if len(lines) != 1 or len(lines[0]) != 3:
        raise RuntimeError("S2 product observation missing")
    return {"exitCode": int(lines[0][0]), "outputExists": lines[0][1] == "true", "markerPresent": lines[0][2] == "true"}

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def invoke_s16_boundary(tmp_path: Path, method: str, failure_id: str) -> bool:
    root = Path(__file__).resolve().parents[3]; results = tmp_path / method; results.mkdir()
    name = f"PhaseA.Platform.Tests.PhaseB.Repair.S16BoundaryTests.{method}"
    p = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--no-build", "--filter", f"FullyQualifiedName={name}", "--logger", "trx", "--results-directory", str(results)], cwd=root, shell=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    files = list(results.glob("*.trx"));
    if len(files) != 1: raise RuntimeError("S16 invocation did not produce one TRX")
    rows = [x for x in ET.parse(files[0]).getroot().iter() if x.tag.endswith("UnitTestResult") and x.attrib.get("testName") == name]
    if len(rows) != 1: raise RuntimeError("S16 exact case missing")
    outcome = rows[0].attrib.get("outcome")
    if p.returncode != 0 or outcome != "Passed":
        raise RuntimeError(f"{failure_id}: S16 boundary failed")
    return True

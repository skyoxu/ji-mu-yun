import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def invoke_s5_boundary(tmp_path: Path, method: str, failure_id: str) -> bool:
    root = Path(__file__).resolve().parents[3]
    results = tmp_path / method
    results.mkdir()
    common = dict(cwd=root, shell=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    names = {
        "O_13B95D1C5C8A", "O_15899A85BDBA", "O_1D8B1ED237E7", "O_2212486D125E", "O_2247FFA39B29", "O_26B033221921", "O_26F98B8D61E9", "O_2CB0253357BD", "O_33DEBF5E8F57", "O_44D5DCF1D18E", "O_4E1B05260B36", "O_505E0CD0F110", "O_50B0785BC648", "O_60B07564A56E", "O_6D7C468AAEBB", "O_7CCF9E78CC4A", "O_7DB7792164EF", "O_81EB0ACC0879", "O_83872380AF3E", "O_86EB1445D44C", "O_AE28BF0DE9B1", "O_B3B7843B451F", "O_C2ECA44555A8", "O_CEC1F1CB3655", "O_CF3185DF72BF", "O_D12738343B10", "O_DE1F1C0A6FF0"
    }
    if method not in names:
        raise ValueError(method)
    qualified_name = f"PhaseA.Platform.Tests.PhaseB.Repair.S5BoundaryTests.{method}"
    completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--no-build", "--filter", f"FullyQualifiedName={qualified_name}", "--logger", "trx", "--results-directory", str(results)], **common)
    trx_files = list(results.glob("*.trx"))
    if len(trx_files) != 1:
        raise RuntimeError("S5 did not produce exactly one invocation-specific TRX")
    document = ET.parse(trx_files[0]).getroot()
    rows = [x for x in document.iter() if x.tag.endswith("UnitTestResult") and x.attrib.get("testName") == qualified_name]
    if len(rows) != 1:
        raise RuntimeError("S5 exact boundary case is missing or ambiguous")
    outcome = rows[0].attrib.get("outcome")
    if outcome not in {"Passed", "Failed"}:
        raise RuntimeError(f"S5 boundary case has non-admissible outcome: {outcome}")
    if completed.returncode == 0 and outcome != "Passed":
        raise RuntimeError("S5 TRX outcome conflicts with dotnet test exit status")
    if completed.returncode != 0 and outcome != "Failed":
        raise RuntimeError("S5 dotnet test failed before the bound boundary assertion")
    if outcome == "Failed":
        messages = "\n".join(n.text or "" for n in rows[0].iter() if n.tag.endswith("Message"))
        if failure_id not in messages:
            raise RuntimeError("S5 boundary failed outside its bound behavioral assertion")
    return outcome == "Passed"

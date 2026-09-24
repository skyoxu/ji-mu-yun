import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def invoke_s50_boundary(tmp_path: Path, method: str, failure_id: str) -> bool:
    root = Path(__file__).resolve().parents[3]
    results = tmp_path / method
    results.mkdir()
    common = {
        "cwd": root,
        "shell": False,
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": 180,
    }
    if method == "O_0540475EB849":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_0540475EB849"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_0540475EB849", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_17ED20E8D615":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_17ED20E8D615"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_17ED20E8D615", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_2EDAD0C079A7":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_2EDAD0C079A7"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_2EDAD0C079A7", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_350460F95643":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_350460F95643"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_350460F95643", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_38DA71E9D444":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_38DA71E9D444"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_38DA71E9D444", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_571C78093983":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_571C78093983"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_571C78093983", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_5D176438FFA6":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_5D176438FFA6"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_5D176438FFA6", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_7958B030A69B":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_7958B030A69B"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_7958B030A69B", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_7E825F215702":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_7E825F215702"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_7E825F215702", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_B085F1A35441":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_B085F1A35441"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_B085F1A35441", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_CC964B3582F6":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_CC964B3582F6"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_CC964B3582F6", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_D2840720344F":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_D2840720344F"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_D2840720344F", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_D664E1FFDFB3":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_D664E1FFDFB3"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_D664E1FFDFB3", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_D9BA6D66CD0D":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_D9BA6D66CD0D"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_D9BA6D66CD0D", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_DF1BBA997C44":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_DF1BBA997C44"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_DF1BBA997C44", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_E20FAEA5ABC8":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_E20FAEA5ABC8"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_E20FAEA5ABC8", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_E79036BF6FA3":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_E79036BF6FA3"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_E79036BF6FA3", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_EB1DEE188517":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_EB1DEE188517"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_EB1DEE188517", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_FA0C21A344E7":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_FA0C21A344E7"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S50BoundaryTests.O_FA0C21A344E7", "--logger", "trx", "--results-directory", str(results)], **common)
    else:
        raise ValueError(f"unknown S50 boundary method: {method}")

    trx_files = list(results.glob("*.trx"))
    if len(trx_files) != 1:
        raise RuntimeError("S50 did not produce exactly one invocation-specific TRX")
    document = ET.parse(trx_files[0]).getroot()
    rows = [item for item in document.iter() if item.tag.endswith("UnitTestResult") and item.attrib.get("testName") == qualified_name]
    if len(rows) != 1:
        raise RuntimeError("S50 exact boundary case is missing or ambiguous")
    outcome = rows[0].attrib.get("outcome")
    if outcome not in {"Passed", "Failed"}:
        raise RuntimeError(f"S50 boundary case has non-admissible outcome: {outcome}")
    if completed.returncode == 0 and outcome != "Passed":
        raise RuntimeError("S50 TRX outcome conflicts with dotnet test exit status")
    if completed.returncode != 0 and outcome != "Failed":
        raise RuntimeError("S50 dotnet test failed before the bound boundary assertion")
    if outcome == "Failed":
        messages = "\n".join(node.text or "" for node in rows[0].iter() if node.tag.endswith("Message"))
        if failure_id not in messages:
            raise RuntimeError("S50 boundary failed outside its bound behavioral assertion")
    return outcome == "Passed"

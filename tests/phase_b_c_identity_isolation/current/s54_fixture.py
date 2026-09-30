import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def invoke_s54_boundary(tmp_path: Path, method: str, failure_id: str) -> bool:
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
    if method == "O_12F85445CCD2":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_12F85445CCD2"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_12F85445CCD2", "--logger", "trx", "--results-directory", str(results)], cwd=root, shell=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    elif method == "O_1D8CB3E8262F":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_1D8CB3E8262F"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_1D8CB3E8262F", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_270713F3B6BC":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_270713F3B6BC"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_270713F3B6BC", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_358D470F6E85":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_358D470F6E85"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_358D470F6E85", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_3FA9A1207C61":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_3FA9A1207C61"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_3FA9A1207C61", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_4178BD27EC32":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_4178BD27EC32"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_4178BD27EC32", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_4834E9163638":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_4834E9163638"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_4834E9163638", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_4E130E94995A":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_4E130E94995A"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_4E130E94995A", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_5CBD9C2F5F8E":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_5CBD9C2F5F8E"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_5CBD9C2F5F8E", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_B21A2E1BF669":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_B21A2E1BF669"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_B21A2E1BF669", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_C5E83411E41D":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_C5E83411E41D"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_C5E83411E41D", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_D6F9AC452A48":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_D6F9AC452A48"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_D6F9AC452A48", "--logger", "trx", "--results-directory", str(results)], **common)
    elif method == "O_824_ACCOUNT_ROOT_ENUMERATION":
        qualified_name = "PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_824_ACCOUNT_ROOT_ENUMERATION"
        completed = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--filter", "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S54BoundaryTests.O_824_ACCOUNT_ROOT_ENUMERATION", "--logger", "trx", "--results-directory", str(results)], **common)
    else:
        raise ValueError(f"unknown S54 boundary method: {method}")

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
    if outcome == "Failed":
        messages = [item.text or "" for item in rows[0].iter() if item.tag.endswith("Message")]
        if not any(failure_id in message for message in messages):
            raise RuntimeError(
                f"S54 boundary case failed outside its product assertion: {qualified_name}; "
                f"TRX messages={messages!r}"
            )
    return outcome == "Passed"

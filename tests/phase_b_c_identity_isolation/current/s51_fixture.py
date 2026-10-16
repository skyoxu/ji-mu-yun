"""CER adapter for S51's real fourteen-family boundary test."""
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def validate_trx(path: Path, name: str, failure_id: str, returncode: int) -> None:
    document = ET.parse(path)
    ns = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
    rows = document.findall(".//t:UnitTestResult", ns)
    if len(rows) != 1 or rows[0].get("testName") != name:
        raise RuntimeError("S51 missing, duplicate, or wrong-target test result")
    counters = document.find(".//t:Counters", ns)
    if counters is None or counters.get("total") != "1" or counters.get("executed") != "1":
        raise RuntimeError("S51 test was not executed exactly once")
    row = rows[0]
    if row.get("outcome") == "Passed" and returncode == 0:
        return
    message = row.findtext(".//t:Message", default="", namespaces=ns)
    stack = row.findtext(".//t:StackTrace", default="", namespaces=ns)
    if (row.get("outcome") == "Failed" and returncode == 1
            and (message.startswith(failure_id + ":") or message.startswith("Xunit.Sdk.XunitException: " + failure_id + ":"))
            and name in stack):
        print("FAILURE_ID:" + failure_id)
        raise AssertionError(message)
    raise RuntimeError("S51 harness failure; not a bound product assertion: " + message[:1000])


def invoke_s51_boundary(tmp_path: Path, method: str, failure_id: str) -> bool:
    if method != "O_E9499880E6EF":
        raise RuntimeError("S51 unknown exact boundary selector")
    root = Path(__file__).resolve().parents[3]
    results = Path(tempfile.mkdtemp(prefix="s51-trx-", dir=tmp_path))
    completed = subprocess.run(
        ["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--no-restore", "--filter",
         "FullyQualifiedName=PhaseA.Platform.Tests.PhaseB.Repair.S51BoundaryTests.O_E9499880E6EF",
         "--logger", "trx", "--results-directory", str(results)],
        cwd=root, shell=False, check=False, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=240)
    (results / "dotnet.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (results / "dotnet.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    files = list(results.glob("*.trx"))
    if len(files) != 1:
        raise RuntimeError("S51 invocation did not produce one fresh TRX; see " + str(results))
    validate_trx(files[0], "PhaseA.Platform.Tests.PhaseB.Repair.S51BoundaryTests.O_E9499880E6EF", failure_id, completed.returncode)
    return True

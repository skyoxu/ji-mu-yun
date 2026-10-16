import subprocess
import xml.etree.ElementTree as element_tree
from pathlib import Path


def invoke_s21_boundary(tmp_path: Path, case: str, failure_id: str) -> dict:
    root = Path(__file__).resolve().parents[3]
    result_dir = tmp_path / "s21-trx"
    result_dir.mkdir()
    completed = subprocess.run(
        [
            "dotnet",
            "test",
            "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj",
            "--filter",
            f"FullyQualifiedName={case}",
            "--logger",
            "trx",
            "--results-directory",
            str(result_dir),
        ],
        cwd=root,
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    files = list(result_dir.glob("*.trx"))
    if completed.returncode not in {0, 1} or len(files) != 1:
        raise RuntimeError(
            f"S21 harness invocation failed: exit={completed.returncode}, trx_count={len(files)}, "
            f"stdout={completed.stdout}, stderr={completed.stderr}"
        )
    document = element_tree.parse(files[0]).getroot()
    results = [
        item
        for item in document.iter()
        if item.tag.endswith("UnitTestResult") and item.attrib.get("testName") == case
    ]
    if len(results) != 1 or results[0].attrib.get("outcome") not in {"Passed", "Failed"}:
        raise RuntimeError("S21 boundary case was not discovered and executed exactly once.")
    result = results[0]
    error_text = "\n".join(node.text or "" for node in result.iter() if node.tag.endswith(("Message", "StackTrace")))
    if result.attrib.get("outcome") == "Failed" and failure_id not in error_text:
        raise RuntimeError("S21 boundary failed before its bound product assertion.")
    stdout = "\n".join(node.text or "" for node in result.iter() if node.tag.endswith("StdOut"))
    observation = f"S21_OBSERVATION:{case.rsplit('.', 1)[-1]}:"
    lines = [line for line in stdout.splitlines() if line.startswith(observation)]
    if len(lines) != 1 or lines[0][len(observation) :] not in {"true", "false"}:
        raise RuntimeError("S21 boundary did not emit its real product observation.")
    return {
        "satisfied": lines[0][len(observation) :] == "true",
        "outcome": result.attrib["outcome"],
    }

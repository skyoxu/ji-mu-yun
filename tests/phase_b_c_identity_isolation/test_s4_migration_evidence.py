import subprocess
from pathlib import Path


def test_s4_contract_tests_are_present():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--no-restore", "--list-tests"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PhaseB.MigrationEvidenceTests" in result.stdout

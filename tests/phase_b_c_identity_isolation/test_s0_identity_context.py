import subprocess
from pathlib import Path


def test_s0_identity_behavior_passes():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(["dotnet", "test", "PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj", "--no-restore", "--filter", "FullyQualifiedName~PhaseB.IdentityContextTests|FullyQualifiedName~PhaseB.WorkspaceRecoveryBehaviorTests", "--nologo"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "通过" in result.stdout and "失败:     0" in result.stdout

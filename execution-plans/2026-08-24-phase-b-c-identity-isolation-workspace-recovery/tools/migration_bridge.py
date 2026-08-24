from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


TESTS = {
    "S0": ("test_s0_identity_context.py", "PhaseB.IdentityContextTests"),
    "S1": ("test_s1_runner_isolation.py", "PhaseB.RunnerIsolationTests"),
    "S2": ("test_s2_snapshot.py", "PhaseB.SnapshotTests"),
    "S3": ("test_s3_restore_recovery.py", "PhaseB.RestoreRecoveryTests"),
    "S4": ("test_s4_migration_evidence.py", "PhaseB.MigrationEvidenceTests"),
}


def materialize(root: Path, plan: Path, slice_id: str) -> Path:
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = next(item for item in contract["slices"] if item["slice_id"] == slice_id)
    filename, marker = TESTS[slice_id]
    planned = selected.get("planned_new_files")
    expected = f"tests/phase_b_c_identity_isolation/{filename}"
    if planned != [expected]:
        raise ValueError("planned test does not match the bridge")
    target = root / expected
    template = (
        "import subprocess\n"
        "from pathlib import Path\n\n\n"
        f"def test_{slice_id.lower()}_contract_tests_are_present():\n"
        "    root = Path(__file__).resolve().parents[2]\n"
        "    result = subprocess.run([\"dotnet\", \"test\", \"PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj\", \"--no-restore\", \"--list-tests\"], cwd=root, capture_output=True, text=True, encoding=\"utf-8\", errors=\"replace\")\n"
        "    assert result.returncode == 0, result.stdout + result.stderr\n"
        f"    assert \"{marker}\" in result.stdout\n"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_text(encoding="utf-8") != template:
        raise ValueError("existing bridge test differs from immutable template")
    if not target.exists():
        target.write_text(template, encoding="utf-8", newline="\n")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--snapshot-path", action="append", required=True)
    parser.add_argument("snapshot_extras", nargs="*")
    parser.add_argument("--materialize-only", action="store_true")
    args = parser.parse_args()
    path = materialize(args.repository_root.resolve(), args.plan_dir.resolve(), args.slice_id)
    print(json.dumps({"test_path": str(path), "next_action": "prepare-skill-input", "authorizes": []}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

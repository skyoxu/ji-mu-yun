"""Exercise the VDD source-freeze producer without mutating the plan artifact."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        output = Path(raw) / "source-freeze-manifest.v1.json"
        result = subprocess.run([
            sys.executable,
            str(ROOT / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py"),
            "--repository-root", str(ROOT),
            "--spec", str(ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md"),
            "--target-root", "execution-plans/2026-08-13-vdd-conformance-exact-cover",
            "--run-id", "test-source-freeze",
            "--out", str(output),
        ], cwd=ROOT, check=False)
        return 0 if result.returncode == 0 and output.is_file() else 2


if __name__ == "__main__":
    raise SystemExit(main())

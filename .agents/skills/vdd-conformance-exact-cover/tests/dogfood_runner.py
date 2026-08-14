from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"


def main() -> int:
    pointer = ROOT / "_bmad-output/specs/canonical-spec-package-selections/current/SPEC-vdd-conformance-exact-cover.json"
    mapping = PLAN / "repair/round-5/requirements-acceptance-slice-command.v1.json"
    if not all(path.is_file() for path in (pointer, mapping)):
        return 2
    for slice_id in ("S0", "S1", "S2", "S3a", "S3b", "S3c", "S3d", "S4"):
        evidence = list((ROOT / "logs/tdd-adapter/vdd-conformance-exact-cover" / slice_id).glob("*/slice-ready-result.json"))
        if not evidence:
            return 2
    with tempfile.TemporaryDirectory() as raw:
        manifest = Path(raw) / "source-freeze-manifest.v1.json"
        freeze = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py"),
            "--repository-root", str(ROOT), "--spec", str(ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md"),
            "--target-root", "execution-plans/2026-08-13-vdd-conformance-exact-cover", "--run-id", "dogfood", "--out", str(manifest),
        ], cwd=ROOT, check=False)
        if freeze.returncode:
            return 2
        exact = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/validate_conformance.py"),
            "--repository-root", str(ROOT), "--manifest", str(manifest), "--mapping", str(mapping),
        ], cwd=ROOT, check=False)
        return 0 if exact.returncode == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

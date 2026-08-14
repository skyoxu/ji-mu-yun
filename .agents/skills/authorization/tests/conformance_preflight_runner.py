"""Exercise receipt preflight using a newly frozen manifest and exact-cover receipt."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
MAPPING = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover/repair/round-5/requirements-acceptance-slice-command.v1.json"
VALIDATOR = ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/conformance.py"


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        folder = Path(raw)
        manifest = folder / "manifest.json"
        receipt = folder / "receipt.json"
        freeze = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py"),
            "--repository-root", str(ROOT), "--spec", str(ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md"),
            "--target-root", "execution-plans/2026-08-13-vdd-conformance-exact-cover", "--run-id", "authorization-preflight", "--out", str(manifest),
        ], cwd=ROOT, check=False, capture_output=True, text=True)
        if freeze.returncode:
            return 2
        exact = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/validate_conformance.py"),
            "--repository-root", str(ROOT), "--manifest", str(manifest), "--mapping", str(MAPPING),
        ], cwd=ROOT, check=False, capture_output=True, text=True)
        if exact.returncode == 0 or '"status":"requirement_semantic_review_required"' not in exact.stdout:
            return 2
        receipt.write_text(exact.stdout, encoding="utf-8", newline="\n")
        check = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/authorization/scripts/conformance_preflight.py"),
            "--receipt", str(receipt), "--manifest", str(manifest), "--mapping", str(MAPPING), "--validator", str(VALIDATOR),
        ], cwd=ROOT, check=False)
        return 0 if check.returncode != 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Verify exact-cover validation does not mutate its requirements target."""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
TARGET = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover/repair/round-5/requirements-acceptance-slice-command.v1.json"
VALIDATOR = ROOT / ".agents/skills/vdd-conformance-exact-cover/tests/validators/exact_cover.py"


def main() -> int:
    before = hashlib.sha256(TARGET.read_bytes()).digest()
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, check=False)
    after = hashlib.sha256(TARGET.read_bytes()).digest()
    return 0 if result.returncode == 0 and before == after else 2


if __name__ == "__main__":
    raise SystemExit(main())

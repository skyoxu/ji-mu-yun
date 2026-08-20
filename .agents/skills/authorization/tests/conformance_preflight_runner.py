"""Exercise receipt preflight using a newly frozen manifest and exact-cover receipt."""
from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
VALIDATOR = ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/conformance.py"
LINEAGE_POINTER = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover/governance/repair-lineage/repair-lineage-current.v1.json"


def main() -> int:
    if not LINEAGE_POINTER.is_file():
        return 2
    pointer = json.loads(LINEAGE_POINTER.read_text(encoding="utf-8"))
    manifest = ROOT / pointer.get("source_freeze", {}).get("path", "")
    mapping = ROOT / pointer.get("reviewed_mapping", {}).get("path", "")
    receipt = ROOT / pointer.get("conformance_result", {}).get("path", "")
    if not all(path.is_file() for path in (manifest, mapping, receipt)):
        return 2
    check = subprocess.run([
        sys.executable, str(ROOT / ".agents/skills/authorization/scripts/conformance_preflight.py"),
        "--receipt", str(receipt), "--manifest", str(manifest), "--mapping", str(mapping), "--validator", str(VALIDATOR),
    ], cwd=ROOT, check=False)
    return 0 if check.returncode == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

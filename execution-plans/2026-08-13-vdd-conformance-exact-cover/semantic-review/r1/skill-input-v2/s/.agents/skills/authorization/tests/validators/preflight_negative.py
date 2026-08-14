from __future__ import annotations

import subprocess
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[5]


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        receipt = Path(raw) / "receipt.json"
        receipt.write_text('{"status":"conformant","authorizes":[]}\n', encoding="utf-8", newline="\n")
        result = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/authorization/scripts/conformance_preflight.py"),
            "--receipt", str(receipt),
            "--manifest", str(ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover/source-freeze-manifest.v1.json"),
            "--mapping", str(ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover/repair/round-5/requirements-acceptance-slice-command.v1.json"),
            "--validator", str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/conformance.py"),
        ], cwd=ROOT, check=False)
        return 1 if result.returncode else 0


if __name__ == "__main__":
    raise SystemExit(main())

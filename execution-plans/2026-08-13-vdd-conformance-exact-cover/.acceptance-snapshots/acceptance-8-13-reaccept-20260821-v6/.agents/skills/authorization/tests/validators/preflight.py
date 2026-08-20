from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def main() -> int:
    result = subprocess.run([sys.executable, str(ROOT / ".agents/skills/authorization/tests/conformance_preflight_runner.py")], cwd=ROOT, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

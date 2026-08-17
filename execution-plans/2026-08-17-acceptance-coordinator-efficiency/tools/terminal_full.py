"""Run the existing owning regression suites for this compact control-plane plan."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SUITES = (
    ".agents/skills/quick-dev-tdd-adapter/tools/tests",
    ".agents/skills/run-refactor-implementation-acceptance/tests",
)


def main() -> int:
    for suite in SUITES:
        result = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", suite, "-p", "test_*.py"],
            cwd=ROOT,
            check=False,
        )
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The SUT execution owner is intentionally separate from the independent judge."""
from __future__ import annotations

import subprocess
from typing import Sequence


def execute(argv: Sequence[str], *, cwd: str, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(argv), cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)

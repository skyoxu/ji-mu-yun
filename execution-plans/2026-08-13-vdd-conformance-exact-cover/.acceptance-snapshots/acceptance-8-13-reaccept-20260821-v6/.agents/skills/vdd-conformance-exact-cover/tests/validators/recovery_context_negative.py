from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import append_checkpoint  # noqa: E402

def main() -> int:
    checkpoint = {"branch": "fork", "state": "active", "authorized": True}
    with tempfile.TemporaryDirectory() as raw:
        try:
            append_checkpoint(Path(raw) / "checkpoint.json", checkpoint)
        except ValueError:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

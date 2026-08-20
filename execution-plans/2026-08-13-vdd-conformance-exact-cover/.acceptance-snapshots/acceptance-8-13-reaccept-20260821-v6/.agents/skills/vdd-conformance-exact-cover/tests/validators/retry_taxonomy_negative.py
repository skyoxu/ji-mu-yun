from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import resolve_runtime_policy  # noqa: E402


def main() -> int:
    registry = json.loads((ROOT / ".agents/skills/vdd-conformance-exact-cover/references/runtime-policy-registry.v1.json").read_text(encoding="utf-8"))
    registry["policies"][0]["retry_maximums"]["timeout"] = 0
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "registry.json"
        path.write_text(json.dumps(registry), encoding="utf-8", newline="\n")
        try:
            resolve_runtime_policy(path)
        except ValueError:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

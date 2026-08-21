from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-execution-plan/scripts"))
from source_freeze import build_manifest, validate_manifest  # noqa: E402


def main() -> int:
    manifest = build_manifest(
        ROOT,
        ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md",
        "execution-plans/2026-08-13-vdd-conformance-exact-cover",
        "source-freeze-negative",
    )
    mutated = copy.deepcopy(manifest)
    mutated["sources"][0]["role"] = "provenance"
    try:
        validate_manifest(ROOT, mutated)
    except ValueError:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

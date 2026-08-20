from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[5]


def main() -> int:
    module_path = ROOT / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py"
    spec = importlib.util.spec_from_file_location("composition_source_freeze", module_path)
    if spec is None or spec.loader is None:
        return 0
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = module.build_manifest(ROOT, ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md", "execution-plans/2026-08-13-vdd-conformance-exact-cover", "composition-negative")
    mutated = copy.deepcopy(manifest)
    mutated["sources"][0]["role"] = "provenance"
    try:
        module.validate_manifest(ROOT, mutated)
    except ValueError:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Prove VDD source-freeze and exact-cover consume one current manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[5]
PLAN = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    mapping_path = PLAN / "repair/round-5/requirements-acceptance-slice-command.v1.json"
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    if not mapping.get("requirements"):
        return 2
    with tempfile.TemporaryDirectory() as raw:
        manifest_path = Path(raw) / "source-freeze-manifest.v1.json"
        freeze = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py"),
            "--repository-root", str(ROOT), "--spec", str(ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md"),
            "--target-root", "execution-plans/2026-08-13-vdd-conformance-exact-cover", "--run-id", "composition-validator", "--out", str(manifest_path),
        ], cwd=ROOT, check=False, capture_output=True, text=True)
        if freeze.returncode != 0:
            return 2
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        sources = manifest.get("sources")
        if manifest.get("authorizes") != [] or not isinstance(sources, list) or not sources:
            return 2
        for source in sources:
            path = ROOT / source.get("path", "")
            if not path.is_file() or source.get("sha256") != digest(path):
                return 2
        return 0 if sources[0].get("role") == "canonical" else 2


if __name__ == "__main__":
    raise SystemExit(main())

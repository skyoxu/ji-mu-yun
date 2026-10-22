"""Regression fixture for tampered canonical package selection state."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from canonical_package import build_contract, validate_selection


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        package = root / "_bmad-output/specs/example"
        package.mkdir(parents=True)
        (package / "SPEC.md").write_text(
            "---\n"
            "id: SPEC-example\n"
            "package_schema: canonical-spec-package.v1\n"
            "companions: []\n"
            "sources: []\n"
            "---\n\n# Example\n",
            encoding="utf-8",
        )
        spec = package / "SPEC.md"
        descriptor, selection, selection_hash = build_contract(root, spec)
        registry = root / "_bmad-output/specs/canonical-spec-package-selections"
        pointer = registry / "current/SPEC-example.json"
        record = registry / f"{selection_hash.replace(':', '-')}.json"
        pointer.parent.mkdir(parents=True)
        record.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(json.dumps({"package_id": descriptor["id"], "schema": "canonical-spec-package-selection-current.v1", "selection_hash": selection_hash}), encoding="utf-8")
        record.write_text(json.dumps(selection), encoding="utf-8")
        pointer.write_text(pointer.read_text(encoding="utf-8").replace(selection_hash, "sha256:" + "0" * 64), encoding="utf-8")
        try:
            validate_selection(root, spec, pointer)
        except ValueError:
            return 1
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

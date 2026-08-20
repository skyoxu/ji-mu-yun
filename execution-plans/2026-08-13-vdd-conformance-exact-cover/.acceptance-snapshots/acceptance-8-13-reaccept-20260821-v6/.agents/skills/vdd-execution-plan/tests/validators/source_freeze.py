from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / ".agents/skills/bmad-spec/scripts"))
from canonical_package import build_contract  # noqa: E402
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-execution-plan/scripts"))
from source_freeze import build_manifest, validate_manifest  # noqa: E402


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    spec = ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md"
    descriptor, selection, selection_hash = build_contract(ROOT, spec)
    pointer = json.loads((ROOT / "_bmad-output/specs/canonical-spec-package-selections/current/SPEC-vdd-conformance-exact-cover.json").read_text(encoding="utf-8"))
    if pointer.get("selection_hash") != selection_hash:
        return 2
    record = json.loads((ROOT / "_bmad-output/specs/canonical-spec-package-selections" / (selection_hash.replace(":", "-") + ".json")).read_text(encoding="utf-8"))
    if record != selection:
        return 2
    manifest = build_manifest(
        ROOT,
        spec,
        "execution-plans/2026-08-13-vdd-conformance-exact-cover",
        "source-freeze-validator",
    )
    expected = [{"path": "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md", "role": "canonical"}, *selection["role_graph"][1:]]
    actual = [{"path": item["path"], "role": item["role"]} for item in manifest.get("sources", [])]
    if actual[:len(expected)] != expected or manifest.get("selection_hash") != selection_hash or manifest.get("authorizes") != []:
        return 2
    if not {"repository_rules", "knowledge_bindings", "unresolved_inputs"}.issubset(manifest):
        return 2
    if not any(item["role"] == "repository_authority" and item.get("relationship") == "applicable_repository_rule" for item in manifest["sources"]):
        return 2
    if any(set(item) != {"path", "role", "sha256", "relationship"} for item in manifest["sources"]):
        return 2
    for item in manifest["sources"]:
        path = ROOT / item["path"]
        if not path.is_file() or item.get("sha256") != digest(path):
            return 2
    try:
        validate_manifest(ROOT, manifest)
    except ValueError:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

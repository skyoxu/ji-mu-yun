from __future__ import annotations

import json
from pathlib import Path
import sys
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import exact_cover  # noqa: E402


def main() -> int:
    path = ROOT / "execution-plans/2026-08-13-vdd-conformance-exact-cover/repair/round-5/requirements-acceptance-slice-command.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    requirements = data.get("requirements", [])
    acceptance = data.get("acceptance_ids", [])
    reverse = data.get("reverse_mapping", {})
    if data.get("authorizes") != [] or not requirements or len({x.get("id") for x in requirements}) != len(requirements):
        return 2
    ids = {x.get("id") for x in requirements}
    if not all(isinstance(x, str) and x.startswith("VCEC-A") for x in acceptance):
        return 2
    if set(reverse) != set(acceptance):
        return 2
    for row in requirements:
        if not isinstance(row.get("id"), str) or not row.get("acceptance_ids") or not row.get("slice") or not row.get("command"):
            return 2
        if any(item not in acceptance for item in row["acceptance_ids"]):
            return 2
        if any(row["id"] not in reverse.get(item, []) for item in row["acceptance_ids"]):
            return 2
    if any(item not in ids for values in reverse.values() for item in values):
        return 2
    result = exact_cover(requirements, acceptance, reverse)
    if result["status"] != "conformant" or result["authorizes"] != []:
        return 2
    with tempfile.TemporaryDirectory() as raw:
        manifest = Path(raw) / "source-freeze-manifest.v1.json"
        freeze = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-execution-plan/scripts/source_freeze.py"),
            "--repository-root", str(ROOT),
            "--spec", str(ROOT / "_bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md"),
            "--target-root", "execution-plans/2026-08-13-vdd-conformance-exact-cover",
            "--run-id", "exact-cover-validator", "--out", str(manifest),
        ], cwd=ROOT, check=False, capture_output=True, text=True)
        if freeze.returncode != 0:
            return 2
        checked = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/validate_conformance.py"),
            "--repository-root", str(ROOT), "--manifest", str(manifest), "--mapping", str(path),
        ], cwd=ROOT, check=False, capture_output=True, text=True)
        if checked.returncode != 0 or '"status":"conformant"' not in checked.stdout:
            return 2
        mutated = json.loads(path.read_text(encoding="utf-8"))
        mutated["acceptance_ids"] = mutated["acceptance_ids"][:-1]
        mutated["reverse_mapping"].pop("VCEC-A43")
        reduced = Path(raw) / "reduced-mapping.json"
        reduced.write_text(json.dumps(mutated), encoding="utf-8", newline="\n")
        rejected = subprocess.run([
            sys.executable, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/validate_conformance.py"),
            "--repository-root", str(ROOT), "--manifest", str(manifest), "--mapping", str(reduced),
        ], cwd=ROOT, check=False, capture_output=True, text=True)
        return 0 if rejected.returncode != 0 and "frozen_acceptance_universe_mismatch" in rejected.stdout else 2


if __name__ == "__main__":
    raise SystemExit(main())

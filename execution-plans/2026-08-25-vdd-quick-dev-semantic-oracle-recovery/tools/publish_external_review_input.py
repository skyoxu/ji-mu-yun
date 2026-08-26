"""Publish current conformance and external semantic-review input artifacts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery"
GOV = PLAN / "governance"
sys.path.insert(0, str(ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts"))
from conformance import semantic_handoff_hash  # noqa: E402


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path: Path) -> dict[str, str]:
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(), "sha256": sha(path)}


def write_new(path: Path, value: object) -> None:
    encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise FileExistsError(f"refusing to replace existing artifact: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encoded)


def main() -> None:
    mapping = GOV / "requirements-acceptance-mapping.v1.current-20260826.json"
    manifest = GOV / "vdd-source-freeze-manifest.v1.current-bound-20260826.json"
    conformance = GOV / "vdd-conformance-result.v1.current-20260826-final-r3.json"
    review_input = GOV / "external-semantic-review-input.v1.current-20260826-final-r3.json"
    validator = ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/validate_conformance.py"
    result = subprocess.run(
        ["python", str(validator), "--repository-root", str(ROOT), "--manifest", str(manifest), "--mapping", str(mapping)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if not result.stdout.strip():
        raise RuntimeError(result.stderr)
    conformance_value = json.loads(result.stdout)
    write_new(conformance, conformance_value)
    current_receipt = PLAN / "skill-input/repair-round-4/receipt.v1.json"
    handoff = conformance_value.get("semantic_handoff") or {}
    package = {
        "schema_version": "vdd-external-semantic-review-input.v1",
        "plan_id": "vdd-quick-dev-semantic-oracle-recovery",
        "profile": handoff.get("profile", "bootstrap-upstream-plan"),
        "selection_hash": json.loads(manifest.read_text(encoding="utf-8"))["selection_hash"],
        "candidate": {
            "head_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
            "implementation_contract": ref(PLAN / "implementation-contract.v1.json"),
            "command_registry": ref(PLAN / "command-registry.v1.json"),
        },
        "source_freeze": ref(manifest),
        "requirements_mapping": ref(mapping),
        "conformance_result": ref(conformance),
        "skill_input_receipt": ref(current_receipt),
        "required_review_bindings": {
            "semantic_handoff_hash": semantic_handoff_hash(handoff),
            "source_manifest_hash": handoff.get("frozen_authority", {}).get("source_manifest_hash"),
            "requirements_manifest_hash": ref(mapping)["sha256"],
            "ambiguity_ids": handoff.get("affected_obligation_ids", []),
            "affected_requirement_ids": handoff.get("affected_requirement_ids", []),
        },
        "review_scope": "Classify every affected source obligation against the preserved contract; do not authorize implementation.",
        "required_output": "vdd-review-run.v1",
        "authorizes": [],
    }
    write_new(review_input, package)
    print(json.dumps({"conformance": ref(conformance), "review_input": ref(review_input), "status": conformance_value["status"], "errors": conformance_value["errors"], "authorizes": []}, ensure_ascii=False, sort_keys=True))
if __name__ == "__main__":
    main()

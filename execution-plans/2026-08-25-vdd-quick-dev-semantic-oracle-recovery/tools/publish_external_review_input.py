"""Publish current conformance and external semantic-review input artifacts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import argparse
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


def candidate_ref(path: Path, candidate_commit: str) -> dict[str, str]:
    """Reference an immutable candidate file by its committed blob bytes."""
    target = path.resolve()
    try:
        relative = target.relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise RuntimeError(f"candidate input escapes repository: {path}") from exc
    blob = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{candidate_commit}:{relative}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if blob.returncode != 0:
        raise RuntimeError(f"candidate blob is unavailable: {relative}")
    return {"path": relative, "sha256": "sha256:" + hashlib.sha256(blob.stdout).hexdigest()}


def require_head_bytes(path: Path) -> None:
    """Compatibility guard for callers that bind the current HEAD directly."""
    try:
        require_candidate_bytes(path, "HEAD")
    except RuntimeError as exc:
        raise RuntimeError(f"candidate input must match HEAD exactly: {path}") from exc


def require_candidate_bytes(path: Path, candidate_commit: str) -> None:
    """Require immutable candidate inputs to match both the candidate and HEAD."""
    root = ROOT.resolve()
    target = path.resolve()
    try:
        relative = target.relative_to(root).as_posix()
    except ValueError as exc:
        raise RuntimeError(f"candidate input escapes repository: {path}") from exc
    candidate = subprocess.run(
        ["git", "-C", str(root), "rev-parse", f"{candidate_commit}:{relative}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    committed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", f"HEAD:{relative}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    normalized = subprocess.run(
        ["git", "-C", str(root), "hash-object", "--path", relative, str(target)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    if (
        candidate.returncode != 0
        or committed.returncode != 0
        or normalized.returncode != 0
        or candidate.stdout.strip() != committed.stdout.strip()
        or candidate.stdout.strip() != normalized.stdout.strip()
    ):
        raise RuntimeError(f"candidate input must match candidate and HEAD exactly: {relative}")


def require_candidate_ancestor(candidate_commit: str) -> None:
    resolved = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--verify", f"{candidate_commit}^{{commit}}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    if resolved.returncode != 0:
        raise RuntimeError(f"candidate commit is invalid: {candidate_commit}")
    ancestor = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", candidate_commit, "HEAD"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    if ancestor.returncode != 0:
        raise RuntimeError(f"candidate commit is not an ancestor of HEAD: {candidate_commit}")


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--candidate-commit", required=True)
    parser.add_argument("--mapping", type=Path, default=GOV / "requirements-acceptance-mapping.v1.reviewed.json")
    parser.add_argument("--manifest", type=Path, default=GOV / "vdd-source-freeze-manifest.v1.external-bd210cef-successor.json")
    parser.add_argument("--skill-input-receipt", type=Path, default=PLAN / "skill-input/repair-round-4/receipt.v1.json")
    args = parser.parse_args()
    require_candidate_ancestor(args.candidate_commit)
    mapping = args.mapping.resolve()
    manifest = args.manifest.resolve()
    current_receipt = args.skill_input_receipt.resolve()
    for candidate_input in (
        PLAN / "implementation-contract.v1.json",
        PLAN / "command-registry.v1.json",
        manifest,
        mapping,
        current_receipt,
    ):
        require_candidate_bytes(candidate_input, args.candidate_commit)
    conformance = GOV / f"vdd-conformance-result.v1.{args.tag}.json"
    review_input = GOV / f"external-semantic-review-input.v1.{args.tag}.json"
    validator = ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/validate_conformance.py"
    result = subprocess.run(
        ["python", str(validator), "--repository-root", str(ROOT), "--manifest", str(manifest), "--mapping", str(mapping)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if not result.stdout.strip():
        raise RuntimeError(result.stderr)
    conformance_value = json.loads(result.stdout)
    write_new(conformance, conformance_value)
    handoff = conformance_value.get("semantic_handoff") or {}
    frozen_authority = handoff.get("frozen_authority", {})
    source_manifest_hash = frozen_authority.get("source_manifest_hash", conformance_value.get("source_manifest_hash"))
    ambiguity_ids = handoff.get("affected_obligation_ids", [])
    affected_requirement_ids = handoff.get("affected_requirement_ids", [])
    package = {
        "schema_version": "vdd-external-semantic-review-input.v1",
        "plan_id": "vdd-quick-dev-semantic-oracle-recovery",
        "profile": handoff.get("profile", "bootstrap-upstream-plan"),
        "selection_hash": json.loads(manifest.read_text(encoding="utf-8"))["selection_hash"],
        "candidate": {
            "head_commit": args.candidate_commit,
            "implementation_contract": candidate_ref(PLAN / "implementation-contract.v1.json", args.candidate_commit),
            "command_registry": candidate_ref(PLAN / "command-registry.v1.json", args.candidate_commit),
        },
        "source_freeze": ref(manifest),
        "requirements_mapping": ref(mapping),
        "conformance_result": ref(conformance),
        "skill_input_receipt": ref(current_receipt),
        "required_review_bindings": {
            "semantic_handoff_hash": semantic_handoff_hash(handoff) if handoff else None,
            "source_manifest_hash": source_manifest_hash,
            "requirements_manifest_hash": ref(mapping)["sha256"],
            "ambiguity_ids": ambiguity_ids,
            "affected_requirement_ids": affected_requirement_ids,
        },
        "review_scope": "Rebind the reviewed semantic dispositions and source evidence to this exact candidate; do not authorize implementation.",
        "required_output": "vdd-review-run.v1",
        "authorizes": [],
    }
    write_new(review_input, package)
    print(json.dumps({"conformance": ref(conformance), "review_input": ref(review_input), "status": conformance_value["status"], "errors": conformance_value["errors"], "authorizes": []}, ensure_ascii=False, sort_keys=True))
if __name__ == "__main__":
    main()

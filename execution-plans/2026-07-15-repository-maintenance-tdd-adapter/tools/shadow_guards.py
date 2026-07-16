from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


ADDITIVE_FILES = {"implementation-contract.v1.json", "fixtures/tdd-adapter-shadow.v1.json"}


def protected_tree_identity(root: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    count = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(root).as_posix()
        if relative in ADDITIVE_FILES:
            continue
        digest.update(relative.encode("utf-8")); digest.update(b"\0")
        digest.update(path.read_bytes()); digest.update(b"\0")
        count += 1
    return "sha256:" + digest.hexdigest(), count


def validate_shadow_protected_trees(plan_root: Path, shadow: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    import json
    baseline_path = plan_root / "schemas" / "shadow-protected-baseline.v1.json"
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return [{"rule_id": "RMAP-SHADOW-PROTECTED-DRIFT", "target": baseline_path.as_posix(), "message": "protected baseline is missing or invalid"}]
    baseline_plans = {item.get("plan_id"): item for item in baseline.get("plans", []) if isinstance(item, dict)}
    evidence_path = (plan_root / baseline.get("evidence_path", "")).resolve()
    evidence_hash = "sha256:" + hashlib.sha256(evidence_path.read_bytes()).hexdigest() if evidence_path.is_file() else None
    if evidence_hash != baseline.get("evidence_sha256"):
        findings.append({"rule_id": "RMAP-SHADOW-PROTECTED-DRIFT", "target": "shadow-baseline-evidence", "message": "protected baseline evidence is missing or stale"})
    if shadow.get("protected_baseline_id") != baseline.get("baseline_id"):
        findings.append({"rule_id": "RMAP-SHADOW-PROTECTED-DRIFT", "target": "shadow-backfill", "message": "protected baseline identity differs"})
    for item in shadow.get("plans", []):
        frozen = baseline_plans.get(item.get("plan_id"), {})
        if item.get("path") != frozen.get("path"):
            findings.append({"rule_id": "RMAP-SHADOW-PROTECTED-DRIFT", "target": str(item.get("plan_id")), "message": "shadow target differs from protected baseline"}); continue
        target = (plan_root / item.get("path", "")).resolve()
        if not target.is_dir():
            findings.append({"rule_id": "RMAP-SHADOW-PROTECTED-DRIFT", "target": str(item.get("plan_id")), "message": "shadow target is missing"}); continue
        actual_hash, actual_count = protected_tree_identity(target)
        if actual_hash != frozen.get("protected_tree_sha256") or actual_count != frozen.get("protected_file_count"):
            findings.append({"rule_id": "RMAP-SHADOW-PROTECTED-DRIFT", "target": str(item.get("plan_id")), "message": "protected tree bytes differ from baseline"})
    return findings

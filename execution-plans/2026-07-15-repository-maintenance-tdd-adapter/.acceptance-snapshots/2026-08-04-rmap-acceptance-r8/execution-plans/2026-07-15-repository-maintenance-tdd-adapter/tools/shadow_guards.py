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
    baseline_path = plan_root / "schemas" / "shadow-protected-baseline.v2.json"
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return [{"rule_id": "RMAP-SHADOW-PROTECTED-DRIFT", "target": baseline_path.as_posix(), "message": "protected baseline is missing or invalid"}]
    baseline_plans = {item.get("plan_id"): item for item in baseline.get("plans", []) if isinstance(item, dict)}
    historical = baseline.get("historical_source", {})
    predecessor_path = plan_root / "schemas" / "shadow-protected-baseline.v1.json"
    predecessor_hash = "sha256:" + hashlib.sha256(predecessor_path.read_bytes()).hexdigest()
    if (
        baseline.get("schema_version") != "rmap.shadow-protected-baseline.v2"
        or not isinstance(historical, dict)
        or historical.get("required_for_clean_checkout_validation") is not False
        or historical.get("path") != "execution-plans/2026-07-15-repository-maintenance-tdd-adapter/schemas/shadow-protected-baseline.v1.json"
        or historical.get("sha256") != predecessor_hash
        or baseline.get("predecessor_baseline_id") != "repair-20260718-1500-bootstrap-trust-root-successor"
        or baseline.get("revision_reason") != "accepted-downstream-control-plane-evolution"
    ):
        findings.append({"rule_id": "RMAP-SHADOW-PROTECTED-DRIFT", "target": "shadow-baseline-projection", "message": "durable protected baseline projection is invalid"})
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


def validate_shadow_registry(plan_root: Path, shadow: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    expected = ["llm-review-evidence-gate-hardening", "phase-a-frontend-gdd-to-module-workflow-hardening", "phase-frontend-boundary-hardening"]
    plans = shadow.get("plans")
    if shadow.get("authoritative") is not False or shadow.get("mode") != "additive-metadata-shadow-only":
        findings.append({"rule_id": "RMAP-SHADOW-AUTHORITY", "target": "shadow-backfill", "message": "shadow registry is authoritative"})
    if not isinstance(plans, list) or [item.get("plan_id") for item in plans] != expected or [item.get("order") for item in plans] != [1, 2, 3]:
        findings.append({"rule_id": "RMAP-SHADOW-ORDER", "target": "shadow-backfill", "message": "shadow order mismatch"})
    elif any(item.get("state_change_authorized") is not False for item in plans):
        findings.append({"rule_id": "RMAP-SHADOW-AUTHORITY", "target": "shadow-backfill", "message": "shadow state change is authorized"})
    findings.extend(validate_shadow_protected_trees(plan_root, shadow))
    return findings

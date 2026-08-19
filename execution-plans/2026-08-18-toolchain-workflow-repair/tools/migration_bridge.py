"""Materialize one declared future RED test without starting a Quick Dev slice."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


TEMPLATES = {
    "W0": '''from scripts.python import skill_input_consumption as consumption

def test_typed_selection_keeps_selection_and_content_identity_separate():
    source = [{"role": "normative_source", "path": "docs/input.md", "module": "plan", "resource_set": "core", "sha256": "sha256:" + "a" * 64}]
    result = consumption.build_typed_source_selection_v2(source)
    assert result["sourceSelectionHash"].startswith("sha256:")
    assert result["sourceContentHash"].startswith("sha256:")

def test_successor_generation_id_does_not_change_selection_hash():
    base = {"consumer": "quick-dev-tdd-adapter", "operation": "execute", "target": "plan", "source_roles": {"target_files": ["requirements.md"]}}
    first = consumption.source_selection_hash({**base, "route_identity": "quick-dev.self_hosted.plan.prestart-45"})
    successor = consumption.source_selection_hash({**base, "route_identity": "other-route.prestart-46"})
    assert first == successor

def test_equivalent_source_role_order_does_not_change_selection_hash():
    base = {"consumer": "quick-dev-tdd-adapter", "operation": "execute", "target": "plan"}
    first = consumption.source_selection_hash({**base, "source_roles": {"target_files": ["requirements.md", "AGENTS.md"]}})
    equivalent = consumption.source_selection_hash({**base, "source_roles": {"target_files": ["AGENTS.md", "requirements.md"]}})
    assert first == equivalent
''',
    "W1": '''from scripts.python import skill_input_transport as transport

def test_transport_resume_preserves_content_identity():
    plan = transport.plan_transport(32768, 1048576, content_hash="sha256:" + "a" * 64)
    resumed = transport.resume_transport(plan, content_hash="sha256:" + "a" * 64)
    assert resumed["content_hash"] == plan["content_hash"]
''',
"W2": '''from scripts.python import skill_input_coverage as coverage
import pytest

def test_coverage_rejects_missing_required_page():
    result = coverage.evaluate_coverage(required_pages=["p1", "p2"], observed_pages=["p1"])
    assert result["status"] == "insufficient"
    assert result["missing"] == ["p2"]

def test_coverage_rejects_conflicting_duplicate_page():
    result = coverage.evaluate_coverage(required_pages=["p1"], observed_pages=["p1", "p1"])
    assert result["status"] == "insufficient"

def test_coverage_rejects_unexpected_page():
    result = coverage.evaluate_coverage(required_pages=["p1"], observed_pages=["p1", "p3"])
    assert result["status"] == "insufficient"

def test_coverage_rejects_invalid_page_identity():
    with pytest.raises(ValueError):
        coverage.evaluate_coverage(required_pages=["p1"], observed_pages=[None])

def test_coverage_rejects_source_hash_drift():
    result = coverage.evaluate_coverage(required_pages=["p1"], observed_pages=["p1"], source_hash="sha256:" + "a" * 64, observed_source_hash="sha256:" + "b" * 64)
    assert result["status"] == "stale-source"
''',
    "W3": '''from scripts.python import knowledge_gate_projection as gates

def test_knowledge_gates_keep_stale_catalog_degraded():
    result = gates.project_knowledge_gates(catalog_stale=True, read_set_same=True, source_bytes_same=True)
    assert result["route"] == "degraded-continuation"
    assert result["publication_allowed"] is False

def test_knowledge_gates_refresh_same_selection_source_drift():
    result = gates.project_knowledge_gates(catalog_stale=False, read_set_same=True, source_bytes_same=False)
    assert result["route"] == "successor-refresh"
    assert result["publication_allowed"] is False
''',
    "W4": '''from scripts.python import skill_input_generation as generation
from scripts.python import skill_input_current as current

def test_failed_generation_does_not_advance_current_pointer(tmp_path):
    before = current.resolve_current(tmp_path)
    generation.publish_generation(tmp_path, generation_id="g1", content=b"x")
    after = current.resolve_current(tmp_path)
    assert before == after
''',
    "W5": '''from scripts.python import skill_input_retention as retention

def test_retention_apply_requires_explicit_approval(tmp_path):
    plan = retention.plan_retention(tmp_path, dry_run=True)
    assert plan["mode"] == "dry-run"
    assert retention.apply_retention(tmp_path, approval=None)["status"] == "approval-required"
''',
    "W6": '''from scripts.python import skill_input_consumption as consumption

def test_end_to_end_selection_exposes_independent_identity_hashes():
    result = consumption.build_typed_source_selection_v2([])
    assert result["sourceSelectionHash"] != result["sourceContentHash"]
''',
}


def _plan_slice(plan: Path, slice_id: str) -> tuple[dict, str]:
    contract = json.loads((plan / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    selected = next((item for item in contract.get("slices", []) if item.get("slice_id") == slice_id), None)
    if not isinstance(selected, dict):
        raise ValueError("unknown slice")
    selector = selected.get("tdd", {}).get("red", {}).get("test_selector", "").split("::", 1)[0]
    if not selector or selector not in selected.get("planned_new_files", []) or slice_id not in TEMPLATES:
        raise ValueError("current slice template is not declared")
    if selector not in selected.get("allowed_changes", {}).get("tests", []):
        raise ValueError("planned RED test is outside the slice test write set")
    return selected, selector


def materialize(repository_root: Path, plan_dir: Path, slice_id: str, snapshot_paths: list[str]) -> Path:
    root, plan = repository_root.resolve(), plan_dir.resolve()
    try:
        plan.relative_to(root / "execution-plans")
    except ValueError as exc:
        raise ValueError("plan directory is outside execution-plans") from exc
    _slice, selector = _plan_slice(plan, slice_id)
    if snapshot_paths != [selector]:
        raise ValueError("bridge accepts only the current slice declared RED test")
    relative = Path(selector)
    if relative.is_absolute() or ".." in relative.parts or any(part in {"logs", "execution-plans"} for part in relative.parts):
        raise ValueError("bridge target is outside the allowed test boundary")
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("bridge target escapes repository root") from exc
    content = TEMPLATES[slice_id]
    if target.exists():
        if target.read_text(encoding="utf-8") != content:
            raise ValueError("existing planned test conflicts with bridge template")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--slice-id", required=True)
    parser.add_argument("--snapshot-path", nargs="+", required=True)
    parser.add_argument("--materialize-only", action="store_true")
    args = parser.parse_args()
    if not args.materialize_only:
        raise ValueError("bridge requires --materialize-only")
    target = materialize(args.repository_root, args.plan_dir, args.slice_id, args.snapshot_path)
    print(json.dumps({"status": "materialized", "slice_id": args.slice_id, "path": target.as_posix(), "authorizes": []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

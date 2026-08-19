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
    "W1": '''import importlib
import pytest


def test_transport_rejects_stale_continuation():
    try:
        transport = importlib.import_module("scripts.python.skill_input_transport")
    except ImportError:
        pytest.fail("TWR-W1-AUTO-TRANSPORT: module unavailable")
    plan = transport.plan_transport({"content_hash": "sha256:" + "a" * 64}, max_inline_bytes=1, page_bytes=1, max_pages_per_batch=1)
    assert transport.resume_transport(plan, "next", "sha256:" + "b" * 64)["status"] == "stale-continuation", "TWR-W1-AUTO-TRANSPORT: stale continuation accepted"
''',
    "W2": '''import importlib
import pytest


def test_coverage_rejects_gap_and_conflicting_overlap():
    try:
        coverage = importlib.import_module("scripts.python.skill_input_coverage")
    except ImportError:
        pytest.fail("TWR-W2-COVERAGE: module unavailable")
    result = coverage.evaluate_coverage(source_size=4, source_hash="sha256:" + "a" * 64, observed_ranges=[(0, 1), (2, 4)])
    assert result["status"] == "insufficient", "TWR-W2-COVERAGE: gap accepted"
''',
    "W3": '''import importlib
import pytest


def test_knowledge_gates_separate_degraded_execution_from_authority_ambiguity():
    try:
        gates = importlib.import_module("scripts.python.knowledge_gate_projection")
    except ImportError:
        pytest.fail("TWR-W3-THREE-GATES: module unavailable")
    degraded = gates.project_knowledge_gates(context_status="catalog_stale", changed_paths=[], selection_drift=False, authority_ambiguity=False, source_available=True, publication_quality="unknown")
    assert degraded["execution_route"] == "degraded-continuation", "TWR-W3-THREE-GATES: stale catalog blocked execution"
''',
    "W4": '''import importlib
import pytest


def test_partial_generation_cannot_advance_current_pointer(tmp_path):
    try:
        generation = importlib.import_module("scripts.python.skill_input_generation")
        current = importlib.import_module("scripts.python.skill_input_current")
    except ImportError:
        pytest.fail("TWR-W4-CURRENT-POINTER: module unavailable")
    before = current.resolve_current(tmp_path, expected_contract_hash="sha256:" + "a" * 64)
    generation.stage_generation(tmp_path, generation_id="g1", complete=False)
    assert current.resolve_current(tmp_path, expected_contract_hash="sha256:" + "a" * 64) == before, "TWR-W4-CURRENT-POINTER: partial generation advanced current"
''',
    "W5": '''import importlib
import pytest


def test_retention_rejects_unapproved_apply(tmp_path):
    try:
        retention = importlib.import_module("scripts.python.skill_input_retention")
    except ImportError:
        pytest.fail("TWR-W5-RETENTION: module unavailable")
    plan = retention.plan_retention(tmp_path)
    assert retention.apply_retention(plan, maintainer_approval=None)["status"] == "approval-required", "TWR-W5-RETENTION: unapproved retention applied"
''',
    "W6": '''import pytest
from scripts.python import skill_input_consumption as consumption


def test_end_to_end_resolution_rejects_invalid_intermediate():
    try:
        result = consumption.build_typed_source_selection_v2([], consumer="quick-dev", policy_revision="v2")
    except AttributeError:
        pytest.fail("TWR-W6-END-TO-END-MIGRATION: API unavailable")
    assert result["sourceSelectionHash"], "TWR-W6-END-TO-END-MIGRATION: invalid intermediate advanced"
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

from __future__ import annotations

import hashlib
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from closure_predicate import validate_runtime_closure
from current_router import impact_for_kinds, profile_contract, stop_loss
from detached_promotion import validate_detached_bundle
from process_executor_v2 import _counts


def test_zero_case_success_is_not_invented() -> None:
    assert _counts("plain success", timed_out=False) == (0, 0)
    assert _counts("1 passed in 0.01s", timed_out=False) == (1, 1)
    assert _counts("1 failed, 2 passed in 0.02s", timed_out=False) == (1, 3)


def test_terminal_selector_may_differ_from_tdd_selector() -> None:
    snapshot = "sha256:" + "a" * 64
    edge_hash = "sha256:" + "b" * 64
    tuples = []
    for stage in ("red", "green", "refactor", "terminal"):
        tuples.append({"tuple_key": f"S1|A-X|{stage}", "slice_id": "S1", "acceptance_id": "A-X", "stage": stage, "runtime_edge_sha256": edge_hash, "selector_identity": "TDD" if stage != "terminal" else "TERMINAL", "current_snapshot_sha256": snapshot})
    valid, findings = validate_runtime_closure(tuples, {x["tuple_key"] for x in tuples}, snapshot)
    assert valid, findings


def test_duplicate_tuple_fails() -> None:
    snapshot = "sha256:" + "a" * 64
    edge_hash = "sha256:" + "b" * 64
    item = {"tuple_key": "S1|A-X|red", "slice_id": "S1", "acceptance_id": "A-X", "stage": "red", "runtime_edge_sha256": edge_hash, "selector_identity": "X", "current_snapshot_sha256": snapshot}
    valid, findings = validate_runtime_closure([item, dict(item)], {item["tuple_key"]}, snapshot)
    assert not valid and "tuple-key-duplicate" in findings


def test_repeated_fingerprint_stops_second_identical_failure() -> None:
    assert stop_loss([], "x")["stop"] is False
    assert stop_loss(["x"], "x")["stop"] is True


def test_change_impact_matrix_invalidates_only_required_stages() -> None:
    assert impact_for_kinds(["selector_fixture_target_case_source"]) == ["red", "green", "refactor", "terminal"]
    assert impact_for_kinds(["production_owner"]) == ["green", "refactor", "terminal"]
    assert impact_for_kinds(["predecessor"]) == ["successors", "terminal"]
    assert impact_for_kinds(["ordinary_documentation"]) == []
    assert impact_for_kinds(["development_governance"]) == []
    combined = impact_for_kinds(["production_owner", "descriptor_compiler"])
    assert combined == ["descriptor", "red", "green", "refactor", "terminal"]


def test_profiles_cannot_weaken_truth_floor() -> None:
    standard = profile_contract("standard")
    self_hosted = profile_contract("self-hosted")
    assert standard and self_hosted
    for invalid in ("fast-but-trusting", "legacy-v1"):
        try:
            profile_contract(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("unknown profile must fail closed")


def test_detached_bundle_requires_external_positive_negative_mutation_cover(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    detached = tmp_path / "detached"
    candidate.mkdir()
    detached.mkdir()
    artifacts = []
    for role in ("judge", "oracle"):
        path = detached / f"{role}.txt"
        path.write_text(f"{role}\n", encoding="utf-8")
        artifacts.append({"role": role, "path": str(path), "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(), "read_only": True})
    for fixture_kind in ("positive", "negative", "mutation"):
        path = detached / f"fixture-{fixture_kind}.json"
        path.write_text(f"{{\"kind\":\"{fixture_kind}\"}}\n", encoding="utf-8")
        artifacts.append({"role": "fixture", "fixture_kind": fixture_kind, "path": str(path), "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(), "read_only": True})
    bundle = {"schema": "detached-judge-bundle.v1", "source_commit": "c", "source_tree": "t", "judge_identity": "j", "judge_version": "1", "read_only_open_result": True, "promotion_revalidation_result": True, "artifacts": artifacts}
    valid, findings = validate_detached_bundle(bundle, candidate_root=candidate)
    assert valid, findings

    missing_mutation = {**bundle, "artifacts": [item for item in artifacts if item.get("fixture_kind") != "mutation"]}
    valid, findings = validate_detached_bundle(missing_mutation, candidate_root=candidate)
    assert not valid and any("fixture-kind-cover" in item for item in findings)

    artifacts[0]["path"] = str(candidate / "judge.txt")
    (candidate / "judge.txt").write_text("judge", encoding="utf-8")
    artifacts[0]["sha256"] = "sha256:" + hashlib.sha256((candidate / "judge.txt").read_bytes()).hexdigest()
    valid, findings = validate_detached_bundle(bundle, candidate_root=candidate)
    assert not valid and any("inside-candidate" in item for item in findings)

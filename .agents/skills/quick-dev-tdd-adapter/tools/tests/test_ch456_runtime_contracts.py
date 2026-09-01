from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
import sys

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from closure_predicate import validate_runtime_closure
from current_router import impact_for_kinds, profile_contract, stop_loss
from detached_promotion import FAILURE_FAMILIES, validate_detached_bundle
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
    fast_ship = profile_contract("fast-ship")
    standard = profile_contract("standard")
    self_hosted = profile_contract("self-hosted")
    assert fast_ship and standard and self_hosted
    assert fast_ship["targeted_only"] is True
    assert standard["regression_required"] is True
    assert self_hosted["detached_promotion_required"] is True
    for invalid in ("fast-but-trusting", "legacy-v1"):
        try:
            profile_contract(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("unknown profile must fail closed")


def test_detached_bundle_requires_external_fixture_and_failure_family_cover(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    detached = tmp_path / "detached"
    candidate.mkdir()
    detached.mkdir()

    def write_read_only(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")
        path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    def ref(path: Path) -> dict[str, str]:
        return {
            "path": path.relative_to(detached).as_posix(),
            "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    judge = detached / "judge.py"
    oracle = detached / "oracle.py"
    write_read_only(judge, "def judge(value):\n    return bool(value)\n")
    write_read_only(oracle, "EXPECTED = {'status': 'pass'}\n")

    fixtures: list[dict[str, str]] = []
    fixture_meta: dict[str, tuple[str, str | None]] = {}
    positive = detached / "fixture-positive.json"
    write_read_only(positive, json.dumps({"fixture_kind": "positive"}) + "\n")
    fixtures.append(ref(positive))
    fixture_meta[positive.name] = ("positive", None)
    for index, family in enumerate(sorted(FAILURE_FAMILIES)):
        kind = "negative" if index % 2 == 0 else "mutation"
        path = detached / f"fixture-{family}.json"
        write_read_only(path, json.dumps({"fixture_kind": kind, "failure_family": family}) + "\n")
        fixtures.append(ref(path))
        fixture_meta[path.name] = (kind, family)

    bundle = {
        "schema": "detached-judge-bundle.v1",
        "source_commit": "c",
        "source_tree": "sha256:" + "1" * 64,
        "judge": {**ref(judge), "identity": "j"},
        "oracle": ref(oracle),
        "fixtures": fixtures,
        "read_only_open": True,
        "revalidated_at_promotion": True,
    }
    valid, findings = validate_detached_bundle(bundle, candidate_root=candidate, bundle_root=detached, allow_v2=False)
    assert valid, findings

    missing_family = {
        **bundle,
        "fixtures": [
            item for item in fixtures
            if fixture_meta[Path(item["path"]).name][1] != "unexpected-green"
        ],
    }
    valid, findings = validate_detached_bundle(missing_family, candidate_root=candidate, bundle_root=detached, allow_v2=False)
    assert not valid and any("failure-family-cover" in item for item in findings)

    missing_mutation = {
        **bundle,
        "fixtures": [
            item for item in fixtures
            if fixture_meta[Path(item["path"]).name][0] != "mutation"
        ],
    }
    valid, findings = validate_detached_bundle(missing_mutation, candidate_root=candidate, bundle_root=detached, allow_v2=False)
    assert not valid and any("fixture-kind-cover" in item for item in findings)

    old_shape = {
        "schema": "detached-judge-bundle.v1",
        "source_commit": "c",
        "source_tree": "t",
        "judge_identity": "j",
        "judge_version": "1",
        "read_only_open_result": True,
        "promotion_revalidation_result": True,
        "artifacts": [],
    }
    valid, findings = validate_detached_bundle(old_shape, candidate_root=candidate, bundle_root=detached)
    assert not valid and "bundle:closed-schema" in findings

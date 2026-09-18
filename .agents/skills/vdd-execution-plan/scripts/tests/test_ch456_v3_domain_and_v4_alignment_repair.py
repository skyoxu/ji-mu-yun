from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_compiler_gate as gate
import semantic_feasibility_patch  # noqa: F401  # installs stable patch stack
import semantic_alignment_repair_patch as alignment


def _v3_payload(oid: str) -> dict:
    return {
        "acceptances": [{
            "obligation_ids": [oid],
            "source_refs": ["req.md#FR-1"],
            "given": "a duplicate claim",
            "when": "the claim is evaluated",
            "then": "duplicate is returned",
            "oracle": {"observable": "claim result", "expected": "duplicate", "forbidden": ["accepted"]},
            "assertion_ids": ["ASSERT-DUPLICATE"],
        }],
        "failure_intents": [{
            "obligation_ids": [oid],
            "failure_family": "expected-red",
            "selector_intent": "tests/test_ledger.py",
            "expected_outcome": "fail",
            "failure_id": "DUPLICATE-RED",
        }],
        "slice_hints": [{
            "obligation_ids": [oid],
            "production_owners": ["src/ledger.py"],
            "verification_lane": "unit",
            "behavior_change": "reject duplicate claims",
            "affected_subjects": ["ledger"],
            "state_transition": "active->active",
            "rollback_scope": {"production_paths": ["src/ledger.py"], "state_or_schema_compatibility": "compatible"},
            "allowed_write_paths": ["src/ledger.py"],
            "execution_snapshot_paths": ["tests/test_ledger.py"],
            "planned_new_files": ["tests/test_ledger.py"],
            "terminal_predicate": "all assertions pass",
            "forbidden_paths": [],
            "validation_commands": [[sys.executable, "-m", "pytest", "tests/test_ledger.py", "-q"]],
        }],
    }


def _v3_inline_repair_payload(oid: str) -> dict:
    payload = _v3_payload(oid)
    return {
        "obligation_contracts": {
            oid: {
                "acceptance": payload["acceptances"][0],
                "failure_intents": payload["failure_intents"],
                "slice_hint": payload["slice_hints"][0],
            }
        }
    }


def test_unknown_v3_obligation_routes_through_existing_single_repair(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ledger.py").write_text("VALUE = 1\n", encoding="utf-8")
    obligations = [{
        "obligation_id": "O-1",
        "source_refs": ["req.md#FR-1"],
        "subject": "ledger",
        "requirement_type": "Product",
        "obligation_kind": "behavior",
        "status": "active",
    }]
    repaired = _v3_payload("O-1")
    result = gate.normative_invoke_worker(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        stage="v3",
        payload={"obligations": obligations},
        prompt="Compile Acceptance contracts.",
        worker_cache={
            "v3": _v3_payload("O-UNKNOWN"),
            "v3-schema-repair": _v3_inline_repair_payload("O-1"),
        },
    )
    assert result == repaired


def _acceptance() -> dict:
    item = {
        "obligation_ids": ["O-1"],
        "source_refs": ["req.md#FR-1"],
        "given": "a request",
        "when": "processed",
        "then": "a result exists",
        "oracle": {"observable": "result", "expected": "ok", "forbidden": ["error"]},
        "assertion_ids": ["ASSERT-OLD"],
        "red_intent_ids": [],
    }
    item["acceptance_id"] = gate.sc._stable_acceptance_id(item)
    return item


def _failure(aid: str) -> dict:
    item = {
        "acceptance_ids": [aid],
        "failure_id": "CLAIM-RED",
        "failure_family": "expected-red",
        "selector_intent": "tests/test_ledger.py",
        "expected_outcome": "fail",
    }
    item["failure_intent_id"] = gate.sc._stable_failure_intent_id(item)
    return item


def test_v4_misaligned_acceptance_gets_bounded_repair_and_independent_recheck(monkeypatch, tmp_path: Path) -> None:
    obligations = [{
        "obligation_id": "O-1",
        "status": "active",
        "subject": "ledger",
        "source_refs": ["req.md#FR-1"],
    }]
    acceptance = _acceptance()
    failure = _failure(acceptance["acceptance_id"])
    acceptance["red_intent_ids"] = [failure["failure_intent_id"]]
    acceptances = [acceptance]
    failures = [failure]
    old_aid = acceptance["acceptance_id"]
    old_binding = (list(acceptance["obligation_ids"]), list(acceptance["source_refs"]))

    monkeypatch.setattr(
        alignment,
        "_BASE_SEMANTIC_ALIGN",
        lambda **_kwargs: {
            "valid": False,
            "findings": [f"v4:misaligned-acceptance:{old_aid}"],
            "worker": {
                "covered_obligation_ids": ["O-1"],
                "missing_obligation_ids": [],
                "invented_obligation_ids": [],
                "misaligned_acceptance_ids": [old_aid],
                "oracle_alignment": {},
                "repairs": ["make the observable and assertion discriminate the bound behavior"],
            },
        },
    )

    calls: list[str] = []

    def fake_worker(**kwargs):
        stage = kwargs["stage"]
        calls.append(stage)
        if stage == "v4-acceptance-repair":
            return {
                "acceptance_repairs": [{
                    "acceptance_id": old_aid,
                    "given": "the ledger has no active claim for the key",
                    "when": "the key is claimed",
                    "then": "the claim is accepted and becomes active",
                    "oracle": {
                        "observable": "claim result and active state",
                        "expected": "accepted with one active claim",
                        "forbidden": ["duplicate active claims", "no active claim"],
                    },
                    "assertion_ids": ["ASSERT-CLAIM-ACCEPTED", "ASSERT-ACTIVE-ONCE"],
                }]
            }
        if stage == "v4-recheck":
            current_aid = kwargs["payload"]["acceptances"][0]["acceptance_id"]
            return {
                "covered_obligation_ids": ["O-1"],
                "missing_obligation_ids": [],
                "invented_obligation_ids": [],
                "misaligned_acceptance_ids": [],
                "oracle_alignment": {current_aid: "aligned"},
                "repairs": [],
            }
        raise AssertionError(stage)

    monkeypatch.setattr(gate.sc, "invoke_worker", fake_worker)
    result = alignment.semantic_align_with_bounded_repair(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        source_index={"entries": [{"source_ref": "req.md#FR-1"}]},
        obligations=obligations,
        acceptances=acceptances,
        failures=failures,
        worker_cache=None,
    )

    assert result["valid"] is True
    assert result["repair_attempted"] is True
    assert calls == ["v4-acceptance-repair", "v4-recheck"]
    assert (acceptances[0]["obligation_ids"], acceptances[0]["source_refs"]) == old_binding
    assert acceptances[0]["acceptance_id"] != old_aid
    assert failures[0]["acceptance_ids"] == [acceptances[0]["acceptance_id"]]
    assert acceptances[0]["red_intent_ids"] == [failures[0]["failure_intent_id"]]


def test_v4_missing_semantics_never_invokes_acceptance_repair(monkeypatch, tmp_path: Path) -> None:
    obligations = [{"obligation_id": "O-1", "status": "active", "subject": "ledger", "source_refs": ["req.md#FR-1"]}]
    acceptance = _acceptance()
    failure = _failure(acceptance["acceptance_id"])
    acceptance["red_intent_ids"] = [failure["failure_intent_id"]]

    monkeypatch.setattr(
        alignment,
        "_BASE_SEMANTIC_ALIGN",
        lambda **_kwargs: {
            "valid": False,
            "findings": ["v4:missing:O-1", f"v4:misaligned-acceptance:{acceptance['acceptance_id']}"],
            "worker": {},
        },
    )
    monkeypatch.setattr(gate.sc, "invoke_worker", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("repair must not run")))

    result = alignment.semantic_align_with_bounded_repair(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        source_index={"entries": [{"source_ref": "req.md#FR-1"}]},
        obligations=obligations,
        acceptances=[acceptance],
        failures=[failure],
        worker_cache=None,
    )
    assert result["valid"] is False
    assert "v4:missing:O-1" in result["findings"]


def test_v4_isolated_missing_bound_to_misaligned_acceptance_gets_repaired(monkeypatch, tmp_path: Path) -> None:
    obligations = [{"obligation_id": "O-1", "status": "active", "subject": "ledger", "source_refs": ["req.md#FR-1"]}]
    acceptance = _acceptance()
    failure = _failure(acceptance["acceptance_id"])
    acceptance["red_intent_ids"] = [failure["failure_intent_id"]]
    old_aid = acceptance["acceptance_id"]

    monkeypatch.setattr(
        alignment,
        "_BASE_SEMANTIC_ALIGN",
        lambda **_kwargs: {
            "valid": False,
            "findings": [
                "v4:active-not-covered:O-1",
                "v4:missing:O-1",
                f"v4:misaligned-acceptance:{old_aid}",
            ],
            "worker": {
                "covered_obligation_ids": [],
                "missing_obligation_ids": ["O-1"],
                "invented_obligation_ids": [],
                "misaligned_acceptance_ids": [old_aid],
                "oracle_alignment": {},
                "repairs": ["make the Acceptance describe the bound ledger behavior"],
            },
        },
    )

    def worker(**kwargs):
        if kwargs["stage"] == "v4-acceptance-repair":
            return {"acceptance_repairs": [{
                "acceptance_id": old_aid,
                "given": "the ledger has no active claim for the key",
                "when": "the key is claimed",
                "then": "the claim is accepted within the declared ledger boundary",
                "oracle": {"observable": "claim result", "expected": "accepted", "forbidden": ["error"]},
                "assertion_ids": ["ASSERT-CLAIM-BOUNDARY"],
            }]}
        if kwargs["stage"] == "v4-recheck":
            repaired_aid = kwargs["payload"]["acceptances"][0]["acceptance_id"]
            return {
                "covered_obligation_ids": ["O-1"],
                "missing_obligation_ids": [],
                "invented_obligation_ids": [],
                "misaligned_acceptance_ids": [],
                "oracle_alignment": {repaired_aid: "aligned"},
                "repairs": [],
            }
        raise AssertionError(kwargs["stage"])

    monkeypatch.setattr(gate.sc, "invoke_worker", worker)
    result = alignment.semantic_align_with_bounded_repair(
        root=tmp_path,
        out_dir=tmp_path / "plan",
        source_index={"entries": [{"source_ref": "req.md#FR-1"}]},
        obligations=obligations,
        acceptances=[acceptance],
        failures=[failure],
        worker_cache=None,
    )
    assert result["valid"] is True
    assert result["repair_attempted"] is True


def test_v4_permits_one_follow_up_repair_only_for_the_same_isolated_closure(monkeypatch, tmp_path: Path) -> None:
    obligations = [{"obligation_id": "O-1", "status": "active", "subject": "ledger", "source_refs": ["req.md#FR-1"]}]
    acceptance = _acceptance()
    failure = _failure(acceptance["acceptance_id"])
    acceptance["red_intent_ids"] = [failure["failure_intent_id"]]
    old_aid = acceptance["acceptance_id"]
    calls: list[str] = []

    monkeypatch.setattr(
        alignment,
        "_BASE_SEMANTIC_ALIGN",
        lambda **_kwargs: {
            "valid": False,
            "findings": ["v4:active-not-covered:O-1", "v4:missing:O-1", f"v4:misaligned-acceptance:{old_aid}"],
            "worker": {
                "covered_obligation_ids": [], "missing_obligation_ids": ["O-1"],
                "invented_obligation_ids": [], "misaligned_acceptance_ids": [old_aid],
                "oracle_alignment": {}, "repairs": ["make the Acceptance precise"],
            },
        },
    )

    def worker(**kwargs):
        stage = kwargs["stage"]
        calls.append(stage)
        current_aid = kwargs["payload"]["acceptances"][0]["acceptance_id"]
        if stage == "v4-acceptance-repair":
            return {"acceptance_repairs": [{
                "acceptance_id": current_aid,
                "given": "the ledger has no active claim", "when": "the key is claimed",
                "then": "the claim is accepted exactly once",
                "oracle": {"observable": "claim result", "expected": "accepted once", "forbidden": ["duplicate", "error"]},
                "assertion_ids": [f"ASSERT-ROUND-{calls.count(stage)}"],
            }]}
        if stage == "v4-recheck" and calls.count(stage) == 1:
            return {
                "covered_obligation_ids": [], "missing_obligation_ids": ["O-1"],
                "invented_obligation_ids": [], "misaligned_acceptance_ids": [current_aid],
                "oracle_alignment": {}, "repairs": ["make the observable discriminate the result"],
            }
        if stage == "v4-recheck":
            return {
                "covered_obligation_ids": ["O-1"], "missing_obligation_ids": [],
                "invented_obligation_ids": [], "misaligned_acceptance_ids": [],
                "oracle_alignment": {current_aid: "aligned"}, "repairs": [],
            }
        raise AssertionError(stage)

    monkeypatch.setattr(gate.sc, "invoke_worker", worker)
    result = alignment.semantic_align_with_bounded_repair(
        root=tmp_path, out_dir=tmp_path / "plan",
        source_index={"entries": [{"source_ref": "req.md#FR-1"}]},
        obligations=obligations, acceptances=[acceptance], failures=[failure], worker_cache=None,
    )
    assert result["valid"] is True
    assert result["repair_attempted"] is True
    assert result["repair_passes"] == 2
    assert calls == ["v4-acceptance-repair", "v4-recheck", "v4-acceptance-repair", "v4-recheck"]


def test_v4_allows_a_final_closed_repair_after_rechecks_expand_pure_misalignment(monkeypatch, tmp_path: Path) -> None:
    obligations = [{"obligation_id": "O-1", "status": "active", "subject": "ledger", "source_refs": ["req.md#FR-1"]}]
    acceptance = _acceptance()
    failure = _failure(acceptance["acceptance_id"])
    acceptance["red_intent_ids"] = [failure["failure_intent_id"]]
    calls: list[str] = []

    monkeypatch.setattr(
        alignment, "_BASE_SEMANTIC_ALIGN", lambda **_kwargs: {
            "valid": False,
            "findings": [f"v4:misaligned-acceptance:{acceptance['acceptance_id']}"],
            "worker": {
                "covered_obligation_ids": ["O-1"], "missing_obligation_ids": [],
                "invented_obligation_ids": [], "misaligned_acceptance_ids": [acceptance["acceptance_id"]],
                "oracle_alignment": {}, "repairs": ["narrow the oracle"],
            },
        },
    )

    def worker(**kwargs):
        stage = kwargs["stage"]
        calls.append(stage)
        current = kwargs["payload"]["acceptances"][0]["acceptance_id"]
        if stage == "v4-acceptance-repair":
            return {"acceptance_repairs": [{
                "acceptance_id": current, "given": "a ledger is available", "when": "a claim is checked",
                "then": "the claim result is observed", "oracle": {"observable": "claim result", "expected": "observed", "forbidden": ["substitute"]},
                "assertion_ids": [f"ASSERT-{calls.count(stage)}"],
            }]}
        if stage == "v4-recheck" and calls.count(stage) < 3:
            return {
                "covered_obligation_ids": ["O-1"], "missing_obligation_ids": [],
                "invented_obligation_ids": [], "misaligned_acceptance_ids": [current],
                "oracle_alignment": {}, "repairs": ["narrow the oracle again"],
            }
        if stage == "v4-recheck":
            return {
                "covered_obligation_ids": ["O-1"], "missing_obligation_ids": [],
                "invented_obligation_ids": [], "misaligned_acceptance_ids": [],
                "oracle_alignment": {current: "aligned"}, "repairs": [],
            }
        raise AssertionError(stage)

    monkeypatch.setattr(gate.sc, "invoke_worker", worker)
    result = alignment.semantic_align_with_bounded_repair(
        root=tmp_path, out_dir=tmp_path / "plan", source_index={"entries": [{"source_ref": "req.md#FR-1"}]},
        obligations=obligations, acceptances=[acceptance], failures=[failure], worker_cache=None,
    )
    assert result["valid"] is True
    assert result["repair_passes"] == 3
    assert calls == ["v4-acceptance-repair", "v4-recheck"] * 3


def test_v4_explicit_approval_adds_exactly_one_three_repair_cycle(monkeypatch, tmp_path: Path) -> None:
    alignment.configure_approved_v4_repair_cycles(1)
    assert alignment._maximum_closed_v4_repair_passes() == 6
    alignment.configure_approved_v4_repair_cycles(0)
    assert alignment._maximum_closed_v4_repair_passes() == 3


def test_v4_repair_targets_use_only_actual_acceptance_for_a_missing_obligation() -> None:
    acceptances = [
        {"acceptance_id": "A-BOUND", "obligation_ids": ["O-MISSING"]},
        {"acceptance_id": "A-REPORTED", "obligation_ids": ["O-OTHER"]},
    ]
    raw = {
        "missing_obligation_ids": ["O-MISSING"],
        # The worker may correctly identify a wording defect yet incorrectly
        # associate it with the missing obligation. The compiler owns IDs.
        "misaligned_acceptance_ids": ["A-REPORTED"],
    }
    assert alignment._repair_targets(raw, acceptances) == {"A-BOUND"}


def test_v4_repair_targets_drop_a_stale_worker_acceptance_id() -> None:
    acceptances = [{"acceptance_id": "A-BOUND", "obligation_ids": ["O-MISSING"]}]
    raw = {
        "missing_obligation_ids": ["O-MISSING"],
        "misaligned_acceptance_ids": ["A-STALE"],
    }
    assert alignment._repair_targets(raw, acceptances) == {"A-BOUND"}


def test_v4_repair_targets_include_compiler_uncovered_obligation_closure() -> None:
    acceptances = [
        {"acceptance_id": "A-MISSING", "obligation_ids": ["O-MISSING"]},
        {"acceptance_id": "A-UNCOVERED", "obligation_ids": ["O-UNCOVERED"]},
    ]
    raw = {"missing_obligation_ids": ["O-MISSING"], "misaligned_acceptance_ids": []}
    assert alignment._repair_targets(
        raw, acceptances, findings=["v4:active-not-covered:O-MISSING,O-UNCOVERED"]
    ) == {"A-MISSING", "A-UNCOVERED"}


def test_v4_source_chunk_retries_only_its_stale_acceptance_scope(monkeypatch, tmp_path: Path) -> None:
    payload = {"acceptances": [{"acceptance_id": "A-CURRENT"}]}
    stage = "v4-source-chunk-09"
    cache_path = tmp_path / ".compiler-cache" / gate.sc._worker_cache_key(stage, payload)
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("{}", encoding="utf-8")
    calls = []

    def worker(**kwargs):
        calls.append(kwargs["worker_cache"])
        if len(calls) == 1:
            return {
                "covered_obligation_ids": ["O-1"], "missing_obligation_ids": [],
                "misaligned_acceptance_ids": ["A-HISTORICAL"],
            }
        return {
            "covered_obligation_ids": ["O-1"], "missing_obligation_ids": [],
            "misaligned_acceptance_ids": [],
        }

    monkeypatch.setattr(gate.sc, "invoke_worker", worker)
    result = alignment._invoke_v4_source_chunk(
        root=tmp_path, out_dir=tmp_path, stage=stage, payload=payload, prompt="test",
        worker_cache={stage: {"unused": True}}, obligation_ids={"O-1"}, acceptance_ids={"A-CURRENT"},
        acceptance_obligations={"A-CURRENT": {"O-1"}},
    )

    assert result["misaligned_acceptance_ids"] == []
    assert calls == [{stage: {"unused": True}}, None]
    assert not cache_path.exists()
    assert list(cache_path.parent.glob(cache_path.name + ".stale-v4-source-scope*"))


def test_v4_source_chunk_retries_when_missing_obligation_omits_its_bound_acceptance(monkeypatch, tmp_path: Path) -> None:
    payload = {"acceptances": [{"acceptance_id": "A-BOUND"}, {"acceptance_id": "A-OTHER"}]}
    stage = "v4-source-chunk-09"
    cache_path = tmp_path / ".compiler-cache" / gate.sc._worker_cache_key(stage, payload)
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("{}", encoding="utf-8")
    calls = []

    def worker(**kwargs):
        calls.append(kwargs["worker_cache"])
        if len(calls) == 1:
            return {
                "covered_obligation_ids": [], "missing_obligation_ids": ["O-MISSING"],
                "misaligned_acceptance_ids": ["A-OTHER"],
            }
        return {
            "covered_obligation_ids": [], "missing_obligation_ids": ["O-MISSING"],
            "misaligned_acceptance_ids": ["A-BOUND"],
        }

    monkeypatch.setattr(gate.sc, "invoke_worker", worker)
    result = alignment._invoke_v4_source_chunk(
        root=tmp_path, out_dir=tmp_path, stage=stage, payload=payload, prompt="test",
        worker_cache={stage: {"unused": True}}, obligation_ids={"O-MISSING"},
        acceptance_ids={"A-BOUND", "A-OTHER"},
        acceptance_obligations={"A-BOUND": {"O-MISSING"}, "A-OTHER": {"O-OTHER"}},
    )

    assert result["misaligned_acceptance_ids"] == ["A-BOUND"]
    assert calls == [{stage: {"unused": True}}, None]
    assert list(cache_path.parent.glob(cache_path.name + ".stale-v4-source-scope*"))

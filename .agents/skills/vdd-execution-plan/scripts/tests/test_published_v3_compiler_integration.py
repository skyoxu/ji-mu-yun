"""ADR-0041: published V3 repair reuses only V3, not independent V4."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest import mock

from scripts.vdd import compile_plan as cli
import semantic_compiler as sc
import semantic_compiler_authority as authority
import semantic_v3_contract_repair as repair


ROOT = Path(__file__).resolve().parents[5]
PLAN = ROOT / (
    "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/"
    "repair/round-7/recompilation-4/cer-repair-1/quick-dev-ready/s12-runtime-red-repair-2"
)
REQUIREMENTS = ROOT / (
    "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/"
    "repair/round-7/recompilation-4/assembled-requirements.md"
)


def test_real_0805_predecessor_reuses_v3_but_invokes_v4() -> None:
    # A temporary copy keeps the published plan and its evidence immutable.
    with tempfile.TemporaryDirectory(dir=ROOT / "logs") as location:
        predecessor = Path(location) / "predecessor"
        successor = Path(location) / "successor"
        predecessor.mkdir()
        for name in (
            "semantic-plan-bundle.v1.json", "compiler-state.v1.json",
            "source-index.v1.json", "semantic-alignment.v1.json",
            "atomic-recall-alignment.v1.json", "obligations.v1.json",
        ):
            shutil.copyfile(PLAN / name, predecessor / name)
        bundle = json.loads((predecessor / "semantic-plan-bundle.v1.json").read_text(encoding="utf-8"))
        raw = repair.project_published_v3(bundle)
        target = "O-530CF6DD124B"
        acceptance = next(item for item in raw["acceptances"] if item["obligation_ids"] == [target])
        failures = [item for item in raw["failure_intents"] if item["obligation_ids"] == [target]]
        hint = next(item for item in raw["slice_hints"] if item["obligation_ids"] == [target])
        correction = {
            "schema": "vdd.v3-candidate-repair.v1",
            "requirements_sha256": "sha256:" + hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest(),
            "authorizes": [],
            "obligation_contracts": {target: {
                "acceptance": {key: deepcopy(value) for key, value in acceptance.items()
                               if key != "obligation_ids"},
                "failure_intents": [{key: deepcopy(value) for key, value in item.items()
                                     if key != "obligation_ids"} for item in failures],
                "slice_hint": {key: deepcopy(value) for key, value in hint.items()
                               if key != "obligation_ids"},
            }},
        }
        repair_path = Path(location) / "correction.json"
        repair_path.write_text(json.dumps(correction), encoding="utf-8")
        calls = []

        def underlying_worker(**kwargs):
            calls.append(kwargs["stage"])
            return {"independent_v4": True}

        def compile_probe(**kwargs):
            assert kwargs["out_dir"] == successor
            source = json.loads((predecessor / "source-index.v1.json").read_text(encoding="utf-8"))
            obligations = sc.compile_obligations(root=ROOT, out_dir=successor,
                                                  source_index=source, worker_cache=None)
            assert len(obligations) == 116
            observed_v3 = sc.invoke_worker(root=ROOT, out_dir=successor, stage="v3",
                                           payload={"obligations": obligations}, prompt="V3")
            assert len(observed_v3["acceptances"]) == 116
            assert len(observed_v3["failure_intents"]) == 155
            observed_v4 = sc.invoke_worker(root=ROOT, out_dir=successor, stage="v4",
                                           payload={}, prompt="V4")
            assert observed_v4["valid"] is True
            assert observed_v4["source_gap_claims"] == []
            return {"status": "repair-vdd", "stage": "V4"}

        argv = ["compile_plan.py", "--requirements", str(REQUIREMENTS),
                "--out-dir", str(successor), "--profile", "self-hosted",
                "--repair-published-v3-from", str(predecessor),
                "--v3-contract-repair", str(repair_path),
                "--published-v1-gap-extension",
                str(PLAN.parent.parent / "published-v1-fr4-probe-outcomes.json")]
        output = io.StringIO()
        with (mock.patch.object(sc, "invoke_worker", side_effect=underlying_worker),
              mock.patch.object(sc, "semantic_align", sc.semantic_align),
              mock.patch.object(sc, "compile_obligations", sc.compile_obligations),
              mock.patch.object(sc, "_v1_reuse_predecessor_plan", sc._v1_reuse_predecessor_plan),
              mock.patch.object(cli, "compile_plan", side_effect=compile_probe),
              mock.patch.object(sys, "argv", argv), redirect_stdout(output)):
            exit_code = cli.main()
        assert exit_code == 1
        assert calls == []
        assert json.loads(output.getvalue())["stage"] == "V4"
        assert not (successor / "compiler-state.v1.json").exists()


def test_published_v3_repair_stops_at_new_v4_source_gap() -> None:
    with tempfile.TemporaryDirectory() as location:
        root = Path(location)
        (root / ".agents").mkdir()
        (root / "AGENTS.md").write_text("Test repository.\n", encoding="utf-8")
        requirements = root / "req.md"
        requirements.write_text("# FR-1\nA requirement.\n", encoding="utf-8")
        out_dir = root / "plan"
        observations = {
            "V0": {"entries": []},
            "V0A": {"valid": True},
            "V1": [],
            "V2": {"valid": True},
            "V3": ([], [], []),
            "V3A": {"valid": True},
            "V4-atomic-recall": {
                "valid": False, "findings": ["atomic-recall:source-gap-count:2"],
                "metrics": {}, "source_gap_claims": [{"source_ref": "req.md#FR-1"}],
            },
        }
        def stage(_out, label, _function, *args, **kwargs):
            return observations[label]
        with mock.patch.object(authority, "stage_call", side_effect=stage):
            result = authority.compile_plan(requirements=requirements, out_dir=out_dir,
                                            published_v3_repair=True)
        assert result["status"] == "repair-vdd"
        assert result["stage"] == "V4"
        assert result["source_gap_claims"] == observations["V4-atomic-recall"]["source_gap_claims"]


def test_published_gap_extension_adds_only_two_fr4_contracts_without_v1_worker() -> None:
    bundle = json.loads((PLAN / "semantic-plan-bundle.v1.json").read_text(encoding="utf-8"))
    source = json.loads((PLAN / "source-index.v1.json").read_text(encoding="utf-8"))
    extension_path = PLAN.parent.parent / "published-v1-fr4-probe-outcomes.json"
    extension = repair.load_gap_extension(extension_path, REQUIREMENTS, source, bundle)
    ids = set(extension["obligation_contracts"])
    assert len(ids) == 2
    assert ids.isdisjoint({item["obligation_id"] for item in bundle["obligations"]})
    projected = repair.project_published_v3(bundle)
    with (mock.patch.object(sc, "invoke_worker", side_effect=AssertionError("worker called")),
          mock.patch.object(sc, "compile_obligations", sc.compile_obligations),
          mock.patch.object(sc, "_v1_reuse_predecessor_plan", sc._v1_reuse_predecessor_plan)):
        sc.configure_v1_reuse_predecessor_plan(PLAN)
        repair.install_published_v3_reuse(projected)
        repair.install_gap_extension(extension)
        obligations = sc.compile_obligations(root=ROOT, out_dir=PLAN.parent / "unused",
            source_index=source, worker_cache=None)
        raw = sc.invoke_worker(root=ROOT, out_dir=PLAN.parent / "unused", stage="v3",
            payload={"obligations": obligations}, prompt="V3")
    assert len(obligations) == len(bundle["obligations"]) + 2
    assert {item["obligation_id"] for item in obligations} == {
        item["obligation_id"] for item in bundle["obligations"]} | ids
    assert {item["obligation_ids"][0] for item in raw["acceptances"]} == {
        item["obligation_id"] for item in obligations}


def test_published_gap_extension_rejects_extra_obligation() -> None:
    bundle = json.loads((PLAN / "semantic-plan-bundle.v1.json").read_text(encoding="utf-8"))
    source = json.loads((PLAN / "source-index.v1.json").read_text(encoding="utf-8"))
    extension_path = PLAN.parent.parent / "published-v1-fr4-probe-outcomes.json"
    value = json.loads(extension_path.read_text(encoding="utf-8"))
    value["obligations"].append(deepcopy(value["obligations"][0]))
    with tempfile.TemporaryDirectory(dir=ROOT / "logs") as location:
        path = Path(location) / "extension.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        with __import__("pytest").raises(ValueError, match="exactly two"):
            repair.load_gap_extension(path, REQUIREMENTS, source, bundle)


def test_published_v1_replacement_replaces_only_named_fr10_obligations() -> None:
    bundle = json.loads((PLAN / "semantic-plan-bundle.v1.json").read_text(encoding="utf-8"))
    source = json.loads((PLAN / "source-index.v1.json").read_text(encoding="utf-8"))
    value = {
        "schema": "vdd.published-v1-repair.v1",
        "requirements_sha256": "sha256:" + hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest(),
        "authorizes": [],
        "source_ref": next(item["source_ref"] for item in source["entries"] if item["requirement_id"] == "FR-10"),
        "replacements": {},
        "v3_contracts": {},
    }
    targets = {"O-AF55FF781031", "O-B5F365100D81"}
    for oid in targets:
        old = next(item for item in bundle["obligations"] if item["obligation_id"] == oid)
        value["replacements"][oid] = {
            "subject": old["subject"], "trigger": "At disable and rollback, before re-enable.",
            "state_before": old["state_before"],
            "state_after": "Prior is observed at disable/rollback; Candidate is called at re-enable.",
            "expected_behavior": "Disable and rollback call Prior; re-enable calls Candidate.",
            "observable_result": "Transition receipts identify Prior at disable/rollback and Candidate at re-enable.",
            "forbidden_result": old["forbidden_result"], "requirement_type": old["requirement_type"],
            "obligation_kind": old["obligation_kind"], "source_refs": old["source_refs"],
            "unresolved_fragments": [], "status": "active", "depends_on": [],
            }
    for oid, raw in value["replacements"].items():
        new_id = __import__("semantic_compiler")._normalize_obligation(
            next(item for item in source["entries"] if item["requirement_id"] == "FR-10"), raw)["obligation_id"]
        value["v3_contracts"][new_id] = {
            "acceptance": {"source_refs": [value["source_ref"]], "given": "A valid route transition receipt exists.", "when": "Disable and rollback then re-enable execute through real calls.", "then": "Prior is observed before Candidate re-enable.", "oracle": {"observable": "Transition receipts", "expected": "Prior identity and baseline match at disable/rollback; Candidate is called at re-enable.", "forbidden": ["Configuration-only rollback"]}, "assertion_ids": ["fr10-v1-replacement-" + new_id]},
            "failure_intents": [{"failure_family": "expected-red", "selector_intent": "Make the Prior transition or Candidate re-enable call drift and assert rejection.", "expected_outcome": "fail", "failure_id": "FR10-REPLACEMENT-" + new_id}],
            "slice_hint": {"production_owners": ["scripts/sc/_semantic_gate_all_runtime.py"], "verification_lane": "runtime", "behavior_change": "Verify route transition order and baseline restoration.", "affected_subjects": ["Consumer route lifecycle"], "state_transition": "Prior disable/rollback -> Candidate re-enable", "rollback_scope": {"production_paths": ["scripts/sc/_semantic_gate_all_runtime.py"], "state_or_schema_compatibility": "Preserve receipt fields."}, "allowed_write_paths": ["scripts/sc/_semantic_gate_all_runtime.py"], "execution_snapshot_paths": [], "planned_new_files": [], "terminal_predicate": "Prior is observed at disable/rollback and Candidate is called at re-enable.", "forbidden_paths": ["PhaseA.Platform", "runtime/phase-a", "logs"], "validation_commands": [["python", "-m", "pytest", "scripts/sc/tests/tc_d1_cer/test_s44.py", "-q"]]}
        }
    with tempfile.TemporaryDirectory(dir=ROOT / "logs") as location:
        path = Path(location) / "replacement.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        replacement = repair.load_v1_replacement(path, REQUIREMENTS, source, bundle)
        assert set(replacement["normalized_replacements"]) == targets
        assert len(replacement["projected_v3"]["acceptances"]) == 2


def test_published_v1_split_replaces_one_fr6_obligation_with_two_contracts() -> None:
    bundle = json.loads((PLAN / "semantic-plan-bundle.v1.json").read_text(encoding="utf-8"))
    source = json.loads((PLAN / "source-index.v1.json").read_text(encoding="utf-8"))
    split_path = ROOT / (
        "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/"
        "repair/round-7/recompilation-4/cer-repair-1/published-v1-fr6-split.json"
    )
    split = repair.load_v1_split(split_path, REQUIREMENTS, source, bundle)
    assert split["replaced_obligation_id"] == "O-8E718A411378"
    assert len(split["normalized_obligations"]) == 2
    assert set(split["v3_contracts"]) == {
        item["obligation_id"] for item in split["normalized_obligations"]
    }
    assert split["authorizes"] == []


def test_published_v1_split_rejects_wrong_source_binding() -> None:
    bundle = json.loads((PLAN / "semantic-plan-bundle.v1.json").read_text(encoding="utf-8"))
    source = json.loads((PLAN / "source-index.v1.json").read_text(encoding="utf-8"))
    split_path = ROOT / (
        "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/"
        "repair/round-7/recompilation-4/cer-repair-1/published-v1-fr6-split.json"
    )
    value = json.loads(split_path.read_text(encoding="utf-8"))
    value["source_ref"] = value["source_ref"].replace("#FR-6", "#FR-7")
    with tempfile.TemporaryDirectory(dir=ROOT / "logs") as location:
        path = Path(location) / "split.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        with __import__("pytest").raises(ValueError, match="current FR-6"):
            repair.load_v1_split(path, REQUIREMENTS, source, bundle)

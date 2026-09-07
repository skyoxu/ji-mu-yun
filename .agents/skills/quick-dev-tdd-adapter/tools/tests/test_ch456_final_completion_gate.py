from __future__ import annotations

import importlib.util
import json
import pytest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "scripts" / "quick_dev" / "evaluate_final_completion.py"
SPEC = importlib.util.spec_from_file_location("ch456_final_completion", MODULE_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)

RUNNER_MODULE_PATH = ROOT / "scripts" / "quick_dev" / "run_ch456_final_acceptance.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("ch456_final_acceptance_runner", RUNNER_MODULE_PATH)
assert RUNNER_SPEC and RUNNER_SPEC.loader
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(RUNNER)


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return path


def _bound(head: str, **value) -> dict:
    return {**value, "source_head": head}


def _freeze_manifest(args: SimpleNamespace, tmp_path: Path, head: str) -> Path:
    rows = {}
    for key in GATE.EVIDENCE_KEYS:
        path = Path(getattr(args, key)).resolve()
        value = json.loads(path.read_text(encoding="utf-8"))
        rows[key] = {
            "path": str(path),
            "sha256": GATE._sha256(path),
            "schema": value.get("schema"),
            "source_head": value.get("source_head"),
        }
    manifest = _write(
        tmp_path / "manifest.json",
        {
            "schema": GATE.MANIFEST_SCHEMA,
            "candidate_head": head,
            "required_evidence_keys": list(GATE.EVIDENCE_KEYS),
            "evidence": rows,
            "authorizes": [],
        },
    )
    args.manifest = manifest
    return manifest



def _mutation_evidence(*, detached=False) -> dict:
    # ADR-0041: fixtures include actual case dispositions, not a bare pass flag.
    result = dict(threshold_passed=True, baseline_valid=True)
    if detached:
        result.update(structural_mutation_cases=21, structural_rejected_cases=21,
                      structural_rejection_rate=1.0,
                      structural_cases=[{"case": str(i), "rejected": True} for i in range(21)],
                      failure_family_omission_cases=1, failure_family_rejected_cases=1,
                      failure_family_cases=[{"case": "family", "rejected": True}],
                      failure_family_leaks=0, failure_family_leakage_rate=0.0)
    else:
        result.update(mutation_cases=21, rejected_cases=21, rejection_rate=1.0,
                      cases=[{"case": str(i), "rejected": True} for i in range(21)])
    return result


def _args(tmp_path: Path, head: str) -> SimpleNamespace:
    args = SimpleNamespace(
        architecture_reconcile=_write(tmp_path / "architecture.json", _bound(head, schema="architecture.v1", status="pass")),
        curated_semantic=_write(
            tmp_path / "curated.json",
            _bound(
                head,
                schema="curated.v1",
                status="pass",
                precision=1.0,
                required_precision=0.95,
                recall=1.0,
                required_recall=0.95,
                controlled_mutation_rejection_rate=1.0,
            ),
        ),
        semantic_chain_mutations=_write(tmp_path / "semantic-mutations.json", _bound(head, schema="semantic-mutations.v1", **_mutation_evidence())),
        agent_context_mutations=_write(tmp_path / "agent-context.json", _bound(head, schema="agent-context.v1", **_mutation_evidence())),
        real_semantic=_write(
            tmp_path / "real-semantic.json",
            _bound(head, schema="real-semantic.v1", status="pass", execution_attempted=True, execution_succeeded=True),
        ),
        stable_facade=_write(tmp_path / "stable.json", _bound(head, schema="stable.v1", threshold_passed=True)),
        detached_mutations=_write(tmp_path / "detached.json", _bound(head, schema="detached.v1", **_mutation_evidence(detached=True))),
        selective_replay=_write(
            tmp_path / "replay.json",
            _bound(head, schema="replay.v1", status="pass", accuracy=1.0, required_accuracy=0.99, failed_cases=0),
        ),
        live_blind=_write(
            tmp_path / "live.json",
            _bound(head, schema="live.v1", status="pass", execution_attempted=True, product_acceptance_proven=True, under_60_minutes=True),
        ),
        legacy_replay=_write(tmp_path / "legacy.json", _bound(head, schema="legacy.v1", status="pass")),
    )
    _freeze_manifest(args, tmp_path, head)
    return args


def test_strict_gate_passes_only_when_full_live_denominator_passes(tmp_path: Path, monkeypatch) -> None:
    head = "a" * 40
    monkeypatch.setattr(GATE, "_head", lambda: head)
    result = GATE.evaluate(_args(tmp_path, head))
    assert result["status"] == "pass"
    assert result["completion"] == "implementation-work-package-complete"
    assert result["failed_checks"] == []
    assert result["failed_evidence"] == {}
    assert result["checks"]["final_evidence_manifest"] is True
    assert result["checks"]["all_evidence_candidate_binding"] is True
    assert result["checks"]["selective_replay"] is True


def test_environment_blocked_live_evidence_can_never_complete(tmp_path: Path, monkeypatch) -> None:
    head = "b" * 40
    monkeypatch.setattr(GATE, "_head", lambda: head)
    args = _args(tmp_path, head)
    _write(
        args.real_semantic,
        _bound(
            head,
            schema="real-semantic.v1",
            status="environment-blocked",
            execution_attempted=False,
            execution_succeeded=False,
            availability={"backend": "codex-cli", "available": False, "blocking_errors": ["codex executable not found in PATH"]},
        ),
    )
    _write(
        args.live_blind,
        _bound(
            head,
            schema="live.v1",
            status="environment-blocked",
            execution_attempted=False,
            product_acceptance_proven=False,
            under_60_minutes=None,
            backend={"backend": "codex-cli", "available": False, "blocking_errors": ["codex executable not found in PATH"]},
        ),
    )
    _freeze_manifest(args, tmp_path, head)
    result = GATE.evaluate(args)
    assert result["status"] == "blocked"
    assert set(result["failed_checks"]) == {"live_blind_under_60_minutes", "real_semantic_quality"}
    assert result["failed_evidence"]["real_semantic_quality"]["status"] == "environment-blocked"
    assert result["failed_evidence"]["real_semantic_quality"]["backend"]["blocking_errors"] == ["codex executable not found in PATH"]
    assert result["failed_evidence"]["live_blind_under_60_minutes"]["execution_attempted"] is False


def test_failed_live_evidence_exposes_bounded_root_cause(tmp_path: Path, monkeypatch) -> None:
    head = "1" * 40
    monkeypatch.setattr(GATE, "_head", lambda: head)
    args = _args(tmp_path, head)
    _write(
        args.real_semantic,
        _bound(
            head,
            schema="real-semantic.v1",
            status="quality-threshold-failed",
            execution_attempted=True,
            execution_succeeded=False,
            compiler_status="plan-ready",
            compiler_stage="V7",
            precision_threshold_passed=True,
            recall_threshold_passed=False,
            atomic_behavior_floor_passed=True,
            atomic_quality_metrics={"precision": 1.0, "recall": 0.91, "active_obligation_count": 29},
        ),
    )
    _write(
        args.live_blind,
        _bound(
            head,
            schema="live.v1",
            status="worker-failed",
            execution_attempted=True,
            product_acceptance_proven=False,
            under_60_minutes=False,
            elapsed_seconds=42.0,
            final_status=None,
            failure_stage="q2-author-red",
            error="bounded diagnostic",
            backend={"backend": "codex-cli", "available": True},
        ),
    )
    _freeze_manifest(args, tmp_path, head)
    result = GATE.evaluate(args)
    semantic = result["failed_evidence"]["real_semantic_quality"]
    blind = result["failed_evidence"]["live_blind_under_60_minutes"]
    assert semantic["compiler_stage"] == "V7"
    assert semantic["atomic_quality_metrics"]["recall"] == 0.91
    assert blind["failure_stage"] == "q2-author-red"
    assert blind["error"] == "bounded diagnostic"
    assert blind["backend"]["backend"] == "codex-cli"


def test_candidate_binding_drift_blocks_live_evidence(tmp_path: Path, monkeypatch) -> None:
    head = "c" * 40
    monkeypatch.setattr(GATE, "_head", lambda: head)
    args = _args(tmp_path, head)
    live = json.loads(args.live_blind.read_text(encoding="utf-8"))
    live["source_head"] = "d" * 40
    _write(args.live_blind, live)
    real = json.loads(args.real_semantic.read_text(encoding="utf-8"))
    real["source_head"] = "e" * 40
    _write(args.real_semantic, real)
    _freeze_manifest(args, tmp_path, head)
    result = GATE.evaluate(args)
    assert result["status"] == "blocked"
    assert "final_evidence_manifest" in result["failed_checks"]
    assert "all_evidence_candidate_binding" in result["failed_checks"]
    assert "live_blind_candidate_binding" in result["failed_checks"]
    assert "real_semantic_candidate_binding" in result["failed_checks"]
    assert "evidence-candidate-head:live_blind" in result["manifest_findings"]
    assert "evidence-candidate-head:real_semantic" in result["manifest_findings"]


def test_unsealed_deterministic_evidence_is_never_implicitly_promoted(tmp_path: Path, monkeypatch) -> None:
    head = "d" * 40
    monkeypatch.setattr(GATE, "_head", lambda: head)
    args = _args(tmp_path, head)
    curated = json.loads(args.curated_semantic.read_text(encoding="utf-8"))
    curated.pop("source_head")
    _write(args.curated_semantic, curated)
    _freeze_manifest(args, tmp_path, head)
    result = GATE.evaluate(args)
    assert result["status"] == "blocked"
    assert result["checks"]["curated_semantic"] is True
    assert result["checks"]["all_evidence_candidate_binding"] is False
    assert result["checks"]["final_evidence_manifest"] is False
    assert "evidence-unsealed:curated_semantic" in result["manifest_findings"]


def test_stale_or_mutated_deterministic_evidence_breaks_manifest_binding(tmp_path: Path, monkeypatch) -> None:
    head = "e" * 40
    monkeypatch.setattr(GATE, "_head", lambda: head)
    args = _args(tmp_path, head)
    curated = json.loads(args.curated_semantic.read_text(encoding="utf-8"))
    curated["non_authoritative_note"] = "bytes changed after manifest freeze"
    _write(args.curated_semantic, curated)
    result = GATE.evaluate(args)
    assert result["status"] == "blocked"
    assert result["checks"]["curated_semantic"] is True
    assert result["checks"]["all_evidence_candidate_binding"] is True
    assert result["checks"]["final_evidence_manifest"] is False
    assert "manifest-sha256:curated_semantic" in result["manifest_findings"]


def test_selective_replay_uses_status_and_accuracy_contract_not_threshold_field(tmp_path: Path, monkeypatch) -> None:
    head = "f" * 40
    monkeypatch.setattr(GATE, "_head", lambda: head)
    args = _args(tmp_path, head)
    replay = json.loads(args.selective_replay.read_text(encoding="utf-8"))
    assert "threshold_passed" not in replay
    result = GATE.evaluate(args)
    assert result["checks"]["selective_replay"] is True


def test_local_runner_decodes_child_output_without_windows_locale_dependency(monkeypatch) -> None:
    observed = {}

    def fake_run(argv, **kwargs):
        observed.update(kwargs)
        return SimpleNamespace(returncode=1, stdout="semantic → failed", stderr="诊断")

    monkeypatch.setattr(RUNNER.subprocess, "run", fake_run)
    result = RUNNER._run(["python", "child.py"], env={}, label="child")

    assert observed["encoding"] == "utf-8"
    assert observed["errors"] == "replace"
    assert result["stdout_tail"] == "semantic → failed"
    assert result["stderr_tail"] == "诊断"


@pytest.mark.parametrize("key,check,rows_key,count_key,rate_key", [
    ("semantic_chain_mutations", "semantic_chain_mutations", "cases", "rejected_cases", "rejection_rate"),
    ("agent_context_mutations", "agent_context_mutations", "cases", "rejected_cases", "rejection_rate"),
    ("detached_mutations", "detached_anti_false_green", "structural_cases", "structural_rejected_cases", "structural_rejection_rate"),
])
@pytest.mark.parametrize("defect", ["one-leak", "dishonest-summary", "missing-cases"])
def test_critical_mutation_leak_blocks_even_with_valid_manifest(
    tmp_path, monkeypatch, key, check, rows_key, count_key, rate_key, defect
):
    # ADR-0041: exercise the final predicate, not only the metric's threshold.
    head = "9" * 40
    monkeypatch.setattr(GATE, "_head", lambda: head)
    args = _args(tmp_path, head)
    path = getattr(args, key)
    value = json.loads(path.read_text(encoding="utf-8"))
    if defect == "missing-cases":
        value.pop(rows_key)
    else:
        value[rows_key][0]["rejected"] = False
        if defect == "one-leak":
            value[count_key] = 20
            value[rate_key] = 20 / 21
    assert value["threshold_passed"] is True
    _write(path, value)
    _freeze_manifest(args, tmp_path, head)
    result = GATE.evaluate(args)
    assert result["checks"]["final_evidence_manifest"] is True
    assert result["failed_checks"] == [check]
    assert result["completion"] == "not-complete"


def test_detached_family_leak_blocks_despite_structural_success(tmp_path, monkeypatch):
    head = "8" * 40
    monkeypatch.setattr(GATE, "_head", lambda: head)
    args = _args(tmp_path, head)
    value = json.loads(args.detached_mutations.read_text(encoding="utf-8"))
    value["failure_family_cases"][0]["rejected"] = False
    _write(args.detached_mutations, value)
    _freeze_manifest(args, tmp_path, head)
    assert GATE.evaluate(args)["failed_checks"] == ["detached_anti_false_green"]

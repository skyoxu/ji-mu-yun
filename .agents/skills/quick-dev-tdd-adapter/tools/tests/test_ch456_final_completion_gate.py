from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "scripts" / "quick_dev" / "evaluate_final_completion.py"
SPEC = importlib.util.spec_from_file_location("ch456_final_completion", MODULE_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return path


def _args(tmp_path: Path, head: str) -> SimpleNamespace:
    return SimpleNamespace(
        architecture_reconcile=_write(tmp_path / "architecture.json", {"status": "pass"}),
        curated_semantic=_write(
            tmp_path / "curated.json",
            {
                "status": "pass",
                "precision": 1.0,
                "required_precision": 0.95,
                "recall": 1.0,
                "required_recall": 0.95,
                "controlled_mutation_rejection_rate": 1.0,
            },
        ),
        semantic_chain_mutations=_write(tmp_path / "semantic-mutations.json", {"threshold_passed": True}),
        agent_context_mutations=_write(tmp_path / "agent-context.json", {"threshold_passed": True}),
        real_semantic=_write(
            tmp_path / "real-semantic.json",
            {
                "status": "pass",
                "execution_attempted": True,
                "execution_succeeded": True,
                "source_head": head,
            },
        ),
        stable_facade=_write(tmp_path / "stable.json", {"threshold_passed": True}),
        detached_mutations=_write(tmp_path / "detached.json", {"threshold_passed": True}),
        selective_replay=_write(
            tmp_path / "replay.json",
            {"status": "pass", "accuracy": 1.0, "required_accuracy": 0.99, "failed_cases": 0},
        ),
        live_blind=_write(
            tmp_path / "live.json",
            {
                "status": "pass",
                "execution_attempted": True,
                "product_acceptance_proven": True,
                "under_60_minutes": True,
                "source_head": head,
            },
        ),
        legacy_replay=_write(tmp_path / "legacy.json", {"status": "pass"}),
    )


def test_strict_gate_passes_only_when_full_live_denominator_passes(tmp_path: Path, monkeypatch) -> None:
    head = "a" * 40
    monkeypatch.setattr(GATE, "_head", lambda: head)
    result = GATE.evaluate(_args(tmp_path, head))
    assert result["status"] == "pass"
    assert result["completion"] == "implementation-work-package-complete"
    assert result["failed_checks"] == []
    assert result["checks"]["selective_replay"] is True


def test_environment_blocked_live_evidence_can_never_complete(tmp_path: Path, monkeypatch) -> None:
    head = "b" * 40
    monkeypatch.setattr(GATE, "_head", lambda: head)
    args = _args(tmp_path, head)
    _write(
        args.real_semantic,
        {
            "status": "environment-blocked",
            "execution_attempted": False,
            "execution_succeeded": False,
            "source_head": head,
        },
    )
    _write(
        args.live_blind,
        {
            "status": "environment-blocked",
            "execution_attempted": False,
            "product_acceptance_proven": False,
            "under_60_minutes": None,
            "source_head": head,
        },
    )
    result = GATE.evaluate(args)
    assert result["status"] == "blocked"
    assert set(result["failed_checks"]) == {"live_blind_under_60_minutes", "real_semantic_quality"}


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
    result = GATE.evaluate(args)
    assert result["status"] == "blocked"
    assert "live_blind_candidate_binding" in result["failed_checks"]
    assert "real_semantic_candidate_binding" in result["failed_checks"]


def test_selective_replay_uses_status_and_accuracy_contract_not_threshold_field(tmp_path: Path, monkeypatch) -> None:
    head = "f" * 40
    monkeypatch.setattr(GATE, "_head", lambda: head)
    args = _args(tmp_path, head)
    replay = json.loads(args.selective_replay.read_text(encoding="utf-8"))
    assert "threshold_passed" not in replay
    result = GATE.evaluate(args)
    assert result["checks"]["selective_replay"] is True

"""ADR-0041: preserve explicit repair budgets through the formal entry chain."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[5]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/quick_dev" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("budget", [None, 900])
def test_formal_entry_passes_budget_to_both_live_checks(tmp_path, monkeypatch, budget):
    runner = load("budget_final", "run_ch456_final_acceptance.py")
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    calls = {}

    def run(argv, *, env, label):
        calls[label] = argv
        return {"label": label, "argv": argv, "exit_code": 0, "passed": True}

    monkeypatch.setattr(runner, "_run", run)
    monkeypatch.setattr(sys, "argv", ["runner"] + ([] if budget is None else ["--repair-timeout-seconds", str(budget)]))
    assert runner.main() == 0
    for label in ("real-semantic", "live-blind-medium"):
        argv = calls[label]
        if budget is None:
            assert "--repair-timeout-seconds" not in argv
        else:
            assert argv[argv.index("--repair-timeout-seconds") + 1] == "900"
    summary = json.loads((tmp_path / "logs/ch456-final-acceptance/ch456-local-final-acceptance-run.json").read_text())
    assert summary["repair_timeout_seconds_override"] == budget
    assert "strict-final-completion" in calls
    assert "--require-live" in calls["live-blind-medium"]


def test_blind_outer_forwards_override_to_detached_child(tmp_path, monkeypatch):
    runner = load("budget_blind_outer", "run_live_blind_benchmark.py")
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "_git", lambda *a, **kw: SimpleNamespace(stdout="candidate", returncode=0))
    monkeypatch.setattr(runner, "_backend_probe", lambda *a: {"available": True, "backend": "codex-cli"})
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=json.dumps({"schema": runner.SCHEMA, "status": "pass",
                               "repair_timeout_seconds_override": 900}), stderr="")

    monkeypatch.setattr(runner.subprocess, "run", run)
    out = tmp_path / "result.json"
    assert runner._outer(out=out, backend_requested="codex-cli", limit_seconds=3600,
                         require_live=True, repair_timeout_seconds=900) == 0
    assert calls[0][calls[0].index("--repair-timeout-seconds") + 1] == "900"
    assert calls[0][calls[0].index("--limit-seconds") + 1] == "3600"
    assert json.loads(out.read_text())["repair_timeout_seconds_override"] == 900


def test_formal_entry_can_stop_after_first_failed_live_step(tmp_path, monkeypatch):
    runner = load("budget_final_stop", "run_ch456_final_acceptance.py")
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    calls = []

    def run(argv, *, env, label):
        calls.append(label)
        return {"label": label, "passed": label != "real-semantic", "exit_code": int(label == "real-semantic")}

    monkeypatch.setattr(runner, "_run", run)
    monkeypatch.setattr(sys, "argv", ["runner", "--repair-timeout-seconds", "900", "--stop-on-failure"])
    assert runner.main() == 1
    assert calls[-1] == "real-semantic"
    directory = tmp_path / "logs/ch456-final-acceptance"
    result = json.loads((directory / "ch456-local-final-acceptance-run.json").read_text())
    assert result["status"] == "blocked"
    assert result["repair_timeout_seconds_override"] == 900
    assert not (directory / "ch456-final-completion.json").exists()


def test_blind_inner_applies_override_before_compile(monkeypatch, capsys):
    runner = load("budget_blind_inner", "run_live_blind_benchmark.py")
    transport = SimpleNamespace(_REPAIR_TIMEOUT_SECONDS=300)
    monkeypatch.setitem(sys.modules, "semantic_worker_transport_patch", transport)

    def inner(**kwargs):
        assert transport._REPAIR_TIMEOUT_SECONDS == 900
        assert kwargs["limit_seconds"] == 3600
        return {"status": "pass"}

    monkeypatch.setattr(runner, "_inner", inner)
    monkeypatch.setattr(sys, "argv", ["runner", "--inner", "--backend", "codex-cli", "--repair-timeout-seconds", "900"])
    assert runner.main() == 0
    assert json.loads(capsys.readouterr().out)["repair_timeout_seconds_override"] == 900


@pytest.mark.parametrize("filename", ["run_ch456_final_acceptance.py", "run_live_blind_benchmark.py"])
@pytest.mark.parametrize("budget", ["0", "-1"])
def test_invalid_budget_rejected_before_execution(monkeypatch, filename, budget):
    runner = load("budget_invalid", filename)
    monkeypatch.setattr(sys, "argv", ["runner", "--repair-timeout-seconds", budget])
    with pytest.raises(SystemExit) as exc:
        runner.main()
    assert exc.value.code == 2

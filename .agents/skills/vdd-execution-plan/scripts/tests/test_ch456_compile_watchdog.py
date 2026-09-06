"""ADR-0041: compiler hangs terminate with retained non-authoritative progress."""
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parents[3]
for path in (SCRIPTS, ROOT / "scripts/vdd"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
import compiler_watchdog as watchdog
from semantic_progress import worker_call


def test_worker_start_is_durable_before_return_and_exception_is_recorded(tmp_path):
    progress = tmp_path / ".compiler-work/compiler-progress.jsonl"

    def worker(**kwargs):
        rows = [json.loads(line) for line in progress.read_text().splitlines()]
        assert rows[-1]["event"] == "worker-started"
        assert rows[-1]["timeout_seconds"] == 900
        raise RuntimeError("private backend trace")

    with pytest.raises(RuntimeError):
        worker_call(worker, progress_dir=tmp_path, progress_stage="v3-schema-repair",
                    timeout_sec=900, output_last_message=tmp_path / "output.json", backend="test")
    rows = [json.loads(line) for line in progress.read_text().splitlines()]
    assert [r["event"] for r in rows] == ["worker-started", "worker-raised"]
    assert rows[0]["call_id"] == rows[1]["call_id"]
    assert "private backend trace" not in progress.read_text()


def test_global_timeout_stops_child_and_descendant_and_keeps_checkpoint(tmp_path):
    heartbeat = tmp_path / "heartbeat"
    descendant = "import pathlib,time; p=pathlib.Path('heartbeat');\nwhile True:\n p.write_text(str(time.time())); time.sleep(.02)"
    code = ("import sys,time,subprocess; from pathlib import Path; "
            f"sys.path.insert(0,{str(SCRIPTS)!r}); "
            "from semantic_progress import emit; "
            "emit(Path('plan'),'v3-schema-repair','worker-started','blocked'); "
            f"subprocess.Popen([sys.executable,'-c',{descendant!r}]); time.sleep(30)")
    result = watchdog.run_compiler([sys.executable, "-c", code], cwd=tmp_path,
                                   run_dir=tmp_path, timeout_seconds=1)
    assert result["timed_out"] and result["exit_code"] != 0
    assert result["cleanup_error"] is None
    assert result["last_checkpoint"]["stage"] == "v3-schema-repair"
    assert heartbeat.is_file()
    frozen = heartbeat.read_bytes()
    time.sleep(.1)
    assert heartbeat.read_bytes() == frozen
    assert (tmp_path / "watchdog-result.json").is_file()
    assert (tmp_path / "compiler-stdout.log").is_file()


def test_normal_completion_is_not_timeout_and_logs_are_utf8_bytes(tmp_path):
    result = watchdog.run_compiler([sys.executable, "-c", "import sys;sys.stdout.buffer.write('完成'.encode('utf-8'))"],
                                   cwd=tmp_path, run_dir=tmp_path, timeout_seconds=5)
    assert result["exit_code"] == 0 and not result["timed_out"]
    assert (tmp_path / "compiler-stdout.log").read_bytes().decode("utf-8") == "完成"


def test_public_cli_writes_structured_result_and_progress_without_backend(tmp_path):
    from test_ch456_compiler_closure import _cache, _repo
    root, requirements, owner, selector = _repo(tmp_path)
    cache = root / "worker-cache.json"
    cache.write_text(json.dumps(_cache(owner, selector)), encoding="utf-8")
    output = root / "compiler-result.json"
    result = watchdog.run_compiler(
        [sys.executable, str(ROOT / "scripts/vdd/compile_plan.py"),
         "--requirements", str(requirements), "--out-dir", str(root / "plan"),
         "--worker-cache", str(cache), "--result-json", str(output),
         "--repair-timeout-seconds", "900"], cwd=root, run_dir=root, timeout_seconds=10)
    assert result["exit_code"] == 0 and not result["timed_out"]
    assert json.loads(output.read_text())["status"] == "plan-ready"
    records = [json.loads(line) for line in (root / "plan/.compiler-work/compiler-progress.jsonl").read_text().splitlines()]
    assert {"V1", "V3", "V4", "V6"} <= {r["stage"] for r in records}
    assert not any(r["event"].startswith("worker-") for r in records)


def test_windows_cleanup_targets_only_owned_process_tree(monkeypatch):
    calls = []
    monkeypatch.setattr(watchdog.os, "name", "nt")
    monkeypatch.setattr(watchdog.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)) or SimpleNamespace(returncode=0))
    watchdog._terminate_tree(SimpleNamespace(pid=1234))
    assert calls[0][0] == ["taskkill", "/PID", "1234", "/T", "/F"]
    assert calls[0][1]["timeout"] == 10


def test_evaluator_timeout_writes_final_failure_and_retains_run(monkeypatch, tmp_path):
    import evaluate_real_semantic_quality as evaluator
    monkeypatch.setattr(evaluator, "ROOT", tmp_path)
    fixture = tmp_path / "fixture.md"
    fixture.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(evaluator, "FIXTURE", fixture)
    monkeypatch.setattr(evaluator, "_source_head", lambda: "fixed-test-candidate")
    monkeypatch.setattr(evaluator, "resolve_llm_backend", lambda value: "test")
    monkeypatch.setattr(evaluator, "inspect_llm_backend", lambda value: {"available": True})
    entry = tmp_path / "scripts/vdd/compile_plan.py"
    entry.parent.mkdir(parents=True)
    entry.write_text(
        "import sys,time\nfrom pathlib import Path\n"
        f"sys.path.insert(0,{str(SCRIPTS)!r})\nfrom semantic_progress import emit\n"
        "out=Path(sys.argv[sys.argv.index('--out-dir')+1])\n"
        "emit(out,'V1','worker-started','hung')\ntime.sleep(30)\n", encoding="utf-8")
    result = evaluator.evaluate("test", compile_timeout_seconds=1, repair_timeout_seconds=900)
    assert result["status"] == "compile-timeout"
    assert result["compiler_stage"] == "V1"
    assert not result["execution_succeeded"]
    run = Path(result["run_directory"])
    assert json.loads((run / "evaluation-result.json").read_text())["status"] == "compile-timeout"
    assert Path(result["progress_file"]).is_file()
    command = result["watchdog"]["command"]
    assert command[-2:] == ["--repair-timeout-seconds", "900"]


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_invalid_global_budget_is_rejected(value):
    with pytest.raises(ValueError):
        watchdog.positive_timeout(value)

"""ADR-0041: real host transport still passes through native Q2 write guards."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import pytest
TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parents[3] / 'scripts/sc'))
import host_session as host
from worker_orchestrator import run_red_author
spec = importlib.util.spec_from_file_location('host_fixture', Path(__file__).with_name('test_ch456_worker_orchestration.py'))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


@pytest.mark.parametrize('illegal', [False, True])
def test_actual_host_q2_worker_obeys_native_write_set(tmp_path, monkeypatch, illegal):
    plan, semantic, production = fixture._fixture(tmp_path)
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path / '.gitignore').write_text('logs/\n')
    directory = tmp_path / 'logs/session'
    host.initialize(tmp_path, directory, 'test-caller')
    monkeypatch.setenv(host.ENV, str(directory))
    results, errors = [], []
    def run():
        try:
            results.append(run_red_author(workspace=tmp_path, plan_dir=plan,
                semantic_plan=semantic, slice_id='S1', backend='host-session', timeout_seconds=10))
        except Exception as exc:
            errors.append(exc)
    thread = threading.Thread(target=run)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        requests = []
        while not requests and time.monotonic() < deadline:
            requests = host.pending(directory)
            time.sleep(.01)
        assert requests, errors
        request = host.read(Path(requests[0]['request_path']))
        assert request['mode'] == 'workspace-write'
        target = production if illegal else tmp_path / 'tests/test_subject.py'
        target.write_text('def test_subject():\n    assert 1 == 1\n')
        host.respond(directory, request['request_id'], host.digest(request), 'Authored requested file.')
    finally:
        thread.join(12)
    assert not thread.is_alive()
    if illegal:
        assert errors and 'write-set violation' in str(errors[0])
        assert not results
    else:
        assert not errors
        assert results[0]['status'] == 'worker-changes-valid'
        assert results[0]['changed_paths'] == ['tests/test_subject.py']
        assert results[0]['authorizes'] == []

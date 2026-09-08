"""ADR-0041: bounded 8-17 recovery closeout, no live worker calls."""
import json
from pathlib import Path
import pytest
from test_cer_behavior_routing import fixture, execute
from stage_pipeline import execute_stage
from runtime_evidence import load_json, selector_identity_from_descriptor
import case_evidence


def counter(monkeypatch):
    calls = []
    original = case_evidence.run_cases
    def measured(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(case_evidence, 'run_cases', measured)
    return calls


def test_complete_probe_and_regression_reuse_without_execution(tmp_path, monkeypatch):
    semantic, _ = fixture(tmp_path)
    calls = counter(monkeypatch)
    probe = execute(tmp_path, semantic, 'probe')
    assert execute(tmp_path, semantic, 'probe') == probe
    regression = execute(tmp_path, semantic, 'regression', probe)
    assert execute(tmp_path, semantic, 'regression', probe) == regression
    assert len(calls) == 2


@pytest.mark.parametrize('mutation', ['partial', 'stdout', 'candidate', 'plan', 'seal'])
def test_stale_or_partial_evidence_stops_before_process(tmp_path, monkeypatch, mutation):
    semantic, _ = fixture(tmp_path)
    calls = counter(monkeypatch)
    if mutation == 'partial':
        execute(tmp_path, semantic, 'probe', materialize_only=True)
        evidence = tmp_path / 'RUN-1/canonical-evidence/probe'
        evidence.mkdir(parents=True)
        (evidence / 'stdout.bin').write_bytes(b'interrupted')
    else:
        execute(tmp_path, semantic, 'probe')
        if mutation == 'stdout':
            (tmp_path / 'RUN-1/canonical-evidence/probe/stdout.bin').write_bytes(b'changed')
        elif mutation == 'candidate':
            (tmp_path / 'candidate.py').write_text('def value(kind): return 0\n')
        elif mutation == 'plan':
            bundle = load_json(semantic); bundle['plan_id'] = 'CHANGED'
            semantic.write_text(json.dumps(bundle))
        else:
            (tmp_path / 'RUN-1/canonical-evidence/probe/execution-complete.v1.json').unlink()
    before = len(calls)
    with pytest.raises(ValueError, match='stage-reentry-blocked'):
        execute_stage(workspace=tmp_path, semantic_plan=semantic, run_dir=tmp_path/'RUN-1',
                      descriptor_path=tmp_path/'RUN-1/descriptors/probe.json', profile_identity='standard')
    assert len(calls) == before


@pytest.mark.parametrize('stage', ['probe', 'red', 'green', 'refactor', 'regression', 'terminal'])
def test_each_stage_honors_explicit_history_before_execution(tmp_path, monkeypatch, stage):
    semantic, _ = fixture(tmp_path)
    descriptor = execute(tmp_path, semantic, 'probe', materialize_only=True)
    descriptor['stage'] = stage
    path = tmp_path/'RUN-1/descriptors'/f'{stage}.json'
    path.write_text(json.dumps(descriptor))
    row = {'failure_fingerprint': 'sha256:'+'a'*64, 'candidate_hash': descriptor['candidate_hash'],
           'selector_identity': selector_identity_from_descriptor(descriptor)}
    calls = counter(monkeypatch)
    result = execute_stage(workspace=tmp_path, semantic_plan=semantic, run_dir=tmp_path/'RUN-1',
        descriptor_path=path, profile_identity='standard', failure_history=[row, row])
    assert result['status'] == 'blocked' and result['process_attempts'] == 0
    assert calls == []


def test_refactor_reentry_does_not_call_worker(tmp_path, monkeypatch):
    import stable_runner
    from test_cer_behavior_routing import implement
    semantic, _ = fixture(tmp_path, (False, False))
    route = execute(tmp_path, semantic, 'probe')
    execute(tmp_path, semantic, 'red', route)
    implement(tmp_path, (True, True))
    execute(tmp_path, semantic, 'green', route)
    result = execute(tmp_path, semantic, 'refactor', route)
    monkeypatch.setattr(stable_runner, 'ROOT', tmp_path)
    def forbidden(**kwargs):
        raise AssertionError('worker must not run on reentry')
    monkeypatch.setattr(stable_runner, 'run_refactor_worker', forbidden)
    calls = counter(monkeypatch)
    resumed = stable_runner.q6_refactor_worker_and_run(semantic=semantic, slice_id='S1', run_dir=tmp_path/'RUN-1', profile='standard', timeout_seconds=1, backend=None)
    assert resumed['stage_result'] == result and calls == []
    assert resumed['required_next_action'] == 'validate-slice'


@pytest.mark.parametrize('stage', ['probe', 'red', 'green', 'regression', 'terminal'])
def test_named_cli_stage_honors_failure_history(tmp_path, monkeypatch, capsys, stage):
    import sys
    import stable_runner
    semantic, _ = fixture(tmp_path)
    descriptor = execute(tmp_path, semantic, 'probe', materialize_only=True)
    descriptor['stage'] = stage
    (tmp_path/'RUN-1/descriptors'/f'{stage}.json').write_text(json.dumps(descriptor))
    row = {'failure_fingerprint': 'sha256:'+'a'*64, 'candidate_hash': descriptor['candidate_hash'],
           'selector_identity': selector_identity_from_descriptor(descriptor)}
    history = tmp_path/'history.json'; history.write_text(json.dumps([row, row]))
    monkeypatch.setattr(stable_runner, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['run', '--plan', str(semantic.parent), '--slice', 'S1',
        '--action', 'run-'+stage, '--run-dir', str(tmp_path/'RUN-1'), '--failure-history', str(history)])
    calls = counter(monkeypatch)
    assert stable_runner.main() == 0
    assert json.loads(capsys.readouterr().out)['failure_family'] == 'repeated-deterministic-failure'
    assert calls == []

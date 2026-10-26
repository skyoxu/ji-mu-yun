"""ADR-0041: narrow transport metadata boundary; no business/model workflow."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import shared_execution
from runtime_evidence import create_json, sha256_value


def test_only_call_metadata_change_keeps_candidate_environment(monkeypatch):
    monkeypatch.setenv('CODEX_TOOL_CALL_ID', 'first-tool-call')
    first = shared_execution.execution_environment()
    monkeypatch.setenv('CODEX_TOOL_CALL_ID', 'second-tool-call')
    second = shared_execution.execution_environment()
    assert sha256_value(first) == sha256_value(second)
    assert 'CODEX_TOOL_CALL_ID' not in second
    assert os.environ['CODEX_TOOL_CALL_ID'] == 'second-tool-call'
    monkeypatch.delenv('CODEX_TOOL_CALL_ID')
    assert sha256_value(shared_execution.execution_environment()) == sha256_value(first)


@pytest.mark.parametrize('name', [
    'PATH', 'PYTHONPATH', 'HTTPS_PROXY', 'GIT_CONFIG_NOSYSTEM',
    'CODEX_UNKNOWN_SETTING', 'JIMUYUN_QUERY_LIMIT', 'UNRECOGNIZED_TEST_INPUT',
])
def test_nontransport_environment_changes_and_presence_remain_bound(monkeypatch, name):
    monkeypatch.delenv(name, raising=False)
    absent = sha256_value(shared_execution.execution_environment())
    monkeypatch.setenv(name, '')
    empty = sha256_value(shared_execution.execution_environment())
    monkeypatch.setenv(name, 'fixture-value-one')
    first = sha256_value(shared_execution.execution_environment())
    monkeypatch.setenv(name, 'fixture-value-two')
    second = sha256_value(shared_execution.execution_environment())
    assert len({absent, empty, first, second}) == 4
    assert shared_execution.execution_environment()[name] == 'fixture-value-two'
    monkeypatch.delenv(name)
    assert sha256_value(shared_execution.execution_environment()) == absent


def test_independent_processes_use_the_same_normalized_capture():
    script = (
        'import json,sys; sys.path.insert(0,sys.argv[1]); '
        'from shared_execution import execution_environment; '
        'from runtime_evidence import sha256_value; '
        'env=execution_environment(); '
        'print(json.dumps({"hash":sha256_value(env),'
        '"metadata_visible":"CODEX_TOOL_CALL_ID" in env}))'
    )
    observations = []
    for call_id, meaningful in [('first-call', 'same'), ('second-call', 'same'), ('third-call', 'changed')]:
        env = {**os.environ, 'CODEX_TOOL_CALL_ID': call_id, 'RETAINED_TEST_INPUT': meaningful}
        result = subprocess.run([sys.executable, '-B', '-c', script, str(TOOLS)],
                                env=env, capture_output=True, text=True, check=True, timeout=10)
        observations.append(json.loads(result.stdout))
    assert observations[0] == observations[1]
    assert observations[2]['hash'] != observations[0]['hash']
    assert all(not row['metadata_visible'] for row in observations)


@pytest.mark.parametrize('old_schema', [None, 'quick-dev.pytest-environment.v1', 'unknown-future-schema'])
def test_aggregate_only_or_unknown_schema_is_not_upgraded(tmp_path, monkeypatch, old_schema):
    current = {'schema': 'quick-dev.pytest-environment.v2', 'environment': 'sha256:' + 'a' * 64}
    old = deepcopy(current)
    if old_schema is None:
        old.pop('schema')
    else:
        old['schema'] = old_schema
    original, now = {'environment': old}, {'environment': current}
    # Even identical aggregate digests cannot establish the old filtering rule.
    assert shared_execution.invalidation_reason(original, now) == 'reuse-environment-schema-incompatible'
    assert shared_execution.invalidation_reason(now, now) is None

    semantic = tmp_path / 'plan.json'
    create_json(semantic, {'slices': []})
    evidence = tmp_path / 'evidence'
    descriptor = {'stage': 'regression'}
    receipt = {'profile_identity': 'standard'}
    request = {'descriptor_sha256': sha256_value(descriptor), 'profile': 'standard',
               'input': original, 'semantic_plan': 'plan.json'}
    create_json(evidence / 'reuse-request.v1.json', request)
    create_json(evidence / 'reuse-complete.v1.json',
                {'receipt_sha256': sha256_value(receipt), 'request_sha256': sha256_value(request)})
    prior_bytes = (evidence / 'reuse-request.v1.json').read_bytes()
    monkeypatch.setattr(shared_execution, 'input_manifest', lambda *args: now)
    with pytest.raises(ValueError, match='reuse-environment-schema-incompatible'):
        shared_execution.validate_saved_request(tmp_path, evidence, descriptor, receipt)
    assert (evidence / 'reuse-request.v1.json').read_bytes() == prior_bytes


def test_actual_pytest_child_and_reference_share_metadata_boundary(tmp_path, monkeypatch):
    from test_shared_execution import setup, measured, run, descriptor
    semantic, bundle, _ = setup(tmp_path)
    # The actual native collector must receive the same environment that was
    # fingerprinted. This child assertion would fail if only hashing filtered it.
    with (tmp_path / 'tests/test_one.py').open('a', encoding='utf-8') as stream:
        stream.write('\ndef test_transport_is_not_a_test_input():\n import os\n assert "CODEX_TOOL_CALL_ID" not in os.environ\n')
    calls = measured(monkeypatch)
    monkeypatch.setenv('CODEX_TOOL_CALL_ID', 'original-call')
    original = run(tmp_path, semantic, bundle, descriptor(bundle))
    assert original['exit_code'] == 0
    monkeypatch.setenv('CODEX_TOOL_CALL_ID', 'later-terminal-call')
    terminal = descriptor(bundle, 'S2', 'terminal', 'later')
    reference = run(tmp_path, semantic, bundle, terminal)
    assert len(calls) == 1 and reference['process_attempts'] == 0
    assert reference['case_report'] == original['case_report']
    monkeypatch.setenv('CODEX_TOOL_CALL_ID', 'later-validation-call')
    assert shared_execution.validate_use(terminal, reference)['run_id'] == 'run1'
    current = shared_execution.environment_identity()
    assert current['schema'] == 'quick-dev.pytest-environment.v2'

"""ADR-0041: execution failures must not purchase another semantic review."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import types
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import semantic_compiler_authority as authority
# Capture real entrypoints before tests install temporary compiler functions.
import semantic_v3_contract_repair  # noqa: F401
import semantic_compiler as sc
import semantic_compiler_gate as gate
import semantic_worker_transport_patch as transport
from semantic_worker_errors import WorkerTransportError
from execution_preflight import inspect_candidate, check_candidate
from execution_contract import ownerless_guard
from test_ch456_v3_total_coverage_and_slice_cohesion import _obligation, _acceptance, _hint


def candidate(root):
    (root/'src').mkdir(exist_ok=True)
    (root/'src/ledger.py').write_text('value = 0\n', encoding='utf-8')
    obligation = _obligation('O-1')
    acceptance = _acceptance('O-1', 'A-1')
    failure = {'failure_intent_id': 'FI-O-1', 'failure_id': 'F-1', 'failure_family': 'expected-red',
               'acceptance_ids': ['A-1'], 'selector_intent': 'tests/test_ledger.py::test_write', 'expected_outcome': 'fail'}
    hint = {**_hint('tests/test_ledger.py'), 'obligation_ids': ['O-1']}
    hint.update(gate._preflight_contract(hint))
    acceptance.update(gate._preflight_contract(hint))
    return [obligation], [acceptance], [failure], [hint]


def test_preview_is_pure_and_checks_projected_contract(tmp_path):
    inputs = candidate(tmp_path)
    before = deepcopy(inputs)
    assert inspect_candidate(sc, tmp_path, *inputs)['valid']
    assert inputs == before
    inputs[3][0]['allowed_write_paths'].remove('src/ledger.py')
    result = inspect_candidate(sc, tmp_path, *inputs)
    assert not result['valid']
    assert any('owner-outside-write-set' in f for f in result['findings'])


def test_first_use_is_early_non_authorizing_consumer_warning(tmp_path):
    inputs = candidate(tmp_path)
    (tmp_path/'src/ledger.py').unlink()
    inputs[3][0]['planned_new_files'].append('src/ledger.py')
    args = (sc, tmp_path, tmp_path/'out', {'sha256': 'sha256:source'}, *inputs)
    result = check_candidate(*args)
    assert result['valid'] and result['authorizes'] == []
    assert result['consumer_warnings'][0]['code'] == 'planned-production-first-use'
    assert not (tmp_path/'src/ledger.py').exists()
    assert not (tmp_path/'out/compiler-state.v1.json').exists()
    diagnostic = tmp_path/'out'/result['diagnostic']['path']
    previous = diagnostic.read_bytes()
    assert check_candidate(*args) == result
    assert diagnostic.read_bytes() == previous


def test_authority_stops_before_v4_when_execution_is_invalid(tmp_path, monkeypatch):
    inputs = candidate(tmp_path)
    inputs[3][0]['allowed_write_paths'] = ['tests/test_ledger.py']
    monkeypatch.setattr(sc, 'repository_root', lambda _: tmp_path)
    monkeypatch.setattr(sc, 'build_source_index', lambda *args: {'sha256': 'sha256:source'})
    monkeypatch.setattr(sc, 'source_preflight', lambda *args: {'valid': True})
    monkeypatch.setattr(sc, 'compile_obligations', lambda **kwargs: inputs[0])
    monkeypatch.setattr(sc, 'guard_obligations', lambda *args: {'valid': True})
    monkeypatch.setattr(sc, 'compile_acceptances', lambda **kwargs: inputs[1:])
    monkeypatch.setattr(gate, 'atomic_recall_alignment', lambda **kwargs: pytest.fail('V4 must not run'))
    monkeypatch.setattr(gate, '_ORIGINAL_COMPILE_PLAN', lambda **kwargs: pytest.fail('no publication'))
    # The test supplies the candidate seam after ordinary overlay reset.
    monkeypatch.setattr(semantic_v3_contract_repair, 'reset_published_overlays', lambda: None)
    result = authority.compile_plan(requirements=tmp_path/'req.md', out_dir=tmp_path/'out')
    assert result['stage'] == 'V3-execution-preflight'
    assert result['status'] == 'repair-vdd' and result['repair_class'] == 'execution-contract'
    assert not (tmp_path/'out/compiler-state.v1.json').exists()


def test_ownerless_guard_has_same_kind_rule_at_v3_and_final(tmp_path):
    from semantic_worker_v3_execution_contract_patch import _findings
    from semantic_plan_contract import validate_semantic_bundle
    from test_semantic_plan_contract import _bundle
    bundle = _bundle()
    item = bundle['slices'][0]
    item.update(production_owners=[], allowed_write_paths=['tests/test_one.py'],
                execution_snapshot_paths=['tests/test_one.py'], planned_new_files=['tests/test_one.py'])
    item['rollback_scope']['production_paths'] = []
    obligation = bundle['obligations'][0]
    failure = bundle['failure_intents'][0]
    failure['failure_family'] = 'semantic-contract-gap'
    obligation['obligation_kind'] = 'constraint'
    raw = {'slice_hints': [item], 'acceptances': bundle['acceptances'],
           'failure_intents': [{**failure, 'obligation_ids': ['O-ONE']}]}
    assert ownerless_guard(item, [obligation], [failure])
    assert _findings(tmp_path, 'v3', {'obligations': [obligation]}, raw) == []
    assert validate_semantic_bundle(bundle)[0]
    obligation['obligation_kind'] = 'behavior'
    assert any('unowned-production' in f for f in _findings(tmp_path, 'v3', {'obligations': [obligation]}, raw))
    assert any('unowned-production' in f for f in validate_semantic_bundle(bundle)[1])


def test_selector_file_identity_and_conditional_failure_prose(tmp_path):
    inputs = candidate(tmp_path)
    inputs[3][0]['execution_snapshot_paths'] = ['tests/test_ledger.py::test_write']
    slices, by_a = sc.partition_slices(*inputs)
    inputs[2][0]['selector_intent'] = 'Raise AssertionError if the actual ledger violates the required state'
    assert sc.feasibility(tmp_path, slices, inputs[1], inputs[2], by_a)['valid']
    inputs[2][0]['selector_intent'] = 'assert false'
    assert not sc.feasibility(tmp_path, slices, inputs[1], inputs[2], by_a)['valid']


@pytest.mark.parametrize('code,trace,category,count', [
    (1, 'Error loading config.toml: invalid transport', 'environment', 1),
    (1, 'Error code: 403 request_forbidden', 'environment', 1),
    (124, 'timeout', 'timeout', 1), (130, 'cancelled', 'cancelled', 1),
    (1, 'unknown worker failure', 'unknown', 1),
    (1, 'Error code: 503 service unavailable', 'transient-exhausted', 3),
])
def test_transport_errors_do_not_enter_schema_repair(tmp_path, monkeypatch, code, trace, category, count):
    calls = []
    def run(**kwargs):
        calls.append(kwargs)
        return code, trace, ['codex', 'exec']
    monkeypatch.setitem(sys.modules, '_llm_backend', types.SimpleNamespace(
        resolve_llm_backend=lambda _: 'codex-cli', run_llm_exec=run))
    with pytest.raises(WorkerTransportError) as caught:
        gate.normative_invoke_worker(root=tmp_path, out_dir=tmp_path/'out', stage='v1-FR-1',
                                     payload={'source': 'A requirement'}, prompt='Compile.')
    assert caught.value.category == category
    assert len(calls) == count
    assert not any('SCHEMA REPAIR' in c['prompt'] for c in calls)


def test_malformed_success_still_has_one_schema_repair(tmp_path, monkeypatch):
    calls = []
    valid = {'obligations': [_obligation('O-1')]}
    def invoke(**kwargs):
        calls.append(kwargs['stage'])
        if len(calls) == 1:
            raise ValueError('malformed JSON')
        return valid
    monkeypatch.setattr(gate, '_ORIGINAL_INVOKE_WORKER', invoke)
    monkeypatch.setattr(gate, '_worker_schema_findings', lambda *args: [])
    monkeypatch.setattr(gate, '_source_binding_findings', lambda *args: [])
    assert gate.normative_invoke_worker(root=tmp_path, out_dir=tmp_path/'out', stage='v1-FR-1',
                                       payload={}, prompt='Compile.') == valid
    assert calls == ['v1-FR-1', 'v1-FR-1-schema-repair']


@pytest.mark.parametrize('valid', [True, False])
def test_public_cli_preserves_semantic_gates_and_rejects_invalid_execution_early(tmp_path, valid):
    from test_semantic_compiler_ch456 import _repo, _worker_cache
    root, req, owner, selector = _repo(tmp_path)
    cache = _worker_cache('req.md#FR-1', owner, selector)
    if not valid:
        cache['v3']['slice_hints'][0]['execution_snapshot_paths'].append(owner)
        # V1 source recall is retained; Acceptance alignment must not run.
        del cache['v4']
    cache_path = root/'workers.json'
    cache_path.write_text(json.dumps(cache), encoding='utf-8')
    repository = Path(__file__).resolve().parents[5]
    result_path = root/'result.json'
    process = subprocess.run([sys.executable, '-B', str(repository/'scripts/vdd/compile_plan.py'),
               '--requirements', str(req), '--out-dir', str(root/'out'),
               '--worker-cache', str(cache_path), '--result-json', str(result_path)],
               cwd=repository, capture_output=True, text=True, timeout=20)
    assert process.returncode == (0 if valid else 1), process.stdout + process.stderr
    result = json.loads(result_path.read_text())
    progress = (root/'out/.compiler-work/compiler-progress.jsonl').read_text()
    if valid:
        assert result['status'] == 'plan-ready' and result['execution_preflight']['valid']
        assert result['atomic_quality_metrics']['recall'] == 1
        assert 'V4' in progress and 'final-validation' in progress
    else:
        assert result['stage'] == 'V3-execution-preflight', result
        assert any('production-frozen-by-execution-snapshot' in f for f in result['findings'])
        assert 'V4' not in progress
    assert (root/'out/compiler-state.v1.json').exists() == valid


@pytest.mark.parametrize('route', ['v3-group', 'v4-domain', 'v4-source-gap'])
@pytest.mark.parametrize('backend,code', [('codex-cli', 1), ('codex-cli', 124), ('host-session', 130)])
def test_specialized_workers_share_stop_policy(tmp_path, monkeypatch, route, backend, code):
    import semantic_worker_v3_group_repair_patch as grouped
    import semantic_worker_v4_domain_patch as v4
    from test_ch456_v3_inline_context_repair import _inline, _refs, _obligation as group_obligation
    from test_ch456_v4_atomic_recall_domain import _payload
    calls = []
    def run(**kwargs):
        calls.append(kwargs)
        kwargs['output_last_message'].write_text('{"partial":true}', encoding='utf-8')
        return code, 'Error loading config.toml: invalid transport' if code == 1 else 'stopped', []
    monkeypatch.setitem(sys.modules, '_llm_backend', types.SimpleNamespace(
        resolve_llm_backend=lambda _: backend, run_llm_exec=run))
    expected = transport.HostWorkerStopped if backend == 'host-session' else WorkerTransportError
    with pytest.raises(expected):
        if route == 'v3-group':
            raw = _inline(2)
            grouped._live_group_repair(root=tmp_path, out_dir=tmp_path/'out', prompt='Repair.',
                payload={'input': {'obligations': [group_obligation(oid) for oid in _refs(raw)]}})
        elif route == 'v4-domain':
            v4.v4_transport_invoke_worker(root=tmp_path, out_dir=tmp_path/'out',
                stage='v4-atomic-recall', payload=_payload(), prompt='Review.')
        else:
            v4._invoke_source_gap_chunk(root=tmp_path, out_dir=tmp_path/'out',
                stage='v4-source-gap-chunk-01', payload={}, refs=['req.md#FR-1'], worker_cache=None)
    assert len(calls) == 1
    assert not list((tmp_path/'out/.compiler-cache').glob('*.json'))

"""ADR-0041: partial obligation cases retain native RED/GREEN/Q7/Q8 proof."""
import json
from pathlib import Path
import pytest
from test_cer_behavior_routing import fixture, execute, close, implement
from runtime_evidence import sha256_value


def partial(root):
    semantic, roots = fixture(root, (False, True))
    path = root / 'tests/test_one.py'
    path.write_text(path.read_text() + "@pytest.mark.cer_assertion('AS-1')\ndef test_already_present():\n actual=value(2)\n if actual!=2: print('FAILURE_ID:FAIL-1')\n assert actual==2\n", encoding='utf-8')
    return semantic, roots


def test_partial_obligation_closes_native_lifecycle(tmp_path):
    semantic, roots = partial(tmp_path)
    route = execute(tmp_path, semantic, 'probe')
    assert route['predicate_result']
    row = route['behavior_dispositions'][0]
    assert row['disposition'] == 'missing'
    assert {c['outcome'] for c in row['case_outcomes']} == {'passed', 'failed'}
    assert execute(tmp_path, semantic, 'red', route)['predicate_result']
    implement(tmp_path, (True, True))
    for stage in ('green', 'refactor', 'regression'):
        assert execute(tmp_path, semantic, stage, route)['predicate_result']
    assert close(tmp_path, semantic, roots, route)['status'] == 'pass'


@pytest.mark.parametrize('failure', ['skip', 'harness', 'wrong-id'])
def test_partial_unverifiable_cases_remain_blocking(tmp_path, failure):
    semantic, _ = partial(tmp_path)
    path = tmp_path / 'tests/test_one.py'
    source = path.read_text()
    if failure == 'skip':
        source = source.replace('def test_already_present', "@pytest.mark.skip(reason='missing')\ndef test_already_present")
    elif failure == 'harness':
        source = source.replace('assert actual==2', "raise RuntimeError('harness')")
    else:
        source = source.replace('FAILURE_ID:FAIL-1', 'FAILURE_ID:UNDECLARED')
    path.write_text(source, encoding='utf-8')
    assert not execute(tmp_path, semantic, 'probe')['predicate_result']


def test_passing_case_must_remain_green(tmp_path):
    semantic, _ = partial(tmp_path)
    route = execute(tmp_path, semantic, 'probe')
    assert execute(tmp_path, semantic, 'red', route)['predicate_result']
    implement(tmp_path, (True, False))
    assert not execute(tmp_path, semantic, 'green', route)['predicate_result']


def test_formal_red_preserves_partial_case_outcomes(tmp_path):
    semantic, _ = partial(tmp_path)
    route = execute(tmp_path, semantic, 'probe')
    descriptor = execute(tmp_path, semantic, 'red', route, materialize_only=True)
    from case_evidence import run_cases
    from behavior_routing import verify_case_continuity
    from runtime_evidence import sha256_bytes
    process, report, error, _ = run_cases(descriptor, tmp_path)
    receipt = {'case_report': report, 'case_report_error': error, 'exit_code': process.returncode,
        'case_report_sha256': sha256_value(report),
        'target_hashes': {'tests/test_one.py': sha256_bytes((tmp_path/'tests/test_one.py').read_bytes())}}
    verify_case_continuity(descriptor, receipt, route)
    calls = [e for e in report['events'] if e['phase'] == 'call' and 'test_value_2' not in e['node_id']]
    passed, failed = next(e for e in calls if e['outcome']=='passed'), next(e for e in calls if e['outcome']=='failed')
    for key in ('outcome', 'failure_ids', 'assertion_failure'):
        passed[key], failed[key] = failed.get(key), passed.get(key)
    receipt['case_report_sha256'] = sha256_value(report)
    with pytest.raises(ValueError, match='outcome-drift'):
        verify_case_continuity(descriptor, receipt, route)


def test_uniform_probe_cannot_become_partial_red(tmp_path):
    semantic, _ = fixture(tmp_path, (False, True))
    path = tmp_path/'tests/test_one.py'
    path.write_text(path.read_text()+"@pytest.mark.cer_assertion('AS-1')\ndef test_extra():\n print('FAILURE_ID:FAIL-1')\n assert False\n",encoding='utf-8')
    route=execute(tmp_path,semantic,'probe')
    assert 'case_outcomes' not in route['behavior_dispositions'][0]
    descriptor=execute(tmp_path,semantic,'red',route,materialize_only=True)
    from case_evidence import run_cases
    from behavior_routing import verify_case_continuity
    from runtime_evidence import sha256_bytes
    process,report,error,_=run_cases(descriptor,tmp_path)
    receipt={'case_report':report,'case_report_error':error,'exit_code':process.returncode,
      'case_report_sha256':sha256_value(report),'target_hashes':{'tests/test_one.py':sha256_bytes(path.read_bytes())}}
    call=next(e for e in report['events'] if e['phase']=='call' and 'test_extra' in e['node_id'])
    call.update(outcome='passed',failure_ids=[],assertion_failure=False)
    receipt['case_report_sha256']=sha256_value(report)
    with pytest.raises(ValueError,match='outcome-drift'):
        verify_case_continuity(descriptor,receipt,route)


def test_passing_only_assertion_adds_no_red_failure_id(tmp_path):
    semantic, roots = fixture(tmp_path, (False, True))
    bundle = json.loads(semantic.read_text())
    # Both acceptances belong to one obligation, but only A-1 fails at probe.
    bundle['obligations'] = bundle['obligations'][:1]
    bundle['acceptances'][1]['obligation_ids'] = ['O-1']
    for item in bundle['slices'] + bundle['agent_contexts']:
        item['obligation_ids'] = ['O-1']
    bundle['final_plan_coverage'][1]['obligation_id'] = 'O-1'
    from semantic_behavior_contract import project_intents
    bundle['behavior_routing']['intents'] = project_intents(bundle)
    semantic.write_text(json.dumps(bundle), encoding='utf-8')
    route = execute(tmp_path, semantic, 'probe')
    assert route['predicate_result']
    descriptor = execute(tmp_path, semantic, 'red', route, materialize_only=True)
    from behavior_routing import red_failure_ids
    assert red_failure_ids(descriptor, route) == ['FAIL-1']
    assert execute(tmp_path, semantic, 'red', route)['predicate_result']
    implement(tmp_path, (True, True))
    for stage in ('green', 'refactor'):
        assert execute(tmp_path, semantic, stage, route)['predicate_result']
    assert close(tmp_path, semantic, roots, route)['status'] == 'pass'

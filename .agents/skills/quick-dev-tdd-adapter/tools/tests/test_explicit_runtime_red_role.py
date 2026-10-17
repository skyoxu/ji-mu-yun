"""ADR-0041: machine failure roles are distinct from Governance categories."""
import json
from pathlib import Path
import sys
import pytest
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / '.agents/skills/vdd-execution-plan/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from quick_dev_handoff import repair_runtime_red_roles, semantic_projection
from test_cer_behavior_routing import fixture, execute
from semantic_behavior_contract import project_intents
from semantic_chain_audit import audit_bundle
from semantic_plan_contract import validate_semantic_bundle
from case_evidence import contract_for
PLAN = ROOT / 'execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/recompilation-4/cer-repair-1/quick-dev-ready/current-plan/semantic-plan-bundle.v1.json'


def test_real_s1_preserves_other_slices_and_binds_original_marker():
    before = json.loads(PLAN.read_text(encoding='utf-8'))
    after, report = repair_runtime_red_roles(before, ['FI-6AED86AC07D0'])
    assert semantic_projection(before) == semantic_projection(after)
    assert report['affected_slices'] == ['S1']
    for key in ['slices', 'agent_contexts']:
        assert [s for s in before[key] if s['slice_id'] != 'S1'] == [s for s in after[key] if s['slice_id'] != 'S1']
    assert all(f in after['failure_intents'] for f in before['failure_intents'])
    assert validate_semantic_bundle(after) == (True, [])
    assert audit_bundle(after)['valid']
    rows = [{'acceptance_id': 'A-7B64D58A9EDB', 'assertion_id': 'FR-3-candidate-external-trust-independent-verification'}]
    assert contract_for(before, rows)['bindings'][0]['expected_failure_ids'] == []
    assert contract_for(after, rows)['bindings'][0]['expected_failure_ids'] == ['UNVERIFIED-CANDIDATE-EXTERNAL-TRUST-REJECTED']


def _governance_fixture(tmp_path):
    semantic, _ = fixture(tmp_path, present=(False, True))
    bundle = json.loads(semantic.read_text())
    bundle['obligations'][0].update(requirement_type='Governance', obligation_kind='governance')
    bundle['failure_intents'][0]['failure_family'] = 'target-binding-failure'
    bundle['acceptances'][0]['verification_lane'] = 'unit'
    bundle['slices'][0]['proof'] = {'assertion_ids': ['AS-1', 'AS-2'], 'selector_intents': ['tests/test_one.py']}
    bundle['slices'][0]['planned_new_files'] = []
    bundle['slices'][0]['verification_lane'] = 'unit'
    for o in bundle['obligations']:
        o['requirement_id'] = 'FR-1'
    bundle['behavior_routing']['intents'] = project_intents(bundle)
    semantic.write_text(json.dumps(bundle), encoding='utf-8')
    return semantic, bundle


def test_failing_call_becomes_missing_only_after_explicit_binding(tmp_path):
    semantic, before = _governance_fixture(tmp_path)
    result = execute(tmp_path, semantic, 'probe', run_name='BEFORE')
    assert result['behavior_dispositions'][0]['disposition'] == 'unverifiable'
    after, _ = repair_runtime_red_roles(before, ['FI-1'])
    semantic.write_text(json.dumps(after), encoding='utf-8')
    result = execute(tmp_path, semantic, 'probe', run_name='AFTER')
    assert [r['disposition'] for r in result['behavior_dispositions']] == ['missing', 'present']
    assert result['predicate_result'] is True
    red = execute(tmp_path, semantic, 'red', result, run_name='AFTER')
    assert red['predicate_result'] is True and red['failure_family'] == 'expected-red'


@pytest.mark.parametrize('fault', ['wrong-marker', 'setup', 'runtime-error'])
def test_mapping_does_not_authorize_nonbehavior_failure(tmp_path, fault):
    semantic, before = _governance_fixture(tmp_path)
    after, _ = repair_runtime_red_roles(before, ['FI-1'])
    semantic.write_text(json.dumps(after), encoding='utf-8')
    path = tmp_path / 'tests/test_one.py'
    text = path.read_text()
    if fault == 'wrong-marker':
        text = text.replace('FAILURE_ID:FAIL-1', 'FAILURE_ID:WRONG')
    elif fault == 'setup':
        text += "\n@pytest.fixture(autouse=True)\ndef broken_setup():\n print('FAILURE_ID:FAIL-1')\n raise RuntimeError('setup failed')\n"
    else:
        text = text.replace('assert actual==1', "raise RuntimeError('not a behavioral assertion')")
    path.write_text(text, encoding='utf-8')
    result = execute(tmp_path, semantic, 'probe')
    assert result['predicate_result'] is False
    assert result['behavior_dispositions'][0]['disposition'] == 'unverifiable'


def test_unknown_intent_fails_closed():
    with pytest.raises(ValueError, match='unknown failure intent'):
        repair_runtime_red_roles(json.loads(PLAN.read_text(encoding='utf-8')), ['FI-UNKNOWN'])

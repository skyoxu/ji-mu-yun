"""ADR-0041: atomic source-bound repair is not tied to one old FR label."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'scripts/vdd'))
from compile_plan import semantic_compiler
import semantic_v3_contract_repair as repair

BASE = ROOT / 'execution-plans/2026-08-06-skill-authoring-standard'
INPUT = BASE / 'repair/2026-10-20-dependency-atomic/published-v1-split.json'


def inputs():
    value = json.loads(INPUT.read_text())
    source = json.loads((BASE / 'current-plan/source-index.v1.json').read_text())
    bundle = json.loads((BASE / 'current-plan/semantic-plan-bundle.v1.json').read_text())
    return value, source, bundle


def load(tmp_path, value, source, bundle):
    path = tmp_path / 'split.json'
    path.write_text(json.dumps(value))
    return repair.load_v1_split(path, BASE / 'requirements.md', source, bundle)


def test_0806_splits_independent_outcomes_without_changing_source(tmp_path):
    value, source, bundle = inputs()
    result = load(tmp_path, value, source, bundle)
    assert len(result['normalized_obligations']) == 4
    assert len(result['projected_v3']['acceptances']) == 4
    assert all(x['source_refs'] == [value['source_ref']] for x in result['normalized_obligations'])
    assert result['authorizes'] == []
    assert sum(x['status'] == 'active' for x in bundle['obligations']) == 286


@pytest.mark.parametrize('defect', ['unknown-source', 'wrong-source', 'unknown-target',
                                  'duplicate-target', 'inactive-target', 'duplicate-child',
                                  'inactive-child', 'empty-split', 'single-child',
                                  'incomplete-contracts', 'stale-source-hash', 'authority'])
def test_split_rejects_unbound_or_incomplete_inputs(tmp_path, defect):
    value, source, bundle = inputs()
    if defect == 'unknown-source': value['source_ref'] += '-unknown'
    elif defect == 'wrong-source':
        value['source_ref'] = next(x['source_ref'] for x in source['entries'] if x['requirement_id'] == 'SM-A09')
    elif defect == 'unknown-target': value['replaced_obligation_id'] = 'O-UNKNOWN'
    elif defect == 'duplicate-target':
        bundle['obligations'].append(deepcopy(next(x for x in bundle['obligations'] if x['obligation_id'] == value['replaced_obligation_id'])))
    elif defect == 'inactive-target':
        next(x for x in bundle['obligations'] if x['obligation_id'] == value['replaced_obligation_id'])['status'] = 'not_applicable'
    elif defect == 'duplicate-child': value['obligations'][1] = deepcopy(value['obligations'][0])
    elif defect == 'inactive-child': value['obligations'][0]['status'] = 'not_applicable'
    elif defect == 'empty-split': value['obligations'] = []
    elif defect == 'single-child': value['obligations'] = value['obligations'][:1]
    elif defect == 'incomplete-contracts': value['v3_contracts'].pop(next(iter(value['v3_contracts'])))
    elif defect == 'stale-source-hash': value['requirements_sha256'] = 'sha256:' + '0' * 64
    else: value['authorizes'] = ['implementation']
    with pytest.raises(ValueError):
        load(tmp_path, value, source, bundle)


def test_split_cannot_duplicate_an_unselected_peer(tmp_path):
    value, source, bundle = inputs()
    peer = next(x for x in bundle['obligations'] if x['requirement_id'] == 'SM-REPAIR-CONSTRAINTS' and x['obligation_id'] != value['replaced_obligation_id'])
    value['obligations'][0] = deepcopy(peer)
    with pytest.raises(ValueError, match='IDs'):
        load(tmp_path, value, source, bundle)


def test_published_predecessor_validates_current_companion_identity(tmp_path):
    result = repair.load_published_predecessor(
        BASE / 'current-plan', BASE / 'dependency-atomic-plan-test-unwritten',
        BASE / 'requirements.md', ROOT)
    assert result['source_index']['companions'] == []
    # A companion-field mutation must not be accepted under an entries-only hash.
    from unittest import mock
    original_loads = json.loads

    def altered(raw, *args, **kwargs):
        value = original_loads(raw, *args, **kwargs)
        if isinstance(value, dict) and value.get('schema') == 'source-index.v1':
            value['companions'] = [{'source_ref': 'injected.md#FR-1'}]
        return value

    with mock.patch.object(repair.json, 'loads', side_effect=altered):
        with pytest.raises(ValueError, match='source index is invalid'):
            repair.load_published_predecessor(
                BASE / 'current-plan', BASE / 'dependency-atomic-plan-test-unwritten',
                BASE / 'requirements.md', ROOT)


@pytest.mark.parametrize('markers,allowed', [
    (['A-668FC5F50610-MISSING-RECORD'], True),
    (['other-slice'], False),
    ([], False),
    (['A22_STRICT_REJECTS_PRESTANDARD'], False),
])
def test_shared_partial_q2_module_is_not_an_unrelated_test(markers, allowed, tmp_path):
    from quick_dev_handoff import handoff_findings
    _, _, bundle = inputs()
    target = 'scripts/sc/tests/test_skill_quality_examples.py'
    path = tmp_path / target
    path.parent.mkdir(parents=True)
    path.write_text('\n'.join('@pytest.mark.cer_assertion(' + repr(x) + ')' for x in markers)
                    + '\ndef test_declared(): pass\n')
    conflicts = [x for x in handoff_findings(bundle, workspace=tmp_path)
                 if 'existing-test-assertion-mismatch:' + target in x]
    assert bool(conflicts) is not allowed


def test_published_rehydration_preserves_each_acceptance_preflight_metadata():
    import semantic_compiler_gate as gate
    _, _, bundle = inputs()
    projected = repair.project_published_v3(bundle)
    hints = {x['obligation_ids'][0]: x for x in projected['slice_hints']}
    fields = ('verification_lane', 'complexity_class', 'context_lookup_required',
              'context_lookup_reason', 'minimum_red_scope', 'upgrade_conditions')
    for acceptance in bundle['acceptances']:
        actual = gate._preflight_contract(hints[acceptance['obligation_ids'][0]])
        assert {k: actual[k] for k in fields} == {k: acceptance[k] for k in fields}

"""ADR-0041: explicit RED-role repair retains valid source/test bindings."""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT / 'scripts/vdd'))
from compile_plan import semantic_compiler as sc
from quick_dev_handoff import repair_runtime_red_bindings, semantic_projection
import quick_dev_handoff as handoff


def original():
    return json.loads((ROOT / 'execution-plans/2026-08-06-skill-authoring-standard/dependency-atomic-plan-03/semantic-plan-bundle.v1.json').read_text())


def test_explicit_runtime_role_keeps_current_0806_test_surface(tmp_path):
    prior=original()
    aids={'A-865B68436F68','A-95303CCF0FE6'}
    selected=[f['failure_intent_id'] for f in prior['failure_intents'] if set(f['acceptance_ids']) & aids and f['failure_family']!='expected-red']
    # Isolate the historical valid handoff from later deliberate assertion-ID
    # repairs. This fixture exercises static binding admission, not test proof.
    acceptance={a['acceptance_id']:a for a in prior['acceptances']}
    by_path={}
    for item in prior['slices']:
        for path in item['execution_snapshot_paths']:
            by_path.setdefault(path,set()).update(marker for aid in item['acceptance_ids'] for marker in acceptance[aid]['assertion_ids'])
    for relative,markers in by_path.items():
        path=tmp_path/relative;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('import pytest\n'+''.join('@pytest.mark.cer_assertion('+repr(marker)+')\ndef test_binding_'+str(index)+'(): pass\n' for index,marker in enumerate(sorted(markers))))
    result,delta=repair_runtime_red_bindings(prior,'scripts/sc/tests/skill-quality',tmp_path,selected)
    assert semantic_projection(result)==semantic_projection(prior)
    for before,after in zip(prior['slices'],result['slices']):
        assert before['execution_snapshot_paths']==after['execution_snapshot_paths']
        assert before['planned_new_files']==after['planned_new_files']
    assert [c['validation_commands'] for c in result['agent_contexts']]==[c['validation_commands'] for c in prior['agent_contexts']]
    old={f['failure_intent_id'] for f in prior['failure_intents']}
    added=[f for f in result['failure_intents'] if f['failure_intent_id'] not in old]
    assert len(added)==len(selected)
    assert all(set(f['acceptance_ids'])<=aids for f in added)
    assert delta['execution_binding_repair']['retained_current_bindings'] is True


def test_current_and_legacy_source_identity_shapes_remain_exact():
    entries=[{'source_ref':'req.md#A01'}]
    legacy={'entries':entries,'sha256':sc.sha256_value(entries)}
    current={'entries':entries,'companions':[]}
    current['sha256']=sc.sha256_value({'entries':entries,'companions':[]})
    assert handoff.source_index_identity(legacy)==legacy['sha256']
    assert handoff.source_index_identity(current)==current['sha256']
    changed=deepcopy(current);changed['companions']=[{'source_ref':'unreviewed.md'}]
    assert handoff.source_index_identity(changed)!=current['sha256']


def test_textual_prerequisites_are_not_invented_slice_edges():
    prior=original()
    result=handoff._project_slice_dependencies(deepcopy(prior))
    assert result['obligations']==prior['obligations']
    assert all(not s['depends_on'] for s in result['slices'])



def test_multi_file_partial_authoring_checks_each_files_own_markers(tmp_path):
    # Each file contains a known parameter from another slice sharing that file.
    # The current slice may still author its missing marker; a.py's marker must
    # never be compared against b.py's narrower marker domain.
    prior={'behavior_routing':{},'failure_intents':[], 'obligations':[],
           'acceptances':[], 'slices':[], 'agent_contexts':[]}
    for number,paths in [(1,['a.py','b.py']),(2,['a.py']),(3,['b.py'])]:
        oid='O-'+str(number);aid='A-'+str(number);sid='S'+str(number)
        prior['obligations'].append({'obligation_id':oid,'obligation_kind':'constraint','requirement_type':'Platform'})
        prior['acceptances'].append({'acceptance_id':aid,'obligation_ids':[oid],'assertion_ids':[aid],'red_intent_ids':[]})
        prior['slices'].append({'slice_id':sid,'acceptance_ids':[aid],'production_owners':[],
                               'planned_new_files':paths,'execution_snapshot_paths':paths})
        prior['agent_contexts'].append({'slice_id':sid,'validation_commands':[['python','-m','pytest',*paths]],'forbidden_paths':[]})
    for path,marker in [('a.py','A-2'),('b.py','A-3')]:
        (tmp_path/path).write_text('import pytest\n@pytest.mark.cer_assertion('+repr(marker)+')\ndef test_partial(): pass\n')
    assert handoff.handoff_findings(prior,tmp_path)==[]
    (tmp_path/'b.py').write_text('import pytest\n@pytest.mark.cer_assertion("UNKNOWN")\ndef test_partial(): pass\n')
    assert any('existing-test-assertion-mismatch:b.py' in f for f in handoff.handoff_findings(prior,tmp_path))

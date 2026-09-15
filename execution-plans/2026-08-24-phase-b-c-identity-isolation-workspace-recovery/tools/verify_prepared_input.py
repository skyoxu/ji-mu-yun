"""Read-only input/consumer verification; never runs a model or Phase test."""
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / 'execution-plans/2026-08-24-phase-b-c-identity-isolation-workspace-recovery'
sys.path.insert(0, str(ROOT / '.agents/skills/vdd-execution-plan/scripts'))
sys.path.insert(0, str(ROOT / '.agents/skills/quick-dev-tdd-adapter/tools'))
from semantic_plan_contract import validate_semantic_bundle
from q1_planned_preflight import validate_planned_preflight
from current_router import materialize_descriptor
from behavior_routing import production_hashes, validate_plan
from runtime_evidence import sha256_value


def read(name):
    return json.loads((PLAN / name).read_text(encoding='utf-8'))


def main():
    bundle = read('semantic-plan-bundle.v1.json')
    ok, findings = validate_semantic_bundle(bundle)
    assert ok, findings
    validate_plan(bundle)
    for key, file in [('obligations','obligations'), ('acceptances','acceptances'),
                      ('failure_intents','failure-intents'), ('slices','slices'),
                      ('pre_slice_coverage','pre-slice-coverage'), ('final_plan_coverage','final-plan-coverage')]:
        assert read(file+'.v1.json') == bundle[key], key
    contexts = {x['slice_id']: x for x in bundle['agent_contexts']}
    order = read('implementation-order.v1.json')['order']
    cases = read('implementation-case-map.v1.json')['case_maps']
    assert len(cases) == len(bundle['acceptances']) == len(bundle['obligations']) == 351
    assert len(order) == len(set(order)) == len(bundle['slices']) == 73
    assert order[0] == 'S12'
    assert {c['obligation_id'] for c in cases} == {o['obligation_id'] for o in bundle['obligations']}
    source_refs = set()
    owner_hashes = {}
    checks = []
    for selected in bundle['slices']:
        sid = selected['slice_id']
        assert read('agent-context/'+sid+'/agent-context.json') == contexts[sid]
        unhashed = dict(selected)
        digest = unhashed.pop('slice_input_hash')
        assert sha256_value(unhashed) == digest
        assert all(order.index(dep) < order.index(sid) for dep in selected['depends_on'])
        snapshots = set(selected['execution_snapshot_paths'])
        assert snapshots == set(selected['planned_new_files'])
        assert snapshots <= set(selected['allowed_write_paths'])
        assert not snapshots & set(selected['production_owners'])
        assert all(not (ROOT / ref).exists() for ref in snapshots), 'Target tests were not authorized online'
        for ref in selected['production_owners']:
            owner_hashes[ref] = 'sha256:'+hashlib.sha256((ROOT/ref).read_bytes()).hexdigest()
        preflight = validate_planned_preflight(workspace=ROOT, bundle=bundle, slice_id=sid, timeout_seconds=600)
        descriptor = materialize_descriptor(bundle=bundle, slice_id=sid, stage='probe', run_id='input-check-only',
            candidate_hash=preflight['candidate_hash'], argv=preflight['argv'], cwd='.', timeout_seconds=600,
            target_refs=preflight['target_refs'], fixture_refs=preflight['fixture_refs'])
        assert all(x['expected_failure_ids'] for x in descriptor['case_contract']['bindings'])
        hashes = production_hashes(ROOT, bundle, sid)
        assert hashes
        checks.append({'slice_id':sid, 'planned_preflight':'passed', 'probe_descriptor_contract':'passed',
                       'dependency_fingerprint':'passed', 'bound_assertions':len(descriptor['acceptance_assertions'])})
    for obligation in bundle['obligations']:
        source_refs.update(obligation['source_refs'])
    for ref in source_refs:
        path, _, anchor = ref.partition('#')
        text = (ROOT/path).read_text(encoding='utf-8')
        assert text
        if anchor:
            anchors = set(re.findall(r'id="([^"]+)"', text))
            for line in text.splitlines():
                if line.startswith('#'):
                    title = re.sub(r'^#+\s*', '', line).strip().lower()
                    anchors.add(re.sub(r'[^\w\- ]', '', title).replace(' ', '-'))
            assert anchor in anchors, ref
    for source in read('input-repair-source-index.v1.json')['sources']:
        assert 'sha256:'+hashlib.sha256((ROOT/source['path']).read_bytes()).hexdigest() == source['sha256']
    negative_checks=[]
    for mutation in ('undeclared-test-path', 'acceptance-projection-drift'):
        bad=copy.deepcopy(bundle)
        if mutation == 'undeclared-test-path':
            bad['slices'][0]['planned_new_files']=[]
        else:
            next(c for c in bad['agent_contexts'] if c['slice_id']=='S12')['acceptance_ids']=[]
        try:
            validate_planned_preflight(workspace=ROOT,bundle=bad,slice_id='S12',timeout_seconds=600)
        except ValueError:
            negative_checks.append(mutation)
        else:
            raise AssertionError('Invalid input admitted: '+mutation)
    def public_preflight(sid):
        result=subprocess.run([sys.executable,'-B','scripts/quick_dev/run.py','--plan',str(PLAN.relative_to(ROOT)),
                               '--slice',sid,'--profile','standard'],cwd=ROOT,capture_output=True,text=True,timeout=60)
        assert result.returncode == 0, result.stderr
        payload=json.loads(result.stdout)
        assert payload['status']=='preflight-passed', payload
        assert payload['authorizes']==[] and not payload['errors']
        return {'slice_id':sid, 'status':payload['status'], 'profile':payload['profile']}
    with ThreadPoolExecutor(max_workers=6) as pool:
        public=list(pool.map(public_preflight,order))
    print(json.dumps({'schema':'phase-b-c.direct-input-validation.v1','baseline_commit':'9cd87d3ab780f7087b9fd470dc2843968b208eca',
        'semantic_bundle_sha256':sha256_value(bundle),'status':'input-checks-passed','product_completion_claim':False,
        'semantic_contract':'passed','routing_contract':'passed','projection_consistency':'passed','source_manifest':'passed',
        'source_refs_checked':len(source_refs),'slices':checks,'public_preflight':public,'negative_checks':negative_checks,
        'production_sha256':owner_hashes,'model_called':False,'phase_tests_executed':False,'formal_workflow_called':False,
        'authorizes':[]},ensure_ascii=False,sort_keys=True,indent=2))


if __name__ == '__main__':
    main()

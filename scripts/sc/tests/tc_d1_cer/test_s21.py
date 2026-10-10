from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[4]
ENTRY=ROOT/'scripts/sc/skill_package_replay.py'
TARGET='.agents/skills/run-refactor-implementation-acceptance'
CAPABILITY='scripts/sc/config/skill-package-validator-capability.v1.json'
def check(ok, fid, detail):
    if not ok: print(f'FAILURE_ID:{fid}')
    assert ok, detail
def graph(orphan):
    o='O-AE55AC232B50'; nodes=[{'id':o,'node_type':'atomic_obligation'}]; edges=[]
    for t in ('assertions','selectors','commands','witnesses','runtime_evidence'):
        n=f'N-{t}'; nodes.append({'id':n,'node_type':t}); edges += [{'source':o,'target':n},{'source':n,'target':o}]
    if orphan: nodes.append({'id':'W-ORPHAN','node_type':'witnesses'})
    return {'requirements':[{'id':'SM-1','acceptance_ids':['A-1A7801CE3E0D']}],'acceptance_ids':['A-1A7801CE3E0D'],'reverse_mapping':{'A-1A7801CE3E0D':['SM-1']},'exact_cover_graph':{'nodes':nodes,'edges':edges}}
@pytest.mark.parametrize('orphan',[pytest.param(False,marks=pytest.mark.cer_assertion('A-AE55AC232B50-1')),pytest.param(True,marks=pytest.mark.cer_assertion('A-AE55AC232B50-1'))])
def test_sm1_integrity_report(orphan):
    sys.path.insert(0,str(ROOT/'.agents/skills/vdd-conformance-exact-cover/scripts'))
    from conformance import exact_cover
    m=graph(orphan)
    r=exact_cover(m['requirements'],m['acceptance_ids'],m['reverse_mapping'],m['exact_cover_graph'])
    orphan_count=len(r.get('orphan_nodes',[]))
    coverage=r.get('node_type_coverage',{}).get('O-AE55AC232B50',{})
    required_types=('assertions','selectors','commands','witnesses','runtime_evidence')
    complete=all(coverage.get(node_type)=='complete' for node_type in required_types)
    valid=(r['status']=='conformant' and orphan_count==0 and r['bidirectional'] and complete)
    invalid=(r['status']=='blocked' and orphan_count>0 and r['bidirectional'])
    check(valid if not orphan else invalid, 'F-AE55AC232B50-1',
          {'report':r,'orphan_count':orphan_count,'coverage_complete':complete})
@pytest.mark.cer_assertion('A-ACEC1E3A90A2-1')
def test_sm2_unexecuted_case_is_rejected_with_explicit_reason():
    matrix={'schema_version':'jimuyun.stable-candidate-replay-matrix.v2','authorizes':[],'cases':[{'case_id':'unexecuted-case','target':TARGET,'capability':CAPABILITY,'expected_exit':0,'matrix_evidence':[{'case_id':'unexecuted-case','executed':False}]}]}
    child="import runpy,sys\nfrom pathlib import Path\npayload=sys.stdin.read(); old=Path.read_text; oldb=Path.read_bytes\nPath.read_text=lambda p,*a,**k: payload if p.name=='s21-matrix.json' else old(p,*a,**k)\nPath.read_bytes=lambda p,*a,**k: payload.encode() if p.name=='s21-matrix.json' else oldb(p,*a,**k)\nsys.argv=['scripts/sc/skill_package_replay.py','replay-matrix','--matrix','s21-matrix.json']\nrunpy.run_path(sys.argv[0],run_name='__main__')\n"
    x=subprocess.run([sys.executable,'-B','-c',child],cwd=ROOT,input=json.dumps(matrix),capture_output=True,text=True,encoding='utf-8',check=False); r=json.loads(x.stdout); row=r['case_results'][0]
    check(x.returncode!=0 and r.get('aggregate_valid') is False and row.get('status')!='pass' and 'execut' in row.get('rejection_reason','').lower(),'F-ACEC1E3A90A2-1',r)

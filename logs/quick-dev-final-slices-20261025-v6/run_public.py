"""Sequential public CLI calls only; no evidence authority, model or CI routing."""
import ast,json,os,subprocess,sys
from pathlib import Path
from collections import Counter
ROOT=Path.cwd(); LOG=Path('logs/quick-dev-final-slices-20261025-v6'); LOG.mkdir(exist_ok=True)
PLAN='execution-plans/2026-10-25-vdd-knowledge-query-caller-runtime-role'
HOST='d86539b9602d9cff7cfe1d96ae6a58b287ce7b3d'; BASE='965df2e34f71ef197fffd8afb68f037688486ca2'
bundle=json.loads((ROOT/PLAN/'semantic-plan-bundle.v1.json').read_text())
ORDER=['S2','S5','S6','S1','S3','S7','S8','S4','S11','S12','S10','S9']
# The order is checked against actual frozen graph edges, never just numbering.
# Validate the actual frozen dependency order before current execution.
seen=set()
for sid in ORDER:
 s=next(s for s in bundle['slices'] if s['slice_id']==sid)
 assert set(s['depends_on']) <= seen,(sid,s['depends_on']);seen.add(sid)
# All mappings exist; these Q2 entries must not need another author/model.
for sid in ORDER:
 s=next(s for s in bundle['slices'] if s['slice_id']==sid);declared=set()
 for name in s['execution_snapshot_paths']:
  for node in ast.walk(ast.parse((ROOT/name).read_text())):
   if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='cer_assertion' and node.args and isinstance(node.args[0],ast.Constant):declared.add(node.args[0].value)
 required={a for r in bundle['acceptances'] if r['acceptance_id'] in s['acceptance_ids'] for a in r['assertion_ids']}
 assert required <= declared,(sid,required-declared)
env=dict(os.environ,TMPDIR='/workspace/scratch/quick-dev-pytest-tmp-v2',PYTEST_ADDOPTS='-o tmp_path_retention_policy=failed')
env['PATH']='/tmp/vdd-pause-tests/bin:'+env['PATH']
status=[]
def action(sid,run,name,extra=()):
 output=LOG/(sid+'-'+name+'-current.stdout.json'); error=LOG/(sid+'-'+name+'-current.stderr.txt')
 if output.exists() or error.exists():raise RuntimeError('Explicit output already exists; preserve it before choosing recovery: '+str(output))
 argv=[sys.executable,'-B','scripts/quick_dev/run.py','--plan',PLAN,'--slice',sid,'--profile','standard','--action',name,'--run-dir',str(run),'--unit-timeout-seconds','1800','--idle-timeout-seconds','600',*extra]
 with output.open('xb') as out,error.open('xb') as err:
  completed=subprocess.run(argv,cwd=ROOT,env=env,stdout=out,stderr=err)
 if completed.returncode:raise RuntimeError(sid+' '+name+' public CLI exit '+str(completed.returncode)+'; '+str(error))
 result=json.loads(output.read_text())
 print(json.dumps({'slice':sid,'action':name,'status':result.get('status'),'predicate_result':result.get('predicate_result'),'next':result.get('required_next_action')}),flush=True)
 return result

def roots_for(sid,run):
 rows=json.loads(Path('logs/quick-dev-s10-runtime-role-20261025/S10.snapshot-roots.json').read_text())
 s=next(s for s in bundle['slices'] if s['slice_id']==sid)
 for r in rows:
  kind=r['root_kind'];r['inclusion_reason']=sid+' current retained source/contract/case/native proof'
  if kind=='candidate_tree':
   r.pop('repository_relative_posix_path',None);r['repository_relative_posix_paths']=sorted(set(s['production_owners']+s['execution_snapshot_paths']))
  elif kind=='plan':r['repository_relative_posix_path']=PLAN
  elif kind=='contract':r['repository_relative_posix_path']=PLAN+'/semantic-plan-bundle.v1.json'
  elif kind=='descriptor':r['repository_relative_posix_path']=str(run/'descriptors')
  elif kind=='fixture':
   r.pop('repository_relative_posix_path',None);r['repository_relative_posix_paths']=s['execution_snapshot_paths']
  elif kind=='plan_state_transition':r['repository_relative_posix_path']=str(run/'canonical-evidence/probe/observation.v2.json')
  elif kind=='source':r['repository_relative_posix_paths']+=['tests/toolchain/knowledge_query/test_planning_boundaries.py']
 for r in rows:
  if 'repository_relative_posix_paths' in r:r['repository_relative_posix_paths']=list(dict.fromkeys(r['repository_relative_posix_paths']))
 path=LOG/(sid+'-current.snapshot-roots.json');path.write_text(json.dumps(rows,indent=2)+'\n');return path,rows

for sid in ORDER:
 run=LOG/(sid+'-current')
 if True:
  q1=action(sid,run,'preflight');assert q1['status']=='preflight-passed',q1
  q2=action(sid,run,'author-red',['--worker-timeout-seconds','1800'])
  assert q2['status']=='probe-materialized' and q2['worker']['status']=='worker-not-required',q2
  probe=action(sid,run,'run-probe')
 counts=Counter(r['disposition'] for r in probe['behavior_dispositions'])
 assert counts.get('present')==len(next(s for s in bundle['slices'] if s['slice_id']==sid)['obligation_ids']) and len(counts)==1,(sid,counts)
 result=action(sid,run,'run-regression');assert result['predicate_result'],(sid,result.get('failure_family'),result.get('case_evidence_error'))
 roots_path,roots=roots_for(sid,run)
 ready=action(sid,run,'validate-slice',['--snapshot-roots',str(roots_path),'--source-commit',HOST,'--base-commit',BASE,'--out',str(LOG/(sid+'-slice-ready.json'))])
 assert ready['status']=='pass',(sid,ready)
 terminal=action(sid,run,'run-terminal');assert terminal['predicate_result'],(sid,terminal.get('failure_family'))
 sys.path.insert(0,str(ROOT/'.agents/skills/quick-dev-tdd-adapter/tools'))
 from runtime_evidence import current_snapshot
 current=current_snapshot(ROOT,roots,source_commit=HOST,base_commit=BASE)
 assert current['sha256']==ready['current_snapshot_sha256'],(sid,'post-terminal snapshot drift')
 status.append({'slice_id':sid,'Q7':'pass','terminal':'pass','snapshot_matches_after_terminal':True,'run':str(run),'snapshot_sha256':current['sha256'],'ready_ref':str(LOG/(sid+'-slice-ready.json'))})
 (LOG/'current-slice-status.json').write_text(json.dumps({'items':status,'whole_plan_Q8':'not-run','authorizes':[]},indent=2)+'\n')
 print(json.dumps({'slice_completed':sid,'current_count':len(status),'total':12}),flush=True)
print('All 12 current Q7/terminal results obtained; preparing Q8.',flush=True)

# Q8 shares the SAME explicit environment dictionary with every producer call.
# No post-hoc environment whitelist or old receipt upgrade is involved.
from runtime_evidence import sha256_value
predecessors=[];roots_union={}
for item in status:
 ready=json.loads((ROOT/item['ready_ref']).read_text())
 predecessors.append({'slice_id':item['slice_id'],'run_root':item['run'],'result_ref':item['ready_ref'],'result_sha256':sha256_value(ready)})
 for row in ready['snapshot_roots']:
  paths=row.get('repository_relative_posix_paths') or [row['repository_relative_posix_path']]
  roots_union.setdefault(row['root_kind'],set()).update(paths)
q8=LOG/'Q8';q8.mkdir(exist_ok=False)
pre_path=q8/'predecessors.json';pre_path.write_text(json.dumps(predecessors,indent=2)+'\n')
roots_path=q8/'snapshot-roots.json';roots_path.write_text(json.dumps([{'root_kind':kind,'repository_relative_posix_paths':sorted(paths),'inclusion_reason':'Whole-plan union of twelve current explicit runtime roots'} for kind,paths in roots_union.items()],indent=2)+'\n')
result=action('S2',q8,'implementation-complete',['--predecessors',str(pre_path),'--snapshot-roots',str(roots_path),'--source-commit',HOST,'--base-commit',BASE,'--out',str(q8/'implementation-complete-result.v2.json')])
assert result['status']=='pass',result
print('Whole-plan Q8 passed. Stopped before external review/Acceptance/publication.',flush=True)

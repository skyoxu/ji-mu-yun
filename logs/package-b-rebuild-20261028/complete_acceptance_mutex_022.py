"""Run existing native owners after the independently reviewed exact repair."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
T='execution-plans/2026-10-28-skill-compliance-package-b-rebuild-r3'
P=T+'/acceptance-inputs/preparation-mutex-20261028'
STORE=T+'/acceptance-inputs/preparation-20261028/skill-input-v2/acceptance'
CLI='.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py'
V='/workspace/.cloud-tools/package-b-env-20261028/bin/python'
E='1152321cd9133239ba295610a3297b93350e089f';FB='fb676bc398f653a2ffa869c95d6c8d632f6f9796'
ENV=dict(os.environ,PYTHONPATH='.',PYTHONDONTWRITEBYTECODE='1',TMPDIR='/workspace/scratch/package-b-acceptance-temp-20261028')
ENV['PATH']=str(Path(V).parent)+os.pathsep+ENV.get('PATH','')
def put(relative,value):
 p=R/relative;p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():
  assert json.loads(p.read_text())==value,'Immutable artifact mismatch:'+relative
  return
 with p.open('x',encoding='utf-8') as f:f.write(json.dumps(value,sort_keys=True,indent=2)+'\n')
def sha(relative):return 'sha256:'+hashlib.sha256((R/relative).read_bytes()).hexdigest()
def ref(relative):return {'path':os.path.relpath(R/relative,R/P),'sha256':sha(relative)}
def call(label,args):
 started=datetime.datetime.now(datetime.timezone.utc).isoformat();print(json.dumps({'unit':label,'event':'started','at':started}),flush=True)
 p=B/(label+'.log');assert not p.exists()
 with p.open('x',encoding='utf-8') as f:result=subprocess.run([V,'-B',*args],cwd=R,env=ENV,stdout=f,stderr=subprocess.STDOUT,check=False)
 put('logs/package-b-rebuild-20261028/'+label+'-invocation.json',{'schema':'package-b.actual-public-invocation.v1','argv':[V,'-B',*args],'started_utc':started,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':result.returncode,'raw_log':str(p.relative_to(R)),'raw_log_sha256':sha(str(p.relative_to(R))),'authorizes':[]})
 print(json.dumps({'unit':label,'event':'finished','exit_code':result.returncode,'raw_log':str(p.relative_to(R))}),flush=True)
 if result.returncode:raise SystemExit(result.returncode)
 return p.read_text(encoding='utf-8')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==E
repair=json.loads((B/'PUBLICATION-MUTEX-REPAIR-MANIFEST-r2.json').read_text())
for row in repair['files']:assert sha(row['path'])=='sha256:'+row['sha256']
session=json.loads((B/'execution-session-r14.json').read_text());session['source_commit']=E;session['out']='logs/package-b-rebuild-20261028/proof-refresh-mutex-r15/Q8.json'
for sl in session['slices']:
 sl['run_dir']=sl['run_dir'].replace('quick-dev-s1-r14','quick-dev-s1-r15');sl['ready_path']=sl['ready_path'].replace('proof-refresh-acceptance-r14','proof-refresh-mutex-r15')
 for row in sl['snapshot_roots']:
  if row['root_kind']=='descriptor':row['repository_relative_posix_paths']=[sl['run_dir']+'/descriptors']
for row in session['snapshot_roots']:
 if row['root_kind']=='descriptor':row['repository_relative_posix_paths']=['logs/package-b-rebuild-20261028/quick-dev-s1-r15/descriptors']
for roots in [session['snapshot_roots'],session['slices'][0]['snapshot_roots']]:
 for row in roots:
  if row['root_kind']=='validator_judge':
   row['repository_relative_posix_paths']=sorted(set(row['repository_relative_posix_paths']+[v['path'] for v in repair['files']]))
   row['inclusion_reason']='Current native host, fixed quality oracle and exact independently reviewed Acceptance preflight/routing and publisher mutex repair inputs; no new execution authority.'
put('logs/package-b-rebuild-20261028/execution-session-r15.json',session)
put('logs/package-b-rebuild-20261028/R15-PROOF-REFRESH-REASON.json',{'schema':'package-b.proof-successor-reason.v1','predecessor_run':'logs/package-b-rebuild-20261028/quick-dev-s1-r14','predecessor_Q8':'logs/package-b-rebuild-20261028/proof-refresh-acceptance-r14/Q8.json','reason':'Six reviewed source/contract/test bytes changed after real mutex classification defect and tracked-deletionP2 fix. Existing shared input inventory binds them and current judge roots explicitly include all six. Refresh only same S1 existing-present probe/regression/terminal under current stable environment; no newRED or implementation and no rerun merely for commitSHA.','approved_original_scope':'Sixrequests,fivepackages,77obligations unchanged; separate narrow Acceptance prerequisite repair','reviews':repair['predecessor_manifest'],'authorizes':[]})
base=['scripts/quick_dev/run.py','--plan',T,'--action']
q=R/session['out'];assert q.is_file(),'Inspect actual paused/worker/block status before any retry';assert json.loads(q.read_text())['status']=='pass'
binding=json.loads((q.parent/'acceptance-current-quick-dev-binding.json').read_text())
# Source diff and generated/evidence custody remain separate native scopes.
sys.path.insert(0,str(R))
from scripts.toolchain.candidate_content_paths import classify_path,CANDIDATE_CONTENT
allpaths=list(filter(None,subprocess.check_output(['git','diff','--name-only','-z',FB,E],cwd=R).decode().split('\0')))
scoped=[];retained=[]
for path in allpaths:
 generated=path.startswith(T+'/acceptance-inputs/') or path.startswith(T+'/.acceptance-snapshots/') or path.startswith(T+'/acceptance-run-request.')
 if path.startswith('logs/') or generated or classify_path(path)!=CANDIDATE_CONTENT:retained.append(path)
 else:scoped.append(path)
put('logs/package-b-rebuild-20261028/MUTEX-ACCEPTANCE-CANDIDATE-SCOPE.json',{'schema':'package-b.acceptance-source-custody-partition.v1','baseline':FB,'candidate':E,'all_git_difference_paths':allpaths,'candidate_content':scoped,'retained_generated_or_original_evidence':retained,'reason':'Existing native target-owned Acceptance evidence namespaces and retained logs have their own immutable custody. No source,canonicalplan,authority or derivedKnowledge path removed; full original diff preserved explicitly.','authorizes':[]})
registry=json.loads((R/P/'command-registry.projection-input.v1.json').read_text());actions=json.loads((R/P/'action-dag.projection-input.v1.json').read_text());req=json.loads((B/'acceptance-projection-request-017.json').read_text());req.update(runId='acceptance-package-b-mutex-20261028',candidateRevision=E,changedPaths=scoped,knowledgeContextPath='acceptance-inputs/preparation-mutex-20261028/knowledge-context.refactor-acceptance.v1.json',commands=registry['commands'],actions=actions,currentQuickDev=binding,implementationReceiptPath=binding['receipt']['path'],implementationReceiptHash=binding['receipt']['sha256'])
put('logs/package-b-rebuild-20261028/mutex-acceptance-projection-request-021.json',req)
call('mutex-acceptance-projection-021',[CLI,'project-compact-vdd','--repository-root','.', '--request','logs/package-b-rebuild-20261028/mutex-acceptance-projection-request-021.json','--out','logs/package-b-rebuild-20261028/mutex-acceptance-projection-result-021.json'])
projection=json.loads((B/'mutex-acceptance-projection-result-021.json').read_text());assert projection['status']=='ready'
prepared=P+'/prepared-run.v1.json';relative_bundle=str(Path(projection['bundle']).relative_to(T))
call('mutex-acceptance-prepare-run-021',[CLI,'prepare-run','--input',projection['runRequest'],'--knowledge-context','acceptance-inputs/preparation-mutex-20261028/knowledge-context.refactor-acceptance.v1.json','--prerequisite-bundle',relative_bundle,'--out',prepared])
ready=json.loads(call('mutex-skill-input-prepare-021',['scripts/python/skill_input_v2.py','prepare','--request',P+'/skill-input-request.v2.json']).strip());pid=ready['plan_id'];attempt=ready['attempt_id']
transport=call('mutex-skill-input-consume-021',['scripts/python/skill_input_v2.py','consume','--plan-id',pid,'--attempt-id',attempt]);print('Actual redacted Skill-input delivery:\n'+transport,flush=True)
call('mutex-skill-input-finish-021',['scripts/python/skill_input_v2.py','finish','--plan-id',pid,'--attempt-id',attempt])
contract='.agents/skills/run-refactor-implementation-acceptance/references/skill-input-contract.v1.json'
put(P+'/coordinator-request.v3.json',{'schemaVersion':'jimuyun.acceptance-coordinator-request.v3','targetPlan':T,'preparedRunInput':ref(prepared),'skillInputReceipt':ref(STORE+'/current.v1.json'),'skillInputContract':ref(contract),'authorizes':[]})
call('mutex-acceptance-coordinator-021',[CLI,'run-coordinator','--request',P+'/coordinator-request.v3.json','--out',P+'/coordinator-result.v4.json'])
print(json.dumps(json.loads((R/P/'coordinator-result.v4.json').read_text()),sort_keys=True),flush=True)

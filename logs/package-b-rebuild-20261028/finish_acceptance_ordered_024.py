"""Native successor with completed input delivery frozen before proof."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent;sys.path.insert(0,str(R))
T='execution-plans/2026-10-28-skill-compliance-package-b-rebuild-r3';P=T+'/acceptance-inputs/preparation-mutex-20261028';COMMON=T+'/acceptance-inputs';STORE=T+'/acceptance-inputs/preparation-20261028/skill-input-v2/acceptance'
CLI='.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py';V='/workspace/.cloud-tools/package-b-env-20261028/bin/python';F='13bd5b598ffde513cd75acea072f0e433f6c91b0';FB='fb676bc398f653a2ffa869c95d6c8d632f6f9796'
ENV=dict(os.environ,PYTHONPATH='.',PYTHONDONTWRITEBYTECODE='1',TMPDIR='/workspace/scratch/package-b-acceptance-temp-20261028');ENV['PATH']=str(Path(V).parent)+os.pathsep+ENV.get('PATH','')
def put(path,v):
 p=R/path;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:f.write(json.dumps(v,sort_keys=True,indent=2)+'\n')
def sha(path):return 'sha256:'+hashlib.sha256((R/path).read_bytes()).hexdigest()
def call(label,args):
 started=datetime.datetime.now(datetime.timezone.utc).isoformat();print(json.dumps({'unit':label,'event':'started','at':started}),flush=True);p=B/(label+'.log')
 with p.open('x',encoding='utf-8') as f:result=subprocess.run([V,'-B',*args],cwd=R,env=ENV,stdout=f,stderr=subprocess.STDOUT)
 put('logs/package-b-rebuild-20261028/'+label+'-invocation.json',{'schema':'package-b.actual-public-invocation.v1','argv':[V,'-B',*args],'started_utc':started,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_code':result.returncode,'raw_log':str(p.relative_to(R)),'raw_log_sha256':sha(str(p.relative_to(R))),'authorizes':[]});print(json.dumps({'unit':label,'event':'finished','exit_code':result.returncode}),flush=True)
 if result.returncode:raise SystemExit(result.returncode)
 return p.read_text(encoding='utf-8')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==F
contract=P+'/skill-input-contract.v1.json';pointer=STORE+'/current.v1.json'
call('ordered-skill-input-validate-024',['scripts/python/skill_input_v2.py','validate','--pointer',pointer,'--consumer','run-refactor-implementation-acceptance','--operation','acceptance','--contract',contract])
frozen_attempts={str(p.relative_to(R)):sha(str(p.relative_to(R))) for p in (R/'.skill-input-work/package-b-acceptance-20261028').rglob('*') if p.is_file()}
session=json.loads((B/'execution-session-r15.json').read_text());session['source_commit']=F;session['out']='logs/package-b-rebuild-20261028/proof-refresh-final-inputs-r16/Q8.json'
for sl in session['slices']:
 sl['run_dir']=sl['run_dir'].replace('quick-dev-s1-r15','quick-dev-s1-r16');sl['ready_path']=sl['ready_path'].replace('proof-refresh-mutex-r15','proof-refresh-final-inputs-r16')
 for row in sl['snapshot_roots']:
  if row['root_kind']=='descriptor':row['repository_relative_posix_paths']=[sl['run_dir']+'/descriptors']
for row in session['snapshot_roots']:
 if row['root_kind']=='descriptor':row['repository_relative_posix_paths']=['logs/package-b-rebuild-20261028/quick-dev-s1-r16/descriptors']
put('logs/package-b-rebuild-20261028/execution-session-r16.json',session)
base=['scripts/quick_dev/run.py','--plan',T,'--action']
call('ordered-r16-preflight-024',base+['preflight-session','--execution-request','logs/package-b-rebuild-20261028/execution-session-r16.json'])
call('ordered-r16-advance-024',base+['advance-session','--execution-request','logs/package-b-rebuild-20261028/execution-session-r16.json','--max-steps','8'])
q=R/session['out'];assert q.is_file() and json.loads(q.read_text())['status']=='pass'
binding=json.loads((q.parent/'acceptance-current-quick-dev-binding.json').read_text());from scripts.toolchain.candidate_content_paths import classify_path,CANDIDATE_CONTENT
allpaths=list(filter(None,subprocess.check_output(['git','diff','--name-only','-z',FB,F],cwd=R).decode().split('\0')));scoped=[];retained=[]
for path in allpaths:
 generated=path.startswith(T+'/acceptance-inputs/') or path.startswith(T+'/.acceptance-snapshots/') or path.startswith(T+'/acceptance-runs/') or path.startswith(T+'/acceptance-run-request.') or path==T+'/acceptance-current.v1.json'
 if path.startswith('logs/') or generated or classify_path(path)!=CANDIDATE_CONTENT:retained.append(path)
 else:scoped.append(path)
put('logs/package-b-rebuild-20261028/FINAL-ACCEPTANCE-CANDIDATE-SCOPE.json',{'schema':'package-b.acceptance-source-custody-partition.v1','baseline':FB,'candidate':F,'all_git_difference_paths':allpaths,'candidate_content':scoped,'retained_generated_or_original_evidence':retained,'reason':'Source/canonicalplan/derivedKnowledge scope unchanged; normal native generated Acceptance evidence has independent custody. Complete Git difference retained.','authorizes':[]})
req=json.loads((B/'mutex-acceptance-projection-request-021.json').read_text());req.update(runId='acceptance-package-b-mutex-final-20261028',candidateRevision=F,changedPaths=scoped,currentQuickDev=binding,implementationReceiptPath=binding['receipt']['path'],implementationReceiptHash=binding['receipt']['sha256']);put('logs/package-b-rebuild-20261028/final-acceptance-projection-request-024.json',req)
call('ordered-acceptance-projection-024',[CLI,'project-compact-vdd','--repository-root','.', '--request','logs/package-b-rebuild-20261028/final-acceptance-projection-request-024.json','--out','logs/package-b-rebuild-20261028/final-acceptance-projection-result-024.json'])
projection=json.loads((B/'final-acceptance-projection-result-024.json').read_text());newinput=Path(projection['bundle']).parent
for filename in ['baseline-content-manifest.v1.json','candidate-content-manifest.v1.json']:
 assert (R/newinput/filename).read_bytes()==(R/T/'acceptance-inputs/acceptance-package-b-mutex-20261028'/filename).read_bytes(),'The already-bound exact policy action source manifests must remain byte-identical'
prepared=P+'/prepared-run.final.v1.json';call('ordered-acceptance-prepare-024',[CLI,'prepare-run','--input',projection['runRequest'],'--knowledge-context','acceptance-inputs/preparation-mutex-20261028/knowledge-context.refactor-acceptance.v1.json','--prerequisite-bundle',str(Path(projection['bundle']).relative_to(T)),'--out',prepared])
# Reuse the already delivered live generation, never create a new attempt here.
call('ordered-skill-input-revalidate-024',['scripts/python/skill_input_v2.py','validate','--pointer',pointer,'--consumer','run-refactor-implementation-acceptance','--operation','acceptance','--contract',contract])
assert frozen_attempts=={str(p.relative_to(R)):sha(str(p.relative_to(R))) for p in (R/'.skill-input-work/package-b-acceptance-20261028').rglob('*') if p.is_file()}
def ref(path):return {'path':str(Path(path).relative_to(COMMON)),'sha256':sha(path)}
request=COMMON+'/coordinator-request.mutex-final.v3.json';put(request,{'schemaVersion':'jimuyun.acceptance-coordinator-request.v3','targetPlan':T,'preparedRunInput':ref(prepared),'skillInputReceipt':ref(pointer),'skillInputContract':ref(contract),'authorizes':[]})
call('ordered-acceptance-coordinator-024',[CLI,'run-coordinator','--request',request,'--out',P+'/coordinator-result.final.v4.json'])
result=json.loads((R/P/'coordinator-result.final.v4.json').read_text());print(json.dumps(result,sort_keys=True),flush=True)
assert result['status']=='completed' and result['finalization']['status']=='acceptance-passed','Inspect the native waiting/failure result; do not claim pass'

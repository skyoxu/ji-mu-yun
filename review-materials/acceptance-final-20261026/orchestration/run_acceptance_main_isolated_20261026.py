"""Task-local continuation through unchanged public Acceptance entries."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys,time
R=Path('/workspace/ji-mu-yun-acceptance-candidate-20261026');os.chdir(R);sys.path.insert(0,str(R/'scripts'))
from workflow_unit_budget import supervise
# Match the real positive execution environment, not a fresh shell wrapper.
os.environ.update(PATH='/workspace/scratch/stage5-p1-tests-20261026/bin:'+os.environ['PATH'],TMPDIR='/workspace/scratch/quick-dev-pytest-tmp-v2',PYTEST_ADDOPTS='-o tmp_path_retention_policy=failed')
P='execution-plans/2026-10-26-vdd-knowledge-query-p1-static-bindings';PREP=P+'/acceptance-inputs/acceptance-20261026-main-isolated';PROOF='logs/acceptance-main-isolated-proof-refresh-20261026';LOG=R/'logs/acceptance-trusted-main-loader-fix-20261026';PY=sys.executable;CLI='.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py';BASE='965df2e34f71ef197fffd8afb68f037688486ca2'
read=lambda p:json.loads((R/p).read_text());sha=lambda p:'sha256:'+hashlib.sha256((R/p).read_bytes()).hexdigest();now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def put(p,value):
 path=R/p;assert not path.exists(),p;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
preparation=read('logs/acceptance-trusted-main-loader-fix-20261026/preparation-completed.json');HOST=preparation['candidate'];assert read(PROOF+'/checkpoint.json')['state']=='Q8-completed';assert len(read(PROOF+'/checkpoint.json')['completed_slices'])==12
assert subprocess.check_output(['git','symbolic-ref','--short','HEAD'],text=True).strip()=='acceptance/knowledge-query-final-content-20261026','Unexpected branch; do not commit or proceed'
assert subprocess.check_output(['git','rev-parse','refs/heads/main'],text=True).strip()=='a1e783c569cb5a78ea8728c83518fd13c73a99e8','Actual main drifted; preserve checkpoint'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HOST and subprocess.check_output(['git','status','--porcelain'],text=True)==''
assert all(sha(x['path'])==x['sha256'] for x in preparation['attempt_files'])
state={'state':'prepared','commands':{},'candidate':HOST,'authorizes':[]}
checkpoint=LOG/'native-acceptance-checkpoint.json';assert not checkpoint.exists()
def save():checkpoint.write_text(json.dumps(state,indent=2)+'\n')
def run(label,args):
 out=LOG/(label+'.stdout.jsonl');err=LOG/(label+'.stderr.txt');assert not out.exists();argv=[PY,'-B',*args];put(str((LOG/(label+'.command.json')).relative_to(R)),{'argv':argv,'at':now(),'unit_seconds':1800,'idle_seconds':600,'authorizes':[]});state.update(state='running',active=label,started_at=now());save();print(json.dumps({'event':'acceptance-start','label':label,'at':now()}),flush=True);start=time.monotonic()
 old_out=os.dup(1);old_err=os.dup(2)
 try:
  with out.open('wb') as o,err.open('wb') as e:
   os.dup2(o.fileno(),1);os.dup2(e.fileno(),2)
   code=supervise(argv,cwd=R,directory=Path('/tmp/acceptance-main-isolated-native-budget-20261026')/label,total=1800,idle=600)
 finally:os.dup2(old_out,1);os.dup2(old_err,2);os.close(old_out);os.close(old_err)
 state['commands'][label]={'exit_code':code,'seconds':time.monotonic()-start,'finished_at':now()};save();print(json.dumps({'event':'acceptance-return','label':label,**state['commands'][label]}),flush=True);assert code==0,label+' failed; preserve raw output'
 return json.loads(out.read_text().splitlines()[-1])
try:
 receipt=PROOF+'/Q8/implementation-complete-result.v2.json';semantic=P+'/semantic-plan-bundle.v1.json';request={'schemaVersion':'compact-vdd-acceptance-projection-request.v1','targetPlan':P,'runId':'acceptance-main-isolated-20261026','changeId':'knowledge-query-current-isolated-main-validation','baselineRevision':BASE,'candidateRevision':HOST,'changedPaths':preparation['changed_source_paths'],'affectedConsumerRefs':sorted(['.agents/skills/vdd-execution-plan/SKILL.md','.agents/skills/quick-dev-tdd-adapter/SKILL.md','.agents/skills/run-refactor-implementation-acceptance/SKILL.md']),'targetPlanPaths':['semantic-plan-bundle.v1.json'],'knowledgeContextPath':PREP.removeprefix(P+'/')+'/knowledge-context.refactor-acceptance.current.v1.json','codeReviewDomain':'toolchain','codeReviewPolicyPath':'.agents/skills/run-refactor-implementation-acceptance/policies/toolchain-code-review.v1.json','implementationReceiptPath':receipt,'implementationReceiptHash':sha(receipt),'commands':read(PREP+'/command-registry.projection-input.v1.json')['commands'],'actions':read(PREP+'/action-dag.v1.json'),'currentQuickDev':{'semanticPlan':{'path':semantic,'sha256':sha(semantic)},'receipt':{'path':receipt,'sha256':sha(receipt)},'snapshotRoots':read(PROOF+'/Q8/snapshot-roots.json'),'sourceCommit':HOST,'baseCommit':BASE},'authorizes':[]};req_path=PREP+'/compact-vdd-projection-request.v1.json';put(req_path,request)
 projection=run('project-compact-vdd',[CLI,'project-compact-vdd','--repository-root',str(R),'--request',req_path,'--out',PREP+'/compact-projection-result.v1.json']);assert projection['status']=='ready'
 bundle=read(projection['bundle']);actual_registry=read(P+'/'+bundle['commandRegistry']['path']);assert actual_registry==read(PREP+'/command-registry.projection-input.v1.json')
 prepared=PREP+'/prepared-run-input.v1.json';run('prepare-run',[CLI,'prepare-run','--input',projection['runRequest'],'--knowledge-context',request['knowledgeContextPath'],'--prerequisite-bundle',str(Path(projection['bundle']).relative_to(P)),'--out',prepared])
 pointer=preparation['current_pointer'];contract=PREP+'/skill-input-contract.v1.json'
 def ref(p):return {'path':str(Path(p).relative_to(PREP)),'sha256':sha(p)}
 coord={'schemaVersion':'jimuyun.acceptance-coordinator-request.v3','targetPlan':P,'preparedRunInput':ref(prepared),'skillInputReceipt':ref(pointer),'skillInputContract':ref(contract),'authorizes':[]};coord_path=PREP+'/acceptance-coordinator-request.v3.json';put(coord_path,coord);result_path=PREP+'/acceptance-coordinator-result.v4.json';result=run('run-coordinator',[CLI,'run-coordinator','--request',coord_path,'--out',result_path]);assert result['status']=='completed' and result['finalization']['authorizes']==['acceptance-passed']
 assert all(sha(x['path'])==x['sha256'] for x in preparation['attempt_files'])
 state.update(state='acceptance-passed',finished_at=now(),result=result_path,run_directory=result['runDirectory']);save();put('logs/acceptance-trusted-main-loader-fix-20261026/ACCEPTANCE-HANDOFF.json',{'kind':'Actual native Acceptance, not publication authority','at':now(),'candidate':HOST,'plan':P,'plan_sha256':sha(semantic),'Q8':{'path':receipt,'sha256':sha(receipt)},'coordinator_request':{'path':coord_path,'sha256':sha(coord_path)},'coordinator_result':{'path':result_path,'sha256':sha(result_path)},'run_directory':result['runDirectory'],'all_completed_attempt_files_retained_in_place':True,'required_attempt_dependency_originals':preparation['attempt_files'],'isolation_source_paths':preparation['isolation_source_paths'],'compatibility_scope':'logs/acceptance-trusted-main-loader-fix-20261026/compatibility-source-scope.json','published':False,'no_new_models_BMAD_AB_Windows_CI_or_push':True,'authorizes':[]});print(json.dumps({'event':'acceptance-passed','result':result_path,'at':now()}),flush=True)
except Exception as exc:
 state.update(state='blocked',error=str(exc),stopped_at=now());save();raise

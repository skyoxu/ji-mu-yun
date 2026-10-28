"""Repair only native coordinator reference custody before any run starts."""
from pathlib import Path
import json,hashlib,os,subprocess,datetime
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
T='execution-plans/2026-10-28-skill-compliance-package-b-rebuild-r3';P=T+'/acceptance-inputs/preparation-mutex-20261028';COMMON=T+'/acceptance-inputs';STORE=T+'/acceptance-inputs/preparation-20261028/skill-input-v2/acceptance'
CLI='.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py';V='/workspace/.cloud-tools/package-b-env-20261028/bin/python'
ENV=dict(os.environ,PYTHONPATH='.',PYTHONDONTWRITEBYTECODE='1',TMPDIR='/workspace/scratch/package-b-acceptance-temp-20261028');ENV['PATH']=str(Path(V).parent)+os.pathsep+ENV.get('PATH','')
def put(path,value):
 p=R/path;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:f.write(json.dumps(value,sort_keys=True,indent=2)+'\n')
def sha(path):return 'sha256:'+hashlib.sha256((R/path).read_bytes()).hexdigest()
def call(label,args):
 print(json.dumps({'unit':label,'event':'started','at':datetime.datetime.now(datetime.timezone.utc).isoformat()}),flush=True)
 p=B/(label+'.log')
 with p.open('x',encoding='utf-8') as f:result=subprocess.run([V,'-B',*args],cwd=R,env=ENV,stdout=f,stderr=subprocess.STDOUT)
 put('logs/package-b-rebuild-20261028/'+label+'-invocation.json',{'schema':'package-b.actual-public-invocation.v1','argv':[V,'-B',*args],'exit_code':result.returncode,'raw_log':str(p.relative_to(R)),'raw_log_sha256':sha(str(p.relative_to(R))),'authorizes':[]})
 print(json.dumps({'unit':label,'event':'finished','exit_code':result.returncode}),flush=True)
 if result.returncode:raise SystemExit(result.returncode)
 return p.read_text(encoding='utf-8')
canonical='.agents/skills/run-refactor-implementation-acceptance/references/skill-input-contract.v1.json';copy=P+'/skill-input-contract.v1.json'
assert not (R/copy).exists();(R/copy).write_bytes((R/canonical).read_bytes());assert sha(copy)==sha(canonical)
request=json.loads((R/P/'skill-input-request.v2.json').read_text());request['bindings']['contract']={'path':copy,'sha256':sha(copy)};put(P+'/skill-input-request.local-contract.v2.json',request)
put('logs/package-b-rebuild-20261028/MUTEX-COORDINATOR-INPUT-REPAIR.json',{'schema':'package-b.native-input-layout-repair.v1','predecessor_request':P+'/coordinator-request.v3.json','predecessor_error':'Coordinator references cannot contain parent traversal. The previous request wrongly referenced sibling current storage and canonical contract outside its own directory. It failed before any persisted run/action.','repair':'Use the native example-supported byte-identical local contract copy and rebind only contract path in a new Skill-input request; same authority,selection,storage and registry. Place new coordinator request at acceptance-inputs common ancestor; all references strictly below it.','canonical_contract':canonical,'local_contract':copy,'same_sha256':sha(copy),'no_semantic_contract_change':True,'no_business_rerun':True,'authorizes':[]})
ready=json.loads(call('mutex-skill-input-prepare-023',['scripts/python/skill_input_v2.py','prepare','--request',P+'/skill-input-request.local-contract.v2.json']).strip());pid=ready['plan_id'];attempt=ready['attempt_id']
print('Actual redacted Skill-input delivery:\n'+call('mutex-skill-input-consume-023',['scripts/python/skill_input_v2.py','consume','--plan-id',pid,'--attempt-id',attempt]),flush=True)
call('mutex-skill-input-finish-023',['scripts/python/skill_input_v2.py','finish','--plan-id',pid,'--attempt-id',attempt])
def ref(path):return {'path':str(Path(path).relative_to(COMMON)),'sha256':sha(path)}
req=COMMON+'/coordinator-request.mutex-current.v3.json';put(req,{'schemaVersion':'jimuyun.acceptance-coordinator-request.v3','targetPlan':T,'preparedRunInput':ref(P+'/prepared-run.v1.json'),'skillInputReceipt':ref(STORE+'/current.v1.json'),'skillInputContract':ref(copy),'authorizes':[]})
call('mutex-acceptance-coordinator-023',[CLI,'run-coordinator','--request',req,'--out',P+'/coordinator-result.v4.json'])
print(json.dumps(json.loads((R/P/'coordinator-result.v4.json').read_text()),sort_keys=True),flush=True)

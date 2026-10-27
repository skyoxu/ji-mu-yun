"""Task-local assembly through current public entries, never a completion oracle."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys,xml.etree.ElementTree as E
R=Path('/workspace/ji-mu-yun-acceptance-candidate-20261026');os.chdir(R)
P='execution-plans/2026-10-26-vdd-knowledge-query-p1-static-bindings';OLD=P+'/acceptance-inputs/acceptance-20261026-prepared-v2';NEW=P+'/acceptance-inputs/acceptance-20261026-main-isolated';LOG=R/'logs/acceptance-trusted-main-loader-fix-20261026';PY='/workspace/scratch/stage5-p1-tests-20261026/bin/python';BASE='965df2e34f71ef197fffd8afb68f037688486ca2';BEFORE='1986fbe0fa4756ffee6e40edb8a9085fbfc3fd8f';S='.agents/skills/run-refactor-implementation-acceptance/';CLI=S+'scripts/acceptance_cli.py'
FILES=[S+'scripts/knowledge_context.py',S+'scripts/trusted_knowledge_validator.py',S+'tests/test_trusted_knowledge_validator.py',S+'tests/test_current_acceptance_closeout.py',S+'references/prepare-and-run.md']
read=lambda p:json.loads((R/p).read_text());sha=lambda p:'sha256:'+hashlib.sha256((R/p).read_bytes()).hexdigest();now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def put(p,v):
 f=R/p;raw=json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
 if f.exists():assert f.read_text()==raw,'Existing artifact differs: '+p
 else:f.parent.mkdir(parents=True,exist_ok=True);f.write_text(raw,encoding='utf-8')
 return p
def run(label,args):
 dest=LOG/(label+'.stdout.json');err=LOG/(label+'.stderr.txt');assert not dest.exists()
 (LOG/(label+'.command.json')).write_text(json.dumps({'argv':[PY,'-B',*args],'started_at':now(),'authorizes':[]},indent=2)+'\n')
 with dest.open('w') as o,err.open('w') as e:proc=subprocess.run([PY,'-B',*args],cwd=R,stdout=o,stderr=e,check=False)
 assert proc.returncode==0,label+' failed; inspect raw output'
 return json.loads(dest.read_text().splitlines()[-1])
assert read('logs/acceptance-trusted-main-loader-fix-20261026/compatibility-checkpoint.json')['state']=='passed','Existing compatibility process has not passed; do not continue'
for name,expected in [('compatibility-successor-smoke.xml',1),('GREEN-final-focused.xml',33)]:
 tree=E.parse(LOG/name);cases=tree.findall('.//testcase');assert len(cases)==expected and not tree.findall('.//failure') and not tree.findall('.//error') and not tree.findall('.//skipped'),name
compatibility=read('logs/acceptance-trusted-main-loader-fix-20261026/compatibility-checkpoint.json');assert len(compatibility['completed'])==11
for node in compatibility['completed']:
 proof=LOG/compatibility['case_proofs'][node];cases=[x for x in E.parse(proof).findall('.//testcase') if x.attrib['name']==node.split('::')[-1]];assert len(cases)==1 and cases[0].find('failure') is None and cases[0].find('error') is None and cases[0].find('skipped') is None,node
assert read('logs/acceptance-trusted-main-loader-fix-20261026/package-validation-final.json')['status']=='pass'
assert subprocess.check_output(['git','symbolic-ref','--short','HEAD'],text=True).strip()=='acceptance/knowledge-query-final-content-20261026','Unexpected branch; do not commit or proceed'
assert subprocess.check_output(['git','rev-parse','refs/heads/main'],text=True).strip()=='a1e783c569cb5a78ea8728c83518fd13c73a99e8','Actual main drifted; preserve checkpoint'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==BEFORE
actual={row[3:] for row in subprocess.check_output(['git','status','--porcelain'],text=True).splitlines()};assert actual==set(FILES),actual
subprocess.run(['git','add','--',*FILES],check=True);subprocess.run(['git','commit','-m','fix(acceptance): isolate immutable main knowledge validation'],check=True)
HOST=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert subprocess.check_output(['git','status','--porcelain'],text=True)==''
put('logs/acceptance-trusted-main-loader-fix-20261026/compatibility-source-scope.json',{'kind':'Evidence reuse limits, not receipt conversion','unchanged_35_checks':'Original raw compatibility.xml; no claim all ran on final candidate','pre_root_guard_composition_positives':['compatibility-successor-smoke.xml','compatibility-successor.xml successful cases only'],'final_root_guard_proof':'GREEN-final-focused.xml includes real valid-root and nested-main rejection; actual-context-freeze-final.json uses final code','final_source_remaining_composition_cases':'compatibility-r3-*.xml, plus later actual native Acceptance controlled receipts','not_claimed':'No old run is relabeled as execution on the final commit; no zero-regression guarantee','authorizes':[]})
put('logs/acceptance-trusted-main-loader-fix-20261026/stable-source.json',{'candidate':HOST,'predecessor':BEFORE,'actual_main':subprocess.check_output(['git','rev-parse','main'],text=True).strip(),'files':[{ 'path':p,'sha256':sha(p)} for p in FILES],'authorizes':[]})
patch=subprocess.check_output(['git','diff',BEFORE,HOST,'--',*FILES]);(LOG/'implementation.patch').write_bytes(patch)
old_manifest=read(OLD+'/candidate-content-manifest.v1.json');paths=sorted({x['candidate_path'] or x['baseline_path'] for x in old_manifest['files']}|set(FILES));baseline=[];candidate=[]
for p in paths:
 before=subprocess.run(['git','show',BASE+':'+p],capture_output=True);bhash='sha256:'+hashlib.sha256(before.stdout).hexdigest() if before.returncode==0 else None;current=sha(p)
 if bhash:baseline.append({'path':p,'roles':['implementation'],'sha256':bhash,'inclusion_reason':'Explicit current scope; immutable source baseline'})
 candidate.append({'change_type':'modified' if bhash else 'added','roles':['implementation'],'baseline_path':p if bhash else None,'baseline_sha256':bhash,'candidate_path':p,'candidate_sha256':current,'inclusion_reason':'Approved knowledge query, route repair and offline immutable-main isolation'})
put(NEW+'/baseline-content-manifest.v1.json',dict(read(OLD+'/baseline-content-manifest.v1.json'),files=baseline));put(NEW+'/candidate-content-manifest.v1.json',dict(old_manifest,files=candidate))
registry=read(OLD+'/command-registry.projection-input.v1.json')
for command in registry['commands']:command['argv']=[x.replace(OLD,NEW) for x in command['argv']]
# Four actions remain. The existing short regression action now also covers
# the directly changed isolation owner; no long business/compatibility rerun.
reg=next(c for c in registry['commands'] if c['id']=='validate-acceptance-routing');reg['argv']=['-B','-m','pytest','-q','-p','no:cacheprovider',S+'tests/test_toolchain_domain.py',S+'tests/test_trusted_knowledge_validator.py',S+'tests/test_knowledge_context.py',S+'tests/test_knowledge_degraded_execution.py']
put(NEW+'/command-registry.projection-input.v1.json',registry);put(NEW+'/action-dag.v1.json',read(OLD+'/action-dag.v1.json'))
projection=read(OLD+'/acceptance-input-projection.final.v1.json');projection['candidateCommit']=HOST;projection['actionRegistry']={'path':NEW+'/command-registry.projection-input.v1.json','sha256':sha(NEW+'/command-registry.projection-input.v1.json')};projection['requirements']=[x.replace('narrow route regression','narrow route and immutable-main isolation regression') for x in projection['requirements']];put(NEW+'/acceptance-input-projection.v1.json',projection)
put(NEW+'/acceptance-authority.v1.json',dict(read(OLD+'/acceptance-authority.v1.json'),plan_id='knowledge-query-main-isolated-20261026'))
contract=R/S/'references/skill-input-contract.v1.json';(R/NEW/'skill-input-contract.v1.json').write_bytes(contract.read_bytes())
context=NEW+'/knowledge-context.refactor-acceptance.current.v1.json';put(NEW+'/knowledge-context.freeze.v1.json',{'schema_version':'jimuyun.knowledge-consumer-freeze.v1','context_path':'knowledge-context.refactor-acceptance.current.v1.json','context_sha256':sha(context),'authorizes':[]})
sys.path.insert(0,str(R/S/'scripts'));from model_routing import build_route_decision
route=build_route_decision();assert route['requestedExecution']['launchMode']=='none' and route['actualExecution'] is None;put('logs/acceptance-trusted-main-loader-fix-20261026/deterministic-route-decision.json',route)
request=read(OLD+'/skill-input-request.contained.v2.json');request['storage']=NEW+'/skill-input-v2/acceptance';request['plan_id']='knowledge-query-main-isolated-20261026';bound={'authority':'acceptance-authority.v1.json','contract':'skill-input-contract.v1.json','knowledge_freeze':'knowledge-context.freeze.v1.json','registry':'command-registry.projection-input.v1.json'}
request['bindings']={k:{'path':NEW+'/'+v,'sha256':sha(NEW+'/'+v)} for k,v in bound.items()};src=NEW+'/acceptance-input-projection.v1.json';request['sources'][0]['path']=src;request['sources'][0]['sha256']=sha(src);request['inputs']={k:[src] for k in request['inputs']};put(NEW+'/skill-input-request.v2.json',request)
prepared=run('skill-input-prepare',['scripts/python/skill_input_v2.py','prepare','--request',NEW+'/skill-input-request.v2.json']);assert prepared['status']=='prepared'
for page in range(prepared['page_count']):consumed=run('skill-input-consume-'+str(page+1),['scripts/python/skill_input_v2.py','consume','--plan-id',prepared['plan_id'],'--attempt-id',prepared['attempt_id'],'--max-pages','1'])
assert consumed['status']=='complete';finished=run('skill-input-finish',['scripts/python/skill_input_v2.py','finish','--plan-id',prepared['plan_id'],'--attempt-id',prepared['attempt_id']]);assert finished['status']=='ready'
pointer=request['storage']+'/current.v1.json';run('skill-input-validate',['scripts/python/skill_input_v2.py','validate','--pointer',pointer,'--consumer','run-refactor-implementation-acceptance','--operation','acceptance','--contract',NEW+'/skill-input-contract.v1.json'])
attempt=R/'.skill-input-work'/prepared['plan_id']/prepared['attempt_id'];assert json.loads((attempt/'attempt.json').read_text())['status']=='succeeded'
assert subprocess.check_output(['git','status','--porcelain'],text=True)==''
put('logs/acceptance-trusted-main-loader-fix-20261026/preparation-completed.json',{'at':now(),'candidate':HOST,'changed_source_paths':paths,'isolation_source_paths':FILES,'prepared':NEW,'current_pointer':pointer,'completed_attempt':str(attempt.relative_to(R)),'completed_attempt_retained_in_place':True,'attempt_files':[{ 'path':str(p.relative_to(R)),'sha256':sha(str(p.relative_to(R)))} for p in sorted(attempt.rglob('*')) if p.is_file()],'four_registered_actions':True,'context_bytes':(R/src).stat().st_size,'authorizes':[]})
print(json.dumps({'event':'native-preparation-completed','candidate':HOST,'source_paths':len(paths),'attempt_retained':True,'pointer':pointer,'at':now()}),flush=True)

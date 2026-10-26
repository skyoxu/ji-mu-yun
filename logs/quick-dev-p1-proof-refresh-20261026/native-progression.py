"""Task orchestration only: public Quick Dev commands, no evidence-writer replacement."""
from pathlib import Path
import collections,datetime,hashlib,json,os,subprocess,sys,time
ROOT=Path('/workspace/ji-mu-yun-review-publication');os.chdir(ROOT)
BASE=Path('logs/quick-dev-p1-proof-refresh-20261026');BASE.mkdir(exist_ok=True)
PLAN='execution-plans/2026-10-26-vdd-knowledge-query-p1-static-bindings'
HOST='5b585094288f1958539d88261d78467865cfe8e7';PREVIOUS='logs/quick-dev-final-slices-20261025-v6'
PYTHON='/workspace/scratch/stage5-p1-tests-20261026/bin/python'
ENV=dict(os.environ,PATH='/workspace/scratch/stage5-p1-tests-20261026/bin:'+os.environ['PATH'],TMPDIR='/workspace/scratch/quick-dev-pytest-tmp-v2',PYTEST_ADDOPTS='-o tmp_path_retention_policy=failed')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
write=lambda p,v:Path(p).write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
digest=lambda p:'sha256:'+hashlib.sha256(Path(p).read_bytes()).hexdigest()
bundle=read(Path(PLAN)/'semantic-plan-bundle.v1.json'); preferred=['S2','S5','S6','S1','S3','S7','S8','S4','S11','S12','S10','S9']
slices={x['slice_id']:x for x in bundle['slices']};order=[]
while len(order)<len(slices):
 ready=[s for s in preferred if s not in order and set(slices[s]['depends_on'])<=set(order)]
 if not ready:raise RuntimeError('No legal topological successor')
 order.append(ready[0])
files=['scripts/toolchain/knowledge_query/adapter.py','scripts/toolchain/knowledge_query/tests/test_planning_query.py','tests/toolchain/knowledge_query/test_planning_boundaries.py','scripts/vdd/compile_plan.py','.agents/skills/vdd-execution-plan/scripts/quick_dev_handoff.py']
frozen={'host':HOST,'plan':PLAN,'plan_file_sha256':digest(Path(PLAN)/'semantic-plan-bundle.v1.json'),'files':{p:digest(p) for p in files},'order':order,'Windows_original':'logs/windows-p1-result-40293104427/verified-original'}
fp=BASE/'frozen-inputs.json'
if fp.exists():assert read(fp)==frozen,'Input drift from saved proof run'
else:write(fp,frozen)
status=read(BASE/'checkpoint.json') if (BASE/'checkpoint.json').exists() else {'completed_slices':[],'commands':{},'state':'running','authorizes':[]}
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def guard():
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HOST
 assert all(digest(p)==h for p,h in frozen['files'].items()),'Frozen input drift'
 assert digest(Path(PLAN)/'semantic-plan-bundle.v1.json')==frozen['plan_file_sha256']
def command(sid,action,extra=(),run=None):
 guard();key=sid+'-'+action;run=run or str(BASE/(sid+'-current'))
 if status['commands'].get(key,{}).get('exit_code')==0:
  return read(BASE/(key+'.stdout.json'))
 stdout=BASE/(key+'.stdout.json');stderr=BASE/(key+'.stderr.txt')
 if stdout.exists() or stderr.exists():raise RuntimeError('Partial command preserved; explicit recovery required: '+key)
 argv=[PYTHON,'-B','scripts/quick_dev/run.py','--plan',PLAN,'--slice',sid,'--profile','standard','--action',action,'--run-dir',run,'--unit-timeout-seconds','1800','--idle-timeout-seconds','600',*extra]
 write(BASE/(key+'.command.json'),{'argv':argv,'started_at':now(),'unit_seconds':1800,'idle_seconds':600})
 status.update(state='running',current_slice=sid,current_action=action,command_started_at=now());write(BASE/'checkpoint.json',status)
 print(json.dumps({'event':'native-command-started','slice':sid,'action':action,'at':now(),'completed_slices':len(status['completed_slices'])}),flush=True)
 started=time.monotonic()
 with stdout.open('wb') as out,stderr.open('wb') as err:result=subprocess.run(argv,cwd=ROOT,env=ENV,stdout=out,stderr=err)
 raw=stdout.read_text(encoding='utf-8');value=json.loads(raw.splitlines()[-1]) if raw.strip() else {}
 status['commands'][key]={'exit_code':result.returncode,'elapsed_seconds':time.monotonic()-started,'completed_at':now(),'status':value.get('status'),'predicate_result':value.get('predicate_result'),'stdout':str(stdout),'stderr':str(stderr)}
 write(BASE/'checkpoint.json',status)
 print(json.dumps({'event':'native-command-returned','slice':sid,'action':action,**status['commands'][key]}),flush=True)
 if result.returncode or value.get('predicate_result') is False or value.get('status') in {'blocked','repair-vdd','worker-required','stage-reentry-blocked'}:
  status['state']='blocked';write(BASE/'checkpoint.json',status);raise RuntimeError('Native boundary blocked: '+key+' '+raw[-1600:])
 return value
try:
 for sid in order:
  if sid in status['completed_slices']:continue
  run=str(BASE/(sid+'-current'));roots_path=BASE/(sid+'-current.snapshot-roots.json')
  rows=read(Path(PREVIOUS)/(sid+'-current.snapshot-roots.json'))
  for row in rows:
   for key in ['repository_relative_posix_path','repository_relative_posix_paths']:
    if key in row:
     def change(p):return p.replace('execution-plans/2026-10-25-vdd-knowledge-query-caller-runtime-role',PLAN).replace(PREVIOUS+'/'+sid+'-current',run)
     row[key]=[change(p) for p in row[key]] if isinstance(row[key],list) else change(row[key])
   if row['root_kind']=='source':row['repository_relative_posix_paths']=sorted(set(row['repository_relative_posix_paths']+['logs/windows-p1-result-40293104427/verified-original']))
  if roots_path.exists():assert read(roots_path)==rows
  else:write(roots_path,rows)
  command(sid,'preflight')
  command(sid,'author-red')
  probe=command(sid,'run-probe')
  dispositions=collections.Counter(x['disposition'] for x in probe['behavior_dispositions'])
  if set(dispositions)-{'present'}:raise RuntimeError('Actual current behavior needs repair: '+sid+' '+str(dispositions))
  command(sid,'run-regression')
  command(sid,'validate-slice',['--snapshot-roots',str(roots_path),'--source-commit',HOST,'--base-commit','965df2e34f71ef197fffd8afb68f037688486ca2','--out',str(BASE/(sid+'-slice-ready.json'))])
  command(sid,'run-terminal')
  status['completed_slices'].append(sid);status['last_real_progress_at']=now();write(BASE/'checkpoint.json',status)
  print(json.dumps({'event':'slice-complete','slice':sid,'completed':len(status['completed_slices']),'total':len(order),'at':now()}),flush=True)
 # Every per-slice snapshot input is frozen. Deduplicate only identical paths
 # within each root kind; no independent coverage edge or dependency is removed.
 q8=BASE/'Q8';q8.mkdir(exist_ok=True);predecessors=[];by_kind={}
 for sid in order:
  result_path=BASE/(sid+'-slice-ready.json');result=read(result_path)
  from_value='sha256:'+hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
  predecessors.append({'slice_id':sid,'run_root':str(BASE/(sid+'-current')),'result_ref':str(result_path),'result_sha256':from_value})
  for row in read(BASE/(sid+'-current.snapshot-roots.json')):
   by_kind.setdefault(row['root_kind'],set()).update(row.get('repository_relative_posix_paths',[row.get('repository_relative_posix_path')]))
 q8roots=[{'root_kind':kind,'inclusion_reason':'Current P1 proof closure; exact path union without duplicate roots','repository_relative_posix_paths':sorted(paths)} for kind,paths in by_kind.items()]
 write(q8/'predecessors.json',predecessors);write(q8/'snapshot-roots.json',q8roots)
 command(order[0],'implementation-complete',['--snapshot-roots',str(q8/'snapshot-roots.json'),'--predecessors',str(q8/'predecessors.json'),'--source-commit',HOST,'--base-commit','965df2e34f71ef197fffd8afb68f037688486ca2','--out',str(q8/'implementation-complete-result.v2.json')],run=str(q8))
 status['state']='completed';status['stopped_at']='Q8';status['completed_at']=now();write(BASE/'checkpoint.json',status)
 print(json.dumps({'event':'Q8-complete','at':now(),'completed_slices':status['completed_slices']}),flush=True)
except Exception as e:
 status['state']='blocked';status['error']=str(e);status['last_status_at']=now();write(BASE/'checkpoint.json',status);print(json.dumps({'event':'stopped','error':str(e),'at':now()}),flush=True);raise

"""Task-local public entry orchestration; no evidence schema or gate replacement."""
from pathlib import Path
import json,hashlib,subprocess,os,sys,time,datetime,shutil
ROOT=Path('/workspace/ji-mu-yun-acceptance-candidate-20261026');os.chdir(ROOT)
BASE=Path('logs/acceptance-main-isolated-proof-refresh-20261026');OLD=Path('logs/acceptance-proof-refresh-20261026-r2');PLAN='execution-plans/2026-10-26-vdd-knowledge-query-p1-static-bindings';HOST=json.loads((ROOT/'logs/acceptance-trusted-main-loader-fix-20261026/preparation-completed.json').read_text())['candidate'];PYTHON='/workspace/scratch/stage5-p1-tests-20261026/bin/python'
ENV=dict(os.environ,PATH='/workspace/scratch/stage5-p1-tests-20261026/bin:'+os.environ['PATH'],TMPDIR='/workspace/scratch/quick-dev-pytest-tmp-v2',PYTEST_ADDOPTS='-o tmp_path_retention_policy=failed')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
write=lambda p,v:Path(p).write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
sha=lambda p:'sha256:'+hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
bundle=read(Path(PLAN)/'semantic-plan-bundle.v1.json');order=['S2','S5','S6','S1','S3','S7','S8','S4','S11','S12','S10','S9'];slices={q['slice_id']:q for q in bundle['slices']};seen=set()
for sid in order:assert set(slices[sid]['depends_on'])<=seen;seen.add(sid)
preparation=read(Path('logs/acceptance-trusted-main-loader-fix-20261026/preparation-completed.json'))
files=list(preparation['changed_source_paths'])+[p['path'] for p in preparation['attempt_files']]
assert read(Path('logs/acceptance-trusted-main-loader-fix-20261026/compatibility-checkpoint.json'))['state']=='passed'
BASE.mkdir(exist_ok=False)
frozen={p:sha(p) for p in files};frozen[PLAN+'/semantic-plan-bundle.v1.json']=sha(Path(PLAN)/'semantic-plan-bundle.v1.json');write(BASE/'frozen-inputs.json',{'host':HOST,'files':frozen,'no_source_changes_after_this_point':True,'reused_probe_source':str(OLD),'actual_source_difference_from_original':'Immutable-main isolation five source files plus completed Skill-input attempt; actual full input manifests invalidate, not Git SHA alone','original_receipts_unchanged':True})
status={'completed_slices':[],'commands':{},'copied_probe_predecessors':{},'state':'prepared','authorizes':[]};write(BASE/'checkpoint.json',status)
def guard():
 assert subprocess.check_output(['git','symbolic-ref','--short','HEAD'],text=True).strip()=='acceptance/knowledge-query-final-content-20261026','Unexpected branch; do not commit or proceed'
 assert subprocess.check_output(['git','rev-parse','refs/heads/main'],text=True).strip()=='a1e783c569cb5a78ea8728c83518fd13c73a99e8','Actual main drifted; preserve checkpoint'
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==HOST
 assert all(sha(p)==v for p,v in frozen.items()),'Source drift'
 assert shutil.disk_usage(ROOT).free>150*1024*1024,'Insufficient task disk space; preserve evidence and stop'
def command(sid,action,extra=(),run=None):
 guard();key=sid+'-'+action;run=run or str(BASE/(sid+'-current'));argv=[PYTHON,'-B','scripts/quick_dev/run.py','--plan',PLAN,'--slice',sid,'--profile','standard','--action',action,'--run-dir',run,'--unit-timeout-seconds','1800','--idle-timeout-seconds','600',*extra]
 out=BASE/(key+'.stdout.json');err=BASE/(key+'.stderr.txt');assert not out.exists() and not err.exists()
 write(BASE/(key+'.command.json'),{'argv':argv,'started_at':now(),'unit_seconds':1800,'idle_seconds':600});status.update(state='running',current_slice=sid,current_action=action,started_at=now());write(BASE/'checkpoint.json',status)
 print(json.dumps({'event':'native-start','slice':sid,'action':action,'completed':len(status['completed_slices']),'at':now()}),flush=True);start=time.monotonic()
 with out.open('wb') as o,err.open('wb') as e:proc=subprocess.run(argv,cwd=ROOT,env=ENV,stdout=o,stderr=e)
 raw=out.read_text(encoding='utf-8');v=json.loads(raw.splitlines()[-1]) if raw.strip() else {};rec={'exit_code':proc.returncode,'seconds':time.monotonic()-start,'finished_at':now(),'predicate_result':v.get('predicate_result'),'status':v.get('status')};status['commands'][key]=rec;write(BASE/'checkpoint.json',status);print(json.dumps({'event':'native-return','slice':sid,'action':action,**rec}),flush=True)
 if proc.returncode or v.get('predicate_result') is False or v.get('status') in {'blocked','repair-vdd','worker-required','stage-reentry-blocked'}:raise RuntimeError(key+' blocked: '+raw[-1200:])
 return v
try:
 # Transport only exact immutable Q2/probe predecessor bytes. Stale positive stages
 # are not copied into successor runs. Every probe is accepted only by native reentry.
 for sid in order:
  run=BASE/(sid+'-current');(run/'descriptors').mkdir(parents=True);(run/'canonical-evidence').mkdir();source=OLD/(sid+'-current')
  shutil.copy2(source/'descriptors/probe.json',run/'descriptors/probe.json');shutil.copytree(source/'canonical-evidence/probe',run/'canonical-evidence/probe');assert sha(source/'descriptors/probe.json')==sha(run/'descriptors/probe.json')
  copied={q.relative_to(source).as_posix():sha(q) for q in (source/'canonical-evidence/probe').rglob('*') if q.is_file()};assert all(sha(run/p)==v for p,v in copied.items());status['copied_probe_predecessors'][sid]={'source_run':str(source),'descriptor_sha256':sha(source/'descriptors/probe.json'),'files':copied,'not_rebound':True}
  roots=read(OLD/(sid+'-current.snapshot-roots.json'))
  for row in roots:
   for key in ['repository_relative_posix_path','repository_relative_posix_paths']:
    if key in row:
     def repl(p):return p.replace(str(OLD)+'/'+sid+'-current',str(run))
     row[key]=[repl(p) for p in row[key]] if isinstance(row[key],list) else repl(row[key])
  for row in roots:
   if row['root_kind']=='source':
    values=row.get('repository_relative_posix_paths',[row.get('repository_relative_posix_path')]);values=sorted(set(values+preparation['isolation_source_paths']));row.pop('repository_relative_posix_path',None);row['repository_relative_posix_paths']=values
  write(BASE/(sid+'-current.snapshot-roots.json'),roots)
 write(BASE/'checkpoint.json',status)
 for sid in order:
  command(sid,'preflight');v=command(sid,'run-probe');old=read(OLD/(sid+'-current/canonical-evidence/probe/stage-result.v2.json'));assert v==old,'Native probe result differs from transported original'
  status['copied_probe_predecessors'][sid]['native_reentry_same_original']=True;write(BASE/'checkpoint.json',status)
  command(sid,'run-regression');command(sid,'validate-slice',['--snapshot-roots',str(BASE/(sid+'-current.snapshot-roots.json')),'--source-commit',HOST,'--base-commit','965df2e34f71ef197fffd8afb68f037688486ca2','--out',str(BASE/(sid+'-slice-ready.json'))]);command(sid,'run-terminal');status['completed_slices'].append(sid);status['last_real_progress']=now();write(BASE/'checkpoint.json',status);print(json.dumps({'event':'slice-current','slice':sid,'count':len(status['completed_slices']),'at':now()}),flush=True)
 sys.path[:0]=[str(ROOT/'.agents/skills/quick-dev-tdd-adapter/tools'),str(ROOT/'scripts')]
 from runtime_evidence import sha256_value
 q8=BASE/'Q8';q8.mkdir();pre=[];kinds={}
 for sid in order:
  ref=BASE/(sid+'-slice-ready.json');pre.append({'slice_id':sid,'run_root':str(BASE/(sid+'-current')),'result_ref':str(ref),'result_sha256':sha256_value(read(ref))})
  for row in read(BASE/(sid+'-current.snapshot-roots.json')):kinds.setdefault(row['root_kind'],set()).update(row.get('repository_relative_posix_paths',[row.get('repository_relative_posix_path')]))
 roots=[{'root_kind':k,'inclusion_reason':'Immutable-main isolation proof closure; exact path union without duplicate roots','repository_relative_posix_paths':sorted(v)} for k,v in kinds.items()];write(q8/'predecessors.json',pre);write(q8/'snapshot-roots.json',roots)
 command(order[0],'implementation-complete',['--snapshot-roots',str(q8/'snapshot-roots.json'),'--predecessors',str(q8/'predecessors.json'),'--source-commit',HOST,'--base-commit','965df2e34f71ef197fffd8afb68f037688486ca2','--out',str(q8/'implementation-complete-result.v2.json')],run=str(q8))
 status.update(state='Q8-completed',completed_at=now());write(BASE/'checkpoint.json',status);print(json.dumps({'event':'Q8-current','at':now(),'completed':len(status['completed_slices'])}),flush=True)
except Exception as exc:
 status.update(state='blocked',error=str(exc),at=now());write(BASE/'checkpoint.json',status);print(json.dumps({'event':'stopped','error':str(exc),'at':now()}),flush=True);raise

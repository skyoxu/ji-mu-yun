"""Correct caller-owned Q8 reference hashes; preserve all native originals."""
from pathlib import Path
import datetime,hashlib,json,math,os,subprocess,sys,time,itertools
ROOT=Path('/workspace/ji-mu-yun-review-publication');os.chdir(ROOT)
BASE=Path('logs/quick-dev-p1-proof-refresh-20261026')
sys.path[:0]=['.agents/skills/quick-dev-tdd-adapter/tools','scripts']
from runtime_evidence import sha256_value
from execution_environment import execution_environment
read=lambda p:json.loads(Path(p).read_text())
write=lambda p,d:Path(p).write_text(json.dumps(d,indent=2)+'\n')
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
frozen=read(BASE/'frozen-inputs.json');status=read(BASE/'checkpoint.json')
assert len(status['completed_slices'])==12
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==frozen['host']
assert all('sha256:'+hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in frozen['files'].items())
assert 'sha256:'+hashlib.sha256((Path(frozen['plan'])/'semantic-plan-bundle.v1.json').read_bytes()).hexdigest()==frozen['plan_file_sha256']
rows=read(BASE/'Q8/predecessors.json');corrected=[];diff=[]
for row in rows:
    ready=read(row['result_ref']);assert ready['status']=='pass' and ready['slice_id']==row['slice_id']
    changed=dict(row,result_sha256=sha256_value(ready));corrected.append(changed)
    assert {k:v for k,v in row.items() if k!='result_sha256'}=={k:v for k,v in changed.items() if k!='result_sha256'}
    diff.append({'slice_id':row['slice_id'],'old_hash':row['result_sha256'],'native_canonical_hash':changed['result_sha256']})
write(BASE/'Q8/predecessors.canonical.json',corrected)
write(BASE/'Q8/predecessor-assembly-diff.json',{'cause':'Caller omitted canonical JSON final newline; originals are unchanged','changed_only':'result_sha256 in caller input','rows':diff})
PYTHON='/workspace/scratch/stage5-p1-tests-20261026/bin/python'
env=dict(os.environ,PATH='/workspace/scratch/stage5-p1-tests-20261026/bin:'+os.environ['PATH'],TMPDIR='/workspace/scratch/quick-dev-pytest-tmp-v2',PYTEST_ADDOPTS='-o tmp_path_retention_policy=failed')
# The matching original launch had neither variable bound; require its exact hash.
env.pop('PYTHON',None);env.pop('PYTHONPATH',None)
env['_']='/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3'
expected=read(BASE/'S2-current/canonical-evidence/regression/reuse-request.v1.json')['input']['environment']['environment']
saved=dict(os.environ)
matching=[]
for py,depth,pp,marker,pwd in itertools.product([False,True],[1,2],[None,'scripts',str(ROOT/'scripts')],[saved.get('_'),'/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3'],[saved.get('PWD'),'/workspace',str(ROOT)]):
    trial=dict(saved,PATH=('/workspace/scratch/stage5-p1-tests-20261026/bin:'*depth)+saved['PATH'],TMPDIR='/workspace/scratch/quick-dev-pytest-tmp-v2',PYTEST_ADDOPTS='-o tmp_path_retention_policy=failed')
    if py:trial['PYTHON']=PYTHON
    else:trial.pop('PYTHON',None)
    if pp is None:trial.pop('PYTHONPATH',None)
    else:trial['PYTHONPATH']=pp
    if marker is not None:trial['_']=marker
    if pwd is not None:trial['PWD']=pwd
    os.environ.clear();os.environ.update(trial)
    actual=sha256_value(execution_environment())
    if actual==expected:matching.append(trial)
os.environ.clear();os.environ.update(saved)
assert matching,'Known original launch bindings cannot reproduce the recorded environment'
env=matching[0]
assert all(candidate==env for candidate in matching),'Ambiguous environment recovery'
actual=expected
write(BASE/'Q8/retry-environment-check.json',{'matches_original_environment_identity':True,'environment_sha256':actual,'raw_environment_not_saved':True})
old=status['commands']['S2-implementation-complete'];assert old['exit_code']!=0
stable_retry=(BASE/'checkpoint.before-validator-restore.json').exists()
restored=(BASE/'checkpoint.before-q8-input-correction.json').exists()
backup=BASE/('checkpoint.before-metadata-seal-retry.json' if stable_retry else ('checkpoint.before-validator-restore.json' if restored else 'checkpoint.before-q8-input-correction.json'))
assert not backup.exists();write(backup,status)
spent=old['elapsed_seconds']+old.get('prior_same_unit_elapsed_seconds',0)
remaining=1800-math.ceil(spent);assert remaining>0
cmd=read(BASE/'S2-implementation-complete.command.json');argv=cmd['argv']
argv[argv.index('--predecessors')+1]=str(BASE/'Q8/predecessors.canonical.json')
argv[argv.index('--unit-timeout-seconds')+1]=str(remaining)
tag='stable-inputs' if stable_retry else ('restored-validator' if restored else 'canonical-predecessors')
out=BASE/('S2-implementation-complete.'+tag+'.stdout.json');err=BASE/('S2-implementation-complete.'+tag+'.stderr.txt')
cf=BASE/('S2-implementation-complete.'+tag+'.command.json')
assert not out.exists() and not err.exists()
write(cf,{'argv':argv,'started_at':now(),'unit_seconds':remaining,'idle_seconds':600,'prior_same_unit_elapsed_seconds':spent,'bounded_retry':3 if stable_retry else (2 if restored else 1)})
status['commands']['S2-implementation-complete.'+('diagnostic-metadata-seal-error' if stable_retry else ('canonical-input-validator-error' if restored else 'initial-assembly-error'))]=old
status.update(state='running',current_slice='S2',current_action='implementation-complete',command_started_at=now(),error=None)
write(BASE/'checkpoint.json',status)
started=time.monotonic()
with out.open('wb') as stdout,err.open('wb') as stderr:
    proc=subprocess.run(argv,cwd=ROOT,env=env,stdout=stdout,stderr=stderr)
result=json.loads(out.read_text().splitlines()[-1]) if out.stat().st_size else {}
status['commands']['S2-implementation-complete']={'exit_code':proc.returncode,'elapsed_seconds':time.monotonic()-started,'completed_at':now(),'status':result.get('status'),'stdout':str(out),'stderr':str(err),'command_file':str(cf),'prior_same_unit_elapsed_seconds':spent}
ok=proc.returncode==0 and result.get('status')=='pass' and result.get('predicate')=='implementation-complete'
status.update(state='completed' if ok else 'blocked',stopped_at='Q8' if ok else None,completed_at=now(),error=None if ok else result)
write(BASE/'checkpoint.json',status)
print(json.dumps({'Q8_exit':proc.returncode,'status':result.get('status'),'reason':result.get('reason'),'elapsed_seconds':status['commands']['S2-implementation-complete']['elapsed_seconds']}),flush=True)
raise SystemExit(0 if ok else 1)

"""Serial task continuation; only existing approved native entries produce proof."""
from pathlib import Path
import datetime,json,os,signal,subprocess,sys,time
R=Path('/workspace/ji-mu-yun-acceptance-candidate-20261026');sys.path.insert(0,str(R/'scripts'))
from workflow_unit_budget import terminate_tree
L=R/'logs/acceptance-trusted-main-loader-fix-20261026';FILE=L/'continuation-checkpoint.json';assert not FILE.exists();PY='/workspace/scratch/stage5-p1-tests-20261026/bin/python';active=None
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
state={'pid':os.getpid(),'state':'waiting-existing-compatibility','at':now(),'authorizes':[]}
def save():FILE.write_text(json.dumps(state,indent=2)+'\n')
def stop(_signal,_frame):
 if active is not None:terminate_tree(active)
 state.update(state='cancelled',at=now());save();raise SystemExit(130)
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop);save()
def exact_process(script):
 for p in Path('/proc').iterdir():
  if p.name.isdigit():
   try:args=(p/'cmdline').read_bytes().split(b'\0')
   except (OSError,PermissionError):continue
   if script.encode() in args:return int(p.name)
 return None
existing=exact_process('/tmp/resume_acceptance_loader_compat_20261026_r3.py');assert existing,'No existing compatibility driver; inspect checkpoint instead of assuming success';state['existing_compatibility_pid']=existing;save();print(json.dumps(state),flush=True)
while True:
 current=json.loads((L/'compatibility-checkpoint.json').read_text())
 if current['state']=='passed' and exact_process('/tmp/resume_acceptance_loader_compat_20261026_r3.py') is None:break
 if current['state']=='failed':state.update(state='blocked',reason='Existing compatibility failed',at=now());save();raise SystemExit(1)
 if exact_process('/tmp/resume_acceptance_loader_compat_20261026_r3.py') is None:state.update(state='blocked',reason='Existing compatibility exited without success',at=now());save();raise SystemExit(1)
 time.sleep(.5)
for label,script in [('native-preparation','/tmp/prepare_acceptance_main_isolation_20261026.py'),('affected-proof-refresh','/tmp/refresh_acceptance_main_isolation_proofs_20261026.py'),('native-Acceptance','/tmp/run_acceptance_main_isolated_20261026.py')]:
 state.update(state='running',stage=label,started_at=now());save();out=L/(label+'.driver.stdout.txt');err=L/(label+'.driver.stderr.txt');assert not out.exists();print(json.dumps({'event':'stage-start','stage':label,'at':now()}),flush=True)
 with out.open('wb') as o,err.open('wb') as e:
  active=subprocess.Popen([PY,'-B',script],cwd=R,stdout=o,stderr=e,start_new_session=True);state['active_pid']=active.pid;save();code=active.wait();active=None
 state.setdefault('completed_stages',[]).append({'stage':label,'exit_code':code,'finished_at':now()});save();print(json.dumps({'event':'stage-finish','stage':label,'exit_code':code,'at':now()}),flush=True)
 if code:state.update(state='blocked',at=now());save();raise SystemExit(code)
state.update(state='acceptance-passed-unpublished',at=now(),active_pid=None);save();print(json.dumps(state),flush=True)

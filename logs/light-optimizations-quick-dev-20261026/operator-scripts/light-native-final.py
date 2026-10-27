import argparse,json,os,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('slice');p.add_argument('run');p.add_argument('actions');p.add_argument('extra',nargs=argparse.REMAINDER);a=p.parse_args()
r=Path('/workspace/ji-mu-yun-light-optimizations');l=r/'logs/light-optimizations-quick-dev-20261026/final-console';l.mkdir(exist_ok=True)
env=dict(os.environ,PATH='/tmp/ji-mu-yun-light-qd-venv/bin:'+os.environ['PATH'],TMPDIR=str(r/'logs/light-optimizations-quick-dev-20261026/tmp'),PYTHONDONTWRITEBYTECODE='1')
for action in a.actions.split(','):
 argv=['/tmp/ji-mu-yun-light-qd-venv/bin/python','-B','scripts/quick_dev/run.py','--plan','execution-plans/2026-10-26-toolchain-light-optimizations-q2-boundary','--slice',a.slice,'--profile','standard','--action',action,'--run-dir',a.run,'--unit-timeout-seconds','1800','--idle-timeout-seconds','600',*a.extra]
 stem=a.slice+'-'+Path(a.run).name+'-'+action;out=l/(stem+'.stdout.txt');err=l/(stem+'.stderr.txt')
 if out.exists() or err.exists():raise SystemExit('Refusing to overwrite console originals: '+stem)
 with out.open('wb') as so,err.open('wb') as se:result=subprocess.run(argv,cwd=r,env=env,stdout=so,stderr=se)
 try:value=json.loads(out.read_text().splitlines()[-1])
 except (IndexError,ValueError):value={'reason':err.read_text()[-1500:]}
 print(json.dumps({'action':action,'slice':a.slice,'exit_code':result.returncode,'status':value.get('status'),'predicate_result':value.get('predicate_result'),'failure_family':value.get('failure_family'),'required_next_action':value.get('required_next_action'),'reason':value.get('reason'),'stdout':str(out.relative_to(r))}),flush=True)
 if result.returncode:raise SystemExit(result.returncode)

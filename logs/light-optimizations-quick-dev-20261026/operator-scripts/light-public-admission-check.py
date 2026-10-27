import hashlib,json,os,subprocess
from pathlib import Path
r=Path('/workspace/ji-mu-yun-light-optimizations');l=r/'logs/light-optimizations-quick-dev-20261026';d=l/'final-checks/public-admission';d.mkdir(parents=True,exist_ok=True)
def manifest(path):
 return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}
budget=r/'logs/workflow-unit-budgets/vdd';before=manifest(budget);out=l/'readonly-no-plan';assert not out.exists()
env=dict(os.environ)
for key in ('JIMUYUN_WORKFLOW_UNIT_EVENTS','JIMUYUN_WORKFLOW_UNIT_SECONDS','JIMUYUN_WORKFLOW_IDLE_SECONDS'):env.pop(key,None)
argv=['/tmp/ji-mu-yun-light-qd-venv/bin/python','-B','scripts/vdd/compile_plan.py','--requirements','docs/2026-10-26-toolchain-light-optimizations-requirements-v3.md','--out-dir',str(out.relative_to(r)),'--profile','resumable','--execution-profile','fast-ship','--admission-only']
p=subprocess.run(argv,cwd=r,env=env,capture_output=True);(d/'native.stdout.txt').write_bytes(p.stdout);(d/'native.stderr.txt').write_bytes(p.stderr);after=manifest(budget);value=json.loads(p.stdout)
(d/'observed.json').write_text(json.dumps({'authorizes':[],'argv':argv,'exit_code':p.returncode,'native_result':value,'vdd_budget_manifest_before':before,'vdd_budget_manifest_after':after,'output_exists':out.exists()},indent=2)+'\n')
assert p.returncode==0 and value['admission']['status']=='pending' and value['admission']['checks']['dependencies']['status']=='pending'
assert before==after and not out.exists()
print('Actual public admission-only returned pending; no VDD budget/run/plan output was created.')

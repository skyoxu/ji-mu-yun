"""Public explicit recovery and Q7 attempt; no original receipt writes."""
import json,os,subprocess,sys
from pathlib import Path
R=Path.cwd();L=R/'logs/quick-dev-q7-original-fix-20261025';RUN=Path('logs/quick-dev-final-slices-20261025-v4/S12-current');HOST='93d06e67b0276ec8cc2e7ae7298aff8ac8e5fbf6';BASE='965df2e34f71ef197fffd8afb68f037688486ca2';PLAN='execution-plans/2026-10-25-vdd-knowledge-query-caller-runtime-role';ROOTS=Path('logs/quick-dev-final-slices-20261025-v4/S12-current.snapshot-roots.json')
sys.path.insert(0,str(R/'.agents/skills/quick-dev-tdd-adapter/tools'))
from runtime_evidence import current_snapshot,sha256_value
stage=RUN/'canonical-evidence/regression';s=json.loads((stage/'stage-result.v2.json').read_text());r=json.loads((stage/'process-receipt.v2.json').read_text());o=json.loads((stage/'observation.v2.json').read_text())
snapshot=current_snapshot(R,json.loads(ROOTS.read_text()),source_commit=HOST,base_commit=BASE)
request={'schema':'quick-dev.recovery-input.v1','slice_id':'S12','run_id':RUN.name,'stage':'regression','candidate_hash':r['candidate_hash'],'selector_identity':s['selector_identity'],'receipt_ref':str(Path('canonical-evidence/regression/process-receipt.v2.json')),'receipt_sha256':sha256_value(r),'observation_ref':'canonical-evidence/regression/observation.v2.json','observation_sha256':sha256_value(o),'runtime_edges':[{'ref':x['path'],'sha256':x['sha256']} for x in s['runtime_edges']],'current_snapshot_sha256':snapshot['sha256']}
p=L/'S12-old-run-recovery-input.json';p.write_text(json.dumps(request,indent=2)+'\n')
env=dict(os.environ,TMPDIR='/workspace/scratch/quick-dev-pytest-tmp-v2',PYTEST_ADDOPTS='-o tmp_path_retention_policy=failed');env['PATH']='/tmp/vdd-pause-tests/bin:'+env['PATH']
base=[sys.executable,'-B','scripts/quick_dev/run.py','--plan',PLAN,'--slice','S12','--profile','standard','--run-dir',str(RUN),'--snapshot-roots',str(ROOTS),'--source-commit',HOST,'--base-commit',BASE,'--unit-timeout-seconds','1800','--idle-timeout-seconds','600']
for action,extra in [('recover',['--recovery-input',str(p)]),('validate-slice',['--out',str(L/'S12-old-run-ready.json')])]:
 with (L/('S12-old-'+action+'.stdout.json')).open('xb') as out,(L/('S12-old-'+action+'.stderr.txt')).open('xb') as err:
  result=subprocess.run(base+['--action',action]+extra,env=env,stdout=out,stderr=err)
 print(json.dumps({'action':action,'exit_code':result.returncode}),flush=True)
 if action=='recover' and result.returncode:break

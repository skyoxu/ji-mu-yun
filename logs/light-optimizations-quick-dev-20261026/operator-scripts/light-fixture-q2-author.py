import json,sys
from pathlib import Path
r=Path('/workspace/ji-mu-yun-light-optimizations')
sys.path.insert(0,str(r/'.agents/skills/quick-dev-tdd-adapter/tools'))
from worker_orchestrator import run_red_author
plan=r/'execution-plans/2026-10-27-toolchain-light-optimizations-fixture-ready'
value=run_red_author(workspace=r,plan_dir=plan,semantic_plan=plan/'semantic-plan-bundle.v1.json',slice_id='S1',timeout_seconds=1800,backend='host-session')
p=r/'logs/light-optimizations-quick-dev-20261026/fixture-legalization-20261027/q2-author-result.json'
with p.open('x') as f:f.write(json.dumps(value,indent=2)+'\n')
print(json.dumps(value),flush=True)

"""Acceptance operator: preserve the existing native per-command budget."""
import os,sys
from pathlib import Path
r=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(r/'scripts'))
from workflow_unit_budget import supervise
label,*argv=sys.argv[1:]
if label not in {'validate-vdd-contract','validate-code-review-route','validate-acceptance-routing','validate-acceptance-package'}:
    raise SystemExit('Unknown registered Acceptance unit')
tmp=Path('/tmp/light-acceptance-tests-20261027');tmp.mkdir(exist_ok=True)
env=dict(os.environ,TMPDIR=str(tmp),PYTHONDONTWRITEBYTECODE='1')
raise SystemExit(supervise(argv,cwd=r,directory=Path('/tmp/light-acceptance-budgets-20261027')/label,total=1800,idle=600,env=env))

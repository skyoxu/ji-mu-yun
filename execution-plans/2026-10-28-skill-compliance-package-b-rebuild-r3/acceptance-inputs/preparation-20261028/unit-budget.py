"""Bound registered Acceptance commands to the existing unit supervisor."""
import os,sys
from pathlib import Path
r=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(r/'scripts'))
from workflow_unit_budget import supervise
label,*argv=sys.argv[1:]
if label not in {'strict-quick-dev-tdd-adapter', 'strict-run-phase-bootstrap-review', 'strict-maintain-knowledge-base', 'validate-acceptance-package', 'strict-run-refactor-implementation-acceptance', 'validate-vdd-contract', 'strict-vdd-execution-plan', 'validate-code-review-route'}:
    raise SystemExit('Unknown registered Acceptance unit')
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
raise SystemExit(supervise(argv,cwd=r,directory=r.parent/'scratch/package-b-acceptance-unit-budgets-20261028'/label,total=1800,idle=600,env=env))

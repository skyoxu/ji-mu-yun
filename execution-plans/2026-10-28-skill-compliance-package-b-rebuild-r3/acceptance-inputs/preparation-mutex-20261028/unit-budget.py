"""Bound registered Acceptance commands to the existing unit supervisor."""
import os,sys
from pathlib import Path
r=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(r/'scripts'))
from workflow_unit_budget import supervise
label,*argv=sys.argv[1:]
if label not in ['validate-vdd-contract', 'validate-code-review-route', 'validate-acceptance-package', 'strict-vdd-execution-plan', 'strict-quick-dev-tdd-adapter', 'strict-run-phase-bootstrap-review', 'strict-run-refactor-implementation-acceptance', 'strict-maintain-knowledge-base', 'validate-skill-input-mutex']:
    raise SystemExit('Unknown registered Acceptance unit')
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
if label == 'validate-skill-input-mutex':
    env.update(CODEX_HOME=str(Path(__file__).parent/'test-config-fixture'),
               PYTHONPATH=str(r)+os.pathsep+str(r/'scripts/python'))
raise SystemExit(supervise(argv,cwd=r,directory=r.parent/'scratch/package-b-acceptance-unit-budgets-20261028'/label,total=1800,idle=600,env=env))

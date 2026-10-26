"""Supervised, isolated diagnostics; no formal RED or implementation claim."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'scripts'))
from workflow_unit_budget import supervise

env = dict(os.environ, TMPDIR='/workspace/scratch/quick-dev-pytest-tmp-v2',
           PYTEST_ADDOPTS='-o tmp_path_retention_policy=failed')
plan = 'execution-plans/2026-10-25-vdd-knowledge-query-caller-runtime-role'
for sid in ('S1', 'S12'):
    argv = [sys.executable, '-B', 'scripts/quick_dev/run.py', '--plan', plan,
        '--slice', sid, '--profile', 'standard', '--action', 'preflight',
        '--unit-timeout-seconds', '1800', '--idle-timeout-seconds', '600']
    with (OUT / (sid + '-preflight.stdout.json')).open('xb') as out:
        with (OUT / (sid + '-preflight.stderr.txt')).open('xb') as err:
            result = subprocess.run(argv, cwd=ROOT, env=env, stdout=out, stderr=err)
    if result.returncode:
        raise SystemExit(result.returncode)
test = OUT / 'test_counterexamples.py'
(OUT / 'diagnostic-input.json').write_text(json.dumps({
    'test_sha256': hashlib.sha256(test.read_bytes()).hexdigest(),
    'host': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'formal_RED': False, 'implementation_authority': False, 'authorizes': []}, indent=2) + '\n', encoding='utf-8')
argv = [sys.executable, '-B', '-m', 'pytest', str(test), '-q',
        '-W', 'ignore::pytest.PytestUnknownMarkWarning',
        '--junitxml=' + str(OUT / 'diagnostic-first.xml')]
raise SystemExit(supervise(argv, cwd=ROOT, directory=OUT / 'diagnostic-budget',
                           total=1800, idle=600, env=env))

"""ADR-0058: explicit immutable predecessor transfer, with no test execution."""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = HERE / 'owner-recovery-r11-read-only-budget'
sys.path.insert(0, str(ROOT / '.agents/skills/quick-dev-tdd-adapter/tools'))
sys.path.insert(0, str(ROOT / 'scripts/quick_dev'))
from runtime_evidence import canonical_bytes, create_immutable, load_json
from approved_budget_replay import replay_budget_transition, TRANSITION, OWNER_BASELINE
from read_only_reuse_audit import check

BEFORE = {'S2', 'S4', 'S7', 'S9', 'S10', 'S12', 'S13', 'S14', 'S15', 'S17', 'S18',
          'S19', 'S22', 'S24', 'S25', 'S27', 'S31', 'S33', 'S34', 'S36', 'S38', 'S42'}


def rel(path):
    return path.relative_to(ROOT).as_posix()


def write(path, value):
    create_immutable(path, canonical_bytes(value))


def prepare():
    original = json.loads((HERE / 'owner-recovery-r9-budget3/Q8-budget3-r9/predecessors.json').read_bytes())
    plan = json.loads((ROOT / 'compact-vdd-projection-request.815c032b.v1.json').read_bytes())['currentQuickDev']['semanticPlan']['path']
    bundle = load_json(ROOT / plan)
    selected, rows = [], []
    for prior in original:
        row = dict(prior)
        row['budget_compatibility'] = {'schema': 'quick-dev.approved-budget-compatibility.v1',
            'transition_commit': TRANSITION, 'owner_baseline': OWNER_BASELINE,
            'budget_epoch': 'before' if prior['slice_id'] in BEFORE else 'after', 'authorizes': []}
        selected.append(row)
        with replay_budget_transition(ROOT, row['budget_compatibility']):
            result = check(row, bundle)
        rows.append(result)
        print(prior['slice_id'] + ': ' + ('REUSABLE' if result['reusable'] else json.dumps(result['failures'])), flush=True)
    write(OUT / 'predecessors.json', selected)
    write(OUT / 'reuse-audit.json', {'schema': 'quick-dev.read-only-reuse-diagnostic.v1',
        'tests_launched': 0, 'evidence_rebound': False, 'authorizes': [], 'rows': rows,
        'reusable_slices': [r['slice_id'] for r in rows if r['reusable']],
        'blocked_slices': [r['slice_id'] for r in rows if not r['reusable']]})
    if not all(r['reusable'] for r in rows):
        raise RuntimeError('Preserved predecessor failures; no Q8 execution')
    return plan


def q8():
    plan = prepare()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    run = OUT / ('Q8-' + head[:8])
    roots = json.loads((HERE / 'owner-recovery-r9-budget3/Q8-budget3-r9/snapshot-roots.json').read_bytes())
    for row in roots:
        row['source_commit'] = head
        if row['root_kind'] == 'plan_state_transition':
            row['repository_relative_posix_path'] = rel(run)
    write(run / 'snapshot-roots.json', roots)
    args = [sys.executable, '-B', 'scripts/quick_dev/run.py', '--plan', str(Path(plan).parent),
        '--slice', 'S44', '--profile', 'standard', '--action', 'implementation-complete',
        '--snapshot-roots', rel(run / 'snapshot-roots.json'), '--predecessors', rel(OUT / 'predecessors.json'),
        '--source-commit', head, '--base-commit', '94870bbf087254e5e78fbb7752da42a4c56c3174',
        '--out', rel(run / 'implementation-complete-result.v2.json')]
    command = run / 'command'
    if command.exists():
        raise RuntimeError('Existing execution retained; inspect before explicit successor')
    command.mkdir(parents=True)
    print('START read-only public Q8', flush=True)
    started = time.monotonic()
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=3600)
    create_immutable(command / 'stdout.bin', result.stdout)
    create_immutable(command / 'stderr.bin', result.stderr)
    write(command / 'process.json', {'argv': args, 'head': head, 'exit_code': result.returncode,
        'elapsed_seconds': time.monotonic() - started, 'tests_launched': 0, 'authorizes': []})
    print(result.stdout.decode('utf-8', errors='replace'), flush=True)
    print(result.stderr.decode('utf-8', errors='replace'), flush=True)
    if result.returncode:
        raise RuntimeError('Public Q8 failed; original execution retained')


if __name__ == '__main__':
    q8() if 'Q8' in sys.argv else prepare()

#!/usr/bin/env python3
"""ADR-0041: select caller-session transport for the three native Skill entries."""
from pathlib import Path
import argparse
import os
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/sc'))
from host_session import ENV, TIMEOUT_ENV, MAX_TIMEOUT_SECONDS, session, timeout_budget
ENTRIES = {
    'vdd': 'scripts/vdd/compile_plan.py',
    'quick-dev': 'scripts/quick_dev/run.py',
    'acceptance': '.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--host-timeout-seconds', type=int,
                        help=f'Explicit per-worker host budget, 1..{MAX_TIMEOUT_SECONDS}; parent deadlines remain unchanged')
    parser.add_argument('skill', choices=ENTRIES)
    parser.add_argument('native_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.host_timeout_seconds is not None:
        try:
            timeout_budget(1, args.host_timeout_seconds)
        except ValueError as exc:
            parser.error(str(exc))
    directory, _ = session(args.session, ROOT)
    native = args.native_args
    if native[:1] == ['--']:
        native = native[1:]
    # Refuse an override that would silently invoke another provider.
    if any(x == '--llm-backend' or x.startswith('--llm-backend=') for x in native):
        parser.error('host route selects its own backend; use the native entry for other backends')
    env = dict(os.environ, SC_LLM_BACKEND='host-session')
    env[ENV] = str(directory)
    # The wrapper requires its own explicit selection, never an inherited extension.
    env.pop(TIMEOUT_ENV, None)
    if args.host_timeout_seconds is not None:
        env[TIMEOUT_ENV] = str(args.host_timeout_seconds)
    return subprocess.call([sys.executable, '-B', str(ROOT / ENTRIES[args.skill]), *native],
                           cwd=ROOT, env=env, shell=False)


if __name__ == '__main__':
    raise SystemExit(main())

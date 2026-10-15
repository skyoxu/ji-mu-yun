"""One non-authorizing native diagnostic; fixed budgets remain unchanged.

ADR-0058. Timing wrappers preserve arguments, returns and exceptions. This
diagnostic cannot serve as a Quick Dev stage or Acceptance completion proof.
"""
import functools
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = HERE / 'fresh-failure-diagnostic-r2'


def child():
    sys.path.insert(0, str(ROOT / 'scripts/sc'))
    import skill_package_replay as replay
    runtime = replay.runtime
    events = OUT / 'timing.jsonl'

    def event(value):
        with events.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps({'monotonic_seconds': time.monotonic(),
                'authorizes': [], **value}, sort_keys=True) + '\n')

    def observe(module, name):
        original = getattr(module, name)
        @functools.wraps(original)
        def wrapped(*args, **kwargs):
            started = time.monotonic()
            event({'operation': name, 'phase': 'started'})
            try:
                result = original(*args, **kwargs)
            except BaseException as exc:
                event({'operation': name, 'phase': 'failed',
                    'elapsed_seconds': time.monotonic() - started,
                    'exception': type(exc).__name__, 'diagnostic': str(exc)[:4000]})
                raise
            event({'operation': name, 'phase': 'completed',
                'elapsed_seconds': time.monotonic() - started})
            return result
        setattr(module, name, wrapped)

    for name in ('dependency_closure', 'historical_dependency_paths', 'verify_trust',
                 'materialize_git', 'route_transitions', 'snapshot', 'capture_process'):
        observe(runtime, name)
    for name in ('validate_package', 'verify_fresh_replay'):
        observe(replay, name)
    sys.argv = ['skill_package_replay.py', 'replay-package', '--target',
        '.agents/skills/run-refactor-implementation-acceptance', '--capability',
        'scripts/sc/config/skill-package-validator-capability.v1.json', '--probe-mode', 'fresh']
    return replay.main()


def main():
    if '--child' in sys.argv:
        return child()
    if OUT.exists():
        raise RuntimeError('Preserve the explicit previous diagnostic; do not rerun')
    OUT.mkdir()
    trace = OUT / 'native-trace'
    trace.mkdir()
    env = dict(os.environ, TC_D1_NATIVE_TRACE_DIR=str(trace))
    argv = [sys.executable, '-B', str(Path(__file__).resolve()), '--child']
    started = time.monotonic()
    with (OUT / 'stdout.bin').open('xb') as stdout, (OUT / 'stderr.bin').open('xb') as stderr:
        result = subprocess.run(argv, cwd=ROOT, env=env, stdout=stdout, stderr=stderr, timeout=420)
    facts = {'argv': argv, 'exit_code': result.returncode,
        'elapsed_seconds': time.monotonic() - started,
        'fixed_runtime_budgets_unchanged': True, 'authorizes': [],
        **{name + '_sha256': 'sha256:' + hashlib.sha256((OUT / (name + '.bin')).read_bytes()).hexdigest()
           for name in ('stdout', 'stderr')}}
    (OUT / 'process.json').write_text(json.dumps(facts, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(facts), flush=True)
    print((OUT / 'stdout.bin').read_text(encoding='utf-8')[-6000:], flush=True)
    print((OUT / 'stderr.bin').read_text(encoding='utf-8')[-4000:], flush=True)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())

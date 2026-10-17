"""Record real budget regression subprocess evidence (Accepted ADR-0058)."""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
pattern = sys.argv[1] if len(sys.argv) > 1 else 'test_skill_replay_budget_regressions.py'
destination = HERE / ('budget3-validation-r1' if len(sys.argv) == 1 else 'budget3-deadline-validation-r1')
destination.mkdir(exist_ok=False)
argv = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'scripts/sc/tests',
        '-p', pattern, '-v']
started = time.monotonic()
result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=1800)
(destination / 'stdout.bin').write_bytes(result.stdout)
(destination / 'stderr.bin').write_bytes(result.stderr)
facts = {'argv': argv, 'exit_code': result.returncode,
         'elapsed_seconds': time.monotonic() - started,
         'stdout_sha256': 'sha256:' + hashlib.sha256(result.stdout).hexdigest(),
         'stderr_sha256': 'sha256:' + hashlib.sha256(result.stderr).hexdigest(),
         'authorizes': []}
(destination / 'process.json').write_text(json.dumps(facts, indent=2), encoding='utf-8', newline='\n')
print(result.stderr.decode('utf-8', errors='replace'), flush=True)
raise SystemExit(result.returncode)

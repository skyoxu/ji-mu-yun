from __future__ import annotations

import argparse
import json
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", choices=("S0", "S1", "S2"))
    args = parser.parse_args()
    target = ".agents/skills/quick-dev-tdd-adapter/tools/tests" if args.slice is None else {
        "S0": ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_stage_lifecycle.py",
        "S1": ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_stage_recovery.py",
        "S2": ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_migration_cutover.py",
    }[args.slice]
    result = subprocess.run([sys.executable, "-B", "-m", "pytest", target, "-q"], check=False)
    print(json.dumps({"schema_version": "quick-dev-tdd-stage-recovery.terminal-result.v1", "status": "pass" if result.returncode == 0 else "fail", "predicate": "slice-ready" if args.slice else "implementation-complete", "plan_id": "quick-dev-tdd-stage-recovery", "authorizes": ["implementation-complete"] if result.returncode == 0 and args.slice is None else []}))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

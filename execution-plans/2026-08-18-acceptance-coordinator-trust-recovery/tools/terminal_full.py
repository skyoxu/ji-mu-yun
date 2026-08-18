from __future__ import annotations

import argparse
import json
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice")
    args = parser.parse_args()
    commands = [
        [sys.executable, "-m", "pytest", ".agents/skills/quick-dev-tdd-adapter/tools/tests", "-q"],
        [sys.executable, "-m", "pytest", ".agents/skills/run-refactor-implementation-acceptance/tests", "-q"],
    ]
    for command in commands:
        result = subprocess.run(command, check=False)
        if result.returncode:
            print(json.dumps({"predicate":"implementation-complete","status":"fail","slice":args.slice,"authorizes":[]}, sort_keys=True))
            return result.returncode
    print(json.dumps({"predicate":"implementation-complete","status":"pass","slice":args.slice,"authorizes":["implementation-complete"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

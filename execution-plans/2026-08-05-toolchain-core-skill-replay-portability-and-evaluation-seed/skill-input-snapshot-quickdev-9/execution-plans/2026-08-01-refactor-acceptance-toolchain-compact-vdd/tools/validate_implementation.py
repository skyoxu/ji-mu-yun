from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
EXPECTED = [
    ".agents/skills/run-refactor-implementation-acceptance/policies/toolchain-code-review.v1.json",
    ".agents/skills/run-refactor-implementation-acceptance/scripts/compact_vdd_projection.py",
    ".agents/skills/run-refactor-implementation-acceptance/schemas/compact-vdd-acceptance-prerequisite-bundle.v1.schema.json",
    ".agents/skills/run-refactor-implementation-acceptance/tests/test_toolchain_domain.py",
    ".agents/skills/run-refactor-implementation-acceptance/tests/test_compact_vdd_projection.py",
]
COMMANDS = [
    ["py", "-3", ".agents/skills/run-refactor-implementation-acceptance/tests/test_toolchain_domain.py"],
    ["py", "-3", ".agents/skills/run-refactor-implementation-acceptance/tests/test_compact_vdd_projection.py"],
    ["py", "-3", "-m", "unittest", "discover", "-s", ".agents/skills/run-refactor-implementation-acceptance/tests", "-p", "test_*.py"],
    ["py", "-3", ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py", "validate-package"],
    ["py", "-3", "C:/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py", ".agents/skills/run-refactor-implementation-acceptance"],
    ["py", "-3", "execution-plans/2026-08-01-workflow-model-routing-control-plane/tools/validate_implementation.py"],
]


def main() -> int:
    missing = [name for name in EXPECTED if not (ROOT / name).is_file()]
    if missing:
        print(json.dumps({"status":"fail","failure_family":"implementation-not-present","missing":missing,"authorizes":[]}, indent=2))
        return 1
    results = []
    for command in COMMANDS:
        completed = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", check=False)
        results.append({"command":command,"exit_code":completed.returncode})
        if completed.returncode:
            print(json.dumps({"status":"fail","failure_family":"registered-command-failed","results":results,"output":completed.stdout[-4000:],"authorizes":[]}, indent=2))
            return 1
    print(json.dumps({"schema_version":"jimuyun.refactor-acceptance-toolchain-implementation-validation.v1","status":"pass","predicate":"implementation-complete","results":results,"authorizes":["implementation-complete"],"does_not_authorize":["acceptance-passed","release","archived"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

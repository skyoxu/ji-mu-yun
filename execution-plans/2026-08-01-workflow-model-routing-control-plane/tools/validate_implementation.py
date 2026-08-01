from __future__ import annotations

import json
from pathlib import Path
import subprocess


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_FILES = [
    "scripts/sc/config/workflow_model_routes.v1.json",
    "scripts/sc/schemas/workflow-model-route-decision.v1.schema.json",
    "scripts/sc/tests/test_workflow_model_routing.py",
    "scripts/sc/tests/test_workflow_model_routing_evaluation.py",
    "scripts/sc/workflow_model_routing.py",
    ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_model_routing.py",
    ".agents/skills/vdd-execution-plan/scripts/tests/test_model_routing.py",
    ".agents/skills/run-refactor-implementation-acceptance/tests/test_model_routing.py",
]
COMMANDS = [
    ["py", "-3", "scripts/sc/tests/test_llm_backend.py"],
    ["py", "-3", "scripts/sc/tests/test_workflow_model_routing.py"],
    ["py", "-3", "scripts/sc/tests/test_workflow_model_routing_evaluation.py"],
    ["py", "-3", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_model_routing.py"],
    ["py", "-3", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_knowledge_context.py"],
    ["py", "-3", ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_plan_directory_loop.py"],
    ["py", "-3", ".agents/skills/vdd-execution-plan/scripts/tests/test_model_routing.py"],
    ["py", "-3", ".agents/skills/vdd-execution-plan/scripts/tests/test_vdd_knowledge_preflight.py"],
    ["py", "-3", ".agents/skills/vdd-execution-plan/scripts/tests/test_validate_skill_contract.py"],
    ["py", "-3", ".agents/skills/run-refactor-implementation-acceptance/tests/test_model_routing.py"],
    ["py", "-3", ".agents/skills/run-refactor-implementation-acceptance/tests/test_knowledge_context.py"],
    ["py", "-3", ".agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py"],
    ["py", "-3", "-m", "unittest", "discover", "-s", "scripts/python/tests", "-p", "test_knowledge_locator_*.py"],
]


def main() -> int:
    missing = [path for path in EXPECTED_FILES if not (REPOSITORY_ROOT / path).is_file()]
    if missing:
        print(json.dumps({
            "schema_version": "jimuyun.workflow-model-routing-implementation-validation.v1",
            "status": "fail",
            "failure_family": "implementation-not-present",
            "missing": missing,
            "authorizes": [],
        }, indent=2, sort_keys=True))
        return 1

    policy = json.loads(
        (REPOSITORY_ROOT / "scripts/sc/config/workflow_model_routes.v1.json").read_text(encoding="utf-8")
    )
    if policy.get("rolloutMode") != "observe_only":
        print(json.dumps({"status": "fail", "failure_family": "initial-rollout-not-observe-only", "authorizes": []}, sort_keys=True))
        return 1

    results = []
    for command in COMMANDS:
        completed = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )
        results.append({"command": command, "exit_code": completed.returncode})
        if completed.returncode != 0:
            print(json.dumps({
                "schema_version": "jimuyun.workflow-model-routing-implementation-validation.v1",
                "status": "fail",
                "failure_family": "registered-command-failed",
                "results": results,
                "authorizes": [],
            }, indent=2, sort_keys=True))
            return 1

    print(json.dumps({
        "schema_version": "jimuyun.workflow-model-routing-implementation-validation.v1",
        "status": "pass",
        "predicate": "implementation-complete",
        "rollout_mode": "observe_only",
        "results": results,
        "authorizes": ["implementation-complete"],
        "does_not_authorize": ["acceptance-passed", "release", "archived"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

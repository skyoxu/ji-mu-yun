"""Validate the repository-owned Knowledge Locator workflow integration."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONSUMERS = ("vdd", "quick-dev", "bootstrap", "refactor-acceptance")
PROTECTED_PREFIXES = (
    "logs/phase-a-innernet/",
    "runtime/phase-a/",
    "PhaseA.Platform/",
    "PhaseA.Platform.Tests/",
)


def _command(name: str, *arguments: str) -> tuple[str, list[str]]:
    return name, [sys.executable, "-B", *arguments]


def _declared_checks() -> tuple[tuple[str, list[str]], ...]:
    return (
        _command("locator", "-m", "unittest", "discover", "-s", "scripts/python/tests", "-p", "test_knowledge_locator_*.py"),
        _command("vdd", "-m", "unittest", "discover", "-s", ".agents/skills/vdd-execution-plan/scripts/tests", "-p", "test_*.py"),
        _command("vdd-contract", ".agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py", "--skill-root", ".agents/skills/vdd-execution-plan"),
        _command("quick-dev", "-m", "unittest", "discover", "-s", ".agents/skills/quick-dev-tdd-adapter/tools/tests", "-p", "test_*.py"),
        _command("quick-dev-contract", ".agents/skills/quick-dev-tdd-adapter/tools/validate_adapter_contract.py", "execution-plans/2026-07-26-knowledge-locator-workflow-integration/implementation-contract.v1.json"),
        _command("bootstrap", ".agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py"),
        _command("refactor-acceptance", "-m", "unittest", "discover", "-s", ".agents/skills/run-refactor-implementation-acceptance/tests", "-p", "test_*.py"),
        _command("refactor-acceptance-package", ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py", "validate-package"),
        _command("maintenance", ".agents/skills/maintain-knowledge-base/scripts/test_maintain_knowledge.py"),
        _command("maintenance-publication-request", "-m", "unittest", "discover", "-s", ".agents/skills/maintain-knowledge-base/tests", "-p", "test_*.py"),
        _command("publication", "-m", "unittest", "scripts.python.tests.test_publish_knowledge_catalog"),
        _command("generation-retention", "-m", "unittest", "scripts.python.tests.test_prune_knowledge_generations"),
        _command("migration", "scripts/python/tests/test_knowledge_workflow_migration.py"),
        _command("plan-validator", "execution-plans/2026-07-26-knowledge-locator-workflow-integration/tools/validate_plan.py"),
        _command("plan-validator-tests", "-m", "unittest", "discover", "-s", "execution-plans/2026-07-26-knowledge-locator-workflow-integration/tools/tests", "-p", "test_*.py"),
    )


def _protected_worktree_paths(repository_root: Path) -> list[str]:
    commands = (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--cached", "--name-only", "HEAD"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    )
    paths: set[str] = set()
    for command in commands:
        result = subprocess.run(command, cwd=repository_root, capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(f"git scan failed: {' '.join(command)}")
        paths.update(line.replace("\\", "/") for line in result.stdout.splitlines() if line)
    return sorted(path for path in paths if path.startswith(PROTECTED_PREFIXES))


def _required_paths(repository_root: Path) -> list[str]:
    required = (
        "knowledge/contracts/knowledge-locator-request.v1.schema.json",
        "knowledge/contracts/knowledge-locator-result.v1.schema.json",
        "knowledge/contracts/knowledge-consumption-decision.v1.schema.json",
        "knowledge/policies/consumer-policies.v1.json",
        "knowledge/catalogs/repository-knowledge-catalog.v1.json",
        "knowledge/contracts/repository-source-snapshot.v1.schema.json",
        "knowledge/contracts/repository-knowledge-catalog.v2.schema.json",
        "knowledge/contracts/knowledge-consumer-projections.v1.schema.json",
        "knowledge/contracts/knowledge-consumer-context.v1.schema.json",
        "knowledge/contracts/knowledge-publication-request.v1.schema.json",
        "knowledge/contracts/vdd-knowledge-freeze.v1.schema.json",
        "knowledge/contracts/knowledge-generation-retention-policy.v1.schema.json",
        "knowledge/policies/consumer-policies.v2.json",
        "knowledge/policies/source-exclusions.v1.json",
        "knowledge/policies/generation-retention.v1.json",
        "knowledge/snapshots/repository-source-snapshot.v1.json",
        "knowledge/catalogs/repository-knowledge-catalog.v2.json",
        "knowledge/projections/consumer-projections.v1.json",
        "scripts/python/knowledge_locator.py",
        "scripts/python/_knowledge_locator_core.py",
        "scripts/python/_knowledge_catalog_builder.py",
        "scripts/python/build_knowledge_catalog.py",
        "scripts/python/knowledge_context_validation.py",
        "scripts/python/publish_knowledge_catalog.py",
        "scripts/python/prune_knowledge_generations.py",
        "scripts/python/build_knowledge_index.py",
        ".agents/skills/vdd-execution-plan/scripts/vdd_knowledge_preflight.py",
        ".agents/skills/vdd-execution-plan/scripts/prepare_knowledge_context.py",
        ".agents/skills/quick-dev-tdd-adapter/tools/knowledge_context.py",
        ".agents/skills/run-phase-bootstrap-review/scripts/knowledge_context.py",
        ".agents/skills/run-refactor-implementation-acceptance/scripts/knowledge_context.py",
        ".agents/skills/run-refactor-implementation-acceptance/scripts/prepare_knowledge_context.py",
        ".agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-knowledge-maintenance-route.v1.schema.json",
        ".agents/skills/run-refactor-implementation-acceptance/scripts/package_validation.py",
        ".agents/skills/run-refactor-implementation-acceptance/tests/test_knowledge_context.py",
        ".agents/skills/maintain-knowledge-base/SKILL.md",
        ".agents/skills/maintain-knowledge-base/scripts/prepare_publication_request.py",
        ".agents/skills/maintain-knowledge-base/tests/test_prepare_publication_request.py",
    )
    return [relative for relative in required if not (repository_root / relative).is_file()]


def validate_repository(repository_root: Path = DEFAULT_REPOSITORY_ROOT) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    failures: list[dict[str, Any]] = []
    missing = _required_paths(repository_root)
    if missing:
        failures.append({"check": "required-artifacts", "missing": missing})

    try:
        protected = _protected_worktree_paths(repository_root)
    except RuntimeError as exc:
        failures.append({"check": "protected-path-scan", "detail": str(exc)})
    else:
        if protected:
            failures.append({"check": "protected-path-scan", "paths": protected})

    checks: list[dict[str, Any]] = []
    for name, command in _declared_checks():
        result = subprocess.run(command, cwd=repository_root, capture_output=True, text=True, check=False)
        check = {"name": name, "exit_code": result.returncode}
        if result.returncode:
            check["stderr"] = result.stderr[-4000:]
            check["stdout"] = result.stdout[-4000:]
            failures.append({"check": name, "exit_code": result.returncode})
        checks.append(check)

    return {
        "schema_version": "jimuyun.knowledge-workflow-terminal.v1",
        "status": "pass" if not failures else "fail",
        "consumers": list(CONSUMERS),
        "checks": checks,
        "failures": failures,
    }


def main() -> int:
    result = validate_repository()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

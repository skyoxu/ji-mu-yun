from __future__ import annotations

from pathlib import Path
from typing import Any
from shadow_guards import validate_shadow_protected_trees


def _missing(path: Path, repository_root: Path) -> dict[str, str]:
    try:
        target = path.relative_to(repository_root).as_posix()
    except ValueError:
        target = path.as_posix()
    return {"rule_id": "RMAP-AUTH-SLICE-EVIDENCE", "target": target, "message": "required slice output is missing"}


def _existing_paths(repository_root: Path, relatives: list[str]) -> list[dict[str, str]]:
    return [_missing(repository_root / relative, repository_root) for relative in relatives if not (repository_root / relative).is_file()]


def validate_slice_outputs(repository_root: Path, slice_id: str, shadow: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[dict[str, str]]]:
    required = {
        "RMAP-S0": ["docs/adr/ADR-0041-repository-maintenance-agent-protocol-ownership.md", "docs/standards/repository-maintenance-agent-protocol.md", "docs/standards/_index.md", "docs/PROJECT_DOCUMENTATION_INDEX.md"],
        "RMAP-S1": [".agents/skills/quick-dev-tdd-adapter/SKILL.md", ".agents/skills/quick-dev-tdd-adapter/references/implementation-backend-contract.md", ".agents/skills/quick-dev-tdd-adapter/references/tdd-run-protocol.md", ".agents/skills/quick-dev-tdd-adapter/references/evidence-and-freshness.md"],
        "RMAP-S2": [".agents/skills/quick-dev-tdd-adapter/tools/validate_adapter_contract.py"],
        "RMAP-S3": ["execution-plans/2026-07-12-llm-review-evidence-gate-hardening/implementation-contract.v1.json", "execution-plans/2026-07-12-llm-review-evidence-gate-hardening/fixtures/tdd-adapter-shadow.v1.json"],
        "RMAP-S4": ["execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/implementation-contract.v1.json", "execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/fixtures/tdd-adapter-shadow.v1.json"],
        "RMAP-S5": ["execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/implementation-contract.v1.json", "execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/fixtures/tdd-adapter-shadow.v1.json"],
    }
    findings = _existing_paths(repository_root, required.get(slice_id, []))
    if slice_id == "RMAP-S0":
        markers = [("docs/standards/_index.md", "repository-maintenance-agent-protocol.md"), ("docs/PROJECT_DOCUMENTATION_INDEX.md", "repository-maintenance-agent-protocol")]
        for relative, marker in markers:
            path = repository_root / relative
            if path.is_file() and marker not in path.read_text(encoding="utf-8"):
                findings.append(_missing(path, repository_root))
    if slice_id in {"RMAP-S3", "RMAP-S4", "RMAP-S5"}:
        findings.extend(validate_shadow_protected_trees(repository_root / "execution-plans" / "2026-07-15-repository-maintenance-tdd-adapter", shadow or {}))
    if slice_id == "RMAP-S2" and not list(repository_root.glob("logs/tdd-adapter/**/candidate-result.json")):
        findings.append(_missing(repository_root / "logs/tdd-adapter/<plan-id>/<slice-id>/<run-id>/candidate-result.json", repository_root))
    check = {"rule_id": "RMAP-AUTH-SLICE", "status": "pass" if not findings else "fail", "evidence": [f"{slice_id} declared outputs and review state"]}
    return check, findings

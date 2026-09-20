"""CER coverage for TC-D1 plan-validator scope and write boundaries."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Callable

import pytest


ROOT = Path(__file__).resolve().parents[4]
PLAN_ROOT = ROOT / "execution-plans" / "2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed"
VALIDATOR = PLAN_ROOT / "tools" / "validate_plan.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("tc_d1_s8_validate_plan", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("validator import failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_proposal(mutate: Callable[[dict, dict], None]) -> tuple[object, list[str]]:
    module = _load_validator()
    requirements = json.loads((PLAN_ROOT / "requirements.v1.json").read_text(encoding="utf-8"))
    contract = json.loads((PLAN_ROOT / "implementation-contract.v1.json").read_text(encoding="utf-8"))
    registry = json.loads((PLAN_ROOT / "command-registry.v1.json").read_text(encoding="utf-8"))
    mutate(requirements, contract)
    original_load_json = module.load_json

    def load_proposal_fixture(path: Path) -> dict:
        fixtures = {
            "requirements.v1.json": requirements,
            "implementation-contract.v1.json": contract,
            "command-registry.v1.json": registry,
        }
        if path.name in fixtures:
            return fixtures[path.name]
        return original_load_json(path)

    module.load_json = load_proposal_fixture
    try:
        errors: list[str] = []
        module.validate_requirements_and_contract(errors)
    finally:
        module.load_json = original_load_json
    return module, errors


def _assert_rejected(condition: bool, failure_id: str, message: str) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, message


@pytest.mark.cer_assertion("ASSERT-O-B394EE3A39B1-01")
def test_runtime_allowed_change_is_rejected_before_entering_the_write_set() -> None:
    runtime_path = "runtime/phase-a/startup.ps1"

    def mutate(_requirements: dict, contract: dict) -> None:
        contract["slices"][0]["allowed_changes"]["tests"].append(runtime_path)

    module, errors = _validate_proposal(mutate)
    _assert_rejected(
        module.has_forbidden_allowed_path(runtime_path)
        and f"forbidden allowed-change path in RMAP-S0: {runtime_path}" in errors,
        "RUNTIME-WRITE-BOUNDARY",
        "runtime writes must be rejected before they enter the TC-D1 allowed write set",
    )


@pytest.mark.cer_assertion("SM-6-INSTALLED-BMAD-GDS-WRITE-PROTECTION")
@pytest.mark.parametrize(
    "protected_path",
    [
        pytest.param("_bmad/custom/skill.md", id="bmad-root"),
        pytest.param(".agents/skills/bmad-example/SKILL.md", id="installed-bmad-skill"),
        pytest.param(".agents/skills/gds-example/SKILL.md", id="installed-gds-skill"),
    ],
)
def test_installed_skill_allowed_change_is_classified_forbidden_and_rejected(
    protected_path: str,
) -> None:
    def mutate(_requirements: dict, contract: dict) -> None:
        contract["slices"][0]["allowed_changes"]["tests"].append(protected_path)

    module, errors = _validate_proposal(mutate)
    _assert_rejected(
        module.has_forbidden_allowed_path(protected_path)
        and f"forbidden allowed-change path in RMAP-S0: {protected_path}" in errors,
        "SM-6-PROTECTED-INSTALLED-SKILL-PATH-ADMITTED",
        "installed BMAD and GDS Skill paths must remain outside the writable set",
    )


@pytest.mark.cer_assertion("ASSERT-A17-ROADMAP-SCOPE-REJECTION")
@pytest.mark.parametrize(
    "roadmap_id",
    [
        pytest.param("TC-E0-IMPLEMENTATION", id="tc-e0"),
        pytest.param("TC-D2-IMPLEMENTATION", id="tc-d2"),
        pytest.param("TC-D3-IMPLEMENTATION", id="tc-d3"),
        pytest.param("TC-D4-IMPLEMENTATION", id="tc-d4"),
        pytest.param("TC-D5-IMPLEMENTATION", id="tc-d5"),
        pytest.param("TC-D6-IMPLEMENTATION", id="tc-d6"),
    ],
)
def test_roadmap_implementation_scope_is_rejected_as_outside_tc_d1(roadmap_id: str) -> None:
    def mutate(requirements: dict, _contract: dict) -> None:
        requirements["requirements"].append(
            {"id": roadmap_id, "acceptance_ids": [], "slice_ids": []}
        )

    _module, errors = _validate_proposal(mutate)
    _assert_rejected(
        any(roadmap_id.lower() in error.lower() and "outside tc-d1" in error.lower() for error in errors),
        "ROADMAP-SCOPE-ACCEPTANCE",
        "TC-E0 and TC-D2 through TC-D6 implementation requests must be rejected as outside TC-D1",
    )


@pytest.mark.cer_assertion("TC-D1-A17")
@pytest.mark.parametrize(
    "excluded_feature",
    [
        pytest.param("Miner", id="miner"),
        pytest.param("Curator", id="curator"),
        pytest.param("autonomous Skill modification", id="autonomous-skill-modification"),
        pytest.param("learned ranking", id="learned-ranking"),
        pytest.param("reinforcement learning", id="reinforcement-learning"),
    ],
)
def test_excluded_feature_proposal_is_rejected_with_scope_diagnostic(
    excluded_feature: str,
) -> None:
    def mutate(requirements: dict, _contract: dict) -> None:
        requirements["proposed_features"] = [excluded_feature]

    _module, errors = _validate_proposal(mutate)
    _assert_rejected(
        any(
            excluded_feature.lower() in error.lower() and "scope" in error.lower()
            for error in errors
        ),
        "FI-O-12C5846F9454-EXCLUDED-FEATURE-SCOPE",
        "excluded autonomous and ranking features must produce a scope diagnostic",
    )

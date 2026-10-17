"""S29 checks for exactly three approved, non-baseline evaluation seeds."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
MANIFEST = ROOT / "scripts/sc/scenarios/evaluation-seed-manifest.v1.json"
MATRIX = ROOT / (
    "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/"
    "stable-candidate-replay-matrix.v1.json"
)
VALIDATOR = ROOT / (
    "execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/"
    "tools/validate_implementation.py"
)
EXPECTED_OCCURRENCES = {
    "candidate-baseline-contamination",
    "self-hosted-knowledge-read-set-collision",
    "toolchain-policy-architecture-index-gap",
}
APPROVED_CLASSES = {"anchor_candidate", "challenge_candidate"}


def _load_validator():
    spec = importlib.util.spec_from_file_location("s29_validate_implementation", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load the production validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _production_errors(manifest: dict) -> list[str]:
    validator = _load_validator()
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    errors: list[str] = []
    validator.validate_evaluation_artifacts(manifest, matrix, errors, repository_root=ROOT)
    return errors


def _valid_classification(manifest: dict) -> bool:
    seeds = manifest.get("seeds")
    if not isinstance(seeds, list) or len(seeds) != 3:
        return False
    occurrences = [seed.get("occurrence") for seed in seeds if isinstance(seed, dict)]
    return (
        len(occurrences) == 3
        and set(occurrences) == EXPECTED_OCCURRENCES
        and all(
            seed.get("classification") == "approved_non_baseline"
            and seed.get("candidate_class") in APPROVED_CLASSES
            and isinstance(seed.get("provenance"), dict)
            for seed in seeds
        )
    )


def _assert_behavior(condition: bool, detail: object) -> None:
    if not condition:
        print("FAILURE_ID:EVALUATION-SEED-CLASSIFICATION-INVALID")
    assert condition, detail


@pytest.mark.cer_assertion("three-evaluation-seeds-approved-nonbaseline")
def test_three_named_evaluation_seeds_are_approved_nonbaseline() -> None:
    manifest = _manifest()
    production_errors = _production_errors(manifest)
    _assert_behavior(
        _valid_classification(manifest) and not production_errors,
        {"manifest": manifest, "production_errors": production_errors},
    )


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("baseline", id="baseline"),
        pytest.param("missing", id="missing-classification"),
        pytest.param("unapproved", id="unapproved"),
    ],
)
@pytest.mark.cer_assertion("three-evaluation-seeds-approved-nonbaseline")
def test_invalid_seed_classification_is_rejected(mutation: str) -> None:
    manifest = copy.deepcopy(_manifest())
    if mutation == "baseline":
        manifest["seeds"][0]["classification"] = "baseline"
    elif mutation == "missing":
        manifest["seeds"][1].pop("classification")
    else:
        manifest["seeds"][2]["classification"] = "experimental"
    _assert_behavior(not _valid_classification(manifest), manifest)

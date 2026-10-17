from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[4]
PLAN_ROOT = ROOT / "execution-plans" / "2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed"
VALIDATOR = PLAN_ROOT / "tools" / "validate_implementation.py"
MANIFEST = PLAN_ROOT / "evaluation-seeds.v1.json"
SCHEMA = ROOT / "scripts" / "sc" / "schemas" / "toolchain-evaluation-seed-manifest.v1.schema.json"
FAILURE_MISSING_FIELDS = "F-O-B62210A66D2C-MISSING-REQUIRED-FIELDS"
FAILURE_EXACTLY_ONCE = "F-O-B62210A66D2C-DUPLICATE-OR-MISSING-SEED"
ASSERTION_FIELDS = "A-O-B62210A66D2C-1"
ASSERTION_EXACTLY_ONCE = "A-O-B62210A66D2C-2"
EXPECTED_OCCURRENCES = (
    "candidate-baseline-contamination",
    "self-hosted-knowledge-read-set-collision",
    "toolchain-policy-architecture-index-gap",
)


def _load_validator():
    spec = importlib.util.spec_from_file_location("s37_validate_implementation", VALIDATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _matrix(module: object) -> dict:
    return {
        "cases": [
            {
                "case_id": f"case-{category}",
                "category": category,
                "validation_surface": "fixture",
                "expected_observation": "pass",
            }
            for category in module.MATRIX_CATEGORIES
        ],
        "authorizes": [],
    }


def _errors(value: dict) -> list[str]:
    module = _load_validator()
    errors: list[str] = []
    module.validate_evaluation_artifacts(value, _matrix(module), errors)
    return errors


def _schema_rejected(value: dict, path: Path) -> bool:
    path.write_text(json.dumps(value), encoding="utf-8", newline="\n")
    result = subprocess.run(
        [sys.executable, "-m", "jsonschema", "-i", str(path), str(SCHEMA)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.returncode != 0


def _assert_rejected(condition: bool, failure_id: str, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, detail


@pytest.mark.parametrize(
    "missing_field",
    [
        pytest.param("provenance", marks=pytest.mark.cer_assertion(ASSERTION_FIELDS)),
        pytest.param("applicability", marks=pytest.mark.cer_assertion(ASSERTION_FIELDS)),
        pytest.param("missing_labels", marks=pytest.mark.cer_assertion(ASSERTION_FIELDS)),
        pytest.param("counterexample", marks=pytest.mark.cer_assertion(ASSERTION_FIELDS)),
    ],
)
def test_rmap_s2_rejects_seed_missing_fr6_required_field(missing_field: str) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["seeds"][0].pop(missing_field)
    path = ROOT / "scripts" / "sc" / "tests" / "tc_d1_cer" / f".s37-missing-{missing_field}.json"
    try:
        rejected = _schema_rejected(manifest, path)
    finally:
        path.unlink(missing_ok=True)
    _assert_rejected(
        rejected,
        FAILURE_MISSING_FIELDS,
        {"mutation": f"missing-{missing_field}"},
    )


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("missing", marks=pytest.mark.cer_assertion(ASSERTION_EXACTLY_ONCE)),
        pytest.param("duplicate", marks=pytest.mark.cer_assertion(ASSERTION_EXACTLY_ONCE)),
    ],
)
def test_rmap_s2_rejects_missing_or_duplicate_named_seed(mutation: str) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if mutation == "missing":
        manifest["seeds"] = manifest["seeds"][:-1]
    else:
        manifest["seeds"][1] = copy.deepcopy(manifest["seeds"][0])
    errors = _errors(manifest)
    _assert_rejected(
        any("exactly once" in error or "unique" in error or "exactly match" in error for error in errors),
        FAILURE_EXACTLY_ONCE,
        {"errors": errors, "mutation": mutation, "occurrences": [seed.get("occurrence") for seed in manifest["seeds"]]},
    )


@pytest.mark.cer_assertion(ASSERTION_FIELDS)
def test_manifest_fixture_contains_three_named_complete_seed_records() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    seeds = manifest.get("seeds", [])
    occurrences = [seed.get("occurrence") for seed in seeds]
    required = {"provenance", "applicability", "missing_labels", "classification"}
    complete = all(
        required.issubset(seed)
        and seed.get("classification") == "approved_non_baseline"
        and ("counterexample" in seed or "explicit_absence" in seed)
        for seed in seeds
    )
    _assert_rejected(
        occurrences == list(EXPECTED_OCCURRENCES),
        FAILURE_EXACTLY_ONCE,
        {"occurrences": occurrences, "expected": list(EXPECTED_OCCURRENCES)},
    )
    _assert_rejected(
        complete,
        FAILURE_MISSING_FIELDS,
        {"seeds": seeds},
    )

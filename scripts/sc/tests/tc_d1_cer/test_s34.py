"""S34 checks three individually applicable evaluation seeds (Accepted ADR-0058)."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCHEMA = ROOT / "scripts/sc/schemas/toolchain-evaluation-seed-manifest.v1.schema.json"
MANIFEST = ROOT / "scripts/sc/scenarios/evaluation-seed-manifest.v1.json"
OCCURRENCES = (
    "candidate-baseline-contamination",
    "self-hosted-knowledge-read-set-collision",
    "toolchain-policy-architecture-index-gap",
)
ASSERTION = "A-8E718A411378-1"
OCCURRENCE_CASES = tuple(
    pytest.param(index, id=occurrence, marks=pytest.mark.cer_assertion(ASSERTION))
    for index, occurrence in enumerate(OCCURRENCES)
)
MUTATION_CASES = tuple(
    pytest.param(mutation, id=mutation, marks=pytest.mark.cer_assertion(ASSERTION))
    for mutation in ("duplicate", "merged", "fourth")
)


def _assert_behavior(condition: bool, failure_id: str, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, detail


def _fixture_manifest() -> dict:
    return {
        "schema_version": "jimuyun.toolchain-evaluation-seed-manifest.v1",
        "baseline_status": "non-authorizing-candidates",
        "authorizes": [],
        "seeds": [
            {
                "occurrence": occurrence,
                "failure_family": occurrence,
                "candidate_class": "challenge_candidate",
                "provenance": {"source": f"bounded-fixture/{occurrence}"},
                "applicability": {"applicable": True},
                "missing_labels": [],
                "counterexample": {"status": "observed"},
            }
            for occurrence in OCCURRENCES
        ],
    }


def _validate(manifest: dict) -> subprocess.CompletedProcess[str]:
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix="-s34-seed-manifest.json",
        delete=False,
    )
    instance = Path(handle.name)
    try:
        json.dump(manifest, handle)
        handle.close()
        return subprocess.run(
            [sys.executable, "-m", "jsonschema", "-i", str(instance), str(SCHEMA)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30, check=False,
        )
    finally:
        try:
            instance.unlink()
        except FileNotFoundError:
            pass


def _assert_validation_result(result: subprocess.CompletedProcess[str], expected_valid: bool,
                              failure_id: str) -> None:
    output = result.stdout + result.stderr
    if result.returncode not in (0, 1):
        pytest.fail(f"jsonschema could not evaluate the manifest: {output}")
    valid = result.returncode == 0
    _assert_behavior(valid is expected_valid, failure_id, output)


@pytest.mark.cer_assertion(ASSERTION)
def test_complete_fixture_is_accepted_by_manifest_schema() -> None:
    result = _validate(_fixture_manifest())
    _assert_validation_result(result, True, "F-8E718A411378-1")


@pytest.mark.cer_assertion(ASSERTION)
def test_recorded_manifest_has_three_inspectable_applicable_occurrences() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    seeds = manifest.get("seeds")
    present = isinstance(seeds, list) and len(seeds) == 3 and all(isinstance(seed, dict) for seed in seeds)
    _assert_behavior(present, "F-8E718A411378-2", manifest)
    by_occurrence = {
        seed.get("occurrence"): seed
        for seed in seeds
        if isinstance(seed.get("occurrence"), str)
    }
    _assert_behavior(set(by_occurrence) == set(OCCURRENCES)
                     and len(by_occurrence) == len(OCCURRENCES),
                     "F-8E718A411378-2", manifest)
    for occurrence in OCCURRENCES:
        seed = by_occurrence[occurrence]
        _assert_behavior(isinstance(seed.get("provenance"), dict) and bool(seed["provenance"])
                         and isinstance(seed.get("applicability"), dict)
                         and bool(seed["applicability"]),
                         "F-8E718A411378-1", {"occurrence": occurrence, "seed": seed})


@pytest.mark.cer_assertion(ASSERTION)
@pytest.mark.parametrize("index", OCCURRENCE_CASES)
def test_each_missing_applicability_is_rejected(index: int) -> None:
    manifest = _fixture_manifest()
    manifest["seeds"][index].pop("applicability")
    result = _validate(manifest)
    _assert_validation_result(result, False, "F-8E718A411378-1")

@pytest.mark.parametrize("index", OCCURRENCE_CASES)
@pytest.mark.cer_assertion(ASSERTION)
def test_each_empty_applicability_is_rejected(index: int) -> None:
    manifest = _fixture_manifest()
    manifest["seeds"][index]["applicability"] = {}
    result = _validate(manifest)
    _assert_validation_result(result, False, "F-8E718A411378-1")


@pytest.mark.parametrize("mutation", MUTATION_CASES)
@pytest.mark.cer_assertion(ASSERTION)
def test_occurrence_count_or_identity_change_is_rejected(mutation: str) -> None:
    manifest = _fixture_manifest()
    if mutation == "duplicate":
        manifest["seeds"][1]["occurrence"] = OCCURRENCES[0]
    elif mutation == "merged":
        manifest["seeds"].pop()
    else:
        extra = copy.deepcopy(manifest["seeds"][0])
        extra["occurrence"] = "unplanned-fourth-seed"
        manifest["seeds"].append(extra)
    result = _validate(manifest)
    _assert_validation_result(result, False, "F-8E718A411378-2")

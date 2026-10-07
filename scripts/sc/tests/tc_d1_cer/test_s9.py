"""CER checks for Consumer Manifest reconciliation and seed coverage."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.sc import skill_replay_runtime as runtime


ROOT = Path(__file__).resolve().parents[4]
REPLAY_ENTRY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
SEED_SCHEMA = ROOT / "scripts" / "sc" / "schemas" / "toolchain-evaluation-seed-manifest.v1.schema.json"
SEED_OCCURRENCES = (
    "candidate-baseline-contamination",
    "self-hosted-knowledge-read-set-collision",
    "toolchain-policy-architecture-index-gap",
)


def _replay_consumer_manifest() -> dict:
    result = runtime.capture_process([sys.executable, '-B', str(REPLAY_ENTRY), 'replay-package', '--target', TARGET, '--capability', CAPABILITY, '--probe-mode', 'consumer-manifest'], ROOT, timeout=180)
    assert result.returncode == 0, (
        "skill_package_replay.py failed before producing a Consumer Manifest: "
        f"{result.stdout}{result.stderr}"
    )
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"skill_package_replay.py did not emit JSON: {exc}")
    manifest = receipt.get("current_wrapper_replay", {}).get("consumer_manifest")
    if not isinstance(manifest, dict):
        pytest.fail("replay receipt did not contain a Consumer Manifest object")
    return manifest


def _assert_behavior(condition: bool, failure_id: str, message: str) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, message


@pytest.mark.cer_assertion("A-675D-1")
def test_consumer_manifest_reconciliation_has_no_missing_callers() -> None:
    manifest = _replay_consumer_manifest()
    _assert_behavior(
        manifest.get("missing_callers") == [],
        "F-675D-MISSING-CALLER",
        "Consumer Manifest reconciliation must report zero missing callers across VDD, Acceptance, and workflow-model-routing",
    )


@pytest.mark.cer_assertion("A-675D-2")
def test_consumer_manifest_reconciliation_has_no_orphan_entries() -> None:
    manifest = _replay_consumer_manifest()
    _assert_behavior(
        manifest.get("orphan_manifest_entries") == [],
        "F-675D-ORPHAN-ENTRY",
        "Consumer Manifest reconciliation must report zero orphan entries across VDD, Acceptance, and workflow-model-routing",
    )


def _seed_manifest() -> dict:
    return {
        "schema_version": "jimuyun.toolchain-evaluation-seed-manifest.v1",
        "baseline_status": "non-authorizing-candidates",
        "seeds": [
            {
                "occurrence": occurrence,
                "failure_family": occurrence,
                "candidate_class": "challenge_candidate",
                "provenance": {"source": "bounded-cer-fixture"},
                "applicability": {"applicable": True},
                "missing_labels": [],
                "counterexample": {"status": "observed"},
            }
            for occurrence in SEED_OCCURRENCES
        ],
        "authorizes": [],
    }


def _run_seed_schema(instance: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "jsonschema",
            "-i",
            str(instance),
            str(SEED_SCHEMA),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


@pytest.mark.cer_assertion("assert-three-seed-occurrences-covered")
def test_seed_schema_rejects_occurrence_without_counterexample_or_explicit_absence(
    tmp_path: Path,
) -> None:
    complete = _seed_manifest()
    complete_path = tmp_path / "complete-seed-manifest.json"
    complete_path.write_text(json.dumps(complete), encoding="utf-8")
    complete_result = _run_seed_schema(complete_path)
    assert complete_result.returncode == 0, (
        "the complete bounded seed manifest must validate: "
        f"{complete_result.stdout}{complete_result.stderr}"
    )

    incomplete = copy.deepcopy(complete)
    incomplete["seeds"][1].pop("counterexample")
    incomplete_path = tmp_path / "uncovered-seed-manifest.json"
    incomplete_path.write_text(json.dumps(incomplete), encoding="utf-8")
    result = _run_seed_schema(incomplete_path)
    if result.returncode == 0:
        print("FAILURE_ID:SEED-OCCURRENCE-UNCOVERED")
    assert result.returncode != 0, (
        "seed validation must reject an occurrence that has neither a counterexample "
        "nor an explicit absence"
    )

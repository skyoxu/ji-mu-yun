"""S19 bounded CER checks for replay portability and evaluation-seed contracts."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from scripts.sc import skill_replay_runtime as runtime


ROOT = Path(__file__).resolve().parents[4]
REPLAY = ROOT / "scripts" / "sc" / "skill_package_replay.py"
CAPABILITY = "scripts/sc/config/skill-package-validator-capability.v1.json"
TARGET = ".agents/skills/run-refactor-implementation-acceptance"
SEED_SCHEMA = ROOT / "scripts" / "sc" / "schemas" / "toolchain-evaluation-seed-manifest.v1.schema.json"
SEED_MANIFEST = ROOT / "scripts" / "sc" / "scenarios" / "evaluation-seed-manifest.v1.json"
OCCURRENCES = (
    "candidate-baseline-contamination",
    "self-hosted-knowledge-read-set-collision",
    "toolchain-policy-architecture-index-gap",
)


def _python() -> list[str]:
    # Accepted ADR-0058: descendants use the actually bound interpreter.
    return [sys.executable]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return runtime.capture_process([*_python(), '-B', str(REPLAY), *args], ROOT, timeout=runtime.PROCESS_TRANSPORT_SECONDS if args[0] == "replay-package" else 150 if args[0] == "replay-matrix" else 60)


def _replay() -> tuple[subprocess.CompletedProcess[str], dict]:
    result = _run(
        "replay-package",
        "--target",
        TARGET,
        "--capability",
        CAPABILITY,
        "--probe-mode",
        "consumer-manifest",
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    return result, payload if isinstance(payload, dict) else {}


def _assert_behavior(condition: bool, failure_id: str, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, detail


def _seed_fixture() -> dict:
    return {
        "schema_version": "jimuyun.toolchain-evaluation-seed-manifest.v1",
        "baseline_status": "non-authorizing-candidates",
        "authorizes": [],
        "seeds": [
            {
                "occurrence": occurrence,
                "failure_family": occurrence,
                "candidate_class": "challenge_candidate",
                "classification": "approved_non_baseline",
                "provenance": {"path": f"bounded-fixture/{occurrence}.json"},
                "applicability": {"applicable": True},
                "missing_labels": [],
                "counterexample": {"status": "observed"},
            }
            for occurrence in OCCURRENCES
        ],
    }


def _schema_validate(tmp_path: Path, value: dict) -> subprocess.CompletedProcess[str]:
    instance = tmp_path / "seed-manifest.json"
    instance.write_text(json.dumps(value), encoding="utf-8", newline="\n")
    return subprocess.run(
        [*_python(), "-m", "jsonschema", "-i", str(instance), str(SEED_SCHEMA)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )


@pytest.mark.cer_assertion("A-BDE93E01BA76-1")
def test_replay_records_independent_validator_source_verification() -> None:
    result, payload = _replay()
    replay = payload.get("current_wrapper_replay", {})
    verification = replay.get("independent_validator_verification", {})
    _assert_behavior(
        result.returncode == 0
        and verification.get("independent") is True
        and verification.get("status") == "pass"
        and isinstance(verification.get("source_path"), str)
        and verification.get("source_sha256", "").startswith("sha256:"),
        "F-BDE93E01BA76-1",
        {"exit": result.returncode, "verification": verification},
    )


@pytest.mark.cer_assertion("A-EDCB-authority-nonprofile")
def test_profile_authority_candidate_is_rejected_by_real_entry() -> None:
    profile_candidate = str(Path.home() / "profile-authority-candidate")
    result = _run(
        "validate-package",
        "--target",
        profile_candidate,
        "--capability",
        CAPABILITY,
    )
    output = result.stdout + result.stderr
    _assert_behavior(
        result.returncode != 0 and "escapes the repository" in output,
        "F-EDCB-PROFILE-AUTHORITY",
        output,
    )


def _load_replay_module():
    spec = importlib.util.spec_from_file_location("s19_replay", REPLAY)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.cer_assertion("FR-5-A1")
def test_repository_relative_path_manifest_detects_rename() -> None:
    replay = _load_replay_module()
    with tempfile.TemporaryDirectory(prefix="s19-path-", dir=str(ROOT / "scripts" / "sc" / "tests")) as directory:
        package = Path(directory) / "package"
        (package / "docs").mkdir(parents=True)
        (package / "docs" / "historical.md").write_text("frozen\n", encoding="utf-8", newline="\n")
        before = replay.runtime.bindings(package, ("docs",))
        before_identity = replay.manifest(package)
        (package / "docs" / "historical.md").rename(package / "docs" / "renamed.md")
        after = replay.runtime.bindings(package, ("docs",))
        added = sorted({row["path"] for row in after} - {row["path"] for row in before})
        removed = sorted({row["path"] for row in before} - {row["path"] for row in after})
        _assert_behavior(
            added == ["docs/renamed.md"] and removed == ["docs/historical.md"]
            and before[0]["sha256"] == after[0]["sha256"]
            and before_identity != replay.manifest(package),
            "FI-41568BB6C998-PATH-CHANGE",
            {"added_paths": added, "removed_paths": removed},
        )


@pytest.mark.cer_assertion("A-F173-seed-provenance")
def test_recorded_seed_manifest_has_three_unique_complete_occurrences() -> None:
    recorded = json.loads(SEED_MANIFEST.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="s19-seed-", dir=str(ROOT / "scripts" / "sc" / "tests")) as directory:
        result = _schema_validate(Path(directory), recorded)
        seeds = recorded.get("seeds", [])
        identities = [seed.get("occurrence") for seed in seeds if isinstance(seed, dict)]
        _assert_behavior(
            result.returncode == 0
            and identities == list(OCCURRENCES)
            and all(isinstance(seed.get("provenance"), dict) and seed.get("provenance") for seed in seeds)
            and all("missing_labels" in seed for seed in seeds),
            "F-F173-MISSING-PROVENANCE",
            {"schema": result.stderr, "identities": identities},
        )


@pytest.mark.cer_assertion("O-1D1C29C76F06")
@pytest.mark.parametrize("mutation", ["missing-label", "duplicate-or-hidden"])
def test_seed_manifest_rejects_missing_label_or_identity_mutation(mutation: str) -> None:
    fixture = _seed_fixture()
    if mutation == "missing-label":
        fixture["seeds"][1].pop("missing_labels")
        failure_id = "O-1D1C29C76F06-MISSING-LABEL"
    else:
        fixture["seeds"][1]["occurrence"] = fixture["seeds"][0]["occurrence"]
        failure_id = "O-1D1C29C76F06-DUPLICATE-OR-HIDDEN-SEED"
    with tempfile.TemporaryDirectory(prefix="s19-seed-negative-", dir=str(ROOT / "scripts" / "sc" / "tests")) as directory:
        result = _schema_validate(Path(directory), fixture)
        identities = [seed.get("occurrence") for seed in fixture["seeds"]]
        valid = result.returncode == 0 and len(identities) == 3 and set(identities) == set(OCCURRENCES)
        _assert_behavior(not valid, failure_id, {"mutation": mutation, "schema": result.stderr})


@pytest.mark.cer_assertion("A-220-1")
@pytest.mark.cer_assertion("A-220-2")
def test_consumer_manifest_reconciles_both_directions_and_named_scopes() -> None:
    result, payload = _replay()
    manifest = payload.get("current_wrapper_replay", {}).get("consumer_manifest", {})
    entries = manifest.get("entries", [])
    paths = {entry.get("path") for entry in entries if isinstance(entry, dict)}
    scope_paths = {
        "VDD": ".agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py",
        "Acceptance": ".agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py",
        "workflow-model-routing": "scripts/sc/tests/test_workflow_model_routing.py",
        "Knowledge": "scripts/python/validate_knowledge_workflow_integration.py",
    }
    _assert_behavior(
        result.returncode == 0
        and manifest.get("bidirectional_reconciled") is True
        and manifest.get("missing_callers") == []
        and manifest.get("orphan_manifest_entries") == []
        and {entry.get("consumer") for entry in entries} == {
            "vdd-execution-plan", "run-refactor-implementation-acceptance", "workflow-model-routing",
            "knowledge-workflow-vdd-package", "knowledge-workflow-acceptance-package",
        }
        and all(path in paths for path in scope_paths.values()),
        "F-220-SCOPE-OMISSION",
        manifest,
    )


@pytest.mark.cer_assertion("A-F8C403BFB034-1")
def test_foreign_authority_input_cannot_be_accepted_as_success() -> None:
    result, payload = _replay()
    replay = payload.get("current_wrapper_replay", {})
    selected = replay.get("resolved_validator", {}).get("path", "")
    _assert_behavior(
        result.returncode == 0
        and not selected.startswith("%USERPROFILE%")
        and not selected.lower().startswith("c:/users/")
        and replay.get("status") == "pass",
        "F-F8C403BFB034-1",
        {"selected_authority": selected, "status": replay.get("status")},
    )

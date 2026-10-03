"""S14 CER coverage for frozen historical byte preservation."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from hashlib import sha256
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
VERIFY_BASE_CLEAN = ROOT / "scripts" / "ci" / "verify_base_clean.ps1"
EXECUTION_EVIDENCE_VALIDATOR = ROOT / "scripts" / "python" / "validate_acceptance_execution_evidence.py"
ASSERTION = "frozen-historical-bytes-unchanged"
FAILURE_ID = "FROZEN-HISTORICAL-BYTES-MUTATED"


def _sha256_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


def _fixture_root(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "fixture-repository"
    frozen = root / "historical" / "frozen-receipt.bin"
    frozen.parent.mkdir(parents=True)
    frozen.write_bytes(b"frozen historical bytes\n")

    (root / "docs" / "architecture" / "base").mkdir(parents=True)
    (root / "docs" / "architecture" / "base" / "01-foundation.md").write_text(
        "CH01 foundation\n", encoding="utf-8", newline="\n"
    )
    (root / "docs" / "adr").mkdir(parents=True)
    (root / "docs" / "adr" / "ADR-0001-fixture.md").write_text(
        "# Fixture ADR\n", encoding="utf-8", newline="\n"
    )

    _write_json(
        root / ".taskmaster" / "tasks" / "tasks.json",
        {"master": {"tasks": [{"id": 1, "status": "in-progress"}]}},
    )
    _write_json(root / ".taskmaster" / "tasks" / "tasks_back.json", [{"taskmaster_id": 1, "acceptance": []}])
    _write_json(root / ".taskmaster" / "tasks" / "tasks_gameplay.json", [{"taskmaster_id": 1, "acceptance": []}])

    date = "2026-01-01"
    sc_dir = root / "logs" / "ci" / date / "sc-test"
    unit_dir = root / "logs" / "unit" / date
    sc_dir.mkdir(parents=True)
    unit_dir.mkdir(parents=True)
    _write_json(sc_dir / "summary.json", {"run_id": "fixture-run", "steps": [{"name": "unit", "artifacts_dir": str(unit_dir)}]})
    (sc_dir / "run_id.txt").write_text("fixture-run\n", encoding="utf-8", newline="\n")
    (unit_dir / "run_id.txt").write_text("fixture-run\n", encoding="utf-8", newline="\n")
    return root, frozen


def _run_base_clean(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-File", str(VERIFY_BASE_CLEAN), "-RepoRoot", str(root)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )


def _run_execution_evidence_validator(root: Path, out: Path) -> int:
    spec = importlib.util.spec_from_file_location("s14_execution_evidence_validator", EXECUTION_EVIDENCE_VALIDATOR)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load the production validator entry")
    module = importlib.util.module_from_spec(spec)
    # The validator defines dataclasses with postponed annotations. Register
    # the dynamically loaded module before execution so Python 3.13's
    # dataclasses resolver can resolve its module namespace.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    original_root = module.repo_root
    original_argv = sys.argv[:]
    try:
        module.repo_root = lambda: root
        sys.argv = [
            str(EXECUTION_EVIDENCE_VALIDATOR),
            "--task-id",
            "1",
            "--run-id",
            "fixture-run",
            "--date",
            "2026-01-01",
            "--out",
            str(out),
        ]
        return int(module.main())
    finally:
        module.repo_root = original_root
        sys.argv = original_argv
        sys.modules.pop(spec.name, None)


def _run_bounded_operation(root: Path, tmp_path: Path) -> tuple[int, int]:
    base_clean = _run_base_clean(root)
    validator_exit = _run_execution_evidence_validator(root, tmp_path / "execution-evidence.json")
    return base_clean.returncode, validator_exit


def _changed_frozen_artifacts(before: dict[str, str], root: Path) -> list[str]:
    changed: list[str] = []
    for relative, expected_hash in before.items():
        path = root / relative
        observed_hash = _sha256_bytes(path.read_bytes()) if path.is_file() else None
        if observed_hash != expected_hash:
            changed.append(relative)
    return changed


def _assert_behavior(condition: bool, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{FAILURE_ID}")
    assert condition, detail


@pytest.mark.cer_assertion(ASSERTION)
def test_frozen_historical_bytes_remain_identical_after_bounded_operations() -> None:
    with tempfile.TemporaryDirectory(dir=r"C:\tmp") as directory:
        tmp_path = Path(directory)
        root, frozen = _fixture_root(tmp_path)
        before = {frozen.relative_to(root).as_posix(): _sha256_bytes(frozen.read_bytes())}

        exits = _run_bounded_operation(root, tmp_path)
        changed = _changed_frozen_artifacts(before, root)

        _assert_behavior(exits == (0, 0), {"base_clean_exit": exits[0], "validator_exit": exits[1]})
        _assert_behavior(changed == [], {"changed_frozen_artifacts": changed})


@pytest.mark.cer_assertion(ASSERTION)
def test_single_mutated_frozen_artifact_is_reported_by_byte_comparison() -> None:
    with tempfile.TemporaryDirectory(dir=r"C:\tmp") as directory:
        tmp_path = Path(directory)
        root, frozen = _fixture_root(tmp_path)
        before = {frozen.relative_to(root).as_posix(): _sha256_bytes(frozen.read_bytes())}

        frozen.write_bytes(b"mutated historical bytes\n")
        exits = _run_bounded_operation(root, tmp_path)
        changed = _changed_frozen_artifacts(before, root)

        _assert_behavior(exits == (0, 0), {"base_clean_exit": exits[0], "validator_exit": exits[1]})
        _assert_behavior(changed == [frozen.relative_to(root).as_posix()], changed)

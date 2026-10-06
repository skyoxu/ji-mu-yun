"""Independent FR-3 validator-content checks (ADR-0058, ADR-0041)."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts.sc import skill_package_replay as replay


FAILURE_ID = "F-F34-SELF-ATTESTED-VALIDATOR"
RULE = "reject_missing_target"


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _fixture(root: Path, *, include_rule: bool) -> tuple[str, str, str]:
    target = root / "candidate"
    target.mkdir()
    (target / "fixture.json").write_text('{"valid": true}\n', encoding="utf-8")
    (target / "SKILL.md").write_text("# bounded candidate\n", encoding="utf-8")
    source = root / "declared-validator-source.py"
    validator_dir = root / "validator"
    validator_dir.mkdir()
    validator = validator_dir / "check.py"
    lines = [
        "import sys,json",
        "from pathlib import Path",
        "target = Path(sys.argv[1])",
        "valid = json.loads((target / 'fixture.json').read_text(encoding='utf-8')).get('valid') is True",
        "print(json.dumps({'findings': [] if valid else ['invalid-fixture']}))",
        "if not valid:",
        "    raise SystemExit(2)",
    ]
    if include_rule:
        lines.extend(("def reject_missing_target(path):", "    return not path.exists()"))
    lines.append("raise SystemExit(2 if not target.is_dir() else 0)")
    validator.write_text("\n".join(lines) + "\n", encoding="utf-8")
    declared_lines = [
        "import sys,json",
        "from pathlib import Path",
        "target = Path(sys.argv[1])",
        "valid = json.loads((target / 'fixture.json').read_text(encoding='utf-8')).get('valid') is True",
        "print(json.dumps({'findings': [] if valid else ['invalid-fixture']}))",
        "if not valid:",
        "    raise SystemExit(2)",
        "def reject_missing_target(path):",
        "    return not path.exists()",
        "raise SystemExit(2 if not target.is_dir() else 0)",
    ]
    source.write_text("\n".join(declared_lines) + "\n", encoding="utf-8")
    capability = root / "capability.json"
    capability.write_text(
        json.dumps(
            {
                "state": "active",
                "allowed_root": "validator",
                "validator_entrypoint": "check.py",
                "validator_sha256": _sha256(validator.read_bytes()),
                "validator_source": "declared-validator-source.py",
                "validator_source_sha256": _sha256(source.read_bytes()),
                "required_rules": [RULE],
                "probe_args": ["{target}"],
                "negative_probe": {"path": "fixture.json", "replacement": {"valid": False}, "diagnostic": "invalid-fixture"},
                "authorizes": [],
            }
        ),
        encoding="utf-8",
    )
    return "candidate", "capability.json", _sha256(source.read_bytes())


def _assert_oracle(condition: bool, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{FAILURE_ID}")
    assert condition, detail


@pytest.mark.cer_assertion("A-F34-validator-independent")
def test_independent_report_binds_source_content_and_required_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, capability, source_hash = _fixture(tmp_path, include_rule=True)
    monkeypatch.setattr(replay, "ROOT", tmp_path)
    for arguments in (["init", "-q"], ["config", "user.name", "TC-D1 fixture"], ["config", "user.email", "tc-d1-fixture@example.invalid"], ["config", "core.autocrlf", "false"], ["add", "."], ["commit", "-qm", "Freeze independent source"]):
        subprocess.run(["git", *arguments], cwd=tmp_path, check=True, capture_output=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()
    monkeypatch.setenv("TC_D1_TRUST_COMMIT", commit)
    receipt = replay.validate_package(target, capability)
    report = receipt.get("independent_validator_verification")
    checks = report.get("required_rule_checks") if isinstance(report, dict) else None
    _assert_oracle(
        isinstance(report, dict)
        and report.get("status") == "pass"
        and report.get("source_sha256") == source_hash
        and report.get("content_sha256") == _sha256((tmp_path / "validator/check.py").read_bytes())
        and isinstance(checks, dict)
        and checks.get(RULE) is True
        and report.get("independent") is True
        and receipt.get("authorizes") == [],
        receipt,
    )


@pytest.mark.cer_assertion("A-F34-validator-independent")
def test_missing_required_rule_is_rejected_independently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, capability, _ = _fixture(tmp_path, include_rule=False)
    monkeypatch.setattr(replay, "ROOT", tmp_path)
    for arguments in (["init", "-q"], ["config", "user.name", "TC-D1 fixture"], ["config", "user.email", "tc-d1-fixture@example.invalid"], ["config", "core.autocrlf", "false"], ["add", "."], ["commit", "-qm", "Freeze independent source"]):
        subprocess.run(["git", *arguments], cwd=tmp_path, check=True, capture_output=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()
    monkeypatch.setenv("TC_D1_TRUST_COMMIT", commit)
    try:
        receipt = replay.validate_package(target, capability)
    except (ValueError, RuntimeError) as exc:
        diagnostic = str(exc)
        rejected = RULE in diagnostic and ("missing" in diagnostic.lower() or "mismatch" in diagnostic.lower())
    else:
        report = receipt.get("independent_validator_verification")
        checks = report.get("required_rule_checks") if isinstance(report, dict) else None
        rejected = (
            isinstance(report, dict)
            and report.get("status") == "fail"
            and isinstance(checks, dict)
            and checks.get(RULE) is False
        )
    _assert_oracle(rejected, "A validator missing a declared FR-3 rule must not pass independently")

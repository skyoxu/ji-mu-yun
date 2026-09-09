"""ADR-0058: advisory impact, operator status and reviewer input composition."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from operator_support import impact, publish_support
from test_current_acceptance_closeout import build, git
import acceptance_cli as cli


def test_impact_reports_imports_checks_and_incomplete_inventory(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "owner.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "test_owner.py").write_text("from owner import value\nassert value == 1\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    result = impact(tmp_path, ["owner.py"], [{"id": "check", "executable": "python", "argv": ["-m", "pytest", "test_owner.py"]}])
    assert result["consumers"][0]["matches"][0]["lines"] == [1]
    assert result["checks"][0]["commandId"] == "check"
    assert not result["checks"][0]["executedBySupport"]
    assert result["limitations"]
    assert impact(tmp_path / "absent", [], [])["limitations"][-1] == "Tracked source inventory unavailable."


@pytest.mark.parametrize("exit_code, expected", [(0, "completed"), (3, "waiting")])
def test_public_cli_publishes_support_without_changing_action_evidence(tmp_path, monkeypatch, exit_code, expected):
    request, output, _ = build(tmp_path, monkeypatch, command_exit=exit_code)
    monkeypatch.setattr(sys, "argv", ["acceptance", "run-coordinator", "--request", str(request), "--out", str(output)])
    assert cli.main() == 0
    result = json.loads(output.read_text())
    assert result["status"] == expected
    reports = list((tmp_path / "logs/acceptance-operator-support").glob("*/report.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text())
    assert report["status"] == expected and report["authorizes"] == []
    assert report["references"] and report["candidate"]
    assert "Diff unavailable" not in report["diffNote"]
    assert (reports[0].parent / "candidate.diff").read_text()
    if exit_code:
        assert "acceptance-check" in report["blocker"]
    assert (reports[0].parent / "reviewer-prompt.md").is_file()
    events = tmp_path / result["runDirectory"] / "acceptance-events.jsonl"
    before = events.read_bytes()
    assert cli.main() == 0
    assert events.read_bytes() == before


def test_blocked_report_does_not_reuse_saved_success(tmp_path, monkeypatch):
    request, output, _ = build(tmp_path, monkeypatch)
    result = cli.run_coordinator(str(request), str(output))
    assert result["status"] == "completed"
    out = publish_support(tmp_path, request, error="Skill input context is stale")
    report = json.loads((tmp_path / out / "report.json").read_text())
    assert report["status"] == "blocked" and report["coordinatorResult"] is None
    assert report["blocker"] == "Skill input context is stale"

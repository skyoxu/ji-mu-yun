import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[5]
SCRIPT = ROOT / ".agents/skills/quick-dev-tdd-adapter/tools/route_plan_directory.py"


def _route():
    spec = importlib.util.spec_from_file_location("candidate_transition_route", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def _commit(root: Path, message: str) -> str:
    _git(root, "add", ".")
    _git(root, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _candidate_repo(tmp_path: Path) -> tuple[Path, Path, dict]:
    root = tmp_path; plan = root / "execution-plans" / "target"; plan.mkdir(parents=True)
    (plan / "implementation-contract.v1.json").write_text(json.dumps({"plan_id":"target","slices":[]}), encoding="utf-8")
    (plan / "command-registry.v1.json").write_text("{}", encoding="utf-8")
    (plan / "plan-state.v1.json").write_text(json.dumps({"plan_id":"target","state":"plan-ready","authorizes":["plan-ready"]}), encoding="utf-8")
    _git(root, "init")
    candidate = _commit(root, "candidate")
    tree = _git(root, "rev-parse", f"{candidate}^{{tree}}")
    (plan / "governance").mkdir(); (plan / "governance" / "review.json").write_text("{}", encoding="utf-8")
    (plan / "plan-state.v1.json").write_text(json.dumps({"plan_id":"target","state":"implementation-authorized","baseline_commit":candidate,"authorizes":["implementation-authorized"]}), encoding="utf-8")
    _commit(root, "evidence and transition")
    return root, plan, {"candidate_commit":candidate,"candidate_tree_hash":"sha256:" + tree}


@pytest.mark.cer_assertion("A-B148C5C61A99-repository-relative-paths-unchanged")
def test_candidate_allows_evidence_and_exact_plan_state_transition(tmp_path: Path) -> None:
    root, plan, receipt = _candidate_repo(tmp_path)
    assert _route()._candidate_commit_is_current(root, plan, receipt)


def test_candidate_rejects_other_post_candidate_production_change(tmp_path: Path) -> None:
    root, plan, receipt = _candidate_repo(tmp_path)
    (plan / "tools").mkdir(); (plan / "tools" / "producer.py").write_text("changed\n", encoding="utf-8")
    _commit(root, "unauthorized production change")
    assert not _route()._candidate_commit_is_current(root, plan, receipt)


@pytest.mark.cer_assertion("A-B148C5C61A99-repository-relative-paths-unchanged")
def test_worker_delta_rejects_a_renamed_repository_relative_path() -> None:
    worker = importlib.import_module("worker_orchestrator")
    with pytest.raises(ValueError, match="write-set violation"):
        worker._validate_delta(
            ["tools/before.py", "tools/after.py"],
            allowed=["tools/after.py"],
            forbidden=[],
            label="red-author",
        )

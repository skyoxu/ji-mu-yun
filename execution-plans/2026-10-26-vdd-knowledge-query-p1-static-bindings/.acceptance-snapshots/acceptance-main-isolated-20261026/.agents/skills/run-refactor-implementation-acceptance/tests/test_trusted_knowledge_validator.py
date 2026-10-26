"""ADR-0053/0058: main code validates candidate data without importing it."""
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from test_current_acceptance_closeout import ROOT, git, knowledge, write
from knowledge_context import InputError, freeze_knowledge_context


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "candidate"
    root.mkdir()
    (root / "rules.md").write_text("# Rules\nVerify exact source bytes.\n", encoding="utf-8")
    for name in ("knowledge_context_validation.py", "_knowledge_locator_core.py"):
        path = root / "scripts/python" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "scripts/python" / name, path)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "core.autocrlf", "false")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "user.name", "Fixture")
    git(root, "add", ".")
    git(root, "commit", "-qm", "trusted main fixture")
    target = root / "execution-plans/target"
    frozen = knowledge(root, target, git(root, "rev-parse", "HEAD"))
    return root, target, frozen


def test_candidate_core_is_data_and_cannot_execute(repository):
    root, target, expected = repository
    marker = root / "candidate-executed"
    (root / "scripts/python/_knowledge_locator_core.py").write_text(
        "from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\nraise RuntimeError('candidate code')\n",
        encoding="utf-8",
    )
    before = git(root, "rev-parse", "main", "HEAD")
    assert freeze_knowledge_context(target, "knowledge.json") == expected
    assert not marker.exists()
    assert git(root, "rev-parse", "main", "HEAD") == before


def test_candidate_validator_is_never_executed(repository):
    root, target, expected = repository
    (root / "scripts/python/knowledge_context_validation.py").write_text("raise RuntimeError('candidate validator')\n")
    assert freeze_knowledge_context(target, "knowledge.json") == expected


def test_import_pollution_and_python_environment_are_isolated(repository, monkeypatch, tmp_path):
    root, target, expected = repository
    marker = tmp_path / "imported"
    poison = tmp_path / "poison"
    poison.mkdir()
    for name in ("sitecustomize.py", "json.py", "_knowledge_locator_core.py"):
        (poison / name).write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\nraise RuntimeError('poison')\n")
    monkeypatch.setenv("PYTHONPATH", str(poison))
    monkeypatch.setenv("PYTHONHOME", str(poison))
    monkeypatch.setitem(sys.modules, "_knowledge_locator_core", SimpleNamespace())
    assert freeze_knowledge_context(target, "knowledge.json") == expected
    assert not marker.exists()


@pytest.mark.parametrize("mutation", ["consumer", "preflight", "source", "publication", "projection", "policy"])
def test_invalid_candidate_data_remains_rejected(repository, mutation):
    root, target, _ = repository
    path = target / "knowledge.json"
    doc = json.loads(path.read_text())
    if mutation == "consumer":
        doc["consumer"] = "vdd"
    elif mutation == "preflight":
        doc["preflight"]["status"] = "blocked"
    elif mutation == "source":
        (root / "rules.md").write_text("changed\n")
    elif mutation == "publication":
        (root / "knowledge/indexes/current.json").write_text("{}")
    elif mutation == "projection":
        (root / "knowledge/projections/consumer-projections.v1.json").write_text("{}")
    else:
        (root / "knowledge/policies/consumer-policies.v2.json").write_text("{}")
    write(path, doc)
    with pytest.raises(InputError):
        freeze_knowledge_context(target, "knowledge.json")


def test_missing_main_or_dependency_fails_closed(repository):
    root, target, _ = repository
    git(root, "update-ref", "-d", "refs/heads/main")
    with pytest.raises(InputError):
        freeze_knowledge_context(target, "knowledge.json")


def test_missing_main_core_is_not_replaced_by_candidate(repository):
    root, target, _ = repository
    git(root, "rm", "scripts/python/_knowledge_locator_core.py")
    git(root, "commit", "-qm", "main lacks dependency")
    (root / "scripts/python/_knowledge_locator_core.py").write_text("# candidate fallback must not run\n")
    with pytest.raises(InputError):
        freeze_knowledge_context(target, "knowledge.json")


def test_context_and_source_path_escape_fail_closed(repository, tmp_path):
    root, target, _ = repository
    with pytest.raises(InputError):
        freeze_knowledge_context(target, "../target/knowledge.json")
    outside = tmp_path / "outside"
    outside.write_text("outside\n")
    source = root / "rules.md"
    source.unlink()
    try:
        source.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(InputError):
        freeze_knowledge_context(target, "knowledge.json")


def test_main_drift_during_child_rejects_result(repository, monkeypatch):
    root, _, _ = repository
    helper = importlib.import_module("trusted_knowledge_validator")
    proxy = helper.TrustedMainValidator(root)
    original = helper._run_child
    def drift(*args, **kwargs):
        result = original(*args, **kwargs)
        (root / "new.txt").write_text("new main\n")
        git(root, "add", "new.txt")
        git(root, "commit", "-qm", "main moved")
        return result
    monkeypatch.setattr(helper, "_run_child", drift)
    with pytest.raises(ValueError, match="main changed"):
        proxy.validate_catalog_freshness(root)


def test_corrupted_materialized_bytes_reject_before_execution(repository, monkeypatch):
    root, _, _ = repository
    helper = importlib.import_module("trusted_knowledge_validator")
    original = helper._run_child
    def corrupt(directory, request, **kwargs):
        (directory / "_knowledge_locator_core.py").write_text("raise RuntimeError('corrupt')\n")
        return original(directory, request, **kwargs)
    monkeypatch.setattr(helper, "_run_child", corrupt)
    with pytest.raises(ValueError, match="identity|failed"):
        helper.TrustedMainValidator(root).validate_catalog_freshness(root)


def test_unexpected_local_main_dependency_is_rejected(repository):
    root, target, _ = repository
    with (root / "scripts/python/_knowledge_locator_core.py").open("a") as stream:
        stream.write("\nimport arbitrary_candidate_plugin\n")
    git(root, "add", "scripts/python/_knowledge_locator_core.py")
    git(root, "commit", "-qm", "unsupported trusted dependency")
    with pytest.raises(InputError, match="dependency"):
        freeze_knowledge_context(target, "knowledge.json")


def test_refresh_preserves_selection_and_updates_only_selected_bytes(repository):
    root, target, _ = repository
    from knowledge_context import refresh_context_read_set
    doc = json.loads((target / "knowledge.json").read_text())
    (root / "rules.md").write_text("# Rules\nUpdated source bytes.\n")
    refreshed = refresh_context_read_set(doc, root)
    before = doc["locator_result"]["candidates"][0]
    after = refreshed["locator_result"]["candidates"][0]
    assert after["path"] == before["path"] and after["module_id"] == before["module_id"]
    assert after["source_sha256"] != before["source_sha256"]
    assert len(refreshed["locator_result"]["candidates"]) == 1
    assert doc["locator_result"]["candidates"][0] == before


def test_short_child_timeout_cleans_process_and_publishes_nothing(repository, monkeypatch):
    root, target, _ = repository
    helper = importlib.import_module("trusted_knowledge_validator")
    with (root / "scripts/python/_knowledge_locator_core.py").open("a") as stream:
        stream.write("\nwhile True:\n    pass\n")
    git(root, "add", "scripts/python/_knowledge_locator_core.py")
    git(root, "commit", "-qm", "trusted fixture stalls")
    original = helper._run_child
    processes = []
    popen = helper.subprocess.Popen
    def observe(*args, **kwargs):
        process = popen(*args, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(helper.subprocess, "Popen", observe)
    monkeypatch.setattr(helper, "_run_child", lambda d, q: original(d, q, timeout=.15))
    with pytest.raises(InputError):
        freeze_knowledge_context(target, "knowledge.json")
    assert processes and all(p.poll() is not None for p in processes)
    assert not (target / "acceptance-current.v1.json").exists()


def test_private_worker_rejects_unsupported_operation_and_flag_bypass(repository):
    root, target, _ = repository
    helper = importlib.import_module("trusted_knowledge_validator")
    proxy = helper.TrustedMainValidator(root)
    with pytest.raises(ValueError, match="operation"):
        proxy._call("exec")
    with pytest.raises(ValueError, match="flags"):
        proxy.validate_context({}, repository_root=root, verify_sources=False)
    with pytest.raises(ValueError, match="root"):
        proxy.validate_catalog_freshness(target)


@pytest.mark.parametrize("mutation", ["json", "nonce", "result"])
def test_bad_child_responses_cannot_authorize_validation(repository, monkeypatch, mutation):
    root, _, _ = repository
    helper = importlib.import_module("trusted_knowledge_validator")
    original = helper.subprocess.Popen
    class MutatedResponse(original):
        def communicate(self, *args, **kwargs):
            stdout, stderr = super().communicate(*args, **kwargs)
            if "-I" in self.args and self.returncode == 0:
                if mutation == "json":
                    stdout = b"truncated response"
                else:
                    value = json.loads(stdout)
                    value["nonce" if mutation == "nonce" else "result"] = "wrong" if mutation == "nonce" else True
                    stdout = json.dumps(value).encode()
            return stdout, stderr
    monkeypatch.setattr(helper.subprocess, "Popen", MutatedResponse)
    with pytest.raises(ValueError, match="response|identity"):
        helper.TrustedMainValidator(root).validate_catalog_freshness(root)


def test_cancel_reaps_isolated_child(repository, monkeypatch):
    root, _, _ = repository
    helper = importlib.import_module("trusted_knowledge_validator")
    original = helper.subprocess.Popen
    children = []
    class Cancelled(original):
        def communicate(self, *args, **kwargs):
            if "-I" in self.args and self not in children:
                children.append(self)
                raise KeyboardInterrupt
            return super().communicate(*args, **kwargs)
    monkeypatch.setattr(helper.subprocess, "Popen", Cancelled)
    with pytest.raises(KeyboardInterrupt):
        helper.TrustedMainValidator(root).validate_catalog_freshness(root)
    assert len(children) == 1 and children[0].poll() is not None


def test_private_git_snapshot_does_not_follow_candidate_git_environment(repository, monkeypatch, tmp_path):
    root, target, expected = repository
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "unrelated.git"))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.worktree")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(tmp_path))
    assert freeze_knowledge_context(target, "knowledge.json") == expected


def test_target_nested_repository_cannot_choose_its_own_trust_root(repository):
    root, target, _ = repository
    (target / "knowledge").mkdir()
    files = target / "scripts/python"
    files.mkdir(parents=True)
    (files / "_knowledge_locator_core.py").write_text("# Untrusted nested repository.\n")
    (files / "knowledge_context_validation.py").write_text(
        "def validate_context(*args, **kwargs): return None\n"
        "def validate_worktree_sources(*args, **kwargs): return None\n"
        "def validate_catalog_freshness(*args, **kwargs): return None\n"
    )
    git(target, "init", "-q", "-b", "main")
    git(target, "config", "user.email", "fixture@example.invalid")
    git(target, "config", "user.name", "Nested fixture")
    git(target, "add", ".")
    git(target, "commit", "-qm", "candidate-chosen main must not grant trust")
    with pytest.raises(InputError, match="ambiguous"):
        freeze_knowledge_context(target, "knowledge.json")

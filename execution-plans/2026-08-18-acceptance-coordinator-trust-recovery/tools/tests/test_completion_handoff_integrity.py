import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "execution-plans/2026-08-18-acceptance-coordinator-trust-recovery/tools/terminal_full.py"


def _load():
    spec = importlib.util.spec_from_file_location("terminal_full_r5", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_candidate_source_root_is_content_identity_not_git_head(tmp_path):
    module = _load()
    source = tmp_path / "source.py"
    source.write_text("first\n", encoding="utf-8")
    manifest = module.build_candidate_source_manifest(tmp_path, [{"path": "source.py", "role": "production", "slice_ids": ["R5"]}])
    assert manifest["candidate_source_root"].startswith("sha256:")
    same = module.build_candidate_source_manifest(tmp_path, [{"path": "source.py", "role": "production", "slice_ids": ["R5"]}])
    assert same["candidate_source_root"] == manifest["candidate_source_root"]
    source.write_text("second\n", encoding="utf-8")
    changed = module.build_candidate_source_manifest(tmp_path, [{"path": "source.py", "role": "production", "slice_ids": ["R5"]}])
    assert changed["candidate_source_root"] != manifest["candidate_source_root"]


def test_generated_evidence_paths_are_not_candidate_sources():
    module = _load()
    assert module._is_generated_candidate_path("execution-plans/a/terminal-results/terminal-full.json")
    assert module._is_generated_candidate_path("execution-plans/a/repair/round-2/quick-dev-implementation-complete.v2.json")


def test_r5_test_source_bytes_invalidate_candidate_root(tmp_path):
    module = _load()
    production = tmp_path / "production.py"
    test_source = tmp_path / "test_r5.py"
    production.write_text("stable\n", encoding="utf-8")
    test_source.write_text("assert True\n", encoding="utf-8")
    entries = [
        {"path": "production.py", "role": "production", "slice_ids": ["R5"]},
        {"path": "test_r5.py", "role": "test", "slice_ids": ["R5"]},
    ]
    before = module.build_candidate_source_manifest(tmp_path, entries)["candidate_source_root"]
    test_source.write_text("assert False\n", encoding="utf-8")
    after = module.build_candidate_source_manifest(tmp_path, entries)["candidate_source_root"]
    assert after != before


def test_r5_candidate_entries_include_test_sources():
    module = _load()
    entries = {entry["path"]: entry for entry in module._candidate_source_entries()}
    assert entries["execution-plans/2026-08-18-acceptance-coordinator-trust-recovery/tools/tests/test_completion_handoff_integrity.py"]["role"] == "test"
    assert entries[".agents/skills/run-refactor-implementation-acceptance/tests/test_deterministic_finalization.py"]["role"] == "test"

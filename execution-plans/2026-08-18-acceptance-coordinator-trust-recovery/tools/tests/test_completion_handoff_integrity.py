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

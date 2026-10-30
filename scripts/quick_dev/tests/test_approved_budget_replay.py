"""ADR-0058: exact approved budget transition preserves original evidence."""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / ".agents/skills/quick-dev-tdd-adapter/tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO / "scripts/quick_dev"))
TRANSITION = "1b1bf3d8bb694c6f3932039118647a9eb59921ba"
PINNED_OWNER_REVISION = "c15c2839f1ccaa3e4e4ca0febd67f3b009aed3dd"
PATHS = ("scripts/sc/skill_replay_runtime.py", "scripts/sc/tests/tc_d1_cer/conftest.py")


def owner():
    assert importlib.util.find_spec("approved_budget_replay") is not None, "Q8 lacks approved-budget evidence reuse"
    import approved_budget_replay
    return approved_budget_replay


def materialize(root):
    for relative in PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(subprocess.check_output(["git", "show", TRANSITION + ":" + relative], cwd=REPO))
    for relative in owner().OWNER_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        # Historical compatibility admits exactly this old adapter version,
        # never the current implementation or an updated allowlist hash.
        payload = subprocess.check_output(["git", "show", PINNED_OWNER_REVISION + ":" + relative], cwd=REPO)
        assert __import__('hashlib').sha256(payload).hexdigest() == owner().OWNER_FILES[relative]
        path.write_bytes(payload)
    relative = next(p for p in owner().PAIRS if p.endswith(".md"))
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((REPO / relative).read_bytes())


def binding():
    return {"schema": "quick-dev.approved-budget-compatibility.v1", "transition_commit": TRANSITION,
            "owner_baseline": "5f0dd99c398a711c2d5f501756fca64a1a7cc44c",
            "budget_epoch": "before", "authorizes": []}


def test_reads_original_bytes_only_inside_explicit_q8_context(tmp_path):
    module = owner()
    materialize(tmp_path)
    current = (tmp_path / PATHS[0]).read_bytes()
    frozen = subprocess.check_output(["git", "show", TRANSITION + "^:" + PATHS[0]], cwd=REPO)
    from runtime_evidence import sha256_bytes
    with module.replay_budget_transition(tmp_path, binding(), git_root=REPO):
        assert module.hash_path(tmp_path / PATHS[0]) == sha256_bytes(frozen)
        assert module.resolve_file(tmp_path, PATHS[0]).read_bytes() == frozen
        assert (tmp_path / PATHS[0]).read_bytes() == current
    assert module.hash_path(tmp_path / PATHS[0]) == sha256_bytes(current)


def test_extra_semantic_change_rejects_instead_of_masking(tmp_path):
    module = owner()
    materialize(tmp_path)
    with (tmp_path / PATHS[0]).open("ab") as stream:
        stream.write(b"\ndef bypass(): return True\n")
    with pytest.raises(ValueError, match="unapproved budget transition bytes"):
        with module.replay_budget_transition(tmp_path, binding(), git_root=REPO):
            pytest.fail("Unapproved code entered compatibility context")


@pytest.mark.parametrize("bad", [{}, {"authorizes": ["pass"]}, {"transition_commit": "f" * 40}])
def test_malformed_or_forged_binding_rejects(tmp_path, bad):
    module = owner()
    materialize(tmp_path)
    value = binding()
    if not bad:
        value.pop("authorizes")
    else:
        value.update(bad)
    with pytest.raises(ValueError, match="budget compatibility binding"):
        with module.replay_budget_transition(tmp_path, value, git_root=REPO):
            pytest.fail("Invalid binding accepted")


def test_unrelated_fixture_and_exception_cleanup_remain_strict(tmp_path):
    module = owner()
    materialize(tmp_path)
    fixture = tmp_path / "fixture.txt"
    fixture.write_bytes(b"changed fixture")
    from runtime_evidence import sha256_bytes
    with pytest.raises(RuntimeError, match="preserved failure"):
        with module.replay_budget_transition(tmp_path, binding(), git_root=REPO):
            assert module.hash_path(fixture) == sha256_bytes(b"changed fixture")
            raise RuntimeError("preserved failure")
    assert module.hash_path(tmp_path / PATHS[0]) == sha256_bytes((tmp_path / PATHS[0]).read_bytes())


def test_current_budget_proof_keeps_current_budget_identity(tmp_path):
    module = owner()
    materialize(tmp_path)
    value = binding()
    value["budget_epoch"] = "after"
    from runtime_evidence import hash_path
    with module.replay_budget_transition(tmp_path, value, git_root=REPO):
        assert module.hash_path(tmp_path / PATHS[0]) == hash_path(tmp_path / PATHS[0])


def test_contract_reconstructs_only_pinned_adapter_and_preserves_extra_files(tmp_path):
    module = owner()
    materialize(tmp_path)
    root = tmp_path / module.CONTRACT
    original = tmp_path / "historical-contract"
    for relative in module.OWNER_FILES:
        path = original / Path(relative).relative_to(module.CONTRACT)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(subprocess.check_output(["git", "show", module.OWNER_BASELINE + ":" + relative], cwd=REPO))
    from runtime_evidence import hash_path
    with module.replay_budget_transition(tmp_path, binding(), git_root=REPO):
        assert module.hash_path(root) == hash_path(original)
        (root / "extra-file.txt").write_bytes(b"unapproved addition")
        assert module.hash_path(root) != hash_path(original)


def test_changed_owner_adapter_is_not_compatible(tmp_path):
    module = owner()
    materialize(tmp_path)
    relative = next(iter(module.OWNER_FILES))
    with (tmp_path / relative).open("ab") as stream:
        stream.write(b"\n# unrelated adapter edit\n")
    with pytest.raises(ValueError, match="unapproved Q8 owner adapter bytes"):
        with module.replay_budget_transition(tmp_path, binding(), git_root=REPO):
            pytest.fail("Unapproved owner admitted")

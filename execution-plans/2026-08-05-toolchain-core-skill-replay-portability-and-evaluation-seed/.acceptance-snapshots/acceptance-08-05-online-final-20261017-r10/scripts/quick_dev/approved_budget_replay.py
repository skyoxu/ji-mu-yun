"""ADR-0058: read original successful proofs across the approved budget change.

Only two exact before/after blob pairs qualify. No evidence is rewritten, no
process is executed, and the normal Q8 success/exact-cover checks still apply.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
import subprocess

import runtime_evidence as native

TRANSITION = "1b1bf3d8bb694c6f3932039118647a9eb59921ba"
OWNER_BASELINE = "5f0dd99c398a711c2d5f501756fca64a1a7cc44c"
CONTRACT = ".agents/skills/quick-dev-tdd-adapter"
# The adapter is an opt-in read-only extension. Its ordinary predicates are
# unchanged. Pin both adapter blobs; all other contract paths stay byte-exact.
OWNER_FILES = {
    CONTRACT + "/tools/behavior_routing.py": "c5e6d9402e456866299c51be9f21d17c9f1a20c93dcdeb67459342994638750f",
    CONTRACT + "/tools/coverage_predicates.py": "9e8c0343d5a15f51c1257d4f388633972484d0599efe5fc39ac80afaecb0fcc8",
}
PAIRS = {
    "scripts/sc/skill_replay_runtime.py": (
        "2e9b5846c3834651a23c9f801e9d19b323b576e139a94bce1024c5df244ad822",
        "59b78931bba52c1a7bb22de1d9d5ca511ac3872477ac035a9fc4c1a162c67e91"),
    "scripts/sc/tests/tc_d1_cer/conftest.py": (
        "17e663061a91d9c4579431301911da4e750047363dabb2342f60bd801728e30d",
        "d6c138d63ac497a41f61484e4abb62da6ac0487df8afd24ed2cc87c94279982a"),
    "docs/adr/ADR-0058-toolchain-skill-replay-portability-and-evaluation-seeds.md": (
        "12871d598db76e8eadfb00ecabd368e164cc77338ef8266ed4be689d1dc8a31e",
        "ec8e23b87687dc692723c99e77e614962605e71028c7d0e3801b2c247a7233cf"),
}
_ACTIVE = ContextVar("approved_budget_original_bytes", default={})


@lru_cache(maxsize=16)
def _blob(git_root, revision, relative):
    data = subprocess.check_output(["git", "show", revision + ":" + relative], cwd=git_root, timeout=180)
    return data


@contextmanager
def replay_budget_transition(workspace, binding, *, git_root=None):
    if binding is None:
        yield
        return
    epoch = binding.get("budget_epoch") if isinstance(binding, dict) else None
    expected = {"schema": "quick-dev.approved-budget-compatibility.v1",
                "transition_commit": TRANSITION, "owner_baseline": OWNER_BASELINE,
                "budget_epoch": epoch, "authorizes": []}
    if binding != expected or epoch not in {"before", "after"}:
        raise ValueError("invalid budget compatibility binding")
    workspace = workspace.resolve()
    originals = {}
    for relative, (before, after) in PAIRS.items():
        path = native.resolve_file(workspace, relative)
        if native.sha256_bytes(path.read_bytes()) != "sha256:" + after:
            raise ValueError("unapproved budget transition bytes: " + relative)
        data = _blob(str(git_root or workspace), TRANSITION + "^", relative)
        if native.sha256_bytes(data) != "sha256:" + before:
            raise ValueError("approved budget original blob unavailable")
        if relative.endswith(".md") and not path.read_bytes().startswith(data):
            raise ValueError("budget ADR is not an append-only update")
        if epoch == "before":
            originals[path] = data
    for relative, after in OWNER_FILES.items():
        path = native.resolve_file(workspace, relative)
        if native.sha256_bytes(path.read_bytes()) != "sha256:" + after:
            raise ValueError("unapproved Q8 owner adapter bytes: " + relative)
        originals[path] = _blob(str(git_root or workspace), OWNER_BASELINE, relative)
    token = _ACTIVE.set(originals)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def hash_path(path):
    if path.is_symlink():
        raise ValueError("snapshot root may not be symlink")
    data = _ACTIVE.get().get(path.resolve())
    if data is not None:
        return native.sha256_bytes(data)
    if _ACTIVE.get() and path.is_dir():
        # Preserve every path and every unrelated byte. Only the pinned owner
        # adapter files can reconstruct their original historical contract.
        rows = []
        for child in sorted(path.rglob("*")):
            if child.is_symlink():
                raise ValueError("snapshot tree contains symlink")
            if child.is_file():
                rows.append((child.relative_to(path).as_posix(), hash_path(child)))
        return native.sha256_value(rows)
    return native.hash_path(path)


class _OriginalFile:
    def __init__(self, path, payload):
        self.path, self.payload = path, payload

    def read_bytes(self):
        return self.payload

    def read_text(self, encoding="utf-8"):
        return self.payload.decode(encoding)


def resolve_file(root, relative):
    path = native.resolve_file(root, relative)
    data = _ACTIVE.get().get(path.resolve())
    return path if data is None else _OriginalFile(path, data)


def hash_refs(root, refs):
    if not refs:
        raise ValueError("refs must be non-empty")
    return {relative: native.sha256_bytes(resolve_file(root, relative).read_bytes()) for relative in refs}

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path


def _git_paths(repository_root: Path, *arguments: str) -> list[str]:
    environment = dict(os.environ)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    result = subprocess.run(
        ["git", "-c", "core.longpaths=true", "-C", str(repository_root), *arguments],
        capture_output=True,
        check=True,
        env=environment,
        timeout=120,
    )
    payload = result.stdout.encode("utf-8") if isinstance(result.stdout, str) else result.stdout
    return [item.decode("utf-8") for item in payload.split(b"\0") if item]


def _copy_worktree_path(repository_root: Path, relative: str, clone_root: Path) -> None:
    source = repository_root / relative
    target = clone_root / relative
    if not source.exists():
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        shutil.copy2(source, target)


def _include_untracked_test_input(relative: str, plan: str) -> bool:
    excluded = (
        f"{plan}/.acceptance-snapshots/",
        f"{plan}/acceptance-inputs/",
        f"{plan}/acceptance-runs/",
        "knowledge/indexes/generations/",
        "logs/",
    )
    return not relative.startswith(excluded)


def _native_path(path: Path) -> Path:
    if os.name != "nt":
        return path
    rendered = os.path.abspath(str(path))
    if rendered.startswith("\\\\?\\"):
        return Path(rendered)
    if rendered.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + rendered[2:])
    return Path("\\\\?\\" + rendered)


def read_only_index_tree(repository_root: Path) -> str:
    temporary = Path(tempfile.mkdtemp(prefix="ri", dir=repository_root.anchor))
    try:
        git_directory = repository_root / ".git"
        index = temporary / "index"
        objects = temporary / "objects"
        shutil.copy2(git_directory / "index", index)
        objects.mkdir()
        environment = dict(os.environ)
        environment.update({
            "GIT_INDEX_FILE": str(index),
            "GIT_OBJECT_DIRECTORY": str(objects),
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(git_directory / "objects"),
            "GIT_OPTIONAL_LOCKS": "0",
        })
        result = subprocess.run(
            ["git", "write-tree"], cwd=repository_root, env=environment,
            capture_output=True, check=True, timeout=120,
        )
        return result.stdout.decode("ascii").strip()
    finally:
        native = _native_path(temporary)
        if native.exists():
            shutil.rmtree(native)


@contextmanager
def isolated_test_repository(repository_root: Path, plan_root: Path):
    temporary = Path(tempfile.mkdtemp(prefix="r", dir=repository_root.anchor))
    try:
        clone_root = temporary / "repository"
        subprocess.run(
            [
                "git", "-c", "core.longpaths=true", "clone", "--quiet", "--shared",
                str(repository_root), str(clone_root),
            ],
            capture_output=True,
            check=True,
            timeout=180,
        )
        plan = plan_root.relative_to(repository_root).as_posix()
        exact_roots = [
            plan,
            "agentbuild.txt",
            ".agents/skills/quick-dev-tdd-adapter",
            ".agents/skills/run-phase-bootstrap-review",
            ".agents/skills/vdd-execution-plan",
            "execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening",
            "execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan",
            "execution-plans/2026-07-12-llm-review-evidence-gate-hardening",
        ]
        for relative in _git_paths(repository_root, "ls-files", "-z", "--", *exact_roots):
            _copy_worktree_path(repository_root, relative, clone_root)
        changed = set(_git_paths(repository_root, "diff", "--name-only", "--no-ext-diff", "-z"))
        changed.update(_git_paths(repository_root, "diff", "--cached", "--name-only", "--no-ext-diff", "-z"))
        changed.update(
            relative
            for relative in _git_paths(repository_root, "ls-files", "--others", "--exclude-standard", "-z")
            if _include_untracked_test_input(relative, plan)
        )
        for relative in sorted(changed):
            _copy_worktree_path(repository_root, relative, clone_root)
        yield clone_root
    finally:
        native = _native_path(temporary)
        if native.exists():
            shutil.rmtree(native)

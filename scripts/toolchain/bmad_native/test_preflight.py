"""ADR-0041/ADR-0062: real fail-closed entries, no synthetic native success."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest

from scripts.toolchain.bmad_native import NativeError, RECEIPT, SUPPORTED, load_lock, verify
from scripts.toolchain.bmad_native.install import install
from scripts.toolchain.bmad_native.testing import REPO, command, fixture, load

bridge = load("preflight_bridge", ".agents/skills/jimuyun-spec/scripts/bridge.py")
architecture = load("preflight_architecture", ".agents/skills/jimuyun-architecture/scripts/invoke.py")


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("defect,expected", [
    ("missing", "NATIVE_INSTALLATION_MISSING"),
    ("old", "NATIVE_VERSION_OLD"),
    ("newer", "NATIVE_VERSION_NEWER"),
    ("bmad7", "NATIVE_VERSION_NEWER"),
    ("changed", "NATIVE_TREE_DRIFT"),
    ("extra", "NATIVE_TREE_DRIFT"),
    ("missing-dependency", "NATIVE_RUNTIME_MISSING"),
    ("wrong-dependency", "NATIVE_RUNTIME_DRIFT"),
    ("shadow-dependency", "NATIVE_RUNTIME_DRIFT"),
    ("bad-config", "NATIVE_CONFIG_INVALID"),
    ("missing-config", "NATIVE_CONFIG_INVALID"),
])
def test_all_mutating_entries_fail_without_changes(tmp_path, defect, expected):
    root = fixture(tmp_path / "space \u4e2d\u6587")
    (root / "intent.md").write_text("Approved local intent.\n", encoding="utf-8")
    if defect == "missing":
        shutil.rmtree(root / ".agents/skills/bmad-spec")
    elif defect in {"old", "newer", "bmad7"}:
        version = {"old": "6.10.0", "newer": "6.12.5", "bmad7": "7.0.0"}[defect]
        (root / RECEIPT).write_text(json.dumps({"version": version}), encoding="utf-8")
    elif defect == "changed":
        (root / ".agents/skills/bmad-spec/SKILL.md").write_text("changed")
    elif defect == "extra":
        (root / ".agents/skills/bmad-spec/compatibility.py").write_text("pass")
    elif defect == "missing-dependency":
        (root / "_bmad/scripts/config_utils.py").unlink()
    elif defect == "wrong-dependency":
        (root / "_bmad/scripts/config_utils.py").write_text("raise RuntimeError('must never execute')")
    elif defect == "shadow-dependency":
        (root / "_bmad/scripts/json.py").write_text("raise RuntimeError('must never execute')")
    elif defect == "missing-config":
        (root / "_bmad/config.toml").unlink()
    else:
        (root / "_bmad/config.user.toml").write_text("[broken")
    before = snapshot(root)
    for call in [
        lambda: bridge.prepare(root, "_bmad-output/specs/spec-test/SPEC.md", "logs/bmad-wrappers/test", "SPEC-test"),
        lambda: bridge.publish(root, "logs/bmad-wrappers/test"),
        lambda: architecture.prepare(root, "logs/bmad-wrappers/test", ["intent.md"]),
    ]:
        with pytest.raises(NativeError) as error:
            call()
        assert error.value.code == expected
        assert "6.12.4" in error.value.result()["message"]
        assert snapshot(root) == before
    cli = command([sys.executable, "-B", str(REPO / ".agents/skills/jimuyun-spec/scripts/canonical_package.py"),
                   "--repo-root", str(root), "--spec", str(root / "unavailable/SPEC.md"), "--publish"], REPO)
    assert cli.returncode == 2
    assert json.loads(cli.stdout)["error"] == expected
    assert snapshot(root) == before


def test_missing_uv_and_unsupported_python_block_before_writes(tmp_path, monkeypatch):
    root = fixture(tmp_path / "root")
    before = snapshot(root)
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(NativeError, match="NATIVE_RUNTIME_MISSING"):
        bridge.prepare(root, "_bmad-output/specs/spec-test/SPEC.md", "logs/bmad-wrappers/test", "SPEC-test")
    assert snapshot(root) == before
    monkeypatch.setattr(sys, "version_info", (3, 10))
    with pytest.raises(NativeError, match="NATIVE_RUNTIME_MISSING"):
        verify(root)


def test_real_toml_merge_explicit_root_and_output_binding(tmp_path):
    root = fixture(tmp_path / "space \u4e2d\u6587")
    (root / "input.md").write_text("Approved local constraints.", encoding="utf-8")
    custom = root / "_bmad/custom"; custom.mkdir()
    (root / "_bmad/config.user.toml").write_text('[core]\nproject_name="user"\n', encoding="utf-8")
    (custom / "config.toml").write_text('[core]\nproject_name="team"\n', encoding="utf-8")
    (custom / "config.user.toml").write_bytes('[core]\nproject_name="\u4e2d\u6587 merged"\n'.replace('\n','\r\n').encode())
    result = architecture.prepare(root, "logs/bmad-wrappers/config", ["input.md"])
    native = root / "logs/bmad-wrappers/config/native"
    config = command(["uv", "run", str(native / "_bmad/scripts/resolve_config.py"), "--project-root", str(native)], tmp_path)
    assert config.returncode == 0, config.stderr
    resolved = json.loads(config.stdout)
    assert resolved["core"]["project_name"] == "\u4e2d\u6587 merged"
    assert resolved["core"]["output_folder"] == (native / "_bmad-output").as_posix()
    assert resolved["modules"]["bmm"]["planning_artifacts"] == (native / "_bmad-output/planning-artifacts").as_posix()
    override = native / "_bmad/custom"; override.mkdir()
    (override / "bmad-architecture.toml").write_text('[workflow]\npersistent_facts=["explicit caller constraint"]\n', encoding="utf-8")
    resolved = command(["uv", "run", str(native / "_bmad/scripts/resolve_customization.py"), "--skill",
                        str(native / ".agents/skills/bmad-architecture"), "--project-root", str(native), "--key", "workflow"], tmp_path)
    assert resolved.returncode == 0, resolved.stderr
    assert json.loads(resolved.stdout)["workflow"]["persistent_facts"] == ["explicit caller constraint"]
    assert (native / "AGENTS.md").is_file()
    prompt = (root / result["invocation"]).read_text(encoding="utf-8")
    assert "explicit repository constraints" in prompt and "--project-root" in prompt
    verify(root); verify(native)


def test_official_manifest_version_and_conflicts(tmp_path):
    root = fixture(tmp_path / "root")
    (root / RECEIPT).unlink()
    manifest = root / "_bmad/_config/manifest.yaml"; manifest.parent.mkdir()
    manifest.write_text("installation:\n  version: 6.12.4\nmodules: []\n", encoding="utf-8")
    verify(root)
    (root / RECEIPT).write_text('{"version":"6.10.0"}', encoding="utf-8")
    with pytest.raises(NativeError, match="NATIVE_VERSION_CONFLICT"):
        verify(root)


def test_source_install_checks_before_replacing_and_preserves_backup(tmp_path):
    root = fixture(tmp_path / "project"); before = snapshot(root)
    source = tmp_path / "source"; source.mkdir()
    (source / "package.json").write_text('{"name":"bmad-method","version":"6.12.4"}', encoding="utf-8")
    lock = load_lock()
    for relative in [*lock["files"], *lock["runtime"]]:
        if relative.startswith(".agents/"):
            name = relative.split("/")[2]
            rel = lock["trees"][name]["source"] + "/" + "/".join(relative.split("/")[3:])
        else:
            rel = "src/scripts/" + Path(relative).name
        p = source / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes((root / relative).read_bytes())
    with pytest.raises(NativeError, match="NATIVE_INSTALL_CONFLICT"):
        install(root, source)
    assert snapshot(root) == before
    broken = source / "src/scripts/config_utils.py"; original = broken.read_bytes(); broken.write_text("broken")
    with pytest.raises(NativeError, match="NATIVE_SOURCE_MISMATCH"):
        install(root, source, True)
    assert snapshot(root) == before
    broken.write_bytes(original)
    result = install(root, source, True)
    assert result["version"] == SUPPORTED
    assert Path(result["backup"]).joinpath(".agents/skills/bmad-spec/SKILL.md").is_file()
    verify(root)


def test_untracked_distribution_and_retained_custom_bytes():
    import subprocess
    inventory = json.loads((REPO / "scripts/toolchain/bmad_native/distribution-inventory.json").read_text())
    tracked = set(subprocess.check_output(["git", "ls-files"], cwd=REPO, text=True).splitlines())
    for row in inventory["files"]:
        if row["action"] == "untrack":
            assert row["path"] not in tracked
        else:
            assert row["path"] in tracked
            assert hashlib.sha256((REPO / row["path"]).read_bytes()).hexdigest() == row["baseline_sha256"]

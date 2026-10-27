"""ADR-0062: device customization transport through unchanged public wrappers."""
import json
from pathlib import Path
import sys

import pytest

from scripts.toolchain.bmad_native import invocation, new_workspace, verify
from scripts.toolchain.bmad_native.testing import command, fixture, load

bridge = load("device_spec_bridge", ".agents/skills/jimuyun-spec/scripts/bridge.py")
architecture = load("device_architecture", ".agents/skills/jimuyun-architecture/scripts/invoke.py")


def user_file(root, skill="bmad-spec"):
    path = root / f"_bmad/custom/{skill}.user.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def prepare(root, stage, name):
    run = f"logs/bmad-wrappers/{name}"
    if stage == "spec":
        return bridge.prepare(root, f"_bmad-output/specs/{name}/SPEC.md", run, f"SPEC-{name}")
    return architecture.prepare(root, run, ["intent.md"])


@pytest.mark.parametrize("stage", ["spec", "architecture"])
def test_two_new_public_runs_load_original_user_bytes_and_keep_output_binding(tmp_path, stage):
    root = fixture(tmp_path / "project")
    (root / "intent.md").write_text("Approved source-read check only.\n")
    skill = f"bmad-{stage}"
    data = '[workflow]\r\npersistent_facts=["file:approved-source.md"]\r\n'.encode()
    user_file(root, skill).write_bytes(data)
    for name in ("first", "second"):
        result = prepare(root, stage, name)
        native = root / "logs/bmad-wrappers" / name / "native"
        assert (native / f"_bmad/custom/{skill}.user.toml").read_bytes() == data
        resolved = command([sys.executable, "-B", str(native / "_bmad/scripts/resolve_customization.py"),
                            "--project-root", str(native), "--skill", str(native / ".agents/skills" / skill),
                            "--key", "workflow"], tmp_path)
        assert resolved.returncode == 0, resolved.stderr
        workflow = json.loads(resolved.stdout)["workflow"]
        assert workflow["persistent_facts"] == ["file:approved-source.md"]
        if stage == "spec":
            assert workflow["spec_output_path"] == (native / "_bmad-output/specs").as_posix()
            assert workflow["run_folder_pattern"] == name
        else:
            assert f"doc_workspace={native.as_posix()}/_bmad-output/architecture" in (root / result["invocation"]).read_text()
        verify(root)
        verify(native)


@pytest.mark.parametrize("stage", ["spec", "architecture"])
def test_no_user_configuration_preserves_existing_public_behavior(tmp_path, stage):
    root = fixture(tmp_path / "project")
    (root / "intent.md").write_text("Approved fixture input.\n")
    result = prepare(root, stage, "default")
    native = root / "logs/bmad-wrappers/default/native"
    assert not (native / f"_bmad/custom/bmad-{stage}.user.toml").exists()
    assert (root / result["invocation"]).read_text().endswith(
        (native / f".agents/skills/bmad-{stage}/SKILL.md").read_text())


@pytest.mark.parametrize("key", ["spec_output_path", "spec_filename", "spine_output_path",
                                  "run_folder_pattern", "doc_workspace", "output_folder", "planning_artifacts"])
def test_device_configuration_cannot_change_private_output_contract(tmp_path, key):
    root = fixture(tmp_path / "project")
    user_file(root).write_text(f'[workflow]\n{key}="outside"\n')
    with pytest.raises(ValueError, match="NATIVE_CUSTOMIZATION_OUTPUT_CONFLICT"):
        prepare(root, "spec", "blocked")
    assert not (root / "logs/bmad-wrappers/blocked/invocation.md").exists()
    assert not (root / "logs/bmad-wrappers/blocked/native/_bmad/custom/bmad-spec.user.toml").exists()


@pytest.mark.parametrize("data,error", [
    (b"[broken", "INVALID"), (b'workflow="bad"', "INVALID"), (b"\xff", "INVALID"),
    (b'[core]\noutput_folder="outside"', "OUTPUT_CONFLICT"),
    (b'[modules.bmm]\nplanning_artifacts="outside"', "OUTPUT_CONFLICT"),
])
def test_invalid_or_central_configuration_is_not_transferred(tmp_path, data, error):
    root = fixture(tmp_path / "project")
    user_file(root).write_bytes(data)
    with pytest.raises(ValueError, match=f"NATIVE_CUSTOMIZATION_{error}"):
        prepare(root, "spec", "invalid")


def test_only_selected_skill_is_carried_and_conflicts_are_not_overwritten(tmp_path):
    root = fixture(tmp_path / "project")
    original = b'[workflow]\npersistent_facts=["original"]\n'
    user_file(root).write_bytes(original)
    user_file(root, "bmad-architecture").write_text('[workflow]\npersistent_facts=["other"]\n')
    folder, native = new_workspace(root, "logs/bmad-wrappers/conflict")
    target = user_file(native)
    target.write_text('[workflow]\npersistent_facts=["existing"]\n')
    before = target.read_bytes()
    with pytest.raises(ValueError, match="NATIVE_CUSTOMIZATION_CONFLICT"):
        invocation(root, folder, native, "bmad-spec", "Approved fixture.")
    assert target.read_bytes() == before
    target.write_bytes(original)
    invocation(root, folder, native, "bmad-spec", "Approved fixture.")
    assert target.read_bytes() == original
    assert not (native / "_bmad/custom/bmad-architecture.user.toml").exists()


@pytest.mark.parametrize("location", ["source", "target", "parent"])
def test_symlink_escape_is_rejected(tmp_path, location):
    root = fixture(tmp_path / "project")
    outside = tmp_path / "outside.toml"
    outside.write_text('[workflow]\npersistent_facts=["outside"]\n')
    source = user_file(root)
    source.write_text('[workflow]\npersistent_facts=["approved"]\n')
    folder, native = new_workspace(root, "logs/bmad-wrappers/escape")
    target = user_file(native)
    if location == "source":
        source.unlink()
        source.symlink_to(outside)
    elif location == "target":
        target.symlink_to(outside)
    else:
        target.parent.rmdir()
        target.parent.symlink_to(outside.parent, target_is_directory=True)
    before = outside.read_bytes()
    with pytest.raises(ValueError, match="UNSAFE_PATH"):
        invocation(root, folder, native, "bmad-spec", "Approved fixture.")
    assert outside.read_bytes() == before


def test_configuration_cannot_be_copied_to_an_external_verified_install(tmp_path):
    root = fixture(tmp_path / "project")
    external = fixture(tmp_path / "external")
    user_file(root).write_text('[workflow]\npersistent_facts=["private"]\n')
    with pytest.raises(ValueError, match="RUN_OUTSIDE_LOGS"):
        invocation(root, external.parent, external, "bmad-spec", "Approved fixture.")
    assert not (external / "_bmad/custom/bmad-spec.user.toml").exists()


def test_non_file_source_and_unknown_skill_reject(tmp_path):
    root = fixture(tmp_path / "project")
    user_file(root).mkdir()
    folder, native = new_workspace(root, "logs/bmad-wrappers/invalid-source")
    with pytest.raises(ValueError, match="NATIVE_CUSTOMIZATION_INVALID"):
        invocation(root, folder, native, "bmad-spec", "Approved fixture.")
    with pytest.raises(ValueError, match="UNSUPPORTED_NATIVE_SKILL"):
        invocation(root, folder, native, "../../unregistered", "Approved fixture.")

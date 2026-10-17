from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_evidence import hash_path


def test_project_snapshot_excludes_outputs_but_detects_source(tmp_path):
    (tmp_path / "Test.csproj").write_text("<Project />", encoding="utf-8")
    source = tmp_path / "Test.cs"
    source.write_text("class Test {}", encoding="utf-8")
    original = hash_path(tmp_path)
    for directory in ("bin", "obj", "TestResults"):
        output = tmp_path / directory
        output.mkdir()
        (output / "generated.txt").write_text("output", encoding="utf-8")
    assert hash_path(tmp_path) == original
    source.write_text("class Changed {}", encoding="utf-8")
    assert hash_path(tmp_path) != original


def test_explicit_output_and_non_project_bin_remain_bound(tmp_path):
    output = tmp_path / "bin"
    output.mkdir()
    file = output / "fixture.txt"
    file.write_text("before", encoding="utf-8")
    tree_hash, file_hash = hash_path(tmp_path), hash_path(file)
    file.write_text("after", encoding="utf-8")
    assert hash_path(tmp_path) != tree_hash
    assert hash_path(file) != file_hash

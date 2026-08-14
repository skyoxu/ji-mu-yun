from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from canonical_package import build_contract


def write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def make_spec(root: Path, companions: str, sources: str) -> Path:
    spec = root / "_bmad-output/specs/spec-example/SPEC.md"
    write(
        spec,
        "---\n"
        "id: SPEC-example\n"
        "package_schema: canonical-spec-package.v1\n"
        f"companions:\n{companions}"
        f"sources:\n{sources}"
        "---\n\n# Example\n",
    )
    return spec


def test_builds_typed_descriptor_and_selection(tmp_path: Path) -> None:
    write(tmp_path / "_bmad-output/specs/spec-example/contract.md")
    write(tmp_path / "execution-plans/example.md")
    spec = make_spec(
        tmp_path,
        "  - path: _bmad-output/specs/spec-example/contract.md\n    role: normative_companion\n",
        "  - path: execution-plans/example.md\n    role: provenance\n",
    )

    descriptor, selection, selection_hash = build_contract(tmp_path, spec)

    assert descriptor["package_schema"] == "canonical-spec-package.v1"
    assert selection["role_graph"][0]["role"] == "canonical"
    assert selection["descriptor_hash"].startswith("sha256:")
    assert selection_hash.startswith("sha256:")


def test_rejects_legacy_string_arrays(tmp_path: Path) -> None:
    write(tmp_path / "_bmad-output/specs/spec-example/contract.md")
    spec = make_spec(
        tmp_path,
        "  - _bmad-output/specs/spec-example/contract.md\n",
        "[]\n",
    )

    with pytest.raises(ValueError, match="typed path/role"):
        build_contract(tmp_path, spec)


def test_rejects_duplicate_casefolded_paths(tmp_path: Path) -> None:
    write(tmp_path / "_bmad-output/specs/spec-example/contract.md")
    spec = make_spec(
        tmp_path,
        "  - path: _bmad-output/specs/spec-example/contract.md\n    role: normative_companion\n"
        "  - path: _bmad-output/specs/spec-example/CONTRACT.md\n    role: adopted_companion\n",
        "[]\n",
    )

    with pytest.raises(ValueError):
        build_contract(tmp_path, spec)


def test_accepts_empty_typed_arrays(tmp_path: Path) -> None:
    spec = tmp_path / "_bmad-output/specs/spec-example/SPEC.md"
    write(
        spec,
        "---\n"
        "id: SPEC-example\n"
        "package_schema: canonical-spec-package.v1\n"
        "companions: []\n"
        "sources: []\n"
        "---\n\n# Example\n",
    )

    descriptor, _, _ = build_contract(tmp_path, spec)

    assert descriptor["companions"] == []
    assert descriptor["sources"] == []


def test_unlisted_sibling_does_not_gain_authority(tmp_path: Path) -> None:
    write(tmp_path / "_bmad-output/specs/spec-example/notes.md")
    spec = tmp_path / "_bmad-output/specs/spec-example/SPEC.md"
    write(
        spec,
        "---\n"
        "id: SPEC-example\n"
        "package_schema: canonical-spec-package.v1\n"
        "companions: []\n"
        "sources: []\n"
        "---\n\n# Example\n",
    )

    descriptor, selection, _ = build_contract(tmp_path, spec)

    assert descriptor["companions"] == []
    assert all(entry["path"] != "_bmad-output/specs/spec-example/notes.md" for entry in selection["role_graph"])

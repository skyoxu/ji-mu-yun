"""Intentional preflight RED: S1 artifacts are not implementation evidence yet."""
from pathlib import Path


def test_semantic_artifact_set_is_not_prebuilt() -> None:
    artifact = Path(__file__).parent.parent / "semantic-artifacts.v1.json"
    assert artifact.is_file(), "FAILURE_ID:VDD-SEMANTIC-ARTIFACT-SET-INCOMPLETE"

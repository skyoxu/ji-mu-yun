import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.toolchain.candidate_content_paths import (
    CANDIDATE_CONTENT,
    GENERATED_RUN_EVIDENCE,
    HISTORICAL_EVIDENCE,
    classify_path,
)


def test_classifies_candidate_content_and_non_candidate_evidence() -> None:
    assert classify_path("scripts/sc/skill_package_replay.py") == CANDIDATE_CONTENT
    assert classify_path("docs/adr/ADR-0058-toolchain-skill-replay-portability-and-evaluation-seeds.md") == CANDIDATE_CONTENT
    assert classify_path("execution-plans/target/knowledge-context.freeze.history/a.v1.json") == HISTORICAL_EVIDENCE
    assert classify_path("execution-plans/target/knowledge-context.history/a.v1.json") == HISTORICAL_EVIDENCE
    assert classify_path("execution-plans/target/skill-input/receipt.json") == GENERATED_RUN_EVIDENCE
    assert classify_path("execution-plans/target/skill-input-snapshot-quickdev-9/source-manifest.v1.json") == GENERATED_RUN_EVIDENCE

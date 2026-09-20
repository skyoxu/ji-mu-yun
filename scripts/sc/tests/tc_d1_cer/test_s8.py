"""CER coverage for repair-evidence append-only preservation."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / ".agents" / "skills" / "quick-dev-tdd-adapter" / "tools" / "build_repair_review_handoff.py"
FAILURE_ID = "FR5_REPAIR_EVIDENCE_REWRITE"


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _request(root: Path) -> dict[str, object]:
    (root / "execution-plans" / "example").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "logs").mkdir()
    (root / "src" / "consumer.py").write_text("consume()\n", encoding="utf-8")
    (root / "tests" / "test_consumer.py").write_text("def test_consumer():\n    pass\n", encoding="utf-8")
    (root / "logs" / "validation.json").write_text("{}\n", encoding="utf-8")
    for name in ("baseline", "candidate"):
        (root / "logs" / f"{name}.json").write_text("{}\n", encoding="utf-8")
    return {
        "schemaVersion": "quick-dev-repair-review-handoff-input.v1",
        "repositoryRoot": str(root),
        "acceptanceTarget": "execution-plans/example",
        "lineageFamilyId": "repair-evidence-family",
        "semanticRoundsConsumed": 0,
        "predecessorRun": None,
        "baselineManifestPath": "logs/baseline.json",
        "baselineManifestHash": _sha256(root / "logs" / "baseline.json"),
        "candidateManifestPath": "logs/candidate.json",
        "candidateManifestHash": _sha256(root / "logs" / "candidate.json"),
        "changedFiles": ["src/consumer.py"],
        "directConsumers": ["src/consumer.py"],
        "targetedTests": ["tests/test_consumer.py"],
        "validationRefs": ["logs/validation.json"],
        "rootCauseInventories": [{"inventoryId": "repair-evidence"}],
        "compositionChecks": [{"checkId": "repair-evidence"}],
        "novelP0P1FindingIds": [],
        "authorityGraphChanged": False,
        "highRiskBoundaryChanged": False,
        "authorizes": [],
    }


@pytest.mark.cer_assertion("FR-5-repair-evidence-append-only")
@pytest.mark.parametrize(
    "historical_bytes",
    [
        pytest.param(b'{"segments":["overwritten-history"]}\n', id="overwritten"),
        pytest.param(b'{"segments":[]}\n', id="deleted"),
        pytest.param(b'{"segments":["rewritten-history"]}\n', id="rewritten"),
    ],
)
def test_existing_repair_evidence_is_preserved_when_new_output_is_requested(
    historical_bytes: bytes,
) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        root = Path(directory)
        request_path = root / "request.json"
        request_path.write_text(json.dumps(_request(root)), encoding="utf-8")
        evidence_path = root / "repair-evidence.json"
        evidence_path.write_bytes(historical_bytes)

        result = subprocess.run(
            [sys.executable, "-B", str(ENTRY), "--request", str(request_path), "--out", str(evidence_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        preserved = result.returncode != 0 and evidence_path.read_bytes() == historical_bytes
        if not preserved:
            print(f"FAILURE_ID:{FAILURE_ID}")
        assert preserved, "recording new repair evidence must not rewrite existing repair evidence"

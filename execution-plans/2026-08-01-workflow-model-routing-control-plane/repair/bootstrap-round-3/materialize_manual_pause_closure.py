from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
TARGET = "execution-plans/2026-08-01-workflow-model-routing-control-plane"
FAMILY = "ria-77945989035b122f005c98a2c3661cd2"
RUN = ROOT / TARGET / "repair/bootstrap-round-3"
CHANGED = [
    ".agents/skills/run-refactor-implementation-acceptance/scripts/repair_completeness.py",
    ".agents/skills/run-refactor-implementation-acceptance/tests/test_repair_completeness.py",
]
TEST = ".agents/skills/run-refactor-implementation-acceptance/tests/test_repair_completeness.py"
RECEIPT = f"{TARGET}/repair/bootstrap-round-3/repair-composition-receipt.v1.json"
PROTOCOL_REVIEW = (
    "logs/ci/2026-08-01/manual-pause-closure-protocol-v2-r3/"
    "finalized-run-validation.v3.json"
)
FINALIZED_RUN = "logs/ci/2026-08-01/wmr-r3"
FINALIZED_ENVELOPE = f"{FINALIZED_RUN}/finalized-run-validation.v3.json"
BASELINE = f"{TARGET}/repair/bootstrap-round-3/baseline-content-manifest.v1.json"
CANDIDATE = f"{TARGET}/repair/bootstrap-round-3/candidate-content-manifest.v1.json"
HANDOFF_INPUT = f"{TARGET}/repair/bootstrap-round-3/quick-dev-handoff-input.manual-pause.v1.json"
REPAIR_REQUEST = f"{TARGET}/repair/bootstrap-round-3/acceptance-repair-completeness-request.manual-pause.v1.json"
REPAIR_RESULT = f"{TARGET}/repair/bootstrap-round-3/repair-completeness.manual-pause.v1.json"
ROUTE_REQUEST = f"{TARGET}/repair/bootstrap-round-3/manual-pause-route.v3.request.json"
ROUTE = f"{TARGET}/repair/bootstrap-round-3/manual-pause-route.v3.json"
CLOSURE_REQUEST = f"{TARGET}/repair/bootstrap-round-3/manual-pause-closure.request.v1.json"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write_new(relative: str, value: object) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")


def binding(relative: str) -> dict[str, str]:
    return {"path": relative, "sha256": digest(ROOT / relative)}


def materialize_repair_input() -> None:
    artifact_manifest = read(f"{FINALIZED_RUN}/artifact-view/manifest.json")
    frozen = {
        item["originalPath"]: item["snapshotSha256"]
        for item in artifact_manifest["entries"]
        if item["originalPath"] in CHANGED
    }
    if set(frozen) != set(CHANGED):
        raise RuntimeError("Round 3 Artifact View does not bind every repaired path")
    baseline = {
        "schemaVersion": "acceptance-baseline-content-manifest.v1",
        "status": "complete",
        "coverageGaps": [],
        "authorizes": [],
        "files": [
            {
                "path": relative,
                "sha256": frozen[relative],
                "roles": ["implementation"],
                "inclusion_reason": "Frozen Bootstrap Round 3 repair baseline",
            }
            for relative in CHANGED
        ],
    }
    candidate = {
        "schemaVersion": "acceptance-candidate-content-manifest.v1",
        "status": "complete",
        "coverageGaps": [],
        "authorizes": [],
        "files": [
            {
                "change_type": "modified",
                "roles": ["implementation"],
                "baseline_path": relative,
                "baseline_sha256": frozen[relative],
                "candidate_path": relative,
                "candidate_sha256": digest(ROOT / relative),
                "inclusion_reason": "Confirmed Round 3 targeted-test receipt binding repair",
            }
            for relative in CHANGED
        ],
    }
    write_new(BASELINE, baseline)
    write_new(CANDIDATE, candidate)
    validation_refs = [FINALIZED_ENVELOPE, PROTOCOL_REVIEW, RECEIPT]
    handoff = {
        "schemaVersion": "quick-dev-repair-review-handoff-input.v1",
        "repositoryRoot": str(ROOT),
        "acceptanceTarget": TARGET,
        "lineageFamilyId": FAMILY,
        "semanticRoundsConsumed": 3,
        "predecessorRun": FINALIZED_RUN,
        "baselineManifestPath": BASELINE,
        "baselineManifestHash": digest(ROOT / BASELINE),
        "candidateManifestPath": CANDIDATE,
        "candidateManifestHash": digest(ROOT / CANDIDATE),
        "changedFiles": CHANGED,
        "directConsumers": [CHANGED[0]],
        "targetedTests": [TEST],
        "validationRefs": sorted(validation_refs),
        "rootCauseInventories": [
            {
                "inventoryId": "targeted-test-receipt-binding",
                "searchTerm": "targeted_test_paths",
                "searchRoots": [
                    ".agents/skills/run-refactor-implementation-acceptance/scripts"
                ],
                "addressedPaths": [CHANGED[0]],
                "exclusions": [],
            },
            {
                "inventoryId": "stale-targeted-test-regression",
                "searchTerm": "test_audit_rejects_receipt_for_stale_targeted_test_bytes",
                "searchRoots": [
                    ".agents/skills/run-refactor-implementation-acceptance/tests"
                ],
                "addressedPaths": [CHANGED[1]],
                "exclusions": [],
            },
        ],
        "compositionChecks": [
            {
                "checkId": "acceptance-bootstrap-loader-composition",
                "producerPaths": [
                    ".agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py"
                ],
                "consumerPaths": [CHANGED[0]],
                "receiptPath": RECEIPT,
                "commandRegistryPath": (
                    f"{TARGET}/repair/bootstrap-round-1/"
                    "acceptance-loader-command-registry.v1.json"
                ),
            }
        ],
        "novelP0P1FindingIds": [
            "BSR-70B71A7460628393",
            "BSR-9BC70F2A4289C44C",
            "BSR-E5FA31807675B5D1",
        ],
        "authorityGraphChanged": True,
        "highRiskBoundaryChanged": False,
        "authorizes": [],
    }
    write_new(HANDOFF_INPUT, handoff)


def materialize_route_request() -> None:
    route_request = read(f"{TARGET}/repair/bootstrap-round-3/manual-pause-route.request.json")
    route_request["repair_completeness_request"] = read(REPAIR_REQUEST)
    route_request["repair_completeness"] = read(REPAIR_RESULT)
    runtime_evidence = route_request["scope_inputs"]["runtime_evidence"]
    route_request["scope_inputs"]["runtime_evidence"] = sorted({
        *runtime_evidence,
        BASELINE,
        CANDIDATE,
        HANDOFF_INPUT,
        REPAIR_REQUEST,
        REPAIR_RESULT,
        RECEIPT,
        PROTOCOL_REVIEW,
        (
            f"{TARGET}/repair/bootstrap-round-1/"
            "acceptance-loader-command-registry.v1.json"
        ),
    })
    write_new(ROUTE_REQUEST, route_request)


def materialize_closure_request() -> None:
    validation_refs = sorted([PROTOCOL_REVIEW, RECEIPT])
    repairs = [
        {
            "findingId": finding_id,
            "changedPaths": CHANGED,
            "targetedTests": [TEST],
            "validationRefs": validation_refs,
        }
        for finding_id in (
            "BSR-70B71A7460628393",
            "BSR-9BC70F2A4289C44C",
            "BSR-E5FA31807675B5D1",
        )
    ]
    authorities = [
        binding(".agents/skills/run-refactor-implementation-acceptance/SKILL.md"),
        binding("docs/adr/ADR-0054-refactor-acceptance-manual-pause-closure.md"),
        binding("docs/standards/bootstrap-review-control-plane.md"),
    ]
    closure = {
        "schemaVersion": "acceptance-manual-pause-closure-request.v1",
        "repositoryRoot": str(ROOT),
        "acceptanceTarget": TARGET,
        "lineageFamilyId": FAMILY,
        "manualPauseRoute": binding(ROUTE),
        "manualPauseRouteRequest": binding(ROUTE_REQUEST),
        "finalizedRun": {
            "runDirectory": FINALIZED_RUN,
            "envelopePath": FINALIZED_ENVELOPE,
            "envelopeSha256": digest(ROOT / FINALIZED_ENVELOPE),
        },
        "repairCompletenessRequest": read(REPAIR_REQUEST),
        "repairCompleteness": read(REPAIR_RESULT),
        "findingRepairs": repairs,
        "protocolAuthorities": sorted(authorities, key=lambda item: item["path"]),
        "authorizes": [],
    }
    write_new(CLOSURE_REQUEST, closure)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("repair-input", "route-request", "closure-request"))
    args = parser.parse_args()
    {
        "repair-input": materialize_repair_input,
        "route-request": materialize_route_request,
        "closure-request": materialize_closure_request,
    }[args.mode]()

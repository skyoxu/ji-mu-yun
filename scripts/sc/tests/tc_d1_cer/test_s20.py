"""S20 bounded CER checks for isolation and Exact Cover decisions."""
from __future__ import annotations

import copy
import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
CONFORMANCE = ROOT / ".agents" / "skills" / "vdd-conformance-exact-cover" / "scripts" / "conformance.py"
NEGATIVE_FIXTURE = ROOT / ".agents" / "skills" / "vdd-conformance-exact-cover" / "tests" / "validators" / "exact_cover_negative.py"


def _load_conformance():
    scope = runpy.run_path(str(CONFORMANCE), run_name="s20_conformance")
    return scope["exact_cover"]


def _assert_target(condition: bool, failure_id: str, detail: object) -> None:
    if not condition:
        print(f"FAILURE_ID:{failure_id}")
    assert condition, detail


def _mapping(*, orphan: bool = False, missing_reverse: bool = False, missing_witness: bool = False) -> dict:
    obligation = "O-S20"
    nodes = [{"id": obligation, "node_type": "atomic_obligation"}]
    edges: list[dict[str, str]] = []
    for node_type in ("assertions", "selectors", "commands", "witnesses", "runtime_evidence"):
        node_id = f"N-{node_type}"
        if node_type == "witnesses" and missing_witness:
            continue
        nodes.append({"id": node_id, "node_type": node_type})
        edges.append({"source": obligation, "target": node_id})
        if not (missing_reverse and node_type == "assertions"):
            edges.append({"source": node_id, "target": obligation})
    if orphan:
        nodes.append({"id": "W-ORPHAN", "node_type": "witnesses"})
    return {
        "requirements": [{"id": "FR-11", "acceptance_ids": ["A-S20"]}],
        "acceptance_ids": ["A-S20"],
        "reverse_mapping": {"A-S20": ["FR-11"]},
        "exact_cover_graph": {"nodes": nodes, "edges": edges},
    }


def _negative_fixture_mapping() -> dict:
    return {
        "requirements": [{"id": "FR-11", "acceptance_ids": ["VCEC-A01"]}],
        "acceptance_ids": ["VCEC-A01"],
        "reverse_mapping": {"VCEC-A01": ["FR-11"]},
    }


def _evaluate(exact_cover, mapping: dict) -> dict:
    return exact_cover(
        mapping["requirements"],
        mapping["acceptance_ids"],
        mapping["reverse_mapping"],
        mapping.get("exact_cover_graph"),
    )


@pytest.mark.parametrize(
    "mutation",
    [pytest.param("independent", marks=pytest.mark.cer_assertion("A-NFR4-ISO-1"))],
)
def test_mutable_state_and_evidence_are_isolated(mutation: str) -> None:
    entities = {
        name: {"state": {"value": 0}, "evidence": {"verdict": "pending"}}
        for name in ("Subjects", "Probes", "Matrix Cases", "Consumers", "rollback stages")
    }
    identities = [(id(item["state"]), id(item["evidence"])) for item in entities.values()]
    before = copy.deepcopy(entities)
    entities["Subjects"]["state"]["value"] = 1
    entities["Subjects"]["evidence"]["verdict"] = "checked"
    peers_unchanged = all(entities[name] == before[name] for name in entities if name != "Subjects")
    distinct_containers = len(set(identities)) == len(entities)
    _assert_target(
        mutation == "independent" and peers_unchanged and distinct_containers,
        "FI-NFR4-SHARED-STATE",
        {"peer_state": peers_unchanged, "distinct_containers": distinct_containers},
    )


@pytest.mark.parametrize(
    "orphan",
    [
        pytest.param(False, marks=pytest.mark.cer_assertion("FR-11-exact-cover-no-orphans")),
        pytest.param(True, marks=pytest.mark.cer_assertion("FR-11-exact-cover-no-orphans")),
    ],
)
def test_structural_exact_cover_rejects_orphan_nodes(orphan: bool) -> None:
    exact_cover = _load_conformance()
    result = _evaluate(exact_cover, _mapping(orphan=orphan))
    expected = (result["status"] == "blocked" and result["orphan_nodes"] == ["W-ORPHAN"]) if orphan else (
        result["status"] == "conformant" and result["orphan_nodes"] == []
    )
    _assert_target(expected, "EXACT-COVER-ORPHAN-NODE-REJECTED", {"orphan": orphan, "result": result})


@pytest.mark.parametrize(
    "missing_witness",
    [
        pytest.param(False, marks=pytest.mark.cer_assertion("SM-1.required-witnesses-cover-every-atomic-obligation")),
        pytest.param(True, marks=pytest.mark.cer_assertion("SM-1.required-witnesses-cover-every-atomic-obligation")),
    ],
)
def test_required_witness_coverage_is_complete_or_blocked(missing_witness: bool) -> None:
    exact_cover = _load_conformance()
    result = _evaluate(exact_cover, _mapping(missing_witness=missing_witness))
    coverage = result["node_type_coverage"]["O-S20"]
    expected = (result["status"] == "blocked" and coverage["witnesses"] == "missing") if missing_witness else (
        result["status"] == "conformant" and coverage["witnesses"] == "complete"
    )
    _assert_target(expected, "FI-8299BF590523-MISSING-WITNESS", {"missing_witness": missing_witness, "result": result})


def _run_negative_fixture(mapping: dict) -> subprocess.CompletedProcess[str]:
    child = (
        "import json, runpy, sys\n"
        "from pathlib import Path\n"
        "payload = json.load(sys.stdin)\n"
        "original_read = Path.read_text\n"
        "def bounded_read(path, *args, **kwargs):\n"
        "    if path.name == 'requirements-acceptance-slice-command.v1.json':\n"
        "        return json.dumps(payload)\n"
        "    return original_read(path, *args, **kwargs)\n"
        "Path.read_text = bounded_read\n"
        "scope = runpy.run_path(sys.argv[1], run_name='s20_negative_fixture')\n"
        "raise SystemExit(scope['main']())\n"
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", child, str(NEGATIVE_FIXTURE)],
        cwd=ROOT,
        input=json.dumps(mapping),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@pytest.mark.cer_assertion("SM-2-adversarial-target-success-rejected")
def test_adversarial_target_success_is_rejected() -> None:
    result = _run_negative_fixture(_negative_fixture_mapping())
    _assert_target(
        result.returncode == 1,
        "ADVERSARIAL-TARGET-SUCCESS-REJECTED",
        {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr},
    )


@pytest.mark.parametrize(
    "missing_reverse",
    [
        pytest.param(False, marks=pytest.mark.cer_assertion("SM-1-atomic-inventory-bidirectional-exact-cover")),
        pytest.param(True, marks=pytest.mark.cer_assertion("SM-1-atomic-inventory-bidirectional-exact-cover")),
    ],
)
def test_atomic_inventory_requires_bidirectional_exact_cover(missing_reverse: bool) -> None:
    exact_cover = _load_conformance()
    result = _evaluate(exact_cover, _mapping(missing_reverse=missing_reverse))
    expected = (result["status"] == "blocked" and result["bidirectional"] is False) if missing_reverse else (
        result["status"] == "conformant" and result["bidirectional"] is True
    )
    _assert_target(
        expected,
        "ATOMIC-INVENTORY-PARTIAL-EXACT-COVER-REJECTED",
        {"missing_reverse": missing_reverse, "result": result},
    )

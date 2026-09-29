"""Bounded CER checks for obligation graph exact-cover validation."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
VALIDATOR = ROOT / ".agents/skills/vdd-conformance-exact-cover/scripts/validate_conformance.py"
NEGATIVE_FIXTURE = ROOT / ".agents/skills/vdd-conformance-exact-cover/tests/validators/exact_cover_negative.py"
OBLIGATION = "O-F61D63C2F175"
ASSERTION = "A-F61D63C2F175-1"
NODE_TYPES = ("assertions", "selectors", "commands", "witnesses", "runtime_evidence")
FAILURE_ID = "F-F61D63C2F175-1"


def _complete_mapping() -> dict:
    nodes = [{"id": OBLIGATION, "node_type": "atomic_obligation"}]
    edges = []
    for node_type in NODE_TYPES:
        node_id = ASSERTION if node_type == "assertions" else f"N-{node_type}"
        nodes.append({"id": node_id, "node_type": node_type})
        edges.extend((
            {"source": OBLIGATION, "target": node_id},
            {"source": node_id, "target": OBLIGATION},
        ))
    return {
        "schema_version": "vdd.semantic-plan-bundle.v1",
        "requirements": [{"id": "FR-11", "acceptance_ids": ["A-4AC794A8333A"]}],
        "acceptance_ids": ["A-4AC794A8333A"],
        "reverse_mapping": {"A-4AC794A8333A": ["FR-11"]},
        "exact_cover_graph": {"nodes": nodes, "edges": edges},
        "authorizes": [],
    }


def _run_validator(mapping: dict) -> tuple[int, dict]:
    child = (
        "import json, runpy, sys\n"
        "from pathlib import Path\n"
        "payload = json.load(sys.stdin)\n"
        "original_read = Path.read_text\n"
        "def bounded_read(path, *args, **kwargs):\n"
        "    if path == Path('cer-mapping.json'):\n"
        "        return json.dumps(payload)\n"
        "    return original_read(path, *args, **kwargs)\n"
        "Path.read_text = bounded_read\n"
        "sys.path.insert(0, str(Path(sys.argv[1]).parent))\n"
        "sys.argv = [sys.argv[1], '--mapping', 'cer-mapping.json']\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", child, str(VALIDATOR)],
        cwd=ROOT,
        input=json.dumps(mapping),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert not result.stderr, result.stderr
    verdict = json.loads(result.stdout)
    assert isinstance(verdict, dict) and verdict.get("authorizes") == [], verdict
    return result.returncode, verdict


def _assert_target(condition: bool, message: str) -> None:
    if not condition:
        print(f"FAILURE_ID:{FAILURE_ID}")
    assert condition, message


@pytest.mark.cer_assertion("A-F61D63C2F175-1")
@pytest.mark.parametrize(
    "mutation",
    ("complete", "missing-reverse-edge", "missing-node-type", "orphan-node"),
)
def test_exact_cover_graph_reports_bidirectionality_type_coverage_and_orphans(
    mutation: str,
) -> None:
    mapping = _complete_mapping()
    graph = mapping["exact_cover_graph"]
    if mutation == "missing-reverse-edge":
        graph["edges"].remove({"source": ASSERTION, "target": OBLIGATION})
    elif mutation == "missing-node-type":
        witness_id = "N-witnesses"
        graph["nodes"] = [node for node in graph["nodes"] if node["id"] != witness_id]
        graph["edges"] = [edge for edge in graph["edges"] if witness_id not in edge.values()]
    elif mutation == "orphan-node":
        graph["nodes"].append({"id": "W-ORPHAN", "node_type": "witnesses"})

    exit_code, verdict = _run_validator(mapping)
    coverage = verdict.get("node_type_coverage")
    obligation_coverage = coverage.get(OBLIGATION) if isinstance(coverage, dict) else None
    if mutation == "complete":
        matches = (
            exit_code == 0
            and verdict.get("status") == "conformant"
            and verdict.get("bidirectional") is True
            and verdict.get("orphan_nodes") == []
            and isinstance(obligation_coverage, dict)
            and all(obligation_coverage.get(node_type) == "complete" for node_type in NODE_TYPES)
        )
    elif mutation == "missing-reverse-edge":
        matches = exit_code == 2 and verdict.get("status") == "blocked" and verdict.get("bidirectional") is False
    elif mutation == "missing-node-type":
        matches = (
            exit_code == 2
            and verdict.get("status") == "blocked"
            and isinstance(obligation_coverage, dict)
            and obligation_coverage.get("witnesses") != "complete"
            and all(obligation_coverage.get(node_type) == "complete" for node_type in NODE_TYPES if node_type != "witnesses")
        )
    else:
        matches = exit_code == 2 and verdict.get("status") == "blocked" and verdict.get("orphan_nodes") == ["W-ORPHAN"]
    _assert_target(matches, f"Exact Cover must report the graph verdict for {mutation}: {verdict}")


@pytest.mark.cer_assertion("A-F61D63C2F175-1")
def test_existing_negative_fixture_rejects_a_missing_reverse_binding() -> None:
    mapping = _complete_mapping()
    mapping["requirements"] = [{"id": "FR-11", "acceptance_ids": ["VCEC-A01"]}]
    mapping["acceptance_ids"] = ["VCEC-A01"]
    mapping["reverse_mapping"] = {"VCEC-A01": ["FR-11"]}
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
        "scope = runpy.run_path(sys.argv[1], run_name='bounded_negative_fixture')\n"
        "raise SystemExit(scope['main']())\n"
    )
    fixture_result = subprocess.run(
        [sys.executable, "-B", "-c", child, str(NEGATIVE_FIXTURE)],
        cwd=ROOT,
        input=json.dumps(mapping),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert not fixture_result.stderr, fixture_result.stderr

    mutated = copy.deepcopy(mapping)
    mutated["reverse_mapping"]["VCEC-A01"] = []
    exit_code, verdict = _run_validator(mutated)
    _assert_target(
        fixture_result.returncode == 1
        and exit_code == 2
        and verdict.get("status") == "blocked"
        and any(error.get("code") == "wrong_binding" for error in verdict.get("errors", [])),
        f"The bounded negative fixture must reject the removed reverse binding: {verdict}",
    )

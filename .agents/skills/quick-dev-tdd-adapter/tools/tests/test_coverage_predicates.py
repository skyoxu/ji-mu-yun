from __future__ import annotations

import json
from pathlib import Path
import sys
from contextlib import contextmanager

import pytest

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from coverage_predicates import publish_implementation_complete, validate_slice_ready
from current_router import materialize_descriptor, successor_descriptor
from runtime_evidence import create_json, sha256_value
from stage_pipeline import execute_stage

STAGES = ("red", "green", "refactor", "terminal")


def semantic_bundle() -> dict:
    primary = [sys.executable, "-m", "pytest", "tests/test_one.py", "-q"]
    return {
        "schema_version": "vdd.semantic-plan-bundle.v1",
        "plan_id": "P1",
        "obligations": [{
            "obligation_id":"O-ONE","requirement_id":"FR-1","source_refs":["source.txt#FR-1"],
            "subject":"value","trigger":"run","state_before":"red","state_after":"green",
            "expected_behavior":"all assertions pass","observable_result":"pytest exit zero","forbidden_result":[],
            "requirement_type":"Platform","obligation_kind":"behavior","unresolved_fragments":[],"status":"active","depends_on":[],
        }],
        "acceptances": [{
            "acceptance_id": "A-ONE", "obligation_ids":["O-ONE"], "source_refs":["source.txt#FR-1"],
            "given":"a current candidate","when":"the selector runs","then":"both bound assertions pass",
            "oracle":{"observable":"pytest","expected":"pass","forbidden":["red value"]},
            "assertion_ids": ["AS-1", "AS-2"], "red_intent_ids":["FI-ONE"],
        }],
        "failure_intents": [{
            "failure_intent_id": "FI-ONE", "acceptance_ids":["A-ONE"], "failure_id": "EXPECTED-RED",
            "failure_family":"expected-red", "selector_intent":"tests/test_one.py", "expected_outcome":"fail",
        }],
        "slices": [{
            "slice_id": "S1", "acceptance_ids": ["A-ONE"], "failure_intent_ids": ["FI-ONE"],
            "production_owners":["candidate.txt", "candidate.py"], "allowed_write_paths":["candidate.txt", "candidate.py"],
            "execution_snapshot_paths":["tests/test_one.py","tests/test_terminal.py","fixture.txt"],
            "planned_new_files":[], "terminal_predicate":"all assertions pass",
        }],
        "final_plan_coverage": [{"slice_id": "S1", "acceptance_id": "A-ONE", "stage_scope": list(STAGES)}],
        "agent_contexts":[{
            "slice_id":"S1","requirement_ids":["FR-1"],"obligation_ids":["O-ONE"],"acceptance_ids":["A-ONE"],
            "source_refs":["source.txt#FR-1"],"contracts":["contract.json"],"allowed_paths":["candidate.txt"],
            "forbidden_paths":[],"selector_intents":["tests/test_one.py"],"validation_commands":[primary],
        }],
    }



def write_production_binding(root: Path):
    """Current RED guard needs a real declared Python production call."""
    (root / "candidate.py").write_text(
        "from pathlib import Path\ndef current_value():\n"
        " return Path(__file__).with_name('candidate.txt').read_text(encoding='utf-8').strip()\n",
        encoding="utf-8")


def prepare(root: Path):
    (root / "tests").mkdir()
    (root / "plan").mkdir()
    (root / "RUN-1" / "descriptors").mkdir(parents=True)
    (root / "candidate.txt").write_text("red\n", encoding="utf-8")
    write_production_binding(root)
    (root / "contract.json").write_text("{}\n", encoding="utf-8")
    (root / "fixture.txt").write_text("fixture\n", encoding="utf-8")
    (root / "source.txt").write_text("# FR-1\nvalue must be green\n", encoding="utf-8")
    (root / "validator.py").write_text("# validator\n", encoding="utf-8")
    (root / "transition.json").write_text("{}\n", encoding="utf-8")
    (root / "tests" / "test_one.py").write_text(
        "from pathlib import Path\nfrom candidate import current_value\n"
        "import pytest\n"
        "@pytest.mark.cer_assertion('AS-1', 'AS-2')\n"
        "def test_one():\n"
        " root=Path(__file__).resolve().parents[1]\n"
        " value=current_value()\n"
        " if value!='green': print('FAILURE_ID:EXPECTED-RED')\n"
        " assert value=='green'\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_terminal.py").write_text(
        "from pathlib import Path\nfrom candidate import current_value\n"
        "import pytest\n"
        "@pytest.mark.cer_assertion('AS-1', 'AS-2')\n"
        "def test_terminal():\n"
        " root=Path(__file__).resolve().parents[1]\n"
        " assert (root/'candidate.txt').read_text(encoding='utf-8').strip()=='green'\n",
        encoding="utf-8",
    )
    semantic = root / "plan" / "semantic-plan-bundle.v1.json"
    semantic.write_text(json.dumps(semantic_bundle()), encoding="utf-8")
    roots = [{"root_kind": kind, "repository_relative_posix_path": path, "inclusion_reason": "test"} for kind, path in (
        ("candidate_tree", "candidate.txt"), ("plan", "plan/semantic-plan-bundle.v1.json"), ("contract", "contract.json"),
        ("descriptor", "RUN-1/descriptors"), ("fixture", "fixture.txt"), ("source", "source.txt"),
        ("validator_judge", "validator.py"), ("plan_state_transition", "transition.json"),
    )]
    return semantic, roots


def execute_nonterminal_stages(root: Path, semantic: Path) -> tuple[Path, dict, dict, dict]:
    bundle = json.loads(semantic.read_text(encoding="utf-8"))
    run = root / "RUN-1"
    candidate_red = "sha256:" + "0" * 64
    candidate_green = "sha256:" + "1" * 64
    red = materialize_descriptor(
        bundle=bundle, slice_id="S1", stage="red", run_id="RUN-1", candidate_hash=candidate_red,
        argv=[sys.executable,"-m","pytest","tests/test_one.py","-q"], cwd=".", timeout_seconds=30,
        target_refs=["tests/test_one.py"], fixture_refs=["fixture.txt"],
    )
    green = successor_descriptor(red, stage="green", run_id="RUN-1", candidate_hash=candidate_green)
    refactor = successor_descriptor(red, stage="refactor", run_id="RUN-1", candidate_hash=candidate_green)
    terminal = materialize_descriptor(
        bundle=bundle, slice_id="S1", stage="terminal", run_id="RUN-1", candidate_hash=candidate_green,
        argv=[sys.executable,"-m","pytest","tests/test_terminal.py","-q"], cwd=".", timeout_seconds=30,
        target_refs=["tests/test_terminal.py"], fixture_refs=["fixture.txt"],
    )
    for stage, descriptor in (("red", red), ("green", green), ("refactor", refactor), ("terminal", terminal)):
        create_json(run / "descriptors" / f"{stage}.json", descriptor)
    red_result = execute_stage(workspace=root, semantic_plan=semantic, run_dir=run, descriptor_path=run/"descriptors"/"red.json", profile_identity="standard")
    assert red_result["failure_family"] == "expected-red" and red_result["predicate_result"] is True
    (root / "candidate.txt").write_text("green\n", encoding="utf-8")
    green_result = execute_stage(workspace=root, semantic_plan=semantic, run_dir=run, descriptor_path=run/"descriptors"/"green.json", profile_identity="standard")
    refactor_result = execute_stage(workspace=root, semantic_plan=semantic, run_dir=run, descriptor_path=run/"descriptors"/"refactor.json", profile_identity="standard")
    assert green_result["predicate_result"] is True and refactor_result["predicate_result"] is True
    return run, red_result, green_result, refactor_result


def test_q7_and_q8_cover_all_assertions_with_current_runtime(tmp_path: Path) -> None:
    semantic, roots = prepare(tmp_path)
    run, _red, _green, refactor = execute_nonterminal_stages(tmp_path, semantic)
    assert refactor["regression_gate"]["ref"] == "canonical-evidence/refactor/regression-gate.v1.json"
    ready_path = run / "slice-ready-result.v2.json"
    ready = validate_slice_ready(workspace=tmp_path, semantic_plan=semantic, run_root=run, slice_id="S1", snapshot_roots=roots, source_commit="TEST", out=ready_path)
    assert len(ready["assertion_coverage"]["green"]["A-ONE"]) == 2
    terminal = execute_stage(workspace=tmp_path, semantic_plan=semantic, run_dir=run, descriptor_path=run/"descriptors"/"terminal.json", profile_identity="standard")
    assert terminal["predicate_result"] is True
    predecessor = {"slice_id": "S1", "run_root": "RUN-1", "result_ref": "RUN-1/slice-ready-result.v2.json", "result_sha256": sha256_value(ready)}
    result = publish_implementation_complete(workspace=tmp_path, semantic_plan=semantic, predecessors=[predecessor], snapshot_roots=roots, source_commit="TEST", out=run / "implementation-complete-result.v2.json")
    assert result["status"] == "pass"
    assert len(result["runtime_closure_tuples"]) == 4


def test_q7_rejects_mutated_runtime_edge_bytes(tmp_path: Path) -> None:
    semantic, roots = prepare(tmp_path)
    run, _red, green, _refactor = execute_nonterminal_stages(tmp_path, semantic)
    edge_ref = green["runtime_edges"][0]["path"]
    (run / edge_ref).write_text("{}\n", encoding="utf-8")
    try:
        validate_slice_ready(workspace=tmp_path, semantic_plan=semantic, run_root=run, slice_id="S1", snapshot_roots=roots, source_commit="TEST", out=run / "ready.json")
    except ValueError:
        pass
    else:
        raise AssertionError("Q7 must reject mutated runtime edge bytes")


def _q8_fixture(root):
    semantic, roots = prepare(root)
    run, _, _, _ = execute_nonterminal_stages(root, semantic)
    path = run / "ready.json"
    ready = validate_slice_ready(workspace=root, semantic_plan=semantic, run_root=run,
        slice_id="S1", snapshot_roots=roots, source_commit="TEST", out=path)
    terminal = execute_stage(workspace=root, semantic_plan=semantic, run_dir=run,
        descriptor_path=run/"descriptors/terminal.json", profile_identity="standard")
    assert terminal["predicate_result"] is True
    return dict(workspace=root, semantic_plan=semantic, snapshot_roots=roots,
        source_commit="TEST", out=root/"Q8/complete.json", predecessors=[{
            "slice_id":"S1", "run_root":"RUN-1", "result_ref":"RUN-1/ready.json",
            "result_sha256":sha256_value(ready)}])


def test_q8_deduplicates_originals_but_checks_every_edge_within_replay_context(tmp_path, monkeypatch):
    import coverage_predicates as predicates
    import shared_execution
    args = _q8_fixture(tmp_path)
    calls, edges, notifications, active = [], [], [], []
    real_saved = shared_execution.validate_saved_request
    real_edge = predicates._reread_edge
    @contextmanager
    def epoch(*_):
        active.append(True)
        try:
            yield
        finally:
            active.pop()
    def saved(*a, **kw):
        assert active == [True]  # Deferred checks cannot escape a replay epoch.
        calls.append(a[1])
        return real_saved(*a, **kw)
    def edge(*a, **kw):
        edges.append(kw['stage'])
        return real_edge(*a, **kw)
    monkeypatch.setattr(predicates, 'replay_budget_transition', epoch)
    monkeypatch.setattr(shared_execution, 'validate_saved_request', saved)
    monkeypatch.setattr(predicates, '_reread_edge', edge)
    monkeypatch.setattr(predicates, 'progress', lambda call, data: notifications.append(data))
    first = publish_implementation_complete(**args)
    assert first['status'] == 'pass' and len(first['runtime_closure_tuples']) == 4
    assert len(edges) == 11  # terminal 2 + (2 assertion refs + canonical) * 3 stages
    assert len(calls) == 4  # one original per red/green/refactor/terminal stage
    assert len([x for x in notifications if x.startswith(b'original:')]) == 4
    assert len([x for x in notifications if x.startswith(b'Q8-tuple:')]) == 4
    assert len({x for x in notifications if x.startswith(b'Q8-edge:')}) == 8
    publish_implementation_complete(**{**args, 'out':tmp_path/'Q8-second/complete.json'})
    assert len(calls) == 8 and len(edges) == 22  # Nothing cached across calls.


@pytest.mark.parametrize('mutation', ['missing_predecessor', 'duplicate_predecessor',
    'ready_hash', 'terminal_edge', 'terminal_duplicate', 'stdout', 'fixture'])
def test_q8_rejects_bad_proof_without_publishing(tmp_path, mutation):
    args = _q8_fixture(tmp_path)
    run = tmp_path/'RUN-1'
    if mutation == 'missing_predecessor':
        args['predecessors'] = []
    elif mutation == 'duplicate_predecessor':
        args['predecessors'] *= 2
    elif mutation == 'ready_hash':
        args['predecessors'][0]['result_sha256'] = 'sha256:' + '0'*64
    elif mutation == 'terminal_edge':
        result = json.loads((run/'canonical-evidence/terminal/stage-result.v2.json').read_text())
        (run/result['runtime_edges'][0]['path']).write_text('{}')
    elif mutation == 'terminal_duplicate':
        path = run/'canonical-evidence/terminal/stage-result.v2.json'
        result = json.loads(path.read_text());result['runtime_edges'].append(result['runtime_edges'][0])
        path.write_text(json.dumps(result))
    elif mutation == 'stdout':
        (run/'canonical-evidence/refactor/stdout.bin').write_bytes(b'changed')
    else:
        (tmp_path/'fixture.txt').write_text('changed')
    with pytest.raises(ValueError):
        publish_implementation_complete(**args)
    assert not args['out'].exists()


def test_q8_detects_original_mutation_during_deferred_checks(tmp_path, monkeypatch):
    import shared_execution
    args = _q8_fixture(tmp_path)
    real = shared_execution.validate_saved_request
    count = []
    def changed(*a, **kw):
        real(*a, **kw)
        if not count:
            (tmp_path/'RUN-1/canonical-evidence/terminal/stdout.bin').write_bytes(b'changed')
        count.append(1)
    monkeypatch.setattr(shared_execution, 'validate_saved_request', changed)
    with pytest.raises(ValueError, match='Q8 original/input changed during validation'):
        publish_implementation_complete(**args)
    assert not args['out'].exists()

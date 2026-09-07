"""ADR-0041: CER-R1--R3 through real pytest and the current stage/coverage seams."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from case_evidence import assertion_cases
from current_router import materialize_descriptor
from process_executor_v2 import execute_process
from runtime_evidence import create_json, sha256_value
from stage_pipeline import execute_stage
from test_coverage_predicates import prepare, semantic_bundle, execute_nonterminal_stages
from coverage_predicates import validate_slice_ready, publish_implementation_complete


def run_task(root, source, *, stage="terminal", args=(), binding=None, timeout=10):
    (root / "tests").mkdir()
    (root / "tests/test_one.py").write_text(source, encoding="utf-8")
    (root / "fixture.txt").write_text("fixture", encoding="utf-8")
    bundle = semantic_bundle()
    semantic = root / "plan.json"
    semantic.write_text(json.dumps(bundle), encoding="utf-8")
    run = root / "RUN-CER"
    descriptor = materialize_descriptor(
        bundle=bundle, slice_id="S1", stage=stage, run_id=run.name,
        candidate_hash="sha256:" + "0" * 64,
        argv=[sys.executable, "-m", "pytest", "tests/test_one.py", "-q", *args],
        cwd=".", timeout_seconds=timeout, target_refs=["tests/test_one.py"], fixture_refs=["fixture.txt"])
    if binding:
        binding(descriptor)
    path = run / "descriptors" / (stage + ".json")
    create_json(path, descriptor)
    result = execute_stage(workspace=root, semantic_plan=semantic, run_dir=run,
                           descriptor_path=path, profile_identity="fast-ship")
    receipt = json.loads((run / "canonical-evidence" / stage / "process-receipt.v2.json").read_text())
    return result, descriptor, receipt


PASS = "import pytest\n@pytest.mark.cer_assertion('AS-1','AS-2')\ndef test_ok():\n assert 1 == 1\n"


def test_real_case_pass_has_bound_ids(tmp_path):
    result, descriptor, receipt = run_task(tmp_path, PASS)
    assert result["predicate_result"] is True
    assert assertion_cases(descriptor, receipt)[("A-ONE", "AS-1")] == ["tests/test_one.py::test_ok"]
    assert receipt["cases"] == 1


@pytest.mark.parametrize("source,args,reason", [
    ("def test_ok():\n print('ASSERTION_ID:AS-1 ASSERTION_ID:AS-2')\n assert True\n", (), "assertion-binding-gap"),
    ("import pytest\n@pytest.mark.cer_assertion('AS-1','AS-2')\n@pytest.mark.parametrize('x',[1,2])\ndef test_param(x):\n assert x>0\n", ("-k", "[1]"), "case-missing-or-deselected"),
    (PASS + "\n@pytest.mark.cer_assertion('AS-1')\n@pytest.mark.skip(reason='not run')\ndef test_skip():\n assert False\n", (), "case-skipped"),
    (PASS + "\n@pytest.mark.cer_assertion('AS-1')\n@pytest.mark.xfail\ndef test_expected_failure():\n assert False\n", (), "case-skipped"),
    (PASS + "\n@pytest.mark.cer_assertion('AS-1')\n@pytest.mark.xfail\ndef test_unexpected_pass():\n assert True\n", (), "case-xfail-unsupported"),
    ("import pytest\n@pytest.fixture\ndef broken():\n raise RuntimeError('setup')\n@pytest.mark.cer_assertion('AS-1','AS-2')\ndef test_setup(broken):\n assert True\n", (), "case-not-executed"),
    ("import pytest\n@pytest.fixture\ndef broken():\n yield\n raise RuntimeError('teardown')\n@pytest.mark.cer_assertion('AS-1','AS-2')\ndef test_teardown(broken):\n assert True\n", (), "case-setup-or-teardown-error"),
])
def test_missing_skipped_or_unusable_cases_never_make_edges(tmp_path, source, args, reason):
    result, descriptor, receipt = run_task(tmp_path, source, args=args)
    assert result["predicate_result"] is False
    assert result["runtime_edges"] == []
    assert reason in result["case_evidence_error"]


def test_explicit_missing_instance_cannot_be_replaced_by_case_count(tmp_path):
    def bind(descriptor):
        for row in descriptor["case_contract"]["bindings"]:
            row.update(marker=None, case_ids=["tests/test_one.py::test_ok", "tests/test_one.py::test_missing"])
    result, _, _ = run_task(tmp_path, PASS, binding=bind)
    assert not result["predicate_result"]
    assert "case-missing" in result["case_evidence_error"]


def test_one_red_cannot_prove_an_unexecuted_case(tmp_path):
    source = """import pytest
@pytest.mark.cer_assertion('AS-1')
def test_first():
 print('FAILURE_ID:EXPECTED-RED')
 assert False
@pytest.mark.cer_assertion('AS-2')
def test_second():
 print('FAILURE_ID:EXPECTED-RED')
 assert False
"""
    result, _, _ = run_task(tmp_path, source, stage="red", args=("-x",))
    assert result["predicate_result"] is False
    assert "case-not-executed" in result["case_evidence_error"]


def test_failure_marker_without_behavior_assertion_is_not_red(tmp_path):
    source = PASS.replace("assert 1 == 1", "print('FAILURE_ID:EXPECTED-RED')\n raise RuntimeError('harness')")
    result, _, _ = run_task(tmp_path, source, stage="red")
    assert not result["predicate_result"]
    assert "case-unexpected-red" in result["case_evidence_error"]


@pytest.mark.parametrize("mutation", ["old-run", "old-descriptor", "truncated", "duplicate", "missing-call", "old-version"])
def test_invalid_or_replayed_report_cannot_be_admitted(tmp_path, mutation):
    _, descriptor, receipt = run_task(tmp_path, PASS)
    report = receipt["case_report"]
    if mutation == "old-run": report["run_id"] = "RUN-OLD"
    elif mutation == "old-descriptor": report["descriptor_sha256"] = "sha256:" + "f" * 64
    elif mutation == "truncated": report["complete"] = False
    elif mutation == "duplicate": report["events"].append(deepcopy(report["events"][0]))
    elif mutation == "missing-call": report["events"] = [e for e in report["events"] if e["phase"] != "call"]
    else: descriptor.pop("case_contract")
    receipt["case_report_sha256"] = sha256_value(report)
    with pytest.raises(ValueError):
        assertion_cases(descriptor, receipt)


def test_timeout_never_produces_case_proof(tmp_path):
    result, _, receipt = run_task(tmp_path, PASS.replace("assert 1 == 1", "import time; time.sleep(3)"), timeout=1)
    assert result["failure_family"] == "timeout-no-observation"
    assert receipt["case_report"] is None
    assert result["runtime_edges"] == []


def test_q7_rechecks_case_mapping_even_when_edge_hash_is_updated(tmp_path):
    semantic, roots = prepare(tmp_path)
    run, _, _, _ = execute_nonterminal_stages(tmp_path, semantic)
    stage_path = run / "canonical-evidence/green/stage-result.v2.json"
    stage = json.loads(stage_path.read_text())
    ref = stage["runtime_edges"][0]
    edge_path = run / ref["path"]
    edge = json.loads(edge_path.read_text())
    edge["case_ids"] = ["tests/test_one.py::invented"]
    edge_path.write_text(json.dumps(edge), encoding="utf-8")
    ref["sha256"] = sha256_value(edge)
    stage_path.write_text(json.dumps(stage), encoding="utf-8")
    with pytest.raises(ValueError, match="case-edge-binding-stale"):
        validate_slice_ready(workspace=tmp_path, semantic_plan=semantic, run_root=run,
                             slice_id="S1", snapshot_roots=roots, source_commit="TEST", out=run/"ready.json")


def test_q8_rechecks_second_assertion_not_only_first_edge(tmp_path):
    semantic, roots = prepare(tmp_path)
    run, _, _, _ = execute_nonterminal_stages(tmp_path, semantic)
    ready_path = run / "ready.json"
    ready = validate_slice_ready(workspace=tmp_path, semantic_plan=semantic, run_root=run,
                                 slice_id="S1", snapshot_roots=roots, source_commit="TEST", out=ready_path)
    execute_stage(workspace=tmp_path, semantic_plan=semantic, run_dir=run,
                  descriptor_path=run/"descriptors/terminal.json", profile_identity="standard")
    ref = ready["assertion_coverage"]["green"]["A-ONE"][1]
    edge_path = run / ref["path"]
    edge = json.loads(edge_path.read_text())
    edge["case_ids"] = ["tests/test_one.py::invented"]
    edge_path.write_text(json.dumps(edge), encoding="utf-8")
    ref["sha256"] = sha256_value(edge)
    ready_path.write_text(json.dumps(ready), encoding="utf-8")
    predecessor = {"slice_id": "S1", "run_root": "RUN-1", "result_ref": "RUN-1/ready.json",
                   "result_sha256": sha256_value(ready)}
    with pytest.raises(ValueError, match="case-edge-binding-stale"):
        publish_implementation_complete(workspace=tmp_path, semantic_plan=semantic,
            predecessors=[predecessor], snapshot_roots=roots, source_commit="TEST", out=run/"complete.json")


@pytest.mark.parametrize("contents", [None, "{", '{"schema":"quick-dev.pytest-case-report.v1","run_id":"RUN-OLD"}'])
def test_missing_truncated_or_old_runner_output_blocks(tmp_path, monkeypatch, contents):
    import case_evidence
    from types import SimpleNamespace
    original = case_evidence.subprocess.run

    def fake_runner(argv, **kwargs):
        if str(case_evidence.COLLECTOR) not in argv:
            return original(argv, **kwargs)
        if contents is not None:
            Path(argv[3]).write_text(contents, encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout=b"1 passed", stderr=b"")

    monkeypatch.setattr(case_evidence.subprocess, "run", fake_runner)
    result, _, receipt = run_task(tmp_path, PASS)
    assert result["predicate_result"] is False
    assert result["runtime_edges"] == []
    assert "case-report-missing-or-invalid" in receipt["case_report_error"]


def test_unsupported_command_cannot_fall_back_to_summary(tmp_path):
    result, _, receipt = run_task(tmp_path, PASS, binding=lambda d: d.update(argv=[sys.executable, "-c", "print('1 passed')"]))
    assert result["predicate_result"] is False
    assert "case-adapter-gap" in receipt["case_report_error"]


def test_setup_marker_cannot_supply_call_failure_identity(tmp_path):
    source = """import pytest
@pytest.fixture
def setup_marker():
 print('FAILURE_ID:EXPECTED-RED')
@pytest.mark.cer_assertion('AS-1','AS-2')
def test_behavior(setup_marker):
 assert False
"""
    result, _, _ = run_task(tmp_path, source, stage="red")
    assert not result["predicate_result"]
    assert "case-unexpected-red" in result["case_evidence_error"]


def test_descriptor_cannot_replace_semantic_failure_identity(tmp_path):
    def change(descriptor):
        descriptor["case_contract"]["bindings"][0]["expected_failure_ids"] = ["OTHER"]
    with pytest.raises(ValueError, match="case-failure-binding-differs"):
        run_task(tmp_path, PASS, stage="red", binding=change)


def test_green_cannot_shrink_dynamically_collected_red_case_set(tmp_path):
    from current_router import successor_descriptor
    semantic, _ = prepare(tmp_path)
    (tmp_path / "tests/test_one.py").write_text("""import pytest
from pathlib import Path
state = (Path(__file__).resolve().parents[1] / 'candidate.txt').read_text().strip()
@pytest.mark.cer_assertion('AS-1','AS-2')
@pytest.mark.parametrize('index', range(2 if state == 'red' else 1))
def test_one(index):
 if state == 'red': print('FAILURE_ID:EXPECTED-RED')
 assert state == 'green'
""", encoding="utf-8")
    run = tmp_path / "RUN-1"
    red = materialize_descriptor(bundle=json.loads(semantic.read_text()), slice_id="S1", stage="red",
        run_id=run.name, candidate_hash="sha256:" + "0" * 64,
        argv=[sys.executable, "-m", "pytest", "tests/test_one.py", "-q"], cwd=".", timeout_seconds=10,
        target_refs=["tests/test_one.py"], fixture_refs=["fixture.txt"])
    create_json(run / "descriptors/red.json", red)
    result = execute_stage(workspace=tmp_path, semantic_plan=semantic, run_dir=run,
        descriptor_path=run / "descriptors/red.json", profile_identity="standard")
    assert result["predicate_result"] is True
    (tmp_path / "candidate.txt").write_text("green\n", encoding="utf-8")
    green = successor_descriptor(red, stage="green", run_id=run.name, candidate_hash="sha256:" + "1" * 64)
    create_json(run / "descriptors/green.json", green)
    result = execute_stage(workspace=tmp_path, semantic_plan=semantic, run_dir=run,
        descriptor_path=run / "descriptors/green.json", profile_identity="standard")
    assert not result["predicate_result"]
    assert result["case_evidence_error"] == "case-set-changed-since-red"
    assert result["runtime_edges"] == []


def test_stage_only_red_cannot_authorize_current_implementation(tmp_path, monkeypatch):
    import stable_runner
    semantic, roots = prepare(tmp_path)
    monkeypatch.setattr(stable_runner, "ROOT", tmp_path)
    run = tmp_path / "RUN-1"
    create_json(run / "canonical-evidence/red/stage-result.v2.json", {
        "schema": "quick-dev.stage-result.v2", "stage": "red", "predicate_result": True,
        "verification_outcome": "fail", "failure_family": "expected-red"})
    with pytest.raises((ValueError, OSError)):
        stable_runner.q4_handoff(semantic=semantic, slice_id="S1", run_dir=run,
            snapshot_roots=roots, source_commit="TEST", base_commit=None)

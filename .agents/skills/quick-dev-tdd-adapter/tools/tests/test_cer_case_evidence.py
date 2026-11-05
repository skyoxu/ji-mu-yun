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
from test_coverage_predicates import prepare, semantic_bundle, execute_nonterminal_stages, write_production_binding
from coverage_predicates import validate_slice_ready, publish_implementation_complete


def run_task(root, source, *, stage="terminal", args=(), binding=None, timeout=10):
    (root / "tests").mkdir()
    (root / "candidate.txt").write_text("red\n", encoding="utf-8")
    write_production_binding(root)
    if stage == "red":
        source = "from candidate import current_value\n" + source
        source = source.replace(" assert False\n", " assert current_value() == 'green'\n")
        lines = source.splitlines(keepends=True)
        for i in reversed(range(len(lines))):
            if lines[i].startswith("def test_"):
                indent = len(lines[i + 1]) - len(lines[i + 1].lstrip())
                lines.insert(i + 1, " " * indent + "current_value()\n")
        source = "".join(lines)
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
    # ADR-0041: inject report damage at the actual bounded Popen boundary.
    # The removed subprocess.run path cannot exercise current report checks.
    import process_executor_v2 as executor
    from case_evidence import COLLECTOR
    original = executor.subprocess.Popen

    def damaged_report(argv, **kwargs):
        process = original(argv, **kwargs)
        if str(COLLECTOR) not in argv:
            return process
        output = Path(argv[argv.index(str(COLLECTOR)) + 2])
        wait = process.wait
        def finished(*args, **options):
            code = wait(*args, **options)
            if contents is None:
                output.unlink(missing_ok=True)
            else:
                output.write_text(contents, encoding="utf-8")
            return code
        process.wait = finished
        return process

    monkeypatch.setattr(executor.subprocess, "Popen", damaged_report)
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
from candidate import current_value
state = current_value()
@pytest.mark.cer_assertion('AS-1','AS-2')
@pytest.mark.parametrize('index', range(2 if state == 'red' else 1))
def test_one(index):
 current_value()
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


def sub_source(kind, action="pass", *, outer_fail=False):
    """ADR-0041: real pytest 9 subtests, including repeated legal contexts."""
    body = {
        "pass": "assert True",
        "fail": "assert False",
        "skip": "pytest.skip('child not executed')",
        "xfail": "pytest.xfail('child expected failure')",
    }[action]
    if kind == "unit":
        head = "class TestSub(unittest.TestCase):\n @pytest.mark.cer_assertion('AS-1','AS-2')\n def test_s(self):\n"
        indent, context = "  ", "self.subTest(step='same')"
    else:
        head = "@pytest.mark.cer_assertion('AS-1','AS-2')\ndef test_s(subtests):\n"
        indent, context = " ", "subtests.test(step='same')"
    source = "import pytest\nimport unittest\n" + head
    source += (f"{indent}for i in range(2):\n{indent} with {context}:\n"
               f"{indent}  print('FAILURE_ID:EXPECTED-RED')\n{indent}  if i == 0:\n"
               f"{indent}   {body}\n{indent}  else:\n{indent}   assert True\n")
    if outer_fail:
        source += f"{indent}assert False\n"
    return source


@pytest.mark.parametrize("kind", ["unit", "fixture"])
def test_sub_pass(tmp_path, kind):
    result, descriptor, receipt = run_task(tmp_path, sub_source(kind))
    assert result["predicate_result"] is True
    report = receipt["case_report"]
    assert report["errors"] == []
    assert receipt["cases"] == len(report["selected"]) == 1
    assert [e["phase"] for e in report["events"]] == ["setup", "call", "teardown"]
    assert assertion_cases(descriptor, receipt)[("A-ONE", "AS-1")] == report["selected"]


@pytest.mark.parametrize("kind", ["unit", "fixture"])
@pytest.mark.parametrize("action", ["fail", "skip", "xfail"])
def test_sub_block(tmp_path, kind, action):
    result, _, receipt = run_task(tmp_path, sub_source(kind, action))
    assert result["predicate_result"] is False
    assert result["runtime_edges"] == []
    assert receipt["cases"] == 1
    report = receipt["case_report"]
    assert report["errors"] == []
    assert len(report["events"]) == 3
    call = next(e for e in report["events"] if e["phase"] == "call")
    assert call["outcome"] != "passed"
    assert call["assertion_failure"] is False
    assert call["failure_ids"] == []
    if action == "skip":
        assert receipt["exit_code"] == 0  # A successful pytest exit cannot hide a child skip.


@pytest.mark.parametrize("kind", ["unit", "fixture"])
@pytest.mark.parametrize("outer", [False, True], ids=["child-red", "child-marker"])
def test_sub_not_red(tmp_path, kind, outer):
    source = sub_source(kind, "pass" if outer else "fail", outer_fail=outer)
    result, _, receipt = run_task(tmp_path, source, stage="red")
    assert result["predicate_result"] is False
    assert result["runtime_edges"] == []
    assert "case-unexpected-red" in result["case_evidence_error"]
    call = next(e for e in receipt["case_report"]["events"] if e["phase"] == "call")
    assert call["outcome"] == "failed"
    assert call["assertion_failure"] is False
    assert call["failure_ids"] == []


def test_plain_red(tmp_path):
    source = PASS.replace("assert 1 == 1", "print('FAILURE_ID:EXPECTED-RED')\n assert False")
    result, descriptor, receipt = run_task(tmp_path, source, stage="red")
    assert result["predicate_result"] is True
    assert assertion_cases(descriptor, receipt)[("A-ONE", "AS-1")] == ["tests/test_one.py::test_ok"]
    call = next(e for e in receipt["case_report"]["events"] if e["phase"] == "call")
    assert call["assertion_failure"] is True
    assert call["failure_ids"] == ["EXPECTED-RED"]


@pytest.mark.parametrize("damage", ["outer-dupe", "child-dupe", "unknown", "no-stamp", "no-parent"])
def test_sub_bad_report(tmp_path, damage):
    if damage == "no-parent":
        plugin = """from _pytest.runner import call_and_report
def pytest_runtest_protocol(item, nextitem):
 call_and_report(item, 'setup')
 call_and_report(item, 'call', log=False)
 call_and_report(item, 'teardown', nextitem=nextitem)
 return True
"""
    else:
        plugin = """import copy
import pytest
from _pytest.subtests import SubtestReport
hook = None
busy = False
def pytest_configure(config):
 global hook
 hook = config.hook
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_logreport(report):
 global busy
 yield
 mode = DAMAGE
 kind = type(report) is (pytest.TestReport if mode == 'outer-dupe' else SubtestReport)
 if busy or report.when != 'call' or not kind:
  return
 busy = True
 try:
  extra = copy.copy(report)
  if mode == 'unknown':
   class Unknown(SubtestReport):
    pass
   extra.__class__ = Unknown
  elif mode == 'no-stamp':
   del extra._jmy_case_observation
  hook.pytest_runtest_logreport(report=extra)
 finally:
  busy = False
""".replace("DAMAGE", repr(damage))
    (tmp_path / "conftest.py").write_text(plugin, encoding="utf-8")
    result, descriptor, receipt = run_task(tmp_path, PASS if damage == "outer-dupe" else sub_source("fixture"))
    assert result["predicate_result"] is False
    assert result["runtime_edges"] == []
    report = receipt["case_report"]
    if damage == "outer-dupe":
        assert report["errors"] == []
        assert "case-attempt-ambiguous" in result["case_evidence_error"]
    else:
        assert report["errors"]
        if damage == "no-parent":
            assert any(e.startswith("subtest-parent-call-missing:") for e in report["errors"])
    with pytest.raises(ValueError):
        assertion_cases(descriptor, receipt)
    from shared_execution import admissible
    with pytest.raises(ValueError):
        admissible(receipt)


def rejected_observation(result, descriptor, receipt, prefix, *, exit_code=0):
    """ADR-0041: neither stage proof nor reuse may consume hidden attempts."""
    assert result["predicate_result"] is False
    assert result["runtime_edges"] == []
    assert receipt["exit_code"] == exit_code
    report = receipt["case_report"]
    assert len(report["selected"]) == 1
    assert any(error.startswith(prefix) for error in report["errors"])
    with pytest.raises(ValueError):
        assertion_cases(descriptor, receipt)
    from shared_execution import admissible
    with pytest.raises(ValueError):
        admissible(receipt)


@pytest.mark.parametrize("stage", ["terminal", "red"])
def test_unlogged_attempt_cannot_authorize_stage(tmp_path, stage):
    plugin = """from _pytest.runner import call_and_report
def pytest_runtest_protocol(item, nextitem):
 call_and_report(item, 'setup')
 hidden = call_and_report(item, 'call', log=False)
 shown = call_and_report(item, 'call')
 print('CONTROLLED_REPEATED_ATTEMPTS:' + hidden.outcome + ',' + shown.outcome, flush=True)
 call_and_report(item, 'teardown', nextitem=nextitem)
 return True
"""
    source = """import pytest
attempts = 0
@pytest.mark.cer_assertion('AS-1', 'AS-2')
def test_ok():
 global attempts
 attempts += 1
 if attempts == FAIL_ON:
  print('FAILURE_ID:EXPECTED-RED')
  assert False
""".replace("FAIL_ON", "1" if stage == "terminal" else "2")
    (tmp_path / "conftest.py").write_text(plugin, encoding="utf-8")
    result, descriptor, receipt = run_task(tmp_path, source, stage=stage)
    rejected_observation(result, descriptor, receipt, "unlogged-case-report:",
                         exit_code=1 if stage == "red" else 0)
    stdout = (tmp_path / "RUN-CER/canonical-evidence" / stage / "stdout.bin").read_bytes()
    expected = b"failed,passed" if stage == "terminal" else b"passed,failed"
    assert b"CONTROLLED_REPEATED_ATTEMPTS:" + expected in stdout


def test_child_and_parent_cannot_consume_one_observation(tmp_path):
    plugin = """from _pytest.runner import call_and_report
from _pytest.subtests import SubtestContext, SubtestReport
def pytest_runtest_protocol(item, nextitem):
 call_and_report(item, 'setup')
 report = call_and_report(item, 'call', log=False)
 child = SubtestReport._new(report, SubtestContext(msg=None, kwargs={}), None, None)
 item.ihook.pytest_runtest_logreport(report=child)
 item.ihook.pytest_runtest_logreport(report=report)
 call_and_report(item, 'teardown', nextitem=nextitem)
 return True
"""
    (tmp_path / "conftest.py").write_text(plugin, encoding="utf-8")
    result, descriptor, receipt = run_task(tmp_path, PASS)
    rejected_observation(result, descriptor, receipt, "ambiguous-subtest-report:")


@pytest.mark.parametrize("outcome", ["failed", "skipped"])
def test_final_outcome_cannot_replace_observed_outcome(tmp_path, outcome):
    plugin = """import pytest
@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_logreport(report):
 if report.when == 'call' and report.outcome == ORIGINAL:
  print('CONTROLLED_OUTCOME_MUTATION:' + report.outcome + ',passed', flush=True)
  report.outcome = 'passed'
 yield
""".replace("ORIGINAL", repr(outcome))
    source = PASS.replace("assert 1 == 1", "assert False" if outcome == "failed" else "pytest.skip('not executed')")
    (tmp_path / "conftest.py").write_text(plugin, encoding="utf-8")
    result, descriptor, receipt = run_task(tmp_path, source)
    rejected_observation(result, descriptor, receipt, "case-report-outcome-changed:")
    stdout = (tmp_path / "RUN-CER/canonical-evidence/terminal/stdout.bin").read_bytes()
    assert ("CONTROLLED_OUTCOME_MUTATION:" + outcome + ",passed").encode("ascii") in stdout


@pytest.mark.parametrize("wrapper", [False, True], ids=["normal-hook", "outer-wrapper"])
def test_sessionfinish_unlogged_call_is_not_lost(tmp_path, wrapper):
    plugin = """import pytest
from _pytest.runner import runtestprotocol
DECORATOR
def pytest_sessionfinish(session, exitstatus):
YIELD
 reports = runtestprotocol(session.items[0], log=False)
 print('CONTROLLED_SESSIONFINISH_ATTEMPT:' + reports[1].outcome, flush=True)
""".replace("DECORATOR", "@pytest.hookimpl(hookwrapper=True, tryfirst=True)" if wrapper
             else "@pytest.hookimpl(trylast=True)").replace("YIELD", " yield" if wrapper else "")
    (tmp_path / "conftest.py").write_text(plugin, encoding="utf-8")
    result, descriptor, receipt = run_task(tmp_path, PASS)
    rejected_observation(result, descriptor, receipt,
                         "late-case-report:" if wrapper else "unlogged-case-report:")
    stdout = (tmp_path / "RUN-CER/canonical-evidence/terminal/stdout.bin").read_bytes()
    assert b"CONTROLLED_SESSIONFINISH_ATTEMPT:passed" in stdout


@pytest.mark.parametrize("typed_child", [False, True], ids=["no-child", "failed-child"])
def test_failed_child_downgrade_cannot_create_red(tmp_path, typed_child):
    """ADR-0041: only an observed failing child supports a parent downgrade."""
    if typed_child:
        source = sub_source("fixture", "fail")
    else:
        source = PASS
        plugin = """import pytest
@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_logreport(report):
 if report.when == 'call' and report.outcome == 'passed':
  report.outcome = 'failed'
 yield
"""
        (tmp_path / "conftest.py").write_text(plugin, encoding="utf-8")
    result, descriptor, receipt = run_task(tmp_path, source, stage="red")
    if not typed_child:
        rejected_observation(result, descriptor, receipt, "case-report-outcome-changed:", exit_code=1)
        return
    assert result["predicate_result"] is False and result["runtime_edges"] == []
    assert "case-unexpected-red" in result["case_evidence_error"]
    assert receipt["exit_code"] == 1 and receipt["cases"] == 1
    report = receipt["case_report"]
    assert report["errors"] == []
    assert [event["phase"] for event in report["events"]] == ["setup", "call", "teardown"]
    call = report["events"][1]
    assert call["outcome"] == "failed"
    assert call["assertion_failure"] is False and call["failure_ids"] == []
    with pytest.raises(ValueError):
        assertion_cases(descriptor, receipt)

import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile


TOOLS = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_router_recognizes_a_current_red_handoff():
    router = _load("route_plan_directory")
    assert router.next_stage_action(["red"]) == "implement"
    assert router.next_stage_action(["red", "implement"]) == "green"


def test_persisted_stage_router_requires_each_boundary():
    driver = _load("loop_plan_directory")
    with tempfile.TemporaryDirectory() as temp:
        run = Path(temp) / "RUN-001"
        observations = run / "observations"
        observations.mkdir(parents=True)
        (run / "stage-state.json").write_text(json.dumps({"stage": "red"}), encoding="utf-8")
        (observations / "red-observed.json").write_text(json.dumps({"stage": "red", "exit_code": 1}), encoding="utf-8")
        (run / "red-basis.v1.json").write_text("{}", encoding="utf-8")
        assert driver.route_staged_run(run) == "implement"
        (run / "red-basis.v1.json").write_text(json.dumps({
                "contract_hash": "sha256:contract",
                "validator_hash": "sha256:validator",
                "test_selector": "probe.py",
                "test_sha256": "sha256:probe",
            "pre_implementation_candidate": {"candidate_binding_hash": "sha256:before"},
        }), encoding="utf-8")
        (run / "implementation-successor.v1.json").write_text(json.dumps({
            "schema_version": "quick-dev-tdd-adapter.implementation-successor.v1",
            "status": "implementation-observed",
            "red_basis_sha256": "sha256:" + __import__("hashlib").sha256((run / "red-basis.v1.json").read_bytes()).hexdigest(),
            "contract_hash": "sha256:contract",
            "validator_hash": "sha256:validator",
            "pre_implementation_candidate": {"candidate_binding_hash": "sha256:before"},
            "post_implementation_candidate": {"candidate_binding_hash": "sha256:after"},
            "changed_paths": ["probe.py"],
            "authorizes": [],
        }), encoding="utf-8")
        (run / "stage-state.json").write_text(json.dumps({"stage": "implement"}), encoding="utf-8")
        assert driver.route_staged_run(run) == "green"
        (run / "stage-state.json").write_text(json.dumps({"stage": "green"}), encoding="utf-8")
        (observations / "green-observed.json").write_text(json.dumps({"stage": "green", "exit_code": 0}), encoding="utf-8")
        assert driver.route_staged_run(run) == "refactor"
        (run / "stage-state.json").write_text(json.dumps({"stage": "refactor"}), encoding="utf-8")
        (observations / "refactor-observed.json").write_text(json.dumps({"stage": "refactor", "exit_code": 0}), encoding="utf-8")
        assert driver.route_staged_run(run) == "slice-terminal"
        (run / "slice-ready-result.json").write_text("{}", encoding="utf-8")
        assert driver.route_staged_run(run) is None


def test_recovery_derives_refactor_without_stage_state():
    driver = _load("loop_plan_directory")
    with tempfile.TemporaryDirectory() as temp:
        run = Path(temp) / "RUN-001"
        observations = run / "observations"
        observations.mkdir(parents=True)
        (observations / "red-observed.json").write_text(json.dumps({"stage": "red", "exit_code": 1}), encoding="utf-8")
        (run / "red-basis.v1.json").write_text(json.dumps({
                "contract_hash": "sha256:contract", "validator_hash": "sha256:validator",
                "test_selector": "probe.py", "test_sha256": "sha256:probe",
            "pre_implementation_candidate": {"candidate_binding_hash": "sha256:before"},
        }), encoding="utf-8")
        (run / "implementation-successor.v1.json").write_text(json.dumps({
            "schema_version": "quick-dev-tdd-adapter.implementation-successor.v1",
            "status": "implementation-observed",
            "red_basis_sha256": "sha256:" + __import__("hashlib").sha256((run / "red-basis.v1.json").read_bytes()).hexdigest(),
            "contract_hash": "sha256:contract", "validator_hash": "sha256:validator",
            "pre_implementation_candidate": {"candidate_binding_hash": "sha256:before"},
            "post_implementation_candidate": {"candidate_binding_hash": "sha256:after"},
            "changed_paths": ["probe.py"], "authorizes": [],
        }), encoding="utf-8")
        (observations / "green-observed.json").write_text(json.dumps({"stage": "green", "exit_code": 0}), encoding="utf-8")

        assert not (run / "stage-state.json").exists()
        assert driver.route_staged_run(run) == "refactor"
        assert json.loads((run / "stage-state.json").read_text(encoding="utf-8"))["derived"] is True


def test_successor_derives_terminal_from_hash_bound_prior_red(tmp_path):
    driver = _load("loop_plan_directory")
    root = tmp_path
    predecessor = root / "logs" / "tdd-adapter" / "target" / "S0" / "RUN-OLD"
    prior = predecessor / "observations" / "red-observed.json"
    prior.parent.mkdir(parents=True)
    prior.write_text(json.dumps({"stage": "red", "exit_code": 1}), encoding="utf-8")
    successor = predecessor.parent / "RUN-NEW-SUCCESSOR"
    observations = successor / "observations"
    observations.mkdir(parents=True)
    digest = "sha256:" + __import__("hashlib").sha256(prior.read_bytes()).hexdigest()
    (successor / "prior-red-successor-evidence.v1.json").write_text(json.dumps({
        "schema_version": "quick-dev-tdd-adapter.prior-red-successor-evidence.v1",
        "prior_red": {"path": prior.relative_to(root).as_posix(), "sha256": digest},
    }), encoding="utf-8")
    (observations / "green-observed.json").write_text(json.dumps({"stage": "green", "exit_code": 0}), encoding="utf-8")
    (observations / "refactor-observed.json").write_text(json.dumps({"stage": "refactor", "exit_code": 0}), encoding="utf-8")

    assert driver.route_staged_run(successor) == "slice-terminal"


def test_legacy_active_run_requires_successor_when_prior_red_is_reusable(tmp_path):
    driver = _load("loop_plan_directory")
    run = tmp_path / "RUN-OLD"
    run.mkdir()
    (run / "red-basis.v1.json").write_text(json.dumps({"contract_hash": "sha256:old"}), encoding="utf-8")
    assert driver._has_execution_fingerprint(run) is False
    (run / "red-basis.v1.json").write_text(json.dumps({"execution_fingerprint": "sha256:current"}), encoding="utf-8")
    assert driver._has_execution_fingerprint(run) is True


def test_prior_red_handoff_execution_fingerprint_reuses_green_only_run(tmp_path):
    driver = _load("loop_plan_directory")
    run = tmp_path / "RUN-HANDOFF"
    run.mkdir()
    (run / "prior-red-handoff.v2.json").write_text(
        json.dumps({"execution_fingerprint": "sha256:prior-red"}), encoding="utf-8"
    )
    assert driver._has_execution_fingerprint(run) is True


def test_terminal_accepts_prior_red_handoff_with_green_and_refactor(tmp_path):
    driver = _load("loop_plan_directory")
    run = tmp_path / "logs" / "tdd-adapter" / "target" / "S5" / "RUN-HANDOFF"
    observations = run / "observations"
    observations.mkdir(parents=True)
    prior = run.parent / "RUN-RED" / "observations" / "red-observed.json"
    prior.parent.mkdir(parents=True)
    prior.write_text(json.dumps({"stage": "red", "exit_code": 1}), encoding="utf-8")
    digest = "sha256:" + __import__("hashlib").sha256(prior.read_bytes()).hexdigest()
    (run / "prior-red-handoff.v2.json").write_text(json.dumps({"red_observation": {"path": prior.relative_to(tmp_path).as_posix(), "sha256": digest}}), encoding="utf-8")
    (observations / "green-observed.json").write_text(json.dumps({"stage": "green", "exit_code": 0}), encoding="utf-8")
    (observations / "refactor-observed.json").write_text(json.dumps({"stage": "refactor", "exit_code": 0}), encoding="utf-8")
    assert driver.prior_red_observation_path(run) is not None


def test_prior_red_handoff_requires_current_contract_and_historical_successor(tmp_path):
    runner = _load("stage_lifecycle_runner")
    root = tmp_path
    plan_id, slice_id = "target", "S5"
    selector = "execution-plans/target/tools/red.py"
    test_path = root / selector
    test_path.parent.mkdir(parents=True)
    test_path.write_text("# RED selector\n", encoding="utf-8")
    old_contract_hash = "sha256:historical-contract"
    contract = {
        "plan_id": plan_id,
        "slices": [{"slice_id": slice_id, "tdd": {"red": {"test_selector": selector, "expected_failure_ids": ["EXPECTED-RED"]}}}],
        "slice_ready_repair_compatibility": {"predecessor_contract_hashes": [old_contract_hash]},
    }
    contract_path = root / "execution-plans" / plan_id / "implementation-contract.v1.json"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(json.dumps(contract, sort_keys=True), encoding="utf-8")
    validator_path = contract_path.parent / "tools" / "validate_all.py"
    validator_path.parent.mkdir(parents=True, exist_ok=True)
    validator_path.write_text("# validator\n", encoding="utf-8")
    predecessor = root / "logs" / "tdd-adapter" / plan_id / slice_id / "RUN-OLD"
    red = predecessor / "observations" / "red-observed.json"
    red.parent.mkdir(parents=True)
    red.write_text(json.dumps({"stage": "red", "exit_code": 1}), encoding="utf-8")
    basis = {
        "contract_hash": old_contract_hash,
        "validator_hash": "sha256:validator",
        "test_selector": selector,
        "test_sha256": "sha256:" + hashlib.sha256(test_path.read_bytes()).hexdigest(),
        "failure_intent": {"expected_failure_ids": ["EXPECTED-RED"]},
    }
    basis_path = predecessor / "red-basis.v1.json"
    basis_path.write_text(json.dumps(basis, sort_keys=True), encoding="utf-8")
    successor = {
        "schema_version": "quick-dev-tdd-adapter.implementation-successor.v1",
        "status": "implementation-observed",
        "red_basis_sha256": "sha256:" + hashlib.sha256(basis_path.read_bytes()).hexdigest(),
        "contract_hash": old_contract_hash,
        "validator_hash": "sha256:validator",
        "pre_implementation_candidate": {"candidate_hash": "sha256:before"},
        "post_implementation_candidate": {"candidate_hash": "sha256:after"},
        "changed_paths": ["execution-plans/target/tools/owner.py"],
        "authorizes": [],
    }
    (predecessor / "implementation-successor.v1.json").write_text(json.dumps(successor, sort_keys=True), encoding="utf-8")
    current = predecessor.parent / "RUN-NEW"
    current.mkdir()
    handoff = {
        "schema_version": "quick-dev-tdd-adapter.prior-red-handoff.v2",
        "plan_id": plan_id,
        "slice_id": slice_id,
        "run_id": current.name,
        "current_contract_hash": "sha256:" + hashlib.sha256(contract_path.read_bytes()).hexdigest(),
        "plan_binding": {
            "plan_id": plan_id,
            "path_type": "repo_path",
            "path": contract_path.parent.relative_to(root).as_posix(),
            "contract_path": "implementation-contract.v1.json",
            "validator_path": "tools/validate_all.py",
        },
        "execution_fingerprint": "sha256:current-run",
        "test_selector": selector,
        "test_sha256": basis["test_sha256"],
        "expected_failure_ids": ["EXPECTED-RED"],
        "red_observation": {"path": red.relative_to(root).as_posix(), "sha256": "sha256:" + hashlib.sha256(red.read_bytes()).hexdigest()},
        "red_basis": {"path": basis_path.relative_to(root).as_posix(), "sha256": "sha256:" + hashlib.sha256(basis_path.read_bytes()).hexdigest()},
    }
    handoff_path = current / "prior-red-handoff.v2.json"
    handoff_path.write_text(json.dumps(handoff, sort_keys=True), encoding="utf-8")

    assert runner.validate_implementation_successor(current) is True
    observations = current / "observations"
    observations.mkdir()
    for stage in ("green", "refactor"):
        (observations / f"{stage}-observed.json").write_text(
            json.dumps({"stage": stage, "exit_code": 0}), encoding="utf-8"
        )
    (current / "slice-ready-result.json").write_text(
        json.dumps({"predicate": "slice-ready", "status": "blocked"}), encoding="utf-8"
    )
    assert runner.derive_run_state(current) == "slice-terminal"
    router = _load("route_plan_directory")
    assert router._active_slice_action(root, contract_path.parent, slice_id) == "validate-slice"
    loop = _load("loop_plan_directory")
    assert loop._active_slice_run(root, contract_path.parent, slice_id) == (current, "slice-terminal")

    handoff["expected_failure_ids"] = ["TAMPERED"]
    handoff_path.write_text(json.dumps(handoff, sort_keys=True), encoding="utf-8")
    assert runner.validate_implementation_successor(current) is False

    handoff["expected_failure_ids"] = ["EXPECTED-RED"]
    handoff.pop("plan_binding")
    handoff_path.write_text(json.dumps(handoff, sort_keys=True), encoding="utf-8")
    assert runner.validate_implementation_successor(current) is False


def test_prior_red_handoff_writer_binds_the_physical_plan_path(tmp_path):
    lifecycle = _load("run_slice_lifecycle")
    plan = tmp_path / "execution-plans" / "dated-plan"
    context = {
        "plan_id": "target",
        "stage_results": {"red": {
            "execution_fingerprint": "sha256:fingerprint",
            "test_selector": "execution-plans/dated-plan/tools/red.py",
            "test_sha256": "sha256:test",
            "expected_failure_ids": ["EXPECTED-RED"],
            "validator_hash": "sha256:validator",
            "pre_implementation_candidate": {"candidate_hash": "sha256:before"},
            "command_id": "quick-dev-generated-red-S5",
            "contract_hash": "sha256:contract",
        }},
    }
    payload = lifecycle._prior_red_handoff_payload(
        tmp_path, plan, context, "S5", "RUN-NEW",
        {"path": "logs/prior-red.json", "sha256": "sha256:red"},
        {"path": "logs/prior-basis.json", "sha256": "sha256:basis"},
        "RUN-OLD", "s5-green", 0,
    )
    assert payload["plan_binding"] == {
        "plan_id": "target",
        "path_type": "repo_path",
        "path": "execution-plans/dated-plan",
        "contract_path": "implementation-contract.v1.json",
        "validator_path": "tools/validate_all.py",
    }

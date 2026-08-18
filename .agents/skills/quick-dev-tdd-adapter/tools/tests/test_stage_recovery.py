import importlib.util
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

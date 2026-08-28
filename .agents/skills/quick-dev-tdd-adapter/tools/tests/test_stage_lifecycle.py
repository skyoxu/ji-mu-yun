import importlib.util
import ast
import json
from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_red_only_stage_runner_is_available():
    driver = _load("loop_plan_directory")
    basis = driver.build_red_basis(
        {"id": "red", "executable": "py", "argv": [], "cwd": ".", "timeout_seconds": 1, "shell": False},
        {"test_selector": "tests/test_stage.py", "expected_failure_ids": ["QDR-S0-EXIT"]},
        {"head": "head-sha"}, "validator-sha", "contract-sha",
    )
    assert set(basis) == {"failure_intent", "test_selector", "contract_hash", "validator_hash", "pre_implementation_candidate"}
    assert basis["failure_intent"]["command_id"] == "red"


def test_run_slice_lifecycle_loads_context_outside_successor_guard():
    source = (TOOLS / "run_slice_lifecycle.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    assignments = [node for node in main.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "context" for target in node.targets)]
    assert assignments, "context must be initialized in main"
    assert isinstance(assignments[0].value, ast.Call)
    assert not any(isinstance(parent, ast.If) for parent in ast.walk(main)
                   if assignments[0] in ast.walk(parent) and parent is not assignments[0])


def test_execution_fingerprint_ignores_non_execution_metadata(tmp_path):
    builder = _load("build_slice_invocation")
    test = tmp_path / "test_target.py"
    test.write_text("def test_target():\n    assert True\n", encoding="utf-8")
    selected = {
        "slice_id": "S0", "behavior": "target behavior", "depends_on": [],
        "allowed_changes": {"production": ["src/**"], "tests": ["tests/**"]},
        "tdd": {"red": {"test_selector": "test_target.py", "expected_failure_ids": ["S0-RED"]}},
        "report_note": "first wording",
    }
    registry = {"schema_version": "registry.v1"}
    command = {"id": "command", "executable": "py", "argv": ["-3"], "cwd": ".", "timeout_seconds": 1, "shell": False}
    first, _ = builder._execution_fingerprint(tmp_path, selected, registry, command, command, [command], command, "sha256:validator")
    selected["report_note"] = "reworded report"
    second, _ = builder._execution_fingerprint(tmp_path, selected, registry, command, command, [command], command, "sha256:validator")
    selected["behavior"] = "changed behavior"
    third, _ = builder._execution_fingerprint(tmp_path, selected, registry, command, command, [command], command, "sha256:validator")

    assert first == second
    assert first != third


def test_prior_red_basis_is_hash_bound(tmp_path):
    lifecycle = _load("run_slice_lifecycle")
    run = tmp_path / "logs" / "tdd-adapter" / "target" / "S0" / "RUN-OLD"
    observation = run / "observations" / "red-observed.json"
    observation.parent.mkdir(parents=True)
    observation.write_text('{"stage":"red","exit_code":1,"commands_attempted":["red"]}', encoding="utf-8")
    basis = run / "red-basis.v1.json"
    basis.write_text('{"failure_intent":{}}', encoding="utf-8")
    reference = {"path": observation.relative_to(tmp_path).as_posix(), "sha256": "sha256:" + __import__("hashlib").sha256(observation.read_bytes()).hexdigest()}

    result = lifecycle._prior_red_basis(tmp_path, reference)

    assert result is not None
    assert result[0]["path"].endswith("red-basis.v1.json")
    assert result[1] == "RUN-OLD"


def test_terminal_close_reads_predecessor_red_without_copying_it(tmp_path, monkeypatch):
    runner_module = _load("stage_lifecycle_runner")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "snapshot.txt").write_text("current", encoding="utf-8")
    predecessor = tmp_path / "RUN-OLD"
    successor = tmp_path / "RUN-NEW"
    for source, stage, code in ((predecessor, "red", 1), (successor, "green", 0), (successor, "refactor", 0)):
        observation = source / "observations" / f"{stage}-observed.json"
        observation.parent.mkdir(parents=True, exist_ok=True)
        observation.write_text(json.dumps({"stage": stage, "exit_code": code}), encoding="utf-8")
    observed = []
    monkeypatch.setattr(runner_module, "compose", lambda _context, values, _store: (observed.extend(values) or {"schema_version": "bundle"}, {}, None))
    monkeypatch.setattr(runner_module, "persist_protocol_bundle", lambda *_args: None)
    runner = runner_module.LifecycleRunner(workspace, successor, ["snapshot.txt"])
    runner.stages = ["red", "green", "refactor"]

    runner.close({}, {}, observation_sources={"red": predecessor, "green": successor, "refactor": successor})

    assert [item["stage"] for item in observed] == ["red", "green", "refactor"]
    assert not (successor / "observations" / "red-observed.json").exists()

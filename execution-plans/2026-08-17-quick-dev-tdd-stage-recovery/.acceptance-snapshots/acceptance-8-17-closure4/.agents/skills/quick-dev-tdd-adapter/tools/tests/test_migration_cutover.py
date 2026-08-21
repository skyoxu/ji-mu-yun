import importlib.util
import json
from pathlib import Path
import sys
import tempfile


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_staged_cutover_guard_is_available():
    driver = _load("loop_plan_directory")
    assert driver.staged_cutover_guard(
        Path.cwd(),
        Path("execution-plans/2026-08-17-quick-dev-tdd-stage-recovery"),
    ) is True
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "repository"
        outside = Path(temp) / "outside"
        outside.mkdir()
        (outside / "implementation-contract.v1.json").write_text("{}", encoding="utf-8")
        assert driver.staged_cutover_guard(root, outside) is False


def test_8_17_dogfood_is_bound_to_staged_runner():
    plan = Path.cwd() / "execution-plans" / "2026-08-17-quick-dev-tdd-stage-recovery"
    registry = json.loads((plan / "command-registry.v1.json").read_text(encoding="utf-8"))
    command = next(item for item in registry["commands"] if item["id"] == "dogfood-8-17")
    assert command["argv"] == ["-3", "-B", "execution-plans/2026-08-17-quick-dev-tdd-stage-recovery/tools/dogfood_runner.py"]


def test_8_17_dogfood_red_context_has_the_lifecycle_identity_fields():
    plan = Path.cwd() / "execution-plans" / "2026-08-17-quick-dev-tdd-stage-recovery"
    spec = importlib.util.spec_from_file_location("stage_recovery_dogfood", plan / "tools" / "dogfood_runner.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    red_test = plan / "requirements-and-acceptance.md"
    red = {"id": "red", "argv": ["-B", "-m", "pytest", "probe.py", "-q"]}
    green = {"id": "green"}
    refactor = [{"id": "refactor"}]
    terminal = {"id": "terminal"}

    context = module._context("RUN-TEST", red, green, refactor, terminal, red_test)

    red_result = context["stage_results"]["red"]
    assert red_result["test_sha256"].startswith("sha256:")
    assert red_result["execution_fingerprint"].startswith("sha256:")
    assert red_result["test_selector"].endswith("requirements-and-acceptance.md")


def test_8_17_terminal_publishes_an_immutable_receipt_successor(tmp_path):
    plan = Path.cwd() / "execution-plans" / "2026-08-17-quick-dev-tdd-stage-recovery"
    spec = importlib.util.spec_from_file_location("stage_recovery_terminal", plan / "tools" / "terminal_full.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    receipt = {"contract_hash": "sha256:current", "status": "pass"}

    first = module.publish_canonical_receipt(tmp_path, receipt)
    successor = module.publish_canonical_receipt(tmp_path, {"contract_hash": "sha256:next", "status": "pass"})

    assert first.name == "quick-dev-implementation-complete.v1.json"
    assert successor.name.startswith("quick-dev-implementation-complete.")
    assert successor.name.endswith(".v1.json")
    assert json.loads(first.read_text(encoding="utf-8"))["contract_hash"] == "sha256:current"


def test_8_17_terminal_supports_read_only_receipt_replay(tmp_path, monkeypatch, capsys):
    plan = Path.cwd() / "execution-plans" / "2026-08-17-quick-dev-tdd-stage-recovery"
    spec = importlib.util.spec_from_file_location("stage_recovery_terminal_replay", plan / "tools" / "terminal_full.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    contract_hash = "sha256:" + __import__("hashlib").sha256((plan / "implementation-contract.v1.json").read_bytes()).hexdigest()
    registry_hash = "sha256:" + __import__("hashlib").sha256((plan / "command-registry.v1.json").read_bytes()).hexdigest()
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({
        "schema_version": "quick-dev-implementation-complete.v1",
        "plan_id": "quick-dev-tdd-stage-recovery",
        "predicate": "implementation-complete",
        "status": "pass",
        "contract_hash": contract_hash,
        "command_registry_hash": registry_hash,
        "terminal_command_id": "terminal-full",
        "authorizes": ["implementation-complete"],
    }), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["terminal_full.py", "--repository-root", str(Path.cwd()), "--verify-receipt", str(receipt)])

    assert module.main() == 0
    assert json.loads(capsys.readouterr().out)["predicate"] == "implementation-complete"
